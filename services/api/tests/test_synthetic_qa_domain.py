from __future__ import annotations

import asyncio
from hashlib import sha256
from types import SimpleNamespace
from typing import cast

import pytest

from mirror_api.providers.base import NormalizedSyntheticImagePayload, SyntheticVisionRequest
from mirror_api.providers.mock import MockVisionProvider
from mirror_api.synthetic_dataset.qa_repository import SyntheticQARepository
from mirror_api.synthetic_dataset.qa_service import SyntheticQAService
from mirror_api.synthetic_dataset.qa_types import (
    QAMeasurementEvidence,
    QAOutcome,
    QAPolicyDefinition,
    QARequirement,
    QAReviewEvidence,
    ReviewDecision,
    ThresholdOutcome,
    evaluate_qa,
)


class _InMemoryRepository:
    def __init__(self) -> None:
        self.run = SimpleNamespace(status="RUNNING", result_code=None, finalized_at=None)

    async def locked_run(self, run_id: str) -> SimpleNamespace:
        assert run_id == "qa-run-001"
        return self.run

    @staticmethod
    def is_terminal(run: SimpleNamespace) -> bool:
        return run.status in {"PASSED", "REJECTED", "FAILED"}

    async def flush(self) -> None:
        return None


def _measurement(*, outcome: ThresholdOutcome = ThresholdOutcome.PASSED) -> QAMeasurementEvidence:
    return QAMeasurementEvidence(
        measurement_kind="face_count",
        measurement_code="exactly_one_face",
        payload={"count": 1},
        algorithm_reference="mirror.fixture/face-count",
        algorithm_version="v1",
        confidence=1.0,
        hard_gate=True,
        threshold_outcome=outcome,
        reason_code="exactly_one_face",
    )


def _measurement_requirement(*, hard_gate: bool = True) -> QARequirement:
    return QARequirement(
        "exactly_one_face",
        "measurement",
        hard_gate,
        algorithm_reference="mirror.fixture/face-count",
        algorithm_version="v1",
        threshold_rule_reference="face-count-rule-v1",
    )


def test_required_unknown_or_unmeasured_evidence_fails_closed() -> None:
    result = evaluate_qa(
        requirements=(
            QARequirement(
                "approved_vision",
                "measurement",
                True,
                algorithm_reference="mirror.fixture/vision",
                algorithm_version="v1",
                threshold_rule_reference="vision-rule-v1",
            ),
        ),
        measurements=(),
        reviews=(),
    )
    assert result.outcome is QAOutcome.REJECTED
    assert result.reason_code == "required_evidence_unresolved"
    assert result.unresolved_requirements == ("approved_vision",)


def test_hard_measurement_failure_cannot_be_overridden_by_review() -> None:
    result = evaluate_qa(
        requirements=(_measurement_requirement(),),
        measurements=(_measurement(outcome=ThresholdOutcome.FAILED),),
        reviews=(
            QAReviewEvidence(
                review_kind="adult_presentation",
                decision=ReviewDecision.PASSED,
                reason_code="adult_presentation_passed",
                actor_reference="operator:m3-reviewer",
            ),
        ),
    )
    assert result.outcome is QAOutcome.REJECTED
    assert result.reason_code == "hard_measurement_failed"


def test_human_review_is_explicit_and_deterministic() -> None:
    requirements = (
        _measurement_requirement(),
        QARequirement(
            "adult_presentation", "review", True, review_rule_reference="adult-review-v1"
        ),
    )
    reviews = (
        QAReviewEvidence(
            review_kind="adult_presentation",
            decision=ReviewDecision.PASSED,
            reason_code="adult_presentation_passed",
            actor_reference="operator:m3-reviewer",
        ),
    )
    assert evaluate_qa(
        requirements=requirements, measurements=(_measurement(),), reviews=reviews
    ) == evaluate_qa(requirements=requirements, measurements=(_measurement(),), reviews=reviews)
    assert (
        evaluate_qa(
            requirements=requirements,
            measurements=(_measurement(),),
            reviews=(
                QAReviewEvidence(
                    review_kind="adult_presentation",
                    decision=ReviewDecision.REJECTED,
                    reason_code="adult_presentation_rejected",
                    actor_reference="operator:m3-reviewer",
                ),
            ),
        ).outcome
        is QAOutcome.REJECTED
    )


