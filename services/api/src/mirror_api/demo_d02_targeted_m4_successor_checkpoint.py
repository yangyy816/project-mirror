"""Private, Case-25-only recovery checkpoint for ADR-053.

This module deliberately owns neither screening nor admission authority.  It
only makes the one accepted replacement JPEG replayable after the two M4
replays have completed.  Its persisted JSON is public-shaped: bytes and file
locators never cross the checkpoint boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final, NoReturn, cast

from mirror_api.demo_d02_r2_runtime_forward import (
    M4_EXECUTION_OUTPUT_SCHEMA,
    M4ExecutionOutput,
    RuntimeForwardError,
)
from mirror_api.demo_d02_screening_adapters import (
    D02ScreeningAdapterError,
    PrincipalArtifactDecision,
)
from mirror_api.demo_idempotency import DemoIdempotencyInputError, canonical_json_bytes
from mirror_api.image_sanitizer import ImageSanitizationError, decode_canonical_rgb_image

CHECKPOINT_SCHEMA: Final = "mirror.private/D02TargetedM4SuccessorCheckpoint/v1"
STORE_SCHEMA: Final = "mirror.private/D02TargetedM4SuccessorStore/v1"
STORE_ENTRY_SCHEMA: Final = "mirror.private/D02TargetedM4SuccessorStoreEntry/v1"
CHECKPOINT_RELATIVE: Final = Path(".private-handoff") / "D02_TARGETED_M4_SUCCESSOR_CHECKPOINT.json"
STORE_RELATIVE: Final = Path(".private-handoff") / "d02-targeted-m4-successor"
TARGET_CASE_ORDINAL: Final = 25
_STAGES: Final = (
    "PREDECESSOR_REVIEWED_FAILED",
    "REPAIR_POLICY_VALIDATED",
    "TARGET_M4_DURABLE",
    "TARGET_RESULT_M3_COMPLETE",
    "TARGET_REVIEW_REQUIRED",
    "SUCCESSOR_REVIEWED",
    "SUCCESSOR_SCREENING_REPLAYED",
    "ADMISSION_READY",
    "ADMITTED",
)
_PRIVATE_KEYS: Final = frozenset(
    {"bytes", "content", "path", "locator", "raw_bytes", "token", "secret", "url", "storage_key"}
)


class D02TargetedM4SuccessorCheckpointError(RuntimeError):
    """Stable redacted errors only."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True, repr=False)
class SuccessorBindings:
    policy_digest: str
    implementation_digest: str
    config_digest: str
    scope_digest: str
    predecessor_checkpoint_digest: str
    predecessor_report_digest: str
    successor_case_id: str
    successor_admission_idempotency_key_hash: str

    def payload(self) -> dict[str, str]:
        return {
            "policy_digest": self.policy_digest,
            "implementation_digest": self.implementation_digest,
            "config_digest": self.config_digest,
            "scope_digest": self.scope_digest,
            "predecessor_checkpoint_digest": self.predecessor_checkpoint_digest,
            "predecessor_report_digest": self.predecessor_report_digest,
            "successor_case_id": self.successor_case_id,
            "successor_admission_idempotency_key_hash": (
                self.successor_admission_idempotency_key_hash
            ),
        }


@dataclass(frozen=True, slots=True, repr=False)
class RecoveredTargetedM4Successor:
    stage: str
    bindings: SuccessorBindings
    m4_outputs: tuple[M4ExecutionOutput, M4ExecutionOutput] | None
    result_m3_records: tuple[Mapping[str, object], ...]
    artifact_decision: PrincipalArtifactDecision | None
    successor_universe: Mapping[str, object] | None
    provenance_envelope: Mapping[str, object] | None
    document_digest: str


