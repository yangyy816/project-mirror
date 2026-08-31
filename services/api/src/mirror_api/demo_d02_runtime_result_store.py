"""Private availability store for D02's 48 canonical first-replay JPEGs.

This is deliberately not an authority store: it only proves that the exact
bytes already described by an ``M4ExecutionOutput`` remain available twice.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NoReturn, cast

from mirror_api.demo_d02_r2_runtime_forward import M4ExecutionOutput
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.image_sanitizer import ImageSanitizationError, decode_canonical_rgb_image

INDEX_SCHEMA: Final = "mirror.private/D02RuntimeResultIndex/v1"
INDEX_BINDING_SCHEMA: Final = "mirror.private/D02RuntimeResultAvailabilityBinding/v1"
ENTRY_SCHEMA: Final = "mirror.private/D02RuntimeResultEntry/v1"
FILE_SCHEMA: Final = "mirror.private/D02RuntimeResultFile/v1"
INDEX_RELATIVE: Final = Path(".private-handoff") / "D02_RUNTIME_RESULT_INDEX.json"
OBJECTS_RELATIVE: Final = (
    Path(".private-handoff") / "d02-acquisition" / "objects" / "runtime-results"
)
_DIGEST_LENGTH: Final = 64
_INDEX_BASE_HEADER: Final[dict[str, object]] = {
    "schema_version": INDEX_SCHEMA,
    "authority": "AVAILABILITY_INDEX_ONLY",
    "business_authority": False,
    "case_count": 48,
}


def runtime_result_binding_digest(
    *,
    acquisition_run_id: str,
    selected_manifest_digest: str,
    cohort_spec_digest: str,
    runtime_identity_digest: str,
    model_identity_digest: str,
) -> str:
    if len(acquisition_run_id) != 32 or any(
        character not in "0123456789abcdef" for character in acquisition_run_id
    ):
        _fail("RUNTIME_RESULT_BINDING_INVALID")
    values = (
        selected_manifest_digest,
        cohort_spec_digest,
        runtime_identity_digest,
        model_identity_digest,
    )
    if any(
        len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
        for value in values
    ):
        _fail("RUNTIME_RESULT_BINDING_INVALID")
    payload = {
        "acquisition_run_id": acquisition_run_id,
        "selected_manifest_digest": selected_manifest_digest,
        "cohort_spec_digest": cohort_spec_digest,
        "runtime_identity_digest": runtime_identity_digest,
        "model_identity_digest": model_identity_digest,
    }
    return hashlib.sha256(
        INDEX_BINDING_SCHEMA.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


class D02RuntimeResultStoreError(RuntimeError):
    """Redacted store failure; messages and repr contain stable codes only."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True, repr=False)
class StoredFile:
    relative_locator: str
    identity: tuple[int, int]
    sha256: str
    byte_size: int
    width: int
    height: int

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": FILE_SCHEMA,
            "relative_locator": self.relative_locator,
            "identity": [self.identity[0], self.identity[1]],
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True, slots=True, repr=False)
class StoredResult:
    case_ordinal: int
    output: M4ExecutionOutput
    primary: StoredFile
    backup: StoredFile


