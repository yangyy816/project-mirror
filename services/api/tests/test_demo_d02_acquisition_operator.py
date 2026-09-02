from __future__ import annotations

import base64
import json
import os
from collections.abc import Generator
from io import BytesIO, StringIO
from pathlib import Path
from typing import cast

import pytest
from PIL import Image
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from mirror_api.demo_d02_acquisition_operator import (
    _COMPATIBLE_DATABASE_HEADS,
    D02AcquisitionOperator,
    D02LocalDurableIndex,
    D02OperatorError,
    LocalDurableEntry,
    _checkpoint_lock,
    _require_database_head,
)
from mirror_api.demo_d02_r2_generation_receiver import BoundPngFile
from mirror_api.demo_d02_source_acquisition import DurableCandidateBytes
from mirror_api.demo_models import (
    D02SourceAcquisitionEvent,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
)

pytestmark = pytest.mark.integration


class _MigrationHeadSession:
    def __init__(self, heads: list[str]) -> None:
        self._heads = heads

    def scalars(self, _statement: object) -> list[str]:
        return self._heads


@pytest.mark.parametrize("head", sorted(_COMPATIBLE_DATABASE_HEADS))
def test_database_head_guard_accepts_only_registered_forward_heads(head: str) -> None:
    _require_database_head(cast(Session, _MigrationHeadSession([head])))


@pytest.mark.parametrize(
    "heads",
    (
        [],
        ["demo_0018_unknown"],
        ["demo_0016_d06_ref_profile_queue", "demo_0017_d10_context_queue"],
    ),
)
def test_database_head_guard_rejects_unknown_or_multiple_heads(heads: list[str]) -> None:
    with pytest.raises(D02OperatorError, match="DATABASE_MIGRATION_HEAD_MISMATCH"):
        _require_database_head(cast(Session, _MigrationHeadSession(heads)))


@pytest.fixture
def operator_context(
    tmp_path: Path,
) -> Generator[tuple[D02AcquisitionOperator, sessionmaker[Session], Path]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, "
                "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs CASCADE"
            )
        )
    workspace_root = tmp_path.resolve(strict=True)
    (workspace_root / ".private-handoff").mkdir()
    index = D02LocalDurableIndex(workspace_root=workspace_root)
    yield (
        D02AcquisitionOperator(session_factory=sessions, durable_index=index),
        sessions,
        workspace_root,
    )
    with sessions.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, "
                "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs CASCADE"
            )
        )
    engine.dispose()


def _png_data_url(marker: int = 1) -> str:
    image = Image.new("RGB", (96, 96), (marker, 80, 160))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _result_input(marker: int = 1) -> BytesIO:
    envelope = {"outcome": "RESULT", "result": {"image_url": _png_data_url(marker)}}
    return BytesIO((json.dumps(envelope, separators=(",", ":")) + "\n").encode("utf-8"))


def test_bootstrap_is_exactly_replayable_and_status_is_redacted(
    operator_context: tuple[D02AcquisitionOperator, sessionmaker[Session], Path],
) -> None:
    operator, _, workspace_root = operator_context

    first = operator.bootstrap()
    replay = operator.bootstrap()
    status = operator.status()

    assert first["run_id"] == replay["run_id"] == status["run_id"]
    assert first["cohort_spec_id"] == replay["cohort_spec_id"]
    assert status["provider_calls"] == 0
    assert status["budget"] == "0/50"
    assert status["accepted_sources"] == "0/4"
    checkpoint = json.loads(
        (workspace_root / ".private-handoff" / "D02_CURRENT_CHECKPOINT.json").read_text(
            encoding="utf-8"
        )
    )
    assert checkpoint["authority"] == "LOCAL_AVAILABILITY_INDEX_ONLY"
    assert checkpoint["business_authority"] is False
    assert checkpoint["budget_authority"] is False
    assert checkpoint["entries"] == []


