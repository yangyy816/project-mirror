"""Minimal first-party exact and perceptual similarity core for P2-M5.

The algorithm is deliberately bounded, deterministic, and threshold-free. Near-duplicate
policy remains an external preregistered `SyntheticEvaluationPolicy` decision.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from mirror_api.image_sanitizer import (
    ImageSanitizationError,
    decode_canonical_rgb_image,
)

SIMILARITY_SIGNATURE_SCHEMA_VERSION = "mirror.synthetic-dataset/SimilaritySignature/v1"
PHASH_ALGORITHM_VERSION = "phash-dct-nearest-v1"
PHASH_SAMPLE_EDGE = 32
PHASH_LOW_FREQUENCY_EDGE = 8
PHASH_BITS = PHASH_LOW_FREQUENCY_EDGE * PHASH_LOW_FREQUENCY_EDGE
MAX_SIGNATURE_EDGE_PIXELS = 8192
MAX_SIGNATURE_TOTAL_PIXELS = 40_000_000

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_PHASH_PATTERN = re.compile(r"[0-9a-f]{16}\Z")
_COSINE_SCALE = 1_000_000
_COSINE_TABLE = tuple(
    tuple(
        round(
            math.cos(math.pi * (2 * sample_index + 1) * frequency_index / (2 * PHASH_SAMPLE_EDGE))
            * _COSINE_SCALE
        )
        for sample_index in range(PHASH_SAMPLE_EDGE)
    )
    for frequency_index in range(PHASH_LOW_FREQUENCY_EDGE)
)


class SimilarityReasonCode(StrEnum):
    INVALID_CANONICAL_IMAGE = "INVALID_CANONICAL_IMAGE"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    INVALID_DIMENSIONS = "INVALID_DIMENSIONS"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    ALGORITHM_VERSION_MISMATCH = "ALGORITHM_VERSION_MISMATCH"


class SimilarityValidationError(ValueError):
    """Safe error that never echoes image bytes, paths, or caller content."""

    def __init__(self, reason_code: SimilarityReasonCode) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code.value)


@dataclass(frozen=True)
class SimilaritySignature:
    algorithm_version: str
    normalized_sha256: str
    phash_hex: str
    width: int
    height: int
    content_digest: str

    def __post_init__(self) -> None:
        if self.algorithm_version != PHASH_ALGORITHM_VERSION:
            raise SimilarityValidationError(SimilarityReasonCode.ALGORITHM_VERSION_MISMATCH)
        _require_sha256(self.normalized_sha256)
        if not isinstance(self.phash_hex, str) or _PHASH_PATTERN.fullmatch(self.phash_hex) is None:
            raise SimilarityValidationError(SimilarityReasonCode.INVALID_SIGNATURE)
        _validate_dimensions(self.width, self.height)
        _require_sha256(self.content_digest)
        if self.content_digest != _digest(self._canonical_facts()):
            raise SimilarityValidationError(SimilarityReasonCode.INVALID_SIGNATURE)

    def _canonical_facts(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "height": self.height,
            "normalized_sha256": self.normalized_sha256,
            "phash_hex": self.phash_hex,
            "width": self.width,
        }


def compute_similarity_signature(
    canonical_jpeg: bytes,
    *,
    expected_width: int,
    expected_height: int,
    expected_sha256: str,
) -> SimilaritySignature:
    """Decode one checksum-bound canonical JPEG and compute a 64-bit pHash."""
    if type(canonical_jpeg) is not bytes or not canonical_jpeg:
        raise SimilarityValidationError(SimilarityReasonCode.INVALID_CANONICAL_IMAGE)
    _validate_dimensions(expected_width, expected_height)
    _require_sha256(expected_sha256)
    actual_sha256 = hashlib.sha256(canonical_jpeg).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SimilarityValidationError(SimilarityReasonCode.CHECKSUM_MISMATCH)
    try:
        decoded = decode_canonical_rgb_image(
            canonical_jpeg,
            expected_width=expected_width,
            expected_height=expected_height,
        )
    except ImageSanitizationError:
        raise SimilarityValidationError(SimilarityReasonCode.INVALID_CANONICAL_IMAGE) from None
    phash_hex = _phash_rgb(decoded.bytes_value, width=decoded.width, height=decoded.height)
    facts: dict[str, object] = {
        "algorithm_version": PHASH_ALGORITHM_VERSION,
        "height": decoded.height,
        "normalized_sha256": actual_sha256,
        "phash_hex": phash_hex,
        "width": decoded.width,
    }
    return SimilaritySignature(
        algorithm_version=PHASH_ALGORITHM_VERSION,
        normalized_sha256=actual_sha256,
        phash_hex=phash_hex,
        width=decoded.width,
        height=decoded.height,
        content_digest=_digest(facts),
    )


def is_exact_duplicate(left: SimilaritySignature, right: SimilaritySignature) -> bool:
    """Exact normalized SHA-256 equality is the only automatic duplicate hard gate."""
    _require_compatible_signatures(left, right)
    return left.normalized_sha256 == right.normalized_sha256


def phash_hamming_distance(left: SimilaritySignature, right: SimilaritySignature) -> int:
    """Return a deterministic 0..64 distance without applying a rejection threshold."""
    _require_compatible_signatures(left, right)
    return (int(left.phash_hex, 16) ^ int(right.phash_hex, 16)).bit_count()


def _phash_rgb(rgb_bytes: bytes, *, width: int, height: int) -> str:
    if type(rgb_bytes) is not bytes or len(rgb_bytes) != width * height * 3:
        raise SimilarityValidationError(SimilarityReasonCode.INVALID_CANONICAL_IMAGE)
    samples: list[list[int]] = []
    for output_y in range(PHASH_SAMPLE_EDGE):
        source_y = min(
            height - 1,
            ((2 * output_y + 1) * height) // (2 * PHASH_SAMPLE_EDGE),
        )
        row: list[int] = []
        for output_x in range(PHASH_SAMPLE_EDGE):
            source_x = min(
                width - 1,
                ((2 * output_x + 1) * width) // (2 * PHASH_SAMPLE_EDGE),
            )
            offset = (source_y * width + source_x) * 3
            red, green, blue = rgb_bytes[offset : offset + 3]
            row.append((77 * red + 150 * green + 29 * blue + 128) >> 8)
        samples.append(row)

    coefficients: list[int] = []
    for vertical_frequency in range(PHASH_LOW_FREQUENCY_EDGE):
        vertical_weights = _COSINE_TABLE[vertical_frequency]
        for horizontal_frequency in range(PHASH_LOW_FREQUENCY_EDGE):
            horizontal_weights = _COSINE_TABLE[horizontal_frequency]
            coefficient = 0
            for y, row in enumerate(samples):
                vertical_weight = vertical_weights[y]
                for x, pixel in enumerate(row):
                    coefficient += pixel * horizontal_weights[x] * vertical_weight
            coefficients.append(coefficient)

    non_dc = sorted(coefficients[1:])
    median = non_dc[len(non_dc) // 2]
    bit_value = 0
    for coefficient in coefficients:
        bit_value = (bit_value << 1) | int(coefficient > median)
    return f"{bit_value:016x}"


def _require_compatible_signatures(left: SimilaritySignature, right: SimilaritySignature) -> None:
    if not isinstance(left, SimilaritySignature) or not isinstance(right, SimilaritySignature):
        raise SimilarityValidationError(SimilarityReasonCode.INVALID_SIGNATURE)
    if left.algorithm_version != right.algorithm_version:
        raise SimilarityValidationError(SimilarityReasonCode.ALGORITHM_VERSION_MISMATCH)


def _validate_dimensions(width: int, height: int) -> None:
    if (
        type(width) is not int
        or type(height) is not int
        or width < 1
        or height < 1
        or width > MAX_SIGNATURE_EDGE_PIXELS
        or height > MAX_SIGNATURE_EDGE_PIXELS
        or width * height > MAX_SIGNATURE_TOTAL_PIXELS
    ):
        raise SimilarityValidationError(SimilarityReasonCode.INVALID_DIMENSIONS)


def _require_sha256(value: str) -> None:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise SimilarityValidationError(SimilarityReasonCode.INVALID_SIGNATURE)


def _digest(facts: Mapping[str, object]) -> str:
    canonical = json.dumps(
        facts,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    envelope = f"{SIMILARITY_SIGNATURE_SCHEMA_VERSION}\n{canonical}".encode()
    return hashlib.sha256(envelope).hexdigest()
