"""Canonical generic D02 screening, QuestionBank, and pair authority.

The autonomous acquisition manifest selects Candidates.  This module builds a
separate formal-source manifest after normalization and formal QA, then binds
the complete screening graph to both manifests without changing legacy R2 v3
semantics.  It performs no filesystem, Provider, network, or database access.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_r2_authority as r2
from mirror_api.demo_d02_generic_admission import (
    IDENTITY_SCHEMA,
    SOURCE_SCHEMA,
    GenericAdmissionError,
    GenericSourceInput,
    validate_identity_row,
    validate_source_authority,
)
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest

REPORT_SCHEMA: Final = "mirror.demo/D02GenericPairScreeningReport/v1"
REPORT_ID_SCHEMA: Final = "mirror.demo/D02GenericPairScreeningReportId/v1"
BANK_SCHEMA: Final = "mirror.demo/D02GenericQuestionBank/v1"
BANK_ID_SCHEMA: Final = "mirror.demo/D02GenericQuestionBankId/v1"
PAIR_SCHEMA: Final = "mirror.demo/D02GenericQuestionPair/v1"
PAIR_ID_SCHEMA: Final = "mirror.demo/D02GenericQuestionPairId/v1"
SOURCE_ENTRY_SCHEMA: Final = "mirror.demo/D02GenericSourceManifestEntry/v1"
FORMAL_SOURCE_MANIFEST_SCHEMA: Final = "mirror.demo/D02GenericFormalSourceManifest/v1"
SELECTED_SOURCE_BINDING_SCHEMA: Final = "mirror.demo/D02SelectedSourceBinding/v1"
DIMENSION_MANIFEST_SCHEMA: Final = "mirror.demo/D02GenericDimensionManifest/v1"
PAIR_QA_SCHEMA: Final = "mirror.demo/D02GenericQuestionPairQAPayload/v1"
SELECTED_PAIR_MANIFEST_SCHEMA: Final = "mirror.demo/D02GenericSelectedPairManifest/v1"
ASSET_ENTRY_SCHEMA: Final = "mirror.demo/D02GenericScreeningAssetEntry/v1"
VARIANT_ENTRY_SCHEMA: Final = "mirror.demo/D02GenericScreeningVariantEntry/v1"

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[0-9a-f]{32}\Z")
_REPORT_FIELDS: Final = frozenset(r2.R2_REPORT_FIELDS)
_BANK_FIELDS: Final = frozenset(r2.R2_BANK_FIELDS)
_PAIR_FIELDS: Final = frozenset(r2.R2_PAIR_FIELDS)
_EXTRA_REPORT_GROUPS: Final = {
    "selected_source_manifest_binding",
    "asset_authority_manifest",
    "asset_variant_manifest",
}
_ASSET_ENTRY_FIELDS: Final = frozenset(
    {
        "schema_version",
        "asset_id",
        "sha256",
        "byte_size",
        "mime_type",
        "width",
        "height",
        "asset_kind",
        "source_ordinal",
        "case_ordinal",
        "record_digest",
    }
)
_VARIANT_ENTRY_FIELDS: Final = frozenset(
    {
        "schema_version",
        "variant_id",
        "source_asset_id",
        "result_asset_id",
        "variant_type",
        "source_ordinal",
        "case_ordinal",
        "record_digest",
    }
)
_REPORT_GROUPS: Final = frozenset(r2.R2_REPORT_PAYLOAD_KEYS) | _EXTRA_REPORT_GROUPS
_FIXED_COUNTS: Final = {
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


def _fail(message: str) -> NoReturn:
    raise GenericAdmissionError(message)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _exact(value: object, keys: set[str] | frozenset[str], label: str) -> Mapping[str, object]:
    item = _mapping(value, label)
    if set(item) != set(keys):
        _fail(f"{label} has unknown or missing fields")
    return item


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        _fail(f"{label} must be a 32-character identifier")
    return value


def _integer(value: object, label: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} is invalid")
    return value


def _hash(schema: str, payload: Mapping[str, object]) -> str:
    return mirror_demo_digest(schema, cast(Mapping[str, JsonValue], payload))


def _manifest_hash(schema: str, entries: Sequence[Mapping[str, object]]) -> str:
    return _hash(schema, {"ordered_entries": list(entries)})


def _reject_noncanonical(value: object) -> None:
    if isinstance(value, float):
        _fail("generic authority rejects floating-point JSON")
    if isinstance(value, Mapping):
        for nested in value.values():
            _reject_noncanonical(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_noncanonical(nested)


def _record_digest(schema: str, value: Mapping[str, object], field: str) -> str:
    return _hash(
        schema, {key: item for key, item in value.items() if key not in {"schema_version", field}}
    )


def _validate_evidence_member(value: object, *, schema: str, label: str) -> Mapping[str, object]:
    member = _mapping(value, label)
    _reject_noncanonical(member)
    if member.get("schema_version") != schema or len(member) < 4:
        _fail(f"{label} schema or shape is invalid")
    if "record_digest" in member:
        if _digest(member["record_digest"], f"{label} record digest") != _record_digest(
            schema, member, "record_digest"
        ):
            _fail(f"{label} record digest does not replay")
    elif "entry_digest" in member:
        if _digest(member["entry_digest"], f"{label} entry digest") != _record_digest(
            schema, member, "entry_digest"
        ):
            _fail(f"{label} entry digest does not replay")
    elif "pair_screening_record_digest" in member:
        payload = _mapping(member.get("pair_screening_record_payload"), f"{label} payload")
        if _digest(member["pair_screening_record_digest"], f"{label} pair digest") != _hash(
            schema, payload
        ):
            _fail(f"{label} pair digest does not replay")
    elif not any(
        isinstance(item, str) and _DIGEST.fullmatch(item) is not None
        for key, item in member.items()
        if key.endswith("_digest")
    ):
        _fail(f"{label} lacks replayable digest evidence")
    return member


def build_source_manifest_entry(
    *,
    source_input: GenericSourceInput,
    source_row: Mapping[str, object],
    identity_row: Mapping[str, object],
    selected_source_manifest_id: str,
    selected_source_manifest_digest: str,
) -> dict[str, object]:
    """Project one generic formal source and v5 identity into screening."""

    manifest_id = _id(selected_source_manifest_id, "selected source manifest ID")
    manifest_digest = _digest(selected_source_manifest_digest, "selected source manifest digest")
    validate_source_authority(source_input, source_row=source_row)
    validate_identity_row(
        source_input,
        source_row=source_row,
        identity_row=identity_row,
    )
    if source_row.get("schema_version") != SOURCE_SCHEMA:
        _fail("formal source uses an unsupported schema")
    if identity_row.get("schema_version") != IDENTITY_SCHEMA:
        _fail("formal source identity uses an unsupported schema")
    if (
        source_row.get("selected_source_manifest_id") != manifest_id
        or source_row.get("r2_source_authority_record_id") is not None
        or identity_row.get("r2_source_authority_record_id") != source_row.get("id")
    ):
        _fail("formal source, identity, and selected manifest do not match")
    position = _integer(source_row.get("manifest_position"), "formal source position")
    if position not in {1, 2, 3, 4} or source_row.get("source_ordinal") != position:
        _fail("formal source position is invalid")
    for key, identity_key in (
        ("source_output_id", "source_output_id"),
        ("source_asset_id", "formal_canonical_asset_id"),
        ("source_asset_sha256", "formal_canonical_asset_sha256"),
        ("source_authority_digest", "source_authority_digest"),
        ("source_authority_key", "source_authority_key"),
        ("source_qa_snapshot_digest", "source_qa_snapshot_digest"),
        ("source_provenance_digest", "source_provenance_digest"),
    ):
        if source_row.get(key) != identity_row.get(identity_key):
            _fail(f"formal source identity projection disagrees for {key}")
    if identity_row.get("source_receipt_digest") is not None:
        _fail("generic formal source must not acquire a legacy receipt")
    fact_snapshot = _mapping(identity_row.get("source_fact_snapshot"), "formal source facts")
    measurement_projection = _mapping(
        identity_row.get("source_measurement_projection"), "formal measurement projection"
    )
    payload: dict[str, object] = {
        "source_ordinal": position,
        "selected_source_manifest_id": manifest_id,
        "selected_source_manifest_digest": manifest_digest,
        "acquisition_candidate_id": _id(
            source_row.get("acquisition_candidate_id"), "acquisition Candidate ID"
        ),
        "r2_source_authority_record_id": _id(source_row.get("id"), "formal source row ID"),
        "source_authority_key": _digest(
            source_row.get("source_authority_key"), "source authority key"
        ),
        "source_authority_digest": _digest(
            source_row.get("source_authority_digest"), "source authority digest"
        ),
        "source_admission_event_id": _id(identity_row.get("id"), "source identity ID"),
        "source_admission_content_digest": _digest(
            identity_row.get("content_digest"), "source identity digest"
        ),
        "source_output_id": source_row.get("source_output_id"),
        "source_asset_id": _id(source_row.get("source_asset_id"), "source Asset ID"),
        "source_asset_sha256": _digest(
            source_row.get("source_asset_sha256"), "source Asset SHA-256"
        ),
        "source_asset_byte_size": _integer(
            source_row.get("source_asset_byte_size"), "source Asset byte size"
        ),
        "source_asset_mime_type": source_row.get("source_asset_mime_type"),
        "source_asset_width": _integer(source_row.get("source_asset_width"), "source Asset width"),
        "source_asset_height": _integer(
            source_row.get("source_asset_height"), "source Asset height"
        ),
        "source_qa_snapshot_digest": _digest(
            source_row.get("source_qa_snapshot_digest"), "formal source QA digest"
        ),
        "source_landmark_digest": _digest(
            identity_row.get("source_landmark_digest"), "source landmark digest"
        ),
        "source_measurement_digest": _digest(
            identity_row.get("source_measurement_digest"), "source measurement digest"
        ),
        "source_provenance_digest": _digest(
            source_row.get("source_provenance_digest"), "source provenance digest"
        ),
        "source_fact_snapshot": dict(fact_snapshot),
        "source_fact_snapshot_digest": _digest(
            identity_row.get("source_fact_snapshot_digest"), "source facts digest"
        ),
        "source_measurement_projection": dict(measurement_projection),
        "source_measurement_projection_digest": _digest(
            identity_row.get("source_measurement_projection_digest"),
            "source measurement projection digest",
        ),
        "adult_synthetic_attested": identity_row.get("adult_synthetic_attested"),
    }
    if (
        payload["source_asset_mime_type"] != "image/jpeg"
        or payload["adult_synthetic_attested"] is not True
    ):
        _fail("generic formal source must be an adult synthetic JPEG")
    return {
        "schema_version": SOURCE_ENTRY_SCHEMA,
        **payload,
        "record_digest": _hash(SOURCE_ENTRY_SCHEMA, payload),
    }


def build_formal_source_manifest(
    *,
    source_inputs: Sequence[GenericSourceInput],
    source_rows: Sequence[Mapping[str, object]],
    identity_rows: Sequence[Mapping[str, object]],
    selected_source_manifest_id: str,
    selected_source_manifest_digest: str,
) -> tuple[list[dict[str, object]], str]:
    if len(source_inputs) != 4 or len(source_rows) != 4 or len(identity_rows) != 4:
        _fail("formal source manifest requires exactly four sources and identities")
    entries = [
        build_source_manifest_entry(
            source_input=source_input,
            source_row=source,
            identity_row=identity,
            selected_source_manifest_id=selected_source_manifest_id,
            selected_source_manifest_digest=selected_source_manifest_digest,
        )
        for source_input, source, identity in zip(
            source_inputs, source_rows, identity_rows, strict=True
        )
    ]
    if [entry["source_ordinal"] for entry in entries] != [1, 2, 3, 4]:
        _fail("formal source manifest order is invalid")
    for key in (
        "acquisition_candidate_id",
        "r2_source_authority_record_id",
        "source_admission_event_id",
        "source_asset_id",
        "record_digest",
    ):
        if len({entry[key] for entry in entries}) != 4:
            _fail(f"formal source manifest {key} values must be unique")
    return entries, _manifest_hash(FORMAL_SOURCE_MANIFEST_SCHEMA, entries)


def build_asset_manifest_entry(
    *,
    asset_id: str,
    sha256: str,
    byte_size: int,
    mime_type: str,
    width: int,
    height: int,
    asset_kind: str,
    source_ordinal: int,
    case_ordinal: int | None,
) -> dict[str, object]:
    if asset_kind not in {"SOURCE", "RESULT"}:
        _fail("screening Asset kind is invalid")
    ordinal = _integer(source_ordinal, "screening Asset source ordinal")
    if ordinal not in {1, 2, 3, 4}:
        _fail("screening Asset source ordinal is invalid")
    if (asset_kind == "SOURCE") != (case_ordinal is None):
        _fail("screening Asset case binding is invalid")
    if case_ordinal is not None and not 1 <= case_ordinal <= 48:
        _fail("screening Asset case ordinal is invalid")
    payload = {
        "asset_id": _id(asset_id, "screening Asset ID"),
        "sha256": _digest(sha256, "screening Asset SHA-256"),
        "byte_size": _integer(byte_size, "screening Asset byte size"),
        "mime_type": mime_type,
        "width": _integer(width, "screening Asset width"),
        "height": _integer(height, "screening Asset height"),
        "asset_kind": asset_kind,
        "source_ordinal": ordinal,
        "case_ordinal": case_ordinal,
    }
    if mime_type != "image/jpeg":
        _fail("screening Assets must be JPEG")
    return {
        "schema_version": ASSET_ENTRY_SCHEMA,
        **payload,
        "record_digest": _hash(ASSET_ENTRY_SCHEMA, payload),
    }


def build_variant_manifest_entry(
    *,
    variant_id: str,
    source_asset_id: str,
    result_asset_id: str,
    source_ordinal: int,
    case_ordinal: int,
) -> dict[str, object]:
    ordinal = _integer(source_ordinal, "Variant source ordinal")
    case = _integer(case_ordinal, "Variant case ordinal")
    if ordinal not in {1, 2, 3, 4} or not 1 <= case <= 48:
        _fail("Variant ordinal binding is invalid")
    source_id = _id(source_asset_id, "Variant source Asset ID")
    result_id = _id(result_asset_id, "Variant result Asset ID")
    if source_id == result_id:
        _fail("Variant source and result Assets must differ")
    payload = {
        "variant_id": _id(variant_id, "AssetVariant ID"),
        "source_asset_id": source_id,
        "result_asset_id": result_id,
        "variant_type": "demo_p3_p7_geometry_v1",
        "source_ordinal": ordinal,
        "case_ordinal": case,
    }
    return {
        "schema_version": VARIANT_ENTRY_SCHEMA,
        **payload,
        "record_digest": _hash(VARIANT_ENTRY_SCHEMA, payload),
    }


def _validate_asset_manifests(
    payload: Mapping[str, object], sources: Sequence[Mapping[str, object]]
) -> None:
    assets = payload.get("asset_authority_manifest")
    variants = payload.get("asset_variant_manifest")
    if not isinstance(assets, list) or len(assets) != 52:
        _fail("generic screening requires exactly 52 Asset entries")
    if not isinstance(variants, list) or len(variants) != 48:
        _fail("generic screening requires exactly 48 AssetVariant entries")
    parsed_assets = []
    for item in assets:
        parsed_assets.append(
            _validate_evidence_member(
                _exact(item, _ASSET_ENTRY_FIELDS, "Asset manifest entry"),
                schema=ASSET_ENTRY_SCHEMA,
                label="Asset manifest entry",
            )
        )
    parsed_variants = [
        _validate_evidence_member(
            _exact(item, _VARIANT_ENTRY_FIELDS, "AssetVariant manifest entry"),
            schema=VARIANT_ENTRY_SCHEMA,
            label="AssetVariant manifest entry",
        )
        for item in variants
    ]
    if len({item["asset_id"] for item in parsed_assets}) != 52:
        _fail("screening Asset IDs must be unique")
    if len({item["variant_id"] for item in parsed_variants}) != 48:
        _fail("screening AssetVariant IDs must be unique")
    source_assets = [item for item in parsed_assets if item.get("asset_kind") == "SOURCE"]
    result_assets = [item for item in parsed_assets if item.get("asset_kind") == "RESULT"]
    if len(source_assets) != 4 or len(result_assets) != 48:
        _fail("screening Asset role cardinality is invalid")
    if [item.get("asset_id") for item in source_assets] != [
        item.get("source_asset_id") for item in sources
    ]:
        _fail("screening source Asset manifest is not the formal source projection")
    for asset, source in zip(source_assets, sources, strict=True):
        for asset_key, source_key in (
            ("sha256", "source_asset_sha256"),
            ("byte_size", "source_asset_byte_size"),
            ("mime_type", "source_asset_mime_type"),
            ("width", "source_asset_width"),
            ("height", "source_asset_height"),
            ("source_ordinal", "source_ordinal"),
        ):
            if asset.get(asset_key) != source.get(source_key):
                _fail(f"screening source Asset {asset_key} does not replay")
    result_ids = {item["asset_id"] for item in result_assets}
    if {item["result_asset_id"] for item in parsed_variants} != result_ids:
        _fail("every result Asset must have exactly one AssetVariant")
    source_ids = {item["asset_id"] for item in source_assets}
    if {item["source_asset_id"] for item in parsed_variants} != source_ids:
        _fail("AssetVariants must use all four formal source Assets")
    if Counter(cast(int, item["source_ordinal"]) for item in parsed_variants) != Counter(
        {1: 12, 2: 12, 3: 12, 4: 12}
    ):
        _fail("AssetVariant source distribution is invalid")
    if {cast(int, item["case_ordinal"]) for item in result_assets} != set(range(1, 49)):
        _fail("screening result Asset case ordinals are invalid")
    if {cast(int, item["case_ordinal"]) for item in parsed_variants} != set(range(1, 49)):
        _fail("screening AssetVariant case ordinals are invalid")
    assets_by_id = {item["asset_id"]: item for item in parsed_assets}
    source_by_ordinal = {item["source_ordinal"]: item["asset_id"] for item in source_assets}
    for variant in parsed_variants:
        result = assets_by_id.get(variant["result_asset_id"])
        if (
            result is None
            or result.get("asset_kind") != "RESULT"
            or result.get("source_ordinal") != variant.get("source_ordinal")
            or result.get("case_ordinal") != variant.get("case_ordinal")
            or variant.get("source_asset_id")
            != source_by_ordinal.get(variant.get("source_ordinal"))
        ):
            _fail("screening AssetVariant authority does not match its Assets")


def _validate_common_groups(payload: Mapping[str, object]) -> None:
    for name, schema, count in r2.R2_REPORT_GROUPS:
        if name == "ordered_source_manifest":
            continue
        group = payload.get(name)
        if name == "selected_pair_manifest":
            if not isinstance(group, list):
                _fail("selected pair manifest must be an ordered list")
            for item in group:
                _validate_evidence_member(
                    item, schema=r2.R2_SELECTED_ENTRY_SCHEMA, label="selected pair entry"
                )
            continue
        if count == 1:
            _validate_evidence_member(group, schema=schema, label=name)
            continue
        if not isinstance(group, list) or len(group) != count:
            _fail(f"{name} cardinality is invalid")
        for item in group:
            _validate_evidence_member(item, schema=schema, label=name)


def _nested_source(value: object, *, pair_wrapper: bool = False) -> Mapping[str, object]:
    member = _mapping(value, "source-bound evidence")
    if pair_wrapper:
        return _mapping(member.get("pair_screening_record_payload"), "pair screening payload")
    return member


def _validate_source_distribution(
    payload: Mapping[str, object], sources: Sequence[Mapping[str, object]]
) -> None:
    groups = (
        ("ordered_case_manifest", 12, False),
        ("source_m3_repeat_evidence", 3, False),
        ("pair_quality_evidence", 6, True),
        ("selected_pair_manifest", 4, False),
    )
    for name, per_source, wrapped in groups:
        raw = payload.get(name)
        if not isinstance(raw, list):
            _fail(f"{name} must be a list")
        counts: Counter[int] = Counter()
        for item in raw:
            member = _nested_source(item, pair_wrapper=wrapped)
            ordinal = _integer(member.get("source_ordinal"), f"{name} source ordinal")
            if ordinal not in {1, 2, 3, 4}:
                _fail(f"{name} source ordinal is invalid")
            counts[ordinal] += 1
            source = sources[ordinal - 1]
            for key in (
                "source_authority_key",
                "source_admission_event_id",
                "source_asset_id",
                "source_asset_sha256",
                "r2_source_authority_record_id",
            ):
                if key in member and member[key] != source.get(key):
                    _fail(f"{name} source projection disagrees for {key}")
        if counts != Counter({1: per_source, 2: per_source, 3: per_source, 4: per_source}):
            _fail(f"{name} source distribution is invalid")


def _selected_source_binding(
    *, selected_source_manifest_id: str, selected_source_manifest_digest: str, formal_digest: str
) -> dict[str, object]:
    payload = {
        "selected_source_manifest_id": _id(
            selected_source_manifest_id, "selected source manifest ID"
        ),
        "selected_source_manifest_digest": _digest(
            selected_source_manifest_digest, "selected source manifest digest"
        ),
        "formal_source_manifest_digest": _digest(formal_digest, "formal source manifest digest"),
        "source_count": 4,
    }
    return {
        "schema_version": SELECTED_SOURCE_BINDING_SCHEMA,
        **payload,
        "binding_digest": _hash(SELECTED_SOURCE_BINDING_SCHEMA, payload),
    }


def _validate_selected_pair_order(
    selected: Sequence[object], *, selected_dimensions: Sequence[object]
) -> None:
    if len(selected) != 16 or len(selected_dimensions) != 2:
        _fail("generic selected pair order is incomplete")
    members = [_mapping(item, "selected pair entry") for item in selected]
    for key in (
        "entry_digest",
        "pair_record_id",
        "pair_screening_record_digest",
        "left_result_asset_id",
        "right_result_asset_id",
        "left_asset_variant_id",
        "right_asset_variant_id",
    ):
        values = [member.get(key) for member in members]
        expected_count = 32 if key.startswith(("left_", "right_")) else 16
        if key.startswith(("left_", "right_")):
            continue
        if len(set(values)) != expected_count:
            _fail(f"generic selected pair {key} values must be unique")
    side_assets = {
        cast(str, member[key])
        for member in members
        for key in ("left_result_asset_id", "right_result_asset_id")
    }
    side_variants = {
        cast(str, member[key])
        for member in members
        for key in ("left_asset_variant_id", "right_asset_variant_id")
    }
    if len(side_assets) != 32 or len(side_variants) != 32:
        _fail("generic selected result sides must be unique")
    expected_sources = [1, 1, 2, 2, 3, 3, 4, 4] * 2
    expected_magnitudes = [15000, 30000] * 8
    expected_slots = [1] * 8 + [2] * 8
    for index, member in enumerate(members):
        if (
            member.get("selected_pair_ordinal") != index + 1
            or member.get("selected_dimension_slot") != expected_slots[index]
            or member.get("dimension_key") != selected_dimensions[expected_slots[index] - 1]
            or member.get("source_ordinal") != expected_sources[index]
            or member.get("magnitude_ppm") != expected_magnitudes[index]
        ):
            _fail("generic selected pair fixed order is invalid")


def build_report_row(
    fields: Mapping[str, object],
    *,
    source_inputs: Sequence[GenericSourceInput],
    source_rows: Sequence[Mapping[str, object]],
    identity_rows: Sequence[Mapping[str, object]],
    selected_source_manifest_id: str,
    selected_source_manifest_digest: str,
) -> dict[str, object]:
    row = _exact(fields, _REPORT_FIELDS, "generic screening Report input")
    entries, formal_digest = build_formal_source_manifest(
        source_inputs=source_inputs,
        source_rows=source_rows,
        identity_rows=identity_rows,
        selected_source_manifest_id=selected_source_manifest_id,
        selected_source_manifest_digest=selected_source_manifest_digest,
    )
    payload = dict(_mapping(row.get("report_payload"), "generic screening Report payload"))
    expected_binding = _selected_source_binding(
        selected_source_manifest_id=selected_source_manifest_id,
        selected_source_manifest_digest=selected_source_manifest_digest,
        formal_digest=formal_digest,
    )
    for key, expected_value in (
        ("ordered_source_manifest", entries),
        ("selected_source_manifest_binding", expected_binding),
    ):
        if key in payload and payload[key] != expected_value:
            _fail(f"generic screening Report {key} does not replay")
        payload[key] = expected_value
    if set(payload) != set(_REPORT_GROUPS):
        _fail("generic screening Report groups are incomplete or unknown")
    _validate_common_groups(payload)
    _validate_asset_manifests(payload, entries)
    _validate_source_distribution(payload, entries)
    if row.get("source_manifest_digest") != formal_digest:
        _fail("Report formal source manifest digest is invalid")
    for key, expected_count in _FIXED_COUNTS.items():
        if row.get(key) != expected_count:
            _fail(f"generic screening Report {key} is invalid")
    status = row.get("status")
    selected = payload.get("selected_pair_manifest")
    if not isinstance(selected, list):
        _fail("selected pair manifest is invalid")
    expected_selected_digest = _manifest_hash(SELECTED_PAIR_MANIFEST_SCHEMA, selected)
    if status != "PASSED":
        _fail("generic admission only accepts a PASSED screening Report")
    if (
        row.get("selected_pair_count") != 16
        or row.get("selected_result_side_count") != 32
        or len(selected) != 16
        or row.get("selected_pair_manifest_digest") != expected_selected_digest
    ):
        _fail("generic screening selected-pair projection is invalid")
    eligible = row.get("eligible_dimension_keys")
    selected_dimensions = row.get("selected_dimension_keys")
    if (
        not isinstance(eligible, list)
        or len(eligible) < 2
        or len(set(eligible)) != len(eligible)
        or not isinstance(selected_dimensions, list)
        or len(selected_dimensions) != 2
        or len(set(selected_dimensions)) != 2
        or not set(selected_dimensions).issubset(set(eligible))
    ):
        _fail("generic screening dimension selection is invalid")
    _validate_selected_pair_order(selected, selected_dimensions=selected_dimensions)
    _reject_noncanonical(row)
    canonical = {
        key: (payload if key == "report_payload" else row[key])
        for key in _REPORT_FIELDS
        if key != "created_at"
    }
    report_digest = _hash(REPORT_SCHEMA, payload)
    return {
        "id": _hash(
            REPORT_ID_SCHEMA,
            {
                "report_digest": report_digest,
                "formal_source_manifest_digest": formal_digest,
                "selected_source_manifest_id": selected_source_manifest_id,
                "selected_source_manifest_digest": selected_source_manifest_digest,
                "case_manifest_digest": row["case_manifest_digest"],
            },
        )[:32],
        "schema_version": REPORT_SCHEMA,
        **dict(row),
        "report_payload": payload,
        "report_digest": report_digest,
        "canonical_payload": canonical,
        "content_digest": _hash(REPORT_SCHEMA, canonical),
    }


def validate_report_row(
    value: object,
    *,
    source_inputs: Sequence[GenericSourceInput],
    source_rows: Sequence[Mapping[str, object]],
    identity_rows: Sequence[Mapping[str, object]],
    selected_source_manifest_id: str,
    selected_source_manifest_digest: str,
) -> Mapping[str, object]:
    row = _mapping(value, "generic screening Report row")
    if row.get("schema_version") != REPORT_SCHEMA:
        _fail("generic screening Report schema is invalid")
    expected = build_report_row(
        {key: row[key] for key in _REPORT_FIELDS},
        source_inputs=source_inputs,
        source_rows=source_rows,
        identity_rows=identity_rows,
        selected_source_manifest_id=selected_source_manifest_id,
        selected_source_manifest_digest=selected_source_manifest_digest,
    )
    if dict(row) != expected:
        _fail("generic screening Report does not replay")
    return row


def build_question_bank_row(
    fields: Mapping[str, object],
    *,
    report: Mapping[str, object],
    selected_source_manifest_id: str,
    selected_source_manifest_digest: str,
) -> dict[str, object]:
    bank = _exact(fields, _BANK_FIELDS, "generic QuestionBank input")
    if (
        bank.get("screening_report_id") != report.get("id")
        or bank.get("screening_report_digest") != report.get("report_digest")
        or bank.get("pair_manifest_digest") != report.get("selected_pair_manifest_digest")
    ):
        _fail("generic QuestionBank Report binding is invalid")
    manifest = _exact(
        bank.get("dimension_manifest"),
        {
            "schema_version",
            "screening_report_id",
            "screening_report_digest",
            "selected_source_manifest_id",
            "selected_source_manifest_digest",
            "formal_source_manifest_digest",
            "selected_pair_manifest_digest",
            "selected_dimensions",
        },
        "generic QuestionBank dimension manifest",
    )
    if (
        manifest.get("schema_version") != DIMENSION_MANIFEST_SCHEMA
        or manifest.get("screening_report_id") != report.get("id")
        or manifest.get("screening_report_digest") != report.get("report_digest")
        or manifest.get("selected_source_manifest_id") != selected_source_manifest_id
        or manifest.get("selected_source_manifest_digest") != selected_source_manifest_digest
        or manifest.get("formal_source_manifest_digest") != report.get("source_manifest_digest")
        or manifest.get("selected_pair_manifest_digest")
        != report.get("selected_pair_manifest_digest")
    ):
        _fail("generic QuestionBank manifest binding is invalid")
    dimensions = manifest.get("selected_dimensions")
    selected_entries = _mapping(report.get("report_payload"), "Report payload").get(
        "selected_pair_manifest"
    )
    if not isinstance(dimensions, list) or len(dimensions) != 2:
        _fail("generic QuestionBank requires two selected dimensions")
    if not isinstance(selected_entries, list) or len(selected_entries) != 16:
        _fail("generic QuestionBank selected pair authority is incomplete")
    observed: list[object] = []
    for index, dimension in enumerate(dimensions):
        item = _mapping(dimension, "generic selected dimension")
        entries = item.get("ordered_selected_pair_entry_digests")
        if (
            item.get("dimension_key")
            != cast(list[object], report.get("selected_dimension_keys"))[index]
            or not isinstance(entries, list)
            or len(entries) != 8
        ):
            _fail("generic selected dimension projection is invalid")
        observed.extend(entries)
    expected = [
        _mapping(item, "selected pair entry").get("entry_digest") for item in selected_entries
    ]
    if observed != expected or len(set(observed)) != 16:
        _fail("generic QuestionBank selected-pair order is invalid")
    canonical = {key: bank[key] for key in _BANK_FIELDS if key != "created_at"}
    return {
        "id": _hash(
            BANK_ID_SCHEMA,
            {
                "algorithm_config_digest": bank["algorithm_config_digest"],
                "screening_report_id": report["id"],
                "screening_report_digest": report["report_digest"],
                "formal_source_manifest_digest": report["source_manifest_digest"],
                "selected_source_manifest_id": selected_source_manifest_id,
                "selected_pair_manifest_digest": bank["pair_manifest_digest"],
            },
        )[:32],
        "schema_version": BANK_SCHEMA,
        **dict(bank),
        "canonical_payload": canonical,
        "content_digest": _hash(BANK_SCHEMA, canonical),
    }


def validate_question_bank_row(
    value: object,
    *,
    report: Mapping[str, object],
    selected_source_manifest_id: str,
    selected_source_manifest_digest: str,
) -> Mapping[str, object]:
    row = _mapping(value, "generic QuestionBank row")
    if row.get("schema_version") != BANK_SCHEMA:
        _fail("generic QuestionBank schema is invalid")
    expected = build_question_bank_row(
        {key: row[key] for key in _BANK_FIELDS},
        report=report,
        selected_source_manifest_id=selected_source_manifest_id,
        selected_source_manifest_digest=selected_source_manifest_digest,
    )
    if dict(row) != expected:
        _fail("generic QuestionBank does not replay")
    return row


def build_question_pair_row(
    fields: Mapping[str, object],
    *,
    report: Mapping[str, object],
    bank: Mapping[str, object],
) -> dict[str, object]:
    pair = _exact(fields, _PAIR_FIELDS, "generic QuestionPair input")
    if (
        pair.get("question_bank_id") != bank.get("id")
        or pair.get("screening_report_id") != report.get("id")
        or pair.get("screening_report_digest") != report.get("report_digest")
    ):
        _fail("generic QuestionPair Bank or Report binding is invalid")
    payload = _mapping(report.get("report_payload"), "generic Report payload")
    binding = _mapping(payload.get("selected_source_manifest_binding"), "selected source binding")
    qa = _exact(
        pair.get("qa_payload"),
        {
            "schema_version",
            "screening_report_id",
            "screening_report_digest",
            "selected_source_manifest_id",
            "selected_source_manifest_digest",
            "formal_source_manifest_digest",
            "source_manifest_entry_schema_version",
            "source_manifest_entry_digest",
            "pair_screening_record_schema_version",
            "pair_screening_record_digest",
            "pair_screening_record_payload",
            "selected_pair_manifest_digest",
            "selected_pair_entry_schema_version",
            "selected_pair_entry_digest",
            "selected_pair_entry_payload",
        },
        "generic QuestionPair QA payload",
    )
    if (
        qa.get("schema_version") != PAIR_QA_SCHEMA
        or qa.get("screening_report_id") != report.get("id")
        or qa.get("screening_report_digest") != report.get("report_digest")
        or qa.get("selected_source_manifest_id") != binding.get("selected_source_manifest_id")
        or qa.get("selected_source_manifest_digest")
        != binding.get("selected_source_manifest_digest")
        or qa.get("formal_source_manifest_digest") != report.get("source_manifest_digest")
        or qa.get("selected_pair_manifest_digest") != report.get("selected_pair_manifest_digest")
        or qa.get("source_manifest_entry_schema_version") != SOURCE_ENTRY_SCHEMA
        or qa.get("pair_screening_record_schema_version") != r2.R2_PAIR_SCREENING_SCHEMA
        or qa.get("selected_pair_entry_schema_version") != r2.R2_SELECTED_ENTRY_SCHEMA
    ):
        _fail("generic QuestionPair QA binding is invalid")
    sources = payload.get("ordered_source_manifest")
    pairs = payload.get("pair_quality_evidence")
    selected = payload.get("selected_pair_manifest")
    if (
        not isinstance(sources, list)
        or not isinstance(pairs, list)
        or not isinstance(selected, list)
    ):
        _fail("generic Report pair authority is incomplete")
    source = next(
        (
            _mapping(item, "generic source entry")
            for item in sources
            if _mapping(item, "generic source entry").get("record_digest")
            == qa.get("source_manifest_entry_digest")
        ),
        None,
    )
    pair_wrapper = next(
        (
            _mapping(item, "pair screening record")
            for item in pairs
            if _mapping(item, "pair screening record").get("pair_screening_record_digest")
            == qa.get("pair_screening_record_digest")
        ),
        None,
    )
    selected_entry = next(
        (
            _mapping(item, "selected pair entry")
            for item in selected
            if _mapping(item, "selected pair entry").get("entry_digest")
            == qa.get("selected_pair_entry_digest")
        ),
        None,
    )
    if source is None or pair_wrapper is None or selected_entry is None:
        _fail("generic QuestionPair Report membership is invalid")
    pair_payload = _mapping(
        pair_wrapper.get("pair_screening_record_payload"), "pair screening payload"
    )
    if (
        qa.get("pair_screening_record_payload") != pair_wrapper
        or qa.get("selected_pair_entry_payload") != selected_entry
        or pair.get("demo_synthetic_identity_id") != source.get("source_admission_event_id")
        or pair.get("source_asset_id") != source.get("source_asset_id")
        or pair.get("source_asset_sha256") != source.get("source_asset_sha256")
        or pair_payload.get("source_admission_event_id") != pair.get("demo_synthetic_identity_id")
        or pair_payload.get("source_asset_id") != pair.get("source_asset_id")
        or pair_payload.get("source_asset_sha256") != pair.get("source_asset_sha256")
        or pair_payload.get("dimension_key") != pair.get("dimension_key")
        or pair_payload.get("magnitude_ppm") != pair.get("magnitude_ppm")
        or pair_payload.get("pair_quality_ppm") != pair.get("pair_quality_ppm")
        or pair_payload.get("pair_gate_passed") is not True
        or selected_entry.get("pair_screening_record_digest")
        != pair_wrapper.get("pair_screening_record_digest")
    ):
        _fail("generic QuestionPair source or screening projection is invalid")
    for side, prefix in (("left", "left"), ("right", "right")):
        side_payload = _mapping(pair_payload.get(side), f"{side} pair side")
        for field, side_field in (
            (f"{prefix}_asset_id", "result_asset_id"),
            (f"{prefix}_asset_sha256", "result_asset_sha256"),
            (f"{prefix}_asset_variant_id", "asset_variant_id"),
        ):
            if pair.get(field) != side_payload.get(side_field):
                _fail(f"generic QuestionPair {side} side projection is invalid")
    canonical = {key: pair[key] for key in _PAIR_FIELDS if key != "created_at"}
    return {
        "id": _hash(
            PAIR_ID_SCHEMA,
            {
                "question_bank_id": pair["question_bank_id"],
                "source_admission_event_id": pair["demo_synthetic_identity_id"],
                "dimension_key": pair["dimension_key"],
                "magnitude_ppm": pair["magnitude_ppm"],
                "source_manifest_entry_digest": qa["source_manifest_entry_digest"],
                "pair_screening_record_digest": qa["pair_screening_record_digest"],
                "selected_pair_entry_digest": qa["selected_pair_entry_digest"],
            },
        )[:32],
        "schema_version": PAIR_SCHEMA,
        **dict(pair),
        "canonical_payload": canonical,
        "content_digest": _hash(PAIR_SCHEMA, canonical),
    }


def validate_question_pair_row(
    value: object,
    *,
    report: Mapping[str, object],
    bank: Mapping[str, object],
) -> Mapping[str, object]:
    row = _mapping(value, "generic QuestionPair row")
    if row.get("schema_version") != PAIR_SCHEMA:
        _fail("generic QuestionPair schema is invalid")
    expected = build_question_pair_row(
        {key: row[key] for key in _PAIR_FIELDS}, report=report, bank=bank
    )
    if dict(row) != expected:
        _fail("generic QuestionPair does not replay")
    return row


def validate_complete_question_bank(
    *,
    report: Mapping[str, object],
    bank: Mapping[str, object],
    pair_rows: Sequence[Mapping[str, object]],
) -> None:
    if len(pair_rows) != 16:
        _fail("generic QuestionBank requires exactly sixteen QuestionPairs")
    validated = [validate_question_pair_row(row, report=report, bank=bank) for row in pair_rows]
    if len({row["id"] for row in validated}) != 16:
        _fail("generic QuestionPair IDs must be unique")
    if len({row["demo_synthetic_identity_id"] for row in validated}) != 4:
        _fail("generic QuestionBank must use four identities")
    if len({row["dimension_key"] for row in validated}) != 2:
        _fail("generic QuestionBank must use two dimensions")
    if len({row["magnitude_ppm"] for row in validated}) != 2:
        _fail("generic QuestionBank must use two magnitudes")
    if (
        len(
            {
                (
                    row["demo_synthetic_identity_id"],
                    row["dimension_key"],
                    row["magnitude_ppm"],
                )
                for row in validated
            }
        )
        != 16
    ):
        _fail("generic QuestionBank identity/dimension/magnitude grid is incomplete")
    side_ids = {
        cast(str, row[key]) for row in validated for key in ("left_asset_id", "right_asset_id")
    }
    if len(side_ids) != 32:
        _fail("generic QuestionBank must select thirty-two distinct result sides")
    payload = _mapping(report.get("report_payload"), "generic Report payload")
    selected = payload.get("selected_pair_manifest")
    if not isinstance(selected, list):
        _fail("generic selected pair manifest is invalid")
    expected = [_mapping(item, "selected pair entry").get("entry_digest") for item in selected]
    observed = [
        _mapping(row["qa_payload"], "QuestionPair QA").get("selected_pair_entry_digest")
        for row in validated
    ]
    if observed != expected:
        _fail("generic QuestionPairs do not preserve selected manifest order")
