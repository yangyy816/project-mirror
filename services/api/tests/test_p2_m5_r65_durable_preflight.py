from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from mirror_api.synthetic_dataset import private_execution_overlay as overlay


def test_r65_temporary_transport_harness_is_non_authoritative_and_recoverable(
    tmp_path: Path,
) -> None:
    """Exercise isolated orchestration only; this is not a formal preflight."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").write_text("gitdir: durable-preflight-test\n", encoding="utf-8")
    (project / ".gitignore").write_text(".private-handoff/\n", encoding="utf-8")
    private_parent = project / ".private-handoff"
    private_parent.mkdir()
    root = private_parent / "cal-req-005-durable-preflight"
    controller_sha256 = overlay.sha256_file(Path(overlay.__file__))
    initial = overlay.initialize_overlay(
        allowed_parent=private_parent,
        root=root,
        overlay_output_id="OVERLAY-CAL-REQ-005",
        controller_sha256=controller_sha256,
        binding=overlay.GenesisBinding(
            genesis_output_id="GENESIS-CAL-REQ-005",
            genesis_bootstrap_sha256="1" * 64,
            genesis_receipt_sha256="2" * 64,
            private_registry_sha256="3" * 64,
            generation_specification_version="durable-preflight-v1",
            generation_specification_sha256="4" * 64,
            assignment_manifest_version="durable-preflight-assignment-v1",
            assignment_manifest_sha256="5" * 64,
            prompt_template_version="durable-preflight-prompt-v1",
            prompt_template_sha256="6" * 64,
            policy_digest="7" * 64,
            request_call_count=4,
            requested_output_count=4,
            returned_output_count=4,
            raw_output_count=4,
            formal_calls_remaining=28,
            formal_raw_capacity_remaining=28,
            global_native_output_capacity_remaining=59,
            global_native_output_consumed=5,
            next_unused_ordinal="CAL-REQ-005",
        ),
        timestamp="2026-09-01T00:00:00Z",
    )
    action_id = "ACTION-CAL-REQ-005-PREFLIGHT"
    output_id = "OUTPUT-CAL-REQ-005-PREFLIGHT"
    prepared = overlay.prepare_dispatch(
        receipt_path=initial.receipt_path,
        expected_controller_sha256=controller_sha256,
        ordinal="CAL-REQ-005",
        action_id=action_id,
        expected_output_opaque_id=output_id,
        timestamp="2026-09-01T00:00:01Z",
    )
    consumed = overlay.consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=controller_sha256,
        action_id=action_id,
        timestamp="2026-09-01T00:00:02Z",
    )
    payload = b"\x89PNG\r\n\x1a\nR65-DURABLE-PREFLIGHT-NO-DECODE"
    data_url = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
    returned = overlay.record_output_returned(
        receipt_path=consumed.receipt_path,
        expected_controller_sha256=controller_sha256,
        action_id=action_id,
        timestamp="2026-09-01T00:00:03Z",
        returned_output_count=1,
        exact_generated_artifact_receipt=data_url,
    )
    registered = overlay.register_imagegen_data_url_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=controller_sha256,
        action_id=action_id,
        project_worktree_root=project,
        imagegen_data_url=data_url,
        timestamp="2026-09-01T00:00:04Z",
    )
    registration = overlay.verify_registration_before_decode(
        registered.receipt_path,
        expected_controller_sha256=controller_sha256,
        project_worktree_root=project,
    )
    verified = overlay.verify_overlay(
        registered.receipt_path, expected_controller_sha256=controller_sha256
    )
    state = cast(dict[str, Any], verified["state"])
    assert state["phase"] == "OUTPUT_REGISTERED_PRE_DECODE"
    assert registration["source_sha256"] == overlay.sha256_bytes(payload)
    assert state["counters"]["request_call_count"] == 5
    assert state["counters"]["raw_output_count"] == 5
    assert state["counters"]["formal_calls_remaining"] == 27
    assert state["counters"]["formal_raw_capacity_remaining"] == 27
    assert state["output_registration"]["registration_status"] == "COMMITTED"
    assert state["output_registration"]["receipt_status"] == "VALID"

    code = (
        "from pathlib import Path\n"
        "from mirror_api.synthetic_dataset import private_execution_overlay as o\n"
        f"o.verify_registration_before_decode(Path({str(registered.receipt_path)!r}),"
        f"expected_controller_sha256={controller_sha256!r},project_worktree_root=Path({str(project)!r}))\n"
    )
    fresh = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        check=False,
        capture_output=True,
        text=True,
    )
    assert fresh.returncode == 0, fresh.stderr
