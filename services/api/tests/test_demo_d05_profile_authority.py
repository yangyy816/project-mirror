"""PostgreSQL-only invariants for D05 profile compilation authority."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any, cast

import pytest
import test_demo_schema_authority_invariants as authority
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from mirror_api.config import get_settings
from mirror_api.demo_models import (
    DemoDesiredDeltaProfile,
    DemoIdentityConstraints,
    DemoProfileCompilationBundle,
    DemoSelfTransferDimensionEvidence,
    DemoSelfTransferRun,
    DemoStyleProfile,
)

_HEAD = "demo_0012_d05_profile_auth"
_DOWN = "demo_0011_d03_job_recovery"


@pytest.fixture
def session() -> Generator[Session]:
    """Reuse the established real-PostgreSQL graph fixture and clean D05 rows too."""
    fixture = cast(Any, authority.session).__wrapped__()
    db_session = next(fixture)
    db_session.execute(
        text("TRUNCATE TABLE demo_profile_compilation_bundles, demo_self_transfer_evidence CASCADE")
    )
    db_session.commit()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.execute(
            text(
                "TRUNCATE TABLE demo_profile_compilation_bundles, "
                "demo_self_transfer_evidence CASCADE"
            )
        )
        db_session.commit()
        try:
            next(fixture)
        except StopIteration:
            pass


def _persistent_constraints(session: Session, graph: dict[str, Any]) -> DemoIdentityConstraints:
    source_event = graph.get("persistent_event", graph["source_event"])
    return authority._insert_demo_row(
        session,
        DemoIdentityConstraints,
        demo_actor_id=graph["actor"].id,
        demo_session_id=None,
        self_state_id=graph["self_state"].id,
        version=2,
        constraint_scope="PERSISTENT",
        source_event_digests=[source_event.content_digest],
        locks={"eyes": "PRESERVE"},
        bounds={"max_ppm": 10_000},
        prohibited_operations=[],
    )


def _session_constraints(
    session: Session, graph: dict[str, Any], *, version: int
) -> DemoIdentityConstraints:
    source_event = graph.get("session_event", graph["source_event"])
    return authority._insert_demo_row(
        session,
        DemoIdentityConstraints,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        self_state_id=graph["self_state"].id,
        version=version,
        constraint_scope="SESSION_OVERRIDE",
        source_event_digests=[source_event.content_digest],
        locks={"eyes": "PRESERVE"},
        bounds={"max_ppm": 10_000},
        prohibited_operations=[],
    )


def _bundle(
    graph: dict[str, Any],
    persistent: DemoIdentityConstraints,
    session_override: DemoIdentityConstraints,
    **overrides: Any,
) -> DemoProfileCompilationBundle:
    desired = graph["desired_delta"]
    fields: dict[str, Any] = {
        "demo_actor_id": graph["actor"].id,
        "demo_session_id": graph["session"].id,
        "demo_job_binding_id": graph["compiler_binding"].id,
        "self_state_id": graph["self_state"].id,
        "desired_delta_profile_id": desired.id,
        "style_profile_id": graph["style"].id,
        "persistent_constraints_id": persistent.id,
        "session_override_constraints_id": session_override.id,
        "as_of_event_sequence": desired.as_of_event_sequence,
        "compilation_watermark": desired.compilation_watermark,
        "compiler_version": desired.compiler_version,
        "input_digest": authority._digest("mirror.demo/TestD05Input/v1", {"v": 1}),
        "compilation_digest": authority._digest("mirror.demo/TestD05Compilation/v1", {"v": 1}),
    }
    fields.update(overrides)
    return authority._build_demo_row(DemoProfileCompilationBundle, **fields)


def _graph_with_bundle(
    session: Session,
) -> tuple[dict[str, Any], DemoIdentityConstraints, DemoProfileCompilationBundle]:
    graph = authority._insert_full_demo_graph(session, include_episode=False)
    style_event = authority._insert_preference_event(
        session,
        graph["actor"],
        sequence=3,
        previous_digest=graph["accepted_event"].content_digest,
        signal={"style_key": "natural"},
        demo_session=graph["session"],
        event_type="EXPLICIT_STYLE_SELECTION",
        source_type="EXPLICIT_USER_ACTION",
    )
    persistent_event = authority._insert_preference_event(
        session,
        graph["actor"],
        sequence=4,
        previous_digest=style_event.content_digest,
        signal={"constraint_scope": "PERSISTENT", "dimension_key": "eyes"},
        demo_session=graph["session"],
        event_type="FEATURE_LOCKED",
        source_type="EXPLICIT_USER_ACTION",
    )
    session_event = authority._insert_preference_event(
        session,
        graph["actor"],
        sequence=5,
        previous_digest=persistent_event.content_digest,
        signal={"constraint_scope": "SESSION_OVERRIDE", "dimension_key": "eyes"},
        demo_session=graph["session"],
        event_type="FEATURE_LOCKED",
        source_type="EXPLICIT_USER_ACTION",
    )
    graph["persistent_event"] = persistent_event
    graph["session_event"] = session_event
    _, binding = authority._insert_job_binding(
        session,
        graph["actor"],
        endpoint_operation="profile.compile",
        target_type="DEMO_ACTOR",
        target_id=graph["actor"].id,
        demo_session=graph["session"],
    )
    desired = authority._insert_demo_row(
        session,
        DemoDesiredDeltaProfile,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        self_state_id=graph["self_state"].id,
        demo_job_binding_id=binding.id,
        version=2,
        as_of_event_sequence=5,
        compilation_watermark=session_event.content_digest,
        compiler_version="demo-profile-compiler-v1",
        dimensions={"jaw_width_ppm": 10_000},
        evidence_digests=[graph["source_event"].content_digest],
        restraint={"max_ppm": 10_000},
    )
    style = authority._insert_demo_row(
        session,
        DemoStyleProfile,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        desired_delta_profile_id=desired.id,
        demo_job_binding_id=binding.id,
        version=2,
        as_of_event_sequence=5,
        compilation_watermark=session_event.content_digest,
        compiler_version="demo-profile-compiler-v1",
        preferences={"style_keys": ["natural"]},
        negative_evidence=[],
        evidence_digests=[style_event.content_digest],
    )
    graph["compiler_binding"] = binding
    graph["desired_delta"] = desired
    graph["style"] = style
    persistent = _persistent_constraints(session, graph)
    session_override = _session_constraints(session, graph, version=3)
    graph["constraints"] = session_override
    bundle = _bundle(graph, persistent, session_override)
    session.add(bundle)
    session.commit()
    return graph, persistent, bundle


def test_profile_bundle_persists_exact_ownership_and_rejects_duplicate_output(
    session: Session,
) -> None:
    graph, persistent, bundle = _graph_with_bundle(session)
    assert bundle.demo_actor_id == graph["actor"].id
    assert bundle.persistent_constraints_id == persistent.id

    duplicate = _bundle(graph, persistent, graph["constraints"])
    session.add(duplicate)
    with pytest.raises((DBAPIError, IntegrityError)):
        session.commit()
    session.rollback()


@pytest.mark.parametrize(
    "mutation",
    ("wrong_actor", "wrong_session", "wrong_job", "wrong_watermark", "wrong_scope"),
)
def test_profile_bundle_rejects_mixed_authority_components(session: Session, mutation: str) -> None:
    graph = authority._insert_full_demo_graph(session, include_episode=False)
    persistent = _persistent_constraints(session, graph)
    session_override = graph["constraints"]
    overrides: dict[str, Any] = {}

    if mutation == "wrong_actor":
        overrides["demo_actor_id"] = authority._insert_actor(session).id
    elif mutation == "wrong_session":
        overrides["demo_session_id"] = authority._insert_session(
            session, graph["actor"], config={"alternate": 1}
        ).id
    elif mutation == "wrong_job":
        _, binding = authority._insert_job_binding(
            session,
            graph["actor"],
            endpoint_operation="context.compile",
            target_type="DEMO_SESSION",
            target_id=graph["session"].id,
            demo_session=graph["session"],
        )
        overrides["demo_job_binding_id"] = binding.id
    elif mutation == "wrong_watermark":
        overrides["compilation_watermark"] = authority._digest(
            "mirror.demo/TestD05WrongWatermark/v1", {"v": 1}
        )
    else:
        session_override = _session_constraints(session, graph, version=3)
        overrides["persistent_constraints_id"] = graph["constraints"].id

    session.add(_bundle(graph, persistent, session_override, **overrides))
    with pytest.raises((DBAPIError, IntegrityError)):
        session.commit()
    session.rollback()


def test_profile_bundle_rejects_nonexplicit_style_event(session: Session) -> None:
    graph = authority._insert_full_demo_graph(session, include_episode=False)
    event = authority._insert_preference_event(
        session,
        graph["actor"],
        sequence=3,
        previous_digest=graph["accepted_event"].content_digest,
        signal={"answer": "RIGHT"},
        demo_session=graph["session"],
        event_type="EXPLICIT_STYLE_SELECTION",
        source_type="QUESTIONNAIRE",
    )
    _, binding = authority._insert_job_binding(
        session,
        graph["actor"],
        endpoint_operation="profile.compile",
        target_type="DEMO_ACTOR",
        target_id=graph["actor"].id,
        demo_session=graph["session"],
    )
    desired = authority._insert_demo_row(
        session,
        DemoDesiredDeltaProfile,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        self_state_id=graph["self_state"].id,
        demo_job_binding_id=binding.id,
        version=2,
        as_of_event_sequence=3,
        compilation_watermark=event.content_digest,
        compiler_version="fixture-profile-v1",
        dimensions={"jaw_width_ppm": 0},
        evidence_digests=[event.content_digest],
        restraint={"reason": "test"},
    )
    style = authority._insert_demo_row(
        session,
        DemoStyleProfile,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        desired_delta_profile_id=desired.id,
        demo_job_binding_id=binding.id,
        version=2,
        as_of_event_sequence=3,
        compilation_watermark=event.content_digest,
        compiler_version="fixture-profile-v1",
        preferences={"style_keys": ["matte"]},
        negative_evidence=[],
        evidence_digests=[event.content_digest],
    )
    persistent = _persistent_constraints(session, graph)
    session_override = _session_constraints(session, graph, version=3)
    bundle = _bundle(
        graph,
        persistent,
        session_override,
        demo_job_binding_id=binding.id,
        desired_delta_profile_id=desired.id,
        style_profile_id=style.id,
        as_of_event_sequence=3,
        compilation_watermark=event.content_digest,
    )
    session.add(bundle)
    with pytest.raises((DBAPIError, IntegrityError), match="non-authoritative explicit event"):
        session.commit()
    session.rollback()


def _valid_self_transfer_evidence(
    session: Session,
) -> tuple[dict[str, Any], DemoSelfTransferDimensionEvidence]:
    graph = authority._insert_full_demo_graph(session, include_episode=False)
    request = graph["transfer_request"]
    _, binding = authority._insert_job_binding(
        session,
        graph["actor"],
        endpoint_operation="self_transfer.execute",
        target_type="SELF_TRANSFER_RUN",
        target_id=request.id,
        demo_session=graph["session"],
    )
    result = authority._insert_demo_row(
        session,
        DemoSelfTransferRun,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        desired_delta_profile_id=graph["desired_delta"].id,
        record_kind="RESULT",
        request_run_id=request.id,
        demo_job_binding_id=binding.id,
        source_asset_id=graph["source_asset"].id,
        result_asset_id=graph["image1_asset"].id,
        requested_delta={"jaw_width_ppm": 10_000},
        measured_delta={"jaw_width": 10_000},
        non_target_drift={"max_ppm": 0},
        verifier_digest=graph["verification"].content_digest,
        user_outcome="ACCEPTED",
    )
    evidence = authority._build_demo_row(
        DemoSelfTransferDimensionEvidence,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        self_transfer_run_id=result.id,
        dimension_key="jaw_width",
        desired_delta_ppm=10_000,
        confidence_ppm=900_000,
        verifier_outcome="PASS",
        verifier_digest=graph["verification"].content_digest,
        projection_version="demo-self-transfer-projection-v1",
        projection_config_digest=authority._digest("mirror.demo/TestD05Projection/v1", {"v": 1}),
    )
    session.add(evidence)
    session.commit()
    return graph, evidence


def test_self_transfer_projection_requires_parent_measurement_verifier_and_is_immutable(
    session: Session,
) -> None:
    _, evidence = _valid_self_transfer_evidence(session)
    assert evidence.verifier_outcome == "PASS"

    for statement in (
        "UPDATE demo_self_transfer_evidence SET confidence_ppm=1 WHERE id=:id",
        "DELETE FROM demo_self_transfer_evidence WHERE id=:id",
    ):
        with pytest.raises((DBAPIError, IntegrityError)):
            session.execute(text(statement), {"id": evidence.id})
            session.commit()
        session.rollback()


@pytest.mark.parametrize(
    "field,value", (("desired_delta_ppm", 9_999), ("verifier_outcome", "FAIL"))
)
def test_self_transfer_projection_rejects_wrong_measurement_or_verifier(
    session: Session, field: str, value: object
) -> None:
    graph, evidence = _valid_self_transfer_evidence(session)
    forged = authority._build_demo_row(
        DemoSelfTransferDimensionEvidence,
        demo_actor_id=evidence.demo_actor_id,
        demo_session_id=evidence.demo_session_id,
        self_transfer_run_id=evidence.self_transfer_run_id,
        dimension_key="chin_height",
        desired_delta_ppm=10_000,
        confidence_ppm=900_000,
        verifier_outcome="PASS",
        verifier_digest=graph["verification"].content_digest,
        projection_version=evidence.projection_version,
        projection_config_digest=evidence.projection_config_digest,
    )
    setattr(forged, field, value)
    forged = authority._build_demo_row(
        DemoSelfTransferDimensionEvidence,
        row_id=forged.id,
        demo_actor_id=forged.demo_actor_id,
        demo_session_id=forged.demo_session_id,
        self_transfer_run_id=forged.self_transfer_run_id,
        dimension_key=forged.dimension_key,
        desired_delta_ppm=forged.desired_delta_ppm,
        confidence_ppm=forged.confidence_ppm,
        verifier_outcome=forged.verifier_outcome,
        verifier_digest=forged.verifier_digest,
        projection_version=forged.projection_version,
        projection_config_digest=forged.projection_config_digest,
    )
    session.add(forged)
    with pytest.raises((DBAPIError, IntegrityError)):
        session.commit()
    session.rollback()


def test_self_transfer_projection_rejects_verifier_for_different_result_asset(
    session: Session,
) -> None:
    graph, _ = _valid_self_transfer_evidence(session)
    unrelated_execution = authority._prepare_followup_execution(session, graph)
    authority._commit_execution_pair(session, unrelated_execution)

    request = graph["transfer_request"]
    _, binding = authority._insert_job_binding(
        session,
        graph["actor"],
        endpoint_operation="self_transfer.execute",
        target_type="SELF_TRANSFER_RUN",
        target_id=request.id,
        demo_session=graph["session"],
    )
    unrelated_verifier = unrelated_execution["verification"]
    result = authority._insert_demo_row(
        session,
        DemoSelfTransferRun,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        desired_delta_profile_id=graph["desired_delta"].id,
        record_kind="RESULT",
        request_run_id=request.id,
        demo_job_binding_id=binding.id,
        source_asset_id=graph["source_asset"].id,
        result_asset_id=graph["image1_asset"].id,
        requested_delta={"jaw_width_ppm": 10_000},
        measured_delta={"jaw_width": 10_000},
        non_target_drift={"max_ppm": 0},
        verifier_digest=unrelated_verifier.content_digest,
        user_outcome="ACCEPTED",
    )
    evidence = authority._build_demo_row(
        DemoSelfTransferDimensionEvidence,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        self_transfer_run_id=result.id,
        dimension_key="jaw_width",
        desired_delta_ppm=10_000,
        confidence_ppm=900_000,
        verifier_outcome="PASS",
        verifier_digest=unrelated_verifier.content_digest,
        projection_version="demo-self-transfer-projection-v1",
        projection_config_digest=authority._digest("mirror.demo/TestD05Projection/v1", {"v": 1}),
    )
    session.add(evidence)
    with pytest.raises((DBAPIError, IntegrityError), match="verifier mismatch"):
        session.commit()
    session.rollback()


def test_d05_alembic_check_and_populated_downgrade_fail_closed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _ = _valid_self_transfer_evidence(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = authority._demo_alembic_config(database_url)
    command.check(config)
    session.close()
    with pytest.raises(Exception, match="cannot downgrade populated D05 profile authority"):
        command.downgrade(config, _DOWN)
    command.upgrade(config, _HEAD)
