"""Typed, replayable D08 fixed-case geometry execution evidence.

This is deliberately an in-process boundary.  It does not discover D02 data,
open an Asset, run M3, or persist a Job.  Its inputs are already-derived,
non-private authority facts and the fresh structural result returned by the
injected D02-compatible backend.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from mirror_api import demo_d02_targeted_m4_repair as targeted_repair
from mirror_api.demo_d02_targeted_m4_repair_backend import D02TargetedM4RepairBackend
from mirror_api.demo_operation_graph import OperationSpec, canonical_json_bytes
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION, CANDIDATE_ID

D08_SCHEMA_VERSION: Final = "mirror.demo/D08GeometryAdapter/v1"
D08_VERIFIER_POLICY_VERSION: Final = "d08-independent-geometry-verifier-v1"
D08_OPERATION_SPEC_DIGEST_SCHEMA_VERSION: Final = "mirror.demo/D08OperationSpecDigest/v1"
FIXED_GEOMETRY_DIMENSIONS: Final = frozenset({"jaw_width", "chin_height", "eye_spacing"})
FIXED_GEOMETRY_MAGNITUDES_PPM: Final = frozenset({15_000, 30_000})
FIXED_RESULT_MEDIA_TYPE: Final = "image/jpeg"
MAX_IMAGE_DIMENSION: Final = 20_000
TARGETED_REPAIR_ALGORITHM_VERSION: Final = D02TargetedM4RepairBackend.algorithm_version
TARGETED_REPAIR_CANDIDATE_ID: Final = "D02_TARGETED_JAW_REPAIR_V1"

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[0-9a-f]{32}$")
_OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class GeometryDirection(StrEnum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"


class GeometryAdapterAuthorityError(ValueError):
    """A typed D08 authority or evidence object is not internally consistent."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def qualified_backend_candidate_id(
    *,
    case_ordinal: int,
    source_ordinal: int,
    dimension_key: str,
    direction: str,
    magnitude_ppm: int,
    algorithm_version: str,
) -> str:
    """Resolve the exact tracked backend allowlist for one admitted case.

    The accepted successor universe is deliberately heterogeneous: ordinary
    cases use the frozen OpenCV backend, while ADR-053 may replace only its
    exact Case-25 selector with the source-byte-bound repair backend.
    """

    if algorithm_version == ALGORITHM_VERSION:
        return CANDIDATE_ID
    selector = targeted_repair.TARGET_SELECTOR
    if algorithm_version == TARGETED_REPAIR_ALGORITHM_VERSION and (
        case_ordinal == targeted_repair.TARGET_CASE_ORDINAL
        and source_ordinal == targeted_repair.TARGET_SOURCE_ORDINAL
        and dimension_key == selector["dimension_key"]
        and direction == selector["direction"]
        and magnitude_ppm == selector["magnitude_ppm"]
    ):
        return TARGETED_REPAIR_CANDIDATE_ID
    raise GeometryAdapterAuthorityError(
        "UNQUALIFIED_BACKEND", "case backend is not in the exact D08 allowlist"
    )


