"""Epoch 02 source normalization and atomic D02 QuestionBank admission.

The module consumes only caller-supplied structural authorities and already
received PNG bytes.  It never resolves a private locator, calls a Provider, or
opens public-network access.  PostgreSQL remains the final admission authority.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, NoReturn, cast

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api import demo_d02_r2_authority as r2
from mirror_api.demo_d02_r2_epoch2_generation_receipt import GENERATION_RECEIPT_SCHEMA
from mirror_api.demo_d02_r2_generation_epoch2 import (
    E2_DISPATCH_EPOCH,
    E2_PRODUCER_TASK_ID,
    E2_ROOT_ID,
)
from mirror_api.demo_idempotency import (
    IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_measurement_quality import canonical_json_bytes, mirror_demo_digest
from mirror_api.demo_models import (
    DemoD02R2Epoch2Admission,
    DemoD02R2SourceAuthority,
    DemoPairScreeningReport,
    DemoQuestionBank,
    DemoQuestionPair,
    DemoSyntheticIdentity,
)
from mirror_api.models import Asset, AssetVariant

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

E2_SOURCE_AUTHORITY_SCHEMA: Final = "mirror.demo/D02R2Epoch2SourceAuthority/v1"
E2_SOURCE_QA_SCHEMA: Final = "mirror.demo/D02R2Epoch2SourceQASnapshot/v1"
E2_SOURCE_RECORD_SCHEMA: Final = "mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1"
E2_SOURCE_RECORD_ID_DOMAIN: Final = "mirror.demo/D02R2Epoch2SourceAuthorityRecordId/v1"
E2_ADMISSION_SCHEMA: Final = "mirror.demo/D02R2Epoch2Admission/v1"
E2_ADMISSION_ID_DOMAIN: Final = "mirror.demo/D02R2Epoch2AdmissionId/v1"
E2_EXECUTION_EPOCH: Final = "D02_R2_EPOCH_02"
SOURCE_NORMALIZATION_SCHEMA: Final = "mirror.demo/D02R2Epoch2SourceNormalizationReceipt/v1"
SOURCE_NORMALIZATION_VERSION: Final = "demo-d02-r2-e2-png-to-jpeg-v1"
SOURCE_JPEG_QUALITY: Final = 95
SOURCE_JPEG_SUBSAMPLING: Final = 0

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_ID_RE: Final = re.compile(r"[0-9a-f]{32}\Z")
_OUTPUT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

_GENERATION_RECEIPT_KEYS: Final = {
    "schema_version",
    "candidate_ordinal",
    "producer_task_id",
    "source_producer_task_id",
    "dispatch_epoch",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_output_id",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "generation_result_provenance_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "source_provenance_seal_receipt_digest",
    "source_provenance_registry_commit_receipt_digest",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "synthetic_only_attested",
    "real_person_reference_used",
    "receipt_digest",
}
_SOURCE_AUTHORITY_KEYS: Final = {
    "schema_version",
    "source_ordinal",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_output_id",
    "source_asset_id",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "generation_source_asset_sha256",
    "generation_source_asset_byte_size",
    "generation_source_asset_mime_type",
    "generation_source_asset_width",
    "generation_source_asset_height",
    "source_normalization_receipt_digest",
    "source_generation_receipt_digest",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "generation_request_digest",
    "source_provenance_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "source_provenance_seal_receipt_digest",
    "source_provenance_registry_commit_receipt_digest",
    "synthetic_only_attested",
    "real_person_reference_used",
    "authority_kind",
    "authority_digest",
}
_QA_KEYS: Final = (
    _SOURCE_AUTHORITY_KEYS - {"schema_version", "authority_kind", "authority_digest"}
) | {
    "schema_version",
    "source_authority_key",
    "source_authority_digest",
    "qa_policy_digest",
    "decode_record_digest",
    "ordered_review_decision_digests",
    "adult_synthetic_attested",
    "qa_state",
    "source_qa_snapshot_digest",
}
_E2_RECORD_ONLY_FIELDS: Final = {
    "generation_request_digest",
    "execution_epoch",
    "producer_task_id",
    "dispatch_epoch",
    "generation_source_asset_sha256",
    "generation_source_asset_byte_size",
    "generation_source_asset_mime_type",
    "generation_source_asset_width",
    "generation_source_asset_height",
    "source_normalization_receipt_digest",
}
_RECORD_KEYS: Final = set(r2._RECORD_FIELDS) | _E2_RECORD_ONLY_FIELDS
_PACKET_KEYS: Final = {
    "generation_receipt",
    "source_authority",
    "source_qa_snapshot",
    "supporting_row",
    "facts",
    "identity_row",
    "source_manifest_entry",
    "source_manifest_digest",
}
_ASSET_ROW_KEYS: Final = {
    "id",
    "owner_user_id",
    "asset_role",
    "storage_key",
    "mime_type",
    "byte_size",
    "width",
    "height",
    "sha256",
    "synthetic",
    "is_ai_generated",
    "is_ai_modified",
    "internal_purpose",
    "deleted_at",
}
_ASSET_VARIANT_ROW_KEYS: Final = {
    "id",
    "source_asset_id",
    "result_asset_id",
    "variant_type",
    "created_at",
}


class D02R2Epoch2AdmissionError(RuntimeError):
    """Base fail-closed error for Epoch 02 admission."""


class D02R2Epoch2PayloadConflict(D02R2Epoch2AdmissionError):
    code = IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD

    def __init__(self) -> None:
        super().__init__(self.code)


class D02R2Epoch2AuthorityCorruption(D02R2Epoch2AdmissionError):
    """A persisted admission cannot replay its target graph."""


@dataclass(frozen=True, slots=True)
class NormalizedSource:
    jpeg_bytes: bytes = field(repr=False)
    sha256: str
    byte_size: int
    width: int
    height: int
    receipt: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Epoch2AdmissionBundle:
    source_packets: tuple[Mapping[str, object], ...]
    asset_rows: tuple[Mapping[str, object], ...]
    asset_variant_rows: tuple[Mapping[str, object], ...]
    report_row: Mapping[str, object]
    question_bank_row: Mapping[str, object]
    question_pair_rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class Epoch2AdmissionResult:
    admission_id: str
    screening_report_id: str
    question_bank_id: str
    replayed: bool


def _fail(message: str) -> NoReturn:
    raise D02R2Epoch2AdmissionError(message)


def _exact(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _fail(f"{label} fields are invalid")
    return cast(Mapping[str, object], value)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase hexadecimal ID")
    return value


def _output_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _OUTPUT_ID_RE.fullmatch(value) is None:
        _fail(f"{label} must be an opaque output ID")
    return value


def normalize_epoch2_source_png(
    png_bytes: bytes,
    *,
    generation_receipt: Mapping[str, object],
) -> NormalizedSource:
    """Decode a received PNG and deterministically emit the bank's JPEG source."""

    receipt = validate_epoch2_generation_receipt(generation_receipt)
    if not isinstance(png_bytes, bytes) or not png_bytes:
        _fail("source PNG bytes are empty")
    if hashlib.sha256(png_bytes).hexdigest() != receipt["source_asset_sha256"]:
        _fail("source PNG checksum differs from its generation receipt")
    if len(png_bytes) != receipt["source_asset_byte_size"]:
        _fail("source PNG byte size differs from its generation receipt")
    try:
        with Image.open(io.BytesIO(png_bytes)) as image:
            image.load()
            if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                _fail("source bytes are not one static PNG")
            if image.size != (receipt["source_asset_width"], receipt["source_asset_height"]):
                _fail("source PNG dimensions differ from its generation receipt")
            rgb = image.convert("RGB")
            output = io.BytesIO()
            rgb.save(
                output,
                format="JPEG",
                quality=SOURCE_JPEG_QUALITY,
                subsampling=SOURCE_JPEG_SUBSAMPLING,
                optimize=False,
                progressive=False,
                exif=b"",
                icc_profile=None,
            )
            jpeg_bytes = output.getvalue()
    except (OSError, UnidentifiedImageError) as exc:
        raise D02R2Epoch2AdmissionError("source PNG normalization failed") from exc
    jpeg_sha256 = hashlib.sha256(jpeg_bytes).hexdigest()
    normalization: JsonObject = {
        "schema_version": SOURCE_NORMALIZATION_SCHEMA,
        "normalization_version": SOURCE_NORMALIZATION_VERSION,
        "source_generation_receipt_digest": cast(JsonScalar, receipt["receipt_digest"]),
        "generation_source_asset_sha256": cast(JsonScalar, receipt["source_asset_sha256"]),
        "generation_source_asset_byte_size": cast(JsonScalar, receipt["source_asset_byte_size"]),
        "generation_source_asset_mime_type": "image/png",
        "generation_source_asset_width": cast(JsonScalar, receipt["source_asset_width"]),
        "generation_source_asset_height": cast(JsonScalar, receipt["source_asset_height"]),
        "normalized_source_asset_sha256": jpeg_sha256,
        "normalized_source_asset_byte_size": len(jpeg_bytes),
        "normalized_source_asset_mime_type": "image/jpeg",
        "normalized_source_asset_width": cast(JsonScalar, receipt["source_asset_width"]),
        "normalized_source_asset_height": cast(JsonScalar, receipt["source_asset_height"]),
        "jpeg_quality": SOURCE_JPEG_QUALITY,
        "jpeg_subsampling": SOURCE_JPEG_SUBSAMPLING,
        "metadata_policy": "STRIP_ALL",
    }
    normalization["normalization_receipt_digest"] = mirror_demo_digest(
        SOURCE_NORMALIZATION_SCHEMA, normalization
    )
    return NormalizedSource(
        jpeg_bytes=jpeg_bytes,
        sha256=jpeg_sha256,
        byte_size=len(jpeg_bytes),
        width=cast(int, receipt["source_asset_width"]),
        height=cast(int, receipt["source_asset_height"]),
        receipt=normalization,
    )