def test_algorithm_or_hard_gate_mismatch_fails_closed() -> None:
    incompatible = QAMeasurementEvidence(
        measurement_kind="face_count",
        measurement_code="exactly_one_face",
        payload={"count": 1},
        algorithm_reference="mirror.fixture/other",
        algorithm_version="v2",
        confidence=1.0,
        hard_gate=False,
        threshold_outcome=ThresholdOutcome.PASSED,
        reason_code="exactly_one_face",
    )
    result = evaluate_qa(
        requirements=(_measurement_requirement(),), measurements=(incompatible,), reviews=()
    )
    assert result.outcome is QAOutcome.REJECTED
    assert result.reason_code == "required_evidence_unresolved"


def test_policy_definition_requires_closed_versioned_grammar() -> None:
    with pytest.raises(ValueError, match="schema"):
        QAPolicyDefinition.parse({"requirements": []})
    with pytest.raises(ValueError, match="invalid"):
        QAPolicyDefinition.parse(
            {
                "schema_version": "mirror.synthetic-dataset/QAPolicyDefinition/v1",
                "requirements": [{"code": "extra", "evidence_type": "review", "hard_gate": True}],
            }
        )


def test_execution_failure_is_not_content_rejection() -> None:
    repository = _InMemoryRepository()
    service = SyntheticQAService(cast(SyntheticQARepository, repository))
    assert asyncio.run(service.fail_execution(run_id="qa-run-001", reason_code="vision_timeout"))
    assert repository.run.status == "FAILED"
    assert repository.run.result_code == "vision_timeout"
    with pytest.raises(ValueError, match="canonical JSON"):
        QAMeasurementEvidence(
            measurement_kind="face_count",
            measurement_code="exactly_one_face",
            payload={"count": float("nan")},
            algorithm_reference="mirror.fixture/face-count",
            algorithm_version="v1",
            confidence=1.0,
            hard_gate=True,
            threshold_outcome=ThresholdOutcome.PASSED,
            reason_code="exactly_one_face",
        )
    with pytest.raises(ValueError, match="algorithm reference"):
        QAMeasurementEvidence(
            measurement_kind="face_count",
            measurement_code="exactly_one_face",
            payload={"count": 1},
            algorithm_reference="mirror.fixture/face-count",
            algorithm_version="invalid version",
            confidence=1.0,
            hard_gate=True,
            threshold_outcome=ThresholdOutcome.PASSED,
            reason_code="exactly_one_face",
        )


def test_normalized_vision_port_rejects_raw_style_and_is_zero_network_deterministic() -> None:
    with pytest.raises(TypeError):
        SyntheticVisionRequest(  # type: ignore[call-arg]
            request_reference="vision-request-raw",
            image=object(),
            vision_policy_reference="vision-policy-v1",
        )
    request = SyntheticVisionRequest(
        request_reference="vision-request-001",
        normalized_image=NormalizedSyntheticImagePayload(
            normalized_asset_reference="normalized-asset-001",
            content=b"canonical-jpeg-fixture",
            sha256=sha256(b"canonical-jpeg-fixture").hexdigest(),
            media_type="image/jpeg",
        ),
        vision_policy_reference="vision-policy-v1",
    )
    provider = MockVisionProvider()
    assert asyncio.run(provider.inspect_synthetic(request=request)) == asyncio.run(
        provider.inspect_synthetic(request=request)
    )
    with pytest.raises(ValueError, match="canonical JPEG"):
        NormalizedSyntheticImagePayload(
            normalized_asset_reference="normalized-asset-001",
            content=b"raw-png",
            sha256=sha256(b"raw-png").hexdigest(),
            media_type="image/png",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="opaque first-party reference"):
        NormalizedSyntheticImagePayload(
            normalized_asset_reference="https://untrusted.example/object",
            content=b"canonical-jpeg-fixture",
            sha256=sha256(b"canonical-jpeg-fixture").hexdigest(),
            media_type="image/jpeg",
        )