@dataclass(frozen=True, slots=True)
class D02FixedGeometryCase:
    """Public, fixed D02 case facts.  It never carries a historical result."""

    case_id: str
    case_record_digest: str
    case_specification_digest: str
    case_binding_digest: str
    case_ordinal: int
    source_ordinal: int
    source_asset_id: str
    source_asset_sha256: str
    dimension_key: str
    direction: GeometryDirection
    magnitude_ppm: int
    warp_plan_digest: str
    geometry_ontology_digest: str
    source_landmark_digest: str
    output_policy_version: str
    determinism_version: str
    backend_candidate_id: str
    backend_algorithm_version: str
    backend_runtime_manifest_digest: str
    backend_configuration_digest: str
    output_width: int
    output_height: int

    def __post_init__(self) -> None:
        _id(self.case_id, "case_id")
        _bounded_integer(self.case_ordinal, "case_ordinal", 1, 48)
        _bounded_integer(self.source_ordinal, "source_ordinal", 1, 4)
        _id(self.source_asset_id, "source_asset_id")
        _digest(self.source_asset_sha256, "source_asset_sha256")
        _dimension(self.dimension_key)
        if not isinstance(self.direction, GeometryDirection):
            raise GeometryAdapterAuthorityError("INVALID_DIRECTION", "direction is invalid")
        _magnitude(self.magnitude_ppm)
        for name in (
            "warp_plan_digest",
            "geometry_ontology_digest",
            "source_landmark_digest",
            "backend_runtime_manifest_digest",
            "backend_configuration_digest",
            "case_record_digest",
            "case_specification_digest",
        ):
            _digest(getattr(self, name), name)
        for name in (
            "output_policy_version",
            "determinism_version",
            "backend_candidate_id",
            "backend_algorithm_version",
        ):
            _opaque(getattr(self, name), name)
        expected_candidate = qualified_backend_candidate_id(
            case_ordinal=self.case_ordinal,
            source_ordinal=self.source_ordinal,
            dimension_key=self.dimension_key,
            direction=self.direction.value,
            magnitude_ppm=self.magnitude_ppm,
            algorithm_version=self.backend_algorithm_version,
        )
        if self.backend_candidate_id != expected_candidate:
            raise GeometryAdapterAuthorityError(
                "BACKEND_CANDIDATE_MISMATCH",
                "backend candidate does not match the admitted case algorithm",
            )
        _digest(self.case_binding_digest, "case_binding_digest")
        _positive(self.output_width, "output_width", maximum=MAX_IMAGE_DIMENSION)
        _positive(self.output_height, "output_height", maximum=MAX_IMAGE_DIMENSION)
        expected_digest = self.content_digest()
        if self.case_binding_digest == "0" * 64:
            object.__setattr__(self, "case_binding_digest", expected_digest)
        elif self.case_binding_digest != expected_digest:
            raise GeometryAdapterAuthorityError(
                "CASE_BINDING_DIGEST_MISMATCH", "case binding digest does not replay"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "backend_algorithm_version": self.backend_algorithm_version,
            "backend_candidate_id": self.backend_candidate_id,
            "backend_configuration_digest": self.backend_configuration_digest,
            "backend_runtime_manifest_digest": self.backend_runtime_manifest_digest,
            "case_record_digest": self.case_record_digest,
            "case_specification_digest": self.case_specification_digest,
            "case_id": self.case_id,
            "case_ordinal": self.case_ordinal,
            "determinism_version": self.determinism_version,
            "dimension_key": self.dimension_key,
            "direction": self.direction.value,
            "geometry_ontology_digest": self.geometry_ontology_digest,
            "magnitude_ppm": self.magnitude_ppm,
            "output_height": self.output_height,
            "output_policy_version": self.output_policy_version,
            "output_width": self.output_width,
            "schema_version": D08_SCHEMA_VERSION,
            "source_asset_id": self.source_asset_id,
            "source_asset_sha256": self.source_asset_sha256,
            "source_landmark_digest": self.source_landmark_digest,
            "source_ordinal": self.source_ordinal,
            "warp_plan_digest": self.warp_plan_digest,
        }

    def content_digest(self) -> str:
        return _content_digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class GeometryExecutionAuthority:
    """Repository-derived execution authority for sequence-zero D02 source only."""

    editing_session_id: str
    editing_session_digest: str
    plan_id: str
    plan_digest: str
    operation_id: str
    operation_authority_digest: str
    operation_spec_digest: str
    input_image_version_id: str
    input_image_version_digest: str
    input_sequence: int
    input_asset_id: str
    input_asset_sha256: str
    root_source_asset_id: str
    root_source_asset_sha256: str
    d02_admission_id: str
    d02_admission_digest: str
    d02_screening_report_id: str
    d02_screening_report_digest: str
    fixed_case: D02FixedGeometryCase
    authority_digest: str

    def __post_init__(self) -> None:
        for name in (
            "editing_session_id",
            "plan_id",
            "operation_id",
            "input_image_version_id",
            "input_asset_id",
            "root_source_asset_id",
            "d02_admission_id",
            "d02_screening_report_id",
        ):
            _id(getattr(self, name), name)
        for name in (
            "editing_session_digest",
            "plan_digest",
            "operation_authority_digest",
            "operation_spec_digest",
            "input_image_version_digest",
            "input_asset_sha256",
            "root_source_asset_sha256",
            "d02_admission_digest",
            "d02_screening_report_digest",
            "authority_digest",
        ):
            _digest(getattr(self, name), name)
        if not isinstance(self.fixed_case, D02FixedGeometryCase):
            raise GeometryAdapterAuthorityError("INVALID_CASE", "fixed case must be typed")
        if type(self.input_sequence) is not int or self.input_sequence != 0:
            raise GeometryAdapterAuthorityError(
                "INVALID_INPUT_SEQUENCE", "geometry is limited to sequence-zero source input"
            )
        if (
            self.input_asset_id == self.root_source_asset_id
            or self.input_asset_sha256 != self.root_source_asset_sha256
            or self.root_source_asset_id != self.fixed_case.source_asset_id
            or self.root_source_asset_sha256 != self.fixed_case.source_asset_sha256
        ):
            raise GeometryAdapterAuthorityError(
                "SOURCE_LINEAGE_MISMATCH", "input, root source, and fixed case must agree"
            )
        expected_digest = self.content_digest()
        if self.authority_digest == "0" * 64:
            object.__setattr__(self, "authority_digest", expected_digest)
        elif self.authority_digest != expected_digest:
            raise GeometryAdapterAuthorityError(
                "AUTHORITY_DIGEST_MISMATCH", "authority digest does not replay"
            )

    @property
    def dimension_key(self) -> str:
        return self.fixed_case.dimension_key

    @property
    def direction(self) -> GeometryDirection:
        return self.fixed_case.direction

    @property
    def magnitude_ppm(self) -> int:
        return self.fixed_case.magnitude_ppm

    def canonical_payload(self) -> dict[str, object]:
        return {
            "d02_admission_digest": self.d02_admission_digest,
            "d02_admission_id": self.d02_admission_id,
            "d02_screening_report_digest": self.d02_screening_report_digest,
            "d02_screening_report_id": self.d02_screening_report_id,
            "editing_session_digest": self.editing_session_digest,
            "editing_session_id": self.editing_session_id,
            "fixed_case": {
                **self.fixed_case.canonical_payload(),
                "case_binding_digest": self.fixed_case.case_binding_digest,
            },
            "input_asset_id": self.input_asset_id,
            "input_asset_sha256": self.input_asset_sha256,
            "input_image_version_digest": self.input_image_version_digest,
            "input_image_version_id": self.input_image_version_id,
            "input_sequence": self.input_sequence,
            "operation_authority_digest": self.operation_authority_digest,
            "operation_spec_digest": self.operation_spec_digest,
            "operation_id": self.operation_id,
            "plan_digest": self.plan_digest,
            "plan_id": self.plan_id,
            "root_source_asset_id": self.root_source_asset_id,
            "root_source_asset_sha256": self.root_source_asset_sha256,
            "schema_version": D08_SCHEMA_VERSION,
        }

    def content_digest(self) -> str:
        return _content_digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class GeometryJobAttemptBinding:
    job_id: str
    execution_job_binding_id: str
    job_binding_digest: str
    attempt_id: str
    attempt_digest: str

    def __post_init__(self) -> None:
        _id(self.job_id, "job_id")
        _id(self.execution_job_binding_id, "execution_job_binding_id")
        _id(self.attempt_id, "attempt_id")
        _digest(self.job_binding_digest, "job_binding_digest")
        _digest(self.attempt_digest, "attempt_digest")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "attempt_digest": self.attempt_digest,
            "attempt_id": self.attempt_id,
            "execution_job_binding_id": self.execution_job_binding_id,
            "job_binding_digest": self.job_binding_digest,
            "job_id": self.job_id,
        }