class D02RuntimeResultStore:
    """Exact-path, two-copy recovery for canonical M4 first replay outputs."""

    def __init__(self, *, workspace_root: Path, availability_binding_digest: str) -> None:
        if not isinstance(workspace_root, Path) or not workspace_root.is_absolute():
            _fail("WORKSPACE_ROOT_INVALID")
        try:
            resolved = workspace_root.resolve(strict=True)
        except OSError as error:
            raise D02RuntimeResultStoreError("WORKSPACE_ROOT_INVALID") from error
        if resolved != workspace_root or not workspace_root.is_dir():
            _fail("WORKSPACE_ROOT_INVALID")
        if (
            not isinstance(availability_binding_digest, str)
            or len(availability_binding_digest) != 64
            or any(character not in "0123456789abcdef" for character in availability_binding_digest)
        ):
            _fail("RUNTIME_RESULT_BINDING_INVALID")
        self._root = workspace_root
        self._private = workspace_root / ".private-handoff"
        self._acquisition_parent = workspace_root / ".private-handoff" / "d02-acquisition"
        self._objects_parent = workspace_root / OBJECTS_RELATIVE.parent
        self._objects = workspace_root / OBJECTS_RELATIVE
        self._index = workspace_root / INDEX_RELATIVE
        self._index_header = {
            **_INDEX_BASE_HEADER,
            "availability_binding_digest": availability_binding_digest,
        }

    def persist(self, output: M4ExecutionOutput, case_ordinal: int) -> StoredResult:
        """Create or replay the exact primary/backup bytes for one ordinal."""

        _validate_output(output, case_ordinal)
        self._ensure_layout()
        entries = self._load_entries()
        prior = entries.get(case_ordinal)
        if prior is not None:
            stored = self._load_entry(prior)
            if stored.output != output:
                _fail("RUNTIME_RESULT_ORDINAL_COLLISION")
            return stored
        primary = self._materialize(case_ordinal, "primary", output)
        backup = self._materialize(case_ordinal, "backup", output)
        entry = self._entry_payload(case_ordinal, output, primary, backup)
        entries[case_ordinal] = entry
        self._replace_index(entries)
        return self._load_entry(entry)

    def load(self, *, case_ordinal: int) -> M4ExecutionOutput:
        """Re-read and verify an exact stored first-replay output."""

        _validate_ordinal(case_ordinal)
        self._ensure_layout()
        entry = self._load_entries().get(case_ordinal)
        if entry is None:
            _fail("RUNTIME_RESULT_NOT_FOUND")
        return self._load_entry(entry).output

    def verify(self, *, case_ordinal: int) -> StoredResult:
        """Return verified availability facts without granting business authority."""

        _validate_ordinal(case_ordinal)
        self._ensure_layout()
        entry = self._load_entries().get(case_ordinal)
        if entry is None:
            _fail("RUNTIME_RESULT_NOT_FOUND")
        return self._load_entry(entry)

    def count(self) -> int:
        """Return the contiguous durable prefix length without exposing locators."""

        self._ensure_layout()
        entries = self._load_entries()
        if set(entries) != set(range(1, len(entries) + 1)):
            _fail("RUNTIME_RESULT_COUNT_INVALID")
        return len(entries)

    def finalize(self) -> tuple[M4ExecutionOutput, ...]:
        """Verify every ordinal exactly once and return the 48 replay outputs."""

        self._ensure_layout()
        entries = self._load_entries()
        if set(entries) != set(range(1, 49)):
            _fail("RUNTIME_RESULT_COUNT_INVALID")
        return tuple(self._load_entry(entries[ordinal]).output for ordinal in range(1, 49))

    def verify_complete(self, *, outputs: Sequence[M4ExecutionOutput]) -> None:
        """Prove that the exact supplied 48 outputs remain available twice."""

        if len(outputs) != 48 or tuple(outputs) != self.finalize():
            _fail("RUNTIME_RESULT_COUNT_INVALID")

    def _ensure_layout(self) -> None:
        _directory_exact(self._private, "PRIVATE_NAMESPACE_UNAVAILABLE")
        _mkdir_exact(self._acquisition_parent, "PRIVATE_NAMESPACE_UNAVAILABLE")
        _mkdir_exact(self._objects_parent, "PRIVATE_NAMESPACE_UNAVAILABLE")
        _mkdir_exact(self._objects, "PRIVATE_NAMESPACE_UNAVAILABLE")
        if not self._index.exists():
            self._create_index({})
        self._load_entries()

    def _expected_path(self, ordinal: int, copy: str) -> Path:
        return self._objects / f"d02-runtime-result-o{ordinal:02d}-{copy}.jpg"

    def _materialize(self, ordinal: int, copy: str, output: M4ExecutionOutput) -> StoredFile:
        path = self._expected_path(ordinal, copy)
        expected_locator = path.relative_to(self._root).as_posix()
        if path.exists():
            return self._file_facts(path, expected_locator, output)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            return self._file_facts(path, expected_locator, output)
        except OSError as error:
            raise D02RuntimeResultStoreError("RUNTIME_RESULT_FILE_CREATE_FAILED") from error
        try:
            _write_all(descriptor, output.content)
            os.fsync(descriptor)
        except OSError as error:
            raise D02RuntimeResultStoreError("RUNTIME_RESULT_FILE_WRITE_FAILED") from error
        finally:
            os.close(descriptor)
        _sync_directory(path.parent)
        return self._file_facts(path, expected_locator, output)

    def _file_facts(self, path: Path, locator: str, output: M4ExecutionOutput) -> StoredFile:
        identity = _regular_identity(path, "RUNTIME_RESULT_FILE_INVALID")
        data = _read_exact(path, identity)
        if (
            len(data) != output.result_byte_size
            or hashlib.sha256(data).hexdigest() != output.result_sha256
        ):
            _fail("RUNTIME_RESULT_FILE_TAMPERED")
        try:
            decode_canonical_rgb_image(
                data,
                expected_width=output.result_width,
                expected_height=output.result_height,
            )
        except ImageSanitizationError as error:
            raise D02RuntimeResultStoreError("RUNTIME_RESULT_FILE_INVALID") from error
        return StoredFile(
            relative_locator=locator,
            identity=identity,
            sha256=output.result_sha256,
            byte_size=output.result_byte_size,
            width=output.result_width,
            height=output.result_height,
        )

    def _entry_payload(
        self, ordinal: int, output: M4ExecutionOutput, primary: StoredFile, backup: StoredFile
    ) -> dict[str, object]:
        return {
            "schema_version": ENTRY_SCHEMA,
            "case_ordinal": ordinal,
            "output": _output_payload(output),
            "primary": primary.payload(),
            "backup": backup.payload(),
        }

    def _load_entry(self, value: object) -> StoredResult:
        if not isinstance(value, Mapping) or set(value) != {
            "schema_version",
            "case_ordinal",
            "output",
            "primary",
            "backup",
        }:
            _fail("RUNTIME_RESULT_ENTRY_SCHEMA_INVALID")
        entry = cast(Mapping[str, object], value)
        if entry.get("schema_version") != ENTRY_SCHEMA:
            _fail("RUNTIME_RESULT_ENTRY_SCHEMA_UNKNOWN")
        ordinal = entry.get("case_ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool):
            _fail("RUNTIME_RESULT_ENTRY_INVALID")
        _validate_ordinal(ordinal)
        output_value = _output_mapping(entry.get("output"))
        primary = self._parse_file(entry.get("primary"), ordinal, "primary", output_value)
        backup = self._parse_file(entry.get("backup"), ordinal, "backup", output_value)
        content = _read_exact(self._expected_path(ordinal, "primary"), primary.identity)
        output = _parse_output(output_value, content)
        _validate_output(output, ordinal)
        return StoredResult(ordinal, output, primary, backup)

    def _parse_file(
        self, value: object, ordinal: int, copy: str, output: Mapping[str, object]
    ) -> StoredFile:
        expected = {
            "schema_version",
            "relative_locator",
            "identity",
            "sha256",
            "byte_size",
            "width",
            "height",
        }
        if (
            not isinstance(value, Mapping)
            or set(value) != expected
            or value.get("schema_version") != FILE_SCHEMA
        ):
            _fail("RUNTIME_RESULT_FILE_SCHEMA_INVALID")
        item = cast(Mapping[str, object], value)
        locator = item.get("relative_locator")
        identity = item.get("identity")
        if (
            not isinstance(locator, str)
            or locator != self._expected_path(ordinal, copy).relative_to(self._root).as_posix()
            or not isinstance(identity, list)
            or len(identity) != 2
            or any(
                not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in identity
            )
            or item.get("sha256") != output["result_sha256"]
            or item.get("byte_size") != output["result_byte_size"]
            or item.get("width") != output["result_width"]
            or item.get("height") != output["result_height"]
        ):
            _fail("RUNTIME_RESULT_FILE_BINDING_INVALID")
        path = self._expected_path(ordinal, copy)
        actual_identity = _regular_identity(path, "RUNTIME_RESULT_FILE_INVALID")
        data = _read_exact(path, actual_identity)
        if (
            len(data) != output["result_byte_size"]
            or hashlib.sha256(data).hexdigest() != output["result_sha256"]
        ):
            _fail("RUNTIME_RESULT_FILE_TAMPERED")
        facts = StoredFile(
            relative_locator=locator,
            identity=actual_identity,
            sha256=output["result_sha256"],
            byte_size=output["result_byte_size"],
            width=cast(int, output["result_width"]),
            height=cast(int, output["result_height"]),
        )
        if facts.identity != (cast(int, identity[0]), cast(int, identity[1])):
            _fail("RUNTIME_RESULT_FILE_TAMPERED")
        return facts

    def _load_entries(self) -> dict[int, object]:
        raw = self._read_index()
        expected = {*self._index_header, "entries"}
        if (
            not isinstance(raw, dict)
            or set(raw) != expected
            or any(raw.get(key) != value for key, value in self._index_header.items())
        ):
            _fail("RUNTIME_RESULT_INDEX_SCHEMA_INVALID")
        document = cast(dict[str, object], raw)
        values = document.get("entries")
        if not isinstance(values, list) or len(values) > 48:
            _fail("RUNTIME_RESULT_INDEX_SCHEMA_INVALID")
        entries: dict[int, object] = {}
        for entry in values:
            if (
                not isinstance(entry, Mapping)
                or not isinstance(entry.get("case_ordinal"), int)
                or isinstance(entry.get("case_ordinal"), bool)
            ):
                _fail("RUNTIME_RESULT_ENTRY_INVALID")
            ordinal = cast(int, entry["case_ordinal"])
            if ordinal in entries:
                _fail("RUNTIME_RESULT_ORDINAL_COLLISION")
            entries[ordinal] = entry
        return entries

    def _read_index(self) -> object:
        identity = _regular_identity(self._index, "RUNTIME_RESULT_INDEX_INVALID")
        data = _read_exact(self._index, identity)
        try:
            return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_object)
        except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey) as error:
            raise D02RuntimeResultStoreError("RUNTIME_RESULT_INDEX_UNREADABLE") from error

    def _create_index(self, entries: Mapping[int, object]) -> None:
        self._write_index(entries, create=True)

    def _replace_index(self, entries: Mapping[int, object]) -> None:
        if self._index.exists():
            _regular_identity(self._index, "RUNTIME_RESULT_INDEX_INVALID")
        self._write_index(entries, create=False)

    def _write_index(self, entries: Mapping[int, object], *, create: bool) -> None:
        document = {**self._index_header, "entries": [entries[key] for key in sorted(entries)]}
        data = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        target = (
            self._index
            if create
            else self._index.with_name(".D02_RUNTIME_RESULT_INDEX.json.incoming")
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags, 0o600)
            try:
                _write_all(descriptor, data)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            if not create:
                os.replace(target, self._index)
            _sync_directory(self._index.parent)
        except OSError as error:
            if not create:
                try:
                    target.unlink(missing_ok=True)
                except OSError:
                    pass
            raise D02RuntimeResultStoreError("RUNTIME_RESULT_INDEX_UPDATE_FAILED") from error
        if self._read_index() != document:
            _fail("RUNTIME_RESULT_INDEX_REPLAY_FAILED")


