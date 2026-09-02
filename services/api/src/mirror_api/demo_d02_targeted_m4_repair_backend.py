"""Landmark-free, Case-25-only D02 M4 successor backend.

This is deliberately a small, source-byte-bound overlay for ADR-053.  It has
no persistence, discovery, network, landmark, or diagnostic output surface.
The caller supplies the already-durable canonical source bytes; all rejected
inputs receive one stable error without echoing any private value.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from io import BytesIO
from typing import Final, NoReturn

from PIL import Image

from mirror_api import demo_d02_r2_runtime_forward as runtime_forward
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_targeted_m4_repair import (
    build_repair_policy,
    build_repair_warp_plan_digest,
)
from mirror_api.image_sanitizer import ImageSanitizationError, decode_canonical_rgb_image

_ALGORITHM_VERSION: Final = "d02-targeted-jaw-repair-v1"
_CONFIG_VERSION: Final = "d02-targeted-jaw-repair-config-v1"
_OUTPUT_POLICY_VERSION: Final = "d02-targeted-jpeg-q95-420-v1"
_DETERMINISM_LEVEL: Final = "BIT_EXACT_SAME_PLATFORM"
_IMPLEMENTATION_REVISION: Final = "d02-targeted-jaw-repair-implementation-20260902-3"
_TARGET_CASE_ORDINAL: Final = 25
_TARGET_SOURCE_ORDINAL: Final = 3
_TARGET_DIMENSION: Final = "jaw_width"
_TARGET_DIRECTION: Final = "DECREASE"
_TARGET_MAGNITUDE_PPM: Final = 15_000


class TargetedM4RepairError(ValueError):
    """Stable failure that never contains private input data."""

    def __init__(self) -> None:
        super().__init__("D02_TARGETED_M4_REPAIR_FAILED")


def _fail() -> NoReturn:
    raise TargetedM4RepairError()


def _digest_payload(schema: str, payload: Mapping[str, object]) -> str:
    try:
        encoded = json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False
        ).encode("ascii")
    except (TypeError, ValueError):
        _fail()
    return hashlib.sha256(schema.encode("ascii") + b"\n" + encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class TargetedJawRepairConfig:
    """Versioned public-safe tuning values for private calibration attempts."""

    strength_ppm: int = 750
    lower_y_start_ppm: int = 440_000
    lower_y_end_ppm: int = 860_000
    center_x_ppm: int = 500_000
    version: str = _CONFIG_VERSION

    def __post_init__(self) -> None:
        if (
            self.version != _CONFIG_VERSION
            or type(self.strength_ppm) is not int
            or not 100 <= self.strength_ppm <= 200_000
            or type(self.lower_y_start_ppm) is not int
            or type(self.lower_y_end_ppm) is not int
            or not 0 <= self.lower_y_start_ppm < self.lower_y_end_ppm <= 1_000_000
            or type(self.center_x_ppm) is not int
            or not 250_000 <= self.center_x_ppm <= 750_000
        ):
            _fail()

    @property
    def digest(self) -> str:
        return _digest_payload(
            "mirror.demo/D02TargetedJawRepairConfig/v1",
            {
                "version": self.version,
                "strength_ppm": self.strength_ppm,
                "lower_y_start_ppm": self.lower_y_start_ppm,
                "lower_y_end_ppm": self.lower_y_end_ppm,
                "center_x_ppm": self.center_x_ppm,
            },
        )


@dataclass(slots=True)
class _ReplayState:
    content: bytes = field(repr=False)
    changed_pixel_count: int
    delivered: set[int]


class D02TargetedM4RepairBackend:
    """A strict source-byte-only Case-25 M4 backend.

    ``case_fields`` creates the per-case digest binding.  ``transform`` only
    permits a first then second identical replay of that one bound case.
    """

    execution_runtime_set_digest: str = measurement.RUNTIME_MANIFEST_DIGEST
    algorithm_version: str = _ALGORITHM_VERSION
    network_policy: str = runtime_forward.NETWORK_POLICY

    def __init__(
        self,
        *,
        material: runtime_forward.SourceMaterial,
        config: TargetedJawRepairConfig = TargetedJawRepairConfig(),
    ) -> None:
        descriptor = material.descriptor
        if (
            descriptor.ordinal != _TARGET_SOURCE_ORDINAL
            or hashlib.sha256(material.content).hexdigest() != descriptor.content_sha256
            or len(material.content) != descriptor.byte_length
        ):
            _fail()
        self._validate_canonical_source(material)
        self._material = material
        self._config = config
        self._warp_plan_digest = build_repair_warp_plan_digest(
            algorithm_version=self.algorithm_version,
            implementation_digest=self.implementation_digest,
            repair_policy_digest=self.repair_policy_digest,
            configuration_digest=config.digest,
            source_descriptor_digest=descriptor.descriptor_digest,
            source_content_sha256=descriptor.content_sha256,
        )
        self._replay: _ReplayState | None = None
        self._lock = threading.RLock()

    @property
    def config_digest(self) -> str:
        return self._config.digest

    @property
    def implementation_digest(self) -> str:
        return _digest_payload(
            "mirror.demo/D02TargetedJawRepairImplementation/v1",
            {
                "algorithm_version": self.algorithm_version,
                "implementation_revision": _IMPLEMENTATION_REVISION,
                "encoding": _OUTPUT_POLICY_VERSION,
                "warp": "fixed-point-lower-face-horizontal-squeeze-v1",
            },
        )

    @property
    def repair_policy_digest(self) -> str:
        """Bind the ADR-053 target-effect rules without storing source evidence."""

        return str(build_repair_policy()["repair_policy_digest"])

    @property
    def warp_plan_digest(self) -> str:
        return self._warp_plan_digest

    def case_fields(
        self,
        *,
        source_packet: Mapping[str, object],
        source_entry: Mapping[str, object],
        case_ordinal: int,
        dimension_key: str,
        direction: str,
        magnitude_ppm: int,
    ) -> Mapping[str, object]:
        """Return the frozen fields only for the ADR-053 selector."""

        with self._lock:
            self._validate_target(
                source_packet=source_packet,
                source_entry=source_entry,
                case_ordinal=case_ordinal,
                dimension_key=dimension_key,
                direction=direction,
                magnitude_ppm=magnitude_ppm,
            )
            descriptor = self._material.descriptor
            return {
                "geometry_ontology_version_digest": self.implementation_digest,
                "warp_plan_digest": self._warp_plan_digest,
                "geometry_algorithm_version": self.algorithm_version,
                "runtime_config_digest": self._config.digest,
                "output_policy_version": _OUTPUT_POLICY_VERSION,
                "output_width": descriptor.width,
                "output_height": descriptor.height,
                "determinism_level": _DETERMINISM_LEVEL,
            }

    def transform(
        self,
        *,
        content: bytes,
        descriptor: runtime_forward.DurableSourceDescriptor,
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> runtime_forward.BackendM4Result:
        """Generate and require two byte-identical replays of the target only."""

        with self._lock:
            if (
                type(replay_index) is not int
                or replay_index not in {1, 2}
                or descriptor != self._material.descriptor
                or type(content) is not bytes
                or content != self._material.content
                or not self._case_entry_matches(case_entry)
            ):
                _fail()
            if self._replay is None:
                if replay_index != 1:
                    _fail()
            elif replay_index != 2 or replay_index in self._replay.delivered:
                _fail()
            result = self._execute()
            if self._replay is None:
                self._replay = _ReplayState(
                    content=result.content,
                    changed_pixel_count=result.changed_pixel_count,
                    delivered={1},
                )
            else:
                if (
                    result.content != self._replay.content
                    or result.changed_pixel_count != self._replay.changed_pixel_count
                ):
                    _fail()
                self._replay.delivered.add(2)
            return result

    def _validate_target(
        self,
        *,
        source_packet: Mapping[str, object],
        source_entry: Mapping[str, object],
        case_ordinal: int,
        dimension_key: str,
        direction: str,
        magnitude_ppm: int,
    ) -> None:
        if (
            not isinstance(source_packet, Mapping)
            or not isinstance(source_entry, Mapping)
            or case_ordinal != _TARGET_CASE_ORDINAL
            or dimension_key != _TARGET_DIMENSION
            or direction != _TARGET_DIRECTION
            or magnitude_ppm != _TARGET_MAGNITUDE_PPM
        ):
            _fail()
        packet_entry = source_packet.get("source_manifest_entry")
        supporting_row = source_packet.get("supporting_row")
        if not isinstance(packet_entry, Mapping) or not isinstance(supporting_row, Mapping):
            _fail()
        self._validate_entry(source_entry)
        self._validate_entry(packet_entry)
        self._validate_entry(supporting_row)
        if not _same_source_binding(packet_entry, source_entry) or not _same_source_binding(
            supporting_row, source_entry
        ):
            _fail()

    def _validate_entry(self, entry: Mapping[str, object]) -> None:
        descriptor = self._material.descriptor
        expected = {
            "source_asset_id": descriptor.source_id,
            "source_output_id": descriptor.source_output_id,
            "source_asset_sha256": descriptor.content_sha256,
            "source_ordinal": descriptor.ordinal,
            "source_asset_mime_type": descriptor.media_type,
            "source_asset_width": descriptor.width,
            "source_asset_height": descriptor.height,
            "source_asset_byte_size": descriptor.byte_length,
            "source_authority_key": descriptor.source_authority_key,
        }
        if any(entry.get(key) != value for key, value in expected.items()):
            _fail()

    def _case_entry_matches(self, entry: Mapping[str, object]) -> bool:
        if not isinstance(entry, Mapping):
            return False
        descriptor = self._material.descriptor
        source_binding = {
            "source_asset_id": descriptor.source_id,
            "source_asset_sha256": descriptor.content_sha256,
            "source_ordinal": descriptor.ordinal,
            "source_authority_key": descriptor.source_authority_key,
        }
        if any(entry.get(key) != value for key, value in source_binding.items()):
            return False
        expected = {
            "case_ordinal": _TARGET_CASE_ORDINAL,
            "dimension_key": _TARGET_DIMENSION,
            "direction": _TARGET_DIRECTION,
            "magnitude_ppm": _TARGET_MAGNITUDE_PPM,
            "geometry_ontology_version_digest": self.implementation_digest,
            "warp_plan_digest": self._warp_plan_digest,
            "geometry_algorithm_version": self.algorithm_version,
            "runtime_config_digest": self._config.digest,
            "output_policy_version": _OUTPUT_POLICY_VERSION,
            "output_width": self._material.descriptor.width,
            "output_height": self._material.descriptor.height,
            "determinism_level": _DETERMINISM_LEVEL,
        }
        return all(entry.get(key) == value for key, value in expected.items())

    def _execute(self) -> runtime_forward.BackendM4Result:
        descriptor = self._material.descriptor
        try:
            decoded = decode_canonical_rgb_image(
                self._material.content,
                expected_width=descriptor.width,
                expected_height=descriptor.height,
            )
            warped = _warp_rgb(
                decoded.bytes_value,
                width=decoded.width,
                height=decoded.height,
                config=self._config,
            )
            changed = _changed_pixels(decoded.bytes_value, warped)
            if changed < 1:
                _fail()
            content = _encode_jpeg(warped, width=decoded.width, height=decoded.height)
            self._validate_output(content)
            return runtime_forward.BackendM4Result(
                content=content,
                changed_pixel_count=changed,
            )
        except TargetedM4RepairError:
            raise
        except (ImageSanitizationError, OSError, ValueError):
            _fail()

    def _validate_canonical_source(self, material: runtime_forward.SourceMaterial) -> None:
        try:
            decode_canonical_rgb_image(
                material.content,
                expected_width=material.descriptor.width,
                expected_height=material.descriptor.height,
            )
        except ImageSanitizationError:
            _fail()

    def _validate_output(self, content: bytes) -> None:
        descriptor = self._material.descriptor
        try:
            decoded = decode_canonical_rgb_image(
                content,
                expected_width=descriptor.width,
                expected_height=descriptor.height,
            )
        except ImageSanitizationError:
            _fail()
        if not decoded.bytes_value:
            _fail()


def _warp_rgb(source: bytes, *, width: int, height: int, config: TargetedJawRepairConfig) -> bytes:
    """Fixed-point lower-face squeeze; intentionally independent of landmarks."""

    if len(source) != width * height * 3:
        _fail()
    result = bytearray(source)
    denominator_y = max(1, height - 1)
    denominator_x = max(1, width - 1)
    start = config.lower_y_start_ppm
    end = config.lower_y_end_ppm
    center = config.center_x_ppm
    for y in range(height):
        y_ppm = y * 1_000_000 // denominator_y
        if y_ppm < start or y_ppm > end:
            continue
        relative = min(y_ppm - start, end - y_ppm) * 2
        vertical_weight = relative * 1_000_000 // (end - start)
        effective_strength = config.strength_ppm * vertical_weight // 1_000_000
        if effective_strength == 0:
            continue
        for x in range(width):
            x_ppm = x * 1_000_000 // denominator_x
            source_x_ppm = center + (x_ppm - center) * 1_000_000 // (1_000_000 - effective_strength)
            source_x_ppm = max(0, min(1_000_000, source_x_ppm))
            source_x = source_x_ppm * denominator_x // 1_000_000
            source_offset = (y * width + source_x) * 3
            output_offset = (y * width + x) * 3
            result[output_offset : output_offset + 3] = source[source_offset : source_offset + 3]
    return bytes(result)


def _changed_pixels(before: bytes, after: bytes) -> int:
    if len(before) != len(after) or len(before) % 3 != 0:
        _fail()
    return sum(
        before[index : index + 3] != after[index : index + 3] for index in range(0, len(before), 3)
    )


def _same_source_binding(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    return all(
        left.get(key) == right.get(key)
        for key in (
            "source_asset_id",
            "source_output_id",
            "source_asset_sha256",
            "source_ordinal",
            "source_authority_key",
        )
    )


def _encode_jpeg(rgb: bytes, *, width: int, height: int) -> bytes:
    try:
        image = Image.frombytes("RGB", (width, height), rgb)
        try:
            output = BytesIO()
            image.save(
                output,
                format="JPEG",
                quality=95,
                subsampling="4:2:0",
                optimize=False,
                progressive=False,
            )
            return output.getvalue()
        finally:
            image.close()
    except (OSError, ValueError):
        _fail()
