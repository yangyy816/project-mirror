"""Reconstructable Demo-only M3/M4 runtime boundary for D02-R2.

The module keeps durable handles separate from private runtime material.  It
never discovers paths, model bytes, image bytes, Prompt text, or task-scoped
objects.  The Integration Principal injects an already-qualified offline
backend; this module verifies its public identity and binds its outputs to the
existing D02-R2 screening authority.
"""

from __future__ import annotations

import hashlib
import io
import ntpath
import posixpath
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final, NoReturn, Protocol, cast

from PIL import Image, UnidentifiedImageError

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as authority
from mirror_api import demo_d02_r2_e3_admission as epoch3
from mirror_api import demo_d02_r2_epoch2_admission as epoch2
from mirror_api import demo_d02_r2_screening_execution as screening
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_r2_epoch2_admission import SOURCE_NORMALIZATION_VERSION
from mirror_api.demo_d02_r2_generation_e3 import (
    E3_CONTEXT,
    E4_CONTEXT,
    GenerationExecutionContext,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION as M4_ALGORITHM_VERSION

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

SOURCE_DESCRIPTOR_SCHEMA: Final = "mirror.demo/D02R2DurableSourceDescriptor/v1"
SOURCE_DESCRIPTOR_MANIFEST_SCHEMA: Final = "mirror.demo/D02R2DurableSourceDescriptorManifest/v1"
RUNTIME_RECIPE_SCHEMA: Final = "mirror.demo/D02R2DemoRuntimeRecipe/v1"
MODEL_IDENTITY_SCHEMA: Final = "mirror.demo/D02R2DemoModelIdentity/v1"
M3_RUNTIME_HANDLE_SCHEMA: Final = "mirror.demo/D02R2M3RuntimeHandle/v1"
M3_MODEL_HANDLE_SCHEMA: Final = "mirror.demo/D02R2M3ModelHandle/v1"
M3_EXECUTION_OUTPUT_SCHEMA: Final = "mirror.demo/D02R2M3ExecutionOutput/v1"
M4_EXECUTION_OUTPUT_SCHEMA: Final = "mirror.demo/D02R2M4ExecutionOutput/v1"

RUNTIME_RECIPE_VERSION: Final = "demo-m3-m4-runtime-recipe-v1"
E3_RUNTIME_RECIPE_VERSION: Final = "demo-m3-m4-runtime-recipe-e3-v1"
M3_ALGORITHM_VERSION: Final = "source-built-mediapipe-face-landmarker-v0.10.35"
MODEL_VERSION: Final = "face-landmarker-bundle-gcs-1683136941468629"
MODEL_PROVIDER_KIND: Final = "PRIVATE_SOURCE_BUILT_MEDIAPIPE"
MODEL_RUNTIME_DEPENDENCY_VERSION: Final = "mediapipe-v0.10.35-zero-telemetry"
MODEL_CAPABILITY_STATE: Final = "DEMO_SYNTHETIC_OFFLINE_ONLY"
NO_WEIGHTS_SENTINEL: Final = "NO_WEIGHTS_DETERMINISTIC_IMPLEMENTATION"
NETWORK_POLICY: Final = "PUBLIC_INTERNET_EGRESS_DISABLED"

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_ID_RE: Final = re.compile(r"[0-9a-f]{32}\Z")
_OUTPUT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_VERSION_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z")
_FORBIDDEN_KEYS: Final = {
    "absolute_path",
    "content",
    "image_bytes",
    "locator",
    "model_bytes",
    "object_key",
    "private_locator",
    "prompt",
    "prompt_text",
    "raw_bytes",
    "secret",
    "token",
}


class RuntimeForwardError(ValueError):
    """A durable handle, runtime identity, or offline execution failed closed."""


def _fail(message: str) -> NoReturn:
    raise RuntimeForwardError(message)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase 32-character ID")
    return value


def _version(value: object, label: str) -> str:
    if not isinstance(value, str) or _VERSION_RE.fullmatch(value) is None:
        _fail(f"{label} is invalid")
    return value


def _canonical_digest(schema: str, payload: Mapping[str, object]) -> str:
    return mirror_demo_digest(schema, cast(Mapping[str, JsonValue], payload))


def _assert_public_tree(value: object, *, label: str) -> None:
    if isinstance(value, bytes) or isinstance(value, float):
        _fail(f"{label} contains raw bytes or a non-canonical float")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in _FORBIDDEN_KEYS:
                _fail(f"{label} contains a forbidden field")
            _assert_public_tree(item, label=label)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _assert_public_tree(item, label=label)
        return
    if isinstance(value, str) and (ntpath.isabs(value) or posixpath.isabs(value)):
        _fail(f"{label} contains an absolute path")
    if value is not None and not isinstance(value, (str, int, bool)):
        _fail(f"{label} contains a non-canonical value")


@dataclass(frozen=True, slots=True)
class DurableSourceDescriptor:
    source_id: str
    source_output_id: str
    ordinal: int
    content_sha256: str
    media_type: str
    width: int
    height: int
    byte_length: int
    generation_request_identity: str
    provenance_identity: str
    source_authority_key: str
    source_schema_version: str
    schema_version: str = SOURCE_DESCRIPTOR_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_DESCRIPTOR_SCHEMA:
            _fail("source descriptor schema is invalid")
        _identifier(self.source_id, "source ID")
        if _OUTPUT_ID_RE.fullmatch(self.source_output_id) is None:
            _fail("source output ID is invalid")
        if type(self.ordinal) is not int or self.ordinal not in {1, 2, 3, 4}:
            _fail("source ordinal must be one through four")
        for value, label in (
            (self.content_sha256, "source content digest"),
            (self.generation_request_identity, "generation request identity"),
            (self.provenance_identity, "provenance identity"),
            (self.source_authority_key, "source authority key"),
        ):
            _digest(value, label)
        if self.media_type != "image/jpeg":
            _fail("Demo runtime accepts only canonical JPEG sources")
        if any(
            type(value) is not int or value < 1
            for value in (self.width, self.height, self.byte_length)
        ):
            _fail("source dimensions and byte length must be positive integers")
        _version(self.source_schema_version, "source schema version")

    def payload(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "source_output_id": self.source_output_id,
            "ordinal": self.ordinal,
            "content_sha256": self.content_sha256,
            "media_type": self.media_type,
            "width": self.width,
            "height": self.height,
            "byte_length": self.byte_length,
            "generation_request_identity": self.generation_request_identity,
            "provenance_identity": self.provenance_identity,
            "source_authority_key": self.source_authority_key,
            "source_schema_version": self.source_schema_version,
        }

    @property
    def descriptor_digest(self) -> str:
        return _canonical_digest(SOURCE_DESCRIPTOR_SCHEMA, self.payload())

    @classmethod
    def from_epoch2_packet(cls, packet: Mapping[str, object]) -> DurableSourceDescriptor:
        epoch2.validate_epoch2_admission_packet(packet)
        row = cast(Mapping[str, object], packet["supporting_row"])
        return cls(
            source_id=cast(str, row["source_asset_id"]),
            source_output_id=cast(str, row["source_output_id"]),
            ordinal=cast(int, row["source_ordinal"]),
            content_sha256=cast(str, row["source_asset_sha256"]),
            media_type=cast(str, row["source_asset_mime_type"]),
            width=cast(int, row["source_asset_width"]),
            height=cast(int, row["source_asset_height"]),
            byte_length=cast(int, row["source_asset_byte_size"]),
            generation_request_identity=cast(str, row["generation_request_digest"]),
            provenance_identity=cast(str, row["source_provenance_digest"]),
            source_authority_key=cast(str, row["source_authority_key"]),
            source_schema_version=cast(str, row["schema_version"]),
        )

    @classmethod
    def from_epoch3_packet(cls, packet: Mapping[str, object]) -> DurableSourceDescriptor:
        """Mint the unchanged durable descriptor from an E3-only packet.

        The descriptor schema deliberately remains v1: `source_schema_version`
        and the authority key carry the epoch-specific lineage while downstream
        M3/M4 handles retain their accepted contract.
        """

        epoch3.validate_epoch3_admission_packet(packet, context=E3_CONTEXT)
        row = cast(Mapping[str, object], packet["supporting_row"])
        return cls(
            source_id=cast(str, row["source_asset_id"]),
            source_output_id=cast(str, row["source_output_id"]),
            ordinal=cast(int, row["source_ordinal"]),
            content_sha256=cast(str, row["source_asset_sha256"]),
            media_type=cast(str, row["source_asset_mime_type"]),
            width=cast(int, row["source_asset_width"]),
            height=cast(int, row["source_asset_height"]),
            byte_length=cast(int, row["source_asset_byte_size"]),
            generation_request_identity=cast(str, row["generation_request_digest"]),
            provenance_identity=cast(str, row["source_provenance_digest"]),
            source_authority_key=cast(str, row["source_authority_key"]),
            source_schema_version=cast(str, row["schema_version"]),
        )

    @classmethod
    def from_forward_packet(
        cls,
        packet: Mapping[str, object],
        *,
        context: GenerationExecutionContext,
    ) -> DurableSourceDescriptor:
        epoch3.validate_epoch3_admission_packet(packet, context=context)
        row = cast(Mapping[str, object], packet["supporting_row"])
        return cls(
            source_id=cast(str, row["source_asset_id"]),
            source_output_id=cast(str, row["source_output_id"]),
            ordinal=cast(int, row["source_ordinal"]),
            content_sha256=cast(str, row["source_asset_sha256"]),
            media_type=cast(str, row["source_asset_mime_type"]),
            width=cast(int, row["source_asset_width"]),
            height=cast(int, row["source_asset_height"]),
            byte_length=cast(int, row["source_asset_byte_size"]),
            generation_request_identity=cast(str, row["generation_request_digest"]),
            provenance_identity=cast(str, row["source_provenance_digest"]),
            source_authority_key=cast(str, row["source_authority_key"]),
            source_schema_version=cast(str, row["schema_version"]),
        )


@dataclass(frozen=True, slots=True)
class SourceDescriptorManifest:
    descriptors: tuple[
        DurableSourceDescriptor,
        DurableSourceDescriptor,
        DurableSourceDescriptor,
        DurableSourceDescriptor,
    ]
    schema_version: str = SOURCE_DESCRIPTOR_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_DESCRIPTOR_MANIFEST_SCHEMA:
            _fail("source descriptor manifest schema is invalid")
        if tuple(item.ordinal for item in self.descriptors) != (1, 2, 3, 4):
            _fail("source descriptor ordinals must be exactly ordered 1 through 4")
        for field_name in (
            "source_id",
            "source_output_id",
            "content_sha256",
            "generation_request_identity",
            "source_authority_key",
        ):
            values = [getattr(item, field_name) for item in self.descriptors]
            if len(set(values)) != 4:
                _fail(f"source descriptor {field_name} values must be unique")

    def payload(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "source_count": 4,
            "ordered_descriptor_digests": [item.descriptor_digest for item in self.descriptors],
            "ordered_source_ids": [item.source_id for item in self.descriptors],
        }

    @property
    def manifest_digest(self) -> str:
        return _canonical_digest(SOURCE_DESCRIPTOR_MANIFEST_SCHEMA, self.payload())

    @classmethod
    def from_epoch2_packets(
        cls, packets: Sequence[Mapping[str, object]]
    ) -> SourceDescriptorManifest:
        if len(packets) != 4:
            _fail("source descriptor manifest requires exactly four packets")
        values = tuple(DurableSourceDescriptor.from_epoch2_packet(packet) for packet in packets)
        descriptors = cast(
            tuple[
                DurableSourceDescriptor,
                DurableSourceDescriptor,
                DurableSourceDescriptor,
                DurableSourceDescriptor,
            ],
            values,
        )
        return cls(descriptors)

    @classmethod
    def from_epoch3_packets(
        cls, packets: Sequence[Mapping[str, object]]
    ) -> SourceDescriptorManifest:
        if len(packets) != 4:
            _fail("source descriptor manifest requires exactly four packets")
        values = tuple(DurableSourceDescriptor.from_epoch3_packet(packet) for packet in packets)
        descriptors = cast(
            tuple[
                DurableSourceDescriptor,
                DurableSourceDescriptor,
                DurableSourceDescriptor,
                DurableSourceDescriptor,
            ],
            values,
        )
        return cls(descriptors)

    @classmethod
    def from_forward_packets(
        cls,
        packets: Sequence[Mapping[str, object]],
        *,
        context: GenerationExecutionContext,
    ) -> SourceDescriptorManifest:
        if len(packets) != 4:
            _fail("source descriptor manifest requires exactly four packets")
        values = tuple(
            DurableSourceDescriptor.from_forward_packet(packet, context=context)
            for packet in packets
        )
        return cls(
            cast(
                tuple[
                    DurableSourceDescriptor,
                    DurableSourceDescriptor,
                    DurableSourceDescriptor,
                    DurableSourceDescriptor,
                ],
                values,
            )
        )


def _manifest_from_versioned_packets(
    packets: Sequence[Mapping[str, object]],
) -> SourceDescriptorManifest:
    schemas = {
        cast(Mapping[str, object], packet.get("supporting_row", {})).get("schema_version")
        for packet in packets
    }
    if schemas == {epoch2.E2_SOURCE_RECORD_SCHEMA}:
        return SourceDescriptorManifest.from_epoch2_packets(packets)
    if schemas == {epoch3.E3_SOURCE_RECORD_SCHEMA}:
        return SourceDescriptorManifest.from_epoch3_packets(packets)
    if schemas == {E4_CONTEXT.source_record_schema}:
        return SourceDescriptorManifest.from_forward_packets(packets, context=E4_CONTEXT)
    _fail("source packets mix unsupported execution epochs")


def _descriptor_from_versioned_packet(
    packet: Mapping[str, object],
) -> DurableSourceDescriptor:
    row = packet.get("supporting_row")
    schema = row.get("schema_version") if isinstance(row, Mapping) else None
    if schema == epoch2.E2_SOURCE_RECORD_SCHEMA:
        return DurableSourceDescriptor.from_epoch2_packet(packet)
    if schema == epoch3.E3_SOURCE_RECORD_SCHEMA:
        return DurableSourceDescriptor.from_epoch3_packet(packet)
    if schema == E4_CONTEXT.source_record_schema:
        return DurableSourceDescriptor.from_forward_packet(packet, context=E4_CONTEXT)
    _fail("source packet schema is unsupported")


@dataclass(frozen=True, slots=True)
class DemoRuntimeRecipe:
    recipe_version: str
    preprocessing_version: str
    m3_algorithm_version: str
    m4_algorithm_version: str
    runtime_manifest_digest: str
    topology_digest: str
    measurement_config_digest: str
    threshold_config_digest: str
    deterministic_ordering: str
    unsupported_behavior: str
    failure_behavior: str
    network_policy: str
    source_m3_output_schema: str
    result_m3_output_schema: str
    m4_output_schema: str
    screening_output_schema: str
    schema_version: str = RUNTIME_RECIPE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != RUNTIME_RECIPE_SCHEMA:
            _fail("runtime recipe schema is invalid")
        for value, label in (
            (self.recipe_version, "runtime recipe version"),
            (self.preprocessing_version, "preprocessing version"),
            (self.m3_algorithm_version, "M3 algorithm version"),
            (self.m4_algorithm_version, "M4 algorithm version"),
            (self.deterministic_ordering, "deterministic ordering"),
            (self.unsupported_behavior, "unsupported behavior"),
            (self.failure_behavior, "failure behavior"),
            (self.network_policy, "network policy"),
            (self.source_m3_output_schema, "source M3 schema"),
            (self.result_m3_output_schema, "result M3 schema"),
            (self.m4_output_schema, "M4 schema"),
            (self.screening_output_schema, "screening schema"),
        ):
            _version(value, label)
        for value, label in (
            (self.runtime_manifest_digest, "runtime manifest digest"),
            (self.topology_digest, "topology digest"),
            (self.measurement_config_digest, "measurement config digest"),
            (self.threshold_config_digest, "threshold config digest"),
        ):
            _digest(value, label)
        if (
            self.network_policy != NETWORK_POLICY
            or self.source_m3_output_schema != authority.R2_SOURCE_M3_SCHEMA
            or self.result_m3_output_schema != authority.R2_RESULT_M3_SCHEMA
            or self.m4_output_schema != authority.R2_M4_SCHEMA
            or self.screening_output_schema != authority.R2_REPORT_SCHEMA
        ):
            _fail("runtime recipe output schemas differ from the accepted R2 contract")

    def payload(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "recipe_version": self.recipe_version,
            "preprocessing_version": self.preprocessing_version,
            "m3_algorithm_version": self.m3_algorithm_version,
            "m4_algorithm_version": self.m4_algorithm_version,
            "runtime_manifest_digest": self.runtime_manifest_digest,
            "topology_digest": self.topology_digest,
            "measurement_config_digest": self.measurement_config_digest,
            "threshold_config_digest": self.threshold_config_digest,
            "deterministic_ordering": self.deterministic_ordering,
            "unsupported_behavior": self.unsupported_behavior,
            "failure_behavior": self.failure_behavior,
            "network_policy": self.network_policy,
            "source_m3_output_schema": self.source_m3_output_schema,
            "result_m3_output_schema": self.result_m3_output_schema,
            "m4_output_schema": self.m4_output_schema,
            "screening_output_schema": self.screening_output_schema,
            "production_release": "NOT_AUTHORIZED",
        }

    @property
    def recipe_digest(self) -> str:
        return _canonical_digest(RUNTIME_RECIPE_SCHEMA, self.payload())


def build_default_runtime_recipe() -> DemoRuntimeRecipe:
    return DemoRuntimeRecipe(
        recipe_version=RUNTIME_RECIPE_VERSION,
        preprocessing_version=SOURCE_NORMALIZATION_VERSION,
        m3_algorithm_version=M3_ALGORITHM_VERSION,
        m4_algorithm_version=M4_ALGORITHM_VERSION,
        runtime_manifest_digest=measurement.RUNTIME_MANIFEST_DIGEST,
        topology_digest=measurement.TOPOLOGY_DIGEST,
        measurement_config_digest=measurement.MEASUREMENT_CONFIG_DIGEST,
        threshold_config_digest=legacy.SCREENING_POLICY_DIGEST,
        deterministic_ordering="source-ordinal-case-ordinal-repeat-index-v1",
        unsupported_behavior="EXPLICIT_UNSUPPORTED_FAILS_SELECTION_V1",
        failure_behavior="NO_PARTIAL_ADMISSION_OUTPUT_V1",
        network_policy=NETWORK_POLICY,
        source_m3_output_schema=authority.R2_SOURCE_M3_SCHEMA,
        result_m3_output_schema=authority.R2_RESULT_M3_SCHEMA,
        m4_output_schema=authority.R2_M4_SCHEMA,
        screening_output_schema=authority.R2_REPORT_SCHEMA,
    )


def build_epoch3_runtime_recipe(
    *, context: GenerationExecutionContext = E3_CONTEXT
) -> DemoRuntimeRecipe:
    """Bind accepted M3/M4 identities to one versioned normalization context."""

    return DemoRuntimeRecipe(
        recipe_version=context.runtime_recipe_version,
        preprocessing_version=context.source_normalization_version,
        m3_algorithm_version=M3_ALGORITHM_VERSION,
        m4_algorithm_version=M4_ALGORITHM_VERSION,
        runtime_manifest_digest=measurement.RUNTIME_MANIFEST_DIGEST,
        topology_digest=measurement.TOPOLOGY_DIGEST,
        measurement_config_digest=measurement.MEASUREMENT_CONFIG_DIGEST,
        threshold_config_digest=legacy.SCREENING_POLICY_DIGEST,
        deterministic_ordering="source-ordinal-case-ordinal-repeat-index-v1",
        unsupported_behavior="EXPLICIT_UNSUPPORTED_FAILS_SELECTION_V1",
        failure_behavior="NO_PARTIAL_ADMISSION_OUTPUT_V1",
        network_policy=NETWORK_POLICY,
        source_m3_output_schema=authority.R2_SOURCE_M3_SCHEMA,
        result_m3_output_schema=authority.R2_RESULT_M3_SCHEMA,
        m4_output_schema=authority.R2_M4_SCHEMA,
        screening_output_schema=authority.R2_REPORT_SCHEMA,
    )


@dataclass(frozen=True, slots=True)
class DemoModelIdentity:
    provider_kind: str
    model_version: str
    config_digest: str
    weights_digest_or_no_weights: str
    runtime_dependency_version: str
    runtime_manifest_digest: str
    capability_state: str
    schema_version: str = MODEL_IDENTITY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != MODEL_IDENTITY_SCHEMA:
            _fail("model identity schema is invalid")
        for value, label in (
            (self.provider_kind, "model provider kind"),
            (self.model_version, "model version"),
            (self.runtime_dependency_version, "runtime dependency version"),
            (self.capability_state, "model capability state"),
        ):
            _version(value, label)
        _digest(self.config_digest, "model config digest")
        _digest(self.runtime_manifest_digest, "model runtime manifest digest")
        if self.weights_digest_or_no_weights != NO_WEIGHTS_SENTINEL:
            _digest(self.weights_digest_or_no_weights, "model weights digest")
        if self.capability_state != MODEL_CAPABILITY_STATE:
            _fail("model identity is not restricted to Demo synthetic offline execution")

    def payload(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "provider_kind": self.provider_kind,
            "model_version": self.model_version,
            "config_digest": self.config_digest,
            "weights_digest_or_no_weights": self.weights_digest_or_no_weights,
            "runtime_dependency_version": self.runtime_dependency_version,
            "runtime_manifest_digest": self.runtime_manifest_digest,
            "capability_state": self.capability_state,
            "production_approved": False,
        }

    @property
    def identity_digest(self) -> str:
        return _canonical_digest(MODEL_IDENTITY_SCHEMA, self.payload())


def build_default_model_identity() -> DemoModelIdentity:
    config_digest = _canonical_digest(
        "mirror.demo/D02R2DemoModelConfiguration/v1",
        {
            "model_version": MODEL_VERSION,
            "required_face_count": 1,
            "required_landmark_count": 478,
            "topology_digest": measurement.TOPOLOGY_DIGEST,
            "measurement_config_digest": measurement.MEASUREMENT_CONFIG_DIGEST,
            "coordinate_serialization": "original-decimal-token-v1",
        },
    )
    return DemoModelIdentity(
        provider_kind=MODEL_PROVIDER_KIND,
        model_version=MODEL_VERSION,
        config_digest=config_digest,
        weights_digest_or_no_weights=measurement.VISION_MODEL_MANIFEST_DIGEST,
        runtime_dependency_version=MODEL_RUNTIME_DEPENDENCY_VERSION,
        runtime_manifest_digest=measurement.RUNTIME_MANIFEST_DIGEST,
        capability_state=MODEL_CAPABILITY_STATE,
    )


@dataclass(frozen=True, slots=True)
class M3RuntimeHandle:
    source_manifest_digest: str
    ordered_source_ids: tuple[str, str, str, str]
    recipe_version: str
    recipe_digest: str
    runtime_manifest_digest: str
    model_identity_digest: str
    schema_version: str = M3_RUNTIME_HANDLE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != M3_RUNTIME_HANDLE_SCHEMA:
            _fail("M3 runtime handle schema is invalid")
        for value, label in (
            (self.source_manifest_digest, "runtime handle source manifest"),
            (self.recipe_digest, "runtime handle recipe"),
            (self.runtime_manifest_digest, "runtime handle runtime manifest"),
            (self.model_identity_digest, "runtime handle model identity"),
        ):
            _digest(value, label)
        _version(self.recipe_version, "runtime handle recipe version")
        if len(set(self.ordered_source_ids)) != 4:
            _fail("runtime handle requires four unique ordered sources")
        for source_id in self.ordered_source_ids:
            _identifier(source_id, "runtime handle source ID")

    def payload(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "source_manifest_digest": self.source_manifest_digest,
            "source_count": 4,
            "ordered_source_ids": list(self.ordered_source_ids),
            "recipe_version": self.recipe_version,
            "recipe_digest": self.recipe_digest,
            "runtime_manifest_digest": self.runtime_manifest_digest,
            "model_identity_digest": self.model_identity_digest,
        }

    @property
    def handle_digest(self) -> str:
        return _canonical_digest(M3_RUNTIME_HANDLE_SCHEMA, self.payload())


@dataclass(frozen=True, slots=True)
class M3ModelHandle:
    source_manifest_digest: str
    ordered_source_ids: tuple[str, str, str, str]
    recipe_digest: str
    model_identity_digest: str
    model_config_digest: str
    weights_digest_or_no_weights: str
    schema_version: str = M3_MODEL_HANDLE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != M3_MODEL_HANDLE_SCHEMA:
            _fail("M3 model handle schema is invalid")
        for value, label in (
            (self.source_manifest_digest, "model handle source manifest"),
            (self.recipe_digest, "model handle recipe"),
            (self.model_identity_digest, "model handle identity"),
            (self.model_config_digest, "model handle config"),
        ):
            _digest(value, label)
        if self.weights_digest_or_no_weights != NO_WEIGHTS_SENTINEL:
            _digest(self.weights_digest_or_no_weights, "model handle weights")
        if len(set(self.ordered_source_ids)) != 4:
            _fail("model handle requires four unique ordered sources")
        for source_id in self.ordered_source_ids:
            _identifier(source_id, "model handle source ID")

    def payload(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "source_manifest_digest": self.source_manifest_digest,
            "source_count": 4,
            "ordered_source_ids": list(self.ordered_source_ids),
            "recipe_digest": self.recipe_digest,
            "model_identity_digest": self.model_identity_digest,
            "model_config_digest": self.model_config_digest,
            "weights_digest_or_no_weights": self.weights_digest_or_no_weights,
        }

    @property
    def handle_digest(self) -> str:
        return _canonical_digest(M3_MODEL_HANDLE_SCHEMA, self.payload())


def mint_runtime_handles(
    manifest: SourceDescriptorManifest,
    *,
    recipe: DemoRuntimeRecipe,
    model_identity: DemoModelIdentity,
) -> tuple[M3RuntimeHandle, M3ModelHandle]:
    accepted_recipes = (
        build_default_runtime_recipe(),
        build_epoch3_runtime_recipe(),
        build_epoch3_runtime_recipe(context=E4_CONTEXT),
    )
    if recipe not in accepted_recipes:
        _fail("runtime recipe is not the accepted Demo-only recipe")
    if model_identity != build_default_model_identity():
        _fail("model identity is not the accepted Demo-only identity")
    if model_identity.runtime_manifest_digest != recipe.runtime_manifest_digest:
        _fail("model identity and runtime recipe use different runtime manifests")
    source_ids = cast(
        tuple[str, str, str, str], tuple(item.source_id for item in manifest.descriptors)
    )
    runtime = M3RuntimeHandle(
        source_manifest_digest=manifest.manifest_digest,
        ordered_source_ids=source_ids,
        recipe_version=recipe.recipe_version,
        recipe_digest=recipe.recipe_digest,
        runtime_manifest_digest=recipe.runtime_manifest_digest,
        model_identity_digest=model_identity.identity_digest,
    )
    model = M3ModelHandle(
        source_manifest_digest=manifest.manifest_digest,
        ordered_source_ids=source_ids,
        recipe_digest=recipe.recipe_digest,
        model_identity_digest=model_identity.identity_digest,
        model_config_digest=model_identity.config_digest,
        weights_digest_or_no_weights=model_identity.weights_digest_or_no_weights,
    )
    return runtime, model


@dataclass(frozen=True, slots=True)
class SourceMaterial:
    descriptor: DurableSourceDescriptor
    content: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.content) is not bytes or not self.content:
            _fail("source material must contain non-empty bytes")
        if len(self.content) != self.descriptor.byte_length:
            _fail("source material byte length differs from its descriptor")
        if hashlib.sha256(self.content).hexdigest() != self.descriptor.content_sha256:
            _fail("source material digest differs from its descriptor")
        _validate_jpeg(
            self.content,
            expected_width=self.descriptor.width,
            expected_height=self.descriptor.height,
            label="source material",
        )


