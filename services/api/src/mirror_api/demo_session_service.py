"""Owner-bound Demo bootstrap identities and Sessions.

This service activates the already published synchronous Demo contracts.  It
reads only current D02 generic admission authority and creates an immutable
``DemoSession`` through the existing semantic-idempotency coordinator.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from sqlalchemy import and_, exists, or_, select, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from mirror_api.demo_d02_generic_admission import (
    IDENTITY_SCHEMA as D02_GENERIC_IDENTITY_SCHEMA,
)
from mirror_api.demo_d02_generic_admission import SOURCE_SCHEMA as D02_GENERIC_SOURCE_SCHEMA
from mirror_api.demo_idempotency import (
    DemoIdempotencyAuthorityCorruption,
    DemoIdempotencyInputError,
    DemoIdempotencyPayloadConflict,
    DemoIdempotencyTarget,
    DemoSemanticIdempotencyCoordinator,
    canonical_json_bytes,
    idempotency_key_hash,
)
from mirror_api.demo_models import (
    D02SelectedSourceManifest,
    D02SourceAcquisitionRun,
    DemoActor,
    DemoCommandBinding,
    DemoD02R2SourceAuthority,
    DemoSession,
    DemoSyntheticIdentity,
)
from mirror_api.models import new_id, utcnow

DEMO_SESSION_SCHEMA = "mirror.demo/DemoSession/v1"
DEMO_SESSION_CONFIG_SCHEMA = "mirror.demo/DemoSessionConfig/v1"
DEMO_SESSION_OPERATION = "session.create"
DEMO_SESSION_TTL_SECONDS = 900

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class DemoSessionServiceError(RuntimeError):
    """Base failure for the D11 bootstrap application boundary."""


class DemoSessionInputError(DemoSessionServiceError):
    """The caller supplied a value outside the frozen public contract."""


class DemoSessionActorUnavailable(DemoSessionServiceError):
    """The authenticated actor stopped being current before the transaction."""


class DemoSyntheticIdentityUnavailable(DemoSessionServiceError):
    """The requested identity is not a current admitted D02 synthetic identity."""


class DemoSessionAuthorityUnavailable(DemoSessionServiceError):
    """Persisted D02 or Session authority could not be replayed safely."""


class DemoSessionPayloadConflict(DemoSessionServiceError):
    code = "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True)
class DemoIdentitySnapshot:
    identity_id: str
    canonical_asset_digest: str
    admission_status: Literal["ADMITTED"] = "ADMITTED"


@dataclass(frozen=True)
class DemoSessionSnapshot:
    session_id: str
    synthetic_identity_id: str
    status: Literal["ACTIVE", "CLOSED", "TOMBSTONED"]
    expires_at: datetime


@dataclass(frozen=True)
class DemoSessionCanonicalSource:
    asset_id: str
    asset_sha256: str


@dataclass(frozen=True)
class CreateDemoSession:
    demo_actor_id: str
    synthetic_identity_id: str
    context_seed: str
    idempotency_key: str

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.synthetic_identity_id, "synthetic_identity_id")
        _require_digest(self.context_seed, "context_seed")
        try:
            idempotency_key_hash(self.idempotency_key)
        except DemoIdempotencyInputError as exc:
            raise DemoSessionInputError(str(exc)) from exc


class DemoSessionService:
    """Read current identities and create owner-bound, idempotent Sessions."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = session_factory
        self._now = now
        self._idempotency = DemoSemanticIdempotencyCoordinator(session_factory=session_factory)

    async def list_identities(self, *, demo_actor_id: str) -> tuple[DemoIdentitySnapshot, ...]:
        _require_id(demo_actor_id, "demo_actor_id")
        successor = aliased(DemoSyntheticIdentity)
        try:
            async with self._sessions() as session:
                async with session.begin():
                    await _require_active_actor(session, demo_actor_id)
                    rows = list(
                        await session.scalars(
                            select(DemoSyntheticIdentity)
                            .where(
                                DemoSyntheticIdentity.schema_version == D02_GENERIC_IDENTITY_SCHEMA,
                                DemoSyntheticIdentity.admission_action == "ADMIT",
                                ~exists(
                                    select(1).where(
                                        successor.source_authority_key
                                        == DemoSyntheticIdentity.source_authority_key,
                                        or_(
                                            successor.admission_sequence
                                            > DemoSyntheticIdentity.admission_sequence,
                                            and_(
                                                successor.admission_sequence
                                                == DemoSyntheticIdentity.admission_sequence,
                                                successor.id > DemoSyntheticIdentity.id,
                                            ),
                                        ),
                                    )
                                ),
                            )
                            .order_by(DemoSyntheticIdentity.id)
                        )
                    )
                    snapshots: list[DemoIdentitySnapshot] = []
                    for identity in rows:
                        try:
                            snapshots.append(await _identity_snapshot(session, identity))
                        except DemoSyntheticIdentityUnavailable as exc:
                            raise DemoSessionAuthorityUnavailable(
                                "selected D02 identity stopped being current during replay"
                            ) from exc
                    return tuple(snapshots)
        except DemoSessionServiceError:
            raise
        except (DBAPIError, SQLAlchemyError) as exc:
            raise DemoSessionAuthorityUnavailable(
                "current D02 synthetic identity authority is unavailable"
            ) from exc

    async def create(self, command: CreateDemoSession) -> DemoSessionSnapshot:
        command.validate()

        async def create_target(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[DemoSessionSnapshot]:
            await _require_active_actor(session, command.demo_actor_id)
            identity = await _load_identity(session, command.synthetic_identity_id)
            snapshot = await _identity_snapshot(session, identity)
            now = _normalized_time(self._now())
            expires_at = now + timedelta(seconds=DEMO_SESSION_TTL_SECONDS)
            config = {
                "schema_version": DEMO_SESSION_CONFIG_SCHEMA,
                "synthetic_identity_id": snapshot.identity_id,
            }
            session_id = new_id()
            payload = _session_payload(
                demo_actor_id=command.demo_actor_id,
                config=config,
                context_seed=command.context_seed,
                expires_at=expires_at,
            )
            row = DemoSession(
                id=session_id,
                schema_version=DEMO_SESSION_SCHEMA,
                canonical_payload=payload,
                content_digest=_authority_digest(DEMO_SESSION_SCHEMA, payload),
                created_at=now,
                demo_actor_id=command.demo_actor_id,
                config=config,
                context_seed=command.context_seed,
                expires_at=expires_at,
            )
            session.add(row)
            return DemoIdempotencyTarget(
                value=_session_snapshot(row),
                response_id=row.id,
                demo_session_id=row.id,
            )

        async def load_target(
            session: AsyncSession, binding: DemoCommandBinding
        ) -> DemoIdempotencyTarget[DemoSessionSnapshot] | None:
            row = await session.get(DemoSession, binding.response_id)
            if row is None:
                return None
            await _verify_session(session, row, command.demo_actor_id)
            return DemoIdempotencyTarget(
                value=_session_snapshot(row),
                response_id=row.id,
                demo_session_id=row.id,
            )

        try:
            result = await self._idempotency.execute(
                demo_actor_id=command.demo_actor_id,
                endpoint_operation=DEMO_SESSION_OPERATION,
                idempotency_key=command.idempotency_key,
                semantic_request={
                    "context_seed": command.context_seed,
                    "synthetic_identity_id": command.synthetic_identity_id,
                },
                create_target=create_target,
                load_target=load_target,
                serialize_creation=True,
            )
            return result.value
        except DemoIdempotencyPayloadConflict as exc:
            raise DemoSessionPayloadConflict() from exc
        except DemoIdempotencyInputError as exc:
            raise DemoSessionInputError(str(exc)) from exc
        except DemoSessionServiceError:
            raise
        except (DemoIdempotencyAuthorityCorruption, DBAPIError, SQLAlchemyError) as exc:
            raise DemoSessionAuthorityUnavailable(
                "Demo Session authority transaction failed"
            ) from exc


async def _require_active_actor(session: AsyncSession, actor_id: str) -> DemoActor:
    actor = cast(
        DemoActor | None,
        await session.scalar(
            select(DemoActor)
            .where(DemoActor.id == actor_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ),
    )
    if actor is None or actor.tombstoned_at is not None:
        raise DemoSessionActorUnavailable("Demo actor is not active")
    if actor.actor_kind not in {"LOCAL_SINGLE_USER", "AUTOMATED_TEST"}:
        raise DemoSessionActorUnavailable("Demo actor kind is not supported")
    return actor


async def _load_identity(session: AsyncSession, identity_id: str) -> DemoSyntheticIdentity:
    identity = cast(
        DemoSyntheticIdentity | None,
        await session.scalar(
            select(DemoSyntheticIdentity)
            .where(DemoSyntheticIdentity.id == identity_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ),
    )
    if identity is None:
        raise DemoSyntheticIdentityUnavailable("synthetic identity is unavailable")
    return identity


async def _identity_snapshot(
    session: AsyncSession, identity: DemoSyntheticIdentity
) -> DemoIdentitySnapshot:
    if (
        identity.schema_version != D02_GENERIC_IDENTITY_SCHEMA
        or identity.admission_action != "ADMIT"
        or identity.source_authority_kind != "DEMO_R2_GENERATED_SOURCE"
        or identity.r2_source_authority_record_id is None
        or identity.adult_synthetic_attested is not True
        or _DIGEST.fullmatch(identity.formal_canonical_asset_sha256) is None
    ):
        raise DemoSyntheticIdentityUnavailable("synthetic identity is unavailable")
    successor = aliased(DemoSyntheticIdentity)
    newer_exists = bool(
        await session.scalar(
            select(
                exists().where(
                    successor.source_authority_key == identity.source_authority_key,
                    or_(
                        successor.admission_sequence > identity.admission_sequence,
                        and_(
                            successor.admission_sequence == identity.admission_sequence,
                            successor.id > identity.id,
                        ),
                    ),
                )
            )
        )
    )
    if newer_exists:
        raise DemoSyntheticIdentityUnavailable("synthetic identity is unavailable")
    try:
        await session.execute(
            text("SELECT mirror_demo_require_current_synthetic_admission(:identity_id)"),
            {"identity_id": identity.id},
        )
    except DBAPIError as exc:
        raise DemoSessionAuthorityUnavailable(
            "current synthetic identity authority does not replay"
        ) from exc

    source = await session.get(DemoD02R2SourceAuthority, identity.r2_source_authority_record_id)
    if (
        source is None
        or source.schema_version != D02_GENERIC_SOURCE_SCHEMA
        or source.selected_source_manifest_id is None
        or source.authority_state != "PRINCIPAL_ACCEPTED"
        or source.adult_synthetic_attested is not True
        or source.synthetic_only_attested is not True
        or source.real_person_reference_used is not False
        or source.source_asset_id != identity.formal_canonical_asset_id
        or source.source_asset_sha256 != identity.formal_canonical_asset_sha256
        or source.source_authority_digest != identity.source_authority_digest
        or source.source_authority_key != identity.source_authority_key
        or source.source_output_id != identity.source_output_id
        or source.source_qa_snapshot_digest != identity.source_qa_snapshot_digest
        or source.source_provenance_digest != identity.source_provenance_digest
    ):
        raise DemoSessionAuthorityUnavailable(
            "D02 synthetic identity source authority is inconsistent"
        )
    manifest = await session.get(D02SelectedSourceManifest, source.selected_source_manifest_id)
    run = (
        None
        if manifest is None
        else await session.get(D02SourceAcquisitionRun, manifest.acquisition_run_id)
    )
    if (
        manifest is None
        or manifest.manifest_state != "FINALIZED"
        or manifest.source_count != 4
        or run is None
        or run.run_state != "ADMITTED"
        or run.id != manifest.acquisition_run_id
        or run.cohort_spec_id != manifest.cohort_spec_id
    ):
        raise DemoSessionAuthorityUnavailable(
            "D02 synthetic identity admission graph is incomplete"
        )
    return DemoIdentitySnapshot(
        identity_id=identity.id,
        canonical_asset_digest=identity.formal_canonical_asset_sha256,
    )


async def resolve_demo_session_canonical_source(
    session: AsyncSession,
    *,
    row: DemoSession,
    actor_id: str,
) -> DemoSessionCanonicalSource:
    identity = await _verify_session(session, row, actor_id)
    return DemoSessionCanonicalSource(
        asset_id=identity.formal_canonical_asset_id,
        asset_sha256=identity.formal_canonical_asset_sha256,
    )


async def _verify_session(
    session: AsyncSession, row: DemoSession, actor_id: str
) -> DemoSyntheticIdentity:
    await _require_active_actor(session, actor_id)
    config = row.config
    if (
        row.schema_version != DEMO_SESSION_SCHEMA
        or row.demo_actor_id != actor_id
        or not isinstance(config, dict)
        or set(config) != {"schema_version", "synthetic_identity_id"}
        or config.get("schema_version") != DEMO_SESSION_CONFIG_SCHEMA
        or not isinstance(config.get("synthetic_identity_id"), str)
        or _ID.fullmatch(cast(str, config["synthetic_identity_id"])) is None
        or _DIGEST.fullmatch(row.context_seed) is None
        or row.expires_at.tzinfo is None
    ):
        raise DemoSessionAuthorityUnavailable("Demo Session authority is invalid")
    expected = _session_payload(
        demo_actor_id=row.demo_actor_id,
        config=config,
        context_seed=row.context_seed,
        expires_at=row.expires_at,
    )
    if row.canonical_payload != expected or row.content_digest != _authority_digest(
        DEMO_SESSION_SCHEMA, expected
    ):
        raise DemoSessionAuthorityUnavailable("Demo Session authority does not replay")
    identity = await _load_identity(session, cast(str, config["synthetic_identity_id"]))
    await _identity_snapshot(session, identity)
    return identity


def _session_snapshot(row: DemoSession) -> DemoSessionSnapshot:
    config = row.config
    identity_id = config.get("synthetic_identity_id") if isinstance(config, dict) else None
    if not isinstance(identity_id, str) or _ID.fullmatch(identity_id) is None:
        raise DemoSessionAuthorityUnavailable("Demo Session identity is invalid")
    status: Literal["ACTIVE", "CLOSED", "TOMBSTONED"]
    if row.tombstoned_at is not None:
        status = "TOMBSTONED"
    elif row.closed_at is not None:
        status = "CLOSED"
    else:
        status = "ACTIVE"
    return DemoSessionSnapshot(
        session_id=row.id,
        synthetic_identity_id=identity_id,
        status=status,
        expires_at=row.expires_at,
    )


def _session_payload(
    *,
    demo_actor_id: str,
    config: Mapping[str, Any],
    context_seed: str,
    expires_at: datetime,
) -> dict[str, Any]:
    return {
        "config": dict(config),
        "context_seed": context_seed,
        "demo_actor_id": demo_actor_id,
        "expires_at": _canonical_time(expires_at),
    }


def _authority_digest(schema_version: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _normalized_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise DemoSessionAuthorityUnavailable("Demo Session clock must be timezone-aware")
    return value.astimezone(UTC)


def _canonical_time(value: datetime) -> str:
    return _normalized_time(value).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoSessionInputError(f"{name} must be a 32-character lowercase hexadecimal ID")


def _require_digest(value: str, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise DemoSessionInputError(f"{name} must be a lowercase SHA-256 digest")


__all__ = [
    "DEMO_SESSION_CONFIG_SCHEMA",
    "DEMO_SESSION_SCHEMA",
    "DEMO_SESSION_TTL_SECONDS",
    "CreateDemoSession",
    "DemoIdentitySnapshot",
    "DemoSessionActorUnavailable",
    "DemoSessionAuthorityUnavailable",
    "DemoSessionCanonicalSource",
    "DemoSessionInputError",
    "DemoSessionPayloadConflict",
    "DemoSessionService",
    "DemoSessionSnapshot",
    "DemoSyntheticIdentityUnavailable",
    "resolve_demo_session_canonical_source",
]