def validate_epoch2_generation_receipt(value: object) -> Mapping[str, object]:
    receipt = _exact(value, _GENERATION_RECEIPT_KEYS, "Epoch 02 generation receipt")
    if (
        receipt["schema_version"] != GENERATION_RECEIPT_SCHEMA
        or receipt["evidence_root_id"] != E2_ROOT_ID
        or receipt["dispatch_epoch"] != E2_DISPATCH_EPOCH
        or receipt["source_producer_task_id"] != E2_PRODUCER_TASK_ID
        or receipt["source_asset_mime_type"] != "image/png"
        or receipt["synthetic_only_attested"] is not True
        or receipt["real_person_reference_used"] is not False
    ):
        _fail("Epoch 02 generation receipt boundary is invalid")
    ordinal = receipt["candidate_ordinal"]
    if type(ordinal) is not int or ordinal not in {1, 2, 3, 4}:
        _fail("Epoch 02 generation receipt ordinal is invalid")
    _output_id(receipt["source_output_id"], "source output ID")
    _output_id(receipt["source_provenance_output_id"], "source provenance output ID")
    for key in _GENERATION_RECEIPT_KEYS - {
        "schema_version",
        "candidate_ordinal",
        "producer_task_id",
        "source_producer_task_id",
        "dispatch_epoch",
        "evidence_root_id",
        "source_output_id",
        "source_provenance_output_id",
        "source_asset_byte_size",
        "source_asset_mime_type",
        "source_asset_width",
        "source_asset_height",
        "synthetic_only_attested",
        "real_person_reference_used",
    }:
        _digest(receipt[key], key)
    if any(
        type(receipt[key]) is not int or cast(int, receipt[key]) <= 0
        for key in ("source_asset_byte_size", "source_asset_width", "source_asset_height")
    ):
        _fail("Epoch 02 generation receipt image envelope is invalid")
    expected = mirror_demo_digest(
        GENERATION_RECEIPT_SCHEMA,
        cast(
            Mapping[str, JsonValue],
            {key: item for key, item in receipt.items() if key != "receipt_digest"},
        ),
    )
    if receipt["receipt_digest"] != expected:
        _fail("Epoch 02 generation receipt digest does not replay")
    return receipt


