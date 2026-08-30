from __future__ import annotations

import base64
import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from PIL import Image
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from mirror_api import demo_d02_source_acquisition as acquisition
from mirror_api.config import get_settings
from mirror_api.demo_d02_r2_generation_receiver import (
    D02R2PngReceiverError,
    bind_principal_existing_png_file,
    bind_principal_preallocated_destination,
)
from mirror_api.demo_d02_source_acquisition import (
    CallAuthorization,
    D02SourceAcquisitionError,
    D02SourceAcquisitionService,
    D02SpecIdentity,
    D02TwoCopyStorage,
    D02TwoCopyStorageError,
    DurableCandidateBytes,
    DurablePrimaryMaterialization,
    PrimaryRecoveryAuthorization,
)
from mirror_api.demo_models import (
    D02CohortSpec,
    D02SelectedSourceManifest,
    D02SourceAcquisitionEvent,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with Session(engine, expire_on_commit=False) as db_session:
        db_session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, "
                "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs CASCADE"
            )
        )
        db_session.commit()
        yield db_session
        db_session.rollback()
        db_session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, "
                "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs CASCADE"
            )
        )
        db_session.commit()
    engine.dispose()


def _digest(marker: str) -> str:
    return (marker.encode("utf-8").hex() + "0" * 64)[:64]


def _service(session: Session, marker: str = "a") -> tuple[D02SourceAcquisitionService, str]:
    service = D02SourceAcquisitionService(session)
    spec = service.register_spec(
        D02SpecIdentity(
            provider_identity_digest=_digest(f"provider-{marker}"),
            runtime_identity_digest=_digest(f"runtime-{marker}"),
            model_identity_digest=_digest(f"model-{marker}"),
            m3_prescreen_policy_digest=_digest(f"m3-{marker}"),
            qa_policy_digest=_digest(f"qa-{marker}"),
        )
    )
    run = service.create_run(
        cohort_spec_id=spec.id,
        run_key_digest=_digest(f"run-{marker}"),
    )
    return service, run.id


def _png_data_url(marker: int = 1) -> str:
    image = Image.new("RGB", (96, 96), (marker % 255, 80, 160))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _materialize(
    *,
    service: D02SourceAcquisitionService,
    run_id: str,
    parent: Path,
    marker: int,
) -> tuple[CallAuthorization, DurablePrimaryMaterialization]:
    authorization = service.start_call(run_id=run_id)
    primary_leaf = f"primary-{marker}.png"
    primary = bind_principal_preallocated_destination(
        parent=parent,
        leaf_name=primary_leaf,
    )
    candidate = D02TwoCopyStorage().persist_primary_png(
        authorization=authorization,
        result_metadata={"image_url": _png_data_url(marker)},
        primary_destination=primary,
    )
    return authorization, candidate


def _accept_candidate(
    *,
    service: D02SourceAcquisitionService,
    run_id: str,
    parent: Path,
    marker: int,
) -> D02SelectedSourceManifest | None:
    candidate = _durable_candidate(
        service=service,
        run_id=run_id,
        parent=parent,
        marker=marker,
    )
    service.record_m3_supported(
        candidate_id=candidate.id,
        evidence_digest=_digest(f"formal-prescreen-{marker}"),
    )
    return service.record_qa_accepted(
        candidate_id=candidate.id,
        evidence_digest=_digest(f"provisional-qa-{marker}"),
        identity_family_digest=_digest(f"family-{marker}"),
    )


def _durable_candidate(
    *,
    service: D02SourceAcquisitionService,
    run_id: str,
    parent: Path,
    marker: int,
) -> D02SourceCandidate:
    _, materialization = _materialize(
        service=service,
        run_id=run_id,
        parent=parent,
        marker=marker,
    )
    candidate = service.record_materialized_candidate(candidate=materialization.candidate)
    backup_authority = service.authorize_backup_repair(candidate_id=candidate.id)
    reconciled = D02TwoCopyStorage().repair_backup(
        primary=backup_authority,
        primary_file=materialization.primary_file,
        backup_destination=bind_principal_preallocated_destination(
            parent=parent,
            leaf_name=f"backup-{marker}.png",
        ),
    )
    return service.record_backup_reconciled(
        candidate=reconciled,
        recovery_digest=_digest(f"backup-index-{marker}"),
    )


