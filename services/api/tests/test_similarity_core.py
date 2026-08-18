from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import cast

import pytest

from mirror_api.image_sanitizer import ImageSanitizationError, canonicalize_rgb_image
from mirror_api.synthetic_dataset import (
    PHASH_ALGORITHM_VERSION,
    PHASH_BITS,
    SimilarityReasonCode,
    SimilaritySignature,
    SimilarityValidationError,
    compute_similarity_signature,
    is_exact_duplicate,
    phash_hamming_distance,
)


def _canonical_fixture(*, variant: int = 0, width: int = 64, height: int = 64) -> bytes:
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            if variant == 0:
                pixels.extend(((x * 4) % 256, (y * 4) % 256, ((x + y) * 2) % 256))
            else:
                checker = 240 if ((x // 8) + (y // 8)) % 2 else 16
                pixels.extend((checker, (checker + x * 3) % 256, (255 - checker)))
    return canonicalize_rgb_image(bytes(pixels), width=width, height=height).bytes_value


def _signature(*, variant: int = 0) -> SimilaritySignature:
    canonical = _canonical_fixture(variant=variant)
    return compute_similarity_signature(
        canonical,
        expected_width=64,
        expected_height=64,
        expected_sha256=hashlib.sha256(canonical).hexdigest(),
    )


def test_signature_is_deterministic_bounded_and_golden() -> None:
    canonical = _canonical_fixture()
    sha256 = hashlib.sha256(canonical).hexdigest()

    first = compute_similarity_signature(
        canonical,
        expected_width=64,
        expected_height=64,
        expected_sha256=sha256,
    )
    second = compute_similarity_signature(
        canonical,
        expected_width=64,
        expected_height=64,
        expected_sha256=sha256,
    )

    assert first == second
    assert first.algorithm_version == PHASH_ALGORITHM_VERSION
    assert len(first.phash_hex) * 4 == PHASH_BITS
    assert first.phash_hex == "a00d812ea37eff0b"
    assert len(first.content_digest) == 64


def test_exact_duplicate_is_sha_only_and_hamming_is_threshold_free() -> None:
    left = _signature(variant=0)
    same = _signature(variant=0)
    different = _signature(variant=1)

    assert is_exact_duplicate(left, same) is True
    assert phash_hamming_distance(left, same) == 0
    assert is_exact_duplicate(left, different) is False
    assert 0 < phash_hamming_distance(left, different) <= PHASH_BITS


def test_checksum_mismatch_fails_without_echoing_caller_content() -> None:
    canonical = _canonical_fixture()
    marker = "f" * 64

    with pytest.raises(SimilarityValidationError) as error:
        compute_similarity_signature(
            canonical,
            expected_width=64,
            expected_height=64,
            expected_sha256=marker,
        )

    assert error.value.reason_code is SimilarityReasonCode.CHECKSUM_MISMATCH
    assert marker not in str(error.value)


def test_malformed_and_wrong_shape_inputs_fail_closed() -> None:
    malformed = b"not-a-canonical-jpeg"
    with pytest.raises(SimilarityValidationError) as invalid:
        compute_similarity_signature(
            malformed,
            expected_width=64,
            expected_height=64,
            expected_sha256=hashlib.sha256(malformed).hexdigest(),
        )
    assert invalid.value.reason_code is SimilarityReasonCode.INVALID_CANONICAL_IMAGE

    canonical = _canonical_fixture()
    with pytest.raises(SimilarityValidationError) as wrong_shape:
        compute_similarity_signature(
            canonical,
            expected_width=63,
            expected_height=64,
            expected_sha256=hashlib.sha256(canonical).hexdigest(),
        )
    assert wrong_shape.value.reason_code is SimilarityReasonCode.INVALID_CANONICAL_IMAGE


@pytest.mark.parametrize(
    ("width", "height"),
    [(0, 64), (64, 0), (8193, 1), (8000, 6000), (True, 64)],
)
def test_dimensions_are_strictly_bounded(width: object, height: object) -> None:
    canonical = _canonical_fixture()
    with pytest.raises(SimilarityValidationError) as error:
        compute_similarity_signature(
            canonical,
            expected_width=width,  # type: ignore[arg-type]
            expected_height=height,  # type: ignore[arg-type]
            expected_sha256=hashlib.sha256(canonical).hexdigest(),
        )
    assert error.value.reason_code is SimilarityReasonCode.INVALID_DIMENSIONS


def test_decoder_resource_failure_maps_to_safe_similarity_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = _canonical_fixture()

    def reject_bomb(*args: object, **kwargs: object) -> object:
        raise ImageSanitizationError("image_decompression_bomb")

    monkeypatch.setattr(
        "mirror_api.synthetic_dataset.similarity.decode_canonical_rgb_image",
        reject_bomb,
    )
    with pytest.raises(SimilarityValidationError) as error:
        compute_similarity_signature(
            canonical,
            expected_width=64,
            expected_height=64,
            expected_sha256=hashlib.sha256(canonical).hexdigest(),
        )
    assert error.value.reason_code is SimilarityReasonCode.INVALID_CANONICAL_IMAGE


def test_signature_direct_tampering_and_untyped_values_fail_closed() -> None:
    signature = _signature()
    with pytest.raises(SimilarityValidationError) as tampered:
        replace(signature, phash_hex="0" * 16, content_digest="f" * 64)
    assert tampered.value.reason_code is SimilarityReasonCode.INVALID_SIGNATURE

    with pytest.raises(SimilarityValidationError) as invalid_algorithm:
        replace(
            signature,
            algorithm_version="unregistered-phash-v2",
            content_digest="f" * 64,
        )
    assert invalid_algorithm.value.reason_code is SimilarityReasonCode.ALGORITHM_VERSION_MISMATCH

    with pytest.raises(SimilarityValidationError) as untyped:
        phash_hamming_distance(signature, cast(SimilaritySignature, object()))
    assert untyped.value.reason_code is SimilarityReasonCode.INVALID_SIGNATURE