def _validate_jpeg(
    content: bytes, *, expected_width: int, expected_height: int, label: str
) -> None:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            if (
                image.format != "JPEG"
                or getattr(image, "n_frames", 1) != 1
                or image.size != (expected_width, expected_height)
            ):
                _fail(f"{label} JPEG envelope is invalid")
    except (OSError, UnidentifiedImageError) as error:
        raise RuntimeForwardError(f"{label} is not a decodable JPEG") from error


@dataclass(frozen=True, slots=True)
class BackendM3Result:
    payload_schema: str
    fields: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.payload_schema not in {
            authority.R2_SOURCE_M3_SCHEMA,
            authority.R2_RESULT_M3_SCHEMA,
        }:
            _fail("M3 backend output schema is invalid")
        copied = dict(self.fields)
        _assert_public_tree(copied, label="M3 backend output")
        object.__setattr__(self, "fields", MappingProxyType(copied))


@dataclass(frozen=True, slots=True)
class M3ExecutionOutput:
    payload_schema: str
    fields: Mapping[str, object]
    output_digest: str
    schema_version: str = M3_EXECUTION_OUTPUT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != M3_EXECUTION_OUTPUT_SCHEMA:
            _fail("M3 execution output schema is invalid")
        if self.payload_schema not in {
            authority.R2_SOURCE_M3_SCHEMA,
            authority.R2_RESULT_M3_SCHEMA,
        }:
            _fail("M3 execution payload schema is invalid")
        expected_keys = (
            {
                "execution_receipt_digest",
                "vision_model_manifest_digest",
                "runtime_manifest_digest",
                "topology_digest",
                "canonical_output_digest",
                "landmark_digest",
                "measurement_observation",
                "measurement_observation_digest",
                "face_count",
                "landmark_count",
                "coordinates_finite",
                "coordinates_in_bounds",
                "repeat_gate_passed",
            }
            if self.payload_schema == authority.R2_SOURCE_M3_SCHEMA
            else {
                "execution_receipt_digest",
                "vision_model_manifest_digest",
                "topology_digest",
                "canonical_output_digest",
                "landmark_digest",
                "measurement_observation",
                "measurement_observation_digest",
                "face_count",
                "landmark_count",
                "coordinates_finite",
                "coordinates_in_bounds",
                "observation_state",
                "repeat_gate_passed",
            }
        )
        copied = dict(self.fields)
        if set(copied) != expected_keys:
            _fail("M3 execution fields do not match the accepted adapter schema")
        _assert_public_tree(copied, label="M3 execution output")
        digest_keys = {
            "execution_receipt_digest",
            "vision_model_manifest_digest",
            "topology_digest",
            "canonical_output_digest",
            "landmark_digest",
            "measurement_observation_digest",
        }
        if self.payload_schema == authority.R2_SOURCE_M3_SCHEMA:
            digest_keys.add("runtime_manifest_digest")
        for key in digest_keys:
            _digest(copied.get(key), f"M3 {key}")
        observation = copied.get("measurement_observation")
        if not isinstance(observation, Mapping):
            _fail("M3 execution output has no measurement observation")
        if copied["measurement_observation_digest"] != observation.get(
            "measurement_observation_digest"
        ):
            _fail("M3 execution observation digest binding is invalid")
        for key in ("face_count", "landmark_count"):
            if type(copied.get(key)) is not int or cast(int, copied[key]) < 0:
                _fail(f"M3 {key} is invalid")
        for key in ("coordinates_finite", "coordinates_in_bounds", "repeat_gate_passed"):
            if type(copied.get(key)) is not bool:
                _fail(f"M3 {key} is invalid")
        if self.payload_schema == authority.R2_RESULT_M3_SCHEMA and copied.get(
            "observation_state"
        ) not in {"SUPPORTED", "UNSUPPORTED_EXPLICIT"}:
            _fail("M3 result observation state is invalid")
        _digest(self.output_digest, "M3 execution output digest")
        expected = _canonical_digest(
            M3_EXECUTION_OUTPUT_SCHEMA,
            {"payload_schema": self.payload_schema, "fields": copied},
        )
        if self.output_digest != expected:
            _fail("M3 execution output digest does not replay")
        object.__setattr__(self, "fields", MappingProxyType(copied))

    @classmethod
    def create(cls, value: BackendM3Result) -> M3ExecutionOutput:
        fields = dict(value.fields)
        digest = _canonical_digest(
            M3_EXECUTION_OUTPUT_SCHEMA,
            {"payload_schema": value.payload_schema, "fields": fields},
        )
        return cls(payload_schema=value.payload_schema, fields=fields, output_digest=digest)


