from __future__ import annotations

import hashlib
import io
from copy import deepcopy

import pytest
from PIL import Image
from test_demo_d02_r2_generation_e3 import _contract

from mirror_api import demo_d02_r2_e3_admission as e3
from mirror_api.demo_d02_r2_epoch3_generation_receipt import (
    build_epoch3_source_generation_receipt,
)
from mirror_api.demo_d02_r2_generation_e3 import E3_CONTEXT, E4_CONTEXT, GenerationExecutionContext


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _receipt(
    *,
    png: bytes,
    ordinal: int = 1,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> dict[str, object]:
    return build_epoch3_source_generation_receipt(
        contract=_contract(context),
        ordinal=ordinal,
        root_name_receipt_digest=_digest("root"),
        generation_preregistration_digest=_digest("preregistration"),
        source_allocation_manifest_digest=_digest("allocation"),
        source_producer_dispatch_digest=_digest("dispatch"),
        output_name_receipt_digest=_digest("name"),
        output_seal_receipt_digest=_digest("seal"),
        registry_commit_receipt_digest=_digest("commit"),
        generation_capability_authority_digest=_digest("capability"),
        generation_request_digest=_digest(f"request-{ordinal}"),
        generation_result_provenance_digest=_digest(f"provenance-{ordinal}"),
        source_provenance_name_receipt_digest=_digest("provenance-name"),
        source_provenance_seal_receipt_digest=_digest("provenance-seal"),
        source_provenance_registry_commit_receipt_digest=_digest("provenance-commit"),
        source_asset_sha256=hashlib.sha256(png).hexdigest(),
        source_asset_byte_size=len(png),
        source_asset_width=24,
        source_asset_height=16,
        context=context,
    )


def _png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (24, 16), (10, 20, 30)).save(output, format="PNG")
    return output.getvalue()


def _policy_review() -> dict[str, object]:
    return {
        "adult_status": "VERIFIED_SYNTHETIC_ADULT",
        "suspected_minor": False,
        "real_person_reference": False,
        "celebrity_resemblance": False,
        "visual_quality": "PASS",
        "anti_homogenization": "PASS",
        "capture_grammar": "PASS",
        "qa_result": "PASS",
        "rejection_reason": None,
    }


def test_e3_png_normalization_is_deterministic_and_bound() -> None:
    png = _png()
    receipt = _receipt(png=png)
    first = e3.normalize_epoch3_source_png(png, generation_receipt=receipt)
    second = e3.normalize_epoch3_source_png(png, generation_receipt=receipt)
    assert first.jpeg_bytes == second.jpeg_bytes
    assert first.receipt["schema_version"] == e3.SOURCE_NORMALIZATION_SCHEMA
    assert first.receipt["normalization_version"] == e3.SOURCE_NORMALIZATION_VERSION
    assert first.receipt["normalized_source_asset_mime_type"] == "image/jpeg"
    assert first.receipt["jpeg_quality"] == 95
    assert first.receipt["jpeg_subsampling"] == 0


def test_e3_rejects_tampered_and_cross_epoch_receipts() -> None:
    png = _png()
    receipt = _receipt(png=png)
    receipt["dispatch_epoch"] = 2
    with pytest.raises(e3.D02R2Epoch3AdmissionError):
        e3.validate_epoch3_generation_receipt(receipt)

    receipt = _receipt(png=png)
    receipt["source_asset_sha256"] = _digest("tampered")
    with pytest.raises(e3.D02R2Epoch3AdmissionError):
        e3.normalize_epoch3_source_png(png, generation_receipt=receipt)


def test_e3_source_policy_review_rejects_minor_before_authority() -> None:
    png = _png()
    receipt = _receipt(png=png)
    normalized = e3.normalize_epoch3_source_png(png, generation_receipt=receipt)
    review = deepcopy(_policy_review())
    review["suspected_minor"] = True
    with pytest.raises(e3.D02R2Epoch3AdmissionError, match="policy review"):
        e3.build_epoch3_source_authority(
            generation_receipt=receipt,
            normalized_source=normalized,
            source_asset_id="1" * 32,
            policy_review=review,
        )


def test_e4_normalization_and_authority_are_e4_typed() -> None:
    png = _png()
    receipt = _receipt(png=png, context=E4_CONTEXT)
    normalized = e3.normalize_epoch3_source_png(png, generation_receipt=receipt, context=E4_CONTEXT)
    authority = e3.build_epoch3_source_authority(
        generation_receipt=receipt,
        normalized_source=normalized,
        source_asset_id="2" * 32,
        policy_review=_policy_review(),
        context=E4_CONTEXT,
    )
    assert normalized.receipt["schema_version"] == E4_CONTEXT.source_normalization_schema
    assert authority["schema_version"] == E4_CONTEXT.source_authority_schema
    assert authority["evidence_root_id"] == E4_CONTEXT.root_id
    assert (
        e3.validate_epoch3_source_authority(
            authority, generation_receipt=receipt, context=E4_CONTEXT
        )
        == authority
    )
    with pytest.raises(e3.D02R2Epoch3AdmissionError):
        e3.validate_epoch3_source_authority(authority, generation_receipt=receipt)
