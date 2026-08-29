from __future__ import annotations

import asyncio
import hashlib
import io
import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from copy import deepcopy
from functools import lru_cache
from typing import Any, cast

import pytest
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from test_demo_d02_r2_authority import _packet, _report_input_template
from test_demo_d02_r2_schema_authority import _build_r2_bank_and_pairs
from test_demo_d02_r2_screening_execution import _Adapters, _request

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as r2
from mirror_api import demo_d02_r2_screening_execution as screening
from mirror_api.demo_d02_r2_epoch2_admission import (
    E2_SOURCE_AUTHORITY_SCHEMA,
    SOURCE_NORMALIZATION_SCHEMA,
    D02R2Epoch2AdmissionCoordinator,
    D02R2Epoch2AdmissionError,
    D02R2Epoch2AuthorityCorruption,
    D02R2Epoch2PayloadConflict,
    Epoch2AdmissionBundle,
    NormalizedSource,
    _validate_bundle,
    build_epoch2_source_authority,
    build_epoch2_source_qa_snapshot,
    build_epoch2_source_record,
    normalize_epoch2_source_png,
    validate_epoch2_admission_packet,
)
from mirror_api.demo_d02_r2_epoch2_generation_receipt import GENERATION_RECEIPT_SCHEMA
from mirror_api.demo_d02_r2_generation_epoch2 import (
    E2_DISPATCH_EPOCH,
    E2_PRODUCER_TASK_ID,
    E2_ROOT_ID,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest
from mirror_api.demo_models import (
    DEMO_TABLE_NAMES,
    DemoD02R2Epoch2Admission,
    DemoD02R2SourceAuthority,
    DemoPairScreeningReport,
    DemoQuestionBank,
    DemoQuestionPair,
    DemoSyntheticIdentity,
)
from mirror_api.models import Asset, AssetVariant


def _digest(marker: str) -> str:
    return hashlib.sha256(marker.encode()).hexdigest()


def _e2_generation_receipt(
    template: Mapping[str, object],
    *,
    ordinal: int,
    png_sha256: str,
    png_byte_size: int,
) -> dict[str, object]:
    receipt = dict(template)
    receipt.update(
        schema_version=GENERATION_RECEIPT_SCHEMA,
        candidate_ordinal=ordinal,
        source_producer_task_id=E2_PRODUCER_TASK_ID,
        dispatch_epoch=E2_DISPATCH_EPOCH,
        evidence_root_id=E2_ROOT_ID,
        generation_request_policy_digest=_digest(f"e2-request-{ordinal}"),
        source_asset_sha256=png_sha256,
        source_asset_byte_size=png_byte_size,
        source_asset_mime_type="image/png",
    )
    receipt["receipt_digest"] = mirror_demo_digest(
        GENERATION_RECEIPT_SCHEMA,
        {key: value for key, value in receipt.items() if key != "receipt_digest"},
    )
    return receipt


def _normalization_fixture(
    *,
    generation_receipt: Mapping[str, object],
    source_sha256: str,
    source_byte_size: int,
    width: int,
    height: int,
) -> NormalizedSource:
    receipt: dict[str, object] = {
        "schema_version": SOURCE_NORMALIZATION_SCHEMA,
        "normalization_version": "demo-d02-r2-e2-png-to-jpeg-v1",
        "source_generation_receipt_digest": generation_receipt["receipt_digest"],
        "generation_source_asset_sha256": generation_receipt["source_asset_sha256"],
        "generation_source_asset_byte_size": generation_receipt["source_asset_byte_size"],
        "generation_source_asset_mime_type": "image/png",
        "generation_source_asset_width": width,
        "generation_source_asset_height": height,
        "normalized_source_asset_sha256": source_sha256,
        "normalized_source_asset_byte_size": source_byte_size,
        "normalized_source_asset_mime_type": "image/jpeg",
        "normalized_source_asset_width": width,
        "normalized_source_asset_height": height,
        "jpeg_quality": 95,
        "jpeg_subsampling": 0,
        "metadata_policy": "STRIP_ALL",
    }
    receipt["normalization_receipt_digest"] = mirror_demo_digest(
        SOURCE_NORMALIZATION_SCHEMA, receipt
    )
    return NormalizedSource(
        jpeg_bytes=b"deterministic-test-only-jpeg-projection",
        sha256=source_sha256,
        byte_size=source_byte_size,
        width=width,
        height=height,
        receipt=cast(Mapping[str, Any], receipt),
    )


def _epoch2_packet(marker: str, ordinal: int) -> dict[str, object]:
    template = _packet(marker, source_ordinal=ordinal)
    facts = deepcopy(cast(dict[str, object], template["facts"]))
    old_receipt = cast(dict[str, object], template["generation_receipt"])
    generation_receipt = _e2_generation_receipt(
        old_receipt,
        ordinal=ordinal,
        png_sha256=_digest(f"original-png-{marker}"),
        png_byte_size=cast(int, facts["source_asset_byte_size"]) + ordinal,
    )
    normalized = _normalization_fixture(
        generation_receipt=generation_receipt,
        source_sha256=cast(str, facts["source_asset_sha256"]),
        source_byte_size=cast(int, facts["source_asset_byte_size"]),
        width=cast(int, facts["source_asset_width"]),
        height=cast(int, facts["source_asset_height"]),
    )
    source_asset_id = cast(
        str, cast(dict[str, object], template["identity_row"])["formal_canonical_asset_id"]
    )
    authority = build_epoch2_source_authority(
        generation_receipt=generation_receipt,
        normalized_source=normalized,
        source_asset_id=source_asset_id,
    )
    qa = build_epoch2_source_qa_snapshot(
        source_authority=authority,
        generation_receipt=generation_receipt,
        qa_policy_digest=_digest(f"e2-qa-policy-{marker}"),
        decode_record_digest=_digest(f"e2-decode-{marker}"),
        ordered_review_decision_digests=[
            _digest(f"e2-review-{marker}-{index}") for index in range(6)
        ],
    )
    supporting = build_epoch2_source_record(
        source_authority=authority,
        source_qa_snapshot=qa,
        generation_receipt=generation_receipt,
        created_at="2026-08-29T00:00:00Z",
    )
    source_key = cast(str, supporting["source_authority_key"])
    facts.update(
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
    )
    identity = deepcopy(cast(dict[str, object], template["identity_row"]))
    identity.update(
        formal_canonical_asset_id=supporting["source_asset_id"],
        formal_canonical_asset_sha256=supporting["source_asset_sha256"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        source_fact_snapshot=facts,
        source_fact_snapshot_digest=r2.digest_r2_facts(facts),
        source_authority_key=source_key,
        r2_source_authority_record_id=supporting["id"],
    )
    identity_canonical = {
        key: value
        for key, value in identity.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    identity["canonical_payload"] = identity_canonical
    identity["content_digest"] = mirror_demo_digest(r2.R2_IDENTITY_SCHEMA, identity_canonical)
    identity["id"] = mirror_demo_digest(
        r2.R2_IDENTITY_ID_DOMAIN,
        {
            "source_authority_kind": r2.R2_SOURCE_AUTHORITY_KIND,
            "source_authority_key": source_key,
            "r2_source_authority_record_id": supporting["id"],
            "admission_sequence": identity["admission_sequence"],
            "admission_action": identity["admission_action"],
            "supersedes_id": identity["supersedes_id"],
            "admission_config_digest": identity["admission_config_digest"],
            "canonical_payload_digest": identity["content_digest"],
        },
    )[:32]
    entry = deepcopy(cast(dict[str, object], template["source_manifest_entry"]))
    entry.update(
        source_authority_key=source_key,
        source_admission_event_id=identity["id"],
        source_admission_content_digest=identity["content_digest"],
        source_output_id=supporting["source_output_id"],
        source_asset_id=supporting["source_asset_id"],
        source_asset_sha256=supporting["source_asset_sha256"],
        source_asset_byte_size=supporting["source_asset_byte_size"],
        source_asset_mime_type=supporting["source_asset_mime_type"],
        source_asset_width=supporting["source_asset_width"],
        source_asset_height=supporting["source_asset_height"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        source_fact_snapshot_digest=identity["source_fact_snapshot_digest"],
        r2_source_authority_record_id=supporting["id"],
    )
    entry["record_digest"] = mirror_demo_digest(
        r2.R2_SOURCE_ENTRY_SCHEMA,
        {
            key: value
            for key, value in entry.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    return {
        "generation_receipt": generation_receipt,
        "source_authority": authority,
        "source_qa_snapshot": qa,
        "supporting_row": supporting,
        "facts": facts,
        "identity_row": identity,
        "source_manifest_entry": entry,
        "source_manifest_digest": _digest("pending-manifest"),
    }


def _epoch2_packets() -> list[dict[str, object]]:
    packets = [_epoch2_packet(marker, ordinal) for ordinal, marker in enumerate("abcd", start=1)]
    manifest = legacy._sequence_digest(
        r2.R2_SOURCE_MANIFEST_SCHEMA,
        [cast(dict[str, object], packet["source_manifest_entry"]) for packet in packets],
    )
    for packet in packets:
        packet["source_manifest_digest"] = manifest
        validate_epoch2_admission_packet(packet)
        r2.validate_r2_admission_packet(packet)
    return packets


def _asset_rows(
    report: Mapping[str, object], packets: list[dict[str, object]]
) -> tuple[Mapping[str, object], ...]:
    rows: list[Mapping[str, object]] = []
    for packet in packets:
        source = cast(dict[str, object], packet["supporting_row"])
        rows.append(
            {
                "id": source["source_asset_id"],
                "owner_user_id": None,
                "asset_role": "synthetic",
                "storage_key": f"demo-r2-e2-test/source/{source['source_ordinal']}",
                "mime_type": source["source_asset_mime_type"],
                "byte_size": source["source_asset_byte_size"],
                "width": source["source_asset_width"],
                "height": source["source_asset_height"],
                "sha256": source["source_asset_sha256"],
                "synthetic": True,
                "is_ai_generated": True,
                "is_ai_modified": False,
                "internal_purpose": "synthetic_dataset",
                "deleted_at": None,
            }
        )
    payload = cast(dict[str, object], report["report_payload"])
    exact = cast(dict[str, object], payload["exact_duplicate_evidence"])
    for image in cast(list[dict[str, object]], exact["image_records"]):
        if image["authority_role"] == "SOURCE":
            continue
        rows.append(
            {
                "id": image["deterministic_result_asset_id"],
                "owner_user_id": None,
                "asset_role": "synthetic",
                "storage_key": f"demo-r2-e2-test/result/{image['case_id']}",
                "mime_type": image["mime_type"],
                "byte_size": image["byte_size"],
                "width": image["width"],
                "height": image["height"],
                "sha256": image["sha256"],
                "synthetic": True,
                "is_ai_generated": False,
                "is_ai_modified": True,
                "internal_purpose": "synthetic_dataset",
                "deleted_at": None,
            }
        )
    return tuple(rows)


def _variant_rows(report: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    payload = cast(dict[str, object], report["report_payload"])
    rows: list[Mapping[str, object]] = []
    for wrapper in cast(list[dict[str, object]], payload["pair_quality_evidence"]):
        pair = cast(dict[str, object], wrapper["pair_screening_record_payload"])
        for side_name in ("left", "right"):
            side = cast(dict[str, object], pair[side_name])
            rows.append(
                {
                    "id": side["asset_variant_id"],
                    "source_asset_id": pair["source_asset_id"],
                    "result_asset_id": side["result_asset_id"],
                    "variant_type": side["asset_variant_type"],
                    "created_at": "2026-08-29T00:00:00Z",
                }
            )
    return tuple(rows)


@lru_cache(maxsize=1)
def _bundle() -> Epoch2AdmissionBundle:
    packets = _epoch2_packets()
    fields, _ = _report_input_template()
    report = screening.run_offline_screening(_request(_Adapters(fields), fields, packets))
    bank, pairs = _build_r2_bank_and_pairs(report, packets)
    return Epoch2AdmissionBundle(
        source_packets=tuple(packets),
        asset_rows=_asset_rows(report, packets),
        asset_variant_rows=_variant_rows(report),
        report_row=report,
        question_bank_row=bank,
        question_pair_rows=tuple(pairs),
    )


def test_png_normalization_is_deterministic_and_metadata_free() -> None:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), (80, 120, 160)).save(output, format="PNG")
    png = output.getvalue()
    template = cast(dict[str, object], _packet("a")["generation_receipt"])
    receipt = _e2_generation_receipt(
        template,
        ordinal=1,
        png_sha256=hashlib.sha256(png).hexdigest(),
        png_byte_size=len(png),
    )
    receipt["source_asset_width"] = 32
    receipt["source_asset_height"] = 24
    receipt["receipt_digest"] = mirror_demo_digest(
        GENERATION_RECEIPT_SCHEMA,
        {key: value for key, value in receipt.items() if key != "receipt_digest"},
    )
    first = normalize_epoch2_source_png(png, generation_receipt=receipt)
    second = normalize_epoch2_source_png(png, generation_receipt=receipt)
    assert first.jpeg_bytes == second.jpeg_bytes
    assert first.sha256 == second.sha256
    assert first.receipt == second.receipt
    with Image.open(io.BytesIO(first.jpeg_bytes)) as decoded:
        assert decoded.format == "JPEG"
        assert decoded.info.get("exif") in (None, b"")
        assert decoded.info.get("icc_profile") is None


def test_epoch2_packet_dispatch_and_complete_runner_replay() -> None:
    bundle = _bundle()
    assert len(bundle.source_packets) == 4
    assert len(bundle.asset_rows) == 52
    assert len(bundle.asset_variant_rows) == 48
    assert len(bundle.question_pair_rows) == 16
    assert bundle.report_row["status"] == "PASSED"
    assert bundle.report_row["selected_result_side_count"] == 32


def test_complete_asset_and_variant_authority_is_bound_to_report() -> None:
    bundle = _bundle()
    selected_result_ids = {
        cast(str, pair[side])
        for pair in bundle.question_pair_rows
        for side in ("left_asset_id", "right_asset_id")
    }
    tampered_assets = [dict(row) for row in bundle.asset_rows]
    unselected_result = next(
        row
        for row in tampered_assets
        if row["is_ai_modified"] is True and row["id"] not in selected_result_ids
    )
    unselected_result["sha256"] = _digest("substituted-unselected-result")
    asset_substitution = Epoch2AdmissionBundle(
        source_packets=bundle.source_packets,
        asset_rows=tuple(tampered_assets),
        asset_variant_rows=bundle.asset_variant_rows,
        report_row=bundle.report_row,
        question_bank_row=bundle.question_bank_row,
        question_pair_rows=bundle.question_pair_rows,
    )
    with pytest.raises(D02R2Epoch2AdmissionError, match="Report image authority"):
        _validate_bundle(asset_substitution)

    tampered_variants = [dict(row) for row in bundle.asset_variant_rows]
    tampered_variants[0]["result_asset_id"] = tampered_variants[1]["result_asset_id"]
    variant_substitution = Epoch2AdmissionBundle(
        source_packets=bundle.source_packets,
        asset_rows=bundle.asset_rows,
        asset_variant_rows=tuple(tampered_variants),
        report_row=bundle.report_row,
        question_bank_row=bundle.question_bank_row,
        question_pair_rows=bundle.question_pair_rows,
    )
    with pytest.raises(D02R2Epoch2AdmissionError, match="Report pair authority"):
        _validate_bundle(variant_substitution)


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for the Epoch 02 PostgreSQL gate")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tables = ", ".join(sorted(DEMO_TABLE_NAMES))
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE TABLE {tables} CASCADE"))
            await connection.execute(text("TRUNCATE TABLE assets CASCADE"))
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE TABLE {tables} CASCADE"))
            await connection.execute(text("TRUNCATE TABLE assets CASCADE"))
        await engine.dispose()


async def _count(sessions: async_sessionmaker[AsyncSession], model: type[Any]) -> int:
    async with sessions() as session:
        value = await session.scalar(select(func.count()).select_from(model))
    assert isinstance(value, int)
    return value


@pytest.mark.asyncio
async def test_atomic_admission_replay_conflict_and_cardinality() -> None:
    bundle = _bundle()
    async with _database() as sessions:
        idempotency_key = _digest("epoch2-admission-replay")
        preexisting_asset = dict(bundle.asset_rows[0])
        preexisting_asset["storage_key"] = "demo-r2-e2-test/preexisting-source-1"
        async with sessions() as session, session.begin():
            await session.execute(
                pg_insert(Asset)
                .values(**preexisting_asset)
                .on_conflict_do_nothing(index_elements=(Asset.id,))
            )
        coordinator = D02R2Epoch2AdmissionCoordinator(session_factory=sessions)
        first, replay = await asyncio.gather(
            coordinator.admit(idempotency_key=idempotency_key, bundle=bundle),
            coordinator.admit(idempotency_key=idempotency_key, bundle=bundle),
        )
        assert {first.replayed, replay.replayed} == {False, True}
        assert first.admission_id == replay.admission_id
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 1
        assert await _count(sessions, DemoD02R2SourceAuthority) == 4
        assert await _count(sessions, DemoSyntheticIdentity) == 4
        assert await _count(sessions, DemoPairScreeningReport) == 1
        assert await _count(sessions, DemoQuestionBank) == 1
        assert await _count(sessions, DemoQuestionPair) == 16
        assert await _count(sessions, Asset) == 52
        assert await _count(sessions, AssetVariant) == 48

        conflicting_assets = [dict(row) for row in bundle.asset_rows]
        conflicting_assets[-1]["storage_key"] = "demo-r2-e2-test/result/conflicting-key"
        conflicting = Epoch2AdmissionBundle(
            source_packets=bundle.source_packets,
            asset_rows=tuple(conflicting_assets),
            asset_variant_rows=bundle.asset_variant_rows,
            report_row=bundle.report_row,
            question_bank_row=bundle.question_bank_row,
            question_pair_rows=bundle.question_pair_rows,
        )
        with pytest.raises(D02R2Epoch2PayloadConflict):
            await coordinator.admit(idempotency_key=idempotency_key, bundle=conflicting)
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 1


@pytest.mark.asyncio
async def test_mid_transaction_asset_failure_rolls_back_every_row() -> None:
    bundle = _bundle()
    broken_assets = [dict(row) for row in bundle.asset_rows]
    broken_assets[0]["storage_key"] = broken_assets[1]["storage_key"]
    broken = Epoch2AdmissionBundle(
        source_packets=bundle.source_packets,
        asset_rows=tuple(broken_assets),
        asset_variant_rows=bundle.asset_variant_rows,
        report_row=bundle.report_row,
        question_bank_row=bundle.question_bank_row,
        question_pair_rows=bundle.question_pair_rows,
    )
    async with _database() as sessions:
        coordinator = D02R2Epoch2AdmissionCoordinator(session_factory=sessions)
        with pytest.raises(D02R2Epoch2AuthorityCorruption):
            await coordinator.admit(idempotency_key="epoch2-rollback-key", bundle=broken)
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 0
        assert await _count(sessions, DemoD02R2SourceAuthority) == 0
        assert await _count(sessions, DemoPairScreeningReport) == 0
        assert await _count(sessions, DemoQuestionBank) == 0
        assert await _count(sessions, DemoQuestionPair) == 0
        assert await _count(sessions, Asset) == 0
        assert await _count(sessions, AssetVariant) == 0


def test_epoch2_source_authority_schema_is_not_e1_reinterpretation() -> None:
    packet = _epoch2_packets()[0]
    authority = cast(dict[str, object], packet["source_authority"])
    support = cast(dict[str, object], packet["supporting_row"])
    assert authority["schema_version"] == E2_SOURCE_AUTHORITY_SCHEMA
    assert support["schema_version"] == "mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1"
    assert support["evidence_root_id"] == E2_ROOT_ID
    assert support["generation_request_digest"] == support["generation_request_policy_digest"]