def test_authority_tokens_cannot_be_constructed_or_replaced() -> None:
    with pytest.raises(TypeError, match="issued by the acquisition service"):
        CallAuthorization(
            run_id="a" * 32,
            cohort_spec_id="b" * 32,
            provider_ordinal=1,
            selector_slot=object(),  # type: ignore[arg-type]
            tranche_number=1,
            call_started_event_digest="c" * 64,
            _factory_token=object(),
        )
    with pytest.raises(TypeError, match="issued by D02 two-copy storage"):
        DurableCandidateBytes(
            run_id="a" * 32,
            cohort_spec_id="b" * 32,
            provider_ordinal=1,
            selector_slot_id="D02_SLOT_01",
            call_started_event_digest="c" * 64,
            output_id="d02-output",
            provider_result_digest="d" * 64,
            media_type="image/png",
            byte_size=1,
            primary_sha256="e" * 64,
            backup_sha256="e" * 64,
            width=1,
            height=1,
            _factory_token=object(),
        )
    with pytest.raises(TypeError, match="issued by the acquisition service"):
        PrimaryRecoveryAuthorization(
            run_id="a" * 32,
            cohort_spec_id="b" * 32,
            provider_ordinal=1,
            selector_slot=object(),  # type: ignore[arg-type]
            tranche_number=1,
            call_started_event_digest="c" * 64,
            _factory_token=object(),
        )


def test_two_copy_token_binds_call_and_candidate(session: Session, tmp_path: Path) -> None:
    service, run_id = _service(session)
    authorization, materialization = _materialize(
        service=service,
        run_id=run_id,
        parent=tmp_path.resolve(strict=True),
        marker=1,
    )
    primary_candidate = materialization.candidate
    assert primary_candidate.call_started_event_digest == authorization.call_started_event_digest
    assert primary_candidate.backup_sha256 is None
    assert primary_candidate.output_id.startswith("d02-")
    with pytest.raises(TypeError):
        replace(primary_candidate, output_id="forged")
    candidate = service.record_materialized_candidate(candidate=primary_candidate)
    assert candidate.call_started_event_digest == authorization.call_started_event_digest
    assert candidate.candidate_state == "PRIMARY_DURABLE"
    backup_authority = service.authorize_backup_repair(candidate_id=candidate.id)
    repaired = D02TwoCopyStorage().repair_backup(
        primary=backup_authority,
        primary_file=materialization.primary_file,
        backup_destination=bind_principal_preallocated_destination(
            parent=tmp_path.resolve(strict=True), leaf_name="backup-token.png"
        ),
    )
    candidate = service.record_backup_reconciled(
        candidate=repaired,
        recovery_digest=_digest("backup-token-reconciled"),
    )
    assert candidate.candidate_state == "DURABLE"
    assert candidate.durable_primary_sha256 == candidate.durable_backup_sha256
    session.commit()