def build_epoch2_source_authority(
    *,
    generation_receipt: Mapping[str, object],
    normalized_source: NormalizedSource,
    source_asset_id: str,
) -> JsonObject:
    receipt = validate_epoch2_generation_receipt(generation_receipt)
    _id(source_asset_id, "normalized source Asset ID")
    normalization = normalized_source.receipt
    normalization_digest = _digest(
        normalization.get("normalization_receipt_digest"), "normalization receipt digest"
    )
    if (
        normalization.get("generation_source_asset_sha256") != receipt["source_asset_sha256"]
        or normalization.get("normalized_source_asset_sha256") != normalized_source.sha256
    ):
        _fail("source normalization receipt binding is invalid")
    authority: JsonObject = {
        "schema_version": E2_SOURCE_AUTHORITY_SCHEMA,
        "source_ordinal": cast(JsonScalar, receipt["candidate_ordinal"]),
        "execution_contract_digest": cast(JsonScalar, receipt["execution_contract_digest"]),
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": cast(JsonScalar, receipt["root_name_receipt_digest"]),
        "generation_preregistration_digest": cast(
            JsonScalar, receipt["generation_preregistration_digest"]
        ),
        "source_allocation_manifest_digest": cast(
            JsonScalar, receipt["source_allocation_manifest_digest"]
        ),
        "source_producer_dispatch_digest": cast(
            JsonScalar, receipt["source_producer_dispatch_digest"]
        ),
        "source_output_id": cast(JsonScalar, receipt["source_output_id"]),
        "source_asset_id": source_asset_id,
        "source_asset_sha256": normalized_source.sha256,
        "source_asset_byte_size": normalized_source.byte_size,
        "source_asset_mime_type": "image/jpeg",
        "source_asset_width": normalized_source.width,
        "source_asset_height": normalized_source.height,
        "generation_source_asset_sha256": cast(JsonScalar, receipt["source_asset_sha256"]),
        "generation_source_asset_byte_size": cast(JsonScalar, receipt["source_asset_byte_size"]),
        "generation_source_asset_mime_type": "image/png",
        "generation_source_asset_width": cast(JsonScalar, receipt["source_asset_width"]),
        "generation_source_asset_height": cast(JsonScalar, receipt["source_asset_height"]),
        "source_normalization_receipt_digest": normalization_digest,
        "source_generation_receipt_digest": cast(JsonScalar, receipt["receipt_digest"]),
        "output_name_receipt_digest": cast(JsonScalar, receipt["output_name_receipt_digest"]),
        "output_seal_receipt_digest": cast(JsonScalar, receipt["output_seal_receipt_digest"]),
        "registry_commit_receipt_digest": cast(
            JsonScalar, receipt["registry_commit_receipt_digest"]
        ),
        "generation_capability_authority_digest": cast(
            JsonScalar, receipt["generation_capability_authority_digest"]
        ),
        "generation_request_policy_digest": cast(
            JsonScalar, receipt["generation_request_policy_digest"]
        ),
        "generation_request_digest": cast(JsonScalar, receipt["generation_request_policy_digest"]),
        "source_provenance_digest": cast(
            JsonScalar, receipt["generation_result_provenance_digest"]
        ),
        "source_provenance_output_id": cast(JsonScalar, receipt["source_provenance_output_id"]),
        "source_provenance_name_receipt_digest": cast(
            JsonScalar, receipt["source_provenance_name_receipt_digest"]
        ),
        "source_provenance_seal_receipt_digest": cast(
            JsonScalar, receipt["source_provenance_seal_receipt_digest"]
        ),
        "source_provenance_registry_commit_receipt_digest": cast(
            JsonScalar, receipt["source_provenance_registry_commit_receipt_digest"]
        ),
        "synthetic_only_attested": True,
        "real_person_reference_used": False,
        "authority_kind": r2.R2_SOURCE_AUTHORITY_KIND,
    }
    authority["authority_digest"] = mirror_demo_digest(E2_SOURCE_AUTHORITY_SCHEMA, authority)
    return authority


def validate_epoch2_source_authority(
    value: object, *, generation_receipt: Mapping[str, object]
) -> Mapping[str, object]:
    authority = _exact(value, _SOURCE_AUTHORITY_KEYS, "Epoch 02 source authority")
    receipt = validate_epoch2_generation_receipt(generation_receipt)
    if (
        authority["schema_version"] != E2_SOURCE_AUTHORITY_SCHEMA
        or authority["authority_kind"] != r2.R2_SOURCE_AUTHORITY_KIND
        or authority["evidence_root_id"] != E2_ROOT_ID
        or authority["generation_request_digest"] != authority["generation_request_policy_digest"]
        or authority["source_asset_mime_type"] != "image/jpeg"
        or authority["generation_source_asset_mime_type"] != "image/png"
    ):
        _fail("Epoch 02 source authority boundary is invalid")
    copied = {
        "source_ordinal": "candidate_ordinal",
        "execution_contract_digest": "execution_contract_digest",
        "root_name_receipt_digest": "root_name_receipt_digest",
        "generation_preregistration_digest": "generation_preregistration_digest",
        "source_allocation_manifest_digest": "source_allocation_manifest_digest",
        "source_producer_dispatch_digest": "source_producer_dispatch_digest",
        "source_output_id": "source_output_id",
        "generation_source_asset_sha256": "source_asset_sha256",
        "generation_source_asset_byte_size": "source_asset_byte_size",
        "generation_source_asset_mime_type": "source_asset_mime_type",
        "generation_source_asset_width": "source_asset_width",
        "generation_source_asset_height": "source_asset_height",
        "output_name_receipt_digest": "output_name_receipt_digest",
        "output_seal_receipt_digest": "output_seal_receipt_digest",
        "registry_commit_receipt_digest": "registry_commit_receipt_digest",
        "generation_capability_authority_digest": "generation_capability_authority_digest",
        "generation_request_policy_digest": "generation_request_policy_digest",
        "source_provenance_output_id": "source_provenance_output_id",
        "source_provenance_name_receipt_digest": "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest": "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest": (
            "source_provenance_registry_commit_receipt_digest"
        ),
        "synthetic_only_attested": "synthetic_only_attested",
        "real_person_reference_used": "real_person_reference_used",
    }
    if any(authority[target] != receipt[source] for target, source in copied.items()):
        _fail("Epoch 02 source authority generation projection is invalid")
    if (
        authority["source_generation_receipt_digest"] != receipt["receipt_digest"]
        or authority["source_provenance_digest"] != receipt["generation_result_provenance_digest"]
    ):
        _fail("Epoch 02 source authority receipt binding is invalid")
    for key in (
        "source_asset_id",
        "source_asset_sha256",
        "source_normalization_receipt_digest",
    ):
        (_id if key == "source_asset_id" else _digest)(authority[key], key)
    expected = mirror_demo_digest(
        E2_SOURCE_AUTHORITY_SCHEMA,
        cast(
            Mapping[str, JsonValue],
            {key: item for key, item in authority.items() if key != "authority_digest"},
        ),
    )
    if authority["authority_digest"] != expected:
        _fail("Epoch 02 source authority digest does not replay")
    return authority


