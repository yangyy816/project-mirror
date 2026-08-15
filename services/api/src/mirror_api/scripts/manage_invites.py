from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, TextIO, cast

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from mirror_api.config import Environment, Settings
from mirror_api.models import AuditLog, InviteCode, new_id
from mirror_api.security import hmac_digest

INVITE_ID_LENGTH = 32
ENVIRONMENT_VARIABLE_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
SYSTEM_ACTOR_TYPE = "system"
INVITE_TARGET_TYPE = "invite_code"


class InviteManagementError(ValueError):
    """A safe management error that never contains an invite code."""


class TransactionalSessionFactory(Protocol):
    def begin(self) -> AbstractContextManager[Session]: ...


@dataclass(frozen=True)
class CreatedInvite:
    invite_id: str
    code: str
    max_uses: int
    expires_at: datetime | None


@dataclass(frozen=True)
class InviteAuditView:
    invite_id: str
    status: str
    max_uses: int
    use_count: int
    expires_at: datetime | None
    disabled_at: datetime | None
    actions: tuple[str, ...]


def generate_invite_code() -> str:
    """Generate a high-entropy code whose plaintext is never persisted."""
    return secrets.token_urlsafe(32)


def parse_expiry(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InviteManagementError("expiry must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise InviteManagementError("expiry must include a timezone")
    expiry = parsed.astimezone(UTC)
    if expiry <= datetime.now(UTC):
        raise InviteManagementError("expiry must be in the future")
    return expiry


def _validate_invite_id(invite_id: str) -> None:
    if len(invite_id) != INVITE_ID_LENGTH or any(
        character not in "0123456789abcdef" for character in invite_id
    ):
        raise InviteManagementError("invite id is invalid")


def _validate_create_inputs(max_uses: int, expires_at: datetime | None) -> None:
    if max_uses < 1:
        raise InviteManagementError("max uses must be positive")
    if expires_at is not None and (expires_at.tzinfo is None or expires_at <= datetime.now(UTC)):
        raise InviteManagementError("expiry must be in the future and timezone-aware")


def _system_audit(
    *, session: Session, action: str, invite_id: str, metadata: dict[str, object]
) -> None:
    session.add(
        AuditLog(
            actor_type=SYSTEM_ACTOR_TYPE,
            actor_id=None,
            action=action,
            target_type=INVITE_TARGET_TYPE,
            target_id=invite_id,
            request_id=f"invite-cli-{new_id()}",
            metadata_json=metadata,
        )
    )


def create_invite(
    session: Session,
    *,
    hmac_keyring: Mapping[str, str],
    active_key_id: str,
    max_uses: int,
    expires_at: datetime | None,
) -> CreatedInvite:
    _validate_create_inputs(max_uses, expires_at)
    code = generate_invite_code()
    invite = InviteCode(
        code_hash=hmac_digest(
            code,
            purpose="invite",
            keyring=hmac_keyring,
            key_id=active_key_id,
        ),
        max_uses=max_uses,
        expires_at=expires_at,
    )
    session.add(invite)
    session.flush()
    _system_audit(
        session=session,
        action="invite_created",
        invite_id=invite.id,
        metadata={
            "max_uses": max_uses,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )
    return CreatedInvite(
        invite_id=invite.id,
        code=code,
        max_uses=max_uses,
        expires_at=expires_at,
    )


def disable_invite(session: Session, *, invite_id: str) -> bool:
    _validate_invite_id(invite_id)
    invite = session.get(InviteCode, invite_id)
    if invite is None:
        raise InviteManagementError("invite was not found")
    if invite.disabled_at is not None:
        return False
    invite.disabled_at = datetime.now(UTC)
    _system_audit(
        session=session,
        action="invite_disabled",
        invite_id=invite.id,
        metadata={},
    )
    return True


def invite_status(invite: InviteCode, *, now: datetime | None = None) -> str:
    timestamp = now or datetime.now(UTC)
    if invite.disabled_at is not None:
        return "disabled"
    if invite.expires_at is not None and invite.expires_at <= timestamp:
        return "expired"
    if invite.use_count >= invite.max_uses:
        return "exhausted"
    return "active"


def audit_invite(session: Session, *, invite_id: str) -> InviteAuditView:
    _validate_invite_id(invite_id)
    invite = session.get(InviteCode, invite_id)
    if invite is None:
        raise InviteManagementError("invite was not found")
    audit_rows = session.scalars(
        select(AuditLog)
        .where(AuditLog.target_type == INVITE_TARGET_TYPE, AuditLog.target_id == invite_id)
        .order_by(AuditLog.occurred_at)
    )
    actions = tuple(f"{row.action}@{row.occurred_at.isoformat()}" for row in audit_rows)
    return InviteAuditView(
        invite_id=invite.id,
        status=invite_status(invite),
        max_uses=invite.max_uses,
        use_count=invite.use_count,
        expires_at=invite.expires_at,
        disabled_at=invite.disabled_at,
        actions=actions,
    )


def validate_environment(environment: str | None) -> Environment:
    if environment not in {"development", "test", "ci", "production"}:
        raise InviteManagementError("an explicit supported environment is required")
    if environment == "production":
        raise InviteManagementError("production invite CLI execution is not authorized")
    return cast(Environment, environment)


def database_url_from_environment(name: str) -> str:
    if not ENVIRONMENT_VARIABLE_NAME.fullmatch(name):
        raise InviteManagementError("database environment variable name is invalid")
    database_url = os.getenv(name)
    if not database_url:
        raise InviteManagementError("database URL environment variable is missing")
    return database_url


def validate_execution_target(*, database_url: str | None, environment: str | None) -> Environment:
    resolved_environment = validate_environment(environment)
    if not database_url:
        raise InviteManagementError("database URL environment variable is missing")
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise InviteManagementError("a PostgreSQL database URL is required")
    return resolved_environment


def write_created_invite(result: CreatedInvite, *, output: TextIO) -> None:
    output.write(f"invite_id={result.invite_id}\n")
    output.write(f"invite_code={result.code}\n")


def write_audit(result: InviteAuditView, *, output: TextIO) -> None:
    output.write(f"invite_id={result.invite_id}\n")
    output.write(f"status={result.status}\n")
    output.write(f"max_uses={result.max_uses}\n")
    output.write(f"use_count={result.use_count}\n")
    output.write(f"expires_at={result.expires_at.isoformat() if result.expires_at else ''}\n")
    output.write(f"disabled_at={result.disabled_at.isoformat() if result.disabled_at else ''}\n")
    for action in result.actions:
        output.write(f"audit={action}\n")


def _create_and_emit_after_commit(
    session_factory: TransactionalSessionFactory,
    *,
    hmac_keyring: Mapping[str, str],
    active_key_id: str,
    max_uses: int,
    expires_at: datetime | None,
    output: TextIO,
) -> None:
    with session_factory.begin() as session:
        created = create_invite(
            session,
            hmac_keyring=hmac_keyring,
            active_key_id=active_key_id,
            max_uses=max_uses,
            expires_at=expires_at,
        )
    write_created_invite(created, output=output)


def _disable_and_emit_after_commit(
    session_factory: TransactionalSessionFactory,
    *,
    invite_id: str,
    output: TextIO,
) -> None:
    with session_factory.begin() as session:
        changed = disable_invite(session, invite_id=invite_id)
    output.write(f"invite_id={invite_id}\n")
    output.write(f"disabled={'true' if changed else 'already_disabled'}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline invite management; never reveals stored codes."
    )
    parser.add_argument(
        "--database-env",
        default="DATABASE_URL",
        help="environment variable containing the PostgreSQL URL",
    )
    parser.add_argument(
        "--environment", required=True, choices=("development", "test", "ci", "production")
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--max-uses", type=int, default=1)
    create.add_argument("--expires-at")
    disable = commands.add_parser("disable")
    disable.add_argument("--invite-id", required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("--invite-id", required=True)
    return parser


def run(argv: Sequence[str] | None = None, *, output: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_environment(args.environment)
    database_url = database_url_from_environment(args.database_env)
    environment = validate_execution_target(
        database_url=database_url,
        environment=args.environment,
    )
    settings = Settings(app_env=environment, database_url=database_url)
    engine = create_engine(database_url)
    session_factory = sessionmaker(engine)
    stream = output or sys.stdout
    try:
        if args.command == "create":
            expiry = parse_expiry(args.expires_at) if args.expires_at else None
            _create_and_emit_after_commit(
                session_factory,
                hmac_keyring=settings.auth_hmac_keyring,
                active_key_id=settings.auth_hmac_active_kid,
                max_uses=args.max_uses,
                expires_at=expiry,
                output=stream,
            )
        else:
            if args.command == "disable":
                _disable_and_emit_after_commit(
                    session_factory,
                    invite_id=args.invite_id,
                    output=stream,
                )
            elif args.command == "audit":
                with session_factory.begin() as session:
                    write_audit(audit_invite(session, invite_id=args.invite_id), output=stream)
            else:
                raise AssertionError("argument parser returned an unsupported command")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