class D02TargetedM4SuccessorStore:
    """A separate two-copy availability store for one Case-25 result only."""

    def __init__(self, *, workspace_root: Path, successor_case_id: str) -> None:
        self._root = _workspace(workspace_root)
        if not _identifier(successor_case_id):
            _fail("SUCCESSOR_STORE_BINDING_INVALID")
        self._case_id = successor_case_id
        self._private = self._root / STORE_RELATIVE
        self._index = self._private / "index.json"

    @property
    def exists(self) -> bool:
        """Whether any durable-store state exists; partial state is never empty."""

        return self._probe_state() != "EMPTY"

    def _directory(self, *, create: bool) -> Path | None:
        return _safe_workspace_directory(
            self._root,
            STORE_RELATIVE,
            create=create,
            code="SUCCESSOR_STORE_PATH_INVALID",
        )

    def _probe_state(self) -> str:
        directory = self._directory(create=False)
        if directory is None:
            return "EMPTY"
        names = ("index.json", "case25-primary.jpg", "case25-backup.jpg", ".index.incoming")
        present = tuple(_path_present(directory / name) for name in names)
        if not any(present):
            return "EMPTY"
        if present == (True, True, True, False):
            return "COMPLETE"
        return "PARTIAL"

    def _require_complete(self) -> None:
        state = self._probe_state()
        if state == "PARTIAL":
            _fail("SUCCESSOR_STORE_PARTIAL_STATE")
        if state != "COMPLETE":
            _fail("SUCCESSOR_STORE_INVALID")

    def persist(self, first: M4ExecutionOutput, second: M4ExecutionOutput) -> None:
        _validate_m4_pair(first, second, self._case_id)
        state = self._probe_state()
        if state == "PARTIAL":
            _fail("SUCCESSOR_STORE_PARTIAL_STATE")
        if state == "COMPLETE":
            existing = self.load()
            if existing != (first, second):
                _fail("SUCCESSOR_STORE_COLLISION")
            return
        directory = self._directory(create=True)
        if directory is None:  # pragma: no cover - create=True either returns a directory or fails.
            _fail("SUCCESSOR_STORE_PATH_INVALID")
        primary = directory / "case25-primary.jpg"
        backup = directory / "case25-backup.jpg"
        for path in (primary, backup):
            self._directory(create=False)
            _atomic_create(path, first.content)
            self._directory(create=False)
            _verify_file(path, first)
        entry = {
            "schema_version": STORE_ENTRY_SCHEMA,
            "case_ordinal": TARGET_CASE_ORDINAL,
            "m4_outputs": [_output_payload(first), _output_payload(second)],
            "primary_sha256": first.result_sha256,
            "backup_sha256": first.result_sha256,
        }
        self._atomic_json(self._index, {"schema_version": STORE_SCHEMA, "entry": entry})
        self.load()

    def load(self) -> tuple[M4ExecutionOutput, M4ExecutionOutput]:
        self._require_complete()
        directory = self._directory(create=False)
        if directory is None:  # pragma: no cover - guarded by _require_complete.
            _fail("SUCCESSOR_STORE_INVALID")
        document = _read_json(directory / "index.json", "SUCCESSOR_STORE_INVALID")
        if (
            not isinstance(document, Mapping)
            or set(document) != {"schema_version", "entry"}
            or document.get("schema_version") != STORE_SCHEMA
        ):
            _fail("SUCCESSOR_STORE_INVALID")
        entry = document.get("entry")
        if (
            not isinstance(entry, Mapping)
            or set(entry)
            != {"schema_version", "case_ordinal", "m4_outputs", "primary_sha256", "backup_sha256"}
            or entry.get("schema_version") != STORE_ENTRY_SCHEMA
            or entry.get("case_ordinal") != TARGET_CASE_ORDINAL
        ):
            _fail("SUCCESSOR_STORE_INVALID")
        values = entry.get("m4_outputs")
        if not isinstance(values, list) or len(values) != 2:
            _fail("SUCCESSOR_STORE_INVALID")
        self._directory(create=False)
        first = _parse_output(values[0], directory / "case25-primary.jpg", self._case_id)
        self._directory(create=False)
        second = _parse_output(values[1], directory / "case25-primary.jpg", self._case_id)
        _validate_m4_pair(first, second, self._case_id)
        if (
            entry.get("primary_sha256") != first.result_sha256
            or entry.get("backup_sha256") != first.result_sha256
        ):
            _fail("SUCCESSOR_STORE_INVALID")
        self._directory(create=False)
        _verify_file(directory / "case25-primary.jpg", first)
        self._directory(create=False)
        _verify_file(directory / "case25-backup.jpg", first)
        return first, second

    def _atomic_json(self, target: Path, value: Mapping[str, object]) -> None:
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        incoming = target.with_name(".index.incoming")
        self._directory(create=False)
        _atomic_create(incoming, data, code="SUCCESSOR_STORE_WRITE_FAILED")
        try:
            self._directory(create=False)
            os.replace(incoming, target)
        except OSError as error:
            raise D02TargetedM4SuccessorCheckpointError("SUCCESSOR_STORE_WRITE_FAILED") from error