def test_primary_only_recovery_reuses_same_candidate_without_new_call(
    session: Session, tmp_path: Path
) -> None:
    service, run_id = _service(session, "partial")
    parent = tmp_path.resolve(strict=True)
    authorization = service.start_call(run_id=run_id)
    primary_leaf = "primary-partial.png"
    primary = bind_principal_preallocated_destination(parent=parent, leaf_name=primary_leaf)
    materialization = D02TwoCopyStorage().persist_primary_png(
        authorization=authorization,
        result_metadata={"image_url": _png_data_url(2)},
        primary_destination=primary,
    )
    row = service.record_materialized_candidate(candidate=materialization.candidate)
    assert row.candidate_state == "PRIMARY_DURABLE"
    assert row.durable_backup_sha256 is None
    assert session.get(D02SourceAcquisitionRun, run_id).run_state == "PAUSED_INFRASTRUCTURE"
    with pytest.raises(D02SourceAcquisitionError, match="M3_TRANSITION_INVALID"):
        service.record_m3_supported(candidate_id=row.id, evidence_digest=_digest("blocked-m3"))

    repair_authority = service.authorize_backup_repair(candidate_id=row.id)
    repaired = D02TwoCopyStorage().repair_backup(
        primary=repair_authority,
        primary_file=materialization.primary_file,
        backup_destination=bind_principal_preallocated_destination(
            parent=parent,
            leaf_name="backup-repaired.png",
        ),
    )
    recovered = service.record_backup_reconciled(
        candidate=repaired,
        recovery_digest=_digest("private-index-reconciled"),
    )
    assert recovered.id == row.id
    assert recovered.candidate_state == "DURABLE"
    assert recovered.durable_primary_sha256 == recovered.durable_backup_sha256
    assert session.get(D02SourceAcquisitionRun, run_id).budget_consumed == 1
    service.record_m3_supported(candidate_id=row.id, evidence_digest=_digest("same-candidate-m3"))
    session.commit()


def test_primary_publish_can_recover_same_open_call_after_process_interruption(
    session: Session, tmp_path: Path
) -> None:
    service, run_id = _service(session, "primary-crash")
    parent = tmp_path.resolve(strict=True)
    authorization = service.start_call(run_id=run_id)
    primary_path = parent / "primary-crash.png"
    published = D02TwoCopyStorage().persist_primary_png(
        authorization=authorization,
        result_metadata={"image_url": _png_data_url(7)},
        primary_destination=bind_principal_preallocated_destination(
            parent=parent,
            leaf_name=primary_path.name,
        ),
    )
    private_index_identity = published.primary_file.file_identity
    session.commit()
    session.expire_all()

    recovered_authorization = service.authorize_primary_recovery(
        run_id=run_id,
        call_started_event_digest=authorization.call_started_event_digest,
    )
    with pytest.raises(D02TwoCopyStorageError, match="CALL_AUTHORIZATION_INVALID"):
        D02TwoCopyStorage().persist_primary_png(
            authorization=recovered_authorization,  # type: ignore[arg-type]
            result_metadata={"image_url": _png_data_url(9)},
            primary_destination=bind_principal_preallocated_destination(
                parent=parent,
                leaf_name="forbidden-retry.png",
            ),
        )
    assert not (parent / "forbidden-retry.png").exists()
    rebound = bind_principal_existing_png_file(
        path=primary_path,
        expected_identity=private_index_identity,
    )
    recovered = D02TwoCopyStorage().recover_primary_png(
        authorization=recovered_authorization,
        primary_file=rebound,
    )
    assert recovered.candidate == published.candidate
    row = service.record_materialized_candidate(candidate=recovered.candidate)
    assert row.candidate_state == "PRIMARY_DURABLE"
    assert session.get(D02SourceAcquisitionRun, run_id).budget_consumed == 1
    session.commit()


def test_primary_recovery_rejects_same_bytes_at_different_file_identity(
    session: Session, tmp_path: Path
) -> None:
    service, run_id = _service(session, "wrong-primary")
    parent = tmp_path.resolve(strict=True)
    authorization = service.start_call(run_id=run_id)
    primary_path = parent / "primary-bound.png"
    published = D02TwoCopyStorage().persist_primary_png(
        authorization=authorization,
        result_metadata={"image_url": _png_data_url(8)},
        primary_destination=bind_principal_preallocated_destination(
            parent=parent,
            leaf_name=primary_path.name,
        ),
    )
    substituted = parent / "same-bytes-other-file.png"
    substituted.write_bytes(primary_path.read_bytes())

    with pytest.raises(D02R2PngReceiverError, match="private checkpoint"):
        bind_principal_existing_png_file(
            path=substituted,
            expected_identity=published.primary_file.file_identity,
        )
    assert session.get(D02SourceAcquisitionRun, run_id).budget_consumed == 1
    session.rollback()


