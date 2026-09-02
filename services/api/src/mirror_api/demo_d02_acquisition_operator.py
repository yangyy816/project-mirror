"""Internal, non-HTTP operator for the D02 autonomous acquisition ledger.

The operator owns only short PostgreSQL transactions and one fixed ignored
private checkpoint.  It never calls ImageGen itself: ``call-session`` commits a
``CALL_STARTED`` event, emits the safe authorization facts, then consumes one
bounded newline-delimited result envelope from non-TTY stdin.  This keeps the
Provider side effect outside every database transaction while preserving the
same in-memory authorization token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import IO, Any, Final, NoReturn, Protocol, TextIO, cast

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from mirror_api.demo_d02_acquisition_identity import RUN_KEY_DIGEST, default_spec_identity
from mirror_api.demo_d02_r2_generation_receiver import (
    MAXIMUM_PROVIDER_RESULT_FILE_BYTES,
    BoundPngFile,
    D02R2PngReceiverError,
    bind_principal_existing_png_file,
    bind_principal_preallocated_destination,
)
from mirror_api.demo_d02_source_acquisition import (
    CallAuthorization,
    D02SourceAcquisitionError,
    D02SourceAcquisitionService,
    D02TwoCopyStorage,
    D02TwoCopyStorageError,
    DurableCandidateBytes,
)
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import (
    D02CohortSpec,
    D02SelectedSourceManifest,
    D02SourceAcquisitionEvent,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
)
from mirror_api.image_sanitizer import ImageSanitizationError, decode_canonical_rgb_image

MIGRATION_HEAD: Final = "demo_0015_d02_source_acq_pool"
_COMPATIBLE_DATABASE_HEADS: Final = frozenset(
    {
        MIGRATION_HEAD,
        "demo_0016_d06_ref_profile_queue",
        "demo_0017_d10_context_queue",
    }
)
LOCAL_INDEX_SCHEMA: Final = "mirror.private/D02LocalDurableIndex/v1"
LOCAL_ENTRY_SCHEMA: Final = "mirror.private/D02LocalDurableEntry/v1"
LOCAL_FILE_SCHEMA: Final = "mirror.private/D02LocalDurableFile/v1"
TRANCHE_RECONCILIATION_SCHEMA: Final = "mirror.demo/D02TrancheReconciliation/v1"
CHECKPOINT_RELATIVE: Final = Path(".private-handoff") / "D02_CURRENT_CHECKPOINT.json"
OBJECTS_RELATIVE: Final = Path(".private-handoff") / "d02-acquisition" / "objects"
LOCK_RELATIVE: Final = Path(".private-handoff") / ".D02_CURRENT_CHECKPOINT.lock"
MAXIMUM_RESULT_ENVELOPE_BYTES: Final = MAXIMUM_PROVIDER_RESULT_FILE_BYTES + 1_048_576
MAXIMUM_RECOVERY_CONTROL_BYTES: Final = 4096
EXPECTED_BRANCH: Final = "codex/p3-p7-d02-final-gate"
REQUIRED_BOOTSTRAP_ANCESTOR: Final = "6bea83742346e6ae817dd53812ab003b33712b21"

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_ID_RE: Final = re.compile(r"[0-9a-f]{32}\Z")
_CODE_RE: Final = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_ENV_NAME_RE: Final = re.compile(r"[A-Z_][A-Z0-9_]*\Z")

_INDEX_HEADER: Final[dict[str, object]] = {
    "schema_version": LOCAL_INDEX_SCHEMA,
    "checkpoint_id": "D02_AUTONOMY_BOOTSTRAP_LOCAL_INDEX",
    "authority": "LOCAL_AVAILABILITY_INDEX_ONLY",
    "business_authority": False,
    "budget_authority": False,
    "custodian": "D02_SUBSYSTEM_PRINCIPAL",
    "future_task_scope": "D02_ONLY",
    "retention": "PRESERVE_UNTIL_INTEGRATION_HANDOFF_COMPLETE",
    "cleanup": "EXPLICIT_OWNER_OR_INTEGRATION_PRINCIPAL_ACTION_ONLY",
}


class D02OperatorError(RuntimeError):
    """A redacted, allowlisted operator failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TransactionalSessionFactory(Protocol):
    def begin(self) -> AbstractContextManager[Session]: ...