class D02TargetedM4SuccessorCheckpoint:
    """Monotonic recovery checkpoint bound to the ADR-053 successor only."""

    def __init__(self, *, workspace_root: Path, bindings: SuccessorBindings) -> None:
        self._root = _workspace(workspace_root)
        _validate_bindings(bindings)
        self._bindings = bindings
        self._path = self._root / CHECKPOINT_RELATIVE

    @property
    def exists(self) -> bool:
        directory = self._directory(create=False)
        return directory is not None and _path_present(self._path)

    def _directory(self, *, create: bool) -> Path | None:
        return _safe_workspace_directory(
            self._root,
            CHECKPOINT_RELATIVE.parent,
            create=create,
            code="SUCCESSOR_CHECKPOINT_PATH_INVALID",
        )

    def advance(
        self,
        *,
        stage: str,
        m4_outputs: Sequence[M4ExecutionOutput] = (),
        result_m3_records: Sequence[Mapping[str, object]] = (),
        artifact_decision: PrincipalArtifactDecision | None = None,
        successor_universe: Mapping[str, object] | None = None,
        provenance_envelope: Mapping[str, object] | None = None,
    ) -> None:
        if stage not in _STAGES:
            _fail("SUCCESSOR_STAGE_INVALID")
        previous = self._read_optional()
        if previous is None and stage != _STAGES[0]:
            _fail("SUCCESSOR_STAGE_NOT_MONOTONIC")
        if (
            previous is not None
            and _STAGES.index(stage) != _STAGES.index(cast(str, previous["stage"])) + 1
        ):
            _fail("SUCCESSOR_STAGE_NOT_MONOTONIC")
        self._validate_stage_payload(
            stage,
            m4_outputs,
            result_m3_records,
            artifact_decision,
            successor_universe,
            provenance_envelope,
        )
        if previous is not None:
            current = {
                "m4_outputs": [_output_payload(item) for item in m4_outputs],
                "result_m3_records": [dict(item) for item in result_m3_records],
                "artifact_decision": _decision_payload(artifact_decision),
                "successor_universe": None
                if successor_universe is None
                else dict(successor_universe),
                "provenance_envelope": None
                if provenance_envelope is None
                else dict(provenance_envelope),
            }
            for key, value in current.items():
                if previous[key] not in ([], None) and previous[key] != value:
                    _fail("SUCCESSOR_CHECKPOINT_REBINDING")
        document: dict[str, object] = {
            "schema_version": CHECKPOINT_SCHEMA,
            "stage": stage,
            "bindings": self._bindings.payload(),
            "m4_outputs": [_output_payload(item) for item in m4_outputs],
            "result_m3_records": [dict(item) for item in result_m3_records],
            "artifact_decision": _decision_payload(artifact_decision),
            "successor_universe": None if successor_universe is None else dict(successor_universe),
            "provenance_envelope": None
            if provenance_envelope is None
            else dict(provenance_envelope),
        }
        document["document_digest"] = _digest(document)
        self._write(document)

    def load(self, *, store: D02TargetedM4SuccessorStore) -> RecoveredTargetedM4Successor:
        if not self.exists and store.exists:
            _fail("SUCCESSOR_STORE_WITHOUT_CHECKPOINT")
        document = self._read_required()
        if store._case_id != self._bindings.successor_case_id:
            _fail("SUCCESSOR_STORE_BINDING_INVALID")
        stage = cast(str, document["stage"])
        outputs_raw = cast(Sequence[object], document["m4_outputs"])
        stored: tuple[M4ExecutionOutput, M4ExecutionOutput] | None = None
        durable = _STAGES.index(stage) >= _STAGES.index("TARGET_M4_DURABLE")
        if durable:
            if not store.exists:
                _fail("SUCCESSOR_DURABLE_STORE_MISSING")
            stored = store.load()
            parsed = tuple(
                _validate_output_payload(item, self._bindings.successor_case_id)
                for item in outputs_raw
            )
            if len(parsed) != 2 or tuple(_output_payload(item) for item in stored) != parsed:
                _fail("SUCCESSOR_STORE_CHECKPOINT_MISMATCH")
        elif store.exists:
            stored = store.load()
        records = tuple(
            cast(Mapping[str, object], _freeze(value))
            for value in cast(Sequence[object], document["result_m3_records"])
        )
        decision: PrincipalArtifactDecision | None = None
        if _STAGES.index(stage) >= _STAGES.index("SUCCESSOR_REVIEWED"):
            if stored is None:  # pragma: no cover - later stages are necessarily durable.
                _fail("SUCCESSOR_DURABLE_STORE_MISSING")
            decision = _parse_artifact_decision(
                document["artifact_decision"],
                case_id=self._bindings.successor_case_id,
                result_sha256=stored[0].result_sha256,
            )
        universe = document["successor_universe"]
        envelope = document["provenance_envelope"]
        return RecoveredTargetedM4Successor(
            stage=stage,
            bindings=self._bindings,
            m4_outputs=stored,
            result_m3_records=records,
            artifact_decision=decision,
            successor_universe=None
            if universe is None
            else cast(Mapping[str, object], _freeze(universe)),
            provenance_envelope=None
            if envelope is None
            else cast(Mapping[str, object], _freeze(envelope)),
            document_digest=cast(str, document["document_digest"]),
        )

    def _validate_stage_payload(
        self,
        stage: str,
        outputs: Sequence[M4ExecutionOutput],
        records: Sequence[Mapping[str, object]],
        decision: PrincipalArtifactDecision | None,
        universe: Mapping[str, object] | None,
        envelope: Mapping[str, object] | None,
    ) -> None:
        durable = _STAGES.index(stage) >= _STAGES.index("TARGET_M4_DURABLE")
        completed = _STAGES.index(stage) >= _STAGES.index("TARGET_RESULT_M3_COMPLETE")
        reviewed = _STAGES.index(stage) >= _STAGES.index("SUCCESSOR_REVIEWED")
        if len(outputs) != 2 if durable else bool(outputs):
            _fail("SUCCESSOR_M4_CARDINALITY_INVALID")
        first: M4ExecutionOutput | None = None
        if durable:
            first, second = outputs
            _validate_m4_pair(first, second, self._bindings.successor_case_id)
        if len(records) != 3 if completed else bool(records):
            _fail("SUCCESSOR_RESULT_M3_CARDINALITY_INVALID")
        for record in records:
            _validate_record(record, "record_digest")
        if (decision is None) == reviewed:
            _fail("SUCCESSOR_REVIEW_BINDING_INVALID")
        if decision is not None:
            _validate_artifact_decision(
                decision,
                case_id=self._bindings.successor_case_id,
                result_sha256=None if first is None else first.result_sha256,
            )
        replayed = _STAGES.index(stage) >= _STAGES.index("SUCCESSOR_SCREENING_REPLAYED")
        if (universe is None) == replayed:
            _fail("SUCCESSOR_UNIVERSE_BINDING_INVALID")
        if universe is not None:
            _validate_record(universe, "successor_universe_digest")
        if (envelope is None) == replayed:
            _fail("SUCCESSOR_PROVENANCE_BINDING_INVALID")
        if envelope is not None:
            _validate_record(envelope, "provenance_envelope_digest")

    def _read_optional(self) -> dict[str, object] | None:
        return None if not self.exists else self._read_required()

    def _read_required(self) -> dict[str, object]:
        if self._directory(create=False) is None:
            _fail("SUCCESSOR_CHECKPOINT_INVALID")
        document = _read_json(self._path, "SUCCESSOR_CHECKPOINT_INVALID")
        expected = {
            "schema_version",
            "stage",
            "bindings",
            "m4_outputs",
            "result_m3_records",
            "artifact_decision",
            "successor_universe",
            "provenance_envelope",
            "document_digest",
        }
        if (
            not isinstance(document, dict)
            or set(document) != expected
            or document.get("schema_version") != CHECKPOINT_SCHEMA
            or not isinstance(document.get("stage"), str)
            or document.get("stage") not in _STAGES
        ):
            _fail("SUCCESSOR_CHECKPOINT_INVALID")
        if document.get("bindings") != self._bindings.payload():
            _fail("SUCCESSOR_CHECKPOINT_BINDING_INVALID")
        digest = document.pop("document_digest")
        valid = _is_digest(digest) and digest == _digest(document)
        document["document_digest"] = digest
        if not valid:
            _fail("SUCCESSOR_CHECKPOINT_INVALID")
        self._validate_loaded(document)
        return document

    def _validate_loaded(self, document: Mapping[str, object]) -> None:
        stage = cast(str, document["stage"])
        if not isinstance(document["m4_outputs"], list) or not isinstance(
            document["result_m3_records"], list
        ):
            _fail("SUCCESSOR_CHECKPOINT_INVALID")
        raw_outputs = cast(Sequence[object], document["m4_outputs"])
        durable = _STAGES.index(stage) >= _STAGES.index("TARGET_M4_DURABLE")
        if len(raw_outputs) != 2 if durable else bool(raw_outputs):
            _fail("SUCCESSOR_M4_CARDINALITY_INVALID")
        parsed = tuple(
            _validate_output_payload(item, self._bindings.successor_case_id) for item in raw_outputs
        )
        if durable and (
            parsed[0]["replay_index"] != 1
            or parsed[1]["replay_index"] != 2
            or parsed[0]["result_sha256"] != parsed[1]["result_sha256"]
        ):
            _fail("SUCCESSOR_M4_REPEAT_INVALID")
        records = cast(Sequence[object], document["result_m3_records"])
        completed = _STAGES.index(stage) >= _STAGES.index("TARGET_RESULT_M3_COMPLETE")
        if len(records) != 3 if completed else bool(records):
            _fail("SUCCESSOR_RESULT_M3_CARDINALITY_INVALID")
        for record in records:
            _validate_record(record, "record_digest")
        reviewed = _STAGES.index(stage) >= _STAGES.index("SUCCESSOR_REVIEWED")
        decision = document["artifact_decision"]
        if (decision is None) == reviewed or (
            decision is not None and not isinstance(decision, Mapping)
        ):
            _fail("SUCCESSOR_REVIEW_BINDING_INVALID")
        if isinstance(decision, Mapping):
            _parse_artifact_decision(
                decision,
                case_id=self._bindings.successor_case_id,
                result_sha256=cast(str, parsed[0]["result_sha256"]) if durable else None,
            )
        replayed = _STAGES.index(stage) >= _STAGES.index("SUCCESSOR_SCREENING_REPLAYED")
        pairs = (
            ("successor_universe", "successor_universe_digest"),
            ("provenance_envelope", "provenance_envelope_digest"),
        )
        for key, digest_key in pairs:
            value = document[key]
            if (value is None) == replayed or (
                value is not None and not isinstance(value, Mapping)
            ):
                _fail("SUCCESSOR_PROVENANCE_BINDING_INVALID")
            if isinstance(value, Mapping):
                _validate_record(value, digest_key)

    def _write(self, document: Mapping[str, object]) -> None:
        # create=True either returns a directory or raises a stable error.
        if self._directory(create=True) is None:  # pragma: no cover
            _fail("SUCCESSOR_CHECKPOINT_PATH_INVALID")
        data = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        incoming = self._path.with_name(".D02_TARGETED_M4_SUCCESSOR_CHECKPOINT.incoming")
        self._directory(create=False)
        _atomic_create(incoming, data, code="SUCCESSOR_CHECKPOINT_WRITE_FAILED")
        try:
            self._directory(create=False)
            os.replace(incoming, self._path)
        except OSError as error:
            raise D02TargetedM4SuccessorCheckpointError(
                "SUCCESSOR_CHECKPOINT_WRITE_FAILED"
            ) from error