@dataclass(frozen=True, slots=True)
class BackendM4Result:
    content: bytes = field(repr=False)
    changed_pixel_count: int
    payload_schema: str = authority.R2_M4_SCHEMA

    def __post_init__(self) -> None:
        if type(self.content) is not bytes or not self.content:
            _fail("M4 backend returned no result bytes")
        if type(self.changed_pixel_count) is not int or self.changed_pixel_count < 1:
            _fail("M4 backend changed pixel count is invalid")
        if self.payload_schema != authority.R2_M4_SCHEMA:
            _fail("M4 backend output schema is invalid")


@dataclass(frozen=True, slots=True)
class M4ExecutionOutput:
    case_id: str
    replay_index: int
    result_output_id: str
    content: bytes = field(repr=False)
    result_sha256: str
    result_byte_size: int
    result_width: int
    result_height: int
    changed_pixel_count: int
    execution_receipt_digest: str
    output_digest: str
    result_mime_type: str = "image/jpeg"
    execution_succeeded: bool = True
    schema_version: str = M4_EXECUTION_OUTPUT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != M4_EXECUTION_OUTPUT_SCHEMA:
            _fail("M4 execution output schema is invalid")
        _identifier(self.case_id, "M4 case ID")
        if type(self.replay_index) is not int or self.replay_index not in {1, 2}:
            _fail("M4 replay index must be one or two")
        if _OUTPUT_ID_RE.fullmatch(self.result_output_id) is None:
            _fail("M4 result output ID is invalid")
        if (
            type(self.content) is not bytes
            or not self.content
            or len(self.content) != self.result_byte_size
            or hashlib.sha256(self.content).hexdigest() != self.result_sha256
        ):
            _fail("M4 output bytes do not match their immutable descriptor")
        if (
            type(self.result_byte_size) is not int
            or self.result_byte_size < 1
            or type(self.result_width) is not int
            or self.result_width < 1
            or type(self.result_height) is not int
            or self.result_height < 1
        ):
            _fail("M4 output dimensions or byte length are invalid")
        if self.result_mime_type != "image/jpeg" or self.execution_succeeded is not True:
            _fail("M4 output did not complete as canonical JPEG")
        if (
            type(self.changed_pixel_count) is not int
            or self.changed_pixel_count < 1
            or self.changed_pixel_count > self.result_width * self.result_height
        ):
            _fail("M4 changed pixel count is invalid")
        _digest(self.result_sha256, "M4 result digest")
        _digest(self.execution_receipt_digest, "M4 execution receipt")
        _digest(self.output_digest, "M4 execution output digest")
        _validate_jpeg(
            self.content,
            expected_width=self.result_width,
            expected_height=self.result_height,
            label="M4 result",
        )
        expected = _canonical_digest(M4_EXECUTION_OUTPUT_SCHEMA, self.payload())
        if self.output_digest != expected:
            _fail("M4 execution output digest does not replay")

    def payload(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "replay_index": self.replay_index,
            "result_output_id": self.result_output_id,
            "result_sha256": self.result_sha256,
            "result_byte_size": self.result_byte_size,
            "result_mime_type": self.result_mime_type,
            "result_width": self.result_width,
            "result_height": self.result_height,
            "changed_pixel_count": self.changed_pixel_count,
            "execution_receipt_digest": self.execution_receipt_digest,
            "execution_succeeded": self.execution_succeeded,
        }

    def screening_fields(self, *, source_output_id: str) -> dict[str, object]:
        if _OUTPUT_ID_RE.fullmatch(source_output_id) is None:
            _fail("M4 source output ID is invalid")
        return {
            "source_output_id": source_output_id,
            "result_output_id": self.result_output_id,
            "result_sha256": self.result_sha256,
            "result_byte_size": self.result_byte_size,
            "result_mime_type": self.result_mime_type,
            "result_width": self.result_width,
            "result_height": self.result_height,
            "changed_pixel_count": self.changed_pixel_count,
            "execution_receipt_digest": self.execution_receipt_digest,
            "execution_succeeded": self.execution_succeeded,
        }