def build_epoch2_source_qa_snapshot(
    *,
    source_authority: Mapping[str, object],
    generation_receipt: Mapping[str, object],
    qa_policy_digest: str,
    decode_record_digest: str,
    ordered_review_decision_digests: Sequence[str],
) -> JsonObject:
    authority = validate_epoch2_source_authority(
        source_authority, generation_receipt=generation_receipt
    )
    _digest(qa_policy_digest, "QA policy digest")
    _digest(decode_record_digest, "decode record digest")
    if len(ordered_review_decision_digests) != 6:
        _fail("Epoch 02 source QA requires six ordered review decisions")
    for decision_digest in ordered_review_decision_digests:
        _digest(decision_digest, "review decision digest")
    qa: JsonObject = {
        "schema_version": E2_SOURCE_QA_SCHEMA,
        **{
            key: cast(JsonValue, value)
            for key, value in authority.items()
            if key not in {"schema_version", "authority_kind", "authority_digest"}
        },
        "source_authority_key": r2.derive_r2_source_authority_key(
            source_output_id=cast(str, authority["source_output_id"]),
            source_asset_id=cast(str, authority["source_asset_id"]),
            source_asset_sha256=cast(str, authority["source_asset_sha256"]),
            source_generation_receipt_digest=cast(
                str, authority["source_generation_receipt_digest"]
            ),
            source_authority_digest=cast(str, authority["authority_digest"]),
        ),
        "source_authority_digest": cast(JsonScalar, authority["authority_digest"]),
        "qa_policy_digest": qa_policy_digest,
        "decode_record_digest": decode_record_digest,
        "ordered_review_decision_digests": list(ordered_review_decision_digests),
        "adult_synthetic_attested": True,
        "qa_state": "PASSED",
    }
    qa["source_qa_snapshot_digest"] = mirror_demo_digest(E2_SOURCE_QA_SCHEMA, qa)
    return qa


def validate_epoch2_source_qa_snapshot(
    value: object,
    *,
    source_authority: Mapping[str, object],
    generation_receipt: Mapping[str, object],
) -> Mapping[str, object]:
    qa = _exact(value, _QA_KEYS, "Epoch 02 source QA snapshot")
    authority = validate_epoch2_source_authority(
        source_authority, generation_receipt=generation_receipt
    )
    if qa["schema_version"] != E2_SOURCE_QA_SCHEMA or qa["qa_state"] != "PASSED":
        _fail("Epoch 02 source QA state is invalid")
    expected = build_epoch2_source_qa_snapshot(
        source_authority=authority,
        generation_receipt=generation_receipt,
        qa_policy_digest=_digest(qa["qa_policy_digest"], "QA policy digest"),
        decode_record_digest=_digest(qa["decode_record_digest"], "decode record digest"),
        ordered_review_decision_digests=cast(Sequence[str], qa["ordered_review_decision_digests"]),
    )
    if dict(qa) != expected:
        _fail("Epoch 02 source QA snapshot does not replay")
    return qa


