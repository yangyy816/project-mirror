"""Pure, fail-closed D02-R2 source-admission authority.

This module deliberately accepts only caller supplied structural payloads.  It
does not resolve registry locators, files, image bytes, databases, Providers,
or private evidence.  The caller must complete this replay before opening a
database transaction; PostgreSQL then independently verifies the public
supporting-row projection.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final, NoReturn, cast

from mirror_api import demo_d02_authority as legacy
from mirror_api.demo_measurement_quality import (
    canonical_json_bytes,
    mirror_demo_digest,
)

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

R2_GENERATION_RECEIPT_SCHEMA: Final = "mirror.demo/D02R2SourceGenerationReceipt/v1"
R2_SOURCE_AUTHORITY_SCHEMA: Final = "mirror.demo/D02R2SourceAuthority/v1"
R2_SOURCE_QA_SCHEMA: Final = "mirror.demo/D02R2SourceQASnapshot/v1"
R2_SOURCE_AUTHORITY_RECORD_SCHEMA: Final = "mirror.demo/D02R2SourceAuthorityRecord/v1"
R2_FACTS_SCHEMA: Final = "mirror.demo/D02R2SyntheticIdentityFacts/v1"
R2_IDENTITY_SCHEMA: Final = "mirror.demo/DemoSyntheticIdentity/v4"
R2_SOURCE_ENTRY_SCHEMA: Final = "mirror.demo/D02SourceAuthorityManifestEntry/v4"
R2_SOURCE_MANIFEST_SCHEMA: Final = "mirror.demo/D02SourceAuthorityManifest/v2"
R2_SOURCE_AUTHORITY_KIND: Final = "DEMO_R2_GENERATED_SOURCE"
R2_SOURCE_KEY_DOMAIN: Final = "mirror.demo/D02R2SourceAuthorityKey/v1"
R2_RECORD_ID_DOMAIN: Final = "mirror.demo/D02R2SourceAuthorityRecordId/v1"
R2_IDENTITY_ID_DOMAIN: Final = "mirror.demo/DemoSyntheticIdentityAdmissionEventId/v3"
R2_NOT_APPLICABLE_STATUS: Final = "NOT_APPLICABLE_DEMO_R2_GENERATED_SOURCE"
R2_EVIDENCE_ROOT_ID: Final = "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"
R2_ADMISSION_CONFIG_SCHEMA: Final = "mirror.demo/D02R2SyntheticAdmissionConfiguration/v1"

_DIGEST = re.compile(r"[0-9a-f]{64}$")
_ID = re.compile(r"[0-9a-f]{32}$")
_OUTPUT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PHASH_HEX = re.compile(r"[0-9a-f]{16}$")

R2_ADMISSION_CONFIG_PAYLOAD: Final[dict[str, JsonValue]] = {
    "track": "DEMO_PROTOTYPE",
    "source_mode": R2_SOURCE_AUTHORITY_KIND,
    "identity_schema_version": R2_IDENTITY_SCHEMA,
    "source_authority_record_schema_version": R2_SOURCE_AUTHORITY_RECORD_SCHEMA,
    "generation_preregistration_schema_version": (
        "mirror.demo/D02R2SourceGenerationPreregistrationAuthority/v1"
    ),
    "source_allocation_manifest_schema_version": "mirror.demo/D02R2SourceAllocationManifest/v1",
    "source_producer_dispatch_schema_version": "mirror.demo/D02R2SourceProducerDispatchReceipt/v1",
    "source_generation_receipt_schema_version": R2_GENERATION_RECEIPT_SCHEMA,
    "source_authority_key_domain": R2_SOURCE_KEY_DOMAIN,
    "source_facts_schema_version": R2_FACTS_SCHEMA,
    "source_qa_schema_version": R2_SOURCE_QA_SCHEMA,
    "source_manifest_entry_schema_version": R2_SOURCE_ENTRY_SCHEMA,
    "source_manifest_schema_version": R2_SOURCE_MANIFEST_SCHEMA,
    "source_output_id_contract": "OPAQUE_PRIVATE_OUTPUT_REGISTRY_ID_V1",
    "source_receipt_binding_required": True,
    "root_name_receipt_binding_required": True,
    "registry_commit_binding_required": True,
    "adult_synthetic_attestation_required": True,
    "synthetic_only_attestation_required": True,
    "real_person_reference_forbidden": True,
    "original_formal_identity_id_status": R2_NOT_APPLICABLE_STATUS,
    "public_internet_egress_during_core_execution": "DENIED",
    "production_release": "NOT_AUTHORIZED",
}
R2_ADMISSION_CONFIG_DIGEST: Final = mirror_demo_digest(
    R2_ADMISSION_CONFIG_SCHEMA, R2_ADMISSION_CONFIG_PAYLOAD
)

_GENERATION_RECEIPT_FIELDS: Final = {
    "schema_version",
    "candidate_ordinal",
    "producer_task_id",
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
_SOURCE_AUTHORITY_FIELDS: Final = {
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
    "source_generation_receipt_digest",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
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
_QA_FIELDS: Final = {
    "schema_version",
    "source_ordinal",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_authority_key",
    "source_authority_digest",
    "source_output_id",
    "source_asset_id",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "source_generation_receipt_digest",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "source_provenance_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "source_provenance_seal_receipt_digest",
    "source_provenance_registry_commit_receipt_digest",
    "qa_policy_digest",
    "decode_record_digest",
    "ordered_review_decision_digests",
    "adult_synthetic_attested",
    "synthetic_only_attested",
    "real_person_reference_used",
    "qa_state",
    "source_qa_snapshot_digest",
}
_RECORD_FIELDS: Final = {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "created_at",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_ordinal",
    "source_output_id",
    "source_asset_id",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "source_generation_receipt_digest",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "source_provenance_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "source_provenance_seal_receipt_digest",
    "source_provenance_registry_commit_receipt_digest",
    "source_authority_digest",
    "source_authority_key",
    "source_qa_snapshot_digest",
    "adult_synthetic_attested",
    "synthetic_only_attested",
    "real_person_reference_used",
    "authority_state",
}


class D02R2AuthorityError(ValueError):
    """A structural R2 admission assertion did not replay exactly."""


def _fail(message: str) -> NoReturn:
    raise D02R2AuthorityError(message)


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _fail(f"{label} keys are not exact")
    return dict(value)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        _fail(f"{label} is not a lowercase SHA-256 digest")
    return value


def _require_mandatory_digest_leaves(
    value: object, mandatory_keys: tuple[str, ...], label: str
) -> None:
    """Reject missing, null, non-string, or non-canonical authority digests."""

    if not isinstance(value, Mapping):
        _fail(f"{label} mandatory digest leaf container is invalid")
    for key in mandatory_keys:
        if key not in value:
            _fail(f"{label} mandatory digest leaf is missing: {key}")
        try:
            _digest(value[key], f"{label} mandatory digest leaf {key}")
        except D02R2AuthorityError as error:
            raise D02R2AuthorityError(f"{label} mandatory digest leaf is invalid: {key}") from error


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        _fail(f"{label} is not a lowercase 32-hex ID")
    return value


def _opaque_output_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _OUTPUT_ID.fullmatch(value) is None:
        _fail(f"{label} is not an opaque output ID")
    return value


def _bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        _fail(f"{label} must be a JSON boolean")
    return value


def _digest_payload(schema: str, payload: Mapping[str, object], digest_key: str) -> None:
    if payload[digest_key] != mirror_demo_digest(
        schema, cast(dict[str, JsonValue], {k: v for k, v in payload.items() if k != digest_key})
    ):
        _fail(f"{schema} digest does not replay")


def _asset_fields(value: Mapping[str, object]) -> None:
    _id(value["source_asset_id"], "source asset ID")
    _digest(value["source_asset_sha256"], "source asset checksum")
    if (
        type(value["source_asset_byte_size"]) is not int
        or int(value["source_asset_byte_size"]) < 1
        or type(value["source_asset_width"]) is not int
        or int(value["source_asset_width"]) < 1
        or type(value["source_asset_height"]) is not int
        or int(value["source_asset_height"]) < 1
        or value["source_asset_mime_type"] != "image/jpeg"
    ):
        _fail("source Asset fields are invalid")


def derive_r2_source_authority_key(
    *,
    source_output_id: str,
    source_asset_id: str,
    source_asset_sha256: str,
    source_generation_receipt_digest: str,
    source_authority_digest: str,
) -> str:
    _opaque_output_id(source_output_id, "source output ID")
    _id(source_asset_id, "source Asset ID")
    for value, label in (
        (source_asset_sha256, "source Asset checksum"),
        (source_generation_receipt_digest, "generation receipt"),
        (source_authority_digest, "source authority"),
    ):
        _digest(value, label)
    return mirror_demo_digest(
        R2_SOURCE_KEY_DOMAIN,
        {
            "authority_kind": R2_SOURCE_AUTHORITY_KIND,
            "source_output_id": source_output_id,
            "source_asset_id": source_asset_id,
            "source_asset_sha256": source_asset_sha256,
            "source_generation_receipt_digest": source_generation_receipt_digest,
            "authority_digest": source_authority_digest,
        },
    )


def validate_r2_generation_receipt(value: object) -> Mapping[str, Any]:
    receipt = _exact(value, _GENERATION_RECEIPT_FIELDS, "R2 generation receipt")
    if receipt["schema_version"] != R2_GENERATION_RECEIPT_SCHEMA:
        _fail("R2 generation receipt schema is invalid")
    if type(receipt["candidate_ordinal"]) is not int or receipt["candidate_ordinal"] not in {
        1,
        2,
        3,
        4,
    }:
        _fail("R2 generation ordinal is invalid")
    if type(receipt["dispatch_epoch"]) is not int or receipt["dispatch_epoch"] != 1:
        _fail("R2 generation dispatch epoch is invalid")
    if not isinstance(receipt["producer_task_id"], str) or not receipt["producer_task_id"]:
        _fail("R2 generation producer task is invalid")
    if receipt["evidence_root_id"] != R2_EVIDENCE_ROOT_ID:
        _fail("R2 generation evidence root is invalid")
    for key in (
        "execution_contract_digest",
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "generation_request_policy_digest",
        "generation_result_provenance_digest",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
        "source_asset_sha256",
        "receipt_digest",
    ):
        _digest(receipt[key], key)
    _opaque_output_id(receipt["source_output_id"], "R2 source output ID")
    _opaque_output_id(receipt["source_provenance_output_id"], "R2 provenance output ID")
    if (
        receipt["synthetic_only_attested"] is not True
        or receipt["real_person_reference_used"] is not False
    ):
        _fail("R2 generation attestations are invalid")
    _asset_fields({"source_asset_id": "0" * 32, **receipt})
    _digest_payload(R2_GENERATION_RECEIPT_SCHEMA, receipt, "receipt_digest")
    return receipt


def validate_r2_source_authority(
    value: object, *, receipt: Mapping[str, object]
) -> Mapping[str, Any]:
    authority = _exact(value, _SOURCE_AUTHORITY_FIELDS, "R2 source authority")
    generation = validate_r2_generation_receipt(receipt)
    if (
        authority["schema_version"] != R2_SOURCE_AUTHORITY_SCHEMA
        or authority["authority_kind"] != R2_SOURCE_AUTHORITY_KIND
    ):
        _fail("R2 source authority schema or kind is invalid")
    if authority["source_ordinal"] != generation["candidate_ordinal"]:
        _fail("R2 source authority ordinal does not equal generation receipt")
    for key in (
        "execution_contract_digest",
        "evidence_root_id",
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "source_output_id",
        "source_asset_sha256",
        "source_asset_byte_size",
        "source_asset_mime_type",
        "source_asset_width",
        "source_asset_height",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "generation_request_policy_digest",
        "source_provenance_output_id",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
        "synthetic_only_attested",
        "real_person_reference_used",
    ):
        if authority[key] != generation[key]:
            _fail(f"R2 authority/generation equality is invalid for {key}")
    if authority["source_generation_receipt_digest"] != generation["receipt_digest"]:
        _fail("R2 authority generation-receipt binding is invalid")
    _id(authority["source_asset_id"], "R2 source Asset ID")
    for key in ("source_provenance_digest", "authority_digest"):
        _digest(authority[key], key)
    if authority["source_provenance_digest"] != generation["generation_result_provenance_digest"]:
        _fail("R2 authority provenance binding is invalid")
    _digest_payload(R2_SOURCE_AUTHORITY_SCHEMA, authority, "authority_digest")
    return authority


def validate_r2_source_qa_snapshot(
    value: object, *, authority: Mapping[str, object], receipt: Mapping[str, object]
) -> Mapping[str, Any]:
    qa = _exact(value, _QA_FIELDS, "R2 source QA snapshot")
    source_authority = validate_r2_source_authority(authority, receipt=receipt)
    if qa["schema_version"] != R2_SOURCE_QA_SCHEMA or qa["qa_state"] != "PASSED":
        _fail("R2 source QA schema or state is invalid")
    source_key = derive_r2_source_authority_key(
        source_output_id=cast(str, source_authority["source_output_id"]),
        source_asset_id=cast(str, source_authority["source_asset_id"]),
        source_asset_sha256=cast(str, source_authority["source_asset_sha256"]),
        source_generation_receipt_digest=cast(
            str, source_authority["source_generation_receipt_digest"]
        ),
        source_authority_digest=cast(str, source_authority["authority_digest"]),
    )
    copies = {
        "source_ordinal": "source_ordinal",
        "execution_contract_digest": "execution_contract_digest",
        "evidence_root_id": "evidence_root_id",
        "root_name_receipt_digest": "root_name_receipt_digest",
        "generation_preregistration_digest": "generation_preregistration_digest",
        "source_allocation_manifest_digest": "source_allocation_manifest_digest",
        "source_producer_dispatch_digest": "source_producer_dispatch_digest",
        "source_output_id": "source_output_id",
        "source_asset_id": "source_asset_id",
        "source_asset_sha256": "source_asset_sha256",
        "source_asset_byte_size": "source_asset_byte_size",
        "source_asset_mime_type": "source_asset_mime_type",
        "source_asset_width": "source_asset_width",
        "source_asset_height": "source_asset_height",
        "source_generation_receipt_digest": "source_generation_receipt_digest",
        "output_name_receipt_digest": "output_name_receipt_digest",
        "output_seal_receipt_digest": "output_seal_receipt_digest",
        "registry_commit_receipt_digest": "registry_commit_receipt_digest",
        "generation_capability_authority_digest": "generation_capability_authority_digest",
        "generation_request_policy_digest": "generation_request_policy_digest",
        "source_provenance_digest": "source_provenance_digest",
        "source_provenance_output_id": "source_provenance_output_id",
        "source_provenance_name_receipt_digest": "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest": "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest": (
            "source_provenance_registry_commit_receipt_digest"
        ),
        "synthetic_only_attested": "synthetic_only_attested",
        "real_person_reference_used": "real_person_reference_used",
    }
    if any(qa[target] != source_authority[source] for target, source in copies.items()):
        _fail("R2 QA/source authority copied fields differ")
    if (
        qa["source_authority_key"] != source_key
        or qa["source_authority_digest"] != source_authority["authority_digest"]
    ):
        _fail("R2 QA source key or authority binding is invalid")
    reviews = qa["ordered_review_decision_digests"]
    if not isinstance(reviews, list) or len(reviews) != 6:
        _fail("R2 QA requires six ordered Principal reviews")
    for digest in reviews:
        _digest(digest, "R2 QA review digest")
    for key in ("qa_policy_digest", "decode_record_digest", "source_qa_snapshot_digest"):
        _digest(qa[key], key)
    if qa["adult_synthetic_attested"] is not True:
        _fail("R2 QA adult attestation is invalid")
    _digest_payload(R2_SOURCE_QA_SCHEMA, qa, "source_qa_snapshot_digest")
    return qa


def validate_r2_source_authority_record(
    value: object,
    *,
    authority: Mapping[str, object],
    qa_snapshot: Mapping[str, object],
    receipt: Mapping[str, object],
) -> Mapping[str, Any]:
    row = _exact(value, _RECORD_FIELDS, "R2 source authority record")
    source_authority = validate_r2_source_authority(authority, receipt=receipt)
    qa = validate_r2_source_qa_snapshot(qa_snapshot, authority=source_authority, receipt=receipt)
    if (
        row["schema_version"] != R2_SOURCE_AUTHORITY_RECORD_SCHEMA
        or row["authority_state"] != "PRINCIPAL_ACCEPTED"
    ):
        _fail("R2 supporting row schema or state is invalid")
    canonical = {
        key: row[key]
        for key in _RECORD_FIELDS
        - {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    if row["canonical_payload"] != canonical or row["content_digest"] != mirror_demo_digest(
        R2_SOURCE_AUTHORITY_RECORD_SCHEMA, canonical
    ):
        _fail("R2 supporting row canonical payload is invalid")
    copies = {
        "execution_contract_digest": "execution_contract_digest",
        "evidence_root_id": "evidence_root_id",
        "root_name_receipt_digest": "root_name_receipt_digest",
        "generation_preregistration_digest": "generation_preregistration_digest",
        "source_allocation_manifest_digest": "source_allocation_manifest_digest",
        "source_producer_dispatch_digest": "source_producer_dispatch_digest",
        "source_ordinal": "source_ordinal",
        "source_output_id": "source_output_id",
        "source_asset_id": "source_asset_id",
        "source_asset_sha256": "source_asset_sha256",
        "source_asset_byte_size": "source_asset_byte_size",
        "source_asset_mime_type": "source_asset_mime_type",
        "source_asset_width": "source_asset_width",
        "source_asset_height": "source_asset_height",
        "output_name_receipt_digest": "output_name_receipt_digest",
        "output_seal_receipt_digest": "output_seal_receipt_digest",
        "registry_commit_receipt_digest": "registry_commit_receipt_digest",
        "generation_capability_authority_digest": "generation_capability_authority_digest",
        "generation_request_policy_digest": "generation_request_policy_digest",
        "source_provenance_digest": "source_provenance_digest",
        "source_provenance_output_id": "source_provenance_output_id",
        "source_provenance_name_receipt_digest": "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest": "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest": (
            "source_provenance_registry_commit_receipt_digest"
        ),
        "source_authority_digest": "authority_digest",
        "synthetic_only_attested": "synthetic_only_attested",
        "real_person_reference_used": "real_person_reference_used",
    }
    if any(row[target] != source_authority[source] for target, source in copies.items()):
        _fail("R2 supporting row/source authority copied fields differ")
    if (
        row["source_generation_receipt_digest"]
        != source_authority["source_generation_receipt_digest"]
    ):
        _fail("R2 supporting row generation receipt differs")
    key = derive_r2_source_authority_key(
        source_output_id=cast(str, row["source_output_id"]),
        source_asset_id=cast(str, row["source_asset_id"]),
        source_asset_sha256=cast(str, row["source_asset_sha256"]),
        source_generation_receipt_digest=cast(str, row["source_generation_receipt_digest"]),
        source_authority_digest=cast(str, row["source_authority_digest"]),
    )
    if (
        row["source_authority_key"] != key
        or row["source_qa_snapshot_digest"] != qa["source_qa_snapshot_digest"]
    ):
        _fail("R2 supporting row key or QA binding is invalid")
    if (
        row["adult_synthetic_attested"] is not True
        or row["adult_synthetic_attested"] != qa["adult_synthetic_attested"]
    ):
        _fail("R2 supporting row adult attestation is invalid")
    preimage = {
        key: row[key]
        for key in (
            "execution_contract_digest",
            "evidence_root_id",
            "root_name_receipt_digest",
            "generation_preregistration_digest",
            "source_allocation_manifest_digest",
            "source_producer_dispatch_digest",
            "source_ordinal",
            "source_output_id",
            "source_authority_key",
            "source_authority_digest",
            "source_qa_snapshot_digest",
            "content_digest",
        )
    }
    if row["id"] != mirror_demo_digest(R2_RECORD_ID_DOMAIN, preimage)[:32]:
        _fail("R2 supporting row ID is invalid")
    _id(row["id"], "R2 supporting row ID")
    return row


def validate_r2_facts(value: object) -> Mapping[str, Any]:
    facts = _exact(value, set(legacy._FACTS_KEYS), "R2 synthetic identity facts")
    if facts.get("schema_version") is not None:
        _fail("R2 facts must use the frozen 27-key facts payload without a schema member")
    replay = dict(facts)
    replay["original_formal_identity_id_status"] = legacy.UNKNOWN_FORMAL_IDENTITY_STATUS
    legacy.validate_facts(replay)
    if facts["original_formal_identity_id_status"] != R2_NOT_APPLICABLE_STATUS:
        _fail("R2 facts original formal identity status is invalid")
    return facts


def digest_r2_facts(value: Mapping[str, object]) -> str:
    validate_r2_facts(value)
    return mirror_demo_digest(R2_FACTS_SCHEMA, cast(Mapping[str, JsonValue], value))


def _identity_keys() -> set[str]:
    return set(legacy._IDENTITY_ROW_KEYS) | {"r2_source_authority_record_id"}


def validate_r2_identity_row(
    value: object, *, facts: Mapping[str, object], supporting_row: Mapping[str, object]
) -> Mapping[str, Any]:
    row = _exact(value, _identity_keys(), "R2 synthetic identity row")
    verified_facts = validate_r2_facts(facts)
    source = _exact(supporting_row, _RECORD_FIELDS, "R2 supporting row")
    if (
        row["schema_version"] != R2_IDENTITY_SCHEMA
        or row["importer_version"] != "demo-d02-r2-identity-importer-v1"
        or row["import_config_digest"] != R2_ADMISSION_CONFIG_DIGEST
        or row["source_authority_kind"] != R2_SOURCE_AUTHORITY_KIND
    ):
        _fail("R2 identity schema/config/kind is invalid")
    if row["r2_source_authority_record_id"] != source["id"]:
        _fail("R2 identity supporting-row binding is invalid")
    for identity_key, source_key in (
        ("source_output_id", "source_output_id"),
        ("formal_canonical_asset_id", "source_asset_id"),
        ("formal_canonical_asset_sha256", "source_asset_sha256"),
        ("source_receipt_digest", "source_generation_receipt_digest"),
        ("source_authority_digest", "source_authority_digest"),
        ("source_qa_snapshot_digest", "source_qa_snapshot_digest"),
        ("source_provenance_digest", "source_provenance_digest"),
        ("adult_synthetic_attested", "adult_synthetic_attested"),
    ):
        if row[identity_key] != source[source_key]:
            _fail(f"R2 identity/source equality is invalid for {identity_key}")
    if row["source_fact_snapshot"] != verified_facts or row[
        "source_fact_snapshot_digest"
    ] != digest_r2_facts(verified_facts):
        _fail("R2 identity facts copy is invalid")
    for key in (
        "source_output_id",
        "source_receipt_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
        "source_landmark_digest",
        "source_measurement_digest",
        "source_provenance_digest",
        "source_measurement_projection",
        "source_measurement_projection_digest",
        "original_formal_identity_id_status",
        "adult_synthetic_attested",
    ):
        if row[key] != verified_facts[key]:
            _fail(f"R2 identity/facts projection is invalid for {key}")
    canonical = {
        key: item
        for key, item in row.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    if row["canonical_payload"] != canonical or row["content_digest"] != mirror_demo_digest(
        R2_IDENTITY_SCHEMA, canonical
    ):
        _fail("R2 identity canonical payload is invalid")
    expected_key = derive_r2_source_authority_key(
        source_output_id=cast(str, source["source_output_id"]),
        source_asset_id=cast(str, source["source_asset_id"]),
        source_asset_sha256=cast(str, source["source_asset_sha256"]),
        source_generation_receipt_digest=cast(str, source["source_generation_receipt_digest"]),
        source_authority_digest=cast(str, source["source_authority_digest"]),
    )
    preimage = {
        "source_authority_kind": R2_SOURCE_AUTHORITY_KIND,
        "source_authority_key": expected_key,
        "r2_source_authority_record_id": source["id"],
        "admission_sequence": row["admission_sequence"],
        "admission_action": row["admission_action"],
        "supersedes_id": row["supersedes_id"],
        "admission_config_digest": row["admission_config_digest"],
        "canonical_payload_digest": row["content_digest"],
    }
    if (
        row["source_authority_key"] != expected_key
        or row["id"] != mirror_demo_digest(R2_IDENTITY_ID_DOMAIN, preimage)[:32]
    ):
        _fail("R2 identity key or event ID is invalid")
    return row


def _validate_r2_source_manifest_entry(
    value: object,
    *,
    facts: Mapping[str, object],
    identity_row: Mapping[str, object],
    supporting_row: Mapping[str, object],
) -> Mapping[str, Any]:
    """Replay the complete public source projection before Report admission."""

    entry = _exact(
        value,
        set(legacy._SOURCE_ENTRY_KEYS) | {"r2_source_authority_record_id"},
        "R2 source manifest entry",
    )
    verified_facts = validate_r2_facts(facts)
    identity = validate_r2_identity_row(
        identity_row, facts=verified_facts, supporting_row=supporting_row
    )
    row = _exact(supporting_row, _RECORD_FIELDS, "R2 supporting row")
    if entry["schema_version"] != R2_SOURCE_ENTRY_SCHEMA:
        _fail("R2 source manifest entry schema is invalid")
    _reject_noncanonical_json(entry)
    legacy._validate_source_manifest_scalar_domains(entry)
    legacy._validate_shared_quality_fields(entry)
    if (
        entry["source_authority_kind"] != R2_SOURCE_AUTHORITY_KIND
        or entry["source_asset_mime_type"] != "image/jpeg"
        or entry["adult_synthetic_attested"] is not True
        or entry["original_formal_identity_id_status"] != R2_NOT_APPLICABLE_STATUS
        or entry["import_config_digest"] != R2_ADMISSION_CONFIG_DIGEST
    ):
        _fail("R2 source manifest authority shape is invalid")

    row_projection = {
        "source_ordinal": "source_ordinal",
        "source_output_id": "source_output_id",
        "source_asset_id": "source_asset_id",
        "source_asset_sha256": "source_asset_sha256",
        "source_asset_byte_size": "source_asset_byte_size",
        "source_asset_mime_type": "source_asset_mime_type",
        "source_asset_width": "source_asset_width",
        "source_asset_height": "source_asset_height",
        "source_receipt_digest": "source_generation_receipt_digest",
        "source_authority_digest": "source_authority_digest",
        "source_qa_snapshot_digest": "source_qa_snapshot_digest",
        "source_provenance_digest": "source_provenance_digest",
        "adult_synthetic_attested": "adult_synthetic_attested",
        "r2_source_authority_record_id": "id",
    }
    if any(entry[target] != row[source] for target, source in row_projection.items()):
        _fail("R2 source manifest/supporting-row projection is invalid")

    identity_projection = {
        "source_authority_kind": "source_authority_kind",
        "source_authority_key": "source_authority_key",
        "source_admission_event_id": "id",
        "source_admission_content_digest": "content_digest",
        "source_landmark_digest": "source_landmark_digest",
        "source_measurement_digest": "source_measurement_digest",
        "source_fact_snapshot_digest": "source_fact_snapshot_digest",
        "source_measurement_projection_digest": "source_measurement_projection_digest",
        "original_formal_identity_id_status": "original_formal_identity_id_status",
        "import_config_digest": "import_config_digest",
    }
    if any(entry[target] != identity[source] for target, source in identity_projection.items()):
        _fail("R2 source manifest/identity projection is invalid")

    fact_projection = {
        "source_landmark_digest": "source_landmark_digest",
        "source_measurement_digest": "source_measurement_digest",
        "raw_measurement_authority_digest": "raw_measurement_authority_digest",
        "source_measurement_projection_digest": "source_measurement_projection_digest",
        "source_p2_candidate_manifest_content_digest": (
            "source_p2_candidate_manifest_content_digest"
        ),
        "dimension_authority_manifest_content_digest": (
            "dimension_authority_manifest_content_digest"
        ),
        "source_repeat_certification_digest": "source_repeat_certification_digest",
    }
    if entry["source_fact_snapshot_digest"] != digest_r2_facts(verified_facts):
        _fail("R2 source manifest facts digest is invalid")
    for target, source in fact_projection.items():
        if entry[target] != verified_facts[source]:
            _fail(f"R2 source manifest/facts projection is invalid for {target}")
    if entry["ordered_supported_measurements"] != _r2_supported_measurements_from_facts(
        verified_facts
    ):
        _fail("R2 source manifest supported measurements do not replay facts")
    legacy._require_digest_match(R2_SOURCE_ENTRY_SCHEMA, entry, "record_digest", {"schema_version"})
    return entry


def validate_r2_admission_packet(value: object) -> None:
    """Replay G→A→Q→P→Facts→Identity→manifest before database admission.

    The packet has no registry locator, image byte, Prompt, raw generation, or
    QA payload.  It carries only the typed structural projections needed for
    deterministic equality checks.
    """
    packet = _exact(
        value,
        {
            "generation_receipt",
            "source_authority",
            "source_qa_snapshot",
            "supporting_row",
            "facts",
            "identity_row",
            "source_manifest_entry",
            "source_manifest_digest",
        },
        "R2 admission packet",
    )
    receipt = validate_r2_generation_receipt(packet["generation_receipt"])
    authority = validate_r2_source_authority(packet["source_authority"], receipt=receipt)
    qa = validate_r2_source_qa_snapshot(
        packet["source_qa_snapshot"], authority=authority, receipt=receipt
    )
    row = validate_r2_source_authority_record(
        packet["supporting_row"], authority=authority, qa_snapshot=qa, receipt=receipt
    )
    facts = validate_r2_facts(packet["facts"])
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
            _fail(f"R2 facts/supporting-row equality is invalid for {facts_key}")
    identity = validate_r2_identity_row(packet["identity_row"], facts=facts, supporting_row=row)
    _validate_r2_source_manifest_entry(
        packet["source_manifest_entry"],
        facts=facts,
        identity_row=identity,
        supporting_row=row,
    )
    _digest(packet["source_manifest_digest"], "R2 source manifest digest")


def canonical_r2_bytes(value: Mapping[str, object]) -> bytes:
    """Expose the frozen canonicalization used by all R2 payload validators."""
    return canonical_json_bytes(value)


# CC08 R5 import authority.  These deliberately consume only public,
# structural report projections; execution evidence is never resolved here.
R2_REPORT_SCHEMA: Final = "mirror.demo/D02PairScreeningReport/v3"
R2_REPORT_ID_DOMAIN: Final = "mirror.demo/D02PairScreeningReportId/v2"
R2_BANK_SCHEMA: Final = "mirror.demo/DemoQuestionBank/v3"
R2_BANK_ID_DOMAIN: Final = "mirror.demo/D02QuestionBankId/v2"
R2_PAIR_SCHEMA: Final = "mirror.demo/DemoQuestionPair/v3"
R2_PAIR_ID_DOMAIN: Final = "mirror.demo/D02QuestionPairId/v2"
R2_DIMENSION_MANIFEST_SCHEMA: Final = "mirror.demo/D02QuestionBankDimensionManifest/v2"
R2_PAIR_QA_SCHEMA: Final = "mirror.demo/D02QuestionPairQAPayload/v3"
R2_SELECTED_ENTRY_SCHEMA: Final = "mirror.demo/D02SelectedPairManifestEntry/v3"
R2_PAIR_SCREENING_SCHEMA: Final = "mirror.demo/D02PairScreeningRecord/v4"
R2_PAIR_RECORD_ID_DOMAIN: Final = "mirror.demo/D02PairScreeningRecordId/v2"
R2_DIMENSION_SCHEMA: Final = "mirror.demo/D02DimensionEligibilityRecord/v4"
R2_SELECTION_SCHEMA: Final = "mirror.demo/D02SelectionTraceRecord/v3"
R2_SELECTED_MANIFEST_SCHEMA: Final = "mirror.demo/D02SelectedPairManifest/v3"
R2_SCHEMA_POLICY_SCHEMA: Final = "mirror.demo/D02SchemaAndPolicyBinding/v3"
R2_CASE_SCHEMA: Final = "mirror.demo/D02GeometryCaseManifestEntry/v4"
R2_CASE_MANIFEST_SCHEMA: Final = "mirror.demo/D02GeometryCaseManifest/v2"
R2_EXECUTION_CONFIGURATION_SCHEMA: Final = "mirror.demo/D02ExecutionConfiguration/v2"
R2_SOURCE_M3_SCHEMA: Final = "mirror.demo/D02SourceM3RepeatRecord/v3"
R2_M4_SCHEMA: Final = "mirror.demo/D02M4ExecutionRecord/v2"
R2_RESULT_M3_SCHEMA: Final = "mirror.demo/D02ResultM3RepeatRecord/v3"
R2_GATE_SCHEMA: Final = "mirror.demo/D02MeasurementGateRecord/v5"
R2_STRUCTURE_SCHEMA: Final = "mirror.demo/D02DecodeStructureImmutabilityRecord/v2"
R2_MANUAL_SCHEMA: Final = "mirror.demo/D02ManualArtifactDecision/v1"
R2_CASE_ID_DOMAIN: Final = "mirror.demo/D02GeometryCaseId/v2"
R2_CASE_SPEC_DOMAIN: Final = "mirror.demo/D02GeometryCaseSpecification/v2"
R2_M4_ID_DOMAIN: Final = "mirror.demo/D02M4ExecutionRecordId/v2"
R2_SOURCE_M3_ID_DOMAIN: Final = "mirror.demo/D02SourceM3RecordId/v2"
R2_RESULT_M3_ID_DOMAIN: Final = "mirror.demo/D02ResultM3RepeatRecordId/v2"
R2_SOURCE_IMAGE_SCHEMA: Final = "mirror.demo/D02SourceImageAuthorityRecord/v3"
R2_RESULT_IMAGE_SCHEMA: Final = "mirror.demo/D02ResultImageAuthorityRecord/v3"
R2_SOURCE_IMAGE_ID_DOMAIN: Final = "mirror.demo/D02SourceImageAuthorityRecordId/v2"
R2_RESULT_IMAGE_ID_DOMAIN: Final = "mirror.demo/D02ResultImageAuthorityRecordId/v2"
R2_NETWORK_BOUNDARY_RECEIPT_DOMAIN: Final = "mirror.demo/D02R2NetworkRuntimeBoundaryReceipt/v1"

R2_REPORT_GROUPS: Final = (
    ("schema_and_policy", "mirror.demo/D02SchemaAndPolicyBinding/v3", 1),
    ("ordered_source_manifest", R2_SOURCE_ENTRY_SCHEMA, 4),
    ("ordered_case_manifest", "mirror.demo/D02GeometryCaseManifestEntry/v4", 48),
    ("source_m3_repeat_evidence", "mirror.demo/D02SourceM3RepeatRecord/v3", 12),
    ("m4_repeat_evidence", "mirror.demo/D02M4ExecutionRecord/v2", 96),
    ("result_m3_repeat_evidence", "mirror.demo/D02ResultM3RepeatRecord/v3", 144),
    ("measurement_gate_evidence", "mirror.demo/D02MeasurementGateRecord/v5", 48),
    (
        "decode_structure_immutability_evidence",
        "mirror.demo/D02DecodeStructureImmutabilityRecord/v2",
        48,
    ),
    ("manual_review_evidence", "mirror.demo/D02ManualArtifactDecision/v1", 48),
    ("exact_duplicate_evidence", "mirror.demo/D02ExactDuplicateEvidence/v2", 1),
    ("phash_observation_evidence", "mirror.demo/D02PHashObservationEvidence/v2", 1),
    ("pair_quality_evidence", "mirror.demo/D02PairScreeningRecord/v4", 24),
    ("dimension_eligibility", "mirror.demo/D02DimensionEligibilityRecord/v4", 3),
    ("fixed_priority_selection_trace", "mirror.demo/D02SelectionTraceRecord/v3", 3),
    ("selected_pair_manifest", "mirror.demo/D02SelectedPairManifest/v3", 1),
    ("network_and_runtime_boundary", "mirror.demo/D02NetworkRuntimeBoundary/v2", 1),
)
R2_REPORT_PAYLOAD_KEYS: Final = {name for name, _, _ in R2_REPORT_GROUPS}
R2_LEGACY_MEMBER_KEYS: Final[dict[str, set[str]]] = {
    "schema_and_policy": set(legacy._BINDING_KEYS),
    "m4_repeat_evidence": set(legacy._M4_EXECUTION_KEYS),
    "result_m3_repeat_evidence": set(legacy._RESULT_M3_KEYS),
    "measurement_gate_evidence": set(legacy._GATE_KEYS),
    "decode_structure_immutability_evidence": set(legacy._STRUCTURE_KEYS),
    "manual_review_evidence": set(legacy._MANUAL_KEYS),
    "exact_duplicate_evidence": set(legacy._EXACT_DUPLICATE_KEYS),
    "phash_observation_evidence": set(legacy._PHASH_EVIDENCE_KEYS),
    "network_and_runtime_boundary": set(legacy._NETWORK_BOUNDARY_KEYS),
}
R2_CASE_KEYS: Final = set(legacy._CASE_ENTRY_KEYS) | {"r2_source_authority_record_id"}
R2_SOURCE_M3_KEYS: Final = set(legacy._SOURCE_M3_KEYS) | {"source_authority_digest"}
R2_SOURCE_M3_MANDATORY_DIGEST_LEAVES: Final = (
    "source_authority_key",
    "source_authority_digest",
    "source_asset_sha256",
    "execution_receipt_digest",
    "vision_model_manifest_digest",
    "runtime_manifest_digest",
    "topology_digest",
    "canonical_output_digest",
    "landmark_digest",
    "measurement_observation_digest",
    "record_digest",
)
R2_RESULT_M3_MANDATORY_DIGEST_LEAVES: Final = (
    "case_specification_digest",
    "result_sha256",
    "execution_receipt_digest",
    "vision_model_manifest_digest",
    "runtime_manifest_digest",
    "topology_digest",
    "canonical_output_digest",
    "landmark_digest",
    "measurement_observation_digest",
    "record_digest",
)
R2_REPORT_FIELDS: Final = {
    "created_at",
    "source_manifest_digest",
    "case_manifest_digest",
    "screening_policy_digest",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "measurement_config_digest",
    "manual_review_policy_digest",
    "duplicate_policy_digest",
    "phash_implementation_digest",
    "report_payload",
    "status",
    "source_count",
    "case_count",
    "source_m3_repeat_count",
    "m4_execution_count",
    "result_m3_repeat_count",
    "measurement_gate_count",
    "decode_structure_record_count",
    "manual_decision_count",
    "exact_sha_record_count",
    "phash_comparison_count",
    "candidate_pair_count",
    "selected_pair_count",
    "selected_result_side_count",
    "eligible_dimension_keys",
    "selected_dimension_keys",
    "selected_pair_manifest_digest",
}
R2_REPORT_ROW_KEYS: Final = R2_REPORT_FIELDS | {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "report_digest",
    "created_at",
}
R2_BANK_FIELDS: Final = {
    "created_at",
    "version",
    "algorithm_config_digest",
    "routing_version",
    "stopping_version",
    "neighborhood_version",
    "pair_manifest_digest",
    "dimension_manifest",
    "screening_report_id",
    "screening_report_digest",
}
R2_BANK_ROW_KEYS: Final = R2_BANK_FIELDS | {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "created_at",
}
R2_DIMENSION_MANIFEST_KEYS: Final = {
    "schema_version",
    "screening_report_id",
    "screening_report_digest",
    "source_manifest_digest",
    "source_p2_candidate_manifest_content_digest",
    "dimension_authority_manifest_content_digest",
    "selected_pair_manifest_digest",
    "selected_dimensions",
}
R2_SELECTED_DIMENSION_KEYS: Final = {
    "dimension_key",
    "priority_index",
    "sixteen_side_gate_digest",
    "eight_pair_gate_digest",
    "ordered_selected_pair_entry_digests",
}
R2_PAIR_FIELDS: Final = {
    "created_at",
    "question_bank_id",
    "demo_synthetic_identity_id",
    "source_asset_id",
    "source_asset_sha256",
    "left_asset_id",
    "left_asset_sha256",
    "right_asset_id",
    "right_asset_sha256",
    "left_asset_variant_id",
    "right_asset_variant_id",
    "dimension_key",
    "magnitude_ppm",
    "left_delta_ppm",
    "right_delta_ppm",
    "pair_quality_ppm",
    "qa_payload",
    "screening_report_id",
    "screening_report_digest",
}
R2_PAIR_ROW_KEYS: Final = R2_PAIR_FIELDS | {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "created_at",
}
R2_PAIR_QA_KEYS: Final = {
    "schema_version",
    "screening_report_id",
    "screening_report_digest",
    "source_manifest_digest",
    "source_manifest_entry_schema_version",
    "source_manifest_entry_digest",
    "pair_screening_record_schema_version",
    "pair_screening_record_digest",
    "pair_screening_record_payload",
    "selected_pair_manifest_digest",
    "selected_pair_entry_schema_version",
    "selected_pair_entry_digest",
    "selected_pair_entry_payload",
}


def _reject_noncanonical_json(value: object) -> None:
    if isinstance(value, float):
        _fail("R2 canonical authority rejects raw float")
    if isinstance(value, str) and value in {"-0", "-0.0", "-0.00"}:
        _fail("R2 canonical authority rejects negative zero")
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_noncanonical_json(item)
    elif isinstance(value, list):
        for item in value:
            _reject_noncanonical_json(item)


def _typed_member(value: object, schema: str, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema_version") != schema:
        _fail(f"{label} schema is invalid")
    _reject_noncanonical_json(value)
    return cast(Mapping[str, Any], value)


def _member_digest(member: Mapping[str, object], schema: str, label: str) -> str:
    digest = member.get(
        "entry_digest",
        member.get(
            "record_digest",
            member.get("pair_screening_record_digest", member.get("content_digest")),
        ),
    )
    _digest(digest, label)
    return cast(str, digest)


def _replay_member(member: Mapping[str, object], schema: str, label: str) -> str:
    """Replay a named non-wrapper record, rejecting the old two-key placeholder."""
    _typed_member(member, schema, label)
    if len(member) < 3:
        _fail(f"{label} must not use a two-key digest placeholder")
    digest_key = next(
        (
            key
            for key in ("entry_digest", "record_digest", "manual_decision_digest")
            if key in member
        ),
        None,
    )
    if digest_key is None:
        _fail(f"{label} has no named typed digest")
    _digest(member[digest_key], f"{label} digest")
    preimage = {
        key: item for key, item in member.items() if key not in {"schema_version", digest_key}
    }
    if member[digest_key] != mirror_demo_digest(schema, cast(dict[str, JsonValue], preimage)):
        _fail(f"{label} digest does not replay")
    return cast(str, member[digest_key])


def _r2_execution_authority(binding: Mapping[str, object]) -> dict[str, JsonValue]:
    """Return the v2 execution authority after exact schema/policy replay.

    CC08 keeps the predecessor field set here, but moves the binding into the
    R2 domain.  This deliberately has no legacy-mode fallback.
    """
    parsed = _exact(binding, set(legacy._BINDING_KEYS), "R2 schema and policy binding")
    if parsed["schema_version"] != R2_SCHEMA_POLICY_SCHEMA:
        _fail("R2 schema and policy binding schema is invalid")
    _reject_noncanonical_json(parsed)
    for key in (
        "source_manifest_digest",
        "case_manifest_digest",
        "screening_policy_digest",
        "runtime_manifest_digest",
        "vision_model_manifest_digest",
        "topology_digest",
        "measurement_config_digest",
        "measurement_quality_config_digest",
        "measurement_quality_manifest_content_digest",
        "manual_review_policy_digest",
        "duplicate_policy_digest",
        "phash_implementation_digest",
    ):
        _digest(parsed[key], f"R2 {key}")
    config = parsed["measurement_execution_config"]
    if not isinstance(config, Mapping):
        _fail("R2 measurement execution configuration is invalid")
    # CC08 advances the schema/domain only; it explicitly retains the
    # predecessor binding semantics. Replaying digest syntax alone would let a
    # fully re-signed Report replace the accepted Vision/runtime, topology,
    # screening root, or measurement configuration. Normalize only the schema
    # tag and replay the predecessor's exact accepted authority before returning
    # the original R2 binding.
    predecessor = dict(parsed)
    predecessor["schema_version"] = legacy.SCHEMA_POLICY_SCHEMA
    try:
        legacy.validate_schema_and_policy_binding(predecessor)
    except legacy.D02AuthorityError as error:
        raise D02R2AuthorityError(
            "R2 schema and policy binding differs from accepted execution authority"
        ) from error
    return cast(dict[str, JsonValue], dict(parsed))


def _r2_case_execution_digest(case: Mapping[str, object], authority: Mapping[str, object]) -> str:
    if case.get("runtime_manifest_digest") != authority.get("runtime_manifest_digest"):
        _fail("R2 case runtime manifest differs from accepted execution authority")
    return mirror_demo_digest(
        R2_EXECUTION_CONFIGURATION_SCHEMA,
        cast(
            dict[str, JsonValue],
            {
                **{key: authority[key] for key in legacy._EXECUTION_AUTHORITY_KEYS},
                "geometry_algorithm_version": case["geometry_algorithm_version"],
                "runtime_config_digest": case["runtime_config_digest"],
                "output_policy_version": case["output_policy_version"],
                "output_width": case["output_width"],
                "output_height": case["output_height"],
                "determinism_level": case["determinism_level"],
            },
        ),
    )


def _r2_case_id(case: Mapping[str, object]) -> str:
    return mirror_demo_digest(
        R2_CASE_ID_DOMAIN,
        cast(
            dict[str, JsonValue],
            {
                key: case[key]
                for key in (
                    "source_manifest_digest",
                    "source_authority_key",
                    "source_admission_event_id",
                    "source_asset_sha256",
                    "r2_source_authority_record_id",
                    "source_p2_candidate_manifest_content_digest",
                    "dimension_authority_manifest_content_digest",
                    "dimension_key",
                    "direction",
                    "magnitude_ppm",
                    "execution_config_digest",
                )
            },
        ),
    )[:32]


def _r2_case_specification_digest(case: Mapping[str, object]) -> str:
    excluded = {
        "schema_version",
        "case_ordinal",
        "case_id",
        "record_digest",
        "case_specification_digest",
    }
    return mirror_demo_digest(
        R2_CASE_SPEC_DOMAIN,
        cast(
            dict[str, JsonValue], {key: value for key, value in case.items() if key not in excluded}
        ),
    )


def _r2_case_manifest_digest(entries: Sequence[Mapping[str, object]]) -> str:
    return legacy._sequence_digest(R2_CASE_MANIFEST_SCHEMA, entries)


def _validate_r2_case_manifest_entry(
    value: object, *, execution_authority: Mapping[str, object]
) -> Mapping[str, Any]:
    """Replay one CaseEntry/v4 without weakening predecessor case semantics."""

    entry = _exact(value, R2_CASE_KEYS, "R2 geometry case manifest entry")
    _reject_noncanonical_json(entry)
    if entry["schema_version"] != R2_CASE_SCHEMA:
        _fail("R2 geometry case schema is invalid")
    for key in (
        "source_manifest_digest",
        "source_asset_sha256",
        "source_qa_snapshot_digest",
        "source_measurement_projection_digest",
        "source_p2_candidate_manifest_content_digest",
        "dimension_authority_manifest_content_digest",
        "geometry_ontology_version_digest",
        "warp_plan_digest",
        "runtime_manifest_digest",
        "runtime_config_digest",
        "execution_config_digest",
        "case_specification_digest",
    ):
        _digest(entry[key], f"R2 case {key}")
    for key in (
        "case_id",
        "source_admission_event_id",
        "source_asset_id",
        "r2_source_authority_record_id",
    ):
        _id(entry[key], f"R2 case {key}")
    _digest(entry["source_authority_key"], "R2 case source authority key")
    if type(entry["case_ordinal"]) is not int or not 1 <= entry["case_ordinal"] <= 48:
        _fail("R2 case ordinal is invalid")
    if entry["dimension_key"] not in legacy.CASE_DIMENSIONS:
        _fail("R2 case dimension is invalid")
    if entry["direction"] not in legacy.CASE_DIRECTIONS:
        _fail("R2 case direction is invalid")
    if (
        type(entry["magnitude_ppm"]) is not int
        or entry["magnitude_ppm"] not in legacy.CASE_MAGNITUDES
    ):
        _fail("R2 case magnitude is invalid")
    if entry["priority_index"] != legacy.CASE_DIMENSIONS.index(entry["dimension_key"]) + 1:
        _fail("R2 case priority index is invalid")
    if entry["direction_index"] != legacy.CASE_DIRECTIONS.index(entry["direction"]) + 1:
        _fail("R2 case direction index is invalid")
    if entry["magnitude_index"] != legacy.CASE_MAGNITUDES.index(entry["magnitude_ppm"]) + 1:
        _fail("R2 case magnitude index is invalid")
    if entry["ordered_control_dimensions"] != list(
        legacy._case_controls(cast(str, entry["dimension_key"]))
    ):
        _fail("R2 case control dimensions are invalid")
    for key in ("geometry_algorithm_version", "output_policy_version", "determinism_level"):
        if not isinstance(entry[key], str) or legacy._VERSION.fullmatch(entry[key]) is None:
            _fail(f"R2 case {key} is invalid")
    for key in ("output_width", "output_height"):
        if type(entry[key]) is not int or not 1 <= entry[key] <= 2_147_483_647:
            _fail(f"R2 case {key} is invalid")
    authority = _r2_execution_authority(execution_authority)
    if entry["runtime_manifest_digest"] != authority["runtime_manifest_digest"]:
        _fail("R2 case runtime manifest binding is invalid")
    if entry["execution_config_digest"] != _r2_case_execution_digest(entry, authority):
        _fail("R2 execution configuration does not replay")
    if entry["case_id"] != _r2_case_id(entry):
        _fail("R2 case ID does not replay")
    if entry["case_specification_digest"] != _r2_case_specification_digest(entry):
        _fail("R2 case specification digest does not replay")
    _replay_member(entry, R2_CASE_SCHEMA, "R2 case")
    return entry


def derive_r2_source_m3_record_id(
    *,
    source_manifest_digest: str,
    source_authority_key: str,
    source_admission_event_id: str,
    source_asset_id: str,
    source_asset_sha256: str,
    repeat_index: int,
    vision_model_manifest_digest: str,
    runtime_manifest_digest: str,
    topology_digest: str,
) -> str:
    """Derive the R2 SourceM3/v3 identifier from its R2 manifest authority."""
    legacy._digest(source_manifest_digest, "R2 source manifest digest")
    legacy._digest(source_authority_key, "R2 source authority key")
    legacy._id(source_admission_event_id, "R2 source admission event ID")
    legacy._id(source_asset_id, "R2 source Asset ID")
    legacy._digest(source_asset_sha256, "R2 source Asset SHA256")
    if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
        _fail("R2 SourceM3 repeat index must be one through three")
    for value, label in (
        (vision_model_manifest_digest, "R2 SourceM3 Vision manifest"),
        (runtime_manifest_digest, "R2 SourceM3 runtime manifest"),
        (topology_digest, "R2 SourceM3 topology"),
    ):
        legacy._digest(value, label)
    return mirror_demo_digest(
        R2_SOURCE_M3_ID_DOMAIN,
        cast(
            dict[str, JsonValue],
            {
                "source_manifest_digest": source_manifest_digest,
                "source_authority_key": source_authority_key,
                "source_admission_event_id": source_admission_event_id,
                "source_asset_id": source_asset_id,
                "source_asset_sha256": source_asset_sha256,
                "repeat_index": repeat_index,
                "vision_model_manifest_digest": vision_model_manifest_digest,
                "runtime_manifest_digest": runtime_manifest_digest,
                "topology_digest": topology_digest,
            },
        ),
    )[:32]


def _r2_supported_measurements_from_facts(
    facts: Mapping[str, object],
) -> list[Mapping[str, Any]]:
    """Rebuild the Gate source projection from the admitted raw authority."""
    verified = validate_r2_facts(facts)
    raw = cast(Mapping[str, Any], verified["raw_measurement_authority"])
    projection = cast(Mapping[str, Any], verified["source_measurement_projection"])
    raw_entries = cast(list[Mapping[str, Any]], raw["ordered_entries"])
    projection_entries = cast(list[Mapping[str, Any]], projection["ordered_entries"])
    return [
        {
            "schema_version": "mirror.demo/D02SupportedSourceMeasurement/v1",
            "dimension_key": raw_entry["dimension_key"],
            "raw_value_fixed18": raw_entry["raw_value_fixed18"],
            "raw_confidence_fixed18": raw_entry["raw_confidence_fixed18"],
            "raw_reliability_fixed18": raw_entry["raw_reliability_fixed18"],
            "value_ppm": projection_entry["value_ppm"],
            "confidence_ppm": projection_entry["confidence_ppm"],
            "reliability_ppm": projection_entry["reliability_ppm"],
            "unit": "FACE_HEIGHT_PPM",
        }
        for raw_entry, projection_entry in zip(raw_entries, projection_entries, strict=True)
    ]


def _validate_r2_source_m3_record(
    value: object,
    *,
    source: Mapping[str, object],
    facts: Mapping[str, object],
    source_manifest_digest: str,
    execution_authority: Mapping[str, object],
) -> Mapping[str, Any]:
    _require_mandatory_digest_leaves(value, R2_SOURCE_M3_MANDATORY_DIGEST_LEAVES, "R2 SourceM3")
    record = _exact(value, R2_SOURCE_M3_KEYS, "R2 SourceM3 record")
    _reject_noncanonical_json(record)
    if record["schema_version"] != R2_SOURCE_M3_SCHEMA:
        _fail("R2 SourceM3 schema is invalid")
    for key in ("source_m3_record_id", "source_admission_event_id", "source_asset_id"):
        legacy._id(record[key], f"R2 SourceM3 {key}")
    for key in (
        "source_authority_key",
        "source_authority_digest",
        "source_asset_sha256",
        "execution_receipt_digest",
        "vision_model_manifest_digest",
        "runtime_manifest_digest",
        "topology_digest",
        "canonical_output_digest",
        "landmark_digest",
        "measurement_observation_digest",
        "record_digest",
    ):
        legacy._digest(record[key], f"R2 SourceM3 {key}")
    if (
        type(record["source_ordinal"]) is not int
        or record["source_ordinal"] not in {1, 2, 3, 4}
        or type(record["repeat_index"]) is not int
        or record["repeat_index"] not in {1, 2, 3}
        or type(record["face_count"]) is not int
        or type(record["landmark_count"]) is not int
    ):
        _fail("R2 SourceM3 scalar domains are invalid")
    for key in ("coordinates_finite", "coordinates_in_bounds", "repeat_gate_passed"):
        legacy._bool(record[key], f"R2 SourceM3 {key}")
    for key in (
        "source_ordinal",
        "source_authority_key",
        "source_admission_event_id",
        "source_asset_id",
        "source_asset_sha256",
        "source_authority_digest",
    ):
        if record[key] != source[key]:
            _fail("R2 SourceM3 source authority binding is invalid")
    verified_facts = validate_r2_facts(facts)
    observation = legacy.validate_measurement_observation(
        verified_facts["source_measurement_observation"], role="SOURCE"
    )
    certificate = legacy.validate_source_certificate(verified_facts["source_repeat_certification"])
    legacy._validate_source_certificate_observation_crosslinks(certificate, observation)
    if (
        record["measurement_observation"] != observation
        or record["measurement_observation_digest"] != observation["measurement_observation_digest"]
    ):
        _fail("R2 SourceM3 observation does not equal the admitted facts projection")
    for key in ("vision_model_manifest_digest", "runtime_manifest_digest", "topology_digest"):
        if (
            record[key] != observation[key]
            or record[key] != source[key]
            or record[key] != execution_authority[key]
        ):
            _fail("R2 SourceM3 runtime authority is invalid")
    if (
        record["canonical_output_digest"] != observation["canonical_output_digest"]
        or record["landmark_digest"] != observation["landmark_digest"]
        or record["source_asset_id"] != observation["subject"]["source_asset_id"]
        or record["source_asset_sha256"] != observation["subject"]["source_asset_sha256"]
    ):
        _fail("R2 SourceM3 observation lineage is invalid")
    binding = cast(list[Mapping[str, Any]], certificate["ordered_repeat_bindings"])[
        record["repeat_index"] - 1
    ]
    for key in (
        "repeat_index",
        "execution_receipt_digest",
        "canonical_output_digest",
        "landmark_digest",
        "measurement_observation_digest",
        "face_count",
        "landmark_count",
        "coordinates_finite",
        "coordinates_in_bounds",
        "repeat_gate_passed",
    ):
        if record[key] != binding[key]:
            _fail("R2 SourceM3 certificate semantic tuple is invalid")
    expected_id = derive_r2_source_m3_record_id(
        source_manifest_digest=source_manifest_digest,
        source_authority_key=cast(str, record["source_authority_key"]),
        source_admission_event_id=cast(str, record["source_admission_event_id"]),
        source_asset_id=cast(str, record["source_asset_id"]),
        source_asset_sha256=cast(str, record["source_asset_sha256"]),
        repeat_index=record["repeat_index"],
        vision_model_manifest_digest=cast(str, record["vision_model_manifest_digest"]),
        runtime_manifest_digest=cast(str, record["runtime_manifest_digest"]),
        topology_digest=cast(str, record["topology_digest"]),
    )
    if record["source_m3_record_id"] != expected_id:
        _fail("R2 SourceM3 ID does not replay")
    legacy._require_digest_match(R2_SOURCE_M3_SCHEMA, record, "record_digest", {"schema_version"})
    return record


def _validate_r2_result_m3_record(value: object) -> Mapping[str, Any]:
    _require_mandatory_digest_leaves(value, R2_RESULT_M3_MANDATORY_DIGEST_LEAVES, "R2 ResultM3")
    record = _exact(value, set(legacy._RESULT_M3_KEYS), "R2 ResultM3 record")
    _reject_noncanonical_json(record)
    if record["schema_version"] != R2_RESULT_M3_SCHEMA:
        _fail("R2 ResultM3 schema is invalid")
    observation = legacy.validate_measurement_observation(
        record["measurement_observation"], role="RESULT"
    )
    subject = cast(Mapping[str, Any], observation["subject"])
    if any(
        record[key] != subject[key]
        for key in ("case_id", "case_specification_digest", "result_output_id", "result_sha256")
    ):
        _fail("R2 ResultM3 observation subject binding is invalid")
    if any(
        record[key] != observation[observation_key]
        for key, observation_key in (
            ("measurement_observation_digest", "measurement_observation_digest"),
            ("canonical_output_digest", "canonical_output_digest"),
            ("landmark_digest", "landmark_digest"),
            ("runtime_manifest_digest", "runtime_manifest_digest"),
            ("vision_model_manifest_digest", "vision_model_manifest_digest"),
            ("topology_digest", "topology_digest"),
        )
    ):
        _fail("R2 ResultM3 observation lineage is invalid")
    entries = cast(list[Mapping[str, Any]], observation["ordered_measurements"])
    expected_state = (
        "SUPPORTED"
        if all(entry["support_state"] == "SUPPORTED" for entry in entries)
        else "UNSUPPORTED_EXPLICIT"
    )
    if (
        type(record["repeat_index"]) is not int
        or record["repeat_index"] not in {1, 2, 3}
        or type(record["face_count"]) is not int
        or record["face_count"] != 1
        or type(record["landmark_count"]) is not int
        or record["landmark_count"] != 478
        or record["coordinates_finite"] is not True
        or record["coordinates_in_bounds"] is not True
        or record["observation_state"] != expected_state
        or type(record["repeat_gate_passed"]) is not bool
    ):
        _fail("R2 ResultM3 structural state is invalid")
    if record["repeat_gate_passed"] is not (expected_state == "SUPPORTED"):
        _fail("R2 ResultM3 repeat gate does not replay observation support")
    expected_id = mirror_demo_digest(
        R2_RESULT_M3_ID_DOMAIN,
        cast(
            dict[str, JsonValue],
            {
                key: record[key]
                for key in (
                    "case_id",
                    "case_specification_digest",
                    "result_output_id",
                    "result_sha256",
                    "repeat_index",
                    "runtime_manifest_digest",
                    "vision_model_manifest_digest",
                    "topology_digest",
                )
            },
        ),
    )[:32]
    if record["result_m3_record_id"] != expected_id:
        _fail("R2 ResultM3 ID does not replay")
    legacy._require_digest_match(R2_RESULT_M3_SCHEMA, record, "record_digest", {"schema_version"})
    return record


def _validate_r2_m4_execution_record(
    value: object,
    *,
    case: Mapping[str, object],
    source: Mapping[str, object],
) -> Mapping[str, Any]:
    """Replay one R2 M4 receipt against its case and admitted source authority."""

    record = _exact(value, set(legacy._M4_EXECUTION_KEYS), "R2 M4 record")
    _reject_noncanonical_json(record)
    if record["schema_version"] != R2_M4_SCHEMA:
        _fail("R2 M4 schema is invalid")
    legacy._id(record["m4_execution_record_id"], "R2 M4 record ID")
    legacy._id(record["case_id"], "R2 M4 case ID")
    legacy._id(record["source_asset_id"], "R2 M4 source Asset ID")
    legacy._opaque_output_id(record["source_output_id"], "R2 M4 source output ID")
    legacy._opaque_output_id(record["result_output_id"], "R2 M4 result output ID")
    for key in (
        "case_specification_digest",
        "source_asset_sha256",
        "result_sha256",
        "warp_plan_digest",
        "runtime_manifest_digest",
        "runtime_config_digest",
        "execution_receipt_digest",
        "record_digest",
    ):
        legacy._digest(record[key], f"R2 M4 {key}")
    if type(record["replay_index"]) is not int or record["replay_index"] not in {1, 2}:
        _fail("R2 M4 replay index is invalid")
    if (
        type(record["result_byte_size"]) is not int
        or not 1 <= record["result_byte_size"] <= 9_223_372_036_854_775_807
        or record["result_mime_type"] != "image/jpeg"
    ):
        _fail("R2 M4 result descriptor is invalid")
    for key in ("result_width", "result_height"):
        if type(record[key]) is not int or not 1 <= record[key] <= 2_147_483_647:
            _fail(f"R2 M4 {key} is invalid")
    if (
        type(record["changed_pixel_count"]) is not int
        or not 1
        <= record["changed_pixel_count"]
        <= record["result_width"] * record["result_height"]
    ):
        _fail("R2 M4 changed pixel count is invalid")
    if legacy._bool(record["execution_succeeded"], "R2 M4 execution succeeded") is not True:
        _fail("R2 M4 execution must have succeeded")
    for key in (
        "case_id",
        "case_specification_digest",
        "source_asset_id",
        "source_asset_sha256",
        "warp_plan_digest",
        "geometry_algorithm_version",
        "runtime_manifest_digest",
        "runtime_config_digest",
        "determinism_level",
    ):
        if record[key] != case[key]:
            _fail("R2 M4 case authority binding is invalid")
    if record["source_output_id"] != source["source_output_id"]:
        _fail("R2 M4 source output binding is invalid")
    expected_id = mirror_demo_digest(
        R2_M4_ID_DOMAIN,
        cast(
            dict[str, JsonValue],
            {
                "case_id": case["case_id"],
                "case_specification_digest": case["case_specification_digest"],
                "replay_index": record["replay_index"],
                "geometry_algorithm_version": case["geometry_algorithm_version"],
                "runtime_manifest_digest": case["runtime_manifest_digest"],
                "runtime_config_digest": case["runtime_config_digest"],
                "determinism_level": case["determinism_level"],
            },
        ),
    )[:32]
    if record["m4_execution_record_id"] != expected_id:
        _fail("R2 M4 ID does not replay")
    legacy._require_digest_match(R2_M4_SCHEMA, record, "record_digest", {"schema_version"})
    return record


def _validate_r2_result_certificate(
    value: object, records: Sequence[Mapping[str, object]]
) -> Mapping[str, Any]:
    cert = _exact(value, set(legacy._RESULT_CERT_KEYS), "R2 result repeat certificate")
    if cert["schema_version"] != "mirror.demo/D02ResultRepeatDeterminismCertification/v1":
        _fail("R2 result certificate schema is invalid")
    subject = legacy.validate_measurement_subject(cert["subject"], "RESULT")
    legacy._validate_certificate_common(cert, "result_repeat_certification_digest", source=False)
    if len(records) != 3:
        _fail("R2 result certificate requires three ResultM3 records")
    parsed = [_validate_r2_result_m3_record(record) for record in records]
    if any(
        subject[key] != parsed[0][key]
        for key in ("case_id", "case_specification_digest", "result_output_id", "result_sha256")
    ):
        _fail("R2 result certificate subject is invalid")
    for binding, record in zip(cert["ordered_repeat_bindings"], parsed, strict=True):
        if not isinstance(binding, Mapping):
            _fail("R2 result certificate binding is invalid")
        for key in (
            "result_m3_record_id",
            "repeat_index",
            "execution_receipt_digest",
            "canonical_output_digest",
            "landmark_digest",
            "measurement_observation_digest",
            "face_count",
            "landmark_count",
            "coordinates_finite",
            "coordinates_in_bounds",
            "observation_state",
            "repeat_gate_passed",
        ):
            if binding[key] != record[key]:
                _fail("R2 result certificate semantic tuple is invalid")
    return cert


def _validate_r2_measurement_gate(
    value: object,
    *,
    result_records: Sequence[Mapping[str, object]],
    facts: Mapping[str, object],
) -> Mapping[str, Any]:
    gate = _exact(value, set(legacy._GATE_KEYS), "R2 measurement gate")
    _reject_noncanonical_json(gate)
    if gate["schema_version"] != R2_GATE_SCHEMA:
        _fail("R2 measurement gate schema is invalid")
    certificate = _validate_r2_result_certificate(
        gate["result_repeat_certification"], result_records
    )
    if (
        gate["result_repeat_certification_digest"]
        != certificate["result_repeat_certification_digest"]
    ):
        _fail("R2 measurement gate result certificate digest is invalid")
    parsed_records = [_validate_r2_result_m3_record(record) for record in result_records]
    if [record["repeat_index"] for record in parsed_records] != [1, 2, 3]:
        _fail("R2 measurement gate ResultM3 repeat order is invalid")
    dimension = gate["dimension_key"]
    if dimension not in legacy.DIMENSIONS or gate["requested_direction"] not in {
        "INCREASE",
        "DECREASE",
    }:
        _fail("R2 measurement gate dimension or direction is invalid")
    if type(gate["requested_magnitude_ppm"]) is not int or gate["requested_magnitude_ppm"] not in {
        15_000,
        30_000,
    }:
        _fail("R2 measurement gate magnitude is invalid")
    legacy._id(gate["case_id"], "R2 measurement gate case ID")
    legacy._digest(gate["case_specification_digest"], "R2 measurement gate case digest")
    legacy._id(gate["monotonicity_peer_case_id"], "R2 monotonicity peer case ID")
    source_by_dimension = {
        cast(str, item["dimension_key"]): item
        for item in _r2_supported_measurements_from_facts(facts)
    }
    target = legacy._validate_supported_measurement(
        gate["source_target_measurement"], dimension=cast(str, dimension)
    )
    if target != source_by_dimension[cast(str, dimension)]:
        _fail("R2 measurement gate target does not replay admitted source projection")
    expected_controls = tuple(item for item in legacy.DIMENSIONS if item != dimension)
    controls = gate["ordered_source_control_measurements"]
    if not isinstance(controls, list) or len(controls) != len(expected_controls):
        _fail("R2 measurement gate controls are invalid")
    parsed_controls = [
        legacy._validate_supported_measurement(item, dimension=control_dimension)
        for control_dimension, item in zip(expected_controls, controls, strict=True)
    ]
    if parsed_controls != [source_by_dimension[item] for item in expected_controls]:
        _fail("R2 measurement gate controls do not replay admitted source projection")
    measurements = gate["ordered_result_repeat_measurements"]
    if not isinstance(measurements, list) or len(measurements) != 3:
        _fail("R2 measurement gate repeat measurements are invalid")
    parsed_measurements = [
        legacy._validate_result_measurement(
            measurement,
            record=record,
            target=target,
            controls=parsed_controls,
            dimension=cast(str, dimension),
            direction=cast(str, gate["requested_direction"]),
        )
        for measurement, record in zip(measurements, parsed_records, strict=True)
    ]
    legacy._validate_gate_evaluation(
        gate["measurement_evaluation_state"], gate["gate_evaluation"], parsed_measurements
    )
    if any(
        record["case_id"] != gate["case_id"]
        or record["case_specification_digest"] != gate["case_specification_digest"]
        for record in parsed_records
    ):
        _fail("R2 measurement gate case binding is invalid")
    legacy._require_digest_match(R2_GATE_SCHEMA, gate, "record_digest", {"schema_version"})
    return gate


def _r2_structure_values(
    case: Mapping[str, object], first: Mapping[str, object], second: Mapping[str, object]
) -> dict[str, bool]:
    bytes_equal = all(
        first[key] == second[key]
        for key in ("result_output_id", "result_sha256", "result_byte_size", "result_mime_type")
    )
    dimensions_equal = all(first[key] == second[key] for key in ("result_width", "result_height"))
    changed_pixel_count = first["changed_pixel_count"]
    if type(changed_pixel_count) is not int:
        _fail("R2 structure M4 changed pixel count is invalid")
    values = {
        "source_decode_valid": True,
        "result_decode_valid": True,
        "bounded_dimensions_passed": (
            first["result_width"] == case["output_width"]
            and first["result_height"] == case["output_height"]
        ),
        "source_checksum_unchanged": True,
        "m4_replay_bytes_equal": bytes_equal,
        "m4_replay_dimensions_equal": dimensions_equal,
        "changed_pixel_count_equal": first["changed_pixel_count"] == second["changed_pixel_count"],
        "changed_pixel_count_positive": changed_pixel_count > 0,
        "immutable_result_binding_passed": True,
        "exact_lineage_passed": True,
        "target_and_controls_complete": True,
    }
    values["structure_gate_passed"] = all(values.values())
    return values


def _validate_r2_decode_structure_record(
    value: object,
    *,
    case_entry: Mapping[str, object],
    source_entry: Mapping[str, object],
    m4_first: Mapping[str, object],
    m4_second: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> Mapping[str, Any]:
    case = _validate_r2_case_manifest_entry(case_entry, execution_authority=execution_authority)
    first = _validate_r2_m4_execution_record(m4_first, case=case, source=source_entry)
    second = _validate_r2_m4_execution_record(m4_second, case=case, source=source_entry)
    if first["replay_index"] != 1 or second["replay_index"] != 2:
        _fail("R2 structure M4 replay order is invalid")
    record = _exact(value, set(legacy._STRUCTURE_KEYS), "R2 decode structure record")
    _reject_noncanonical_json(record)
    if record["schema_version"] != R2_STRUCTURE_SCHEMA:
        _fail("R2 decode structure schema is invalid")
    for key in (
        "case_specification_digest",
        "source_asset_sha256",
        "result_sha256",
        "record_digest",
    ):
        _digest(record[key], f"R2 structure {key}")
    for key in ("case_id", "source_asset_id", "result_image_record_id"):
        _id(record[key], f"R2 structure {key}")
    _opaque_output_id(record["result_output_id"], "R2 structure result output ID")
    if (
        record["case_id"] != case["case_id"]
        or record["case_specification_digest"] != case["case_specification_digest"]
        or record["source_asset_id"] != case["source_asset_id"]
        or record["source_asset_sha256"] != case["source_asset_sha256"]
        or record["m4_execution_record_digests"]
        != [first["record_digest"], second["record_digest"]]
    ):
        _fail("R2 decode structure case or M4 binding is invalid")
    for key in (
        "result_output_id",
        "result_sha256",
        "result_byte_size",
        "result_mime_type",
        "result_width",
        "result_height",
    ):
        if record[key] != first[key]:
            _fail("R2 decode structure result binding is invalid")
    for key, expected in _r2_structure_values(case, first, second).items():
        if _bool(record[key], f"R2 structure {key}") != expected:
            _fail("R2 decode structure gate is not derived")
    _replay_member(record, R2_STRUCTURE_SCHEMA, "R2 decode structure")
    return record


def _validate_r2_manual_artifact_decision(
    value: object,
    *,
    case_entry: Mapping[str, object],
    source_entry: Mapping[str, object],
    m4_first: Mapping[str, object],
    execution_authority: Mapping[str, object],
    expected_sequence: int | None = None,
) -> Mapping[str, Any]:
    case = _validate_r2_case_manifest_entry(case_entry, execution_authority=execution_authority)
    first = _validate_r2_m4_execution_record(m4_first, case=case, source=source_entry)
    record = _exact(value, set(legacy._MANUAL_KEYS), "R2 manual artifact decision")
    _reject_noncanonical_json(record)
    if record["schema_version"] != R2_MANUAL_SCHEMA:
        _fail("R2 manual artifact decision schema is invalid")
    for key in (
        "result_sha256",
        "manual_review_policy_digest",
        "review_authority_digest",
        "manual_decision_digest",
    ):
        _digest(record[key], f"R2 manual {key}")
    _id(record["case_id"], "R2 manual case ID")
    if record["case_id"] != case["case_id"] or record["result_sha256"] != first["result_sha256"]:
        _fail("R2 manual decision case or result binding is invalid")
    authority = _r2_execution_authority(execution_authority)
    if record["manual_review_policy_digest"] != authority["manual_review_policy_digest"]:
        _fail("R2 manual review policy binding is invalid")
    if (
        not isinstance(record["manual_review_version"], str)
        or legacy._VERSION.fullmatch(record["manual_review_version"]) is None
    ):
        _fail("R2 manual review version is invalid")
    if type(record["decision_sequence"]) is not int or not 1 <= record["decision_sequence"] <= 48:
        _fail("R2 manual decision sequence is invalid")
    if expected_sequence is not None and record["decision_sequence"] != expected_sequence:
        _fail("R2 manual decision sequence order is invalid")
    artifacts = tuple(
        _bool(record[key], f"R2 manual {key}")
        for key in ("background_seam", "disconnected_contour", "duplicated_feature", "warp_tear")
    )
    if record["verdict"] != ("FAIL" if any(artifacts) else "PASS"):
        _fail("R2 manual verdict is not derived")
    _replay_member(record, R2_MANUAL_SCHEMA, "R2 manual decision")
    return record


def _validate_r2_upstream_execution_graph(
    payload: Mapping[str, Any], *, source_packets: Sequence[Mapping[str, object]] | None
) -> None:
    """Replay groups 1--9 against the four validated R2 admission packets.

    The remaining Report groups intentionally remain owned by their later
    checkpoint.  This function is the non-circular boundary: every v2/v3/v4
    execution record is verified from already-admitted source and case state.
    """
    if source_packets is None or len(source_packets) != 4:
        _fail("R2 upstream graph requires four validated admission packets")
    sources_raw = payload["ordered_source_manifest"]
    if not isinstance(sources_raw, list) or len(sources_raw) != 4:
        _fail("R2 upstream source manifest count is invalid")
    sources: list[Mapping[str, Any]] = []
    for ordinal, (entry, packet) in enumerate(
        zip(sources_raw, source_packets, strict=True), start=1
    ):
        validate_r2_admission_packet(packet)
        if entry != packet["source_manifest_entry"] or entry.get("source_ordinal") != ordinal:
            _fail("R2 upstream source manifest is not the validated packet projection")
        sources.append(cast(Mapping[str, Any], entry))
    source_manifest_digest = legacy._sequence_digest(R2_SOURCE_MANIFEST_SCHEMA, sources_raw)
    binding = _r2_execution_authority(cast(Mapping[str, object], payload["schema_and_policy"]))
    if binding["source_manifest_digest"] != source_manifest_digest:
        _fail("R2 execution authority source manifest binding is invalid")

    cases_raw = payload["ordered_case_manifest"]
    if not isinstance(cases_raw, list) or len(cases_raw) != 48:
        _fail("R2 upstream case manifest count is invalid")
    cases: list[Mapping[str, Any]] = []
    for index, raw in enumerate(cases_raw):
        case_entry = _validate_r2_case_manifest_entry(raw, execution_authority=binding)
        source_index, dim_index, direction_index, magnitude_index = (
            index // 12,
            index % 12 // 4,
            index % 4 // 2,
            index % 2,
        )
        source = sources[source_index]
        if (
            case_entry["case_ordinal"] != index + 1
            or case_entry["source_ordinal"] != source_index + 1
            or case_entry["dimension_key"] != legacy.CASE_DIMENSIONS[dim_index]
            or case_entry["direction"] != legacy.CASE_DIRECTIONS[direction_index]
            or case_entry["magnitude_ppm"] != legacy.CASE_MAGNITUDES[magnitude_index]
            or case_entry["priority_index"] != dim_index + 1
            or case_entry["direction_index"] != direction_index + 1
            or case_entry["magnitude_index"] != magnitude_index + 1
            or case_entry["source_manifest_digest"] != source_manifest_digest
        ):
            _fail("R2 case manifest natural order is invalid")
        for key in (
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "source_asset_sha256",
            "source_qa_snapshot_digest",
            "source_measurement_projection_digest",
            "source_p2_candidate_manifest_content_digest",
            "dimension_authority_manifest_content_digest",
            "r2_source_authority_record_id",
        ):
            if case_entry[key] != source[key]:
                _fail("R2 case source authority binding is invalid")
        cases.append(case_entry)
    case_manifest_digest = _r2_case_manifest_digest(cases_raw)
    if binding["case_manifest_digest"] != case_manifest_digest:
        _fail("R2 execution authority case manifest binding is invalid")

    source_m3 = payload["source_m3_repeat_evidence"]
    if not isinstance(source_m3, list) or len(source_m3) != 12:
        _fail("R2 SourceM3 count is invalid")
    for index, raw in enumerate(source_m3):
        source = sources[index // 3]
        packet = source_packets[index // 3]
        facts = packet.get("facts")
        if not isinstance(facts, Mapping):
            _fail("R2 SourceM3 admission facts are invalid")
        record = _validate_r2_source_m3_record(
            raw,
            source=source,
            facts=facts,
            source_manifest_digest=source_manifest_digest,
            execution_authority=binding,
        )
        if record["repeat_index"] != index % 3 + 1:
            _fail("R2 SourceM3 schema or order is invalid")

    m4_records = payload["m4_repeat_evidence"]
    if not isinstance(m4_records, list) or len(m4_records) != 96:
        _fail("R2 M4 count is invalid")
    parsed_m4: list[Mapping[str, Any]] = []
    seen_m4_ids: set[str] = set()
    seen_m4_digests: set[str] = set()
    for index, raw in enumerate(m4_records):
        case = cases[index // 2]
        source = sources[int(case["source_ordinal"]) - 1]
        record = _validate_r2_m4_execution_record(raw, case=case, source=source)
        if record["replay_index"] != index % 2 + 1:
            _fail("R2 M4 natural replay order is invalid")
        for value, seen, label in (
            (record["m4_execution_record_id"], seen_m4_ids, "record ID"),
            (record["record_digest"], seen_m4_digests, "record digest"),
        ):
            if value in seen:
                _fail(f"R2 M4 duplicate {label}")
            seen.add(cast(str, value))
        parsed_m4.append(record)
        if record["replay_index"] == 2:
            first = parsed_m4[index - 1]
            for key in (
                "case_id",
                "case_specification_digest",
                "source_output_id",
                "source_asset_id",
                "source_asset_sha256",
                "result_output_id",
                "result_sha256",
                "result_byte_size",
                "result_mime_type",
                "result_width",
                "result_height",
                "changed_pixel_count",
                "warp_plan_digest",
                "geometry_algorithm_version",
                "runtime_manifest_digest",
                "runtime_config_digest",
                "determinism_level",
            ):
                if record[key] != first[key]:
                    _fail("R2 M4 replay pair is not byte/dimension deterministic")

    results = payload["result_m3_repeat_evidence"]
    if not isinstance(results, list) or len(results) != 144:
        _fail("R2 ResultM3 count is invalid")
    parsed_results: list[Mapping[str, Any]] = []
    for index, raw in enumerate(results):
        record = _validate_r2_result_m3_record(raw)
        case = cases[index // 3]
        first_m4 = parsed_m4[index // 3 * 2]
        if record["repeat_index"] != index % 3 + 1:
            _fail("R2 ResultM3 schema or order is invalid")
        if (
            any(record[key] != case[key] for key in ("case_id", "case_specification_digest"))
            or any(record[key] != first_m4[key] for key in ("result_output_id", "result_sha256"))
            or record["runtime_manifest_digest"] != case["runtime_manifest_digest"]
            or record["runtime_manifest_digest"] != binding["runtime_manifest_digest"]
            or record["vision_model_manifest_digest"] != binding["vision_model_manifest_digest"]
            or record["topology_digest"] != binding["topology_digest"]
        ):
            _fail("R2 ResultM3 case or M4 binding is invalid")
        parsed_results.append(record)

    gates = payload["measurement_gate_evidence"]
    if not isinstance(gates, list) or len(gates) != 48:
        _fail("R2 measurement gate count is invalid")
    parsed_gates: list[Mapping[str, Any]] = []
    for index, raw in enumerate(gates):
        case = cases[index]
        facts = source_packets[index // 12].get("facts")
        if not isinstance(facts, Mapping):
            _fail("R2 measurement gate admission facts are invalid")
        gate = _validate_r2_measurement_gate(
            raw,
            result_records=parsed_results[index * 3 : index * 3 + 3],
            facts=facts,
        )
        if any(
            gate[key] != case[key]
            for key in ("case_id", "case_specification_digest", "dimension_key")
        ):
            _fail("R2 measurement gate case binding is invalid")
        if (
            gate["requested_direction"] != case["direction"]
            or gate["requested_magnitude_ppm"] != case["magnitude_ppm"]
        ):
            _fail("R2 measurement gate requested delta binding is invalid")
        peer = cases[index + 1 if index % 2 == 0 else index - 1]
        if gate["monotonicity_peer_case_id"] != peer["case_id"]:
            _fail("R2 measurement gate monotonicity peer binding is invalid")
        parsed_gates.append(gate)
    for lower_index in range(0, 48, 2):
        lower, upper = parsed_gates[lower_index : lower_index + 2]
        lower_state = lower["measurement_evaluation_state"]
        upper_state = upper["measurement_evaluation_state"]
        if lower_state == upper_state == "SUPPORTED_EVALUATED":
            lower_measurements = cast(
                list[Mapping[str, Any]], lower["ordered_result_repeat_measurements"]
            )
            upper_measurements = cast(
                list[Mapping[str, Any]], upper["ordered_result_repeat_measurements"]
            )
            expected = all(
                legacy._fixed18_units(
                    upper_item["raw_target_absolute_delta_fixed18"],
                    "R2 upper magnitude target delta",
                )
                >= legacy._fixed18_units(
                    lower_item["raw_target_absolute_delta_fixed18"],
                    "R2 lower magnitude target delta",
                )
                for lower_item, upper_item in zip(
                    lower_measurements, upper_measurements, strict=True
                )
            )
            for gate in (lower, upper):
                evaluation = cast(Mapping[str, Any], gate["gate_evaluation"])
                if (
                    legacy._bool(
                        evaluation["magnitude_monotonicity_gate_passed"],
                        "R2 magnitude monotonicity gate",
                    )
                    != expected
                ):
                    _fail("R2 magnitude peer monotonicity does not replay raw fixed18 evidence")
        elif "SUPPORTED_EVALUATED" in {lower_state, upper_state}:
            supported = lower if lower_state == "SUPPORTED_EVALUATED" else upper
            evaluation = cast(Mapping[str, Any], supported["gate_evaluation"])
            if legacy._bool(
                evaluation["magnitude_monotonicity_gate_passed"],
                "R2 mixed-peer monotonicity gate",
            ) or legacy._bool(evaluation["measurement_gate_passed"], "R2 mixed-peer gate"):
                _fail("R2 supported measurement with unsupported magnitude peer must fail closed")

    structures = payload["decode_structure_immutability_evidence"]
    if not isinstance(structures, list) or len(structures) != 48:
        _fail("R2 decode structure count is invalid")
    seen_structure_digests: set[str] = set()
    for index, raw in enumerate(structures):
        case = cases[index]
        first, second = parsed_m4[index * 2 : index * 2 + 2]
        source = sources[int(case["source_ordinal"]) - 1]
        record = _validate_r2_decode_structure_record(
            raw,
            case_entry=case,
            source_entry=source,
            m4_first=first,
            m4_second=second,
            execution_authority=binding,
        )
        digest = cast(str, record["record_digest"])
        if digest in seen_structure_digests:
            _fail("R2 decode structure evidence has duplicate record digest")
        seen_structure_digests.add(digest)

    manuals = payload["manual_review_evidence"]
    if not isinstance(manuals, list) or len(manuals) != 48:
        _fail("R2 manual decision count is invalid")
    by_id = {
        cast(str, case["case_id"]): (index, case, parsed_m4[index * 2])
        for index, case in enumerate(cases)
    }
    previous = ""
    seen_manual_digests: set[str] = set()
    for sequence, raw in enumerate(manuals, start=1):
        if not isinstance(raw, Mapping):
            _fail("R2 manual decision must be an object")
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or case_id not in by_id or case_id <= previous:
            _fail("R2 manual decisions are not case-ID ordered")
        previous = case_id
        _, case, first = by_id[case_id]
        source = sources[int(case["source_ordinal"]) - 1]
        manual = _validate_r2_manual_artifact_decision(
            raw,
            case_entry=case,
            source_entry=source,
            m4_first=first,
            execution_authority=binding,
            expected_sequence=sequence,
        )
        digest = cast(str, manual["manual_decision_digest"])
        if digest in seen_manual_digests:
            _fail("R2 manual review evidence has duplicate decision digest")
        seen_manual_digests.add(digest)


def build_r2_case_manifest_entry(
    fields: Mapping[str, object], *, execution_authority: Mapping[str, object]
) -> dict[str, JsonValue]:
    """Sign one R2 CaseEntry/v4 after its source projection is fixed."""
    _exact(
        fields,
        R2_CASE_KEYS
        - {
            "schema_version",
            "case_id",
            "execution_config_digest",
            "case_specification_digest",
            "record_digest",
        },
        "R2 case input",
    )
    authority = _r2_execution_authority(execution_authority)
    result: dict[str, JsonValue] = {
        "schema_version": R2_CASE_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    result["execution_config_digest"] = _r2_case_execution_digest(result, authority)
    result["case_id"] = _r2_case_id(result)
    result["case_specification_digest"] = _r2_case_specification_digest(result)
    result["record_digest"] = mirror_demo_digest(
        R2_CASE_SCHEMA,
        {
            key: value
            for key, value in result.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    _validate_r2_case_manifest_entry(result, execution_authority=authority)
    return result


def build_r2_source_m3_record(
    fields: Mapping[str, object], *, source_manifest_digest: str
) -> dict[str, JsonValue]:
    """Sign SourceM3/v3 with its frozen R2 source-manifest ID preimage."""
    _exact(
        fields,
        R2_SOURCE_M3_KEYS - {"schema_version", "source_m3_record_id", "record_digest"},
        "R2 SourceM3 input",
    )
    result: dict[str, JsonValue] = {
        "schema_version": R2_SOURCE_M3_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    result["source_m3_record_id"] = derive_r2_source_m3_record_id(
        source_manifest_digest=source_manifest_digest,
        source_authority_key=cast(str, result["source_authority_key"]),
        source_admission_event_id=cast(str, result["source_admission_event_id"]),
        source_asset_id=cast(str, result["source_asset_id"]),
        source_asset_sha256=cast(str, result["source_asset_sha256"]),
        repeat_index=cast(int, result["repeat_index"]),
        vision_model_manifest_digest=cast(str, result["vision_model_manifest_digest"]),
        runtime_manifest_digest=cast(str, result["runtime_manifest_digest"]),
        topology_digest=cast(str, result["topology_digest"]),
    )
    result["record_digest"] = mirror_demo_digest(
        R2_SOURCE_M3_SCHEMA,
        {
            key: value
            for key, value in result.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    return result


def build_r2_m4_execution_record(fields: Mapping[str, object]) -> dict[str, JsonValue]:
    """Sign M4/v2 with its frozen R2 record-ID preimage."""
    _exact(
        fields,
        set(legacy._M4_EXECUTION_KEYS)
        - {"schema_version", "m4_execution_record_id", "record_digest"},
        "R2 M4 input",
    )
    result: dict[str, JsonValue] = {
        "schema_version": R2_M4_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    result["m4_execution_record_id"] = mirror_demo_digest(
        R2_M4_ID_DOMAIN,
        cast(
            dict[str, JsonValue],
            {
                key: result[key]
                for key in (
                    "case_id",
                    "case_specification_digest",
                    "replay_index",
                    "geometry_algorithm_version",
                    "runtime_manifest_digest",
                    "runtime_config_digest",
                    "determinism_level",
                )
            },
        ),
    )[:32]
    result["record_digest"] = mirror_demo_digest(
        R2_M4_SCHEMA,
        {
            key: value
            for key, value in result.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    return result


def build_r2_result_m3_record(fields: Mapping[str, object]) -> dict[str, JsonValue]:
    """Sign ResultM3/v3 without altering the frozen observation primitive."""
    _exact(
        fields,
        set(legacy._RESULT_M3_KEYS) - {"schema_version", "result_m3_record_id", "record_digest"},
        "R2 ResultM3 input",
    )
    result: dict[str, JsonValue] = {
        "schema_version": R2_RESULT_M3_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    result["result_m3_record_id"] = mirror_demo_digest(
        R2_RESULT_M3_ID_DOMAIN,
        cast(
            dict[str, JsonValue],
            {
                key: result[key]
                for key in (
                    "case_id",
                    "case_specification_digest",
                    "result_output_id",
                    "result_sha256",
                    "repeat_index",
                    "runtime_manifest_digest",
                    "vision_model_manifest_digest",
                    "topology_digest",
                )
            },
        ),
    )[:32]
    result["record_digest"] = mirror_demo_digest(
        R2_RESULT_M3_SCHEMA,
        {
            key: value
            for key, value in result.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    return result


def build_r2_measurement_gate(fields: Mapping[str, object]) -> dict[str, JsonValue]:
    _exact(
        fields,
        set(legacy._GATE_KEYS) - {"schema_version", "record_digest"},
        "R2 measurement gate input",
    )
    result: dict[str, JsonValue] = {
        "schema_version": R2_GATE_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    result["record_digest"] = mirror_demo_digest(
        R2_GATE_SCHEMA,
        {
            key: value
            for key, value in result.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    return result


def build_r2_decode_structure_record(
    fields: Mapping[str, object],
    *,
    case_entry: Mapping[str, object],
    source_entry: Mapping[str, object],
    m4_first: Mapping[str, object],
    m4_second: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> dict[str, JsonValue]:
    _exact(fields, set(legacy._STRUCTURE_BUILD_FIELDS), "R2 decode structure input")
    case = _validate_r2_case_manifest_entry(case_entry, execution_authority=execution_authority)
    first = _validate_r2_m4_execution_record(m4_first, case=case, source=source_entry)
    second = _validate_r2_m4_execution_record(m4_second, case=case, source=source_entry)
    result: dict[str, JsonValue] = {
        "schema_version": R2_STRUCTURE_SCHEMA,
        "case_id": cast(str, case["case_id"]),
        "case_specification_digest": cast(str, case["case_specification_digest"]),
        "source_asset_id": cast(str, case["source_asset_id"]),
        "source_asset_sha256": cast(str, case["source_asset_sha256"]),
        "m4_execution_record_digests": [first["record_digest"], second["record_digest"]],
        **{
            key: cast(JsonValue, first[key])
            for key in (
                "result_output_id",
                "result_sha256",
                "result_byte_size",
                "result_mime_type",
                "result_width",
                "result_height",
            )
        },
        **cast(dict[str, JsonValue], dict(fields)),
        **_r2_structure_values(case, first, second),
    }
    result["record_digest"] = mirror_demo_digest(
        R2_STRUCTURE_SCHEMA,
        {
            key: value
            for key, value in result.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    _validate_r2_decode_structure_record(
        result,
        case_entry=case,
        source_entry=source_entry,
        m4_first=first,
        m4_second=second,
        execution_authority=execution_authority,
    )
    return result


def build_r2_manual_artifact_decision(
    fields: Mapping[str, object],
    *,
    case_entry: Mapping[str, object],
    source_entry: Mapping[str, object],
    m4_first: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> dict[str, JsonValue]:
    _exact(fields, set(legacy._MANUAL_BUILD_FIELDS), "R2 manual decision input")
    case = _validate_r2_case_manifest_entry(case_entry, execution_authority=execution_authority)
    first = _validate_r2_m4_execution_record(m4_first, case=case, source=source_entry)
    artifacts = [
        _bool(fields[key], f"R2 manual {key}")
        for key in ("background_seam", "disconnected_contour", "duplicated_feature", "warp_tear")
    ]
    authority = _r2_execution_authority(execution_authority)
    result: dict[str, JsonValue] = {
        "schema_version": R2_MANUAL_SCHEMA,
        "case_id": cast(str, case["case_id"]),
        "result_sha256": cast(str, first["result_sha256"]),
        "manual_review_policy_digest": cast(str, authority["manual_review_policy_digest"]),
        **cast(dict[str, JsonValue], dict(fields)),
        "verdict": "FAIL" if any(artifacts) else "PASS",
    }
    result["manual_decision_digest"] = mirror_demo_digest(
        R2_MANUAL_SCHEMA,
        {
            key: value
            for key, value in result.items()
            if key not in {"schema_version", "manual_decision_digest"}
        },
    )
    _validate_r2_manual_artifact_decision(
        result,
        case_entry=case,
        source_entry=source_entry,
        m4_first=first,
        execution_authority=authority,
    )
    return result


def _r2_image_execution_context(
    *,
    source_packets: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> tuple[
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    Mapping[str, Any],
]:
    """Replay the R2 source/Case/M4 roots needed by image and pair authority."""

    if len(source_packets) != 4 or len(case_manifest) != 48 or len(m4_records) != 96:
        _fail("R2 image authority requires four sources, 48 cases, and 96 M4 records")
    authority = _r2_execution_authority(execution_authority)
    sources: list[Mapping[str, Any]] = []
    for ordinal, packet in enumerate(source_packets, start=1):
        validate_r2_admission_packet(packet)
        source = packet.get("source_manifest_entry")
        if not isinstance(source, Mapping) or source.get("source_ordinal") != ordinal:
            _fail("R2 image authority source packet order is invalid")
        sources.append(cast(Mapping[str, Any], source))
    source_manifest_digest = legacy._sequence_digest(
        R2_SOURCE_MANIFEST_SCHEMA, cast(Sequence[Mapping[str, object]], sources)
    )
    if authority["source_manifest_digest"] != source_manifest_digest:
        _fail("R2 image authority source manifest binding is invalid")

    cases: list[Mapping[str, Any]] = []
    for index, raw in enumerate(case_manifest):
        case = _validate_r2_case_manifest_entry(raw, execution_authority=authority)
        source_index, dimension_index, direction_index, magnitude_index = (
            index // 12,
            index % 12 // 4,
            index % 4 // 2,
            index % 2,
        )
        source = sources[source_index]
        if (
            case["case_ordinal"] != index + 1
            or case["source_ordinal"] != source_index + 1
            or case["dimension_key"] != legacy.CASE_DIMENSIONS[dimension_index]
            or case["direction"] != legacy.CASE_DIRECTIONS[direction_index]
            or case["magnitude_ppm"] != legacy.CASE_MAGNITUDES[magnitude_index]
            or case["source_manifest_digest"] != source_manifest_digest
        ):
            _fail("R2 image authority case order is invalid")
        for key in (
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "source_asset_sha256",
            "r2_source_authority_record_id",
        ):
            if case[key] != source[key]:
                _fail("R2 image authority case/source binding is invalid")
        cases.append(case)
    if authority["case_manifest_digest"] != _r2_case_manifest_digest(case_manifest):
        _fail("R2 image authority case manifest binding is invalid")

    parsed_m4: list[Mapping[str, Any]] = []
    for index, raw in enumerate(m4_records):
        case = cases[index // 2]
        source = sources[int(case["source_ordinal"]) - 1]
        record = _validate_r2_m4_execution_record(raw, case=case, source=source)
        if record["replay_index"] != index % 2 + 1:
            _fail("R2 image authority M4 order is invalid")
        parsed_m4.append(record)
        if index % 2 == 1:
            first = parsed_m4[index - 1]
            for key in (
                "result_output_id",
                "result_sha256",
                "result_byte_size",
                "result_mime_type",
                "result_width",
                "result_height",
                "changed_pixel_count",
            ):
                if record[key] != first[key]:
                    _fail("R2 image authority M4 replay is not deterministic")
    return sources, cases, parsed_m4, authority


def _expected_r2_result_variant_binding(
    case: Mapping[str, Any], first_m4: Mapping[str, Any]
) -> dict[str, JsonValue]:
    result_asset_id = legacy.derive_imported_asset_id(
        asset_role="synthetic",
        semantic_role="SELECTED_RESULT",
        sha256=first_m4["result_sha256"],
        byte_size=first_m4["result_byte_size"],
        mime_type=first_m4["result_mime_type"],
        width=first_m4["result_width"],
        height=first_m4["result_height"],
    )
    variant_id = legacy.derive_asset_variant_id(
        variant_type=legacy.VARIANT_TYPE,
        source_asset_id=case["source_asset_id"],
        source_asset_sha256=case["source_asset_sha256"],
        result_asset_id=result_asset_id,
        result_asset_sha256=first_m4["result_sha256"],
        case_specification_digest=case["case_specification_digest"],
    )
    return {
        "source_asset_id": cast(str, case["source_asset_id"]),
        "source_asset_sha256": cast(str, case["source_asset_sha256"]),
        "result_asset_id": result_asset_id,
        "result_asset_sha256": cast(str, first_m4["result_sha256"]),
        "asset_variant_id": variant_id,
        "asset_variant_type": legacy.VARIANT_TYPE,
        "case_specification_digest": cast(str, case["case_specification_digest"]),
    }


def _r2_result_variant_bindings_from_context(
    cases: Sequence[Mapping[str, Any]], m4_records: Sequence[Mapping[str, Any]]
) -> dict[str, Mapping[str, Any]]:
    variants: dict[str, Mapping[str, Any]] = {}
    variant_ids: set[str] = set()
    for index, case in enumerate(cases):
        case_id = cast(str, case["case_id"])
        binding = _expected_r2_result_variant_binding(case, m4_records[index * 2])
        variant_id = cast(str, binding["asset_variant_id"])
        # Result Assets are content addressed.  Two independently executed
        # cases may therefore bind the same Asset when their result bytes and
        # immutable descriptor are identical.  Preserve all 48 case-specific
        # bindings here and let the 52-image exact-SHA outcome Gate classify
        # that duplicate as a complete FAILED Report.  AssetVariant remains
        # case-specific and must never collapse across cases.
        if variant_id in variant_ids:
            _fail("R2 result AssetVariant authority is duplicated")
        variant_ids.add(variant_id)
        variants[case_id] = binding
    if len(variants) != 48:
        _fail("R2 result AssetVariant authority must cover exactly 48 cases")
    return variants


def build_r2_result_variant_bindings(
    *,
    source_packets: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> dict[str, Mapping[str, Any]]:
    """Derive deterministic result Asset and AssetVariant IDs for all R2 cases."""

    _, cases, parsed_m4, _ = _r2_image_execution_context(
        source_packets=source_packets,
        case_manifest=case_manifest,
        m4_records=m4_records,
        execution_authority=execution_authority,
    )
    return _r2_result_variant_bindings_from_context(cases, parsed_m4)


def _r2_image_record_id(schema: str, value: Mapping[str, object]) -> str:
    fields: tuple[str, ...]
    if schema == R2_SOURCE_IMAGE_SCHEMA:
        fields = (
            "authority_role",
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "sha256",
        )
        domain = R2_SOURCE_IMAGE_ID_DOMAIN
    elif schema == R2_RESULT_IMAGE_SCHEMA:
        fields = (
            "authority_role",
            "source_authority_key",
            "source_admission_event_id",
            "case_id",
            "case_specification_digest",
            "result_output_id",
            "deterministic_result_asset_id",
            "sha256",
        )
        domain = R2_RESULT_IMAGE_ID_DOMAIN
    else:
        _fail("R2 image record schema is invalid")
    return mirror_demo_digest(domain, {key: cast(JsonValue, value[key]) for key in fields})[:32]


def _r2_image_record_digest(schema: str, record: Mapping[str, object]) -> str:
    return mirror_demo_digest(
        schema,
        {
            key: cast(JsonValue, value)
            for key, value in record.items()
            if key not in {"schema_version", "image_record_digest"}
        },
    )


def _validate_r2_image_record_shape(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("R2 image authority record must be an object")
    schema = value.get("schema_version")
    if schema == R2_SOURCE_IMAGE_SCHEMA:
        record = _exact(value, set(legacy._SOURCE_IMAGE_KEYS), "R2 source image authority record")
        if record["authority_role"] != "SOURCE":
            _fail("R2 source image authority role is invalid")
    elif schema == R2_RESULT_IMAGE_SCHEMA:
        record = _exact(value, set(legacy._RESULT_IMAGE_KEYS), "R2 result image authority record")
        if record["authority_role"] != "RESULT":
            _fail("R2 result image authority role is invalid")
        for key in ("case_id", "deterministic_result_asset_id"):
            _id(record[key], f"R2 image {key}")
        _digest(record["case_specification_digest"], "R2 image case specification digest")
        _opaque_output_id(record["result_output_id"], "R2 image result output ID")
    else:
        _fail("R2 image authority record schema is invalid")
    _reject_noncanonical_json(record)
    if (
        type(record["image_record_ordinal"]) is not int
        or not 1 <= record["image_record_ordinal"] <= 52
    ):
        _fail("R2 image authority record ordinal is invalid")
    for key in ("image_record_id", "source_admission_event_id"):
        _id(record[key], f"R2 image {key}")
    if schema == R2_SOURCE_IMAGE_SCHEMA:
        _id(record["source_asset_id"], "R2 source image Asset ID")
    for key in ("source_authority_key", "sha256", "image_record_digest"):
        _digest(record[key], f"R2 image {key}")
    if type(record["source_ordinal"]) is not int or not 1 <= record["source_ordinal"] <= 4:
        _fail("R2 image source ordinal is invalid")
    if (
        type(record["byte_size"]) is not int
        or not 1 <= record["byte_size"] <= 9_223_372_036_854_775_807
    ):
        _fail("R2 image byte size is invalid")
    if record["mime_type"] != "image/jpeg":
        _fail("R2 image MIME type is invalid")
    for key in ("width", "height"):
        if type(record[key]) is not int or not 1 <= record[key] <= 2_147_483_647:
            _fail(f"R2 image {key} is invalid")
    if record["image_record_id"] != _r2_image_record_id(cast(str, schema), record):
        _fail("R2 image authority record ID does not replay")
    if record["image_record_digest"] != _r2_image_record_digest(cast(str, schema), record):
        _fail("R2 image authority record digest does not replay")
    return record


def _expected_r2_image_records_from_context(
    sources: Sequence[Mapping[str, Any]],
    cases: Sequence[Mapping[str, Any]],
    m4_records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, JsonValue]], dict[str, Mapping[str, Any]]]:
    variants = _r2_result_variant_bindings_from_context(cases, m4_records)
    records: list[dict[str, JsonValue]] = []
    for source in sources:
        record: dict[str, JsonValue] = {
            "schema_version": R2_SOURCE_IMAGE_SCHEMA,
            "authority_role": "SOURCE",
            "source_ordinal": cast(int, source["source_ordinal"]),
            "source_authority_key": cast(str, source["source_authority_key"]),
            "source_admission_event_id": cast(str, source["source_admission_event_id"]),
            "source_asset_id": cast(str, source["source_asset_id"]),
            "sha256": cast(str, source["source_asset_sha256"]),
            "byte_size": cast(int, source["source_asset_byte_size"]),
            "mime_type": cast(str, source["source_asset_mime_type"]),
            "width": cast(int, source["source_asset_width"]),
            "height": cast(int, source["source_asset_height"]),
        }
        record["image_record_id"] = _r2_image_record_id(R2_SOURCE_IMAGE_SCHEMA, record)
        records.append(record)
    for index, case in enumerate(cases):
        first = m4_records[index * 2]
        variant = variants[cast(str, case["case_id"])]
        record = {
            "schema_version": R2_RESULT_IMAGE_SCHEMA,
            "authority_role": "RESULT",
            "source_ordinal": cast(int, case["source_ordinal"]),
            "source_authority_key": cast(str, case["source_authority_key"]),
            "source_admission_event_id": cast(str, case["source_admission_event_id"]),
            "case_id": cast(str, case["case_id"]),
            "case_specification_digest": cast(str, case["case_specification_digest"]),
            "result_output_id": cast(str, first["result_output_id"]),
            "deterministic_result_asset_id": cast(str, variant["result_asset_id"]),
            "sha256": cast(str, first["result_sha256"]),
            "byte_size": cast(int, first["result_byte_size"]),
            "mime_type": cast(str, first["result_mime_type"]),
            "width": cast(int, first["result_width"]),
            "height": cast(int, first["result_height"]),
        }
        record["image_record_id"] = _r2_image_record_id(R2_RESULT_IMAGE_SCHEMA, record)
        records.append(record)
    records.sort(key=lambda item: (cast(str, item["sha256"]), cast(str, item["image_record_id"])))
    for ordinal, record in enumerate(records, start=1):
        record["image_record_ordinal"] = ordinal
        record["image_record_digest"] = _r2_image_record_digest(
            cast(str, record["schema_version"]), record
        )
    return records, variants


def build_r2_image_authority_evidence(
    *,
    source_packets: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> list[dict[str, JsonValue]]:
    """Build the complete four-source plus 48-result R2 image universe."""

    sources, cases, parsed_m4, _ = _r2_image_execution_context(
        source_packets=source_packets,
        case_manifest=case_manifest,
        m4_records=m4_records,
        execution_authority=execution_authority,
    )
    records, _ = _expected_r2_image_records_from_context(sources, cases, parsed_m4)
    return records


def _validate_r2_image_authority_evidence(
    image_records: Sequence[Mapping[str, object]],
    *,
    source_packets: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> list[Mapping[str, Any]]:
    if len(image_records) != 52:
        _fail("R2 image authority evidence must contain exactly 52 records")
    expected = build_r2_image_authority_evidence(
        source_packets=source_packets,
        case_manifest=case_manifest,
        m4_records=m4_records,
        execution_authority=execution_authority,
    )
    parsed = [_validate_r2_image_record_shape(record) for record in image_records]
    if parsed != expected:
        _fail("R2 image authority does not replay source/Case/M4 lineage")
    if [record["image_record_ordinal"] for record in parsed] != list(range(1, 53)):
        _fail("R2 image authority ordinal order is invalid")
    return parsed


def _r2_exact_duplicate_values(
    image_records: Sequence[Mapping[str, object]],
) -> dict[str, bool]:
    parsed = [_validate_r2_image_record_shape(record) for record in image_records]
    if len(parsed) != 52:
        _fail("R2 exact duplicate evidence must contain exactly 52 image records")
    source_sha = [
        cast(str, record["sha256"]) for record in parsed if record["authority_role"] == "SOURCE"
    ]
    result_sha = [
        cast(str, record["sha256"]) for record in parsed if record["authority_role"] == "RESULT"
    ]
    if len(source_sha) != 4 or len(result_sha) != 48:
        _fail("R2 exact duplicate source/result cardinality is invalid")
    values = {
        "all_record_sha_unique": len(set(source_sha + result_sha)) == 52,
        "source_sha_unique": len(set(source_sha)) == 4,
        "result_sha_unique": len(set(result_sha)) == 48,
        "source_result_sha_disjoint": set(source_sha).isdisjoint(result_sha),
    }
    values["exact_sha_gate_passed"] = all(values.values())
    return values


def build_r2_exact_duplicate_evidence(
    image_records: Sequence[Mapping[str, object]],
) -> dict[str, JsonValue]:
    return {
        "schema_version": legacy.EXACT_DUPLICATE_SCHEMA,
        "image_records": cast(list[JsonValue], list(image_records)),
        **_r2_exact_duplicate_values(image_records),
    }


def _validate_r2_exact_duplicate_evidence(
    value: object,
    *,
    expected_image_records: Sequence[Mapping[str, object]],
) -> Mapping[str, Any]:
    evidence = _exact(value, set(legacy._EXACT_DUPLICATE_KEYS), "R2 exact duplicate evidence")
    if evidence["schema_version"] != legacy.EXACT_DUPLICATE_SCHEMA:
        _fail("R2 exact duplicate evidence schema is invalid")
    image_records = evidence["image_records"]
    if not isinstance(image_records, list) or image_records != list(expected_image_records):
        _fail("R2 exact duplicate image authority is not the complete graph projection")
    expected = _r2_exact_duplicate_values(cast(list[Mapping[str, object]], image_records))
    for key, result in expected.items():
        if _bool(evidence[key], f"R2 exact duplicate {key}") != result:
            _fail("R2 exact duplicate Gate booleans do not replay")
    return evidence


def _r2_phash_signature_digest(record: Mapping[str, object]) -> str:
    return legacy._digest_for(
        legacy.PHASH_SIGNATURE_SCHEMA, record, {"schema_version", "signature_digest"}
    )


def _r2_phash_comparison_digest(record: Mapping[str, object]) -> str:
    return legacy._digest_for(
        legacy.PHASH_COMPARISON_SCHEMA, record, {"schema_version", "comparison_digest"}
    )


def _r2_phash_hex(value: object) -> str:
    if not isinstance(value, str) or _PHASH_HEX.fullmatch(value) is None:
        _fail("R2 pHash signature must be exactly 16 lowercase hexadecimal characters")
    return value


def build_r2_phash_observation_evidence(
    *,
    image_records: Sequence[Mapping[str, object]],
    image_phashes: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> dict[str, JsonValue]:
    if len(image_records) != 52:
        _fail("R2 pHash evidence requires exactly 52 image records")
    images = [_validate_r2_image_record_shape(record) for record in image_records]
    if [record["image_record_ordinal"] for record in images] != list(range(1, 53)):
        _fail("R2 pHash image ordinal order is invalid")
    if set(image_phashes) != {cast(str, record["image_record_id"]) for record in images}:
        _fail("R2 pHash signatures must bind exactly the 52 image record IDs")
    implementation_digest = cast(
        str, _r2_execution_authority(execution_authority)["phash_implementation_digest"]
    )
    signatures: list[dict[str, JsonValue]] = []
    for image in images:
        signature: dict[str, JsonValue] = {
            "schema_version": legacy.PHASH_SIGNATURE_SCHEMA,
            "image_record_ordinal": cast(int, image["image_record_ordinal"]),
            "image_record_id": cast(str, image["image_record_id"]),
            "image_record_digest": cast(str, image["image_record_digest"]),
            "image_sha256": cast(str, image["sha256"]),
            "phash_hex": _r2_phash_hex(image_phashes[cast(str, image["image_record_id"])]),
        }
        signature["signature_digest"] = _r2_phash_signature_digest(signature)
        signatures.append(signature)
    comparisons: list[dict[str, JsonValue]] = []
    comparison_ordinal = 1
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index + 1 :]:
            distance = (
                int(cast(str, left["phash_hex"]), 16) ^ int(cast(str, right["phash_hex"]), 16)
            ).bit_count()
            comparison: dict[str, JsonValue] = {
                "schema_version": legacy.PHASH_COMPARISON_SCHEMA,
                "comparison_ordinal": comparison_ordinal,
                "left_image_record_ordinal": left["image_record_ordinal"],
                "left_image_record_id": left["image_record_id"],
                "left_signature_digest": left["signature_digest"],
                "right_image_record_ordinal": right["image_record_ordinal"],
                "right_image_record_id": right["image_record_id"],
                "right_signature_digest": right["signature_digest"],
                "hamming_distance": distance,
            }
            comparison["comparison_digest"] = _r2_phash_comparison_digest(comparison)
            comparisons.append(comparison)
            comparison_ordinal += 1
    return {
        "schema_version": legacy.PHASH_EVIDENCE_SCHEMA,
        "implementation_digest": implementation_digest,
        "bit_width": 64,
        "threshold_policy": "OBSERVATION_ONLY_NO_THRESHOLD",
        "ordered_record_signatures": cast(list[JsonValue], signatures),
        "comparisons": cast(list[JsonValue], comparisons),
    }


def _validate_r2_phash_observation_evidence(
    value: object,
    *,
    image_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> Mapping[str, Any]:
    evidence = _exact(value, set(legacy._PHASH_EVIDENCE_KEYS), "R2 pHash observation evidence")
    if evidence["schema_version"] != legacy.PHASH_EVIDENCE_SCHEMA:
        _fail("R2 pHash observation evidence schema is invalid")
    if (
        evidence["implementation_digest"]
        != _r2_execution_authority(execution_authority)["phash_implementation_digest"]
    ):
        _fail("R2 pHash implementation digest binding is invalid")
    if evidence["bit_width"] != 64 or evidence["threshold_policy"] != (
        "OBSERVATION_ONLY_NO_THRESHOLD"
    ):
        _fail("R2 pHash observation policy is invalid")
    images = [_validate_r2_image_record_shape(record) for record in image_records]
    signatures = evidence["ordered_record_signatures"]
    comparisons = evidence["comparisons"]
    if not isinstance(signatures, list) or len(signatures) != 52:
        _fail("R2 pHash evidence must contain exactly 52 ordered signatures")
    if not isinstance(comparisons, list) or len(comparisons) != 1326:
        _fail("R2 pHash evidence must contain exactly 1326 ordered comparisons")
    parsed_signatures: list[Mapping[str, Any]] = []
    for image, raw in zip(images, signatures, strict=True):
        signature = _exact(raw, set(legacy._PHASH_SIGNATURE_KEYS), "R2 pHash signature")
        if signature["schema_version"] != legacy.PHASH_SIGNATURE_SCHEMA:
            _fail("R2 pHash signature schema is invalid")
        if signature["image_record_ordinal"] != image["image_record_ordinal"] or any(
            signature[key] != image[image_key]
            for key, image_key in (
                ("image_record_id", "image_record_id"),
                ("image_record_digest", "image_record_digest"),
                ("image_sha256", "sha256"),
            )
        ):
            _fail("R2 pHash signature image binding is invalid")
        _r2_phash_hex(signature["phash_hex"])
        if signature["signature_digest"] != _r2_phash_signature_digest(signature):
            _fail("R2 pHash signature digest does not replay")
        parsed_signatures.append(signature)
    comparison_ordinal = 1
    for left_index, left in enumerate(parsed_signatures):
        for right in parsed_signatures[left_index + 1 :]:
            comparison = _exact(
                comparisons[comparison_ordinal - 1],
                set(legacy._PHASH_COMPARISON_KEYS),
                "R2 pHash comparison",
            )
            if (
                comparison["schema_version"] != legacy.PHASH_COMPARISON_SCHEMA
                or comparison["comparison_ordinal"] != comparison_ordinal
            ):
                _fail("R2 pHash comparison order is invalid")
            expected_binding = {
                "left_image_record_ordinal": left["image_record_ordinal"],
                "left_image_record_id": left["image_record_id"],
                "left_signature_digest": left["signature_digest"],
                "right_image_record_ordinal": right["image_record_ordinal"],
                "right_image_record_id": right["image_record_id"],
                "right_signature_digest": right["signature_digest"],
            }
            if any(comparison[key] != expected for key, expected in expected_binding.items()):
                _fail("R2 pHash comparison signature binding is invalid")
            distance = (
                int(cast(str, left["phash_hex"]), 16) ^ int(cast(str, right["phash_hex"]), 16)
            ).bit_count()
            if (
                type(comparison["hamming_distance"]) is not int
                or comparison["hamming_distance"] != distance
            ):
                _fail("R2 pHash comparison Hamming distance is invalid")
            if comparison["comparison_digest"] != _r2_phash_comparison_digest(comparison):
                _fail("R2 pHash comparison digest does not replay")
            comparison_ordinal += 1
    return evidence


def build_r2_network_runtime_boundary() -> dict[str, JsonValue]:
    boundary: dict[str, JsonValue] = {
        "schema_version": legacy.NETWORK_BOUNDARY_SCHEMA,
        "public_internet_egress": "DENIED",
        "localhost_and_docker_internal_network": True,
        "proxy_environment_present": False,
        "production_provider_calls": 0,
        "runtime_generation_calls": 0,
    }
    boundary["boundary_receipt_digest"] = mirror_demo_digest(
        R2_NETWORK_BOUNDARY_RECEIPT_DOMAIN,
        {key: value for key, value in boundary.items() if key != "schema_version"},
    )
    return boundary


def _validate_r2_network_runtime_boundary(value: object) -> Mapping[str, Any]:
    boundary = _exact(value, set(legacy._NETWORK_BOUNDARY_KEYS), "R2 network boundary")
    if (
        boundary["schema_version"] != legacy.NETWORK_BOUNDARY_SCHEMA
        or boundary["public_internet_egress"] != "DENIED"
        or _bool(
            boundary["localhost_and_docker_internal_network"],
            "R2 localhost and Docker internal network",
        )
        is not True
        or _bool(boundary["proxy_environment_present"], "R2 proxy environment present") is not False
        or type(boundary["production_provider_calls"]) is not int
        or boundary["production_provider_calls"] != 0
        or type(boundary["runtime_generation_calls"]) is not int
        or boundary["runtime_generation_calls"] != 0
    ):
        _fail("R2 network and runtime boundary is invalid")
    expected_receipt = mirror_demo_digest(
        R2_NETWORK_BOUNDARY_RECEIPT_DOMAIN,
        {
            key: cast(JsonValue, item)
            for key, item in boundary.items()
            if key not in {"schema_version", "boundary_receipt_digest"}
        },
    )
    if boundary["boundary_receipt_digest"] != expected_receipt:
        _fail("R2 network boundary receipt digest does not replay")
    return boundary


def _r2_pair_context(
    *,
    source_packets: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    result_records: Sequence[Mapping[str, object]],
    gates: Sequence[Mapping[str, object]],
    structure_records: Sequence[Mapping[str, object]],
    manual_records: Sequence[Mapping[str, object]],
    image_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> tuple[
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
]:
    sources, cases, parsed_m4, authority = _r2_image_execution_context(
        source_packets=source_packets,
        case_manifest=case_manifest,
        m4_records=m4_records,
        execution_authority=execution_authority,
    )
    if (
        len(result_records) != 144
        or len(gates) != 48
        or len(structure_records) != 48
        or len(manual_records) != 48
    ):
        _fail("R2 pair authority execution evidence cardinality is invalid")
    parsed_results: list[Mapping[str, Any]] = []
    for index, raw in enumerate(result_records):
        record = _validate_r2_result_m3_record(raw)
        case = cases[index // 3]
        first = parsed_m4[index // 3 * 2]
        if (
            record["repeat_index"] != index % 3 + 1
            or any(record[key] != case[key] for key in ("case_id", "case_specification_digest"))
            or any(record[key] != first[key] for key in ("result_output_id", "result_sha256"))
            or record["runtime_manifest_digest"] != authority["runtime_manifest_digest"]
            or record["vision_model_manifest_digest"] != authority["vision_model_manifest_digest"]
            or record["topology_digest"] != authority["topology_digest"]
        ):
            _fail("R2 pair ResultM3 binding is invalid")
        parsed_results.append(record)
    parsed_gates: list[Mapping[str, Any]] = []
    for index, raw in enumerate(gates):
        facts = source_packets[index // 12].get("facts")
        if not isinstance(facts, Mapping):
            _fail("R2 pair measurement facts are invalid")
        gate = _validate_r2_measurement_gate(
            raw,
            result_records=parsed_results[index * 3 : index * 3 + 3],
            facts=facts,
        )
        case = cases[index]
        if (
            any(
                gate[key] != case[key]
                for key in ("case_id", "case_specification_digest", "dimension_key")
            )
            or gate["requested_direction"] != case["direction"]
            or gate["requested_magnitude_ppm"] != case["magnitude_ppm"]
        ):
            _fail("R2 pair measurement Gate binding is invalid")
        parsed_gates.append(gate)
    structures: list[Mapping[str, Any]] = []
    for index, raw in enumerate(structure_records):
        case = cases[index]
        source = sources[int(case["source_ordinal"]) - 1]
        structures.append(
            _validate_r2_decode_structure_record(
                raw,
                case_entry=case,
                source_entry=source,
                m4_first=parsed_m4[index * 2],
                m4_second=parsed_m4[index * 2 + 1],
                execution_authority=authority,
            )
        )
    manual_by_case: dict[str, Mapping[str, Any]] = {}
    case_by_id = {cast(str, case["case_id"]): case for case in cases}
    m4_by_case = {
        cast(str, case["case_id"]): parsed_m4[index * 2] for index, case in enumerate(cases)
    }
    previous = ""
    for sequence, raw in enumerate(manual_records, start=1):
        if not isinstance(raw, Mapping):
            _fail("R2 pair manual decision must be an object")
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or case_id not in case_by_id or case_id <= previous:
            _fail("R2 pair manual decisions are not case-ID ordered")
        previous = case_id
        case = case_by_id[case_id]
        source = sources[int(case["source_ordinal"]) - 1]
        manual_by_case[case_id] = _validate_r2_manual_artifact_decision(
            raw,
            case_entry=case,
            source_entry=source,
            m4_first=m4_by_case[case_id],
            execution_authority=authority,
            expected_sequence=sequence,
        )
    parsed_images = _validate_r2_image_authority_evidence(
        image_records,
        source_packets=source_packets,
        case_manifest=case_manifest,
        m4_records=m4_records,
        execution_authority=authority,
    )
    result_image_by_case = {
        cast(str, image["case_id"]): image
        for image in parsed_images
        if image["authority_role"] == "RESULT"
    }
    if len(result_image_by_case) != 48:
        _fail("R2 pair result image authority must cover exactly 48 cases")
    variants = _r2_result_variant_bindings_from_context(cases, parsed_m4)
    return (
        sources,
        cases,
        parsed_m4,
        parsed_results,
        parsed_gates,
        structures,
        manual_by_case,
        result_image_by_case,
        variants,
    )


def _expected_r2_pair_side(
    *,
    case_index: int,
    expected_direction: str,
    cases: Sequence[Mapping[str, Any]],
    m4_records: Sequence[Mapping[str, Any]],
    result_records: Sequence[Mapping[str, Any]],
    gates: Sequence[Mapping[str, Any]],
    structures: Sequence[Mapping[str, Any]],
    manual_by_case: Mapping[str, Mapping[str, Any]],
    result_image_by_case: Mapping[str, Mapping[str, Any]],
    variant_by_case: Mapping[str, Mapping[str, Any]],
) -> dict[str, JsonValue]:
    case = cases[case_index]
    case_id = cast(str, case["case_id"])
    first = m4_records[case_index * 2]
    triple = result_records[case_index * 3 : case_index * 3 + 3]
    gate = gates[case_index]
    structure = structures[case_index]
    manual = manual_by_case[case_id]
    image = result_image_by_case[case_id]
    variant = variant_by_case[case_id]
    if (
        case["direction"] != expected_direction
        or structure["result_image_record_id"] != image["image_record_id"]
        or image["deterministic_result_asset_id"] != variant["result_asset_id"]
        or image["result_output_id"] != first["result_output_id"]
        or image["sha256"] != first["result_sha256"]
        or variant["source_asset_id"] != case["source_asset_id"]
        or variant["source_asset_sha256"] != case["source_asset_sha256"]
        or variant["result_asset_sha256"] != first["result_sha256"]
        or variant["case_specification_digest"] != case["case_specification_digest"]
        or variant["asset_variant_type"] != legacy.VARIANT_TYPE
    ):
        _fail("R2 pair side Case/M4/Image/AssetVariant binding is invalid")
    result_m3_digests: list[JsonValue] = [cast(str, record["record_digest"]) for record in triple]
    repeat_gate_results: list[JsonValue] = [
        _bool(record["repeat_gate_passed"], "R2 ResultM3 repeat Gate") for record in triple
    ]
    evaluation = cast(Mapping[str, Any], gate["gate_evaluation"])
    measurement_gate = _bool(evaluation["measurement_gate_passed"], "R2 measurement Gate")
    structure_gate = _bool(structure["structure_gate_passed"], "R2 structure Gate")
    automated_gate = all(repeat_gate_results) and measurement_gate and structure_gate
    manual_gate = manual["verdict"] == "PASS"
    side_gate = automated_gate and manual_gate
    automated_payload: dict[str, JsonValue] = {
        "case_id": case_id,
        "case_specification_digest": cast(str, case["case_specification_digest"]),
        "result_m3_record_digests": result_m3_digests,
        "result_m3_repeat_gate_results": repeat_gate_results,
        "measurement_gate_record_digest": cast(str, gate["record_digest"]),
        "measurement_evaluation_state": cast(str, gate["measurement_evaluation_state"]),
        "measurement_gate_passed": measurement_gate,
        "decode_structure_record_digest": cast(str, structure["record_digest"]),
        "structure_gate_passed": structure_gate,
        "automated_gate_passed": automated_gate,
    }
    lineage_digest = mirror_demo_digest(
        legacy.VARIANT_LINEAGE_SCHEMA,
        {
            "variant_type": legacy.VARIANT_TYPE,
            "source_asset_id": case["source_asset_id"],
            "source_asset_sha256": case["source_asset_sha256"],
            "result_asset_id": variant["result_asset_id"],
            "result_asset_sha256": first["result_sha256"],
        },
    )
    common: dict[str, JsonValue] = {
        "measurement_evaluation_state": cast(str, gate["measurement_evaluation_state"]),
        "case_id": case_id,
        "case_specification_digest": cast(str, case["case_specification_digest"]),
        "requested_direction": expected_direction,
        "requested_magnitude_ppm": cast(int, case["magnitude_ppm"]),
        "result_output_id": cast(str, first["result_output_id"]),
        "result_asset_id": cast(str, variant["result_asset_id"]),
        "result_asset_sha256": cast(str, first["result_sha256"]),
        "result_asset_byte_size": cast(int, first["result_byte_size"]),
        "result_asset_mime_type": cast(str, first["result_mime_type"]),
        "result_asset_width": cast(int, first["result_width"]),
        "result_asset_height": cast(int, first["result_height"]),
        "asset_variant_id": cast(str, variant["asset_variant_id"]),
        "asset_variant_type": cast(str, variant["asset_variant_type"]),
        "lineage_digest": lineage_digest,
        "image_record_id": cast(str, image["image_record_id"]),
        "image_record_digest": cast(str, image["image_record_digest"]),
        "result_m3_record_digests": result_m3_digests,
        "measurement_gate_record_digest": cast(str, gate["record_digest"]),
        "decode_structure_record_digest": cast(str, structure["record_digest"]),
        "manual_decision_digest": cast(str, manual["manual_decision_digest"]),
        "automated_gate_digest": mirror_demo_digest(
            legacy.AUTOMATED_SIDE_GATE_SCHEMA, automated_payload
        ),
        "automated_gate_passed": automated_gate,
        "manual_gate_passed": manual_gate,
        "side_gate_passed": side_gate,
    }
    if gate["measurement_evaluation_state"] == "SUPPORTED_EVALUATED":
        measurements = cast(list[Mapping[str, Any]], gate["ordered_result_repeat_measurements"])
        measurement = measurements[0]
        quality = legacy._side_quality_ppm(
            measurement["raw_max_control_drift_fixed18"], side_gate_passed=side_gate
        )
        return {
            "schema_version": legacy.EVALUATED_SIDE_SCHEMA,
            **common,
            "raw_signed_target_delta_fixed18": cast(
                str, measurement["raw_signed_target_delta_fixed18"]
            ),
            "raw_target_absolute_delta_fixed18": cast(
                str, measurement["raw_target_absolute_delta_fixed18"]
            ),
            "raw_max_control_drift_fixed18": cast(
                str, measurement["raw_max_control_drift_fixed18"]
            ),
            "measured_signed_delta_ppm": cast(int, measurement["measured_signed_delta_ppm"]),
            "drift_ppm": cast(int, measurement["drift_ppm"]),
            "side_quality_state": "COMPUTED" if side_gate else "NOT_COMPUTED_GATE_FAILED",
            "side_quality_component_ppm": quality,
        }
    if gate["measurement_evaluation_state"] != "UNSUPPORTED_EXPLICIT":
        _fail("R2 pair side measurement evaluation state is invalid")
    unsupported_indexes = evaluation["unsupported_repeat_indexes"]
    unsupported_reasons = evaluation["ordered_unsupported_reasons"]
    if not isinstance(unsupported_indexes, list) or not isinstance(unsupported_reasons, list):
        _fail("R2 unsupported pair side evidence must use ordered arrays")
    if automated_gate or side_gate:
        _fail("R2 unsupported pair side cannot pass automated or side Gate")
    return {
        "schema_version": legacy.UNSUPPORTED_SIDE_SCHEMA,
        **common,
        "unsupported_repeat_indexes": cast(list[JsonValue], unsupported_indexes),
        "ordered_unsupported_reasons": cast(list[JsonValue], unsupported_reasons),
        "side_quality_state": "NOT_COMPUTED_GATE_FAILED",
        "side_quality_component_ppm": 0,
    }


def build_r2_pair_screening_evidence(
    *,
    source_packets: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    result_records: Sequence[Mapping[str, object]],
    gates: Sequence[Mapping[str, object]],
    structure_records: Sequence[Mapping[str, object]],
    manual_records: Sequence[Mapping[str, object]],
    image_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> list[dict[str, JsonValue]]:
    """Derive all 24 R2 pairs from complete typed pair-side authority."""

    (
        sources,
        cases,
        parsed_m4,
        parsed_results,
        parsed_gates,
        structures,
        manual_by_case,
        result_image_by_case,
        variants,
    ) = _r2_pair_context(
        source_packets=source_packets,
        case_manifest=case_manifest,
        m4_records=m4_records,
        result_records=result_records,
        gates=gates,
        structure_records=structure_records,
        manual_records=manual_records,
        image_records=image_records,
        execution_authority=execution_authority,
    )
    authority = _r2_execution_authority(execution_authority)
    records: list[dict[str, JsonValue]] = []
    for source_index, source in enumerate(sources):
        for dimension_index, dimension in enumerate(legacy.CASE_DIMENSIONS):
            for magnitude_index, magnitude in enumerate(legacy.CASE_MAGNITUDES):
                left_index = source_index * 12 + dimension_index * 4 + magnitude_index
                right_index = left_index + 2
                left = _expected_r2_pair_side(
                    case_index=left_index,
                    expected_direction="DECREASE",
                    cases=cases,
                    m4_records=parsed_m4,
                    result_records=parsed_results,
                    gates=parsed_gates,
                    structures=structures,
                    manual_by_case=manual_by_case,
                    result_image_by_case=result_image_by_case,
                    variant_by_case=variants,
                )
                right = _expected_r2_pair_side(
                    case_index=right_index,
                    expected_direction="INCREASE",
                    cases=cases,
                    m4_records=parsed_m4,
                    result_records=parsed_results,
                    gates=parsed_gates,
                    structures=structures,
                    manual_by_case=manual_by_case,
                    result_image_by_case=result_image_by_case,
                    variant_by_case=variants,
                )
                pair_side_gate = (
                    left["side_gate_passed"] is True and right["side_gate_passed"] is True
                )
                payload: dict[str, JsonValue] = {
                    "source_ordinal": source_index + 1,
                    "source_authority_key": cast(str, source["source_authority_key"]),
                    "source_admission_event_id": cast(str, source["source_admission_event_id"]),
                    "source_asset_id": cast(str, source["source_asset_id"]),
                    "source_asset_sha256": cast(str, source["source_asset_sha256"]),
                    "dimension_key": dimension,
                    "priority_index": dimension_index + 1,
                    "magnitude_ppm": magnitude,
                    "screening_policy_digest": cast(str, authority["screening_policy_digest"]),
                    "left": left,
                    "right": right,
                    "same_source_gate_passed": True,
                    "opposed_direction_gate_passed": True,
                    "equal_magnitude_gate_passed": True,
                    "pair_side_gates_passed": pair_side_gate,
                    "empty_lock_policy_gate_passed": True,
                    "pair_quality_state": (
                        "COMPUTED" if pair_side_gate else "NOT_COMPUTED_GATE_FAILED"
                    ),
                    "pair_quality_ppm": (
                        min(
                            cast(int, left["side_quality_component_ppm"]),
                            cast(int, right["side_quality_component_ppm"]),
                        )
                        if pair_side_gate
                        else 0
                    ),
                    "lock_conclusion": "PASS_FOR_FROZEN_EMPTY_NEUTRAL_POLICY_ONLY",
                    "lock_policy_digest": legacy.EMPTY_LOCK_POLICY_DIGEST,
                    "pair_gate_passed": pair_side_gate,
                }
                payload["pair_record_id"] = _pair_record_id(payload)
                records.append(
                    {
                        "schema_version": R2_PAIR_SCREENING_SCHEMA,
                        "pair_screening_record_payload": payload,
                        "pair_screening_record_digest": mirror_demo_digest(
                            R2_PAIR_SCREENING_SCHEMA, payload
                        ),
                    }
                )
    return records


def _pair_record_id(payload: Mapping[str, object]) -> str:
    left = cast(Mapping[str, object], payload["left"])
    right = cast(Mapping[str, object], payload["right"])
    return mirror_demo_digest(
        R2_PAIR_RECORD_ID_DOMAIN,
        cast(
            dict[str, JsonValue],
            {
                "source_authority_key": payload["source_authority_key"],
                "source_admission_event_id": payload["source_admission_event_id"],
                "source_asset_sha256": payload["source_asset_sha256"],
                "dimension_key": payload["dimension_key"],
                "priority_index": payload["priority_index"],
                "magnitude_ppm": payload["magnitude_ppm"],
                "left_case_id": left["case_id"],
                "right_case_id": right["case_id"],
                "screening_policy_digest": payload["screening_policy_digest"],
                "lock_policy_digest": payload["lock_policy_digest"],
            },
        ),
    )[:32]


def _validate_pair_record(value: object) -> Mapping[str, Any]:
    wrapper = _exact(value, set(legacy._PAIR_WRAPPER_KEYS), "R2 pair screening wrapper")
    if wrapper["schema_version"] != R2_PAIR_SCREENING_SCHEMA:
        _fail("R2 pair screening wrapper schema is invalid")
    payload = _exact(
        wrapper["pair_screening_record_payload"],
        set(legacy._PAIR_PAYLOAD_KEYS),
        "R2 pair screening payload",
    )
    for side_name in ("left", "right"):
        side = payload[side_name]
        if not isinstance(side, Mapping):
            _fail("R2 pair side must be an object")
        side_schema = side.get("schema_version")
        expected_keys = (
            legacy._EVALUATED_SIDE_KEYS
            if side_schema == legacy.EVALUATED_SIDE_SCHEMA
            else legacy._UNSUPPORTED_SIDE_KEYS
        )
        _exact(side, set(expected_keys), f"R2 {side_name} pair side")
        if side_schema not in {legacy.EVALUATED_SIDE_SCHEMA, legacy.UNSUPPORTED_SIDE_SCHEMA}:
            _fail("R2 pair side schema is invalid")
        _reject_noncanonical_json(side)
        for key in (
            "case_specification_digest",
            "result_asset_sha256",
            "lineage_digest",
            "image_record_digest",
            "measurement_gate_record_digest",
            "decode_structure_record_digest",
            "manual_decision_digest",
            "automated_gate_digest",
        ):
            _digest(side[key], f"R2 pair side {key}")
        if (
            not isinstance(side["result_m3_record_digests"], list)
            or len(side["result_m3_record_digests"]) != 3
        ):
            _fail("R2 pair side ResultM3 digest order is invalid")
        for digest in side["result_m3_record_digests"]:
            _digest(digest, "R2 pair side ResultM3 digest")
    for key in (
        "source_authority_key",
        "source_asset_sha256",
        "screening_policy_digest",
        "lock_policy_digest",
    ):
        _digest(payload[key], f"R2 pair {key}")
    _id(payload["source_admission_event_id"], "R2 pair source admission event ID")
    _id(payload["source_asset_id"], "R2 pair source Asset ID")
    _id(payload["pair_record_id"], "R2 pair record ID")
    if payload["pair_record_id"] != _pair_record_id(payload):
        _fail("R2 pair record ID does not replay")
    if wrapper["pair_screening_record_digest"] != mirror_demo_digest(
        R2_PAIR_SCREENING_SCHEMA, payload
    ):
        _fail("R2 pair screening digest does not replay")
    return wrapper


def _pair_records(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or len(value) != 24:
        _fail("R2 Report v3 pair screening record count is invalid")
    records = [_validate_pair_record(item) for item in value]
    seen: set[str] = set()
    for ordinal, wrapper in enumerate(records):
        payload = cast(Mapping[str, Any], wrapper["pair_screening_record_payload"])
        expected = (ordinal // 6 + 1, legacy.CASE_DIMENSIONS[(ordinal % 6) // 2], ordinal % 2)
        if (
            payload["source_ordinal"],
            payload["dimension_key"],
            0 if payload["magnitude_ppm"] == 15_000 else 1,
        ) != expected:
            _fail("R2 pair screening record order is invalid")
        digest = cast(str, wrapper["pair_screening_record_digest"])
        if digest in seen:
            _fail("R2 pair screening record digest is duplicated")
        seen.add(digest)
    return records


def _validate_r2_b3_report_graph(
    payload: Mapping[str, Any], *, source_packets: Sequence[Mapping[str, object]] | None
) -> None:
    """Replay image, duplicate, pHash, network, and 24 pair-side authority."""

    if source_packets is None or len(source_packets) != 4:
        _fail("R2 B3 graph requires four validated source admission packets")
    binding = cast(Mapping[str, object], payload["schema_and_policy"])

    def group(name: str, count: int) -> list[Mapping[str, object]]:
        value = payload[name]
        if (
            not isinstance(value, list)
            or len(value) != count
            or any(not isinstance(item, Mapping) for item in value)
        ):
            _fail(f"R2 B3 {name} cardinality is invalid")
        return cast(list[Mapping[str, object]], value)

    cases = group("ordered_case_manifest", 48)
    m4_records = group("m4_repeat_evidence", 96)
    result_records = group("result_m3_repeat_evidence", 144)
    gates = group("measurement_gate_evidence", 48)
    structures = group("decode_structure_immutability_evidence", 48)
    manuals = group("manual_review_evidence", 48)
    expected_images = build_r2_image_authority_evidence(
        source_packets=source_packets,
        case_manifest=cases,
        m4_records=m4_records,
        execution_authority=binding,
    )
    exact = _validate_r2_exact_duplicate_evidence(
        payload["exact_duplicate_evidence"], expected_image_records=expected_images
    )
    raw_images = exact["image_records"]
    if not isinstance(raw_images, list):
        _fail("R2 B3 exact duplicate image records are invalid")
    images = cast(list[Mapping[str, object]], raw_images)
    _validate_r2_phash_observation_evidence(
        payload["phash_observation_evidence"],
        image_records=images,
        execution_authority=binding,
    )
    expected_pairs = build_r2_pair_screening_evidence(
        source_packets=source_packets,
        case_manifest=cases,
        m4_records=m4_records,
        result_records=result_records,
        gates=gates,
        structure_records=structures,
        manual_records=manuals,
        image_records=images,
        execution_authority=binding,
    )
    actual_pairs = _pair_records(payload["pair_quality_evidence"])
    if actual_pairs != expected_pairs:
        _fail("R2 pair screening evidence is not the complete execution graph projection")
    _validate_r2_network_runtime_boundary(payload["network_and_runtime_boundary"])


def validate_r2_report_payload(value: object) -> Mapping[str, Any]:
    payload = _exact(value, R2_REPORT_PAYLOAD_KEYS, "R2 Report v3 payload")
    for name, schema, count in R2_REPORT_GROUPS:
        group = payload[name]
        if name == "pair_quality_evidence":
            _pair_records(group)
            continue
        if name == "selected_pair_manifest":
            if not isinstance(group, list):
                _fail("R2 selected pair manifest is an ordered list, never a wrapper")
            continue
        if count == 1:
            member = _typed_member(group, schema, name)
            if name in R2_LEGACY_MEMBER_KEYS:
                _exact(member, R2_LEGACY_MEMBER_KEYS[name], name)
            if "record_digest" in member or "entry_digest" in member:
                _replay_member(member, schema, name)
            elif len(member) <= 2:
                _fail(f"{name} must not use a two-key digest placeholder")
        else:
            if not isinstance(group, list) or len(group) != count:
                _fail(f"R2 Report v3 {name} count is invalid")
            for item in group:
                if name == "source_m3_repeat_evidence":
                    _require_mandatory_digest_leaves(
                        item,
                        R2_SOURCE_M3_MANDATORY_DIGEST_LEAVES,
                        "R2 SourceM3",
                    )
                elif name == "result_m3_repeat_evidence":
                    _require_mandatory_digest_leaves(
                        item,
                        R2_RESULT_M3_MANDATORY_DIGEST_LEAVES,
                        "R2 ResultM3",
                    )
                member = _typed_member(item, schema, name)
                if name in R2_LEGACY_MEMBER_KEYS:
                    _exact(member, R2_LEGACY_MEMBER_KEYS[name], name)
                _replay_member(member, schema, name)
    return payload


def _dimension_records(
    value: object, *, pairs: list[Mapping[str, Any]], exact_sha_gate_passed: bool
) -> list[Mapping[str, Any]]:
    records = value
    if not isinstance(records, list) or len(records) != 3:
        _fail("R2 dimension eligibility count is invalid")
    parsed: list[Mapping[str, Any]] = []
    for index, item in enumerate(records):
        record = _exact(item, set(legacy._DIMENSION_KEYS), "R2 dimension eligibility record")
        if record["schema_version"] != R2_DIMENSION_SCHEMA:
            _fail("R2 dimension eligibility schema is invalid")
        _replay_member(record, R2_DIMENSION_SCHEMA, "R2 dimension eligibility record")
        if (
            record["dimension_key"] != legacy.CASE_DIMENSIONS[index]
            or record["priority_index"] != index + 1
        ):
            _fail("R2 dimension eligibility order is invalid")
        for key, count in (
            ("ordered_pair_screening_record_digests", 8),
            ("ordered_side_automated_gate_digests", 16),
        ):
            if not isinstance(record[key], list) or len(record[key]) != count:
                _fail("R2 dimension eligibility ordered digest count is invalid")
            for digest in record[key]:
                _digest(digest, "R2 dimension eligibility member digest")
        expected_pair_digests: list[str] = []
        expected_side_digests: list[str] = []
        side_entries: list[dict[str, JsonValue]] = []
        pair_entries: list[dict[str, JsonValue]] = []
        all_side = True
        all_pair = True
        all_manual = True
        all_lock = True
        for source_index in range(4):
            for magnitude_index, magnitude in enumerate((15_000, 30_000)):
                pair = pairs[source_index * 6 + index * 2 + magnitude_index]
                payload = cast(Mapping[str, Any], pair["pair_screening_record_payload"])
                expected_pair_digests.append(cast(str, pair["pair_screening_record_digest"]))
                for side_label, side_name in (("LEFT", "left"), ("RIGHT", "right")):
                    side = cast(Mapping[str, Any], payload[side_name])
                    automated = side.get("automated_gate_passed")
                    manual = side.get("manual_gate_passed")
                    side_gate = side.get("side_gate_passed")
                    if (
                        type(automated) is not bool
                        or type(manual) is not bool
                        or type(side_gate) is not bool
                    ):
                        _fail("R2 dimension side gate booleans are invalid")
                    automated_digest = side.get("automated_gate_digest")
                    manual_digest = side.get("manual_decision_digest")
                    _digest(automated_digest, "R2 dimension automated gate digest")
                    _digest(manual_digest, "R2 dimension manual decision digest")
                    expected_side_digests.append(cast(str, automated_digest))
                    side_entries.append(
                        {
                            "schema_version": legacy.DIMENSION_SIDE_GATE_SCHEMA,
                            "source_ordinal": source_index + 1,
                            "magnitude_ppm": magnitude,
                            "side": side_label,
                            "case_id": cast(str, side["case_id"]),
                            "automated_gate_digest": cast(str, automated_digest),
                            "manual_decision_digest": cast(str, manual_digest),
                            "automated_gate_passed": automated,
                            "manual_gate_passed": manual,
                            "side_gate_passed": side_gate,
                        }
                    )
                    all_side = all_side and side_gate
                    all_manual = all_manual and manual
                pair_gate = payload.get("pair_gate_passed")
                lock_gate = payload.get("empty_lock_policy_gate_passed")
                if type(pair_gate) is not bool or type(lock_gate) is not bool:
                    _fail("R2 dimension pair gate booleans are invalid")
                pair_entries.append(
                    {
                        "schema_version": legacy.DIMENSION_PAIR_GATE_SCHEMA,
                        "source_ordinal": source_index + 1,
                        "magnitude_ppm": magnitude,
                        "pair_record_id": cast(str, payload["pair_record_id"]),
                        "pair_screening_record_digest": cast(
                            str, pair["pair_screening_record_digest"]
                        ),
                        "pair_gate_passed": pair_gate,
                    }
                )
                all_pair = all_pair and pair_gate
                all_lock = all_lock and lock_gate
        expected = {
            "ordered_pair_screening_record_digests": expected_pair_digests,
            "ordered_side_automated_gate_digests": expected_side_digests,
            "sixteen_side_gate_digest": mirror_demo_digest(
                legacy.SIXTEEN_SIDE_GATE_SCHEMA,
                cast(
                    dict[str, Any],
                    {
                        "dimension_key": record["dimension_key"],
                        "priority_index": record["priority_index"],
                        "ordered_side_gate_entries": side_entries,
                    },
                ),
            ),
            "eight_pair_gate_digest": mirror_demo_digest(
                legacy.EIGHT_PAIR_GATE_SCHEMA,
                cast(
                    dict[str, Any],
                    {
                        "dimension_key": record["dimension_key"],
                        "priority_index": record["priority_index"],
                        "ordered_pair_gate_entries": pair_entries,
                    },
                ),
            ),
            "all_sixteen_side_gates_passed": all_side,
            "all_eight_pair_gates_passed": all_pair,
            "all_manual_gates_passed": all_manual,
            "global_exact_sha_gate_passed": exact_sha_gate_passed,
            "empty_lock_policy_gate_passed": all_lock,
            "eligible": all_side and all_pair and all_manual and exact_sha_gate_passed and all_lock,
            "failure_reasons": [
                reason
                for reason, passed in zip(
                    legacy._FAILURE_REASONS,
                    (all_side, all_pair, all_manual, exact_sha_gate_passed, all_lock),
                    strict=True,
                )
                if not passed
            ],
        }
        if any(record[key] != expected[key] for key in expected):
            _fail("R2 dimension eligibility is not the complete pair-side projection")
        parsed.append(record)
    return parsed


def _selection_trace(
    value: object, dimensions: list[Mapping[str, Any]]
) -> tuple[list[str], list[str], str]:
    if not isinstance(value, list) or len(value) != 3:
        _fail("R2 selection trace count is invalid")
    eligible = [item["dimension_key"] for item in dimensions if item["eligible"] is True]
    selected = eligible[:2] if len(eligible) >= 2 else []
    for index, item in enumerate(value):
        record = _exact(item, set(legacy._SELECTION_KEYS), "R2 selection trace record")
        if record["schema_version"] != R2_SELECTION_SCHEMA:
            _fail("R2 selection trace schema is invalid")
        _replay_member(record, R2_SELECTION_SCHEMA, "R2 selection trace record")
        dimension = dimensions[index]
        if (
            record["selection_step"] != index + 1
            or record["dimension_key"] != dimension["dimension_key"]
            or record["priority_index"] != dimension["priority_index"]
            or record["dimension_eligibility_record_digest"] != dimension["record_digest"]
        ):
            _fail("R2 selection trace dimension binding is invalid")
        wanted_selected = dimension["dimension_key"] in selected
        eligible_rank = (
            eligible.index(dimension["dimension_key"]) + 1 if dimension["eligible"] is True else 0
        )
        expected_decision = (
            "INELIGIBLE"
            if dimension["eligible"] is not True
            else "ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET"
            if len(eligible) < 2
            else "SELECTED_SLOT_1"
            if eligible_rank == 1
            else "SELECTED_SLOT_2"
            if eligible_rank == 2
            else "ELIGIBLE_NOT_SELECTED_CAPACITY"
        )
        if (
            record["eligible"] is not (dimension["eligible"] is True)
            or record["eligible_rank"] != eligible_rank
            or record["selection_decision"] != expected_decision
            or record["selected"] is not wanted_selected
            or record["selection_slot"]
            != (selected.index(dimension["dimension_key"]) + 1 if wanted_selected else 0)
        ):
            _fail("R2 selection trace selection projection is invalid")
    return eligible, selected, "PASSED" if len(eligible) >= 2 else "FAILED"


def _selected_manifest(
    value: object, *, pairs: list[Mapping[str, Any]], selected_dimensions: list[str]
) -> str | None:
    if not isinstance(value, list):
        _fail("R2 selected pair manifest must be a list")
    if not selected_dimensions:
        if value:
            _fail("FAILED R2 selected pair manifest must be empty")
        return None
    if len(value) != 16:
        _fail("PASSED R2 selected pair manifest must contain 16 entries")
    expected: list[dict[str, object]] = []
    for slot, dimension in enumerate(selected_dimensions, start=1):
        dimension_index = legacy.CASE_DIMENSIONS.index(dimension)
        for source_index in range(4):
            for magnitude_index, magnitude in enumerate((15_000, 30_000)):
                wrapper = pairs[source_index * 6 + dimension_index * 2 + magnitude_index]
                payload = cast(Mapping[str, Any], wrapper["pair_screening_record_payload"])
                if payload["pair_gate_passed"] is not True:
                    _fail("selected manifest cannot include a failed pair")
                left = cast(Mapping[str, Any], payload["left"])
                right = cast(Mapping[str, Any], payload["right"])
                expected.append(
                    {
                        "schema_version": R2_SELECTED_ENTRY_SCHEMA,
                        "selected_pair_ordinal": len(expected) + 1,
                        "selected_dimension_slot": slot,
                        "dimension_key": dimension,
                        "priority_index": dimension_index + 1,
                        "source_ordinal": source_index + 1,
                        "source_authority_key": payload["source_authority_key"],
                        "source_admission_event_id": payload["source_admission_event_id"],
                        "magnitude_ppm": magnitude,
                        "pair_record_id": payload["pair_record_id"],
                        "pair_screening_record_digest": wrapper["pair_screening_record_digest"],
                        "left_case_id": left["case_id"],
                        "left_result_asset_id": left["result_asset_id"],
                        "left_result_asset_sha256": left["result_asset_sha256"],
                        "left_asset_variant_id": left["asset_variant_id"],
                        "right_case_id": right["case_id"],
                        "right_result_asset_id": right["result_asset_id"],
                        "right_result_asset_sha256": right["result_asset_sha256"],
                        "right_asset_variant_id": right["asset_variant_id"],
                    }
                )
    for record in expected:
        record["entry_digest"] = mirror_demo_digest(
            R2_SELECTED_ENTRY_SCHEMA,
            cast(
                dict[str, JsonValue],
                {key: item for key, item in record.items() if key != "schema_version"},
            ),
        )
    for actual, expected_record in zip(value, expected, strict=True):
        item = _exact(actual, set(legacy._SELECTED_PAIR_KEYS), "R2 selected pair manifest entry")
        if item != expected_record:
            _fail("R2 selected pair manifest entry is not the exact pair projection")
    # CC08 freezes this as the digest of the exact ordered sequence, not a
    # wrapper object.  Keep the predecessor sequence preimage byte-for-byte.
    return legacy._sequence_digest(
        R2_SELECTED_MANIFEST_SCHEMA, cast(list[Mapping[str, object]], value)
    )


def _validate_report_graph(
    payload: Mapping[str, Any], row: Mapping[str, object]
) -> tuple[list[str], list[str], str, str | None]:
    pairs = _pair_records(payload["pair_quality_evidence"])
    sources = payload["ordered_source_manifest"]
    if not isinstance(sources, list) or len(sources) != 4:
        _fail("R2 Report v3 ordered source manifest is invalid")
    for pair in pairs:
        pair_payload = cast(Mapping[str, Any], pair["pair_screening_record_payload"])
        source = sources[pair_payload["source_ordinal"] - 1]
        if not isinstance(source, Mapping) or any(
            pair_payload[pair_key] != source[source_key]
            for pair_key, source_key in (
                ("source_authority_key", "source_authority_key"),
                ("source_admission_event_id", "source_admission_event_id"),
                ("source_asset_id", "source_asset_id"),
                ("source_asset_sha256", "source_asset_sha256"),
            )
        ):
            _fail("R2 pair screening record source projection is invalid")
    exact_duplicate = cast(Mapping[str, object], payload["exact_duplicate_evidence"])
    dimensions = _dimension_records(
        payload["dimension_eligibility"],
        pairs=pairs,
        exact_sha_gate_passed=exact_duplicate["exact_sha_gate_passed"] is True,
    )
    eligible, selected, status = _selection_trace(
        payload["fixed_priority_selection_trace"], dimensions
    )
    manifest_digest = _selected_manifest(
        payload["selected_pair_manifest"], pairs=pairs, selected_dimensions=selected
    )
    return eligible, selected, status, manifest_digest


def _report_canonical(row: Mapping[str, object]) -> dict[str, JsonValue]:
    canonical = {key: cast(JsonValue, row[key]) for key in R2_REPORT_FIELDS if key != "created_at"}
    if row["status"] == "FAILED":
        if row["selected_pair_manifest_digest"] is not None:
            _fail("FAILED R2 Report v3 has a selected manifest")
        canonical.pop("selected_pair_manifest_digest")
    return canonical


def _validate_report_sources(
    payload: Mapping[str, Any],
    source_packets: Sequence[Mapping[str, object]] | None,
    source_manifest_digest: object,
) -> None:
    if source_packets is None or len(source_packets) != 4:
        _fail("R2 Report v3 requires four validated source admission packets")
    entries = payload["ordered_source_manifest"]
    if not isinstance(entries, list):
        _fail("R2 Report v3 source manifest is invalid")
    expected_manifest_digest = legacy._sequence_digest(
        R2_SOURCE_MANIFEST_SCHEMA, cast(list[Mapping[str, object]], entries)
    )
    for ordinal, (entry, packet) in enumerate(zip(entries, source_packets, strict=True), start=1):
        validate_r2_admission_packet(packet)
        if entry != packet["source_manifest_entry"] or entry.get("source_ordinal") != ordinal:
            _fail("R2 Report v3 SourceEntry is not the validated admission projection")
        if packet["source_manifest_digest"] != expected_manifest_digest:
            _fail("R2 admission packet source manifest digest differs from cohort authority")
    # SourceManifest/v2 is likewise an ordered four-entry sequence.  A
    # mapping wrapper changes canonical bytes and is a distinct authority.
    if source_manifest_digest != expected_manifest_digest:
        _fail("R2 Report v3 source manifest digest does not replay")


def build_r2_report_row(
    fields: Mapping[str, object], *, source_packets: Sequence[Mapping[str, object]] | None = None
) -> dict[str, JsonValue]:
    row = _exact(fields, R2_REPORT_FIELDS, "R2 Report v3 input")
    validate_r2_report_payload(row["report_payload"])
    _validate_report_sources(
        cast(Mapping[str, Any], row["report_payload"]),
        source_packets,
        row["source_manifest_digest"],
    )
    _validate_r2_upstream_execution_graph(
        cast(Mapping[str, Any], row["report_payload"]), source_packets=source_packets
    )
    _validate_r2_b3_report_graph(
        cast(Mapping[str, Any], row["report_payload"]), source_packets=source_packets
    )
    _reject_noncanonical_json(row)
    if not isinstance(row["created_at"], str) or not row["created_at"]:
        _fail("R2 Report v3 created_at is invalid")
    expected_counts = {
        "source_count": 4,
        "case_count": 48,
        "source_m3_repeat_count": 12,
        "m4_execution_count": 96,
        "result_m3_repeat_count": 144,
        "measurement_gate_count": 48,
        "decode_structure_record_count": 48,
        "manual_decision_count": 48,
        "exact_sha_record_count": 52,
        "phash_comparison_count": 1326,
        "candidate_pair_count": 24,
    }
    for key, count in expected_counts.items():
        if row[key] != count:
            _fail("R2 Report v3 fixed count is invalid")
    if row["status"] == "PASSED":
        if row["selected_pair_count"] != 16 or row["selected_result_side_count"] != 32:
            _fail("PASSED R2 Report v3 selection counts are invalid")
    elif row["status"] == "FAILED":
        if row["selected_pair_count"] != 0 or row["selected_result_side_count"] != 0:
            _fail("FAILED R2 Report v3 selection counts are invalid")
    else:
        _fail("R2 Report v3 status is invalid")
    eligible, selected, status, manifest_digest = _validate_report_graph(
        cast(Mapping[str, Any], row["report_payload"]), row
    )
    if (
        row["status"] != status
        or row["eligible_dimension_keys"] != eligible
        or row["selected_dimension_keys"] != selected
        or row["selected_pair_manifest_digest"] != manifest_digest
    ):
        _fail("R2 Report v3 graph projection is invalid")
    report_digest = mirror_demo_digest(
        R2_REPORT_SCHEMA, cast(dict[str, JsonValue], row["report_payload"])
    )
    canonical = _report_canonical(row)
    content_digest = mirror_demo_digest(R2_REPORT_SCHEMA, canonical)
    result: dict[str, JsonValue] = {
        "schema_version": R2_REPORT_SCHEMA,
        **cast(dict[str, JsonValue], row),
        "report_digest": report_digest,
        "canonical_payload": canonical,
        "content_digest": content_digest,
        "id": mirror_demo_digest(
            R2_REPORT_ID_DOMAIN,
            {
                "report_digest": report_digest,
                "source_manifest_digest": row["source_manifest_digest"],
                "case_manifest_digest": row["case_manifest_digest"],
            },
        )[:32],
    }
    return result


def validate_r2_report_row(
    value: object, *, source_packets: Sequence[Mapping[str, object]] | None = None
) -> Mapping[str, Any]:
    row = _exact(value, R2_REPORT_ROW_KEYS, "R2 Report v3 row")
    if row["schema_version"] != R2_REPORT_SCHEMA:
        _fail("R2 Report v3 schema is invalid")
    validate_r2_report_payload(row["report_payload"])
    _validate_report_sources(
        cast(Mapping[str, Any], row["report_payload"]),
        source_packets,
        row["source_manifest_digest"],
    )
    _validate_r2_upstream_execution_graph(
        cast(Mapping[str, Any], row["report_payload"]), source_packets=source_packets
    )
    for key in R2_REPORT_FIELDS - {
        "report_payload",
        "status",
        "eligible_dimension_keys",
        "selected_dimension_keys",
        "created_at",
    }:
        if key.endswith("digest") and row[key] is not None:
            _digest(row[key], key)
    expected = build_r2_report_row(
        cast(Mapping[str, object], {key: row[key] for key in R2_REPORT_FIELDS}),
        source_packets=source_packets,
    )
    if any(
        row[key] != expected[key]
        for key in ("id", "report_digest", "canonical_payload", "content_digest")
    ):
        _fail("R2 Report v3 authority does not replay")
    return row


def validate_r2_dimension_manifest(
    value: object, *, report: Mapping[str, object]
) -> Mapping[str, Any]:
    manifest = _exact(value, R2_DIMENSION_MANIFEST_KEYS, "R2 Bank dimension manifest")
    if manifest["schema_version"] != R2_DIMENSION_MANIFEST_SCHEMA:
        _fail("R2 Bank dimension manifest schema is invalid")
    for manifest_key, report_key in (
        ("screening_report_id", "id"),
        ("screening_report_digest", "report_digest"),
        ("source_manifest_digest", "source_manifest_digest"),
        ("selected_pair_manifest_digest", "selected_pair_manifest_digest"),
    ):
        if manifest[manifest_key] != report[report_key]:
            _fail("R2 Bank dimension manifest report binding is invalid")
    dimensions = manifest["selected_dimensions"]
    if not isinstance(dimensions, list) or len(dimensions) != 2:
        _fail("R2 Bank requires two selected dimensions")
    previous: tuple[int, str] | None = None
    observed_entry_digests: list[str] = []
    report_dimensions = cast(Mapping[str, Any], report["report_payload"])["dimension_eligibility"]
    if not isinstance(report_dimensions, list):
        _fail("R2 Report v3 dimension eligibility is invalid")
    for dimension in dimensions:
        item = _exact(dimension, R2_SELECTED_DIMENSION_KEYS, "R2 selected dimension")
        if type(item["priority_index"]) is not int or type(item["dimension_key"]) is not str:
            _fail("R2 selected dimension order is invalid")
        order = (item["priority_index"], item["dimension_key"])
        if previous is not None and order <= previous:
            _fail("R2 selected dimensions are not priority ordered")
        previous = order
        matching = next(
            (
                candidate
                for candidate in report_dimensions
                if isinstance(candidate, Mapping)
                and candidate.get("dimension_key") == item["dimension_key"]
                and candidate.get("priority_index") == item["priority_index"]
            ),
            None,
        )
        if matching is None or any(
            item[key] != matching[key]
            for key in ("sixteen_side_gate_digest", "eight_pair_gate_digest")
        ):
            _fail("R2 selected dimension gate projection is invalid")
        entries = item["ordered_selected_pair_entry_digests"]
        if not isinstance(entries, list) or len(entries) != 8 or len(set(entries)) != 8:
            _fail("R2 selected dimension entries are invalid")
        for key in ("sixteen_side_gate_digest", "eight_pair_gate_digest"):
            _digest(item[key], key)
        for digest in entries:
            _digest(digest, "selected pair entry digest")
            observed_entry_digests.append(digest)
    expected_entries = cast(Mapping[str, object], report["report_payload"])[
        "selected_pair_manifest"
    ]
    if not isinstance(expected_entries, list) or observed_entry_digests != [
        _member_digest(
            _typed_member(item, R2_SELECTED_ENTRY_SCHEMA, "selected entry"),
            R2_SELECTED_ENTRY_SCHEMA,
            "selected entry",
        )
        for item in expected_entries
    ]:
        _fail("R2 selected dimension ordering is not the Report v3 projection")
    if [item["dimension_key"] for item in dimensions] != report["selected_dimension_keys"]:
        _fail("R2 selected dimensions do not equal the Report v3 projection")
    return manifest


def build_r2_question_bank_row(
    fields: Mapping[str, object],
    *,
    report: Mapping[str, object],
    source_packets: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, JsonValue]:
    bank = _exact(fields, R2_BANK_FIELDS, "R2 QuestionBank v3 input")
    validated_report = validate_r2_report_row(report, source_packets=source_packets)
    if (
        bank["screening_report_id"] != validated_report["id"]
        or bank["screening_report_digest"] != validated_report["report_digest"]
    ):
        _fail("R2 QuestionBank row report binding is invalid")
    manifest = validate_r2_dimension_manifest(bank["dimension_manifest"], report=validated_report)
    if bank["pair_manifest_digest"] != manifest["selected_pair_manifest_digest"]:
        _fail("R2 QuestionBank pair manifest binding is invalid")
    if not isinstance(bank["created_at"], str) or not bank["created_at"]:
        _fail("R2 QuestionBank created_at is invalid")
    canonical = cast(
        dict[str, JsonValue], {key: item for key, item in bank.items() if key != "created_at"}
    )
    result: dict[str, JsonValue] = {
        "schema_version": R2_BANK_SCHEMA,
        **cast(dict[str, JsonValue], dict(bank)),
        "canonical_payload": canonical,
        "content_digest": mirror_demo_digest(R2_BANK_SCHEMA, canonical),
    }
    result["id"] = mirror_demo_digest(
        R2_BANK_ID_DOMAIN,
        {
            "algorithm_config_digest": bank["algorithm_config_digest"],
            "screening_report_digest": bank["screening_report_digest"],
            "screening_report_id": bank["screening_report_id"],
            "selected_pair_manifest_digest": bank["pair_manifest_digest"],
            "source_manifest_digest": manifest["source_manifest_digest"],
        },
    )[:32]
    return result


def validate_r2_question_bank_row(
    value: object,
    *,
    report: Mapping[str, object],
    source_packets: Sequence[Mapping[str, object]] | None = None,
) -> Mapping[str, Any]:
    row = _exact(value, R2_BANK_ROW_KEYS, "R2 QuestionBank v3 row")
    if row["schema_version"] != R2_BANK_SCHEMA:
        _fail("R2 QuestionBank v3 schema is invalid")
    expected = build_r2_question_bank_row(
        cast(Mapping[str, object], {key: row[key] for key in R2_BANK_FIELDS}),
        report=report,
        source_packets=source_packets,
    )
    if any(row[key] != expected[key] for key in ("id", "canonical_payload", "content_digest")):
        _fail("R2 QuestionBank v3 authority does not replay")
    return row


def _report_members(
    report: Mapping[str, object], group: str, schema: str
) -> dict[str, Mapping[str, Any]]:
    payload = validate_r2_report_payload(report["report_payload"])
    values = payload[group]
    if group == "selected_pair_manifest":
        if not isinstance(values, list) or len(values) != 16:
            _fail("R2 selected pair manifest entries are invalid")
    sequence = values if isinstance(values, list) else [values]
    members: dict[str, Mapping[str, Any]] = {}
    for item in sequence:
        member = _typed_member(item, schema, group)
        members[_member_digest(member, schema, group)] = member
    return members


def validate_r2_pair_qa_payload(
    value: object, *, report: Mapping[str, object]
) -> Mapping[str, Any]:
    qa = _exact(value, R2_PAIR_QA_KEYS, "R2 QuestionPair QA payload")
    if qa["schema_version"] != R2_PAIR_QA_SCHEMA:
        _fail("R2 QuestionPair QA schema is invalid")
    for qa_key, report_key in (
        ("screening_report_id", "id"),
        ("screening_report_digest", "report_digest"),
        ("source_manifest_digest", "source_manifest_digest"),
    ):
        if qa[qa_key] != report[report_key]:
            _fail("R2 QuestionPair QA report binding is invalid")
    bindings = (
        ("source_manifest_entry", "ordered_source_manifest", R2_SOURCE_ENTRY_SCHEMA),
        ("pair_screening_record", "pair_quality_evidence", "mirror.demo/D02PairScreeningRecord/v4"),
        ("selected_pair_entry", "selected_pair_manifest", R2_SELECTED_ENTRY_SCHEMA),
    )
    for prefix, group, schema in bindings:
        if qa[f"{prefix}_schema_version"] != schema:
            _fail("R2 QuestionPair QA member schema is invalid")
        members = _report_members(report, group, schema)
        digest = qa[f"{prefix}_digest"]
        _digest(digest, f"{prefix} digest")
        if prefix != "source_manifest_entry":
            member = _typed_member(qa[f"{prefix}_payload"], schema, prefix)
            if _member_digest(member, schema, prefix) != digest:
                _fail("R2 QuestionPair QA member digest is invalid")
            if members.get(cast(str, digest)) != member:
                _fail("R2 QuestionPair QA member payload is not the Report v3 member")
        if digest not in members:
            _fail("R2 QuestionPair QA member is not in Report v3")
    if qa["selected_pair_manifest_digest"] != report["selected_pair_manifest_digest"]:
        _fail("R2 QuestionPair QA selected manifest binding is invalid")
    return qa


def build_r2_question_pair_row(
    fields: Mapping[str, object],
    *,
    report: Mapping[str, object],
    bank: Mapping[str, object],
    source_packets: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, JsonValue]:
    pair = _exact(fields, R2_PAIR_FIELDS, "R2 QuestionPair v3 input")
    validated_bank = validate_r2_question_bank_row(
        bank, report=report, source_packets=source_packets
    )
    if pair["question_bank_id"] != validated_bank["id"]:
        _fail("R2 QuestionPair bank binding is invalid")
    if (
        pair["screening_report_id"] != report["id"]
        or pair["screening_report_digest"] != report["report_digest"]
    ):
        _fail("R2 QuestionPair row report binding is invalid")
    validate_r2_pair_qa_payload(pair["qa_payload"], report=report)
    if not isinstance(pair["created_at"], str) or not pair["created_at"]:
        _fail("R2 QuestionPair created_at is invalid")
    canonical = cast(
        dict[str, JsonValue], {key: item for key, item in pair.items() if key != "created_at"}
    )
    result: dict[str, JsonValue] = {
        "schema_version": R2_PAIR_SCHEMA,
        **cast(dict[str, JsonValue], dict(pair)),
        "canonical_payload": canonical,
        "content_digest": mirror_demo_digest(R2_PAIR_SCHEMA, canonical),
    }
    qa = cast(Mapping[str, object], pair["qa_payload"])
    source_members = _report_members(report, "ordered_source_manifest", R2_SOURCE_ENTRY_SCHEMA)
    source_entry = source_members.get(cast(str, qa["source_manifest_entry_digest"]))
    if source_entry is None or pair["demo_synthetic_identity_id"] != source_entry.get(
        "source_admission_event_id"
    ):
        _fail("R2 QuestionPair source admission binding is invalid")
    record = _report_members(report, "pair_quality_evidence", R2_PAIR_SCREENING_SCHEMA).get(
        cast(str, qa["pair_screening_record_digest"])
    )
    selected = _report_members(report, "selected_pair_manifest", R2_SELECTED_ENTRY_SCHEMA).get(
        cast(str, qa["selected_pair_entry_digest"])
    )
    if record is None or selected is None:
        _fail("R2 QuestionPair Report membership is invalid")
    record_payload = cast(Mapping[str, Any], record["pair_screening_record_payload"])
    if (
        pair["source_asset_id"] != record_payload["source_asset_id"]
        or pair["source_asset_sha256"] != record_payload["source_asset_sha256"]
        or pair["dimension_key"] != record_payload["dimension_key"]
        or pair["magnitude_ppm"] != record_payload["magnitude_ppm"]
        or pair["pair_quality_ppm"] != record_payload["pair_quality_ppm"]
        or pair["dimension_key"] != selected["dimension_key"]
        or pair["magnitude_ppm"] != selected["magnitude_ppm"]
        or pair["left_asset_id"] != selected["left_result_asset_id"]
        or pair["right_asset_id"] != selected["right_result_asset_id"]
        or pair["left_asset_sha256"] != selected["left_result_asset_sha256"]
        or pair["right_asset_sha256"] != selected["right_result_asset_sha256"]
        or pair["left_asset_variant_id"] != selected["left_asset_variant_id"]
        or pair["right_asset_variant_id"] != selected["right_asset_variant_id"]
    ):
        _fail("R2 QuestionPair common projection is invalid")
    result["id"] = mirror_demo_digest(
        R2_PAIR_ID_DOMAIN,
        {
            "dimension_key": cast(JsonValue, pair["dimension_key"]),
            "magnitude_ppm": cast(JsonValue, pair["magnitude_ppm"]),
            "pair_screening_record_digest": cast(JsonValue, qa["pair_screening_record_digest"]),
            "question_bank_id": cast(JsonValue, pair["question_bank_id"]),
            "source_admission_event_id": cast(JsonValue, source_entry["source_admission_event_id"]),
            "source_manifest_entry_digest": cast(JsonValue, qa["source_manifest_entry_digest"]),
            "selected_pair_entry_digest": cast(JsonValue, qa["selected_pair_entry_digest"]),
        },
    )[:32]
    return result


def validate_r2_question_pair_row(
    value: object,
    *,
    report: Mapping[str, object],
    bank: Mapping[str, object],
    source_packets: Sequence[Mapping[str, object]] | None = None,
) -> Mapping[str, Any]:
    row = _exact(value, R2_PAIR_ROW_KEYS, "R2 QuestionPair v3 row")
    if row["schema_version"] != R2_PAIR_SCHEMA:
        _fail("R2 QuestionPair v3 schema is invalid")
    expected = build_r2_question_pair_row(
        cast(Mapping[str, object], {key: row[key] for key in R2_PAIR_FIELDS}),
        report=report,
        bank=bank,
        source_packets=source_packets,
    )
    if any(row[key] != expected[key] for key in ("id", "canonical_payload", "content_digest")):
        _fail("R2 QuestionPair v3 authority does not replay")
    return row