def test_call_session_commits_call_started_before_stdin_and_keeps_locators_private(
    operator_context: tuple[D02AcquisitionOperator, sessionmaker[Session], Path],
) -> None:
    operator, sessions, workspace_root = operator_context
    run_id = str(operator.bootstrap()["run_id"])

    class CommitCheckingInput(BytesIO):
        def readline(self, size: int | None = -1) -> bytes:
            with sessions.begin() as session:
                run = session.get(D02SourceAcquisitionRun, run_id)
                assert run is not None
                assert run.budget_consumed == 1
                assert run.open_call_ordinal == 1
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(D02SourceAcquisitionEvent)
                        .where(D02SourceAcquisitionEvent.event_kind == "CALL_STARTED")
                    )
                    == 1
                )
            return super().readline(size)

    output = StringIO()
    raw = _result_input(4).getvalue()
    result = operator.call_session(
        run_id=run_id,
        input_stream=CommitCheckingInput(raw),
        output=output,
    )

    assert result == 0
    lines = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [line["status"] for line in lines] == ["CALL_STARTED", "CANDIDATE_DURABLE"]
    assert ".private-handoff" not in output.getvalue()
    assert "data:image" not in output.getvalue()
    with sessions.begin() as session:
        run = session.get(D02SourceAcquisitionRun, run_id)
        candidate = session.scalar(select(D02SourceCandidate))
        assert run is not None and run.budget_consumed == 1 and run.run_state == "ACTIVE"
        assert candidate is not None and candidate.candidate_state == "DURABLE"
        assert candidate.durable_primary_sha256 == candidate.durable_backup_sha256
    checkpoint = json.loads(
        (workspace_root / ".private-handoff" / "D02_CURRENT_CHECKPOINT.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(checkpoint["entries"]) == 1
    assert checkpoint["entries"][0]["primary"]["relative_locator"].startswith(
        ".private-handoff/d02-acquisition/objects/"
    )
    assert checkpoint["entries"][0]["backup"] is not None


def test_invalid_result_consumes_ordinal_and_pauses_without_candidate(
    operator_context: tuple[D02AcquisitionOperator, sessionmaker[Session], Path],
) -> None:
    operator, sessions, _ = operator_context
    run_id = str(operator.bootstrap()["run_id"])
    envelope = {
        "outcome": "RESULT",
        "result": {"image_url": "data:image/png;base64,AAAA"},
    }
    input_stream = BytesIO((json.dumps(envelope) + "\n").encode("utf-8"))
    output = StringIO()

    assert operator.call_session(run_id=run_id, input_stream=input_stream, output=output) == 3

    with sessions.begin() as session:
        run = session.get(D02SourceAcquisitionRun, run_id)
        assert run is not None
        assert run.budget_consumed == 1
        assert run.open_call_ordinal is None
        assert run.run_state == "PAUSED_INFRASTRUCTURE"
        assert session.scalar(select(func.count()).select_from(D02SourceCandidate)) == 0
        kinds = list(
            session.scalars(
                select(D02SourceAcquisitionEvent.event_kind).order_by(
                    D02SourceAcquisitionEvent.event_sequence
                )
            )
        )
        assert kinds[-2:] == ["MATERIALIZATION_FAILED", "INFRASTRUCTURE_PAUSED"]


def test_missing_result_line_fails_entire_run_closed(
    operator_context: tuple[D02AcquisitionOperator, sessionmaker[Session], Path],
) -> None:
    operator, sessions, _ = operator_context
    run_id = str(operator.bootstrap()["run_id"])

    with pytest.raises(D02OperatorError, match="PROVIDER_OUTCOME_UNCERTAIN"):
        operator.call_session(run_id=run_id, input_stream=BytesIO(b""), output=StringIO())

    with sessions.begin() as session:
        run = session.get(D02SourceAcquisitionRun, run_id)
        assert run is not None
        assert run.budget_consumed == 1
        assert run.run_state == "FAILED_CLOSED"
        assert run.terminal_reason == "PROVIDER_OUTCOME_UNCERTAIN"


def test_primary_index_transient_failure_retries_same_published_bytes(
    operator_context: tuple[D02AcquisitionOperator, sessionmaker[Session], Path],
) -> None:
    bootstrap_operator, sessions, workspace_root = operator_context
    run_id = str(bootstrap_operator.bootstrap()["run_id"])

    class FailOnceIndex(D02LocalDurableIndex):
        def __init__(self, *, workspace_root: Path) -> None:
            super().__init__(workspace_root=workspace_root)
            self.failed = False

        def record_primary(
            self,
            *,
            candidate: DurableCandidateBytes,
            primary_file: BoundPngFile,
            primary_path: Path,
        ) -> LocalDurableEntry:
            if not self.failed:
                self.failed = True
                raise D02OperatorError("TEST_PRIVATE_INDEX_TRANSIENT")
            return super().record_primary(
                candidate=candidate,
                primary_file=primary_file,
                primary_path=primary_path,
            )

    operator = D02AcquisitionOperator(
        session_factory=sessions,
        durable_index=FailOnceIndex(workspace_root=workspace_root),
    )
    result_line = _result_input(7).getvalue()
    retry_line = b'{"action":"RETRY_PRIMARY_INDEX"}\n'
    output = StringIO()

    assert (
        operator.call_session(
            run_id=run_id,
            input_stream=BytesIO(result_line + retry_line),
            output=output,
        )
        == 0
    )
    statuses = [json.loads(line)["status"] for line in output.getvalue().splitlines()]
    assert statuses == [
        "CALL_STARTED",
        "PRIMARY_PUBLISHED_INDEX_RETRY_REQUIRED",
        "CANDIDATE_DURABLE",
    ]
    with sessions.begin() as session:
        run = session.get(D02SourceAcquisitionRun, run_id)
        assert run is not None and run.budget_consumed == 1
        assert session.scalar(select(func.count()).select_from(D02SourceCandidate)) == 1


def test_checkpoint_lock_rejects_symlink_without_touching_target(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"unchanged")
    link = tmp_path / "checkpoint.lock"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("host does not permit a symlink negative control")

    with pytest.raises(D02OperatorError, match="PRIVATE_INDEX_LOCK_INVALID"):
        with _checkpoint_lock(link):
            pytest.fail("symlink lock unexpectedly acquired")

    assert target.read_bytes() == b"unchanged"


def test_crash_after_primary_publish_recovers_from_preallocated_exact_locator(
    operator_context: tuple[D02AcquisitionOperator, sessionmaker[Session], Path],
) -> None:
    bootstrap_operator, sessions, workspace_root = operator_context
    run_id = str(bootstrap_operator.bootstrap()["run_id"])

    class InterruptAfterPublishIndex(D02LocalDurableIndex):
        def record_primary(
            self,
            *,
            candidate: DurableCandidateBytes,
            primary_file: BoundPngFile,
            primary_path: Path,
        ) -> LocalDurableEntry:
            raise D02OperatorError("TEST_SIMULATED_PROCESS_INTERRUPTION")

    interrupted = D02AcquisitionOperator(
        session_factory=sessions,
        durable_index=InterruptAfterPublishIndex(workspace_root=workspace_root),
    )
    output = StringIO()
    with pytest.raises(D02OperatorError, match="PRIMARY_PUBLISHED_INDEX_RECOVERY_INTERRUPTED"):
        interrupted.call_session(
            run_id=run_id,
            input_stream=_result_input(9),
            output=output,
        )
    lines = [json.loads(line) for line in output.getvalue().splitlines()]
    call_digest = str(lines[0]["call_started_event_digest"])
    assert lines[-1]["status"] == "PRIMARY_PUBLISHED_INDEX_RETRY_REQUIRED"
    with sessions.begin() as session:
        run = session.get(D02SourceAcquisitionRun, run_id)
        assert run is not None and run.open_call_ordinal == 1
        assert run.budget_consumed == 1
        assert session.scalar(select(func.count()).select_from(D02SourceCandidate)) == 0

    recovered = D02AcquisitionOperator(
        session_factory=sessions,
        durable_index=D02LocalDurableIndex(workspace_root=workspace_root),
    ).recover_primary(
        run_id=run_id,
        call_started_event_digest=call_digest,
    )

    assert recovered["status"] == "CANDIDATE_DURABLE"
    with sessions.begin() as session:
        run = session.get(D02SourceAcquisitionRun, run_id)
        candidate = session.scalar(select(D02SourceCandidate))
        assert run is not None and run.budget_consumed == 1 and run.run_state == "ACTIVE"
        assert candidate is not None and candidate.candidate_state == "DURABLE"