@dataclass(frozen=True, slots=True)
class GeometryStableMaterializationCore:
    """Attempt-independent materialization identity; it has no receipt or Job."""

    operation_id: str
    operation_authority_digest: str
    operation_spec_digest: str
    authority_digest: str
    case_id: str
    case_record_digest: str
    case_specification_digest: str
    case_binding_digest: str
    backend_candidate_id: str
    backend_algorithm_version: str
    backend_runtime_manifest_digest: str
    backend_configuration_digest: str
    warp_plan_digest: str
    input_image_version_id: str
    input_image_version_digest: str
    input_asset_id: str
    input_asset_sha256: str
    root_source_asset_id: str
    root_source_asset_sha256: str
    result_sha256: str
    result_byte_size: int
    result_media_type: str
    result_width: int
    result_height: int
    changed_pixel_count: int
    engine_digest: str
    config_digest: str
    stable_core_digest: str

    def __post_init__(self) -> None:
        for name in (
            "operation_id",
            "case_id",
            "input_image_version_id",
            "input_asset_id",
            "root_source_asset_id",
        ):
            _id(getattr(self, name), name)
        for name in (
            "operation_authority_digest",
            "operation_spec_digest",
            "authority_digest",
            "case_record_digest",
            "case_specification_digest",
            "case_binding_digest",
            "backend_runtime_manifest_digest",
            "backend_configuration_digest",
            "warp_plan_digest",
            "input_image_version_digest",
            "input_asset_sha256",
            "root_source_asset_sha256",
            "result_sha256",
            "engine_digest",
            "config_digest",
            "stable_core_digest",
        ):
            _digest(getattr(self, name), name)
        _opaque(self.backend_candidate_id, "backend_candidate_id")
        _opaque(self.backend_algorithm_version, "backend_algorithm_version")
        if self.result_media_type != FIXED_RESULT_MEDIA_TYPE:
            raise GeometryAdapterAuthorityError(
                "INVALID_RESULT_MEDIA_TYPE", "result media type is invalid"
            )
        _positive(self.result_byte_size, "result_byte_size")
        _positive(self.result_width, "result_width", maximum=MAX_IMAGE_DIMENSION)
        _positive(self.result_height, "result_height", maximum=MAX_IMAGE_DIMENSION)
        _bounded_integer(
            self.changed_pixel_count,
            "changed_pixel_count",
            1,
            self.result_width * self.result_height,
        )
        expected_digest = self.content_digest()
        if self.stable_core_digest == "0" * 64:
            object.__setattr__(self, "stable_core_digest", expected_digest)
        elif self.stable_core_digest != expected_digest:
            raise GeometryAdapterAuthorityError(
                "STABLE_CORE_DIGEST_MISMATCH", "stable core digest does not replay"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in (
                "authority_digest",
                "backend_algorithm_version",
                "backend_candidate_id",
                "backend_configuration_digest",
                "backend_runtime_manifest_digest",
                "case_record_digest",
                "case_specification_digest",
                "case_binding_digest",
                "case_id",
                "changed_pixel_count",
                "config_digest",
                "engine_digest",
                "input_asset_id",
                "input_asset_sha256",
                "input_image_version_digest",
                "input_image_version_id",
                "operation_authority_digest",
                "operation_spec_digest",
                "operation_id",
                "result_byte_size",
                "result_height",
                "result_media_type",
                "result_sha256",
                "result_width",
                "root_source_asset_id",
                "root_source_asset_sha256",
                "warp_plan_digest",
            )
        } | {"schema_version": D08_SCHEMA_VERSION}

    def content_digest(self) -> str:
        return _content_digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class GeometryAttemptExecutionEvidence:
    """Fresh, Attempt-specific receipt which never participates in stable replay."""

    job_attempt: GeometryJobAttemptBinding
    operation_id: str
    operation_authority_digest: str
    operation_spec_digest: str
    authority_digest: str
    stable_core_digest: str
    backend_execution_receipt: str
    attempt_receipt_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.job_attempt, GeometryJobAttemptBinding):
            raise GeometryAdapterAuthorityError("INVALID_JOB_ATTEMPT", "job attempt must be typed")
        _id(self.operation_id, "operation_id")
        for name in (
            "operation_authority_digest",
            "operation_spec_digest",
            "authority_digest",
            "stable_core_digest",
            "attempt_receipt_digest",
        ):
            _digest(getattr(self, name), name)
        _digest(self.backend_execution_receipt, "backend_execution_receipt")
        expected_digest = self.content_digest()
        if self.attempt_receipt_digest == "0" * 64:
            object.__setattr__(self, "attempt_receipt_digest", expected_digest)
        elif self.attempt_receipt_digest != expected_digest:
            raise GeometryAdapterAuthorityError(
                "ATTEMPT_RECEIPT_DIGEST_MISMATCH", "attempt receipt digest does not replay"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "authority_digest": self.authority_digest,
            "backend_execution_receipt": self.backend_execution_receipt,
            "job_attempt": self.job_attempt.canonical_payload(),
            "operation_authority_digest": self.operation_authority_digest,
            "operation_spec_digest": self.operation_spec_digest,
            "operation_id": self.operation_id,
            "schema_version": D08_SCHEMA_VERSION,
            "stable_core_digest": self.stable_core_digest,
        }

    def content_digest(self) -> str:
        return _content_digest(self.canonical_payload())


