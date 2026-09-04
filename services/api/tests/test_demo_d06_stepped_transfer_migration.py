from __future__ import annotations

import os
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _build_demo_row,
    _insert_full_demo_graph,
    _truncate_demo_authority,
)

from mirror_api.demo_models import DemoSelfTransferRun

pytestmark = pytest.mark.integration

_HEAD = "demo_0019_d06_stepped_transfer"
_PREDECESSOR = "demo_0018_d03_pose_evidence"
_CONSTRAINT_NAME = "ck_demo_self_transfer_runs_schema_version_shape"
_V1 = "mirror.demo/DemoSelfTransferRun/v1"
_V2 = "mirror.demo/DemoSelfTransferRun/v2"


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with Session(engine) as db_session:
        _truncate_demo_authority(db_session)
        yield db_session
        db_session.rollback()
        _truncate_demo_authority(db_session)
    engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _constraint_sql(session: Session) -> str:
    value = session.scalar(
        text(
            "SELECT pg_get_constraintdef(constraint_row.oid, true) "
            "FROM pg_constraint AS constraint_row "
            "JOIN pg_class AS table_row ON table_row.oid = constraint_row.conrelid "
            "WHERE table_row.relname = 'demo_self_transfer_runs' "
            "AND constraint_row.conname = :constraint_name"
        ),
        {"constraint_name": _CONSTRAINT_NAME},
    )
    assert isinstance(value, str)
    return value


def _row_json(session: Session, run_id: str) -> str:
    value = session.scalar(
        text(
            "SELECT to_jsonb(authority_row)::text FROM "
            "(SELECT * FROM demo_self_transfer_runs WHERE id = :run_id) "
            "AS authority_row"
        ),
        {"run_id": run_id},
    )
    assert isinstance(value, str)
    return value


def _normalized_constraint_sql(value: str) -> str:
    return re.sub(r"[()\s]", "", value.replace("::character varying", "").replace("::text", ""))


def _assert_v1_v2_constraint(session: Session) -> None:
    normalized = _normalized_constraint_sql(_constraint_sql(session))
    assert normalized in {
        "CHECKschema_versionIN'mirror.demo/DemoSelfTransferRun/v1','mirror.demo/DemoSelfTransferRun/v2'",
        "CHECKschema_version=ANYARRAY['mirror.demo/DemoSelfTransferRun/v1','mirror.demo/DemoSelfTransferRun/v2'][]",
    }


def _assert_v1_only_constraint(session: Session) -> None:
    normalized = _normalized_constraint_sql(_constraint_sql(session))
    assert normalized == "CHECKschema_version~'^mirror[.]demo/[A-Za-z0-9]+/v1$'"


def _new_request(graph: dict[str, object], *, schema_version: str) -> DemoSelfTransferRun:
    transfer_request = graph["transfer_request"]
    assert isinstance(transfer_request, DemoSelfTransferRun)
    return _build_demo_row(
        DemoSelfTransferRun,
        authority_schema_version=schema_version,
        demo_actor_id=transfer_request.demo_actor_id,
        demo_session_id=transfer_request.demo_session_id,
        desired_delta_profile_id=transfer_request.desired_delta_profile_id,
        record_kind="REQUEST",
        request_run_id=None,
        demo_job_binding_id=None,
        source_asset_id=transfer_request.source_asset_id,
        result_asset_id=None,
        requested_delta=dict(transfer_request.requested_delta),
        measured_delta=None,
        non_target_drift=None,
        verifier_digest=None,
        user_outcome=None,
    )


def test_d06_schema_version_upgrade_and_downgrade_lifecycle(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    config = _alembic_config(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    session.close()
    command.downgrade(config, _PREDECESSOR)

    engine = create_engine(database_url)
    try:
        with Session(engine) as legacy:
            graph = _insert_full_demo_graph(legacy)
            transfer_request = graph["transfer_request"]
            assert isinstance(transfer_request, DemoSelfTransferRun)
            v1_before = _row_json(legacy, transfer_request.id)

        command.upgrade(config, _HEAD)
        with Session(engine) as upgraded:
            _assert_v1_v2_constraint(upgraded)
            assert _row_json(upgraded, transfer_request.id) == v1_before

            upgraded.add(_new_request(graph, schema_version=_V2))
            upgraded.commit()

            unknown_row = _new_request(graph, schema_version="mirror.demo/DemoSelfTransferRun/v999")
            upgraded.add(unknown_row)
            with pytest.raises(DBAPIError, match=_CONSTRAINT_NAME):
                upgraded.commit()
            upgraded.rollback()

        with pytest.raises(DBAPIError, match="D06 stepped-transfer downgrade blocked"):
            command.downgrade(config, _PREDECESSOR)

        with Session(engine) as after_failed_downgrade:
            assert (
                after_failed_downgrade.scalar(text("SELECT version_num FROM alembic_version"))
                == _HEAD
            )
            _assert_v1_v2_constraint(after_failed_downgrade)
            # Authority rows are append-only.  A clean rollback test therefore
            # clears its isolated fixture with PostgreSQL TRUNCATE rather than
            # disabling the immutable-authority guard or mutating a v2 row.
            after_failed_downgrade.execute(text("TRUNCATE TABLE demo_self_transfer_runs CASCADE"))
            after_failed_downgrade.commit()

        command.downgrade(config, _PREDECESSOR)
        with Session(engine) as downgraded:
            assert (
                downgraded.scalar(text("SELECT version_num FROM alembic_version")) == _PREDECESSOR
            )
            _assert_v1_only_constraint(downgraded)
            # The pre-0019 constraint is the shared Demo v1 shape, not a
            # narrower per-model equality check.
            downgraded.add(_new_request(graph, schema_version="mirror.demo/OtherType/v1"))
            downgraded.commit()
            # Restore an empty isolated fixture before re-applying the new
            # closed v1/v2 set, which intentionally excludes OtherType/v1.
            downgraded.execute(text("TRUNCATE TABLE demo_self_transfer_runs CASCADE"))
            downgraded.commit()

        command.upgrade(config, _HEAD)
        with Session(engine) as reupgraded:
            _assert_v1_v2_constraint(reupgraded)
            assert reupgraded.scalar(text("SELECT version_num FROM alembic_version")) == _HEAD
    finally:
        command.upgrade(config, _HEAD)
        engine.dispose()
