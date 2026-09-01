from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = (
    ROOT / "docs" / "operations" / "P2_M5_R65_CUSTODY_LOSS_RETIREMENT_AND_CAL005_PREFLIGHT.md"
)
EVIDENCE = ROOT / "docs" / "operations" / "P2_M5_R65_RECOVERY_EXHAUSTION_EVIDENCE.json"
ACCEPTANCE = ROOT / "docs" / "operations" / "P2_M5_ACCEPTANCE.md"
EXECUTION = ROOT / "docs" / "operations" / "P2_M5_EXECUTION_PROTOCOL.md"


def test_r65_retirement_and_preflight_contract_is_fail_closed() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    for required in (
        "CONSUMED_REGISTERED_PRE_DECODE_PRIVATE_OBJECT_UNRECOVERABLE_WITHIN_AUTHORIZED_SCOPE",
        "FAILED_INFRASTRUCTURE_EVIDENCE_LOCATION_LOST_NO_RETRY",
        "CAL_REQ_004_REDISPATCH: PROHIBITED",
        "CAL_REQ_004_RETRY: PROHIBITED",
        "CAL_REQ_004_COUNTER_REFUND: PROHIBITED",
        "p2-m5-cal-req-005-end-to-end-durable-handle-v1",
        "REQUIRED_ZERO_IMAGE_ZERO_ORDINAL",
        "not an end-to-end durable preflight",
        "zero-impact proof is performed against the real durable chain",
        "real M3 executor handle",
        "NEXT_READY_TASK: EXECUTE_CAL_REQ_005",
    ):
        assert required in contract

    assert evidence["recovery_result"] == (
        "UNRECOVERABLE_WITHIN_FINAL_AUTHORIZED_PROJECT_PRIVATE_SCOPE"
    )
    assert evidence["path_entries_enumerated"] == 200000
    assert evidence["metadata_content_reads"] == 0
    assert evidence["reparse_points_followed"] == 0
    assert evidence["imagegen_calls"] == evidence["decode_calls"] == evidence["m3_calls"] == 0
    assert evidence["resource_ledger_expected"] == {
        "next_unused_formal_ordinal": "CAL-REQ-005",
        "formal_calls_remaining": 28,
        "formal_raw_capacity_remaining": 28,
        "global_native_output_capacity_remaining": 59,
    }

    for forbidden in (".private-handoff", ".local-storage", "data:image/", "receipt_locator"):
        assert forbidden not in contract


def test_r65_true_eof_is_canonical_mirror_and_locator_free() -> None:
    canonical_text = ACCEPTANCE.read_text(encoding="utf-8")
    mirror_text = EXECUTION.read_text(encoding="utf-8")
    canonical = canonical_text.rsplit("## Current authoritative state — P2-M5-R65", 1)[1]
    mirror = mirror_text.rsplit("## Current authoritative state mirror — P2-M5-R65", 1)[1]
    assert canonical == mirror
    assert canonical_text.rstrip().endswith("P2_M5_R65_CUSTODY_LOSS_RETIREMENT_TRUE_EOF")
    assert mirror_text.rstrip().endswith("P2_M5_R65_CUSTODY_LOSS_RETIREMENT_TRUE_EOF")

    for required in (
        "P2_M5_R65: PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE",
        "CAL_REQ_004_REPLACEMENT: PROHIBITED",
        "CAL_REQ_004_COUNTER_REFUND: PROHIBITED",
        "NEXT_UNUSED_FORMAL_ORDINAL: CAL-REQ-005",
        "CAL_REQ_005_DURABLE_PREFLIGHT: REQUIRED_ZERO_IMAGE_ZERO_ORDINAL",
        "NEXT_READY_TASK: EXECUTE_CAL_REQ_005",
    ):
        assert required in canonical

    for forbidden in (".private-handoff", ".local-storage", "data:image/", "receipt_locator"):
        assert forbidden not in canonical
