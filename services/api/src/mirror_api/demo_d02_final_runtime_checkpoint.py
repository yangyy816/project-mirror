"""Ignored recovery checkpoint for the post-Manifest D02 runtime stage.

PostgreSQL remains the only business-state authority.  This file only retains
the public, replayable adapter evidence needed to avoid a second M3/M4 run
after process interruption.  Result JPEG bytes stay in the separate two-copy
availability store; source bytes stay in the Candidate index.
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

from mirror_api import demo_d02_generic_screening as generic_screening
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_r2_screening_execution as screening_execution
from mirror_api.demo_d02_candidate_qualification import NormalizedCandidateMaterial
from mirror_api.demo_d02_final_orchestrator import (
    _PREPARED_TOKEN,
    FormalRuntimeBundleView,
    PreparedRuntimeEvidence,
    RuntimeReviewSubject,
)
from mirror_api.demo_d02_generic_admission import GenericSourceInput
from mirror_api.demo_d02_runtime_result_store import D02RuntimeResultStore
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision
from mirror_api.demo_idempotency import canonical_json_bytes

CHECKPOINT_SCHEMA: Final = "mirror.private/D02FinalRuntimeRecoveryCheckpoint/v1"
CHECKPOINT_RELATIVE: Final = Path(".private-handoff") / "D02_FINAL_RUNTIME_CHECKPOINT.json"
_MAXIMUM_CHECKPOINT_BYTES: Final = 32 * 1024 * 1024
_FORBIDDEN_KEYS: Final = frozenset(
    {
        "absolute_path",
        "content",
        "image_bytes",
        "locator",
        "object_key",
        "path",
        "private_locator",
        "prompt",
        "prompt_text",
        "raw_bytes",
        "secret",
        "signed_url",
        "storage_key",
        "token",
        "url",
    }
)


class D02FinalRuntimeCheckpointError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RecoveredFormalSource:
    position: int
    source_input: GenericSourceInput
    source_row: Mapping[str, object]
    identity_row: Mapping[str, object]
    source_m3_outputs: tuple[
        runtime.M3ExecutionOutput,
        runtime.M3ExecutionOutput,
        runtime.M3ExecutionOutput,
    ]


@dataclass(frozen=True, slots=True)
class RecoveredFormalRuntimeBundle:
    sources: tuple[
        RecoveredFormalSource,
        RecoveredFormalSource,
        RecoveredFormalSource,
        RecoveredFormalSource,
    ]
    source_manifest_entries: tuple[
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object],
    ]
    formal_source_manifest_digest: str
    runtime_source_manifest_digest: str
    runtime_packets: tuple[
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object],
    ]
    descriptor_manifest: runtime.SourceDescriptorManifest
    runtime_handle: runtime.M3RuntimeHandle
    model_handle: runtime.M3ModelHandle


@dataclass(frozen=True, slots=True)
class RecoveredFinalRuntime:
    prepared: PreparedRuntimeEvidence
    artifact_decisions: Mapping[str, PrincipalArtifactDecision] | None
    stage: str


class D02FinalRuntimeCheckpoint:
    def __init__(
        self,
        *,
        workspace_root: Path,
        availability_binding_digest: str,
        acquisition_run_id: str,
        selected_manifest_digest: str,
        admission_idempotency_key_hash: str,
        result_store: D02RuntimeResultStore,
    ) -> None:
        if (
            not isinstance(workspace_root, Path)
            or not workspace_root.is_absolute()
            or not _is_id(acquisition_run_id)
            or not _is_digest(selected_manifest_digest)
            or not _is_digest(availability_binding_digest)
            or not _is_digest(admission_idempotency_key_hash)
        ):
            _fail("FINAL_RUNTIME_CHECKPOINT_BINDING_INVALID")
        try:
            resolved = workspace_root.resolve(strict=True)
        except OSError as error:
            raise D02FinalRuntimeCheckpointError(
                "FINAL_RUNTIME_CHECKPOINT_BINDING_INVALID"
            ) from error
        if resolved != workspace_root or not workspace_root.is_dir():
            _fail("FINAL_RUNTIME_CHECKPOINT_BINDING_INVALID")
        self._workspace_root = workspace_root
        self._private_parent = workspace_root / CHECKPOINT_RELATIVE.parent
        self._path = workspace_root / CHECKPOINT_RELATIVE
        self._availability_binding_digest = availability_binding_digest
        self._acquisition_run_id = acquisition_run_id
        self._selected_manifest_digest = selected_manifest_digest
        self._admission_idempotency_key_hash = admission_idempotency_key_hash
        self._result_store = result_store

    @property
    def exists(self) -> bool:
        return self._path.exists()

    def save_prepared(self, prepared: PreparedRuntimeEvidence) -> None:
        self._write(self._document(prepared=prepared, decisions=None, stage="PREPARED"))

    def save_reviewed(
        self,
        *,
        prepared: PreparedRuntimeEvidence,
        decisions: Mapping[str, PrincipalArtifactDecision],
    ) -> None:
        if set(decisions) != {item.case_id for item in prepared.review_subjects}:
            _fail("FINAL_RUNTIME_REVIEW_CARDINALITY_INVALID")
        self._write(self._document(prepared=prepared, decisions=decisions, stage="REVIEWED"))

    def load(
        self,
        *,
        materials: Sequence[NormalizedCandidateMaterial | runtime.SourceMaterial],
    ) -> RecoveredFinalRuntime:
        document = self._read_document()
        if len(materials) != 4:
            _fail("FINAL_RUNTIME_SOURCE_MATERIAL_INVALID")
        packets_raw = document.get("runtime_packets")
        source_outputs_raw = document.get("source_m3_outputs")
        if (
            not isinstance(packets_raw, list)
            or len(packets_raw) != 4
            or not isinstance(source_outputs_raw, list)
            or len(source_outputs_raw) != 4
        ):
            _fail("FINAL_RUNTIME_CHECKPOINT_INVALID")
        packets = cast(
            tuple[
                Mapping[str, object],
                Mapping[str, object],
                Mapping[str, object],
                Mapping[str, object],
            ],
            tuple(_mapping(item, "FINAL_RUNTIME_PACKET") for item in packets_raw),
        )
        runtime_manifest_digest = screening_execution._validated_sources(packets)[2]
        if runtime_manifest_digest != document.get("runtime_source_manifest_digest"):
            _fail("FINAL_RUNTIME_MANIFEST_BINDING_INVALID")
        sources: list[RecoveredFormalSource] = []
        for position, (packet, raw_outputs) in enumerate(
            zip(packets, source_outputs_raw, strict=True), start=1
        ):
            if not isinstance(raw_outputs, list) or len(raw_outputs) != 3:
                _fail("FINAL_RUNTIME_SOURCE_M3_INVALID")
            source_input = generic_screening.decode_generic_source_input(packet.get("source_input"))
            row = _mapping(packet.get("supporting_row"), "FINAL_RUNTIME_SOURCE_ROW")
            identity = _mapping(packet.get("identity_row"), "FINAL_RUNTIME_IDENTITY_ROW")
            outputs = cast(
                tuple[
                    runtime.M3ExecutionOutput,
                    runtime.M3ExecutionOutput,
                    runtime.M3ExecutionOutput,
                ],
                tuple(_parse_m3_output(item) for item in raw_outputs),
            )
            sources.append(
                RecoveredFormalSource(
                    position=position,
                    source_input=source_input,
                    source_row=dict(row),
                    identity_row=dict(identity),
                    source_m3_outputs=outputs,
                )
            )
        first = sources[0].source_input
        entries, formal_digest = generic_screening.build_formal_source_manifest(
            source_inputs=tuple(item.source_input for item in sources),
            source_rows=tuple(item.source_row for item in sources),
            identity_rows=tuple(item.identity_row for item in sources),
            selected_source_manifest_id=first.manifest_id,
            selected_source_manifest_digest=first.manifest_content_digest,
        )
        if (
            first.acquisition_run_id != self._acquisition_run_id
            or first.manifest_content_digest != self._selected_manifest_digest
            or formal_digest != document.get("formal_source_manifest_digest")
            or any(
                dict(entry)
                != dict(
                    _mapping(
                        packet.get("source_manifest_entry"),
                        "FINAL_RUNTIME_SOURCE_MANIFEST_ENTRY",
                    )
                )
                for entry, packet in zip(entries, packets, strict=True)
            )
        ):
            _fail("FINAL_RUNTIME_MANIFEST_BINDING_INVALID")
        descriptor_manifest = runtime.SourceDescriptorManifest.from_generic_packets(packets)
        recipe = runtime.build_default_runtime_recipe()
        model = runtime.build_default_model_identity()
        runtime_handle, model_handle = runtime.mint_runtime_handles(
            descriptor_manifest, recipe=recipe, model_identity=model
        )
        if (
            recipe.recipe_digest != document.get("recipe_digest")
            or model.identity_digest != document.get("model_identity_digest")
            or runtime_handle.handle_digest != document.get("runtime_handle_digest")
            or model_handle.handle_digest != document.get("model_handle_digest")
        ):
            _fail("FINAL_RUNTIME_HANDLE_BINDING_INVALID")
        bundle = RecoveredFormalRuntimeBundle(
            sources=cast(
                tuple[
                    RecoveredFormalSource,
                    RecoveredFormalSource,
                    RecoveredFormalSource,
                    RecoveredFormalSource,
                ],
                tuple(sources),
            ),
            source_manifest_entries=cast(
                tuple[
                    Mapping[str, object],
                    Mapping[str, object],
                    Mapping[str, object],
                    Mapping[str, object],
                ],
                tuple(entries),
            ),
            formal_source_manifest_digest=formal_digest,
            runtime_source_manifest_digest=runtime_manifest_digest,
            runtime_packets=packets,
            descriptor_manifest=descriptor_manifest,
            runtime_handle=runtime_handle,
            model_handle=model_handle,
        )
        source_materials = cast(
            tuple[
                runtime.SourceMaterial,
                runtime.SourceMaterial,
                runtime.SourceMaterial,
                runtime.SourceMaterial,
            ],
            tuple(
                _source_material(descriptor, material)
                for descriptor, material in zip(
                    descriptor_manifest.descriptors, materials, strict=True
                )
            ),
        )
        result_outputs = self._result_store.finalize()
        output_descriptors = document.get("result_outputs")
        if not isinstance(output_descriptors, list) or len(output_descriptors) != 48:
            _fail("FINAL_RUNTIME_RESULT_OUTPUT_INVALID")
        if any(
            _output_payload(output) != descriptor
            for output, descriptor in zip(result_outputs, output_descriptors, strict=True)
        ):
            _fail("FINAL_RUNTIME_RESULT_OUTPUT_INVALID")
        prepared = PreparedRuntimeEvidence(
            formal_bundle=cast(FormalRuntimeBundleView, bundle),
            source_materials=source_materials,
            recipe=recipe,
            model_identity=model,
            created_at=cast(str, document["created_at"]),
            execution_authority=_mapping(
                document["execution_authority"], "FINAL_RUNTIME_EXECUTION_AUTHORITY"
            ),
            cases=_mapping_tuple(document["cases"], 48, "FINAL_RUNTIME_CASES"),
            m4_adapter_fields=_mapping_tuple(document["m4_adapter_fields"], 96, "FINAL_RUNTIME_M4"),
            result_m3_adapter_fields=_mapping_tuple(
                document["result_m3_adapter_fields"], 144, "FINAL_RUNTIME_RESULT_M3"
            ),
            result_outputs=result_outputs,
            _factory_token=_PREPARED_TOKEN,
        )
        decisions = _parse_decisions(document.get("artifact_decisions"), prepared.review_subjects)
        stage = cast(str, document["stage"])
        if (stage == "PREPARED") != (decisions is None):
            _fail("FINAL_RUNTIME_CHECKPOINT_STAGE_INVALID")
        return RecoveredFinalRuntime(
            prepared=prepared,
            artifact_decisions=decisions,
            stage=stage,
        )

    def _document(
        self,
        *,
        prepared: PreparedRuntimeEvidence,
        decisions: Mapping[str, PrincipalArtifactDecision] | None,
        stage: str,
    ) -> dict[str, object]:
        if stage not in {"PREPARED", "REVIEWED"}:
            _fail("FINAL_RUNTIME_CHECKPOINT_STAGE_INVALID")
        bundle = prepared.formal_bundle
        payload: dict[str, object] = {
            "authority": "AVAILABILITY_RECOVERY_ONLY_NOT_BUSINESS_STATE",
            "business_authority": False,
            "availability_binding_digest": self._availability_binding_digest,
            "acquisition_run_id": self._acquisition_run_id,
            "selected_manifest_digest": self._selected_manifest_digest,
            "admission_idempotency_key_hash": self._admission_idempotency_key_hash,
            "stage": stage,
            "created_at": prepared.created_at,
            "formal_source_manifest_digest": bundle.formal_source_manifest_digest,
            "runtime_source_manifest_digest": bundle.runtime_source_manifest_digest,
            "recipe_digest": prepared.recipe.recipe_digest,
            "model_identity_digest": prepared.model_identity.identity_digest,
            "runtime_handle_digest": bundle.runtime_handle.handle_digest,
            "model_handle_digest": bundle.model_handle.handle_digest,
            "runtime_packets": [dict(item) for item in bundle.runtime_packets],
            "source_m3_outputs": [
                [_m3_output_payload(output) for output in source.source_m3_outputs]
                for source in bundle.sources
            ],
            "execution_authority": dict(prepared.execution_authority),
            "cases": [dict(item) for item in prepared.cases],
            "m4_adapter_fields": [dict(item) for item in prepared.m4_adapter_fields],
            "result_m3_adapter_fields": [dict(item) for item in prepared.result_m3_adapter_fields],
            "result_outputs": [_output_payload(output) for output in prepared.result_outputs],
            "artifact_decisions": (
                [_decision_payload(decisions[item.case_id]) for item in prepared.review_subjects]
                if decisions is not None
                else None
            ),
        }
        _reject_private_tree(payload)
        return {
            "schema_version": CHECKPOINT_SCHEMA,
            **payload,
            "payload_digest": _digest(CHECKPOINT_SCHEMA, payload),
        }

    def _write(self, document: Mapping[str, object]) -> None:
        _directory_exact(self._private_parent)
        if self._path.exists():
            current = self._read_document()
            if current == document:
                return
            current_stage = current.get("stage")
            if not (current_stage == "PREPARED" and document.get("stage") == "REVIEWED"):
                _fail("FINAL_RUNTIME_CHECKPOINT_COLLISION")
            for key in current:
                if key not in {"stage", "artifact_decisions", "payload_digest"} and current.get(
                    key
                ) != document.get(key):
                    _fail("FINAL_RUNTIME_CHECKPOINT_COLLISION")
        data = _json_bytes(document)
        incoming = self._path.with_name(".D02_FINAL_RUNTIME_CHECKPOINT.json.incoming")
        target = self._path if not self._path.exists() else incoming
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags, 0o600)
            try:
                _write_all(descriptor, data)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            if target == incoming:
                os.replace(incoming, self._path)
            _sync_directory(self._private_parent)
        except OSError as error:
            try:
                incoming.unlink(missing_ok=True)
            except OSError:
                pass
            raise D02FinalRuntimeCheckpointError("FINAL_RUNTIME_CHECKPOINT_WRITE_FAILED") from error
        if self._read_document() != dict(document):
            _fail("FINAL_RUNTIME_CHECKPOINT_REPLAY_FAILED")

    def _read_document(self) -> dict[str, object]:
        identity = _regular_identity(self._path)
        content = _read_exact(self._path, identity)
        if len(content) > _MAXIMUM_CHECKPOINT_BYTES:
            _fail("FINAL_RUNTIME_CHECKPOINT_INVALID")
        try:
            value = json.loads(content.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise D02FinalRuntimeCheckpointError("FINAL_RUNTIME_CHECKPOINT_INVALID") from error
        if not isinstance(value, dict):
            _fail("FINAL_RUNTIME_CHECKPOINT_INVALID")
        required = {
            "schema_version",
            "authority",
            "business_authority",
            "availability_binding_digest",
            "acquisition_run_id",
            "selected_manifest_digest",
            "admission_idempotency_key_hash",
            "stage",
            "created_at",
            "formal_source_manifest_digest",
            "runtime_source_manifest_digest",
            "recipe_digest",
            "model_identity_digest",
            "runtime_handle_digest",
            "model_handle_digest",
            "runtime_packets",
            "source_m3_outputs",
            "execution_authority",
            "cases",
            "m4_adapter_fields",
            "result_m3_adapter_fields",
            "result_outputs",
            "artifact_decisions",
            "payload_digest",
        }
        payload = {
            key: item
            for key, item in value.items()
            if key not in {"schema_version", "payload_digest"}
        }
        if (
            set(value) != required
            or value.get("schema_version") != CHECKPOINT_SCHEMA
            or value.get("authority") != "AVAILABILITY_RECOVERY_ONLY_NOT_BUSINESS_STATE"
            or value.get("business_authority") is not False
            or value.get("availability_binding_digest") != self._availability_binding_digest
            or value.get("acquisition_run_id") != self._acquisition_run_id
            or value.get("selected_manifest_digest") != self._selected_manifest_digest
            or value.get("admission_idempotency_key_hash") != self._admission_idempotency_key_hash
            or value.get("stage") not in {"PREPARED", "REVIEWED"}
            or value.get("payload_digest") != _digest(CHECKPOINT_SCHEMA, payload)
        ):
            _fail("FINAL_RUNTIME_CHECKPOINT_INVALID")
        _reject_private_tree(payload)
        return cast(dict[str, object], value)


def _source_material(
    descriptor: runtime.DurableSourceDescriptor,
    material: NormalizedCandidateMaterial | runtime.SourceMaterial,
) -> runtime.SourceMaterial:
    if isinstance(material, runtime.SourceMaterial):
        if material.descriptor != descriptor:
            _fail("FINAL_RUNTIME_SOURCE_MATERIAL_INVALID")
        return material
    if (
        descriptor.content_sha256 != material.sha256
        or descriptor.source_output_id != material.source_output_id
        or descriptor.byte_length != material.byte_size
        or descriptor.width != material.width
        or descriptor.height != material.height
    ):
        _fail("FINAL_RUNTIME_SOURCE_MATERIAL_INVALID")
    return runtime.SourceMaterial(descriptor=descriptor, content=material.content)


def _m3_output_payload(output: runtime.M3ExecutionOutput) -> dict[str, object]:
    return {
        "schema_version": output.schema_version,
        "payload_schema": output.payload_schema,
        "fields": dict(output.fields),
        "output_digest": output.output_digest,
    }


def _parse_m3_output(value: object) -> runtime.M3ExecutionOutput:
    item = _mapping(value, "FINAL_RUNTIME_M3_OUTPUT")
    if set(item) != {"schema_version", "payload_schema", "fields", "output_digest"}:
        _fail("FINAL_RUNTIME_SOURCE_M3_INVALID")
    return runtime.M3ExecutionOutput(
        schema_version=cast(str, item["schema_version"]),
        payload_schema=cast(str, item["payload_schema"]),
        fields=_mapping(item["fields"], "FINAL_RUNTIME_M3_FIELDS"),
        output_digest=cast(str, item["output_digest"]),
    )


def _output_payload(output: runtime.M4ExecutionOutput) -> dict[str, object]:
    return {**output.payload(), "output_digest": output.output_digest}


def _decision_payload(value: PrincipalArtifactDecision) -> dict[str, object]:
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


def _parse_decisions(
    value: object, subjects: Sequence[RuntimeReviewSubject]
) -> Mapping[str, PrincipalArtifactDecision] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 48 or len(subjects) != 48:
        _fail("FINAL_RUNTIME_REVIEW_CARDINALITY_INVALID")
    result: dict[str, PrincipalArtifactDecision] = {}
    for raw, subject in zip(value, subjects, strict=True):
        item = _mapping(raw, "FINAL_RUNTIME_REVIEW")
        if set(item) != {
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
        }:
            _fail("FINAL_RUNTIME_REVIEW_INVALID")
        decision = PrincipalArtifactDecision(
            case_id=cast(str, item["case_id"]),
            result_sha256=cast(str, item["result_sha256"]),
            decision_sequence=cast(int, item["decision_sequence"]),
            manual_review_version=cast(str, item["manual_review_version"]),
            manual_review_policy_digest=cast(str, item["manual_review_policy_digest"]),
            background_seam=cast(bool, item["background_seam"]),
            disconnected_contour=cast(bool, item["disconnected_contour"]),
            duplicated_feature=cast(bool, item["duplicated_feature"]),
            warp_tear=cast(bool, item["warp_tear"]),
            review_authority_digest=cast(str, item["review_authority_digest"]),
        )
        if (
            decision.case_id != subject.case_id
            or decision.result_sha256 != subject.result_sha256
            or decision.decision_sequence != subject.decision_sequence
        ):
            _fail("FINAL_RUNTIME_REVIEW_INVALID")
        result[decision.case_id] = decision
    return result


def _mapping_tuple(value: object, count: int, label: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or len(value) != count:
        _fail(f"{label}_INVALID")
    return tuple(dict(_mapping(item, label)) for item in value)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label}_INVALID")
    return cast(Mapping[str, object], value)


def _reject_private_tree(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in _FORBIDDEN_KEYS:
                _fail("FINAL_RUNTIME_CHECKPOINT_PRIVATE_FIELD_FORBIDDEN")
            _reject_private_tree(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private_tree(item)
    elif isinstance(value, bytes):
        _fail("FINAL_RUNTIME_CHECKPOINT_PRIVATE_FIELD_FORBIDDEN")


def _digest(schema: str, payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = item
    return result


def _directory_exact(path: Path) -> None:
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise D02FinalRuntimeCheckpointError("FINAL_RUNTIME_PRIVATE_NAMESPACE_INVALID") from error
    if (
        resolved != path
        or not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
    ):
        _fail("FINAL_RUNTIME_PRIVATE_NAMESPACE_INVALID")


def _regular_identity(path: Path) -> tuple[int, int]:
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise D02FinalRuntimeCheckpointError("FINAL_RUNTIME_CHECKPOINT_UNAVAILABLE") from error
    if (
        resolved != path
        or parent != path.parent
        or not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
    ):
        _fail("FINAL_RUNTIME_CHECKPOINT_INVALID")
    return info.st_dev, info.st_ino


def _read_exact(path: Path, identity: tuple[int, int]) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != identity:
                _fail("FINAL_RUNTIME_CHECKPOINT_INVALID")
            chunks: list[bytes] = []
            total = 0
            while chunk := os.read(descriptor, 1_048_576):
                total += len(chunk)
                if total > _MAXIMUM_CHECKPOINT_BYTES:
                    _fail("FINAL_RUNTIME_CHECKPOINT_INVALID")
                chunks.append(chunk)
            if _regular_identity(path) != identity:
                _fail("FINAL_RUNTIME_CHECKPOINT_INVALID")
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except D02FinalRuntimeCheckpointError:
        raise
    except OSError as error:
        raise D02FinalRuntimeCheckpointError("FINAL_RUNTIME_CHECKPOINT_UNAVAILABLE") from error


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(descriptor, view[offset:])
        if written <= 0:
            _fail("FINAL_RUNTIME_CHECKPOINT_WRITE_FAILED")
        offset += written


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _is_reparse(info: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and getattr(info, "st_file_attributes", 0) & flag)


def _fail(code: str) -> NoReturn:
    raise D02FinalRuntimeCheckpointError(code)