def _validate_bindings(bindings: SuccessorBindings) -> None:
    digest_values = (
        value for key, value in bindings.payload().items() if key != "successor_case_id"
    )
    if (
        type(bindings) is not SuccessorBindings
        or not all(_is_digest(value) for value in digest_values)
        or not _identifier(bindings.successor_case_id)
    ):
        _fail("SUCCESSOR_CHECKPOINT_BINDING_INVALID")


def _validate_output(output: M4ExecutionOutput, case_id: str, *, replay_index: int) -> None:
    if (
        type(output) is not M4ExecutionOutput
        or output.case_id != case_id
        or output.replay_index != replay_index
    ):
        _fail("SUCCESSOR_M4_BINDING_INVALID")


def _validate_m4_pair(first: M4ExecutionOutput, second: M4ExecutionOutput, case_id: str) -> None:
    _validate_output(first, case_id, replay_index=1)
    _validate_output(second, case_id, replay_index=2)
    if (
        first.content != second.content
        or first.result_sha256 != second.result_sha256
        or first.result_byte_size != second.result_byte_size
        or first.result_width != second.result_width
        or first.result_height != second.result_height
        or first.changed_pixel_count != second.changed_pixel_count
    ):
        _fail("SUCCESSOR_M4_REPEAT_INVALID")