def build_epoch2_source_record(
    *,
    source_authority: Mapping[str, object],
    source_qa_snapshot: Mapping[str, object],
    generation_receipt: Mapping[str, object],
    created_at: str,
) -> JsonObject:
    authority = validate_epoch2_source_authority(
        source_authority, generation_receipt=generation_receipt
    )
    qa = validate_epoch2_source_qa_snapshot(
        source_qa_snapshot,
        source_authority=authority,
        generation_receipt=generation_receipt,
    )
    key = r2.derive_r2_source_authority_key(
        source_output_id=cast(str, authority["source_output_id"]),
        source_asset_id=cast(str, authority["source_asset_id"]),
        source_asset_sha256=cast(str, authority["source_asset_sha256"]),
        source_generation_receipt_digest=cast(str, authority["source_generation_receipt_digest"]),
        source_authority_digest=cast(str, authority["authority_digest"]),
    )
    canonical: JsonObject = {
        **{
            field_name: cast(JsonValue, field_value)
            for field_name, field_value in authority.items()
            if field_name not in {"schema_version", "authority_kind", "authority_digest"}
        },
        "source_authority_digest": cast(JsonScalar, authority["authority_digest"]),
        "source_authority_key": key,
        "source_qa_snapshot_digest": cast(JsonScalar, qa["source_qa_snapshot_digest"]),
        "adult_synthetic_attested": True,
        "authority_state": "PRINCIPAL_ACCEPTED",
        "execution_epoch": E2_EXECUTION_EPOCH,
        "producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
    }
    content_digest = mirror_demo_digest(E2_SOURCE_RECORD_SCHEMA, canonical)
    preimage: JsonObject = {
        "execution_contract_digest": cast(JsonScalar, canonical["execution_contract_digest"]),
        "evidence_root_id": E2_ROOT_ID,
        "root_name_receipt_digest": cast(JsonScalar, canonical["root_name_receipt_digest"]),
        "generation_preregistration_digest": cast(
            JsonScalar, canonical["generation_preregistration_digest"]
        ),
        "source_allocation_manifest_digest": cast(
            JsonScalar, canonical["source_allocation_manifest_digest"]
        ),
        "source_producer_dispatch_digest": cast(
            JsonScalar, canonical["source_producer_dispatch_digest"]
        ),
        "source_ordinal": cast(JsonScalar, canonical["source_ordinal"]),
        "source_output_id": cast(JsonScalar, canonical["source_output_id"]),
        "source_authority_key": key,
        "source_authority_digest": cast(JsonScalar, authority["authority_digest"]),
        "source_qa_snapshot_digest": cast(JsonScalar, qa["source_qa_snapshot_digest"]),
        "content_digest": content_digest,
        "generation_request_digest": cast(JsonScalar, canonical["generation_request_digest"]),
        "execution_epoch": E2_EXECUTION_EPOCH,
        "producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "generation_source_asset_sha256": cast(
            JsonScalar, canonical["generation_source_asset_sha256"]
        ),
        "generation_source_asset_byte_size": cast(
            JsonScalar, canonical["generation_source_asset_byte_size"]
        ),
        "generation_source_asset_mime_type": "image/png",
        "generation_source_asset_width": cast(
            JsonScalar, canonical["generation_source_asset_width"]
        ),
        "generation_source_asset_height": cast(
            JsonScalar, canonical["generation_source_asset_height"]
        ),
        "source_normalization_receipt_digest": cast(
            JsonScalar, canonical["source_normalization_receipt_digest"]
        ),
    }
    return {
        "id": mirror_demo_digest(E2_SOURCE_RECORD_ID_DOMAIN, preimage)[:32],
        "schema_version": E2_SOURCE_RECORD_SCHEMA,
        "canonical_payload": canonical,
        "content_digest": content_digest,
        "created_at": created_at,
        **canonical,
    }


def validate_epoch2_source_record(
    value: object,
    *,
    source_authority: Mapping[str, object],
    source_qa_snapshot: Mapping[str, object],
    generation_receipt: Mapping[str, object],
) -> Mapping[str, object]:
    row = _exact(value, _RECORD_KEYS, "Epoch 02 source authority record")
    expected = build_epoch2_source_record(
        source_authority=source_authority,
        source_qa_snapshot=source_qa_snapshot,
        generation_receipt=generation_receipt,
        created_at=cast(str, row["created_at"]),
    )
    if dict(row) != expected:
        _fail("Epoch 02 source authority record does not replay")
    return row


def validate_epoch2_admission_packet(value: object) -> None:
    packet = _exact(value, _PACKET_KEYS, "Epoch 02 admission packet")
    receipt = validate_epoch2_generation_receipt(packet["generation_receipt"])
    authority = validate_epoch2_source_authority(
        packet["source_authority"], generation_receipt=receipt
    )
    qa = validate_epoch2_source_qa_snapshot(
        packet["source_qa_snapshot"],
        source_authority=authority,
        generation_receipt=receipt,
    )
    row = validate_epoch2_source_record(
        packet["supporting_row"],
        source_authority=authority,
        source_qa_snapshot=qa,
        generation_receipt=receipt,
    )
    facts = r2.validate_r2_facts(packet["facts"])
    for facts_key, row_key in (
        ("source_output_id", "source_output_id"),
        ("source_asset_sha256", "source_asset_sha256"),
        ("source_asset_byte_size", "source_asset_byte_size"),
        ("source_asset_mime_type", "source_asset_mime_type"),
        ("source_asset_width", "source_asset_width"),
        ("source_asset_height", "source_asset_height"),
        ("source_receipt_digest", "source_generation_receipt_digest"),
        ("source_authority_digest", "source_authority_digest"),
        ("source_qa_snapshot_digest", "source_qa_snapshot_digest"),
        ("source_provenance_digest", "source_provenance_digest"),
        ("adult_synthetic_attested", "adult_synthetic_attested"),
    ):
        if facts[facts_key] != row[row_key]:
            _fail(f"Epoch 02 facts/source equality is invalid for {facts_key}")
    legacy_row = {key: item for key, item in row.items() if key not in _E2_RECORD_ONLY_FIELDS}
    identity = r2.validate_r2_identity_row(
        packet["identity_row"], facts=facts, supporting_row=legacy_row
    )
    r2._validate_r2_source_manifest_entry(
        packet["source_manifest_entry"],
        facts=facts,
        identity_row=identity,
        supporting_row=legacy_row,
    )
    _digest(packet["source_manifest_digest"], "source manifest digest")


