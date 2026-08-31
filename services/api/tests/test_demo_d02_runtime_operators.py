from __future__ import annotations

import json
import os
from io import BytesIO
from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import create_engine

from mirror_api.demo_d02_candidate_operator import (
    CANDIDATE_REVIEW_COMMAND_SCHEMA,
    D02CandidateOperatorError,
    _candidate_review,
    _read_command,
)
from mirror_api.demo_d02_final_orchestrator import RuntimeReviewSubject
from mirror_api.demo_d02_final_runtime_operator import (
    ARTIFACT_REVIEW_COMMAND_SCHEMA,
    SOURCE_REVIEW_COMMAND_SCHEMA,
    D02FinalRuntimeOperatorError,
    _artifact_decisions,
    _read_json_line,
    _run_advisory_lock,
    _source_reviews,
)
from mirror_api.demo_models import D02SelectedSourceManifest, D02SourceCandidate


def _candidate(position: int) -> D02SourceCandidate:
    return cast(
        D02SourceCandidate,
        SimpleNamespace(
            id=f"{position:032x}",
            content_digest=f"{position:064x}",
            selector_slot_id=f"D02_SLOT_0{position}",
        ),
    )


def _candidate_command() -> dict[str, object]:
    return {
        "schema_version": CANDIDATE_REVIEW_COMMAND_SCHEMA,
        "reviewer_role": "D02_SUBSYSTEM_PRINCIPAL",
        "synthetic_adult_attested": True,
        "suspected_minor": False,
        "real_person_reference_used": False,
        "celebrity_imitation_suspected": False,
        "face_count": 1,
        "front_facing": True,
        "features_unobstructed": True,
        "quality_sufficient": True,
        "style_context_match": True,
        "variable_contamination": False,
        "anti_homogenization_passed": True,
        "rejection_code": None,
    }


def test_candidate_review_command_is_bound_by_operator() -> None:
    candidate = _candidate(1)
    command = _candidate_command()
    review = _candidate_review(command, candidate=candidate, normalized_sha256="a" * 64)
    assert review.accepted
    assert review.candidate_id == candidate.id
    assert review.normalized_sha256 == "a" * 64

    command["synthetic_adult_attested"] = "yes"
    with pytest.raises(D02CandidateOperatorError):
        _candidate_review(command, candidate=candidate, normalized_sha256="a" * 64)


def test_candidate_and_final_review_readers_consume_one_bounded_line() -> None:
    first = json.dumps(_candidate_command(), separators=(",", ":")).encode() + b"\n"
    assert _read_command(BytesIO(first))["schema_version"] == CANDIDATE_REVIEW_COMMAND_SCHEMA
    stream = BytesIO(b'{"schema_version":"one"}\n{"schema_version":"two"}\n')
    assert _read_json_line(stream, code="BAD")["schema_version"] == "one"
    assert _read_json_line(stream, code="BAD")["schema_version"] == "two"


def test_source_and_artifact_review_commands_require_exact_order_and_digest() -> None:
    candidates = tuple(_candidate(index) for index in range(1, 5))
    normalized = tuple(f"{index + 20:064x}" for index in range(1, 5))
    manifest = cast(
        D02SelectedSourceManifest,
        SimpleNamespace(id="f" * 32, content_digest="e" * 64),
    )
    source_command = {
        "schema_version": SOURCE_REVIEW_COMMAND_SCHEMA,
        "reviews": [
            {
                "position": position,
                "candidate_id": candidate.id,
                "normalized_sha256": sha256,
                "synthetic_adult_attested": True,
                "suspected_minor": False,
                "real_person_reference_used": False,
                "celebrity_imitation_suspected": False,
                "style_context_match": True,
                "anti_homogenization_passed": True,
            }
            for position, (candidate, sha256) in enumerate(
                zip(candidates, normalized, strict=True), start=1
            )
        ],
    }
    reviews = _source_reviews(
        source_command,
        manifest=manifest,
        candidates=candidates,
        normalized_sha256=normalized,
    )
    assert len(reviews) == 4
    assert all(review.accepted for review in reviews)

    subjects = tuple(
        RuntimeReviewSubject(
            case_id=f"{index:032x}",
            result_sha256=f"{index + 100:064x}",
            decision_sequence=index,
        )
        for index in range(1, 49)
    )
    artifact_command = {
        "schema_version": ARTIFACT_REVIEW_COMMAND_SCHEMA,
        "decisions": [
            {
                "case_id": subject.case_id,
                "result_sha256": subject.result_sha256,
                "decision_sequence": subject.decision_sequence,
                "manual_review_version": "d02-artifact-review-v1",
                "background_seam": False,
                "disconnected_contour": False,
                "duplicated_feature": False,
                "warp_tear": False,
            }
            for subject in subjects
        ],
    }
    decisions = _artifact_decisions(artifact_command, subjects)
    assert len(decisions) == 48

    cast(list[dict[str, object]], artifact_command["decisions"])[0]["result_sha256"] = "0" * 64
    with pytest.raises(D02FinalRuntimeOperatorError, match="ARTIFACT_REVIEW_COMMAND_INVALID"):
        _artifact_decisions(artifact_command, subjects)


@pytest.mark.integration
def test_final_runtime_advisory_lock_is_run_scoped_and_releasable() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required")
    engine = create_engine(database_url)
    run_id = "a" * 32
    try:
        with _run_advisory_lock(engine, run_id):
            with pytest.raises(D02FinalRuntimeOperatorError, match="FINAL_RUNTIME_ALREADY_ACTIVE"):
                with _run_advisory_lock(engine, run_id):
                    raise AssertionError("concurrent final runtime acquired the same run lock")
        with _run_advisory_lock(engine, run_id):
            pass
    finally:
        engine.dispose()