class OfflineM3Backend(Protocol):
    execution_runtime_set_digest: str
    model_identity_digest: str
    model_config_digest: str
    weights_digest_or_no_weights: str
    network_policy: str

    def inspect_source(
        self,
        *,
        content: bytes,
        descriptor: DurableSourceDescriptor,
        repeat_index: int,
    ) -> BackendM3Result: ...

    def inspect_result(
        self,
        *,
        content: bytes,
        case_entry: Mapping[str, object],
        repeat_index: int,
    ) -> BackendM3Result: ...


class OfflineM4Backend(Protocol):
    execution_runtime_set_digest: str
    algorithm_version: str
    network_policy: str

    def transform(
        self,
        *,
        content: bytes,
        descriptor: DurableSourceDescriptor,
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> BackendM4Result: ...


@dataclass(frozen=True, slots=True)
class DemoM3M4Executor:
    manifest: SourceDescriptorManifest
    recipe: DemoRuntimeRecipe
    model_identity: DemoModelIdentity
    runtime_handle: M3RuntimeHandle
    model_handle: M3ModelHandle
    m3_backend: OfflineM3Backend
    m4_backend: OfflineM4Backend

    def inspect_source(self, *, material: SourceMaterial, repeat_index: int) -> M3ExecutionOutput:
        self._validate_material(material)
        if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
            _fail("M3 source repeat index must be one through three")
        result = self.m3_backend.inspect_source(
            content=material.content,
            descriptor=material.descriptor,
            repeat_index=repeat_index,
        )
        return self._validate_m3_result(
            result,
            expected_schema=authority.R2_SOURCE_M3_SCHEMA,
            repeat_index=repeat_index,
            expected_canonical_output_digest=material.descriptor.content_sha256,
            expected_subject={
                "source_output_id": material.descriptor.source_output_id,
                "source_asset_id": material.descriptor.source_id,
                "source_asset_sha256": material.descriptor.content_sha256,
            },
        )

    def transform(
        self,
        *,
        material: SourceMaterial,
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> M4ExecutionOutput:
        self._validate_material(material)
        if type(replay_index) is not int or replay_index not in {1, 2}:
            _fail("M4 replay index must be one or two")
        case_id = _identifier(case_entry.get("case_id"), "M4 case ID")
        if (
            case_entry.get("source_asset_id") != material.descriptor.source_id
            or case_entry.get("source_asset_sha256") != material.descriptor.content_sha256
            or case_entry.get("source_ordinal") != material.descriptor.ordinal
            or case_entry.get("runtime_manifest_digest") != self.recipe.runtime_manifest_digest
            or case_entry.get("geometry_algorithm_version") != self.recipe.m4_algorithm_version
        ):
            _fail("M4 case does not bind the validated source and runtime recipe")
        result = self.m4_backend.transform(
            content=material.content,
            descriptor=material.descriptor,
            case_entry=case_entry,
            replay_index=replay_index,
        )
        if result.payload_schema != self.recipe.m4_output_schema:
            _fail("M4 backend output schema differs from the runtime recipe")
        if type(result.content) is not bytes or not result.content:
            _fail("M4 backend returned no result bytes")
        if result.content == material.content:
            _fail("M4 backend returned the immutable source unchanged")
        width = case_entry.get("output_width")
        height = case_entry.get("output_height")
        if type(width) is not int or type(height) is not int:
            _fail("M4 case output dimensions are invalid")
        result_sha256 = hashlib.sha256(result.content).hexdigest()
        result_output_id = f"m4-{case_id}"
        receipt = _canonical_digest(
            "mirror.demo/D02R2M4ExecutionReceipt/v1",
            {
                "runtime_handle_digest": self.runtime_handle.handle_digest,
                "model_handle_digest": self.model_handle.handle_digest,
                "case_id": case_id,
                "replay_index": replay_index,
                "source_descriptor_digest": material.descriptor.descriptor_digest,
                "result_sha256": result_sha256,
            },
        )
        payload = {
            "schema_version": M4_EXECUTION_OUTPUT_SCHEMA,
            "case_id": case_id,
            "replay_index": replay_index,
            "result_output_id": result_output_id,
            "result_sha256": result_sha256,
            "result_byte_size": len(result.content),
            "result_mime_type": "image/jpeg",
            "result_width": width,
            "result_height": height,
            "changed_pixel_count": result.changed_pixel_count,
            "execution_receipt_digest": receipt,
            "execution_succeeded": True,
        }
        output_digest = _canonical_digest(M4_EXECUTION_OUTPUT_SCHEMA, payload)
        return M4ExecutionOutput(
            case_id=case_id,
            replay_index=replay_index,
            result_output_id=result_output_id,
            content=result.content,
            result_sha256=result_sha256,
            result_byte_size=len(result.content),
            result_width=width,
            result_height=height,
            changed_pixel_count=result.changed_pixel_count,
            execution_receipt_digest=receipt,
            output_digest=output_digest,
        )

    def inspect_result(
        self,
        *,
        output: M4ExecutionOutput,
        case_entry: Mapping[str, object],
        repeat_index: int,
    ) -> M3ExecutionOutput:
        if (
            output.case_id != case_entry.get("case_id")
            or output.result_width != case_entry.get("output_width")
            or output.result_height != case_entry.get("output_height")
        ):
            _fail("M3 result inspection is not bound to its M4 case")
        if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
            _fail("M3 result repeat index must be one through three")
        result = self.m3_backend.inspect_result(
            content=output.content,
            case_entry=case_entry,
            repeat_index=repeat_index,
        )
        return self._validate_m3_result(
            result,
            expected_schema=authority.R2_RESULT_M3_SCHEMA,
            repeat_index=repeat_index,
            expected_canonical_output_digest=output.result_sha256,
            expected_subject={
                "case_id": output.case_id,
                "case_specification_digest": case_entry.get("case_specification_digest"),
                "result_output_id": output.result_output_id,
                "result_sha256": output.result_sha256,
            },
        )

    def _validate_material(self, material: SourceMaterial) -> None:
        expected = self.manifest.descriptors[material.descriptor.ordinal - 1]
        if material.descriptor != expected:
            _fail("source material is not a member of the runtime handle manifest")

    def _validate_m3_result(
        self,
        result: BackendM3Result,
        *,
        expected_schema: str,
        repeat_index: int,
        expected_canonical_output_digest: str,
        expected_subject: Mapping[str, object],
    ) -> M3ExecutionOutput:
        if result.payload_schema != expected_schema:
            _fail("M3 backend output schema differs from the requested execution")
        fields = result.fields
        observation = fields.get("measurement_observation")
        if not isinstance(observation, Mapping):
            _fail("M3 backend output is missing its measurement observation")
        subject = observation.get("subject")
        if not isinstance(subject, Mapping) or any(
            subject.get(key) != value for key, value in expected_subject.items()
        ):
            _fail("M3 measurement subject is not bound to the executed image")
        role = "SOURCE" if expected_schema == authority.R2_SOURCE_M3_SCHEMA else "RESULT"
        try:
            verified = legacy.validate_measurement_observation(observation, role=cast(Any, role))
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeForwardError("M3 measurement observation failed replay") from error
        if dict(verified) != dict(observation):
            _fail("M3 measurement observation differs from deterministic replay")
        if (
            fields.get("canonical_output_digest") != expected_canonical_output_digest
            or observation.get("canonical_output_digest") != expected_canonical_output_digest
            or fields.get("landmark_digest") != observation.get("landmark_digest")
            or fields.get("measurement_observation_digest")
            != observation.get("measurement_observation_digest")
            or fields.get("vision_model_manifest_digest")
            != self.model_identity.weights_digest_or_no_weights
            or (
                expected_schema == authority.R2_SOURCE_M3_SCHEMA
                and fields.get("runtime_manifest_digest") != self.recipe.runtime_manifest_digest
            )
            or fields.get("topology_digest") != self.recipe.topology_digest
            or observation.get("vision_model_manifest_digest")
            != self.model_identity.weights_digest_or_no_weights
            or observation.get("runtime_manifest_digest") != self.recipe.runtime_manifest_digest
            or observation.get("topology_digest") != self.recipe.topology_digest
            or observation.get("measurement_config_digest") != self.recipe.measurement_config_digest
        ):
            _fail("M3 output runtime/model/topology binding is invalid")
        backend_receipt = _digest(fields.get("execution_receipt_digest"), "M3 backend receipt")
        bound_fields = dict(fields)
        bound_fields["execution_receipt_digest"] = _canonical_digest(
            "mirror.demo/D02R2M3ExecutionReceipt/v1",
            {
                "runtime_handle_digest": self.runtime_handle.handle_digest,
                "model_handle_digest": self.model_handle.handle_digest,
                "payload_schema": expected_schema,
                "repeat_index": repeat_index,
                "canonical_output_digest": expected_canonical_output_digest,
                "measurement_subject": dict(subject),
                "backend_execution_receipt_digest": backend_receipt,
            },
        )
        return M3ExecutionOutput.create(
            BackendM3Result(payload_schema=result.payload_schema, fields=bound_fields)
        )


def reconstruct_executor(
    manifest: SourceDescriptorManifest,
    *,
    recipe: DemoRuntimeRecipe,
    model_identity: DemoModelIdentity,
    runtime_handle: M3RuntimeHandle,
    model_handle: M3ModelHandle,
    m3_backend: OfflineM3Backend,
    m4_backend: OfflineM4Backend,
) -> DemoM3M4Executor:
    expected_runtime, expected_model = mint_runtime_handles(
        manifest, recipe=recipe, model_identity=model_identity
    )
    if runtime_handle != expected_runtime or model_handle != expected_model:
        _fail("runtime/model handles do not replay from durable inputs")
    if (
        m3_backend.execution_runtime_set_digest != recipe.runtime_manifest_digest
        or m3_backend.model_identity_digest != model_identity.identity_digest
        or m3_backend.model_config_digest != model_identity.config_digest
        or m3_backend.weights_digest_or_no_weights != model_identity.weights_digest_or_no_weights
        or m4_backend.execution_runtime_set_digest != recipe.runtime_manifest_digest
        or m4_backend.algorithm_version != recipe.m4_algorithm_version
        or m3_backend.network_policy != recipe.network_policy
        or m4_backend.network_policy != recipe.network_policy
    ):
        _fail("injected runtime material differs from the accepted handle identities")
    return DemoM3M4Executor(
        manifest=manifest,
        recipe=recipe,
        model_identity=model_identity,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
        m3_backend=m3_backend,
        m4_backend=m4_backend,
    )


class RuntimeScreeningBridge:
    """Concrete VisionM3/M4 adapters backed by validated offline execution."""

    def __init__(
        self,
        *,
        source_packets: Sequence[Mapping[str, object]],
        source_materials: Sequence[SourceMaterial],
        executor: DemoM3M4Executor,
    ) -> None:
        packet_manifest = _manifest_from_versioned_packets(source_packets)
        if packet_manifest != executor.manifest:
            _fail("source packets differ from the reconstructed runtime manifest")
        if len(source_materials) != 4:
            _fail("runtime screening requires exactly four source materials")
        materials = tuple(source_materials)
        if tuple(item.descriptor for item in materials) != executor.manifest.descriptors:
            _fail("source materials are missing, reordered, or bound to another manifest")
        self._executor = executor
        self._materials = {item.descriptor.source_id: item for item in materials}
        self._source_output_ids: dict[str, str] = {}
        for packet in source_packets:
            row = cast(Mapping[str, object], packet["supporting_row"])
            source_id = cast(str, row["source_asset_id"])
            self._source_output_ids[source_id] = cast(str, row["source_output_id"])
        self._m4_outputs: dict[tuple[str, int], M4ExecutionOutput] = {}

    def inspect_source(
        self, *, source_packet: Mapping[str, object], repeat_index: int
    ) -> Mapping[str, object]:
        material = self._material_for_packet(source_packet)
        output = self._executor.inspect_source(material=material, repeat_index=repeat_index)
        return dict(output.fields)

    def transform(
        self,
        *,
        source_packet: Mapping[str, object],
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> Mapping[str, object]:
        material = self._material_for_packet(source_packet)
        output = self._executor.transform(
            material=material,
            case_entry=case_entry,
            replay_index=replay_index,
        )
        key = (output.case_id, replay_index)
        if key in self._m4_outputs:
            _fail("M4 case replay was executed more than once")
        self._m4_outputs[key] = output
        return output.screening_fields(
            source_output_id=self._source_output_ids[material.descriptor.source_id]
        )

    def inspect_result(
        self,
        *,
        case_entry: Mapping[str, object],
        m4_record: Mapping[str, object],
        repeat_index: int,
    ) -> Mapping[str, object]:
        case_id = _identifier(case_entry.get("case_id"), "result M3 case ID")
        output = self._m4_outputs.get((case_id, 1))
        if output is None:
            _fail("result M3 inspection has no completed first M4 replay")
        if (
            m4_record.get("result_output_id") != output.result_output_id
            or m4_record.get("result_sha256") != output.result_sha256
        ):
            _fail("result M3 inspection received a substituted M4 record")
        result = self._executor.inspect_result(
            output=output,
            case_entry=case_entry,
            repeat_index=repeat_index,
        )
        return dict(result.fields)

    def result_outputs(self) -> tuple[M4ExecutionOutput, ...]:
        outputs = tuple(
            output
            for (case_id, replay), output in sorted(self._m4_outputs.items())
            if replay == 1 and case_id == output.case_id
        )
        if len(outputs) != 48:
            _fail("runtime screening did not produce exactly 48 first-replay results")
        return outputs

    def _material_for_packet(self, packet: Mapping[str, object]) -> SourceMaterial:
        authority.validate_r2_admission_packet(packet)
        row = cast(Mapping[str, object], packet["supporting_row"])
        source_id = _identifier(row.get("source_asset_id"), "source packet Asset ID")
        material = self._materials.get(source_id)
        if material is None or _descriptor_from_versioned_packet(packet) != material.descriptor:
            _fail("source packet does not match a runtime source material")
        return material


@dataclass(frozen=True, slots=True)
class RuntimeScreeningRequest:
    created_at: str
    source_packets: Sequence[Mapping[str, object]]
    source_materials: Sequence[SourceMaterial]
    execution_authority: Mapping[str, object]
    recipe: DemoRuntimeRecipe
    model_identity: DemoModelIdentity
    runtime_handle: M3RuntimeHandle
    model_handle: M3ModelHandle
    m3_backend: OfflineM3Backend
    m4_backend: OfflineM4Backend
    case_fields: screening.CaseFieldsAdapter
    measurement_gate: screening.MeasurementGateAdapter
    manual_review: screening.ManualReviewAdapter
    phash: screening.PHashAdapter


@dataclass(frozen=True, slots=True)
class RuntimeScreeningResult:
    report_row: Mapping[str, Any]
    source_packets: tuple[Mapping[str, object], ...]
    result_outputs: tuple[M4ExecutionOutput, ...]
    runtime_handle_digest: str
    model_handle_digest: str
    source_descriptor_manifest_digest: str
    recipe_digest: str
    model_identity_digest: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.runtime_handle_digest, "runtime result handle"),
            (self.model_handle_digest, "runtime result model handle"),
            (self.source_descriptor_manifest_digest, "runtime result source manifest"),
            (self.recipe_digest, "runtime result recipe"),
            (self.model_identity_digest, "runtime result model identity"),
        ):
            _digest(value, label)
        manifest = _manifest_from_versioned_packets(self.source_packets)
        if manifest.manifest_digest != self.source_descriptor_manifest_digest:
            _fail("runtime result source manifest does not replay")
        try:
            report = authority.validate_r2_report_row(
                self.report_row, source_packets=self.source_packets
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeForwardError("runtime screening report failed replay") from error
        payload = report.get("report_payload")
        records = payload.get("m4_repeat_evidence") if isinstance(payload, Mapping) else None
        if not isinstance(records, list):
            _fail("runtime screening report has no M4 evidence")
        first_replays = {
            cast(str, record["case_id"]): record
            for record in records
            if isinstance(record, Mapping) and record.get("replay_index") == 1
        }
        if len(first_replays) != 48 or len(self.result_outputs) != 48:
            _fail("runtime screening result must contain 48 first-replay outputs")
        if len({output.case_id for output in self.result_outputs}) != 48:
            _fail("runtime screening result contains duplicate case outputs")
        for output in self.result_outputs:
            record = first_replays.get(output.case_id)
            if record is None or any(
                record.get(key) != value
                for key, value in (
                    ("result_output_id", output.result_output_id),
                    ("result_sha256", output.result_sha256),
                    ("result_byte_size", output.result_byte_size),
                    ("result_mime_type", output.result_mime_type),
                    ("result_width", output.result_width),
                    ("result_height", output.result_height),
                    ("changed_pixel_count", output.changed_pixel_count),
                    ("execution_receipt_digest", output.execution_receipt_digest),
                    ("execution_succeeded", output.execution_succeeded),
                )
            ):
                _fail("runtime M4 bytes differ from the screening report authority")

    @property
    def admission_ready(self) -> bool:
        report = self.report_row
        return (
            report.get("status") == "PASSED"
            and report.get("source_count") == 4
            and report.get("case_count") == 48
            and report.get("m4_execution_count") == 96
            and report.get("result_m3_repeat_count") == 144
            and report.get("selected_pair_count") == 16
            and report.get("selected_result_side_count") == 32
            and len(self.result_outputs) == 48
        )


def build_epoch2_admission_bundle(
    result: RuntimeScreeningResult,
    *,
    asset_rows: Sequence[Mapping[str, object]],
    asset_variant_rows: Sequence[Mapping[str, object]],
    question_bank_row: Mapping[str, object],
    question_pair_rows: Sequence[Mapping[str, object]],
) -> epoch2.Epoch2AdmissionBundle:
    """Return the existing coordinator input only after its full graph replays."""

    if not result.admission_ready:
        _fail("runtime screening result is not eligible for Epoch 02 admission")
    bundle = epoch2.Epoch2AdmissionBundle(
        source_packets=result.source_packets,
        asset_rows=tuple(asset_rows),
        asset_variant_rows=tuple(asset_variant_rows),
        report_row=result.report_row,
        question_bank_row=question_bank_row,
        question_pair_rows=tuple(question_pair_rows),
    )
    try:
        epoch2._validate_bundle(bundle)
    except epoch2.D02R2Epoch2AdmissionError as error:
        raise RuntimeForwardError("Epoch 02 admission bundle failed replay") from error
    return bundle


def build_epoch3_admission_bundle(
    result: RuntimeScreeningResult,
    *,
    asset_rows: Sequence[Mapping[str, object]],
    asset_variant_rows: Sequence[Mapping[str, object]],
    question_bank_row: Mapping[str, object],
    question_pair_rows: Sequence[Mapping[str, object]],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> epoch3.Epoch3AdmissionBundle:
    """Return versioned coordinator input only after the entire graph replays."""

    if not result.admission_ready:
        _fail(f"runtime screening result is not eligible for {context.cohort_label} admission")
    if {
        cast(Mapping[str, object], packet["supporting_row"])["schema_version"]
        for packet in result.source_packets
    } != {context.source_record_schema}:
        _fail(f"{context.cohort_label} admission bundle requires one source schema")
    bundle = epoch3.Epoch3AdmissionBundle(
        source_packets=result.source_packets,
        asset_rows=tuple(asset_rows),
        asset_variant_rows=tuple(asset_variant_rows),
        report_row=result.report_row,
        question_bank_row=question_bank_row,
        question_pair_rows=tuple(question_pair_rows),
    )
    try:
        epoch3._validate_bundle(bundle, context=context)
    except epoch3.D02R2Epoch3AdmissionError as error:
        raise RuntimeForwardError(
            f"{context.cohort_label} admission bundle failed replay"
        ) from error
    return bundle


def run_runtime_screening(request: RuntimeScreeningRequest) -> RuntimeScreeningResult:
    """Execute real injected M3/M4 backends, then reuse the accepted R2 runner."""

    manifest = _manifest_from_versioned_packets(request.source_packets)
    authority_binding = request.execution_authority
    if (
        authority_binding.get("runtime_manifest_digest") != request.recipe.runtime_manifest_digest
        or authority_binding.get("vision_model_manifest_digest")
        != request.model_identity.weights_digest_or_no_weights
        or authority_binding.get("topology_digest") != request.recipe.topology_digest
        or authority_binding.get("measurement_config_digest")
        != request.recipe.measurement_config_digest
        or authority_binding.get("screening_policy_digest")
        != request.recipe.threshold_config_digest
    ):
        _fail("screening execution authority differs from the runtime recipe")
    executor = reconstruct_executor(
        manifest,
        recipe=request.recipe,
        model_identity=request.model_identity,
        runtime_handle=request.runtime_handle,
        model_handle=request.model_handle,
        m3_backend=request.m3_backend,
        m4_backend=request.m4_backend,
    )
    bridge = RuntimeScreeningBridge(
        source_packets=request.source_packets,
        source_materials=request.source_materials,
        executor=executor,
    )
    report = screening.run_offline_screening(
        screening.OfflineScreeningRequest(
            created_at=request.created_at,
            source_packets=request.source_packets,
            execution_authority=request.execution_authority,
            case_fields=request.case_fields,
            vision_m3=bridge,
            m4=bridge,
            measurement_gate=request.measurement_gate,
            manual_review=request.manual_review,
            phash=request.phash,
        )
    )
    return RuntimeScreeningResult(
        report_row=report,
        source_packets=tuple(request.source_packets),
        result_outputs=bridge.result_outputs(),
        runtime_handle_digest=request.runtime_handle.handle_digest,
        model_handle_digest=request.model_handle.handle_digest,
        source_descriptor_manifest_digest=manifest.manifest_digest,
        recipe_digest=request.recipe.recipe_digest,
        model_identity_digest=request.model_identity.identity_digest,
    )
