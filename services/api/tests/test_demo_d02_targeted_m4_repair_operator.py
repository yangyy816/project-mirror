from __future__ import annotations

import io
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from test_demo_d02_targeted_m4_successor_checkpoint import (
    _actual_successor_evidence,
    _output,
    _screened_checkpoint,
    _setup,
)

from mirror_api import demo_d02_targeted_m4_repair as repair
from mirror_api import demo_d02_targeted_m4_repair_execution as repair_execution
from mirror_api import demo_d02_targeted_m4_repair_operator as repair_operator
from mirror_api.demo_d02_r2_runtime_forward import M4ExecutionOutput
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision
from mirror_api.demo_d02_targeted_m4_repair_backend import D02TargetedM4RepairBackend


def _review_command(output: M4ExecutionOutput) -> dict[str, object]:
    return {
        "schema_version": repair_operator.TARGETED_ARTIFACT_REVIEW_COMMAND_SCHEMA,
        "decision": {
            "case_id": output.case_id,
            "result_sha256": output.result_sha256,
            "decision_sequence": 25,
            "manual_review_version": "d02-targeted-artifact-review-v1",
            "background_seam": False,
            "disconnected_contour": False,
            "duplicated_feature": False,
            "warp_tear": False,
        },
    }


def test_targeted_artifact_review_is_bound_to_one_successor() -> None:
    first = _output(1)
    decision = repair_operator._targeted_artifact_decision(
        _review_command(first),
        output=first,
    )

    assert isinstance(decision, PrincipalArtifactDecision)
    assert decision.case_id == first.case_id
    assert decision.result_sha256 == first.result_sha256
    assert decision.decision_sequence == 25

    tampered = deepcopy(_review_command(first))
    cast(dict[str, object], tampered["decision"])["result_sha256"] = "0" * 64
    with pytest.raises(
        repair_operator.D02TargetedM4RepairOperatorError,
        match="TARGETED_ARTIFACT_REVIEW_COMMAND_INVALID",
    ):
        repair_operator._targeted_artifact_decision(tampered, output=first)


def test_targeted_review_reader_rejects_tty_and_duplicate_keys() -> None:
    class _TTY(io.BytesIO):
        def isatty(self) -> bool:
            return True

    with pytest.raises(
        repair_operator.D02TargetedM4RepairOperatorError,
        match="TTY_INPUT_FORBIDDEN",
    ):
        repair_operator._read_json_line(_TTY(b"{}\n"), code="INVALID")

    with pytest.raises(
        repair_operator.D02TargetedM4RepairOperatorError,
        match="INVALID",
    ):
        repair_operator._read_json_line(
            io.BytesIO(b'{"schema_version":"a","schema_version":"b"}\n'),
            code="INVALID",
        )


def test_complete_store_at_policy_stage_advances_without_m4_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    store.persist(first, second)
    recovered = checkpoint.load(store=store)
    assert recovered.m4_outputs == (first, second)

    operator = object.__new__(repair_operator.D02TargetedM4RepairOperator)

    def forbidden(**_: object) -> object:
        raise AssertionError("durable M4 must not be reexecuted")

    monkeypatch.setattr(operator, "_execution_context", forbidden)
    advanced = operator._ensure_m4_durable(
        checkpoint=checkpoint,
        store=store,
        recovered=recovered,
        predecessor=cast(repair_operator._Predecessor, object()),
        m4_backend=cast(D02TargetedM4RepairBackend, object()),
    )
    assert advanced.stage == "TARGET_M4_DURABLE"
    assert advanced.m4_outputs == (first, second)


def test_stage_order_is_exact_and_fail_closed() -> None:
    assert repair_operator._stage_at_least("ADMISSION_READY", "TARGET_M4_DURABLE")
    assert not repair_operator._stage_at_least("REPAIR_POLICY_VALIDATED", "TARGET_M4_DURABLE")
    with pytest.raises(
        repair_operator.D02TargetedM4RepairOperatorError,
        match="SUCCESSOR_STAGE_INVALID",
    ):
        repair_operator._stage_at_least("UNKNOWN", "TARGET_M4_DURABLE")


def test_screened_checkpoint_resume_normalizes_frozen_public_trees(tmp_path: Path) -> None:
    checkpoint, store = _screened_checkpoint(tmp_path)
    recovered = checkpoint.load(store=store)
    _, _, records, _, universe, envelope = _actual_successor_evidence()
    assert len(repair_execution.adapter_fields_from_records(recovered.result_m3_records)) == 3

    operator = object.__new__(repair_operator.D02TargetedM4RepairOperator)
    successor = cast(
        repair.TargetedM4RepairSuccessor,
        SimpleNamespace(successor_universe=universe, provenance_envelope=envelope),
    )
    replayed = operator._ensure_screening_checkpoint(
        checkpoint=checkpoint,
        store=store,
        recovered=recovered,
        successor=successor,
    )
    assert replayed.stage == "SUCCESSOR_SCREENING_REPLAYED"
    assert [item["record_digest"] for item in recovered.result_m3_records] == [
        item["record_digest"] for item in records
    ]
