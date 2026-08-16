"""Application service for ADR-027 QA evidence; identity registration stays in T05."""

from __future__ import annotations

import re
from decimal import Decimal

from mirror_api.models import SyntheticQAMeasurement, SyntheticQAReviewDecision, new_id, utcnow
from mirror_api.synthetic_dataset.domain import CanonicalPolicy
from mirror_api.synthetic_dataset.qa_repository import SyntheticQARepository
from mirror_api.synthetic_dataset.qa_types import (
    QAEvaluation,
    QAMeasurementEvidence,
    QAOutcome,
    QAPolicyDefinition,
    QAReviewEvidence,
    ReviewDecision,
    ThresholdOutcome,
    evaluate_qa,
)


class SyntheticQAService:
    def __init__(self, repository: SyntheticQARepository) -> None:
        self._repository = repository

    async def start(self, *, run_id: str) -> bool:
        run = await self._repository.locked_run(run_id)
        if run is None:
            raise ValueError("QA run was not found")
        if run.status == "RUNNING":
            return False
        if self._repository.is_terminal(run):
            return False
        if run.status != "PENDING":
            raise ValueError("QA run state is invalid")
        run.status = "RUNNING"
        run.started_at = utcnow()
        await self._repository.flush()
        return True

    async def append_measurement(self, *, run_id: str, evidence: QAMeasurementEvidence) -> None:
        run = await self._repository.locked_run(run_id)
        if run is None or run.status != "RUNNING":
            raise ValueError("QA evidence requires a running QA run")
        self._repository.add(
            SyntheticQAMeasurement(
                id=new_id(),
                qa_run_id=run_id,
                measurement_kind=evidence.measurement_kind,
                measurement_code=evidence.measurement_code,
                payload=evidence.payload,
                payload_digest=evidence.payload_digest,
                algorithm_reference=evidence.algorithm_reference,
                algorithm_version=evidence.algorithm_version,
                confidence=(
                    Decimal(str(evidence.confidence)) if evidence.confidence is not None else None
                ),
                hard_gate=evidence.hard_gate,
                threshold_outcome=evidence.threshold_outcome.value,
                reason_code=evidence.reason_code,
            )
        )
        await self._repository.flush()

    async def append_review(self, *, run_id: str, evidence: QAReviewEvidence) -> None:
        run = await self._repository.locked_run(run_id)
        if run is None or run.status != "RUNNING":
            raise ValueError("QA evidence requires a running QA run")
        now = utcnow()
        self._repository.add(
            SyntheticQAReviewDecision(
                id=new_id(),
                qa_run_id=run_id,
                review_kind=evidence.review_kind,
                decision=evidence.decision.value,
                reason_code=evidence.reason_code,
                actor_reference=evidence.actor_reference,
                reviewed_at=now,
                created_at=now,
            )
        )
        await self._repository.flush()

    async def fail_execution(self, *, run_id: str, reason_code: str) -> bool:
        """Record an execution failure without claiming the normalized asset was rejected."""
        if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", reason_code) is None:
            raise ValueError("QA execution reason code is invalid")
        run = await self._repository.locked_run(run_id)
        if run is None:
            raise ValueError("QA run was not found")
        if self._repository.is_terminal(run):
            return False
        if run.status != "RUNNING":
            raise ValueError("QA execution failure requires a running QA run")
        run.status = "FAILED"
        run.result_code = reason_code
        run.finalized_at = utcnow()
        await self._repository.flush()
        return True

    async def finalize(self, *, run_id: str) -> QAEvaluation:
        run = await self._repository.locked_run(run_id)
        if run is None:
            raise ValueError("QA run was not found")
        if self._repository.is_terminal(run):
            raise ValueError("QA run is already terminal")
        if run.status != "RUNNING":
            raise ValueError("QA run must be running before finalization")
        policy = await self._repository.policy_for_run(run)
        if policy is None or policy.approval_status != "APPROVED":
            raise ValueError("QA run requires an approved policy definition")
        CanonicalPolicy.validate_external(
            schema_version=policy.schema_version,
            version=policy.version,
            content=policy.content,
            content_digest=policy.content_digest,
        )
        definition = QAPolicyDefinition.parse(policy.content)
        measurement_rows, review_rows = await self._repository.evidence(run_id)
        evaluation = evaluate_qa(
            requirements=definition.requirements,
            measurements=tuple(
                QAMeasurementEvidence(
                    measurement_kind=row.measurement_kind,
                    measurement_code=row.measurement_code,
                    payload=row.payload,
                    algorithm_reference=row.algorithm_reference,
                    algorithm_version=row.algorithm_version,
                    confidence=float(row.confidence) if row.confidence is not None else None,
                    hard_gate=row.hard_gate,
                    threshold_outcome=ThresholdOutcome(row.threshold_outcome),
                    reason_code=row.reason_code,
                )
                for row in measurement_rows
            ),
            reviews=tuple(
                QAReviewEvidence(
                    review_kind=row.review_kind,
                    decision=ReviewDecision(row.decision),
                    reason_code=row.reason_code,
                    actor_reference=row.actor_reference,
                )
                for row in review_rows
            ),
        )
        run.status = "PASSED" if evaluation.outcome is QAOutcome.PASSED else "REJECTED"
        run.result_code = evaluation.reason_code
        run.finalized_at = utcnow()
        await self._repository.flush()
        return evaluation
