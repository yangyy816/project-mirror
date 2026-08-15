from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import String, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from mirror_api.models import (
    AgeAssuranceRecord,
    IdempotencyRecord,
    InviteCode,
    InviteRedemption,
    PhoneVerificationChallenge,
    PolicyAcceptanceRecord,
    User,
    UserSession,
    new_id,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                "invite_codes CASCADE"
            )
        )
    with Session(engine) as db_session:
        yield db_session
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                "invite_codes CASCADE"
            )
        )
    engine.dispose()


def make_user(seed: str) -> User:
    return User(id=new_id(), phone_hash=seed * 128)


def test_hmac_columns_allow_keyed_digests() -> None:
    for column in (
        User.__table__.c.phone_hash,
        PhoneVerificationChallenge.__table__.c.phone_hash,
        IdempotencyRecord.__table__.c.key_hash,
    ):
        assert isinstance(column.type, String)
        assert column.type.length == 128


def test_auth_evidence_is_append_only_and_minimized(session: Session) -> None:
    user = make_user("a")
    invite = InviteCode(id=new_id(), code_hash="b" * 128)
    challenge = PhoneVerificationChallenge(
        id=new_id(),
        phone_hash=user.phone_hash,
        code_hash="c" * 128,
        invite_code_id=invite.id,
        purpose="authenticate",
        request_id="req-auth-challenge",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    redemption = InviteRedemption(
        id=new_id(),
        invite_code_id=invite.id,
        user_id=user.id,
        challenge_id=challenge.id,
        request_id="req-auth-redemption",
    )
    age = AgeAssuranceRecord(
        id=new_id(),
        user_id=user.id,
        provider="deterministic_fixture",
        provider_reference_hash="d" * 128,
        result="verified",
        provider_version="fixture-v1",
        policy_version="age-policy-v1",
        verified_at=datetime.now(UTC),
        request_id="req-age",
    )
    policy = PolicyAcceptanceRecord(
        id=new_id(),
        user_id=user.id,
        document_code="terms",
        document_version="v1",
        document_digest="e" * 64,
        source="web_beta",
        request_id="req-policy",
    )
    session.add_all([user, invite])
    session.commit()
    session.add(challenge)
    session.commit()
    session.add_all([redemption, age, policy])
    session.commit()

    for record_id, update_statement, delete_statement in (
        (
            redemption.id,
            text("UPDATE invite_redemptions SET request_id='changed' WHERE id=:id"),
            text("DELETE FROM invite_redemptions WHERE id=:id"),
        ),
        (
            age.id,
            text("UPDATE age_assurance_records SET request_id='changed' WHERE id=:id"),
            text("DELETE FROM age_assurance_records WHERE id=:id"),
        ),
        (
            policy.id,
            text("UPDATE policy_acceptance_records SET request_id='changed' WHERE id=:id"),
            text("DELETE FROM policy_acceptance_records WHERE id=:id"),
        ),
    ):
        with pytest.raises(DBAPIError, match="immutable record"):
            session.execute(update_statement, {"id": record_id})
        session.rollback()
        with pytest.raises(DBAPIError, match="immutable record"):
            session.execute(delete_statement, {"id": record_id})
        session.rollback()

    for model in (AgeAssuranceRecord, PolicyAcceptanceRecord):
        field_names = set(model.__table__.columns.keys())
        assert not field_names.intersection(
            {"date_of_birth", "birthdate", "dob", "exact_age", "raw_payload", "credential"}
        )


def test_auth_constraints_lineage_and_runtime_updates(session: Session) -> None:
    user = make_user("f")
    expires_at = datetime.now(UTC) + timedelta(days=30)
    parent = UserSession(
        id=new_id(),
        user_id=user.id,
        family_id=new_id(),
        token_id=new_id(),
        refresh_token_hash="g" * 128,
        refresh_key_id="refresh-v1",
        expires_at=expires_at,
    )
    child = UserSession(
        id=new_id(),
        user_id=user.id,
        family_id=parent.family_id,
        token_id=new_id(),
        refresh_token_hash="h" * 128,
        refresh_key_id="refresh-v1",
        rotated_from_id=parent.id,
        expires_at=expires_at,
    )
    idempotency = IdempotencyRecord(
        id=new_id(),
        actor_key="actor-hmac",
        scope="auth.session.create",
        key_hash="kid:" + "i" * 64,
        request_fingerprint="j" * 64,
        expires_at=expires_at,
    )
    session.add(user)
    session.commit()
    session.add(parent)
    session.commit()
    session.add(child)
    session.commit()
    parent.replaced_by_id = child.id
    session.commit()
    session.add(idempotency)
    session.commit()

    parent.consumed_at = datetime.now(UTC)
    parent.revoked_at = datetime.now(UTC)
    parent.revocation_reason = "rotation"
    child.last_seen_at = datetime.now(UTC)
    idempotency.state = "completed"
    idempotency.completed_at = datetime.now(UTC)
    session.commit()

    duplicate_child = UserSession(
        id=new_id(),
        user_id=user.id,
        family_id=parent.family_id,
        token_id=new_id(),
        refresh_token_hash="k" * 128,
        refresh_key_id="refresh-v1",
        rotated_from_id=parent.id,
        expires_at=expires_at,
    )
    session.add(duplicate_child)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    with pytest.raises(IntegrityError):
        session.execute(
            text("UPDATE user_sessions SET rotated_from_id=id WHERE id=:id"), {"id": child.id}
        )
    session.rollback()

    first_invite = InviteCode(id=new_id(), code_hash="l" * 128)
    session.add(first_invite)
    session.commit()
    first_challenge = PhoneVerificationChallenge(
        id=new_id(),
        phone_hash=user.phone_hash,
        code_hash="m" * 128,
        invite_code_id=first_invite.id,
        purpose="authenticate",
        request_id="req-first-challenge",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    session.add(first_challenge)
    session.commit()
    session.add(
        InviteRedemption(
            id=new_id(),
            invite_code_id=first_invite.id,
            user_id=user.id,
            challenge_id=first_challenge.id,
            request_id="req-first-redemption",
        )
    )
    session.commit()

    second_challenge = PhoneVerificationChallenge(
        id=new_id(),
        phone_hash=user.phone_hash,
        code_hash="n" * 128,
        purpose="authenticate",
        request_id="req-second-challenge",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    second_invite = InviteCode(id=new_id(), code_hash="o" * 128)
    session.add_all([second_challenge, second_invite])
    session.commit()
    session.add(
        InviteRedemption(
            id=new_id(),
            invite_code_id=second_invite.id,
            user_id=user.id,
            challenge_id=second_challenge.id,
            request_id="req-duplicate-redemption",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    for statement in (
        text("UPDATE idempotency_records SET state='unknown' WHERE id=:id"),
        text("UPDATE idempotency_records SET completed_at=NULL WHERE id=:id"),
        text("UPDATE idempotency_records SET state='failed', completed_at=now() WHERE id=:id"),
    ):
        with pytest.raises(IntegrityError):
            session.execute(statement, {"id": idempotency.id})
        session.rollback()

    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO age_assurance_records "
                "(id, user_id, provider, provider_reference_hash, result, provider_version, "
                "policy_version, verified_at, request_id, created_at) "
                "VALUES (:id, :user_id, 'fixture', 'l', 'invalid', 'v1', 'p1', now(), 'req', now())"
            ),
            {"id": new_id(), "user_id": user.id},
        )
    session.rollback()


def test_identity_migration_backfills_legacy_phase0_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")

    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.downgrade(config, "0001_phase0")

    user_id = new_id()
    challenge_id = new_id()
    session_id = new_id()
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                "invite_codes CASCADE"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, phone_hash, status, age_confirmed_at, created_at, updated_at) "
                "VALUES (:id, :phone_hash, 'pending', NULL, now(), now())"
            ),
            {"id": user_id, "phone_hash": "legacy-phone-hmac"},
        )
        connection.execute(
            text(
                "INSERT INTO phone_verification_challenges "
                "(id, phone_hash, code_hash, provider_message_id, attempts, expires_at, "
                "consumed_at, created_at) VALUES "
                "(:id, :phone_hash, :code_hash, NULL, 0, now() + interval '5 minutes', NULL, now())"
            ),
            {
                "id": challenge_id,
                "phone_hash": "legacy-phone-hmac",
                "code_hash": "legacy-code-hmac",
            },
        )
        connection.execute(
            text(
                "INSERT INTO user_sessions "
                "(id, user_id, refresh_token_hash, expires_at, revoked_at, created_at) "
                "VALUES (:id, :user_id, :refresh_hash, now() + interval '30 days', NULL, now())"
            ),
            {"id": session_id, "user_id": user_id, "refresh_hash": "legacy-refresh-hmac"},
        )
        connection.execute(
            text(
                "INSERT INTO idempotency_records "
                "(id, user_id, actor_key, scope, key_hash, request_fingerprint, response_status, "
                "response_reference, expires_at, created_at) "
                "VALUES (:id, NULL, 'legacy-actor', 'legacy.scope', :key_hash, :fingerprint, "
                "NULL, NULL, now() + interval '1 day', now())"
            ),
            {"id": new_id(), "key_hash": "legacy-key-hmac", "fingerprint": "legacy-fingerprint"},
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        challenge = (
            connection.execute(
                text("SELECT purpose, request_id FROM phone_verification_challenges WHERE id=:id"),
                {"id": challenge_id},
            )
            .mappings()
            .one()
        )
        upgraded_session = (
            connection.execute(
                text("SELECT family_id, token_id, refresh_key_id FROM user_sessions WHERE id=:id"),
                {"id": session_id},
            )
            .mappings()
            .one()
        )
        idempotency = (
            connection.execute(
                text(
                    "SELECT state, completed_at FROM idempotency_records WHERE scope='legacy.scope'"
                )
            )
            .mappings()
            .one()
        )

    assert challenge == {"purpose": "legacy-phase0", "request_id": "legacy-phase0"}
    assert upgraded_session == {
        "family_id": session_id,
        "token_id": session_id,
        "refresh_key_id": "legacy-phase0",
    }
    assert idempotency == {"state": "in_progress", "completed_at": None}
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE idempotency_records, phone_verification_challenges, users, "
                "invite_codes CASCADE"
            )
        )
    engine.dispose()