def stable_engine_digest(authority: GeometryExecutionAuthority, engine_version: str) -> str:
    _opaque(engine_version, "engine_version")
    case = authority.fixed_case
    return _content_digest(
        {
            "accepted_algorithm_version": case.backend_algorithm_version,
            "engine_version": engine_version,
            "runtime_manifest_digest": case.backend_runtime_manifest_digest,
            "schema_version": D08_SCHEMA_VERSION,
        }
    )


def stable_config_digest(
    authority: GeometryExecutionAuthority, verifier_policy_version: str
) -> str:
    _opaque(verifier_policy_version, "verifier_policy_version")
    case = authority.fixed_case
    return _content_digest(
        {
            "authority_digest": authority.authority_digest,
            "case_binding_digest": case.case_binding_digest,
            "case_record_digest": case.case_record_digest,
            "case_specification_digest": case.case_specification_digest,
            "operation_authority_digest": authority.operation_authority_digest,
            "operation_spec_digest": authority.operation_spec_digest,
            "output_policy_version": case.output_policy_version,
            "plan_digest": authority.plan_digest,
            "schema_version": D08_SCHEMA_VERSION,
            "verifier_policy_version": verifier_policy_version,
            "warp_plan_digest": case.warp_plan_digest,
        }
    )


def operation_spec_digest(operation: OperationSpec) -> str:
    """Digest a frozen OperationSpec projection without reading repository state."""

    if not isinstance(operation, OperationSpec):
        raise GeometryAdapterAuthorityError(
            "INVALID_OPERATION_SPEC", "operation spec must be typed"
        )
    return hashlib.sha256(
        D08_OPERATION_SPEC_DIGEST_SCHEMA_VERSION.encode("utf-8")
        + b"\n"
        + canonical_json_bytes(operation.canonical_payload())
    ).hexdigest()