def _decision_payload(value: PrincipalArtifactDecision | None) -> dict[str, object] | None:
    if value is None:
        return None
    _validate_artifact_decision(value, case_id=value.case_id, result_sha256=value.result_sha256)
    return {
        "case_id": value.case_id,
        "result_sha256": value.result_sha256,
        "decision_sequence": value.decision_sequence,
        "manual_review_version": value.manual_review_version,
        "manual_review_policy_digest": value.manual_review_policy_digest,
        "background_seam": value.background_seam,
        "disconnected_contour": value.disconnected_contour,
        "duplicated_feature": value.duplicated_feature,
        "warp_tear": value.warp_tear,
        "review_authority_digest": value.review_authority_digest,
    }


def _validate_artifact_decision(
    value: object, *, case_id: str, result_sha256: str | None
) -> PrincipalArtifactDecision:
    if (
        not isinstance(value, PrincipalArtifactDecision)
        or type(value) is not PrincipalArtifactDecision
    ):
        _fail("SUCCESSOR_REVIEW_BINDING_INVALID")
    if (
        value.case_id != case_id
        or value.decision_sequence != TARGET_CASE_ORDINAL
        or (result_sha256 is not None and value.result_sha256 != result_sha256)
    ):
        _fail("SUCCESSOR_REVIEW_BINDING_INVALID")
    try:
        PrincipalArtifactDecision(
            case_id=value.case_id,
            result_sha256=value.result_sha256,
            decision_sequence=value.decision_sequence,
            manual_review_version=value.manual_review_version,
            manual_review_policy_digest=value.manual_review_policy_digest,
            background_seam=value.background_seam,
            disconnected_contour=value.disconnected_contour,
            duplicated_feature=value.duplicated_feature,
            warp_tear=value.warp_tear,
            review_authority_digest=value.review_authority_digest,
        )
    except (D02ScreeningAdapterError, TypeError, ValueError):
        _fail("SUCCESSOR_REVIEW_BINDING_INVALID")
    return value