def _validate_persistence_bindings(
    *,
    bundle: Epoch2AdmissionBundle,
    report: Mapping[str, Any],
    pairs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, JsonValue]], list[dict[str, JsonValue]]]:
    payload = cast(Mapping[str, object], report["report_payload"])
    exact_evidence = cast(Mapping[str, object], payload["exact_duplicate_evidence"])
    raw_images = exact_evidence["image_records"]
    if not isinstance(raw_images, list) or len(raw_images) != 52:
        _fail("Epoch 02 Report image authority must contain exactly 52 records")

    expected_assets: dict[str, Mapping[str, object]] = {}
    for raw_image in raw_images:
        if not isinstance(raw_image, Mapping):
            _fail("Epoch 02 Report image authority record is invalid")
        image = cast(Mapping[str, object], raw_image)
        role = image.get("authority_role")
        if role == "SOURCE":
            asset_id = _id(image.get("source_asset_id"), "Report source Asset ID")
        elif role == "RESULT":
            asset_id = _id(image.get("deterministic_result_asset_id"), "Report result Asset ID")
        else:
            _fail("Epoch 02 Report image authority role is invalid")
        if asset_id in expected_assets:
            _fail("Epoch 02 Report image authority duplicates an Asset ID")
        expected_assets[asset_id] = image
    if len(expected_assets) != 52:
        _fail("Epoch 02 Report image authority does not cover 52 Assets")

    actual_assets: dict[str, Mapping[str, object]] = {}
    asset_authorities: list[dict[str, JsonValue]] = []
    for raw_asset in bundle.asset_rows:
        asset = _exact(raw_asset, _ASSET_ROW_KEYS, "Epoch 02 Asset row")
        asset_id = _id(asset["id"], "Asset ID")
        asset_sha = _digest(asset["sha256"], "Asset checksum")
        storage_key = asset["storage_key"]
        if not isinstance(storage_key, str) or not storage_key:
            _fail("Epoch 02 Asset storage key is invalid")
        if (
            any(
                type(asset[field]) is not int or cast(int, asset[field]) < 1
                for field in ("byte_size", "width", "height")
            )
            or asset["mime_type"] != "image/jpeg"
        ):
            _fail("Epoch 02 Asset decoded image metadata is invalid")
        if (
            asset["owner_user_id"] is not None
            or asset["asset_role"] != "synthetic"
            or asset["synthetic"] is not True
            or asset["internal_purpose"] != "synthetic_dataset"
            or asset["deleted_at"] is not None
        ):
            _fail("Epoch 02 Asset synthetic-only boundary is invalid")
        expected = expected_assets.get(asset_id)
        if expected is None or any(
            asset[asset_key] != expected[record_key]
            for asset_key, record_key in (
                ("sha256", "sha256"),
                ("byte_size", "byte_size"),
                ("mime_type", "mime_type"),
                ("width", "width"),
                ("height", "height"),
            )
        ):
            _fail("Epoch 02 Asset does not match Report image authority")
        expected_ai_generated = expected["authority_role"] == "SOURCE"
        if (
            asset["is_ai_generated"] is not expected_ai_generated
            or asset["is_ai_modified"] is expected_ai_generated
        ):
            _fail("Epoch 02 Asset generation lineage flags are invalid")
        if asset_id in actual_assets:
            _fail("Epoch 02 Asset ID is duplicated")
        actual_assets[asset_id] = asset
        asset_authorities.append(
            {
                "id": asset_id,
                "sha256": asset_sha,
                "storage_key_digest": hashlib.sha256(storage_key.encode("utf-8")).hexdigest(),
                "byte_size": cast(int, asset["byte_size"]),
                "mime_type": asset["mime_type"],
                "width": cast(int, asset["width"]),
                "height": cast(int, asset["height"]),
            }
        )
    if set(actual_assets) != set(expected_assets):
        _fail("Epoch 02 Asset rows do not exactly cover Report image authority")

    raw_pair_evidence = payload["pair_quality_evidence"]
    if not isinstance(raw_pair_evidence, list) or len(raw_pair_evidence) != 24:
        _fail("Epoch 02 Report pair authority must contain exactly 24 records")
    expected_variants: dict[str, dict[str, object]] = {}
    for raw_wrapper in raw_pair_evidence:
        wrapper = cast(Mapping[str, object], raw_wrapper)
        pair_payload = cast(Mapping[str, object], wrapper["pair_screening_record_payload"])
        source_asset_id = _id(pair_payload["source_asset_id"], "variant source Asset ID")
        for side_name in ("left", "right"):
            side = cast(Mapping[str, object], pair_payload[side_name])
            variant_id = _id(side["asset_variant_id"], "AssetVariant ID")
            if variant_id in expected_variants:
                _fail("Epoch 02 Report duplicates an AssetVariant ID")
            expected_variants[variant_id] = {
                "source_asset_id": source_asset_id,
                "result_asset_id": _id(side["result_asset_id"], "variant result Asset ID"),
                "variant_type": side["asset_variant_type"],
            }
    if len(expected_variants) != 48:
        _fail("Epoch 02 Report does not cover 48 AssetVariants")

    actual_variants: dict[str, Mapping[str, object]] = {}
    variant_authorities: list[dict[str, JsonValue]] = []
    for raw_variant in bundle.asset_variant_rows:
        variant = _exact(raw_variant, _ASSET_VARIANT_ROW_KEYS, "Epoch 02 AssetVariant row")
        variant_id = _id(variant["id"], "AssetVariant ID")
        source_asset_id = _id(variant["source_asset_id"], "variant source Asset ID")
        result_asset_id = _id(variant["result_asset_id"], "variant result Asset ID")
        expected = expected_variants.get(variant_id)
        if expected is None or any(
            variant[key] != expected[key]
            for key in ("source_asset_id", "result_asset_id", "variant_type")
        ):
            _fail("Epoch 02 AssetVariant does not match Report pair authority")
        if not isinstance(variant["variant_type"], str) or not variant["variant_type"]:
            _fail("Epoch 02 AssetVariant type is invalid")
        if source_asset_id not in actual_assets or result_asset_id not in actual_assets:
            _fail("Epoch 02 AssetVariant references an unbound Asset")
        created_at = variant["created_at"]
        if not isinstance(created_at, str) or not created_at:
            _fail("Epoch 02 AssetVariant created_at is invalid")
        try:
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            _fail("Epoch 02 AssetVariant created_at is invalid")
        if variant_id in actual_variants:
            _fail("Epoch 02 AssetVariant ID is duplicated")
        actual_variants[variant_id] = variant
        variant_authorities.append(
            {
                "id": variant_id,
                "source_asset_id": source_asset_id,
                "result_asset_id": result_asset_id,
                "variant_type": variant["variant_type"],
            }
        )
    if set(actual_variants) != set(expected_variants):
        _fail("Epoch 02 AssetVariant rows do not exactly cover Report pair authority")

    for pair in pairs:
        for side_name in ("left", "right"):
            asset_id = cast(str, pair[f"{side_name}_asset_id"])
            selected_asset = actual_assets.get(asset_id)
            if (
                selected_asset is None
                or selected_asset["sha256"] != pair[f"{side_name}_asset_sha256"]
            ):
                _fail("Epoch 02 QuestionPair result checksum is not bound to Asset authority")
            if cast(str, pair[f"{side_name}_asset_variant_id"]) not in actual_variants:
                _fail("Epoch 02 QuestionPair AssetVariant is not admitted")

    asset_authorities.sort(key=lambda item: cast(str, item["id"]))
    variant_authorities.sort(key=lambda item: cast(str, item["id"]))
    return asset_authorities, variant_authorities