@dataclass(frozen=True, slots=True)
class LocalFileFacts:
    relative_locator: str
    file_identity: tuple[int, int]
    media_type: str
    sha256: str
    byte_size: int
    width: int
    height: int

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": LOCAL_FILE_SCHEMA,
            "relative_locator": self.relative_locator,
            "file_identity": [self.file_identity[0], self.file_identity[1]],
            "media_type": self.media_type,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def parse(cls, value: object) -> LocalFileFacts:
        expected = {
            "schema_version",
            "relative_locator",
            "file_identity",
            "media_type",
            "sha256",
            "byte_size",
            "width",
            "height",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            _fail("PRIVATE_INDEX_FILE_FACTS_INVALID")
        if value.get("schema_version") != LOCAL_FILE_SCHEMA:
            _fail("PRIVATE_INDEX_FILE_SCHEMA_UNKNOWN")
        locator = value.get("relative_locator")
        identity = value.get("file_identity")
        media_type = value.get("media_type")
        digest = value.get("sha256")
        byte_size = value.get("byte_size")
        width = value.get("width")
        height = value.get("height")
        if not isinstance(locator, str):
            _fail("PRIVATE_INDEX_LOCATOR_INVALID")
        _validate_relative_locator(locator)
        if (
            not isinstance(identity, list)
            or len(identity) != 2
            or any(
                not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in identity
            )
        ):
            _fail("PRIVATE_INDEX_FILE_IDENTITY_INVALID")
        _require_digest(digest, "PRIVATE_INDEX_DIGEST_INVALID")
        if media_type not in {"image/png", "image/jpeg"}:
            _fail("PRIVATE_INDEX_MEDIA_TYPE_INVALID")
        if any(
            not isinstance(item, int) or isinstance(item, bool) or item < 1
            for item in (byte_size, width, height)
        ):
            _fail("PRIVATE_INDEX_FILE_DIMENSIONS_INVALID")
        return cls(
            relative_locator=locator,
            file_identity=(cast(int, identity[0]), cast(int, identity[1])),
            media_type=cast(str, media_type),
            sha256=cast(str, digest),
            byte_size=cast(int, byte_size),
            width=cast(int, width),
            height=cast(int, height),
        )


@dataclass(frozen=True, slots=True)
class LocalDurableEntry:
    run_id: str
    cohort_spec_id: str
    provider_ordinal: int
    selector_slot_id: str
    call_started_event_digest: str
    primary_relative_locator: str
    primary: LocalFileFacts | None
    backup: LocalFileFacts | None
    normalized_primary: LocalFileFacts | None
    normalized_backup: LocalFileFacts | None

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": LOCAL_ENTRY_SCHEMA,
            "run_id": self.run_id,
            "cohort_spec_id": self.cohort_spec_id,
            "provider_ordinal": self.provider_ordinal,
            "selector_slot_id": self.selector_slot_id,
            "call_started_event_digest": self.call_started_event_digest,
            "primary_relative_locator": self.primary_relative_locator,
            "primary": self.primary.payload() if self.primary is not None else None,
            "backup": self.backup.payload() if self.backup is not None else None,
            "normalized_primary": (
                self.normalized_primary.payload() if self.normalized_primary is not None else None
            ),
            "normalized_backup": (
                self.normalized_backup.payload() if self.normalized_backup is not None else None
            ),
        }

    @property
    def availability_digest(self) -> str:
        return _canonical_digest(LOCAL_ENTRY_SCHEMA, self.payload())

    @classmethod
    def parse(cls, value: object) -> LocalDurableEntry:
        expected = {
            "schema_version",
            "run_id",
            "cohort_spec_id",
            "provider_ordinal",
            "selector_slot_id",
            "call_started_event_digest",
            "primary_relative_locator",
            "primary",
            "backup",
            "normalized_primary",
            "normalized_backup",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            _fail("PRIVATE_INDEX_ENTRY_INVALID")
        if value.get("schema_version") != LOCAL_ENTRY_SCHEMA:
            _fail("PRIVATE_INDEX_ENTRY_SCHEMA_UNKNOWN")
        run_id = value.get("run_id")
        cohort_spec_id = value.get("cohort_spec_id")
        ordinal = value.get("provider_ordinal")
        slot = value.get("selector_slot_id")
        call_digest = value.get("call_started_event_digest")
        primary_locator = value.get("primary_relative_locator")
        if not isinstance(run_id, str) or _ID_RE.fullmatch(run_id) is None:
            _fail("PRIVATE_INDEX_RUN_ID_INVALID")
        if not isinstance(cohort_spec_id, str) or _ID_RE.fullmatch(cohort_spec_id) is None:
            _fail("PRIVATE_INDEX_SPEC_ID_INVALID")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal not in range(1, 51):
            _fail("PRIVATE_INDEX_ORDINAL_INVALID")
        if not isinstance(slot, str) or re.fullmatch(r"D02_SLOT_0[1-4]", slot) is None:
            _fail("PRIVATE_INDEX_SLOT_INVALID")
        _require_digest(call_digest, "PRIVATE_INDEX_CALL_DIGEST_INVALID")
        if not isinstance(primary_locator, str):
            _fail("PRIVATE_INDEX_LOCATOR_INVALID")
        _validate_relative_locator(primary_locator)
        raw_primary = value.get("primary")
        raw_backup = value.get("backup")
        raw_normalized_primary = value.get("normalized_primary")
        raw_normalized_backup = value.get("normalized_backup")
        parsed = cls(
            run_id=run_id,
            cohort_spec_id=cohort_spec_id,
            provider_ordinal=ordinal,
            selector_slot_id=slot,
            call_started_event_digest=cast(str, call_digest),
            primary_relative_locator=primary_locator,
            primary=LocalFileFacts.parse(raw_primary) if raw_primary is not None else None,
            backup=LocalFileFacts.parse(raw_backup) if raw_backup is not None else None,
            normalized_primary=(
                LocalFileFacts.parse(raw_normalized_primary)
                if raw_normalized_primary is not None
                else None
            ),
            normalized_backup=(
                LocalFileFacts.parse(raw_normalized_backup)
                if raw_normalized_backup is not None
                else None
            ),
        )
        if (
            parsed.primary is not None
            and parsed.primary.relative_locator != parsed.primary_relative_locator
        ) or (parsed.backup is not None and parsed.primary is None):
            _fail("PRIVATE_INDEX_ENTRY_STAGE_INVALID")
        if (parsed.normalized_primary is None) != (parsed.normalized_backup is None) or (
            parsed.normalized_primary is not None
            and (
                parsed.primary is None
                or parsed.normalized_primary.media_type != "image/jpeg"
                or parsed.normalized_backup is None
                or parsed.normalized_backup.media_type != "image/jpeg"
                or parsed.normalized_primary.sha256 != parsed.normalized_backup.sha256
            )
        ):
            _fail("PRIVATE_INDEX_NORMALIZED_STAGE_INVALID")
        return parsed


class D02LocalDurableIndex:
    """Atomic access to the one known ignored D02 checkpoint."""

    def __init__(self, *, workspace_root: Path) -> None:
        if not isinstance(workspace_root, Path) or not workspace_root.is_absolute():
            _fail("WORKSPACE_ROOT_INVALID")
        try:
            resolved = workspace_root.resolve(strict=True)
        except OSError as error:
            raise D02OperatorError("WORKSPACE_ROOT_INVALID") from error
        if resolved != workspace_root or not workspace_root.is_dir():
            _fail("WORKSPACE_ROOT_INVALID")
        self._workspace_root = workspace_root
        self._private_parent = workspace_root / CHECKPOINT_RELATIVE.parent
        self._checkpoint = workspace_root / CHECKPOINT_RELATIVE
        self._objects = workspace_root / OBJECTS_RELATIVE
        self._lock = workspace_root / LOCK_RELATIVE

    @property
    def objects_parent(self) -> Path:
        return self._objects

    def ensure_layout(self) -> None:
        _require_exact_directory(self._private_parent, code="PRIVATE_NAMESPACE_UNAVAILABLE")
        acquisition_parent = self._objects.parent
        _mkdir_exact(acquisition_parent)
        _mkdir_exact(self._objects)
        if not self._checkpoint.exists():
            document = {**_INDEX_HEADER, "updated_at": _now(), "entries": []}
            self._write_new_checkpoint(document)
        self._load_document()

    def primary_leaf(self, *, ordinal: int, call_started_event_digest: str) -> str:
        _require_digest(call_started_event_digest, "CALL_STARTED_DIGEST_INVALID")
        if ordinal not in range(1, 51):
            _fail("PROVIDER_ORDINAL_INVALID")
        return f"d02-o{ordinal:02d}-{call_started_event_digest[:16]}-primary.png"

    def backup_leaf(self, *, ordinal: int, call_started_event_digest: str) -> str:
        _require_digest(call_started_event_digest, "CALL_STARTED_DIGEST_INVALID")
        if ordinal not in range(1, 51):
            _fail("PROVIDER_ORDINAL_INVALID")
        return f"d02-o{ordinal:02d}-{call_started_event_digest[:16]}-backup.png"

    def record_primary(
        self,
        *,
        candidate: DurableCandidateBytes,
        primary_file: BoundPngFile,
        primary_path: Path,
    ) -> LocalDurableEntry:
        facts = self._file_facts(
            path=primary_path,
            bound=primary_file,
            candidate=candidate,
        )
        entry = LocalDurableEntry(
            run_id=candidate.run_id,
            cohort_spec_id=candidate.cohort_spec_id,
            provider_ordinal=candidate.provider_ordinal,
            selector_slot_id=candidate.selector_slot_id,
            call_started_event_digest=candidate.call_started_event_digest,
            primary_relative_locator=facts.relative_locator,
            primary=facts,
            backup=None,
            normalized_primary=None,
            normalized_backup=None,
        )
        return self._upsert_entry(entry)

    def allocate_call(self, authorization: CallAuthorization) -> LocalDurableEntry:
        primary_path = self._objects / self.primary_leaf(
            ordinal=authorization.provider_ordinal,
            call_started_event_digest=authorization.call_started_event_digest,
        )
        entry = LocalDurableEntry(
            run_id=authorization.run_id,
            cohort_spec_id=authorization.cohort_spec_id,
            provider_ordinal=authorization.provider_ordinal,
            selector_slot_id=authorization.selector_slot.slot_id,
            call_started_event_digest=authorization.call_started_event_digest,
            primary_relative_locator=self._relative_locator(primary_path),
            primary=None,
            backup=None,
            normalized_primary=None,
            normalized_backup=None,
        )
        return self._upsert_entry(entry)

    def record_backup(
        self,
        *,
        candidate: DurableCandidateBytes,
        backup_file: BoundPngFile,
        backup_path: Path,
    ) -> LocalDurableEntry:
        if candidate.backup_sha256 is None:
            _fail("BACKUP_NOT_RECONCILED")
        current = self.require_entry(candidate.call_started_event_digest)
        self._require_candidate_binding(current, candidate)
        if current.primary is None:
            _fail("PRIVATE_INDEX_PRIMARY_NOT_FOUND")
        backup = self._file_facts(path=backup_path, bound=backup_file, candidate=candidate)
        if backup.sha256 != current.primary.sha256:
            _fail("TWO_COPY_DIGEST_MISMATCH")
        updated = LocalDurableEntry(
            run_id=current.run_id,
            cohort_spec_id=current.cohort_spec_id,
            provider_ordinal=current.provider_ordinal,
            selector_slot_id=current.selector_slot_id,
            call_started_event_digest=current.call_started_event_digest,
            primary_relative_locator=current.primary_relative_locator,
            primary=current.primary,
            backup=backup,
            normalized_primary=current.normalized_primary,
            normalized_backup=current.normalized_backup,
        )
        return self._upsert_entry(updated)

    def require_entry(self, call_started_event_digest: str) -> LocalDurableEntry:
        _require_digest(call_started_event_digest, "CALL_STARTED_DIGEST_INVALID")
        entries = self._load_entries()
        matches = [
            entry
            for entry in entries
            if entry.call_started_event_digest == call_started_event_digest
        ]
        if len(matches) != 1:
            _fail("PRIVATE_INDEX_ENTRY_NOT_FOUND")
        return matches[0]

    def bind_primary(self, entry: LocalDurableEntry) -> BoundPngFile:
        if entry.primary is None:
            _fail("PRIVATE_INDEX_PRIMARY_NOT_FOUND")
        return self._bind(entry.primary)

    def bind_allocated_primary(self, entry: LocalDurableEntry) -> BoundPngFile:
        if entry.primary is not None:
            _fail("PRIVATE_INDEX_PRIMARY_ALREADY_BOUND")
        return bind_principal_existing_png_file(
            path=self._path_from_locator(entry.primary_relative_locator)
        )

    def primary_path(self, entry: LocalDurableEntry) -> Path:
        return self._path_from_locator(entry.primary_relative_locator)

    def bind_backup(self, entry: LocalDurableEntry) -> BoundPngFile:
        if entry.backup is None:
            _fail("PRIVATE_INDEX_BACKUP_NOT_FOUND")
        return self._bind(entry.backup)

    def count(self) -> int:
        return len(self._load_entries())

    def record_normalized_jpeg(
        self,
        *,
        call_started_event_digest: str,
        primary_path: Path,
        backup_path: Path,
        expected_sha256: str,
        expected_byte_size: int,
        expected_width: int,
        expected_height: int,
    ) -> LocalDurableEntry:
        entry = self.require_entry(call_started_event_digest)
        if entry.primary is None or entry.backup is None:
            _fail("PRIVATE_INDEX_CANDIDATE_NOT_DURABLE")
        primary = self._normalized_file_facts(
            path=primary_path,
            expected_sha256=expected_sha256,
            expected_byte_size=expected_byte_size,
            expected_width=expected_width,
            expected_height=expected_height,
        )
        backup = self._normalized_file_facts(
            path=backup_path,
            expected_sha256=expected_sha256,
            expected_byte_size=expected_byte_size,
            expected_width=expected_width,
            expected_height=expected_height,
        )
        if primary.sha256 != backup.sha256:
            _fail("TWO_COPY_DIGEST_MISMATCH")
        updated = LocalDurableEntry(
            run_id=entry.run_id,
            cohort_spec_id=entry.cohort_spec_id,
            provider_ordinal=entry.provider_ordinal,
            selector_slot_id=entry.selector_slot_id,
            call_started_event_digest=entry.call_started_event_digest,
            primary_relative_locator=entry.primary_relative_locator,
            primary=entry.primary,
            backup=entry.backup,
            normalized_primary=primary,
            normalized_backup=backup,
        )
        return self._upsert_entry(updated)

    def read_normalized_jpeg(self, entry: LocalDurableEntry) -> bytes:
        if entry.normalized_primary is None or entry.normalized_backup is None:
            _fail("PRIVATE_INDEX_NORMALIZED_NOT_FOUND")
        primary = self._read_local_file(entry.normalized_primary)
        backup = self._read_local_file(entry.normalized_backup)
        if primary != backup:
            _fail("TWO_COPY_DIGEST_MISMATCH")
        return primary

    def _upsert_entry(self, entry: LocalDurableEntry) -> LocalDurableEntry:
        with _checkpoint_lock(self._lock):
            document = self._load_document()
            entries = [
                LocalDurableEntry.parse(item) for item in cast(list[object], document["entries"])
            ]
            existing = next(
                (
                    item
                    for item in entries
                    if item.call_started_event_digest == entry.call_started_event_digest
                ),
                None,
            )
            if existing is not None:
                if existing == entry:
                    return existing
                if not _same_local_allocation(existing, entry):
                    _fail("PRIVATE_INDEX_ENTRY_COLLISION")
                if existing.primary is not None and entry.primary != existing.primary:
                    _fail("PRIVATE_INDEX_ENTRY_COLLISION")
                if existing.backup is not None and entry.backup != existing.backup:
                    _fail("PRIVATE_INDEX_ENTRY_COLLISION")
                if (
                    existing.normalized_primary is not None
                    and entry.normalized_primary != existing.normalized_primary
                ):
                    _fail("PRIVATE_INDEX_ENTRY_COLLISION")
                if (
                    existing.normalized_backup is not None
                    and entry.normalized_backup != existing.normalized_backup
                ):
                    _fail("PRIVATE_INDEX_ENTRY_COLLISION")
                entries = [entry if item == existing else item for item in entries]
            else:
                if any(
                    item.provider_ordinal == entry.provider_ordinal or item.run_id != entry.run_id
                    for item in entries
                ):
                    _fail("PRIVATE_INDEX_ENTRY_COLLISION")
                entries.append(entry)
            entries.sort(key=lambda item: item.provider_ordinal)
            updated = {
                **_INDEX_HEADER,
                "updated_at": _now(),
                "entries": [item.payload() for item in entries],
            }
            self._replace_checkpoint(updated)
            return self.require_entry(entry.call_started_event_digest)

    def _file_facts(
        self,
        *,
        path: Path,
        bound: BoundPngFile,
        candidate: DurableCandidateBytes,
    ) -> LocalFileFacts:
        received = bound.validate()
        if (
            received.sha256 != candidate.primary_sha256
            or received.byte_size != candidate.byte_size
            or received.width != candidate.width
            or received.height != candidate.height
        ):
            _fail("PRIVATE_INDEX_FILE_BINDING_MISMATCH")
        relative = self._relative_locator(path)
        return LocalFileFacts(
            relative_locator=relative,
            file_identity=bound.file_identity,
            media_type=candidate.media_type,
            sha256=received.sha256,
            byte_size=received.byte_size,
            width=received.width,
            height=received.height,
        )

    def _bind(self, facts: LocalFileFacts) -> BoundPngFile:
        if facts.media_type != "image/png":
            _fail("PRIVATE_INDEX_MEDIA_TYPE_INVALID")
        path = self._path_from_locator(facts.relative_locator)
        bound = bind_principal_existing_png_file(
            path=path,
            expected_identity=facts.file_identity,
        )
        received = bound.validate()
        if (
            received.sha256 != facts.sha256
            or received.byte_size != facts.byte_size
            or received.width != facts.width
            or received.height != facts.height
        ):
            _fail("PRIVATE_INDEX_FILE_BINDING_MISMATCH")
        return bound

    def _normalized_file_facts(
        self,
        *,
        path: Path,
        expected_sha256: str,
        expected_byte_size: int,
        expected_width: int,
        expected_height: int,
    ) -> LocalFileFacts:
        _require_digest(expected_sha256, "PRIVATE_INDEX_DIGEST_INVALID")
        relative = self._relative_locator(path)
        identity = _regular_file_identity(path, code="PRIVATE_INDEX_NORMALIZED_FILE_INVALID")
        content = _read_bound_file(
            path,
            expected_identity=identity,
            maximum_bytes=MAXIMUM_PROVIDER_RESULT_FILE_BYTES,
            code="PRIVATE_INDEX_NORMALIZED_FILE_INVALID",
        )
        if (
            len(content) != expected_byte_size
            or hashlib.sha256(content).hexdigest() != expected_sha256
        ):
            _fail("PRIVATE_INDEX_NORMALIZED_FILE_MISMATCH")
        try:
            decode_canonical_rgb_image(
                content,
                expected_width=expected_width,
                expected_height=expected_height,
            )
        except ImageSanitizationError as error:
            raise D02OperatorError("PRIVATE_INDEX_NORMALIZED_FILE_INVALID") from error
        return LocalFileFacts(
            relative_locator=relative,
            file_identity=identity,
            media_type="image/jpeg",
            sha256=expected_sha256,
            byte_size=expected_byte_size,
            width=expected_width,
            height=expected_height,
        )

    def _read_local_file(self, facts: LocalFileFacts) -> bytes:
        path = self._path_from_locator(facts.relative_locator)
        content = _read_bound_file(
            path,
            expected_identity=facts.file_identity,
            maximum_bytes=MAXIMUM_PROVIDER_RESULT_FILE_BYTES,
            code="PRIVATE_INDEX_FILE_BINDING_MISMATCH",
        )
        if len(content) != facts.byte_size or hashlib.sha256(content).hexdigest() != facts.sha256:
            _fail("PRIVATE_INDEX_FILE_BINDING_MISMATCH")
        return content

    def _relative_locator(self, path: Path) -> str:
        if not path.is_absolute():
            _fail("PRIVATE_INDEX_LOCATOR_INVALID")
        try:
            relative = path.relative_to(self._workspace_root)
        except ValueError as error:
            raise D02OperatorError("PRIVATE_INDEX_LOCATOR_INVALID") from error
        locator = relative.as_posix()
        _validate_relative_locator(locator)
        return locator

    def _path_from_locator(self, locator: str) -> Path:
        _validate_relative_locator(locator)
        pure = PurePosixPath(locator)
        path = self._workspace_root.joinpath(*pure.parts)
        if path.parent != self._objects:
            _fail("PRIVATE_INDEX_LOCATOR_INVALID")
        return path

    def _load_entries(self) -> list[LocalDurableEntry]:
        document = self._load_document()
        return [LocalDurableEntry.parse(item) for item in cast(list[object], document["entries"])]

    def _load_document(self) -> dict[str, object]:
        try:
            raw = self._checkpoint.read_bytes()
            decoded = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise D02OperatorError("PRIVATE_INDEX_UNREADABLE") from error
        expected_keys = {*_INDEX_HEADER, "updated_at", "entries"}
        if not isinstance(decoded, dict) or set(decoded) != expected_keys:
            _fail("PRIVATE_INDEX_SCHEMA_INVALID")
        if any(decoded.get(key) != value for key, value in _INDEX_HEADER.items()):
            _fail("PRIVATE_INDEX_AUTHORITY_MISMATCH")
        if not isinstance(decoded.get("updated_at"), str) or not isinstance(
            decoded.get("entries"), list
        ):
            _fail("PRIVATE_INDEX_SCHEMA_INVALID")
        entries = [LocalDurableEntry.parse(item) for item in cast(list[object], decoded["entries"])]
        if len({item.call_started_event_digest for item in entries}) != len(entries) or len(
            {item.provider_ordinal for item in entries}
        ) != len(entries):
            _fail("PRIVATE_INDEX_ENTRY_COLLISION")
        return cast(dict[str, object], decoded)

    def _write_new_checkpoint(self, document: Mapping[str, object]) -> None:
        data = _json_document(document)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(self._checkpoint, flags, 0o600)
            try:
                _write_all(descriptor, data)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as error:
            raise D02OperatorError("PRIVATE_INDEX_CREATE_FAILED") from error
        _sync_directory(self._private_parent)

    def _replace_checkpoint(self, document: Mapping[str, object]) -> None:
        data = _json_document(document)
        temporary = self._checkpoint.with_name(".D02_CURRENT_CHECKPOINT.json.incoming")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(temporary, flags, 0o600)
            try:
                _write_all(descriptor, data)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(temporary, self._checkpoint)
            _sync_directory(self._private_parent)
            if self._checkpoint.read_bytes() != data:
                _fail("PRIVATE_INDEX_REPLAY_FAILED")
            self._load_document()
        except D02OperatorError:
            _best_effort_unlink(temporary)
            raise
        except OSError as error:
            _best_effort_unlink(temporary)
            raise D02OperatorError("PRIVATE_INDEX_UPDATE_FAILED") from error

    @staticmethod
    def _require_candidate_binding(
        entry: LocalDurableEntry, candidate: DurableCandidateBytes
    ) -> None:
        if (
            entry.primary is None
            or entry.run_id != candidate.run_id
            or entry.cohort_spec_id != candidate.cohort_spec_id
            or entry.provider_ordinal != candidate.provider_ordinal
            or entry.selector_slot_id != candidate.selector_slot_id
            or entry.call_started_event_digest != candidate.call_started_event_digest
            or entry.primary_relative_locator != entry.primary.relative_locator
            or entry.primary.sha256 != candidate.primary_sha256
            or entry.primary.byte_size != candidate.byte_size
            or entry.primary.width != candidate.width
            or entry.primary.height != candidate.height
        ):
            _fail("PRIVATE_INDEX_CANDIDATE_BINDING_MISMATCH")


class D02AcquisitionOperator:
    """Short-transaction application boundary for one autonomous D02 run."""

    def __init__(
        self,
        *,
        session_factory: TransactionalSessionFactory,
        durable_index: D02LocalDurableIndex,
    ) -> None:
        self._sessions = session_factory
        self._index = durable_index
        self._storage = D02TwoCopyStorage()

    def bootstrap(self) -> dict[str, object]:
        self._index.ensure_layout()
        with self._sessions.begin() as session:
            _require_database_head(session)
            service = D02SourceAcquisitionService(session)
            spec = service.register_spec(default_spec_identity())
            run = service.create_run(cohort_spec_id=spec.id, run_key_digest=RUN_KEY_DIGEST)
            result = _run_status(run, spec=spec)
        result["private_entry_count"] = self._index.count()
        return result

    def status(self) -> dict[str, object]:
        self._index.ensure_layout()
        with self._sessions.begin() as session:
            _require_database_head(session)
            run = session.scalar(select(D02SourceAcquisitionRun))
            spec = session.scalar(select(D02CohortSpec))
            if run is None or spec is None:
                return {
                    "status": "READY_NOT_STARTED",
                    "migration_head": MIGRATION_HEAD,
                    "provider_calls": 0,
                    "budget": "0/50",
                    "accepted_sources": "0/4",
                    "private_entry_count": self._index.count(),
                }
            result = _run_status(run, spec=spec)
            result["candidate_count"] = int(
                session.scalar(select(func.count()).select_from(D02SourceCandidate)) or 0
            )
            result["event_count"] = int(
                session.scalar(select(func.count()).select_from(D02SourceAcquisitionEvent)) or 0
            )
            manifest = session.scalar(select(D02SelectedSourceManifest))
            result["manifest_finalized"] = manifest is not None
        result["private_entry_count"] = self._index.count()
        return result

    def call_session(self, *, run_id: str, input_stream: IO[bytes], output: TextIO) -> int:
        self._index.ensure_layout()
        if bool(getattr(input_stream, "isatty", lambda: False)()):
            _fail("PROVIDER_RESULT_STDIN_MUST_BE_NON_TTY")
        with self._sessions.begin() as session:
            _require_database_head(session)
            authorization = D02SourceAcquisitionService(session).start_call(run_id=run_id)
        _emit(
            output,
            {
                "status": "CALL_STARTED",
                "run_id": authorization.run_id,
                "cohort_spec_id": authorization.cohort_spec_id,
                "provider_ordinal": authorization.provider_ordinal,
                "selector_slot_id": authorization.selector_slot.slot_id,
                "declared_age_band": authorization.selector_slot.declared_age_band,
                "style_context": authorization.selector_slot.style_context,
                "tranche_number": authorization.tranche_number,
                "call_started_event_digest": authorization.call_started_event_digest,
            },
        )
        output.flush()
        try:
            envelope = _read_result_envelope(input_stream)
        except D02OperatorError:
            self._record_uncertain(authorization)
            raise
        outcome = envelope.get("outcome")
        if outcome == "UNCERTAIN":
            self._record_uncertain(authorization)
            _emit(output, {"status": "FAILED_CLOSED", "code": "PROVIDER_OUTCOME_UNCERTAIN"})
            return 3
        if outcome == "NO_RESULT":
            detail = envelope.get("detail_code")
            if not isinstance(detail, str) or _CODE_RE.fullmatch(detail) is None:
                self._record_uncertain(authorization)
                _fail("PROVIDER_NO_RESULT_CODE_INVALID")
            with self._sessions.begin() as session:
                _require_database_head(session)
                D02SourceAcquisitionService(session).record_call_consumed_no_result(
                    authorization=authorization,
                    detail_code=detail,
                )
            _emit(
                output,
                {
                    "status": "CALL_CONSUMED_NO_RESULT",
                    "provider_ordinal": authorization.provider_ordinal,
                    "detail_code": detail,
                },
            )
            return 0
        if outcome != "RESULT" or "result" not in envelope:
            self._record_uncertain(authorization)
            _fail("PROVIDER_RESULT_ENVELOPE_INVALID")
        primary_leaf = self._index.primary_leaf(
            ordinal=authorization.provider_ordinal,
            call_started_event_digest=authorization.call_started_event_digest,
        )
        primary_path = self._index.objects_parent / primary_leaf
        self._allocate_call_index_with_recovery(
            authorization=authorization,
            input_stream=input_stream,
            output=output,
        )
        try:
            primary_destination = bind_principal_preallocated_destination(
                parent=self._index.objects_parent,
                leaf_name=primary_leaf,
            )
            materialization = self._storage.persist_primary_png(
                authorization=authorization,
                result_metadata=envelope["result"],
                primary_destination=primary_destination,
            )
            candidate = materialization.candidate
            primary_file = materialization.primary_file
        except D02R2PngReceiverError:
            with self._sessions.begin() as session:
                _require_database_head(session)
                D02SourceAcquisitionService(session).record_materialization_failed(
                    authorization=authorization,
                    detail_code="PRIMARY_DESTINATION_FAILED",
                )
            _emit(
                output,
                {
                    "status": "PAUSED_INFRASTRUCTURE",
                    "provider_ordinal": authorization.provider_ordinal,
                    "code": "PRIMARY_DESTINATION_FAILED",
                },
            )
            return 3
        except D02TwoCopyStorageError as error:
            if error.durable_candidate is None:
                with self._sessions.begin() as session:
                    _require_database_head(session)
                    D02SourceAcquisitionService(session).record_materialization_failed(
                        authorization=authorization,
                        detail_code=error.code,
                    )
                _emit(
                    output,
                    {
                        "status": "PAUSED_INFRASTRUCTURE",
                        "provider_ordinal": authorization.provider_ordinal,
                        "code": error.code,
                    },
                )
                return 3
            candidate = error.durable_candidate
            try:
                primary_file = bind_principal_existing_png_file(path=primary_path)
                _require_file_matches_candidate(primary_file, candidate)
            except (D02R2PngReceiverError, D02OperatorError) as binding_error:
                raise D02OperatorError("PRIMARY_PUBLISHED_BINDING_UNAVAILABLE") from binding_error
        self._record_primary_index_with_recovery(
            candidate=candidate,
            primary_file=primary_file,
            primary_path=primary_path,
            input_stream=input_stream,
            output=output,
        )
        with self._sessions.begin() as session:
            _require_database_head(session)
            row = D02SourceAcquisitionService(session).record_materialized_candidate(
                candidate=candidate
            )
            candidate_id = row.id
        try:
            durable = self._complete_backup(candidate_id=candidate_id, primary_file=primary_file)
        except (D02TwoCopyStorageError, D02R2PngReceiverError, D02OperatorError) as error:
            code = getattr(error, "code", "BACKUP_STORAGE_FAILED")
            _emit(
                output,
                {
                    "status": "PAUSED_INFRASTRUCTURE",
                    "provider_ordinal": authorization.provider_ordinal,
                    "candidate_id": candidate_id,
                    "code": code,
                },
            )
            return 3
        _emit(
            output,
            {
                "status": "CANDIDATE_DURABLE",
                "provider_ordinal": durable.provider_ordinal,
                "candidate_id": candidate_id,
                "output_id": durable.output_id,
                "sha256": durable.primary_sha256,
                "byte_size": durable.byte_size,
                "width": durable.width,
                "height": durable.height,
            },
        )
        return 0

    def recover_primary(self, *, run_id: str, call_started_event_digest: str) -> dict[str, object]:
        self._index.ensure_layout()
        entry = self._index.require_entry(call_started_event_digest)
        if entry.run_id != run_id or entry.backup is not None:
            _fail("PRIMARY_RECOVERY_ENTRY_INVALID")
        with self._sessions.begin() as session:
            _require_database_head(session)
            authorization = D02SourceAcquisitionService(session).authorize_primary_recovery(
                run_id=run_id,
                call_started_event_digest=call_started_event_digest,
            )
        primary_file = (
            self._index.bind_primary(entry)
            if entry.primary is not None
            else self._index.bind_allocated_primary(entry)
        )
        recovered = self._storage.recover_primary_png(
            authorization=authorization,
            primary_file=primary_file,
        )
        if entry.primary is None:
            entry = self._index.record_primary(
                candidate=recovered.candidate,
                primary_file=recovered.primary_file,
                primary_path=self._index.primary_path(entry),
            )
        with self._sessions.begin() as session:
            _require_database_head(session)
            row = D02SourceAcquisitionService(session).record_materialized_candidate(
                candidate=recovered.candidate
            )
            candidate_id = row.id
        durable = self._complete_backup(
            candidate_id=candidate_id,
            primary_file=recovered.primary_file,
        )
        return {
            "status": "CANDIDATE_DURABLE",
            "provider_ordinal": durable.provider_ordinal,
            "candidate_id": candidate_id,
            "sha256": durable.primary_sha256,
        }

    def repair_backup(self, *, candidate_id: str) -> dict[str, object]:
        self._index.ensure_layout()
        with self._sessions.begin() as session:
            _require_database_head(session)
            primary = D02SourceAcquisitionService(session).authorize_backup_repair(
                candidate_id=candidate_id
            )
        entry = self._index.require_entry(primary.call_started_event_digest)
        durable = self._complete_backup(
            candidate_id=candidate_id,
            primary_file=self._index.bind_primary(entry),
            primary=primary,
            entry=entry,
        )
        return {
            "status": "CANDIDATE_DURABLE",
            "provider_ordinal": durable.provider_ordinal,
            "candidate_id": candidate_id,
            "sha256": durable.primary_sha256,
        }

    def fail_open_uncertain(self, *, run_id: str, call_started_event_digest: str) -> None:
        with self._sessions.begin() as session:
            _require_database_head(session)
            D02SourceAcquisitionService(session).fail_open_call_as_provider_outcome_uncertain(
                run_id=run_id,
                call_started_event_digest=call_started_event_digest,
            )

    def pause_candidate(self, *, candidate_id: str, stage_code: str) -> None:
        with self._sessions.begin() as session:
            _require_database_head(session)
            D02SourceAcquisitionService(session).pause_infrastructure_for_candidate(
                candidate_id=candidate_id,
                stage_code=stage_code,
            )

    def resume_infrastructure(self, *, run_id: str, review_digest: str) -> None:
        with self._sessions.begin() as session:
            _require_database_head(session)
            D02SourceAcquisitionService(session).resume_infrastructure(
                run_id=run_id,
                review_digest=review_digest,
            )

    def resume_content_review(self, *, run_id: str, review_digest: str) -> None:
        with self._sessions.begin() as session:
            _require_database_head(session)
            D02SourceAcquisitionService(session).resume_content_review(
                run_id=run_id,
                review_digest=review_digest,
            )

    def reconcile_tranche(self, *, run_id: str, tranche_number: int) -> str:
        with self._sessions.begin() as session:
            _require_database_head(session)
            events = list(
                session.scalars(
                    select(D02SourceAcquisitionEvent)
                    .where(
                        D02SourceAcquisitionEvent.acquisition_run_id == run_id,
                        D02SourceAcquisitionEvent.provider_ordinal.between(
                            (tranche_number - 1) * 10 + 1, tranche_number * 10
                        ),
                    )
                    .order_by(D02SourceAcquisitionEvent.event_sequence)
                )
            )
            digest = _canonical_digest(
                TRANCHE_RECONCILIATION_SCHEMA,
                {
                    "acquisition_run_id": run_id,
                    "tranche_number": tranche_number,
                    "ordered_event_digests": [event.content_digest for event in events],
                },
            )
            D02SourceAcquisitionService(session).reconcile_tranche(
                run_id=run_id,
                tranche_number=tranche_number,
                reconciliation_digest=digest,
            )
            return digest

    def _record_uncertain(self, authorization: CallAuthorization) -> None:
        with self._sessions.begin() as session:
            _require_database_head(session)
            D02SourceAcquisitionService(session).record_provider_outcome_uncertain(
                authorization=authorization
            )

    def _record_primary_index_with_recovery(
        self,
        *,
        candidate: DurableCandidateBytes,
        primary_file: BoundPngFile,
        primary_path: Path,
        input_stream: IO[bytes],
        output: TextIO,
    ) -> LocalDurableEntry:
        """Keep the exact in-memory file capability alive until its index commits.

        A failed index write must never be misclassified as a materialization
        failure and must not open a new Provider call.  The operator therefore
        remains in the same long-lived session and accepts only an explicit
        local retry control message after the operator has repaired the
        checkpoint condition.
        """

        while True:
            try:
                return self._index.record_primary(
                    candidate=candidate,
                    primary_file=primary_file,
                    primary_path=primary_path,
                )
            except D02OperatorError as error:
                _emit(
                    output,
                    {
                        "status": "PRIMARY_PUBLISHED_INDEX_RETRY_REQUIRED",
                        "provider_ordinal": candidate.provider_ordinal,
                        "call_started_event_digest": candidate.call_started_event_digest,
                        "code": error.code,
                    },
                )
                control = _read_recovery_control(input_stream)
                if control.get("action") != "RETRY_PRIMARY_INDEX":
                    _fail("PRIMARY_PUBLISHED_INDEX_RECOVERY_INVALID")

    def _allocate_call_index_with_recovery(
        self,
        *,
        authorization: CallAuthorization,
        input_stream: IO[bytes],
        output: TextIO,
    ) -> LocalDurableEntry:
        while True:
            try:
                return self._index.allocate_call(authorization)
            except D02OperatorError as error:
                _emit(
                    output,
                    {
                        "status": "RESULT_RECEIVED_ALLOCATION_RETRY_REQUIRED",
                        "provider_ordinal": authorization.provider_ordinal,
                        "call_started_event_digest": authorization.call_started_event_digest,
                        "code": error.code,
                    },
                )
                control = _read_recovery_control(input_stream)
                if control.get("action") != "RETRY_PRIMARY_ALLOCATION":
                    _fail("PRIMARY_ALLOCATION_RECOVERY_INVALID")

    def _complete_backup(
        self,
        *,
        candidate_id: str,
        primary_file: BoundPngFile,
        primary: DurableCandidateBytes | None = None,
        entry: LocalDurableEntry | None = None,
    ) -> DurableCandidateBytes:
        if primary is None:
            with self._sessions.begin() as session:
                _require_database_head(session)
                primary = D02SourceAcquisitionService(session).authorize_backup_repair(
                    candidate_id=candidate_id
                )
        if entry is None:
            entry = self._index.require_entry(primary.call_started_event_digest)
        backup_leaf = self._index.backup_leaf(
            ordinal=primary.provider_ordinal,
            call_started_event_digest=primary.call_started_event_digest,
        )
        backup_path = self._index.objects_parent / backup_leaf
        if entry.backup is not None:
            backup_file = self._index.bind_backup(entry)
            durable = self._storage.reconcile_existing_backup(
                primary=primary,
                primary_file=primary_file,
                backup_file=backup_file,
            )
        elif backup_path.exists():
            backup_file = bind_principal_existing_png_file(path=backup_path)
            durable = self._storage.reconcile_existing_backup(
                primary=primary,
                primary_file=primary_file,
                backup_file=backup_file,
            )
            entry = self._index.record_backup(
                candidate=durable,
                backup_file=backup_file,
                backup_path=backup_path,
            )
        else:
            durable = self._storage.repair_backup(
                primary=primary,
                primary_file=primary_file,
                backup_destination=bind_principal_preallocated_destination(
                    parent=self._index.objects_parent,
                    leaf_name=backup_leaf,
                ),
            )
            backup_file = bind_principal_existing_png_file(path=backup_path)
            entry = self._index.record_backup(
                candidate=durable,
                backup_file=backup_file,
                backup_path=backup_path,
            )
        with self._sessions.begin() as session:
            _require_database_head(session)
            D02SourceAcquisitionService(session).record_backup_reconciled(
                candidate=durable,
                recovery_digest=entry.availability_digest,
            )
        return durable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal D02 autonomous acquisition operator")
    parser.add_argument("--database-env", default="D02_DATABASE_URL")
    parser.add_argument("--environment", required=True, choices=("development", "test", "ci"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    commands.add_parser("status")
    call = commands.add_parser("call-session")
    call.add_argument("--run-id", required=True)
    recover = commands.add_parser("recover-primary")
    recover.add_argument("--run-id", required=True)
    recover.add_argument("--call-started-event-digest", required=True)
    repair = commands.add_parser("repair-backup")
    repair.add_argument("--candidate-id", required=True)
    uncertain = commands.add_parser("fail-open-uncertain")
    uncertain.add_argument("--run-id", required=True)
    uncertain.add_argument("--call-started-event-digest", required=True)
    pause = commands.add_parser("pause-candidate")
    pause.add_argument("--candidate-id", required=True)
    pause.add_argument("--stage-code", required=True)
    resume_infra = commands.add_parser("resume-infrastructure")
    resume_infra.add_argument("--run-id", required=True)
    resume_infra.add_argument("--review-digest", required=True)
    resume_content = commands.add_parser("resume-content-review")
    resume_content.add_argument("--run-id", required=True)
    resume_content.add_argument("--review-digest", required=True)
    tranche = commands.add_parser("reconcile-tranche")
    tranche.add_argument("--run-id", required=True)
    tranche.add_argument("--tranche-number", required=True, type=int)
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    input_stream: IO[bytes] | None = None,
    output: TextIO | None = None,
    error_output: TextIO | None = None,
) -> int:
    stream = output or sys.stdout
    error_stream = error_output or sys.stderr
    engine = None
    try:
        args = build_parser().parse_args(argv)
        database_url = _database_url(cast(str, args.database_env))
        workspace_root = Path.cwd()
        _validate_workspace_authority(
            workspace_root=workspace_root,
            environment=cast(str, args.environment),
        )
        index = D02LocalDurableIndex(workspace_root=workspace_root)
        engine = create_engine(database_url, pool_pre_ping=True)
        sessions = sessionmaker(engine, expire_on_commit=False)
        operator = D02AcquisitionOperator(session_factory=sessions, durable_index=index)
        command = cast(str, args.command)
        if command == "bootstrap":
            result = operator.bootstrap()
        elif command == "status":
            result = operator.status()
        elif command == "call-session":
            return operator.call_session(
                run_id=cast(str, args.run_id),
                input_stream=input_stream or sys.stdin.buffer,
                output=stream,
            )
        elif command == "recover-primary":
            result = operator.recover_primary(
                run_id=cast(str, args.run_id),
                call_started_event_digest=cast(str, args.call_started_event_digest),
            )
        elif command == "repair-backup":
            result = operator.repair_backup(candidate_id=cast(str, args.candidate_id))
        elif command == "fail-open-uncertain":
            operator.fail_open_uncertain(
                run_id=cast(str, args.run_id),
                call_started_event_digest=cast(str, args.call_started_event_digest),
            )
            result = {"status": "FAILED_CLOSED", "code": "PROVIDER_OUTCOME_UNCERTAIN"}
        elif command == "pause-candidate":
            operator.pause_candidate(
                candidate_id=cast(str, args.candidate_id),
                stage_code=cast(str, args.stage_code),
            )
            result = {"status": "PAUSED_INFRASTRUCTURE", "candidate_id": args.candidate_id}
        elif command == "resume-infrastructure":
            operator.resume_infrastructure(
                run_id=cast(str, args.run_id),
                review_digest=cast(str, args.review_digest),
            )
            result = {"status": "ACTIVE", "run_id": args.run_id}
        elif command == "resume-content-review":
            operator.resume_content_review(
                run_id=cast(str, args.run_id),
                review_digest=cast(str, args.review_digest),
            )
            result = {"status": "ACTIVE", "run_id": args.run_id}
        elif command == "reconcile-tranche":
            digest = operator.reconcile_tranche(
                run_id=cast(str, args.run_id),
                tranche_number=cast(int, args.tranche_number),
            )
            result = {
                "status": "TRANCHE_RECONCILED",
                "tranche_number": args.tranche_number,
                "reconciliation_digest": digest,
            }
        else:
            _fail("COMMAND_NOT_SUPPORTED")
        _emit(stream, result)
        return 0
    except (
        D02OperatorError,
        D02SourceAcquisitionError,
        D02TwoCopyStorageError,
        D02R2PngReceiverError,
    ) as error:
        _emit(error_stream, {"status": "FAILED", "code": error.code})
        return 2
    except SQLAlchemyError:
        _emit(error_stream, {"status": "FAILED", "code": "DATABASE_OPERATION_FAILED"})
        return 2
    except Exception:
        _emit(error_stream, {"status": "FAILED", "code": "INTERNAL_OPERATOR_FAILURE"})
        return 2
    finally:
        if engine is not None:
            engine.dispose()


def _run_status(run: D02SourceAcquisitionRun, *, spec: D02CohortSpec) -> dict[str, object]:
    return {
        "status": run.run_state,
        "migration_head": MIGRATION_HEAD,
        "cohort_spec_id": spec.id,
        "cohort_spec_digest": spec.content_digest,
        "run_id": run.id,
        "run_digest": run.content_digest,
        "provider_calls": run.budget_consumed,
        "budget": f"{run.budget_consumed}/50",
        "next_ordinal": run.next_ordinal,
        "open_call_ordinal": run.open_call_ordinal,
        "accepted_sources": f"{run.accepted_count}/4",
        "content_review_epoch": run.content_review_epoch,
        "terminal_reason": run.terminal_reason,
    }


def _read_result_envelope(input_stream: IO[bytes]) -> dict[str, object]:
    line = input_stream.readline(MAXIMUM_RESULT_ENVELOPE_BYTES + 1)
    if not line:
        _fail("PROVIDER_OUTCOME_UNCERTAIN")
    if len(line) > MAXIMUM_RESULT_ENVELOPE_BYTES:
        _fail("PROVIDER_RESULT_ENVELOPE_TOO_LARGE")
    if not line.endswith(b"\n"):
        _fail("PROVIDER_RESULT_ENVELOPE_NOT_TERMINATED")
    try:
        value = json.loads(line[:-1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise D02OperatorError("PROVIDER_RESULT_ENVELOPE_INVALID") from error
    if not isinstance(value, dict) or set(value) not in (
        {"outcome", "result"},
        {"outcome", "detail_code"},
        {"outcome"},
    ):
        _fail("PROVIDER_RESULT_ENVELOPE_INVALID")
    return cast(dict[str, object], value)


def _read_recovery_control(input_stream: IO[bytes]) -> dict[str, object]:
    line = input_stream.readline(MAXIMUM_RECOVERY_CONTROL_BYTES + 1)
    if not line or len(line) > MAXIMUM_RECOVERY_CONTROL_BYTES or not line.endswith(b"\n"):
        _fail("PRIMARY_PUBLISHED_INDEX_RECOVERY_INTERRUPTED")
    try:
        value = json.loads(line[:-1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise D02OperatorError("PRIMARY_PUBLISHED_INDEX_RECOVERY_INVALID") from error
    if not isinstance(value, dict) or set(value) != {"action"}:
        _fail("PRIMARY_PUBLISHED_INDEX_RECOVERY_INVALID")
    return cast(dict[str, object], value)


def _database_url(name: str) -> str:
    if _ENV_NAME_RE.fullmatch(name) is None:
        _fail("DATABASE_ENV_NAME_INVALID")
    value = os.getenv(name)
    if not value or not value.startswith(("postgresql://", "postgresql+psycopg://")):
        _fail("POSTGRESQL_DATABASE_URL_REQUIRED")
    return value


def _validate_workspace_authority(*, workspace_root: Path, environment: str) -> None:
    if environment not in {"development", "test", "ci"}:
        _fail("D02_OPERATOR_ENVIRONMENT_NOT_AUTHORIZED")
    configured_environment = os.getenv("APP_ENV")
    if configured_environment is None:
        _fail("D02_OPERATOR_ENVIRONMENT_MISSING")
    if configured_environment != environment:
        _fail("D02_OPERATOR_ENVIRONMENT_MISMATCH")
    root = _git_output(workspace_root, "rev-parse", "--show-toplevel")
    try:
        reported_root = Path(root).resolve(strict=True)
    except OSError as error:
        raise D02OperatorError("D02_WORKTREE_MISMATCH") from error
    if reported_root != workspace_root:
        _fail("D02_WORKTREE_MISMATCH")
    if _git_output(workspace_root, "branch", "--show-current") != EXPECTED_BRANCH:
        _fail("D02_BRANCH_MISMATCH")
    if _git_output(workspace_root, "status", "--short", "--untracked-files=no"):
        _fail("D02_TRACKED_WORKTREE_NOT_CLEAN")
    git_executable = _git_executable()
    ancestor = subprocess.run(  # noqa: S603 - fixed executable and constant arguments only.
        [
            git_executable,
            "merge-base",
            "--is-ancestor",
            REQUIRED_BOOTSTRAP_ANCESTOR,
            "HEAD",
        ],
        cwd=workspace_root,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if ancestor.returncode != 0:
        _fail("D02_BOOTSTRAP_ANCESTOR_MISSING")
    ignored = subprocess.run(  # noqa: S603 - fixed executable and constant arguments only.
        [git_executable, "check-ignore", "-q", "--", CHECKPOINT_RELATIVE.as_posix()],
        cwd=workspace_root,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if ignored.returncode != 0:
        _fail("D02_PRIVATE_CHECKPOINT_NOT_IGNORED")
    for reference in ("MERGE_HEAD", "CHERRY_PICK_HEAD"):
        active = subprocess.run(  # noqa: S603 - reference comes from a fixed allowlist above.
            [git_executable, "rev-parse", "-q", "--verify", reference],
            cwd=workspace_root,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if active.returncode == 0:
            _fail("D02_GIT_OPERATION_IN_PROGRESS")
    for rebase_name in ("rebase-merge", "rebase-apply"):
        git_path = _git_output(workspace_root, "rev-parse", "--git-path", rebase_name)
        candidate = Path(git_path)
        if not candidate.is_absolute():
            candidate = workspace_root / candidate
        if candidate.exists():
            _fail("D02_GIT_OPERATION_IN_PROGRESS")


def _git_output(workspace_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(  # noqa: S603 - callers provide only fixed Git subcommands.
            [_git_executable(), *arguments],
            cwd=workspace_root,
            capture_output=True,
            check=False,
            timeout=10,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise D02OperatorError("D02_GIT_AUTHORITY_UNAVAILABLE") from error
    if result.returncode != 0:
        _fail("D02_GIT_AUTHORITY_UNAVAILABLE")
    return result.stdout.strip()


def _git_executable() -> str:
    located = shutil.which("git")
    if located is None:
        _fail("D02_GIT_AUTHORITY_UNAVAILABLE")
    try:
        path = Path(located).resolve(strict=True)
    except OSError as error:
        raise D02OperatorError("D02_GIT_AUTHORITY_UNAVAILABLE") from error
    if not path.is_absolute() or not path.is_file():
        _fail("D02_GIT_AUTHORITY_UNAVAILABLE")
    return str(path)


def _require_database_head(session: Session) -> None:
    heads = list(session.scalars(text("SELECT version_num FROM alembic_version")))
    if len(heads) != 1 or heads[0] not in _COMPATIBLE_DATABASE_HEADS:
        _fail("DATABASE_MIGRATION_HEAD_MISMATCH")


def _require_file_matches_candidate(bound: BoundPngFile, candidate: DurableCandidateBytes) -> None:
    received = bound.validate()
    if (
        received.sha256 != candidate.primary_sha256
        or received.byte_size != candidate.byte_size
        or received.width != candidate.width
        or received.height != candidate.height
    ):
        _fail("PRIMARY_PUBLISHED_BINDING_MISMATCH")


def _same_local_allocation(left: LocalDurableEntry, right: LocalDurableEntry) -> bool:
    return (
        left.run_id == right.run_id
        and left.cohort_spec_id == right.cohort_spec_id
        and left.provider_ordinal == right.provider_ordinal
        and left.selector_slot_id == right.selector_slot_id
        and left.call_started_event_digest == right.call_started_event_digest
        and left.primary_relative_locator == right.primary_relative_locator
    )


def _canonical_digest(schema_version: str, payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _json_document(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _emit(stream: TextIO, value: Mapping[str, object]) -> None:
    stream.write(_json_document(value).decode("utf-8"))
    stream.flush()


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _validate_relative_locator(value: str) -> None:
    pure = PurePosixPath(value)
    expected_prefix = (".private-handoff", "d02-acquisition", "objects")
    if (
        pure.is_absolute()
        or pure.parts[:3] != expected_prefix
        or len(pure.parts) != 4
        or pure.name in {"", ".", ".."}
        or re.fullmatch(
            r"(?:d02-o[0-9]{2}-[0-9a-f]{16}-(?:primary|backup)\.png|"
            r"d02-c[0-9a-f]{32}-normalized-(?:primary|backup)\.jpg)",
            pure.name,
        )
        is None
    ):
        _fail("PRIVATE_INDEX_LOCATOR_INVALID")


def _require_digest(value: object, code: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail(code)
    return value


def _mkdir_exact(path: Path) -> None:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise D02OperatorError("PRIVATE_NAMESPACE_CREATE_FAILED") from error
    _require_exact_directory(path, code="PRIVATE_NAMESPACE_INVALID")


def _require_exact_directory(path: Path, *, code: str) -> None:
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise D02OperatorError(code) from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        resolved != path
        or not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (reparse_flag and attributes & reparse_flag)
    ):
        _fail(code)


def _regular_file_identity(path: Path, *, code: str) -> tuple[int, int]:
    if not path.is_absolute():
        _fail(code)
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise D02OperatorError(code) from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        resolved != path
        or parent != path.parent
        or not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (reparse_flag and attributes & reparse_flag)
    ):
        _fail(code)
    return info.st_dev, info.st_ino


def _read_bound_file(
    path: Path,
    *,
    expected_identity: tuple[int, int],
    maximum_bytes: int,
    code: str,
) -> bytes:
    if _regular_file_identity(path, code=code) != expected_identity:
        _fail(code)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise D02OperatorError(code) from error
    close_error: OSError | None = None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != expected_identity:
            _fail(code)
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            total += len(chunk)
            if total > maximum_bytes:
                _fail(code)
            chunks.append(chunk)
        if _regular_file_identity(path, code=code) != expected_identity:
            _fail(code)
        return b"".join(chunks)
    except OSError as error:
        raise D02OperatorError(code) from error
    finally:
        try:
            os.close(descriptor)
        except OSError as error:
            close_error = error
        if close_error is not None:
            raise D02OperatorError(code) from close_error


@contextmanager
def _checkpoint_lock(path: Path) -> Iterator[None]:
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise D02OperatorError("PRIVATE_INDEX_LOCK_INVALID") from error
    try:
        opened_info = os.fstat(descriptor)
        path_info = os.lstat(path)
        attributes = getattr(path_info, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            not stat.S_ISREG(opened_info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or stat.S_ISLNK(path_info.st_mode)
            or (reparse_flag and attributes & reparse_flag)
            or (opened_info.st_dev, opened_info.st_ino) != (path_info.st_dev, path_info.st_ino)
        ):
            _fail("PRIVATE_INDEX_LOCK_INVALID")
        handle = os.fdopen(descriptor, "r+b", closefd=True)
        descriptor = -1
    except BaseException:
        os.close(descriptor)
        raise
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        if os.name == "nt":
            msvcrt_module = cast(Any, __import__("msvcrt"))

            try:
                msvcrt_module.locking(handle.fileno(), msvcrt_module.LK_NBLCK, 1)
            except OSError as error:
                raise D02OperatorError("PRIVATE_INDEX_LOCKED") from error
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt_module.locking(handle.fileno(), msvcrt_module.LK_UNLCK, 1)
        else:
            fcntl_module = cast(Any, __import__("fcntl"))

            try:
                fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_EX | fcntl_module.LOCK_NB)
            except OSError as error:
                raise D02OperatorError("PRIVATE_INDEX_LOCKED") from error
            try:
                yield
            finally:
                fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_UN)
    finally:
        handle.close()


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(descriptor, view[offset:])
        if written <= 0:
            _fail("PRIVATE_INDEX_UPDATE_FAILED")
        offset += written


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        # The image receiver already validates durable file publication.  The
        # index replacement is atomic on Windows; reopening the directory is
        # not portable through Python's os.open implementation.
        return
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _best_effort_unlink(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _fail(code: str) -> NoReturn:
    raise D02OperatorError(code)


if __name__ == "__main__":
    raise SystemExit(run())