def test_provider_outcome_uncertain_fails_entire_run(session: Session) -> None:
    service, run_id = _service(session, "uncertain")
    authorization = service.start_call(run_id=run_id)
    service.record_provider_outcome_uncertain(authorization=authorization)
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run.run_state == "FAILED_CLOSED"
    assert run.terminal_reason == "PROVIDER_OUTCOME_UNCERTAIN"
    with pytest.raises(D02SourceAcquisitionError, match="CALL_NOT_AUTHORIZED"):
        service.start_call(run_id=run_id)
    session.commit()


def test_open_call_recovery_after_restart_fails_closed_without_new_call(
    session: Session,
) -> None:
    service, run_id = _service(session, "restart-unknown")
    authorization = service.start_call(run_id=run_id)
    session.commit()

    recovered_service = D02SourceAcquisitionService(session)
    recovered_service.fail_open_call_as_provider_outcome_uncertain(
        run_id=run_id,
        call_started_event_digest=authorization.call_started_event_digest,
    )
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run is not None
    assert run.run_state == "FAILED_CLOSED"
    assert run.budget_consumed == 1
    assert (
        session.scalar(
            select(func.count())
            .select_from(D02SourceAcquisitionEvent)
            .where(
                D02SourceAcquisitionEvent.acquisition_run_id == run_id,
                D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
            )
        )
        == 1
    )
    with pytest.raises(D02SourceAcquisitionError):
        recovered_service.start_call(run_id=run_id)
    session.commit()


def test_durable_candidate_technical_pause_resumes_same_ordinal_without_call(
    session: Session, tmp_path: Path
) -> None:
    service, run_id = _service(session, "durable-pause")
    candidate = _durable_candidate(
        service=service, run_id=run_id, parent=tmp_path.resolve(strict=True), marker=7
    )
    service.pause_infrastructure_for_candidate(candidate_id=candidate.id, stage_code="M3_RUNTIME")
    calls_before = session.scalar(
        select(func.count())
        .select_from(D02SourceAcquisitionEvent)
        .where(
            D02SourceAcquisitionEvent.acquisition_run_id == run_id,
            D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
        )
    )
    service.resume_infrastructure(run_id=run_id, review_digest=_digest("m3-recovered"))
    with pytest.raises(D02SourceAcquisitionError, match="CANDIDATE_PROCESSING_INCOMPLETE"):
        service.start_call(run_id=run_id)
    service.record_m3_supported(candidate_id=candidate.id, evidence_digest=_digest("m3-retry"))
    with pytest.raises(D02SourceAcquisitionError, match="CANDIDATE_PROCESSING_INCOMPLETE"):
        service.start_call(run_id=run_id)
    assert (
        session.scalar(
            select(func.count())
            .select_from(D02SourceAcquisitionEvent)
            .where(
                D02SourceAcquisitionEvent.acquisition_run_id == run_id,
                D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
            )
        )
        == calls_before
    )
    assert session.get(D02SourceAcquisitionRun, run_id).budget_consumed == 1
    session.commit()


def test_postgresql_rejects_call_started_while_candidate_is_incomplete(
    session: Session, tmp_path: Path
) -> None:
    service, run_id = _service(session, "db-incomplete-candidate")
    _durable_candidate(
        service=service,
        run_id=run_id,
        parent=tmp_path.resolve(strict=True),
        marker=6,
    )
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run is not None
    run.budget_consumed = 2
    run.next_ordinal = 3
    run.open_call_ordinal = 2
    run.open_selector_slot_id = "D02_SLOT_02"
    acquisition._seal_run(run)
    with pytest.raises(DBAPIError, match="CALL_STARTED does not bind"):
        service._append_event(
            run,
            event_kind="CALL_STARTED",
            provider_ordinal=2,
            selector_slot_id="D02_SLOT_02",
        )
    session.rollback()


