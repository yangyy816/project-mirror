from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_MODULE_PATH = _ROOT / "scripts/governance/private_input_handoff.py"
_SPEC = importlib.util.spec_from_file_location("private_input_handoff", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
handoff: ModuleType = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = handoff
_SPEC.loader.exec_module(handoff)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _spec(value: bytes, **overrides: object) -> object:
    values: dict[str, object] = {
        "input_id": "SYNTHETIC_REPORT",
        "classification": handoff.InputClassification.PRIVATE_SENSITIVE_INPUT,
        "authority": "synthetic-test-authority",
        "expected_digest": _digest(value),
        "maximum_bytes": 1024,
        "allowed_task_id": "TASK_A",
        "allowed_agent_role": "pm_terra_high_worker",
        "allowed_operation": "READ_EXACT_BYTES",
    }
    values.update(overrides)
    return handoff.PrivateInputSpec(**values)


def _registered(tmp_path: Path) -> tuple[Any, bytes, Path]:
    value = b"synthetic-private-input\n"
    source = tmp_path / "owner-input.bin"
    source.write_bytes(value)
    root = tmp_path / ".private-handoff"
    custodian = handoff.PrivateInputCustodian(root)
    custodian.register_owner_input(_spec(value), source)
    return custodian, value, root


def test_owner_principal_terra_handoff_is_exact_and_cleanup_is_verified(tmp_path: Path) -> None:
    custodian, value, root = _registered(tmp_path)
    receipt = custodian.create_handoff(
        input_id="SYNTHETIC_REPORT",
        task_id="TASK_A",
        agent_role="pm_terra_high_worker",
        operation="READ_EXACT_BYTES",
    )
    assert receipt.digest == _digest(value)
    assert receipt.byte_size == len(value)
    assert receipt.handoff_status == "HANDOFF_COMPLETE"
    assert (
        custodian.read_for_agent(
            input_id="SYNTHETIC_REPORT",
            task_id="TASK_A",
            agent_role="pm_terra_high_worker",
            operation="READ_EXACT_BYTES",
        )
        == value
    )
    assert (
        custodian.cleanup(
            input_id="SYNTHETIC_REPORT",
            task_id="TASK_A",
            agent_role="pm_terra_high_worker",
        )
        == "CLEANUP_COMPLETE"
    )
    assert not list(root.glob("*"))


@pytest.mark.parametrize(
    ("task_id", "agent_role", "outcome"),
    (
        ("TASK_A", "pm_backend_worker", "PRIVATE_INPUT_HANDOFF_DENIED"),
        ("TASK_B", "pm_terra_high_worker", "PRIVATE_INPUT_HANDOFF_DENIED"),
    ),
)
def test_sibling_and_cross_task_handoff_are_denied(
    tmp_path: Path, task_id: str, agent_role: str, outcome: str
) -> None:
    custodian, _, _ = _registered(tmp_path)
    with pytest.raises(handoff.PrivateInputError) as error:
        custodian.create_handoff(
            input_id="SYNTHETIC_REPORT",
            task_id=task_id,
            agent_role=agent_role,
            operation="READ_EXACT_BYTES",
        )
    assert error.value.outcome.value == outcome


def test_authorized_handoff_cannot_be_reused_by_task_b(tmp_path: Path) -> None:
    custodian, _, _ = _registered(tmp_path)
    custodian.create_handoff(
        input_id="SYNTHETIC_REPORT",
        task_id="TASK_A",
        agent_role="pm_terra_high_worker",
        operation="READ_EXACT_BYTES",
    )
    with pytest.raises(handoff.PrivateInputError) as error:
        custodian.read_for_agent(
            input_id="SYNTHETIC_REPORT",
            task_id="TASK_B",
            agent_role="pm_terra_high_worker",
            operation="READ_EXACT_BYTES",
        )
    assert error.value.outcome.value == "PRIVATE_INPUT_HANDOFF_DENIED"


def test_missing_input_requires_owner_action_without_path_discovery(tmp_path: Path) -> None:
    custodian = handoff.PrivateInputCustodian(tmp_path / ".private-handoff")
    with pytest.raises(handoff.PrivateInputError) as error:
        custodian.create_handoff(
            input_id="MISSING_INPUT",
            task_id="TASK_A",
            agent_role="pm_terra_high_worker",
            operation="READ_EXACT_BYTES",
        )
    assert error.value.outcome.value == "OWNER_ACTION_REQUIRED"


def test_missing_source_and_digest_mismatch_fail_closed(tmp_path: Path) -> None:
    custodian = handoff.PrivateInputCustodian(tmp_path / ".private-handoff")
    with pytest.raises(handoff.PrivateInputError) as missing:
        custodian.register_owner_input(_spec(b"expected"), tmp_path / "absent.bin")
    assert missing.value.outcome.value == "OWNER_ACTION_REQUIRED"
    source = tmp_path / "owner-input.bin"
    source.write_bytes(b"actual")
    with pytest.raises(handoff.PrivateInputError) as mismatch:
        custodian.register_owner_input(_spec(b"expected"), source)
    assert mismatch.value.outcome.value == "PRIVATE_INPUT_VALIDATION_FAILED"


@pytest.mark.parametrize(
    "classification",
    (
        "SECRET_CREDENTIAL",
        "REAL_USER_SENSITIVE_INPUT",
    ),
)
def test_secret_and_real_user_input_file_handoff_are_denied(
    tmp_path: Path, classification: str
) -> None:
    value = b"synthetic-placeholder"
    source = tmp_path / "owner-input.bin"
    source.write_bytes(value)
    custodian = handoff.PrivateInputCustodian(tmp_path / ".private-handoff")
    with pytest.raises(handoff.PrivateInputError) as error:
        custodian.register_owner_input(
            _spec(value, classification=handoff.InputClassification(classification)), source
        )
    assert error.value.outcome.value == "PRIVATE_INPUT_HANDOFF_DENIED"


def test_repository_handoff_namespace_is_ignored_and_absent_from_workflows() -> None:
    assert ".private-handoff/" in (_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for workflow in (_ROOT / ".github/workflows").glob("*.yml"):
        assert ".private-handoff" not in workflow.read_text(encoding="utf-8")
    for workflow in (_ROOT / ".github/workflows").glob("*.yaml"):
        assert ".private-handoff" not in workflow.read_text(encoding="utf-8")


def test_governance_freezes_private_output_recovery_and_principal_authority() -> None:
    authority = "\n".join(
        (
            (_ROOT / "AGENTS.md").read_text(encoding="utf-8"),
            (_ROOT / "docs/adr/ADR-049-principal-managed-private-input-delegation.md").read_text(
                encoding="utf-8"
            ),
            (_ROOT / "docs/operations/PRIVATE_INPUT_DELEGATION_PROTOCOL.md").read_text(
                encoding="utf-8"
            ),
        )
    )
    for invariant in (
        "PRIVATE_INPUT_OWNER_HANDOFF_ONCE",
        "SUBAGENT_NO_PRIVATE_DISCOVERY",
        "PRIVATE_INPUT_NON_PROPAGATION",
        "PRINCIPAL_RETAINS_AUTHORITY",
        "PRIVATE_OUTPUT_LOCATION_MUST_BE_RECOVERABLE",
        "SUBAGENT_HANDOFF_IS_PRINCIPAL_RESPONSIBILITY",
        "PRIVATE_BYTES_STAY_OUT_OF_GIT",
        "EVIDENCE_LOCATION_LOST",
    ):
        assert invariant in authority


def test_public_exceptions_never_disclose_source_path_or_payload(tmp_path: Path) -> None:
    private_name = "do-not-disclose-private-name.bin"
    custodian = handoff.PrivateInputCustodian(tmp_path / ".private-handoff")
    with pytest.raises(handoff.PrivateInputError) as error:
        custodian.register_owner_input(_spec(b"expected"), tmp_path / private_name)
    rendered = str(error.value)
    assert private_name not in rendered
    assert "expected" not in rendered
    assert rendered == "OWNER_ACTION_REQUIRED"