def _validate_bundle(bundle: Epoch2AdmissionBundle) -> dict[str, JsonValue]:
    if len(bundle.source_packets) != 4:
        _fail("Epoch 02 admission requires four source packets")
    for packet in bundle.source_packets:
        validate_epoch2_admission_packet(packet)
    report = r2.validate_r2_report_row(bundle.report_row, source_packets=bundle.source_packets)
    bank = r2.validate_r2_question_bank_row(
        bundle.question_bank_row,
        report=report,
        source_packets=bundle.source_packets,
    )
    if len(bundle.question_pair_rows) != 16:
        _fail("Epoch 02 admission requires sixteen QuestionPairs")
    pairs = [
        r2.validate_r2_question_pair_row(
            pair,
            report=report,
            bank=bank,
            source_packets=bundle.source_packets,
        )
        for pair in bundle.question_pair_rows
    ]
    if len(bundle.asset_rows) != 52 or len(bundle.asset_variant_rows) != 48:
        _fail("Epoch 02 admission requires 52 Assets and 48 AssetVariants")
    asset_authorities, variant_authorities = _validate_persistence_bindings(
        bundle=bundle,
        report=report,
        pairs=pairs,
    )
    asset_ids = {cast(str, item["id"]) for item in asset_authorities}
    source_ids = {
        cast(str, cast(Mapping[str, object], packet["supporting_row"])["source_asset_id"])
        for packet in bundle.source_packets
    }
    result_ids = {
        cast(str, pair[side]) for pair in pairs for side in ("left_asset_id", "right_asset_id")
    }
    if len(source_ids) != 4 or len(result_ids) != 32 or not (source_ids | result_ids) <= asset_ids:
        _fail("Epoch 02 selected image graph is incomplete")
    return {
        "source_packet_content_digests": cast(
            JsonValue,
            [
                cast(
                    JsonScalar,
                    cast(Mapping[str, object], packet["supporting_row"])["content_digest"],
                )
                for packet in bundle.source_packets
            ],
        ),
        "asset_authorities": cast(
            JsonValue,
            asset_authorities,
        ),
        "asset_variant_authorities": cast(JsonValue, variant_authorities),
        "screening_report_id": cast(JsonScalar, report["id"]),
        "screening_report_content_digest": cast(JsonScalar, report["content_digest"]),
        "question_bank_id": cast(JsonScalar, bank["id"]),
        "question_bank_content_digest": cast(JsonScalar, bank["content_digest"]),
        "question_pair_content_digests": cast(
            JsonValue,
            sorted(cast(str, pair["content_digest"]) for pair in pairs),
        ),
    }


def _admission_values(
    *,
    bundle: Epoch2AdmissionBundle,
    idempotency_key_hash_value: str,
    request_digest: str,
) -> dict[str, object]:
    report = bundle.report_row
    bank = bundle.question_bank_row
    canonical: dict[str, object] = {
        "idempotency_key_hash": idempotency_key_hash_value,
        "request_digest": request_digest,
        "execution_epoch": E2_EXECUTION_EPOCH,
        "evidence_root_id": E2_ROOT_ID,
        "source_manifest_digest": report["source_manifest_digest"],
        "screening_report_id": report["id"],
        "screening_report_digest": report["report_digest"],
        "question_bank_id": bank["id"],
        "question_bank_content_digest": bank["content_digest"],
        "question_bank_version": bank["version"],
        "selected_pair_manifest_digest": report["selected_pair_manifest_digest"],
        "source_authority_count": 4,
        "synthetic_identity_count": 4,
        "question_pair_count": 16,
        "selected_result_side_count": 32,
        "admission_state": "COMPLETED",
    }
    admission_id = mirror_demo_digest(
        E2_ADMISSION_ID_DOMAIN,
        cast(
            Mapping[str, JsonValue],
            {
                "idempotency_key_hash": idempotency_key_hash_value,
                "request_digest": request_digest,
                "screening_report_id": report["id"],
                "question_bank_id": bank["id"],
            },
        ),
    )[:32]
    return {
        "id": admission_id,
        "schema_version": E2_ADMISSION_SCHEMA,
        "canonical_payload": canonical,
        "content_digest": mirror_demo_digest(
            E2_ADMISSION_SCHEMA, cast(Mapping[str, JsonValue], canonical)
        ),
        **canonical,
    }


def _orm_values(
    value: Mapping[str, object], *, drop_identity_computed: bool = False
) -> dict[str, object]:
    fields = dict(value)
    created_at = fields.get("created_at")
    if isinstance(created_at, str):
        fields["created_at"] = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if drop_identity_computed:
        fields.pop("source_authority_kind", None)
        fields.pop("source_authority_key", None)
    return fields


_ASSET_REPLAY_FIELDS: Final = (
    "owner_user_id",
    "asset_role",
    "mime_type",
    "byte_size",
    "width",
    "height",
    "sha256",
    "synthetic",
    "is_ai_generated",
    "is_ai_modified",
    "internal_purpose",
    "deleted_at",
)
_ASSET_VARIANT_REPLAY_FIELDS: Final = (
    "source_asset_id",
    "result_asset_id",
    "variant_type",
)