def _content_digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        D08_SCHEMA_VERSION.encode() + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _digest(value: object, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GeometryAdapterAuthorityError(
            "INVALID_DIGEST", f"{name} must be a lowercase SHA-256 digest"
        )


def _id(value: object, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise GeometryAdapterAuthorityError(
            "INVALID_ID", f"{name} must be a 32-character lowercase identifier"
        )


def _opaque(value: object, name: str) -> None:
    if not isinstance(value, str) or _OPAQUE.fullmatch(value) is None:
        raise GeometryAdapterAuthorityError("INVALID_OPAQUE_VALUE", f"{name} is invalid")


def _dimension(value: object) -> None:
    if value not in FIXED_GEOMETRY_DIMENSIONS:
        raise GeometryAdapterAuthorityError(
            "UNSUPPORTED_DIMENSION", "dimension is not a fixed D08 dimension"
        )


def _magnitude(value: object) -> None:
    if type(value) is not int or value not in FIXED_GEOMETRY_MAGNITUDES_PPM:
        raise GeometryAdapterAuthorityError(
            "INVALID_MAGNITUDE", "magnitude must be exactly 15000 or 30000"
        )


def _positive(value: object, name: str, *, maximum: int | None = None) -> None:
    if type(value) is not int or value < 1 or (maximum is not None and value > maximum):
        raise GeometryAdapterAuthorityError(
            "INVALID_SCALAR", f"{name} is outside its allowed range"
        )


def _bounded_integer(value: object, name: str, minimum: int, maximum: int) -> None:
    if type(value) is not int or value < minimum or value > maximum:
        raise GeometryAdapterAuthorityError(
            "INVALID_SCALAR", f"{name} is outside its allowed range"
        )


def _nonnegative(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise GeometryAdapterAuthorityError(
            "INVALID_SCALAR", f"{name} must be a non-negative integer"
        )
