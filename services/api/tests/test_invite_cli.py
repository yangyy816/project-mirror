from __future__ import annotations

import io
import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from mirror_api.models import AuditLog, InviteCode
from mirror_api.scripts import manage_invites
from mirror_api.scripts.manage_invites import (
    CreatedInvite,
    InviteManagementError,
    audit_invite,
    create_invite,
    database_url_from_environment,
    disable_invite,
    invite_status,
    parse_expiry,
    run,
    validate_execution_target,
    write_created_invite,
)
from mirror_api.security import hmac_digest

TEST_HMAC_KEYRING = {"test-v1": "t" * 64}
TEST_HMAC_KID = "test-v1"


def test_cli_target_requires_explicit_nonproduction_postgresql() -> None:
    with pytest.raises(InviteManagementError, match="environment variable is missing"):
        validate_execution_target(database_url=None, environment="test")
    with pytest.raises(InviteManagementError, match="PostgreSQL"):
        validate_execution_target(database_url="sqlite://", environment="test")
    with pytest.raises(InviteManagementError, match="explicit supported environment"):
        validate_execution_target(database_url="postgresql://test", environment=None)
    with pytest.raises(InviteManagementError, match="not authorized"):
        validate_execution_target(database_url="postgresql://test", environment="production")
    with pytest.raises(SystemExit):
        run(["create"])
    with pytest.raises(InviteManagementError, match="not authorized"):
        run(["--environment", "production", "create"])


def test_cli_reads_database_url_only_from_safe_named_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_INVITE_DATABASE_URL", raising=False)
    with pytest.raises(InviteManagementError, match="environment variable is missing"):
        run(["--database-env", "TEST_INVITE_DATABASE_URL", "--environment", "test", "create"])
    with pytest.raises(InviteManagementError, match="name is invalid"):
        database_url_from_environment("not-safe")


def test_create_output_emits_plaintext_code_exactly_once() -> None:
    code = "invite-code-sentinel"
    output = io.StringIO()
    write_created_invite(
        CreatedInvite(invite_id="a" * 32, code=code, max_uses=1, expires_at=None), output=output
    )
    assert output.getvalue().count(code) == 1
    assert output.getvalue().count("a" * 32) == 1


def test_expiry_parser_rejects_unsafe_timestamps() -> None:
    with pytest.raises(InviteManagementError, match="timezone"):
        parse_expiry("2030-01-01T00:00:00")
    with pytest.raises(InviteManagementError, match="future"):
        parse_expiry("2000-01-01T00:00:00Z")


class CommitFailure:
    def __enter__(self) -> Session:
        return Session()

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        del exc_type, exc_value, traceback
        raise RuntimeError("commit failed")


class FailingSessionFactory:
    def begin(self) -> CommitFailure:
        return CommitFailure()


def test_create_does_not_emit_code_if_transaction_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code = "commit-failure-code-sentinel"
    monkeypatch.setattr(
        manage_invites,
        "create_invite",
        lambda *args, **kwargs: CreatedInvite("a" * 32, code, 1, None),
    )
    output = io.StringIO()
    with pytest.raises(RuntimeError, match="commit failed"):
        manage_invites._create_and_emit_after_commit(
            FailingSessionFactory(),
            hmac_keyring=TEST_HMAC_KEYRING,
            active_key_id=TEST_HMAC_KID,
            max_uses=1,
            expires_at=None,
            output=output,
        )
    assert code not in output.getvalue()


def test_disable_does_not_emit_success_if_transaction_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invite_id = "b" * 32
    monkeypatch.setattr(manage_invites, "disable_invite", lambda *args, **kwargs: True)
    output = io.StringIO()
    with pytest.raises(RuntimeError, match="commit failed"):
        manage_invites._disable_and_emit_after_commit(
            FailingSessionFactory(),
            invite_id=invite_id,
            output=output,
        )
    assert output.getvalue() == ""


@pytest.mark.integration
def test_invite_create_disable_and_audit_use_real_postgresql() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    created = None
    try:
        with Session(engine) as session:
            with session.begin():
                created = create_invite(
                    session,
                    hmac_keyring=TEST_HMAC_KEYRING,
                    active_key_id=TEST_HMAC_KID,
                    max_uses=2,
                    expires_at=expires_at,
                )
            assert created is not None
            with session.begin():
                invite = session.get(InviteCode, created.invite_id)
                assert invite is not None
                assert "code" not in InviteCode.__table__.columns
                assert invite.code_hash == hmac_digest(
                    created.code,
                    purpose="invite",
                    keyring=TEST_HMAC_KEYRING,
                    key_id=TEST_HMAC_KID,
                )
                assert invite_status(invite) == "active"
                assert invite_status(invite, now=expires_at + timedelta(seconds=1)) == "expired"
                assert disable_invite(session, invite_id=created.invite_id)
            with session.begin():
                audit = audit_invite(session, invite_id=created.invite_id)
                assert audit.status == "disabled"
                assert {entry.split("@", 1)[0] for entry in audit.actions} == {
                    "invite_created",
                    "invite_disabled",
                }
                rows = session.scalars(
                    select(AuditLog).where(AuditLog.target_id == created.invite_id)
                ).all()
                assert all(created.code not in str(row.metadata_json) for row in rows)
    finally:
        if created is not None:
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM audit_logs WHERE target_id = :invite_id"),
                    {"invite_id": created.invite_id},
                )
                connection.execute(
                    text("DELETE FROM invite_codes WHERE id = :invite_id"),
                    {"invite_id": created.invite_id},
                )
        engine.dispose()