class _DuplicateJsonKey(ValueError):
    pass


def _no_duplicate_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey()
        value[key] = item
    return value


def _output_payload(output: M4ExecutionOutput) -> dict[str, object]:
    return {**output.payload(), "output_digest": output.output_digest}


def _output_mapping(value: object) -> Mapping[str, object]:
    expected = {*M4ExecutionOutput.__dataclass_fields__, "content"}
    expected.remove("content")
    if not isinstance(value, Mapping) or set(value) != expected:
        _fail("RUNTIME_RESULT_OUTPUT_SCHEMA_INVALID")
    output = cast(Mapping[str, object], value)
    for key in ("result_sha256", "execution_receipt_digest", "output_digest"):
        candidate = output.get(key)
        if not isinstance(candidate, str) or len(candidate) != _DIGEST_LENGTH:
            _fail("RUNTIME_RESULT_OUTPUT_INVALID")
    for key in ("result_byte_size", "result_width", "result_height"):
        candidate = output.get(key)
        if not isinstance(candidate, int) or isinstance(candidate, bool) or candidate < 1:
            _fail("RUNTIME_RESULT_OUTPUT_INVALID")
    return output


def _parse_output(value: Mapping[str, object], content: bytes) -> M4ExecutionOutput:
    try:
        return M4ExecutionOutput(
            case_id=cast(str, value["case_id"]),
            replay_index=cast(int, value["replay_index"]),
            result_output_id=cast(str, value["result_output_id"]),
            content=content,
            result_sha256=cast(str, value["result_sha256"]),
            result_byte_size=cast(int, value["result_byte_size"]),
            result_width=cast(int, value["result_width"]),
            result_height=cast(int, value["result_height"]),
            changed_pixel_count=cast(int, value["changed_pixel_count"]),
            execution_receipt_digest=cast(str, value["execution_receipt_digest"]),
            output_digest=cast(str, value["output_digest"]),
            result_mime_type=cast(str, value["result_mime_type"]),
            execution_succeeded=cast(bool, value["execution_succeeded"]),
            schema_version=cast(str, value["schema_version"]),
        )
    except (TypeError, ValueError) as error:
        raise D02RuntimeResultStoreError("RUNTIME_RESULT_OUTPUT_INVALID") from error