def test_formal_gate_failure_does_not_open_another_provider_call(
    session: Session, tmp_path: Path
) -> None:
    service, run_id = _service(session, "final-gate-pause")
    for marker in range(1, 5):
        _accept_candidate(
            service=service, run_id=run_id, parent=tmp_path.resolve(strict=True), marker=marker
        )
    calls_before = session.scalar(
        select(func.count())
        .select_from(D02SourceAcquisitionEvent)
        .where(
            D02SourceAcquisitionEvent.acquisition_run_id == run_id,
            D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
        )
    )
    with pytest.raises(D02SourceAcquisitionError, match="FORMAL_SOURCE_SET_INVALID"):
        service.mark_formal_sources_ready(
            run_id=run_id, formal_source_set_digest=_digest("missing-formal-sources")
        )
    service.pause_final_gate(
        run_id=run_id,
        stage_code="SCREENING_NOT_READY",
        evidence_digest=_digest("screening-paused"),
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(D02SourceAcquisitionEvent)
            .where(
                D02SourceAcquisitionEvent.acquisition_run_id == run_id,
                D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
            )
        )
        == calls_before
        == 4
    )
    assert session.get(D02SourceAcquisitionRun, run_id).run_state == "MANIFEST_FINALIZED"
    session.commit()


def test_interrupted_open_call_can_fail_closed_without_new_provider_call(
    session: Session,
) -> None:
    service, run_id = _service(session, "uncertain-restart")
    authorization = service.start_call(run_id=run_id)
    session.commit()
    session.expire_all()

    service.fail_open_call_as_provider_outcome_uncertain(
        run_id=run_id,
        call_started_event_digest=authorization.call_started_event_digest,
    )
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run is not None
    assert run.run_state == "FAILED_CLOSED"
    assert run.terminal_reason == "PROVIDER_OUTCOME_UNCERTAIN"
    assert run.budget_consumed == 1
    assert run.next_ordinal == 2
    assert run.open_call_ordinal is None
    assert (
        session.scalar(
            select(func.count())
            .select_from(D02SourceAcquisitionEvent)
            .where(
                D02SourceAcquisitionEvent.acquisition_run_id == run_id,
                D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
            )
        )
        == 1
    )
    session.commit()


def test_tranche_must_reconcile_before_ordinal_eleven(session: Session) -> None:
    service, run_id = _service(session, "tranche")
    for ordinal in range(1, 11):
        authorization = service.start_call(run_id=run_id)
        assert authorization.provider_ordinal == ordinal
        service.record_call_consumed_no_result(
            authorization=authorization,
            detail_code="PROVIDER_RETURNED_NO_RESULT",
        )
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run.run_state == "PAUSED_CONTENT_REVIEW"
    service.resume_content_review(run_id=run_id, review_digest=_digest("tranche-review"))
    with pytest.raises(D02SourceAcquisitionError, match="PREVIOUS_TRANCHE_NOT_RECONCILED"):
        service.start_call(run_id=run_id)
    service.reconcile_tranche(
        run_id=run_id,
        tranche_number=1,
        reconciliation_digest=_digest("tranche-one-summary"),
    )
    assert service.start_call(run_id=run_id).provider_ordinal == 11
    session.rollback()


def test_four_accepted_candidates_finalize_manifest_and_stop(
    session: Session, tmp_path: Path
) -> None:
    service, run_id = _service(session, "manifest")
    parent = tmp_path.resolve(strict=True)
    manifest: D02SelectedSourceManifest | None = None
    for marker in range(1, 5):
        manifest = _accept_candidate(
            service=service,
            run_id=run_id,
            parent=parent,
            marker=marker,
        )
    assert manifest is not None
    assert manifest.source_count == 4
    assert len(manifest.ordered_candidate_ids) == 4
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run.run_state == "MANIFEST_FINALIZED"
    assert run.accepted_count == 4
    with pytest.raises(D02SourceAcquisitionError, match="CALL_NOT_AUTHORIZED"):
        service.start_call(run_id=run_id)
    session.commit()