async def _insert_or_replay_asset_authority(
    session: AsyncSession, bundle: Epoch2AdmissionBundle
) -> None:
    asset_values = [_orm_values(row) for row in bundle.asset_rows]
    await session.execute(insert(Asset).values(asset_values).on_conflict_do_nothing())
    asset_ids = [cast(str, row["id"]) for row in bundle.asset_rows]
    persisted_assets = (await session.scalars(select(Asset).where(Asset.id.in_(asset_ids)))).all()
    persisted_asset_by_id = {asset.id: asset for asset in persisted_assets}
    expected_asset_by_id = {cast(str, row["id"]): row for row in bundle.asset_rows}
    if set(persisted_asset_by_id) != set(expected_asset_by_id):
        raise D02R2Epoch2AuthorityCorruption(
            "persisted Asset authority does not cover the admission graph"
        )
    for asset_id, expected in expected_asset_by_id.items():
        persisted_asset = persisted_asset_by_id[asset_id]
        if any(
            getattr(persisted_asset, field) != expected[field] for field in _ASSET_REPLAY_FIELDS
        ):
            raise D02R2Epoch2AuthorityCorruption(
                "persisted Asset authority does not replay admission bytes"
            )

    variant_values = [_orm_values(row) for row in bundle.asset_variant_rows]
    await session.execute(insert(AssetVariant).values(variant_values).on_conflict_do_nothing())
    variant_ids = [cast(str, row["id"]) for row in bundle.asset_variant_rows]
    persisted_variants = (
        await session.scalars(select(AssetVariant).where(AssetVariant.id.in_(variant_ids)))
    ).all()
    persisted_variant_by_id = {variant.id: variant for variant in persisted_variants}
    expected_variant_by_id = {cast(str, row["id"]): row for row in bundle.asset_variant_rows}
    if set(persisted_variant_by_id) != set(expected_variant_by_id):
        raise D02R2Epoch2AuthorityCorruption(
            "persisted AssetVariant authority does not cover the admission graph"
        )
    for variant_id, expected in expected_variant_by_id.items():
        persisted_variant = persisted_variant_by_id[variant_id]
        if any(
            getattr(persisted_variant, field) != expected[field]
            for field in _ASSET_VARIANT_REPLAY_FIELDS
        ):
            raise D02R2Epoch2AuthorityCorruption(
                "persisted AssetVariant authority does not replay admission lineage"
            )


class D02R2Epoch2AdmissionCoordinator:
    """Claim idempotency first, then atomically persist the complete graph."""

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def admit(
        self,
        *,
        idempotency_key: str,
        bundle: Epoch2AdmissionBundle,
    ) -> Epoch2AdmissionResult:
        semantic_request = _validate_bundle(bundle)
        key_hash = idempotency_key_hash(idempotency_key)
        request_digest = semantic_request_digest(cast(Mapping[str, Any], semantic_request))
        values = _admission_values(
            bundle=bundle,
            idempotency_key_hash_value=key_hash,
            request_digest=request_digest,
        )
        async with self._session_factory() as session:
            async with session.begin():
                inserted_id = await session.scalar(
                    insert(DemoD02R2Epoch2Admission)
                    .values(**values)
                    .on_conflict_do_nothing(
                        index_elements=(DemoD02R2Epoch2Admission.idempotency_key_hash,)
                    )
                    .returning(DemoD02R2Epoch2Admission.id)
                )
                if inserted_id is None:
                    existing = await session.scalar(
                        select(DemoD02R2Epoch2Admission).where(
                            DemoD02R2Epoch2Admission.idempotency_key_hash == key_hash
                        )
                    )
                    if existing is None:
                        raise D02R2Epoch2AuthorityCorruption(
                            "idempotency winner was not reloadable"
                        )
                    if existing.request_digest != request_digest:
                        raise D02R2Epoch2PayloadConflict()
                    await self._verify_existing(session, existing)
                    return Epoch2AdmissionResult(
                        admission_id=existing.id,
                        screening_report_id=existing.screening_report_id,
                        question_bank_id=existing.question_bank_id,
                        replayed=True,
                    )

                await _insert_or_replay_asset_authority(session, bundle)
                session.add_all(
                    DemoD02R2SourceAuthority(
                        **_orm_values(cast(Mapping[str, object], packet["supporting_row"]))
                    )
                    for packet in bundle.source_packets
                )
                await session.flush()
                session.add_all(
                    DemoSyntheticIdentity(
                        **_orm_values(
                            cast(Mapping[str, object], packet["identity_row"]),
                            drop_identity_computed=True,
                        )
                    )
                    for packet in bundle.source_packets
                )
                await session.flush()
                session.add(DemoPairScreeningReport(**_orm_values(bundle.report_row)))
                await session.flush()
                session.add(DemoQuestionBank(**_orm_values(bundle.question_bank_row)))
                await session.flush()
                session.add_all(
                    DemoQuestionPair(**_orm_values(row)) for row in bundle.question_pair_rows
                )
                await session.flush()
                admission = await session.get(DemoD02R2Epoch2Admission, inserted_id)
                if admission is None:
                    raise D02R2Epoch2AuthorityCorruption(
                        "new admission binding disappeared before commit"
                    )
                return Epoch2AdmissionResult(
                    admission_id=admission.id,
                    screening_report_id=admission.screening_report_id,
                    question_bank_id=admission.question_bank_id,
                    replayed=False,
                )

    async def _verify_existing(
        self, session: AsyncSession, admission: DemoD02R2Epoch2Admission
    ) -> None:
        report = await session.get(DemoPairScreeningReport, admission.screening_report_id)
        bank = await session.get(DemoQuestionBank, admission.question_bank_id)
        pair_ids = await session.scalars(
            select(DemoQuestionPair.id).where(
                DemoQuestionPair.question_bank_id == admission.question_bank_id
            )
        )
        if (
            report is None
            or bank is None
            or report.report_digest != admission.screening_report_digest
            or bank.content_digest != admission.question_bank_content_digest
            or bank.pair_manifest_digest != admission.selected_pair_manifest_digest
            or len(pair_ids.all()) != 16
        ):
            raise D02R2Epoch2AuthorityCorruption("persisted admission graph does not replay")


def canonical_epoch2_admission_bytes(value: Mapping[str, object]) -> bytes:
    """Expose deterministic serialization without accepting raw floats."""

    try:
        decoded = json.loads(canonical_json_bytes(value))
    except (TypeError, ValueError) as exc:
        raise D02R2Epoch2AdmissionError("admission payload is not canonical JSON") from exc
    return canonical_json_bytes(cast(Mapping[str, Any], decoded))
