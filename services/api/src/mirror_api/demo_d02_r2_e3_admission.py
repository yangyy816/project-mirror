"""Epoch 03 source authority and admission-domain boundary.

This module is deliberately pure: callers inject already-received PNG bytes and
the public generation receipt.  It neither discovers a locator nor invokes a
provider.  Persistence is left behind an explicit coordinator seam until the
central E3 ORM/migration binding exists.
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
from mirror_api import demo_d02_r2_epoch2_admission as epoch2
from mirror_api.demo_d02_r2_epoch3_generation_receipt import (
    SOURCE_GENERATION_RECEIPT_SCHEMA,
    validate_epoch3_source_generation_receipt,
)
from mirror_api.demo_d02_r2_generation_e3 import (
    ADULT_STATUS,
    E3_CONTEXT,
    Epoch3GenerationError,
    GenerationExecutionContext,
    validate_epoch3_source_policy_profile,
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

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
type JsonObject = dict[str, JsonValue]

TASK_ID: Final = E3_CONTEXT.task_id
PRODUCER_TASK_ID: Final = E3_CONTEXT.producer_task_id
ROOT_ID: Final = E3_CONTEXT.root_id
DISPATCH_EPOCH: Final = E3_CONTEXT.dispatch_epoch
EXECUTION_EPOCH: Final = E3_CONTEXT.execution_epoch

E3_GENERATION_RECEIPT_SCHEMA: Final = SOURCE_GENERATION_RECEIPT_SCHEMA
E3_SOURCE_AUTHORITY_SCHEMA: Final = E3_CONTEXT.source_authority_schema
E3_SOURCE_QA_SCHEMA: Final = E3_CONTEXT.source_qa_schema
E3_SOURCE_RECORD_SCHEMA: Final = E3_CONTEXT.source_record_schema
E3_SOURCE_RECORD_ID_DOMAIN: Final = E3_CONTEXT.source_record_id_domain
E3_ADMISSION_SCHEMA: Final = E3_CONTEXT.admission_schema
E3_ADMISSION_ID_DOMAIN: Final = E3_CONTEXT.admission_id_domain
SOURCE_NORMALIZATION_SCHEMA: Final = E3_CONTEXT.source_normalization_schema
SOURCE_NORMALIZATION_VERSION: Final = E3_CONTEXT.source_normalization_version
SOURCE_JPEG_QUALITY: Final = 95
SOURCE_JPEG_SUBSAMPLING: Final = 0
SOURCE_POLICY_METADATA_SCHEMA: Final = E3_CONTEXT.source_policy_metadata_schema

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_ID_RE: Final = re.compile(r"[0-9a-f]{32}\Z")

_AUTHORITY_KEYS: Final = {
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
    "generation_policy_metadata",
    "authority_kind",
    "authority_digest",
}
_QA_KEYS: Final = (_AUTHORITY_KEYS - {"schema_version", "authority_kind", "authority_digest"}) | {
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
_E3_RECORD_ONLY_FIELDS: Final = {
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
    "generation_policy_metadata",
}
_POLICY_REVIEW_KEYS: Final = {
    "adult_status",
    "suspected_minor",
    "real_person_reference",
    "celebrity_resemblance",
    "visual_quality",
    "anti_homogenization",
    "capture_grammar",
    "qa_result",
    "rejection_reason",
}
_POLICY_METADATA_KEYS: Final = {
    "schema_version",
    "source_policy_profile",
    "source_policy_profile_digest",
    "adult_status",
    "suspected_minor",
    "real_person_reference",
    "celebrity_resemblance",
    "visual_quality",
    "anti_homogenization",
    "capture_grammar",
    "source_digest",
    "qa_result",
    "rejection_reason",
    "metadata_digest",
}


class D02R2Epoch3AdmissionError(RuntimeError):
    """E3 validation or unavailable central-persistence boundary failed closed."""


class D02R2Epoch3PayloadConflict(D02R2Epoch3AdmissionError):
    code = IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD

    def __init__(self) -> None:
        super().__init__("Epoch 03 idempotency key was reused with another graph")


class D02R2Epoch3AuthorityCorruption(D02R2Epoch3AdmissionError):
    """Raised when an existing PostgreSQL graph no longer replays."""


@dataclass(frozen=True, slots=True)
class NormalizedSource:
    jpeg_bytes: bytes = field(repr=False)
    sha256: str
    byte_size: int
    width: int
    height: int
    receipt: Mapping[str, JsonValue]


@dataclass(frozen=True, slots=True)
class Epoch3AdmissionBundle:
    source_packets: tuple[Mapping[str, object], ...]
    asset_rows: tuple[Mapping[str, object], ...]
    asset_variant_rows: tuple[Mapping[str, object], ...]
    report_row: Mapping[str, object]
    question_bank_row: Mapping[str, object]
    question_pair_rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class Epoch3AdmissionResult:
    admission_id: str
    screening_report_id: str
    question_bank_id: str
    replayed: bool


def _fail(message: str) -> NoReturn:
    raise D02R2Epoch3AdmissionError(message)


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


def _validated_policy_review(
    value: object, *, context: GenerationExecutionContext = E3_CONTEXT
) -> Mapping[str, object]:
    review = _exact(value, _POLICY_REVIEW_KEYS, f"{context.cohort_label} source policy review")
    if (
        review["adult_status"] != ADULT_STATUS
        or review["suspected_minor"] is not False
        or review["real_person_reference"] is not False
        or review["celebrity_resemblance"] is not False
        or review["visual_quality"] != "PASS"
        or review["anti_homogenization"] != "PASS"
        or review["capture_grammar"] != "PASS"
        or review["qa_result"] != "PASS"
        or review["rejection_reason"] is not None
    ):
        _fail(f"{context.cohort_label} source policy review did not satisfy admission")
    return review


def build_epoch3_generation_policy_metadata(
    *,
    generation_receipt: Mapping[str, object],
    normalized_source: NormalizedSource,
    policy_review: Mapping[str, object],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> JsonObject:
    receipt = validate_epoch3_generation_receipt(generation_receipt, context=context)
    ordinal = cast(int, receipt["candidate_ordinal"])
    profile = validate_epoch3_source_policy_profile(
        receipt["source_policy_profile"], ordinal=ordinal, context=context
    )
    review = _validated_policy_review(policy_review, context=context)
    if profile["required_adult_status"] != ADULT_STATUS:
        _fail(f"{context.cohort_label} source policy profile adult status is invalid")
    metadata: JsonObject = {
        "schema_version": context.source_policy_metadata_schema,
        "source_policy_profile": cast(JsonValue, dict(profile)),
        "source_policy_profile_digest": cast(str, profile["profile_digest"]),
        "adult_status": cast(str, review["adult_status"]),
        "suspected_minor": cast(bool, review["suspected_minor"]),
        "real_person_reference": cast(bool, review["real_person_reference"]),
        "celebrity_resemblance": cast(bool, review["celebrity_resemblance"]),
        "visual_quality": cast(str, review["visual_quality"]),
        "anti_homogenization": cast(str, review["anti_homogenization"]),
        "capture_grammar": cast(str, review["capture_grammar"]),
        "source_digest": _digest(normalized_source.sha256, "normalized source digest"),
        "qa_result": cast(str, review["qa_result"]),
        "rejection_reason": cast(str | None, review["rejection_reason"]),
        "metadata_digest": "",
    }
    metadata["metadata_digest"] = mirror_demo_digest(
        context.source_policy_metadata_schema,
        {key: value for key, value in metadata.items() if key != "metadata_digest"},
    )
    return metadata


def validate_epoch3_generation_policy_metadata(
    value: object,
    *,
    generation_receipt: Mapping[str, object],
    normalized_source: NormalizedSource,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> Mapping[str, object]:
    metadata = _exact(
        value,
        _POLICY_METADATA_KEYS,
        f"{context.cohort_label} generation policy metadata",
    )
    review = {key: metadata[key] for key in _POLICY_REVIEW_KEYS}
    expected = build_epoch3_generation_policy_metadata(
        generation_receipt=generation_receipt,
        normalized_source=normalized_source,
        policy_review=review,
        context=context,
    )
    if (
        metadata["schema_version"] != context.source_policy_metadata_schema
        or metadata["source_digest"] != normalized_source.sha256
        or metadata["source_policy_profile_digest"]
        != cast(Mapping[str, object], metadata["source_policy_profile"])["profile_digest"]
        or _digest(metadata["metadata_digest"], "policy metadata digest")
        != expected["metadata_digest"]
        or dict(metadata) != expected
    ):
        _fail(f"{context.cohort_label} generation policy metadata does not replay")
    return metadata


def validate_epoch3_generation_receipt(
    value: object, *, context: GenerationExecutionContext = E3_CONTEXT
) -> Mapping[str, object]:
    try:
        return validate_epoch3_source_generation_receipt(value, context=context)
    except Epoch3GenerationError as error:
        raise D02R2Epoch3AdmissionError(
            f"{context.cohort_label} generation receipt boundary is invalid"
        ) from error


def normalize_epoch3_source_png(
    png_bytes: bytes,
    *,
    generation_receipt: Mapping[str, object],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> NormalizedSource:
    receipt = validate_epoch3_generation_receipt(generation_receipt, context=context)
    if not isinstance(png_bytes, bytes) or not png_bytes:
        _fail("source PNG bytes are empty")
    if (
        hashlib.sha256(png_bytes).hexdigest() != receipt["source_asset_sha256"]
        or len(png_bytes) != receipt["source_asset_byte_size"]
    ):
        _fail("source PNG does not bind to its generation receipt")
    try:
        with Image.open(io.BytesIO(png_bytes)) as image:
            image.load()
            if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                _fail("source bytes are not one static PNG")
            if image.size != (receipt["source_asset_width"], receipt["source_asset_height"]):
                _fail("source PNG dimensions differ from its generation receipt")
            output = io.BytesIO()
            image.convert("RGB").save(
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
        raise D02R2Epoch3AdmissionError("source PNG normalization failed") from exc
    receipt_payload: JsonObject = {
        "schema_version": context.source_normalization_schema,
        "normalization_version": context.source_normalization_version,
        "source_generation_receipt_digest": cast(str, receipt["receipt_digest"]),
        "generation_source_asset_sha256": receipt["source_asset_sha256"],
        "generation_source_asset_byte_size": receipt["source_asset_byte_size"],
        "generation_source_asset_mime_type": "image/png",
        "generation_source_asset_width": cast(int, receipt["source_asset_width"]),
        "generation_source_asset_height": cast(int, receipt["source_asset_height"]),
        "normalized_source_asset_sha256": hashlib.sha256(jpeg_bytes).hexdigest(),
        "normalized_source_asset_byte_size": len(jpeg_bytes),
        "normalized_source_asset_mime_type": "image/jpeg",
        "normalized_source_asset_width": cast(int, receipt["source_asset_width"]),
        "normalized_source_asset_height": cast(int, receipt["source_asset_height"]),
        "jpeg_quality": SOURCE_JPEG_QUALITY,
        "jpeg_subsampling": SOURCE_JPEG_SUBSAMPLING,
        "metadata_policy": "STRIP_ALL",
    }
    receipt_payload["normalization_receipt_digest"] = mirror_demo_digest(
        context.source_normalization_schema, receipt_payload
    )
    return NormalizedSource(
        jpeg_bytes=jpeg_bytes,
        sha256=cast(str, receipt_payload["normalized_source_asset_sha256"]),
        byte_size=len(jpeg_bytes),
        width=cast(int, receipt["source_asset_width"]),
        height=cast(int, receipt["source_asset_height"]),
        receipt=receipt_payload,
    )


def build_epoch3_source_authority(
    *,
    generation_receipt: Mapping[str, object],
    normalized_source: NormalizedSource,
    source_asset_id: str,
    policy_review: Mapping[str, object],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> JsonObject:
    receipt = validate_epoch3_generation_receipt(generation_receipt, context=context)
    _id(source_asset_id, "normalized source Asset ID")
    normalization_digest = _digest(
        normalized_source.receipt.get("normalization_receipt_digest"),
        "normalization receipt digest",
    )
    if (
        normalized_source.receipt.get("schema_version") != context.source_normalization_schema
        or normalized_source.receipt.get("normalization_version")
        != context.source_normalization_version
    ):
        _fail(f"{context.cohort_label} normalization receipt boundary is invalid")
    authority: JsonObject = {
        "schema_version": context.source_authority_schema,
        "source_ordinal": cast(int, receipt["candidate_ordinal"]),
        "execution_contract_digest": cast(str, receipt["execution_contract_digest"]),
        "evidence_root_id": context.root_id,
        "root_name_receipt_digest": cast(str, receipt["root_name_receipt_digest"]),
        "generation_preregistration_digest": cast(
            str, receipt["generation_preregistration_digest"]
        ),
        "source_allocation_manifest_digest": cast(
            str, receipt["source_allocation_manifest_digest"]
        ),
        "source_producer_dispatch_digest": cast(str, receipt["source_producer_dispatch_digest"]),
        "source_output_id": cast(str, receipt["source_output_id"]),
        "source_asset_id": source_asset_id,
        "source_asset_sha256": normalized_source.sha256,
        "source_asset_byte_size": normalized_source.byte_size,
        "source_asset_mime_type": "image/jpeg",
        "source_asset_width": normalized_source.width,
        "source_asset_height": normalized_source.height,
        "generation_source_asset_sha256": cast(str, receipt["source_asset_sha256"]),
        "generation_source_asset_byte_size": cast(int, receipt["source_asset_byte_size"]),
        "generation_source_asset_mime_type": "image/png",
        "generation_source_asset_width": cast(int, receipt["source_asset_width"]),
        "generation_source_asset_height": cast(int, receipt["source_asset_height"]),
        "source_normalization_receipt_digest": normalization_digest,
        "source_generation_receipt_digest": cast(str, receipt["receipt_digest"]),
        "output_name_receipt_digest": cast(str, receipt["output_name_receipt_digest"]),
        "output_seal_receipt_digest": cast(str, receipt["output_seal_receipt_digest"]),
        "registry_commit_receipt_digest": cast(str, receipt["registry_commit_receipt_digest"]),
        "generation_capability_authority_digest": cast(
            str, receipt["generation_capability_authority_digest"]
        ),
        "generation_request_policy_digest": cast(str, receipt["generation_request_policy_digest"]),
        "generation_request_digest": cast(str, receipt["generation_request_policy_digest"]),
        "source_provenance_digest": cast(str, receipt["generation_result_provenance_digest"]),
        "source_provenance_output_id": cast(str, receipt["source_provenance_output_id"]),
        "source_provenance_name_receipt_digest": cast(
            str, receipt["source_provenance_name_receipt_digest"]
        ),
        "source_provenance_seal_receipt_digest": cast(
            str, receipt["source_provenance_seal_receipt_digest"]
        ),
        "source_provenance_registry_commit_receipt_digest": cast(
            str, receipt["source_provenance_registry_commit_receipt_digest"]
        ),
        "synthetic_only_attested": True,
        "real_person_reference_used": False,
        "generation_policy_metadata": build_epoch3_generation_policy_metadata(
            generation_receipt=receipt,
            normalized_source=normalized_source,
            policy_review=policy_review,
            context=context,
        ),
        "authority_kind": r2.R2_SOURCE_AUTHORITY_KIND,
    }
    authority["authority_digest"] = mirror_demo_digest(context.source_authority_schema, authority)
    return authority


def validate_epoch3_source_authority(
    value: object,
    *,
    generation_receipt: Mapping[str, object],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> Mapping[str, object]:
    authority = _exact(value, _AUTHORITY_KEYS, f"{context.cohort_label} source authority")
    receipt = validate_epoch3_generation_receipt(generation_receipt, context=context)
    if (
        authority["schema_version"] != context.source_authority_schema
        or authority["evidence_root_id"] != context.root_id
        or authority["authority_kind"] != r2.R2_SOURCE_AUTHORITY_KIND
        or authority["generation_request_digest"] != authority["generation_request_policy_digest"]
        or authority["source_asset_mime_type"] != "image/jpeg"
        or authority["generation_source_asset_mime_type"] != "image/png"
    ):
        _fail(f"{context.cohort_label} source authority boundary is invalid")
    normalized = NormalizedSource(
        jpeg_bytes=b"",
        sha256=cast(str, authority["source_asset_sha256"]),
        byte_size=cast(int, authority["source_asset_byte_size"]),
        width=cast(int, authority["source_asset_width"]),
        height=cast(int, authority["source_asset_height"]),
        receipt={
            "schema_version": context.source_normalization_schema,
            "normalization_version": context.source_normalization_version,
            "normalization_receipt_digest": cast(
                str, authority["source_normalization_receipt_digest"]
            ),
        },
    )
    metadata = validate_epoch3_generation_policy_metadata(
        authority["generation_policy_metadata"],
        generation_receipt=receipt,
        normalized_source=normalized,
        context=context,
    )
    expected = build_epoch3_source_authority(
        generation_receipt=receipt,
        normalized_source=normalized,
        source_asset_id=cast(str, authority["source_asset_id"]),
        policy_review={key: metadata[key] for key in _POLICY_REVIEW_KEYS},
        context=context,
    )
    if dict(authority) != expected:
        _fail(f"{context.cohort_label} source authority does not replay")
    return authority


def build_epoch3_source_qa_snapshot(
    *,
    source_authority: Mapping[str, object],
    generation_receipt: Mapping[str, object],
    qa_policy_digest: str,
    decode_record_digest: str,
    ordered_review_decision_digests: Sequence[str],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> JsonObject:
    authority = validate_epoch3_source_authority(
        source_authority, generation_receipt=generation_receipt, context=context
    )
    _digest(qa_policy_digest, "QA policy digest")
    _digest(decode_record_digest, "decode record digest")
    if len(ordered_review_decision_digests) != 6:
        _fail(f"{context.cohort_label} source QA requires six ordered review decisions")
    for item in ordered_review_decision_digests:
        _digest(item, "review decision digest")
    qa: JsonObject = {
        "schema_version": context.source_qa_schema,
        **{
            key: cast(JsonValue, item)
            for key, item in authority.items()
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
        "source_authority_digest": cast(str, authority["authority_digest"]),
        "qa_policy_digest": qa_policy_digest,
        "decode_record_digest": decode_record_digest,
        "ordered_review_decision_digests": list(ordered_review_decision_digests),
        "adult_synthetic_attested": True,
        "qa_state": "PASSED",
    }
    qa["source_qa_snapshot_digest"] = mirror_demo_digest(context.source_qa_schema, qa)
    return qa


def validate_epoch3_source_qa_snapshot(
    value: object,
    *,
    source_authority: Mapping[str, object],
    generation_receipt: Mapping[str, object],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> Mapping[str, object]:
    qa = _exact(value, _QA_KEYS, f"{context.cohort_label} source QA snapshot")
    authority = validate_epoch3_source_authority(
        source_authority, generation_receipt=generation_receipt, context=context
    )
    if qa["schema_version"] != context.source_qa_schema or qa["qa_state"] != "PASSED":
        _fail(f"{context.cohort_label} source QA state is invalid")
    expected = build_epoch3_source_qa_snapshot(
        source_authority=authority,
        generation_receipt=generation_receipt,
        qa_policy_digest=_digest(qa["qa_policy_digest"], "QA policy digest"),
        decode_record_digest=_digest(qa["decode_record_digest"], "decode record digest"),
        ordered_review_decision_digests=cast(Sequence[str], qa["ordered_review_decision_digests"]),
        context=context,
    )
    if dict(qa) != expected:
        _fail(f"{context.cohort_label} source QA snapshot does not replay")
    return qa


def build_epoch3_source_record(
    *,
    source_authority: Mapping[str, object],
    source_qa_snapshot: Mapping[str, object],
    generation_receipt: Mapping[str, object],
    created_at: str,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> JsonObject:
    authority = validate_epoch3_source_authority(
        source_authority, generation_receipt=generation_receipt, context=context
    )
    qa = validate_epoch3_source_qa_snapshot(
        source_qa_snapshot,
        source_authority=authority,
        generation_receipt=generation_receipt,
        context=context,
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
            field: cast(JsonValue, item)
            for field, item in authority.items()
            if field not in {"schema_version", "authority_kind", "authority_digest"}
        },
        "source_authority_digest": cast(str, authority["authority_digest"]),
        "source_authority_key": key,
        "source_qa_snapshot_digest": cast(str, qa["source_qa_snapshot_digest"]),
        "adult_synthetic_attested": True,
        "authority_state": "PRINCIPAL_ACCEPTED",
        "execution_epoch": context.execution_epoch,
        "producer_task_id": context.producer_task_id,
        "dispatch_epoch": context.dispatch_epoch,
    }
    content_digest = mirror_demo_digest(context.source_record_schema, canonical)
    preimage: JsonObject = {
        "execution_contract_digest": cast(str, canonical["execution_contract_digest"]),
        "evidence_root_id": context.root_id,
        "root_name_receipt_digest": cast(str, canonical["root_name_receipt_digest"]),
        "generation_preregistration_digest": cast(
            str, canonical["generation_preregistration_digest"]
        ),
        "source_allocation_manifest_digest": cast(
            str, canonical["source_allocation_manifest_digest"]
        ),
        "source_producer_dispatch_digest": cast(str, canonical["source_producer_dispatch_digest"]),
        "source_ordinal": cast(int, canonical["source_ordinal"]),
        "source_output_id": cast(str, canonical["source_output_id"]),
        "source_authority_key": key,
        "source_authority_digest": cast(str, authority["authority_digest"]),
        "source_qa_snapshot_digest": cast(str, qa["source_qa_snapshot_digest"]),
        "content_digest": content_digest,
        "generation_request_digest": cast(str, canonical["generation_request_digest"]),
        "execution_epoch": context.execution_epoch,
        "producer_task_id": context.producer_task_id,
        "dispatch_epoch": context.dispatch_epoch,
        "generation_source_asset_sha256": cast(str, canonical["generation_source_asset_sha256"]),
        "generation_source_asset_byte_size": cast(
            int, canonical["generation_source_asset_byte_size"]
        ),
        "generation_source_asset_mime_type": "image/png",
        "generation_source_asset_width": cast(int, canonical["generation_source_asset_width"]),
        "generation_source_asset_height": cast(int, canonical["generation_source_asset_height"]),
        "source_normalization_receipt_digest": cast(
            str, canonical["source_normalization_receipt_digest"]
        ),
    }
    return {
        "id": mirror_demo_digest(context.source_record_id_domain, preimage)[:32],
        "schema_version": context.source_record_schema,
        "canonical_payload": canonical,
        "content_digest": content_digest,
        "created_at": created_at,
        **canonical,
    }


def validate_epoch3_source_record(
    value: object,
    *,
    source_authority: Mapping[str, object],
    source_qa_snapshot: Mapping[str, object],
    generation_receipt: Mapping[str, object],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail("Epoch 03 source authority record is invalid")
    expected = build_epoch3_source_record(
        source_authority=source_authority,
        source_qa_snapshot=source_qa_snapshot,
        generation_receipt=generation_receipt,
        created_at=cast(str, value.get("created_at")),
        context=context,
    )
    if dict(value) != expected:
        _fail("Epoch 03 source authority record does not replay")
    return value


def validate_epoch3_admission_packet(
    value: object, *, context: GenerationExecutionContext = E3_CONTEXT
) -> None:
    packet = _exact(value, _PACKET_KEYS, f"{context.cohort_label} admission packet")
    receipt = validate_epoch3_generation_receipt(packet["generation_receipt"], context=context)
    authority = validate_epoch3_source_authority(
        packet["source_authority"], generation_receipt=receipt, context=context
    )
    qa = validate_epoch3_source_qa_snapshot(
        packet["source_qa_snapshot"],
        source_authority=authority,
        generation_receipt=receipt,
        context=context,
    )
    row = validate_epoch3_source_record(
        packet["supporting_row"],
        source_authority=authority,
        source_qa_snapshot=qa,
        generation_receipt=receipt,
        context=context,
    )
    facts = r2.validate_r2_facts(packet["facts"])
    for fact_key, row_key in (
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
        if facts[fact_key] != row[row_key]:
            _fail(f"{context.cohort_label} facts/source equality is invalid for {fact_key}")
    legacy_row = {key: item for key, item in row.items() if key not in _E3_RECORD_ONLY_FIELDS}
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


def _validate_bundle(
    bundle: Epoch3AdmissionBundle, *, context: GenerationExecutionContext = E3_CONTEXT
) -> dict[str, JsonValue]:
    if len(bundle.source_packets) != 4:
        _fail(f"{context.cohort_label} admission requires four source packets")
    for packet in bundle.source_packets:
        validate_epoch3_admission_packet(packet, context=context)
    policy_metadata = [
        cast(
            Mapping[str, object],
            cast(Mapping[str, object], packet["supporting_row"])["generation_policy_metadata"],
        )
        for packet in bundle.source_packets
    ]
    age_bands = [
        cast(
            str,
            cast(Mapping[str, object], item["source_policy_profile"])["declared_age_band"],
        )
        for item in policy_metadata
    ]
    identity_families = {
        cast(
            str,
            cast(Mapping[str, object], item["source_policy_profile"])["base_identity_family"],
        )
        for item in policy_metadata
    }
    if (
        age_bands.count("ADULT_20_25") != 3
        or age_bands.count("ADULT_18_19") != 1
        or len(identity_families) != 4
    ):
        _fail(f"{context.cohort_label} source policy distribution is invalid")
    try:
        report = r2.validate_r2_report_row(bundle.report_row, source_packets=bundle.source_packets)
        bank = r2.validate_r2_question_bank_row(
            bundle.question_bank_row,
            report=report,
            source_packets=bundle.source_packets,
        )
        if len(bundle.question_pair_rows) != 16:
            _fail(f"{context.cohort_label} admission requires sixteen QuestionPairs")
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
            _fail(f"{context.cohort_label} admission requires 52 Assets and 48 AssetVariants")
        compatibility_bundle = epoch2.Epoch2AdmissionBundle(
            source_packets=bundle.source_packets,
            asset_rows=bundle.asset_rows,
            asset_variant_rows=bundle.asset_variant_rows,
            report_row=bundle.report_row,
            question_bank_row=bundle.question_bank_row,
            question_pair_rows=bundle.question_pair_rows,
        )
        asset_authorities, variant_authorities = epoch2._validate_persistence_bindings(
            bundle=compatibility_bundle,
            report=report,
            pairs=pairs,
        )
    except epoch2.D02R2Epoch2AdmissionError as error:
        raise D02R2Epoch3AdmissionError(
            f"{context.cohort_label} persistence graph failed replay"
        ) from error
    except (KeyError, TypeError, ValueError) as error:
        raise D02R2Epoch3AdmissionError(
            f"{context.cohort_label} Report/Bank/Pair graph failed replay"
        ) from error

    asset_ids = {cast(str, item["id"]) for item in asset_authorities}
    source_ids = {
        cast(
            str,
            cast(Mapping[str, object], packet["supporting_row"])["source_asset_id"],
        )
        for packet in bundle.source_packets
    }
    result_ids = {
        cast(str, pair[side]) for pair in pairs for side in ("left_asset_id", "right_asset_id")
    }
    if len(source_ids) != 4 or len(result_ids) != 32 or not (source_ids | result_ids) <= asset_ids:
        _fail(f"{context.cohort_label} selected image graph is incomplete")
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
        "asset_authorities": cast(JsonValue, asset_authorities),
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


def validate_epoch3_admission_bundle(
    bundle: Epoch3AdmissionBundle, *, context: GenerationExecutionContext = E3_CONTEXT
) -> None:
    _validate_bundle(bundle, context=context)


def _admission_values(
    *,
    bundle: Epoch3AdmissionBundle,
    idempotency_key_hash_value: str,
    request_digest: str,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> dict[str, object]:
    report = bundle.report_row
    bank = bundle.question_bank_row
    canonical: dict[str, object] = {
        "idempotency_key_hash": idempotency_key_hash_value,
        "request_digest": request_digest,
        "execution_epoch": context.execution_epoch,
        "evidence_root_id": context.root_id,
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
        context.admission_id_domain,
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
        "schema_version": context.admission_schema,
        "canonical_payload": canonical,
        "content_digest": mirror_demo_digest(
            context.admission_schema, cast(Mapping[str, JsonValue], canonical)
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


class D02R2Epoch3AdmissionCoordinator:
    """Claim idempotency first, then atomically persist the complete E3 graph."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        context: GenerationExecutionContext = E3_CONTEXT,
    ) -> None:
        self._session_factory = session_factory
        self._context = context

    async def admit(
        self, *, idempotency_key: str, bundle: Epoch3AdmissionBundle
    ) -> Epoch3AdmissionResult:
        semantic_request = _validate_bundle(bundle, context=self._context)
        key_hash = idempotency_key_hash(idempotency_key)
        request_digest = semantic_request_digest(cast(Mapping[str, Any], semantic_request))
        values = _admission_values(
            bundle=bundle,
            idempotency_key_hash_value=key_hash,
            request_digest=request_digest,
            context=self._context,
        )
        async with self._session_factory() as session:
            async with session.begin():
                inserted_id = await session.scalar(
                    insert(DemoD02R2Epoch2Admission)
                    .values(**values)
                    .on_conflict_do_nothing()
                    .returning(DemoD02R2Epoch2Admission.id)
                )
                if inserted_id is None:
                    existing = await session.scalar(
                        select(DemoD02R2Epoch2Admission).where(
                            DemoD02R2Epoch2Admission.idempotency_key_hash == key_hash
                        )
                    )
                    if existing is None:
                        raise D02R2Epoch3AuthorityCorruption(
                            "idempotency winner was not reloadable"
                        )
                    if existing.request_digest != request_digest:
                        raise D02R2Epoch3PayloadConflict()
                    await self._verify_existing(session, existing)
                    return Epoch3AdmissionResult(
                        admission_id=existing.id,
                        screening_report_id=existing.screening_report_id,
                        question_bank_id=existing.question_bank_id,
                        replayed=True,
                    )

                compatibility_bundle = epoch2.Epoch2AdmissionBundle(
                    source_packets=bundle.source_packets,
                    asset_rows=bundle.asset_rows,
                    asset_variant_rows=bundle.asset_variant_rows,
                    report_row=bundle.report_row,
                    question_bank_row=bundle.question_bank_row,
                    question_pair_rows=bundle.question_pair_rows,
                )
                try:
                    await epoch2._insert_or_replay_asset_authority(session, compatibility_bundle)
                except epoch2.D02R2Epoch2AdmissionError as error:
                    raise D02R2Epoch3AuthorityCorruption(
                        f"{self._context.cohort_label} Asset authority failed replay"
                    ) from error
                session.add_all(
                    DemoD02R2SourceAuthority(
                        **_orm_values(
                            cast(
                                Mapping[str, object],
                                packet["supporting_row"],
                            )
                        )
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
                    raise D02R2Epoch3AuthorityCorruption(
                        "new admission binding disappeared before commit"
                    )
                return Epoch3AdmissionResult(
                    admission_id=admission.id,
                    screening_report_id=admission.screening_report_id,
                    question_bank_id=admission.question_bank_id,
                    replayed=False,
                )

    async def _verify_existing(
        self,
        session: AsyncSession,
        admission: DemoD02R2Epoch2Admission,
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
            raise D02R2Epoch3AuthorityCorruption(
                f"persisted {self._context.cohort_label} admission graph does not replay"
            )


def canonical_epoch3_admission_bytes(value: Mapping[str, object]) -> bytes:
    try:
        decoded = json.loads(canonical_json_bytes(value))
    except (TypeError, ValueError) as exc:
        raise D02R2Epoch3AdmissionError("admission payload is not canonical JSON") from exc
    return canonical_json_bytes(cast(Mapping[str, Any], decoded))