def test_five_consecutive_content_rejections_pause_for_principal_review(
    session: Session, tmp_path: Path
) -> None:
    service, run_id = _service(session, "rejects")
    parent = tmp_path.resolve(strict=True)
    for marker in range(1, 6):
        candidate = _durable_candidate(
            service=service,
            run_id=run_id,
            parent=parent,
            marker=marker,
        )
        service.record_m3_supported(
            candidate_id=candidate.id,
            evidence_digest=_digest(f"reject-m3-{marker}"),
        )
        service.record_qa_rejected(
            candidate_id=candidate.id,
            evidence_digest=_digest(f"reject-qa-{marker}"),
            rejection_code="ANTI_HOMOGENIZATION_REJECTED",
        )
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run.run_state == "PAUSED_CONTENT_REVIEW"
    assert run.consecutive_content_rejects == 5
    assert run.budget_consumed == 5
    with pytest.raises(D02SourceAcquisitionError, match="CALL_NOT_AUTHORIZED"):
        service.start_call(run_id=run_id)
    session.commit()


def test_fifty_calls_are_final_and_ordinal_fifty_one_is_impossible(session: Session) -> None:
    service, run_id = _service(session, "budget")
    for ordinal in range(1, 51):
        authorization = service.start_call(run_id=run_id)
        assert authorization.provider_ordinal == ordinal
        service.record_call_consumed_no_result(
            authorization=authorization,
            detail_code="PROVIDER_RETURNED_NO_RESULT",
        )
        if ordinal in {10, 20, 30, 40}:
            service.resume_content_review(
                run_id=run_id,
                review_digest=_digest(f"review-{ordinal}"),
            )
            service.reconcile_tranche(
                run_id=run_id,
                tranche_number=ordinal // 10,
                reconciliation_digest=_digest(f"summary-{ordinal}"),
            )
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run.budget_consumed == 50
    assert run.next_ordinal == 51
    assert run.run_state == "FAILED_CLOSED"
    assert run.terminal_reason == "CALL_BUDGET_EXHAUSTED"
    assert (
        session.scalar(
            select(D02SourceAcquisitionEvent)
            .where(
                D02SourceAcquisitionEvent.acquisition_run_id == run_id,
                D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
            )
            .order_by(D02SourceAcquisitionEvent.provider_ordinal.desc())
        ).provider_ordinal
        == 50
    )
    with pytest.raises(D02SourceAcquisitionError, match="CALL_NOT_AUTHORIZED"):
        service.start_call(run_id=run_id)
    session.commit()


def test_unknown_spec_fails_closed(session: Session) -> None:
    service = D02SourceAcquisitionService(session)
    with pytest.raises(D02SourceAcquisitionError, match="UNKNOWN_COHORT_SPEC"):
        service.create_run(
            cohort_spec_id="0" * 32,
            run_key_digest=_digest("unknown-run"),
        )


def test_bootstrap_spec_and_run_are_singleton_budget_authorities(session: Session) -> None:
    service = D02SourceAcquisitionService(session)
    identity = D02SpecIdentity(
        provider_identity_digest=_digest("singleton-provider"),
        runtime_identity_digest=_digest("singleton-runtime"),
        model_identity_digest=_digest("singleton-model"),
        m3_prescreen_policy_digest=_digest("singleton-m3"),
        qa_policy_digest=_digest("singleton-qa"),
    )
    spec = service.register_spec(identity)
    assert service.register_spec(identity).id == spec.id
    run = service.create_run(
        cohort_spec_id=spec.id,
        run_key_digest=_digest("singleton-run"),
    )
    assert (
        service.create_run(
            cohort_spec_id=spec.id,
            run_key_digest=_digest("singleton-run"),
        ).id
        == run.id
    )
    with pytest.raises(D02SourceAcquisitionError, match="RUN_SINGLETON_COLLISION"):
        service.create_run(
            cohort_spec_id=spec.id,
            run_key_digest=_digest("second-budget-pool"),
        )
    with pytest.raises(D02SourceAcquisitionError, match="SPEC_SINGLETON_COLLISION"):
        service.register_spec(
            D02SpecIdentity(
                provider_identity_digest=_digest("different-provider"),
                runtime_identity_digest=_digest("different-runtime"),
                model_identity_digest=_digest("different-model"),
                m3_prescreen_policy_digest=_digest("different-m3"),
                qa_policy_digest=_digest("different-qa"),
            )
        )
    assert session.scalar(select(func.count()).select_from(D02CohortSpec)) == 1
    assert session.scalar(select(func.count()).select_from(D02SourceAcquisitionRun)) == 1
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM pg_constraint "
                "WHERE contype = 'u' AND conname IN ("
                "'uq_demo_d02_cohort_specs_bootstrap_singleton',"
                "'uq_demo_d02_source_acquisition_runs_bootstrap_singleton')"
            )
        )
        == 2
    )
    session.commit()