def _validate_output(output: M4ExecutionOutput, ordinal: int) -> None:
    _validate_ordinal(ordinal)
    if output.replay_index != 1:
        _fail("RUNTIME_RESULT_REPLAY_INVALID")


def _validate_ordinal(ordinal: int) -> None:
    if type(ordinal) is not int or ordinal not in range(1, 49):
        _fail("RUNTIME_RESULT_ORDINAL_INVALID")


def _mkdir_exact(path: Path, code: str) -> None:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise D02RuntimeResultStoreError(code) from error
    _directory_exact(path, code)


def _directory_exact(path: Path, code: str) -> None:
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise D02RuntimeResultStoreError(code) from error
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
        or resolved != path
    ):
        _fail(code)


def _regular_identity(path: Path, code: str) -> tuple[int, int]:
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise D02RuntimeResultStoreError(code) from error
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
        or resolved != path
        or parent != path.parent
    ):
        _fail(code)
    return info.st_dev, info.st_ino


def _is_reparse(info: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and getattr(info, "st_file_attributes", 0) & flag)


def _read_exact(path: Path, identity: tuple[int, int]) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise D02RuntimeResultStoreError("RUNTIME_RESULT_FILE_UNREADABLE") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != identity:
            _fail("RUNTIME_RESULT_FILE_TAMPERED")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1_048_576):
            chunks.append(chunk)
        if _regular_identity(path, "RUNTIME_RESULT_FILE_TAMPERED") != identity:
            _fail("RUNTIME_RESULT_FILE_TAMPERED")
        return b"".join(chunks)
    except OSError as error:
        raise D02RuntimeResultStoreError("RUNTIME_RESULT_FILE_UNREADABLE") from error
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(descriptor, view[offset:])
        if written <= 0:
            _fail("RUNTIME_RESULT_FILE_WRITE_FAILED")
        offset += written


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise D02RuntimeResultStoreError("RUNTIME_RESULT_DIRECTORY_SYNC_FAILED") from error
    try:
        os.fsync(descriptor)
    except OSError as error:
        raise D02RuntimeResultStoreError("RUNTIME_RESULT_DIRECTORY_SYNC_FAILED") from error
    finally:
        os.close(descriptor)


def _fail(code: str) -> NoReturn:
    raise D02RuntimeResultStoreError(code)