def _parse_artifact_decision(
    value: object, *, case_id: str, result_sha256: str | None
) -> PrincipalArtifactDecision:
    expected = {
        "case_id",
        "result_sha256",
        "decision_sequence",
        "manual_review_version",
        "manual_review_policy_digest",
        "background_seam",
        "disconnected_contour",
        "duplicated_feature",
        "warp_tear",
        "review_authority_digest",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        _fail("SUCCESSOR_REVIEW_BINDING_INVALID")
    fields = dict(value)
    if (
        not isinstance(fields["case_id"], str)
        or not isinstance(fields["result_sha256"], str)
        or type(fields["decision_sequence"]) is not int
        or not isinstance(fields["manual_review_version"], str)
        or not isinstance(fields["manual_review_policy_digest"], str)
        or any(
            type(fields[key]) is not bool
            for key in (
                "background_seam",
                "disconnected_contour",
                "duplicated_feature",
                "warp_tear",
            )
        )
        or not isinstance(fields["review_authority_digest"], str)
    ):
        _fail("SUCCESSOR_REVIEW_BINDING_INVALID")
    try:
        decision = PrincipalArtifactDecision(
            case_id=fields["case_id"],
            result_sha256=fields["result_sha256"],
            decision_sequence=fields["decision_sequence"],
            manual_review_version=fields["manual_review_version"],
            manual_review_policy_digest=fields["manual_review_policy_digest"],
            background_seam=cast(bool, fields["background_seam"]),
            disconnected_contour=cast(bool, fields["disconnected_contour"]),
            duplicated_feature=cast(bool, fields["duplicated_feature"]),
            warp_tear=cast(bool, fields["warp_tear"]),
            review_authority_digest=fields["review_authority_digest"],
        )
    except (D02ScreeningAdapterError, TypeError, ValueError):
        _fail("SUCCESSOR_REVIEW_BINDING_INVALID")
    return _validate_artifact_decision(decision, case_id=case_id, result_sha256=result_sha256)


def _output_payload(output: M4ExecutionOutput) -> dict[str, object]:
    payload: dict[str, object] = {**output.payload(), "output_digest": output.output_digest}
    _reject_private(payload)
    return payload


def _parse_output(value: object, content_path: Path, case_id: str) -> M4ExecutionOutput:
    _validate_output_payload(value, case_id)
    if not isinstance(value, Mapping):  # narrow for mypy; validation always fails first.
        _fail("SUCCESSOR_M4_PAYLOAD_INVALID")
    content = _read_bytes(content_path, "SUCCESSOR_STORE_INVALID")
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
    except (RuntimeForwardError, TypeError, ValueError) as error:
        raise D02TargetedM4SuccessorCheckpointError("SUCCESSOR_M4_PAYLOAD_INVALID") from error


def _validate_output_payload(value: object, case_id: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail("SUCCESSOR_M4_PAYLOAD_INVALID")
    expected = set(M4ExecutionOutput.__dataclass_fields__) - {"content"}
    if (
        set(value) != expected
        or not isinstance(value.get("schema_version"), str)
        or value.get("schema_version") != M4_EXECUTION_OUTPUT_SCHEMA
        or not isinstance(value.get("case_id"), str)
        or (case_id and value.get("case_id") != case_id)
        or type(value.get("replay_index")) is not int
        or value.get("replay_index") not in (1, 2)
        or not isinstance(value.get("result_output_id"), str)
        or not isinstance(value.get("result_byte_size"), int)
        or type(value.get("result_byte_size")) is not int
        or cast(int, value.get("result_byte_size")) < 1
        or type(value.get("result_width")) is not int
        or cast(int, value.get("result_width")) < 1
        or type(value.get("result_height")) is not int
        or cast(int, value.get("result_height")) < 1
        or type(value.get("changed_pixel_count")) is not int
        or cast(int, value.get("changed_pixel_count")) < 1
        or cast(int, value.get("changed_pixel_count"))
        > cast(int, value.get("result_width")) * cast(int, value.get("result_height"))
        or value.get("result_mime_type") != "image/jpeg"
        or value.get("execution_succeeded") is not True
    ):
        _fail("SUCCESSOR_M4_PAYLOAD_INVALID")
    _reject_private(value)
    for key in ("result_sha256", "execution_receipt_digest", "output_digest"):
        if not _is_digest(value.get(key)):
            _fail("SUCCESSOR_M4_PAYLOAD_INVALID")
    payload = {key: item for key, item in value.items() if key != "output_digest"}
    if (
        value["output_digest"]
        != hashlib.sha256(
            cast(str, value["schema_version"]).encode("utf-8")
            + b"\n"
            + canonical_json_bytes(payload)
        ).hexdigest()
    ):
        _fail("SUCCESSOR_M4_PAYLOAD_INVALID")
    return cast(Mapping[str, object], value)


def _validate_record(value: object, digest_key: str) -> None:
    if (
        not isinstance(value, Mapping)
        or digest_key not in value
        or not _is_digest(value[digest_key])
    ):
        _fail("SUCCESSOR_PUBLIC_RECORD_INVALID")
    _reject_private(value)


def _verify_file(path: Path, output: M4ExecutionOutput) -> None:
    content = _read_bytes(path, "SUCCESSOR_STORE_TAMPERED")
    if (
        hashlib.sha256(content).hexdigest() != output.result_sha256
        or len(content) != output.result_byte_size
    ):
        _fail("SUCCESSOR_STORE_TAMPERED")
    try:
        decode_canonical_rgb_image(
            content, expected_width=output.result_width, expected_height=output.result_height
        )
    except ImageSanitizationError as error:
        raise D02TargetedM4SuccessorCheckpointError("SUCCESSOR_STORE_TAMPERED") from error


def _atomic_create(path: Path, data: bytes, *, code: str = "SUCCESSOR_STORE_WRITE_FAILED") -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
        try:
            written = 0
            while written < len(data):
                count = os.write(descriptor, data[written:])
                if count < 1:
                    _fail(code)
                written += count
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise D02TargetedM4SuccessorCheckpointError(code) from error


def _read_bytes(path: Path, code: str) -> bytes:
    try:
        path_details = path.lstat()
        if _is_link_or_reparse(path_details) or not stat.S_ISREG(path_details.st_mode):
            _fail(code)
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                _fail(code)
            chunks: list[bytes] = []
            remaining = details.st_size
            while remaining:
                chunk = os.read(descriptor, remaining)
                if not chunk:
                    _fail(code)
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise D02TargetedM4SuccessorCheckpointError(code) from error


def _read_json(path: Path, code: str) -> object:
    try:
        return json.loads(_read_bytes(path, code).decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey) as error:
        raise D02TargetedM4SuccessorCheckpointError(code) from error


class _DuplicateJsonKey(ValueError):
    pass


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey()
        result[key] = value
    return result


def _digest(document: Mapping[str, object]) -> str:
    try:
        return hashlib.sha256(
            CHECKPOINT_SCHEMA.encode() + b"\n" + canonical_json_bytes(document)
        ).hexdigest()
    except DemoIdempotencyInputError as error:
        raise D02TargetedM4SuccessorCheckpointError("SUCCESSOR_CHECKPOINT_INVALID") from error


def _workspace(path: Path) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        _fail("SUCCESSOR_WORKSPACE_INVALID")
    _safe_existing_directory(path, code="SUCCESSOR_WORKSPACE_INVALID")
    return path


def _safe_workspace_directory(
    root: Path, relative: Path, *, create: bool, code: str
) -> Path | None:
    """Return a verified workspace descendant without following links or reparses.

    ``O_NOFOLLOW`` protects only the terminal file.  Each directory component
    therefore receives a lexical, lstat, resolved-path and regular-directory
    check before it is used for a create, read, or replacement operation.
    """

    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        _fail(code)
    _safe_existing_directory(root, code=code)
    current = root
    for part in relative.parts:
        candidate = current / part
        try:
            candidate.lstat()
        except FileNotFoundError:
            if not create:
                return None
            try:
                os.mkdir(candidate, 0o700)
            except OSError as error:
                raise D02TargetedM4SuccessorCheckpointError(code) from error
            _safe_existing_directory(current, code=code)
        except OSError as error:
            raise D02TargetedM4SuccessorCheckpointError(code) from error
        _safe_existing_directory(candidate, code=code)
        current = candidate
    return current


def _safe_existing_directory(path: Path, *, code: str) -> None:
    try:
        details = path.lstat()
        if _is_link_or_reparse(details) or not stat.S_ISDIR(details.st_mode):
            _fail(code)
        if path.resolve(strict=True) != path:
            _fail(code)
    except D02TargetedM4SuccessorCheckpointError:
        raise
    except OSError as error:
        raise D02TargetedM4SuccessorCheckpointError(code) from error


def _is_link_or_reparse(details: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return stat.S_ISLNK(details.st_mode) or bool(
        getattr(details, "st_file_attributes", 0) & reparse_flag
    )


def _path_present(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError as error:
        raise D02TargetedM4SuccessorCheckpointError("SUCCESSOR_PATH_STATE_INVALID") from error


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(char in "0123456789abcdef" for char in value)
    )


def _reject_private(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in _PRIVATE_KEYS:
                _fail("SUCCESSOR_PUBLIC_PAYLOAD_PRIVATE_FIELD")
            _reject_private(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_private(item)
    elif isinstance(value, bytes) or (
        isinstance(value, str) and ("\\" in value or value.startswith("file:"))
    ):
        _fail("SUCCESSOR_PUBLIC_PAYLOAD_PRIVATE_FIELD")


def _fail(code: str) -> NoReturn:
    raise D02TargetedM4SuccessorCheckpointError(code)