def test_concurrent_bootstrap_registration_has_one_singleton_winner(session: Session) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    barrier = Barrier(2)

    def attempt(marker: str) -> tuple[str, str]:
        engine = create_engine(database_url)
        try:
            with Session(engine, expire_on_commit=False) as concurrent_session:
                barrier.wait(timeout=5)
                service = D02SourceAcquisitionService(concurrent_session)
                try:
                    spec = service.register_spec(
                        D02SpecIdentity(
                            provider_identity_digest=_digest(f"provider-{marker}"),
                            runtime_identity_digest=_digest(f"runtime-{marker}"),
                            model_identity_digest=_digest(f"model-{marker}"),
                            m3_prescreen_policy_digest=_digest(f"m3-{marker}"),
                            qa_policy_digest=_digest(f"qa-{marker}"),
                        )
                    )
                    service.create_run(
                        cohort_spec_id=spec.id,
                        run_key_digest=_digest(f"run-{marker}"),
                    )
                    concurrent_session.commit()
                except D02SourceAcquisitionError as exc:
                    concurrent_session.rollback()
                    return ("rejected", exc.code)
                return ("created", marker)
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ("one", "two")))

    assert len([result for result in results if result[0] == "created"]) == 1
    assert [result[1] for result in results if result[0] == "rejected"] == [
        "COHORT_SPEC_SINGLETON_COLLISION"
    ]
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(D02CohortSpec)) == 1
    assert session.scalar(select(func.count()).select_from(D02SourceAcquisitionRun)) == 1


def test_populated_bootstrap_downgrade_fails_closed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _service(session, "populated-downgrade")
    session.commit()
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    get_settings.cache_clear()
    try:
        with pytest.raises(DBAPIError, match="D02 autonomous acquisition authority exists"):
            command.downgrade(config, "demo_0014_d02_r2_e3_versioning")
    finally:
        get_settings.cache_clear()


def test_concurrent_start_call_has_one_unique_winner(session: Session) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    _, run_id = _service(session, "concurrent-start")
    session.commit()
    barrier = Barrier(2)

    def attempt_start() -> tuple[str, int | str]:
        engine = create_engine(database_url)
        try:
            with Session(engine, expire_on_commit=False) as concurrent_session:
                barrier.wait(timeout=5)
                service = D02SourceAcquisitionService(concurrent_session)
                try:
                    authorization = service.start_call(run_id=run_id)
                    concurrent_session.commit()
                except D02SourceAcquisitionError as exc:
                    concurrent_session.rollback()
                    return ("rejected", str(exc))
                return ("authorized", authorization.provider_ordinal)
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt_start(), range(2)))

    assert results.count(("authorized", 1)) == 1
    rejected = [value for status, value in results if status == "rejected"]
    assert rejected == ["CALL_NOT_AUTHORIZED_IN_CURRENT_STATE"]
    session.expire_all()
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run is not None
    assert run.budget_consumed == 1
    assert run.next_ordinal == 2
    assert run.open_call_ordinal == 1
    assert (
        session.scalar(
            select(func.count())
            .select_from(D02SourceAcquisitionEvent)
            .where(
                D02SourceAcquisitionEvent.acquisition_run_id == run_id,
                D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
            )
        )
        == 1
    )
