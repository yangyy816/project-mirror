from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from json import dumps

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.auth.repository import AuthRepository
from mirror_api.auth.types import (
    AgeAssuranceOutcome,
    AuthenticatedActor,
    AuthFailure,
    ChallengeResult,
    PersistedAuthFailure,
    PolicyRequirement,
    SessionResult,
)
from mirror_api.auth.uow import transaction
from mirror_api.models import (
    AgeAssuranceRecord,
    AuditLog,
    IdempotencyRecord,
    InviteCode,
    InviteRedemption,
    PhoneVerificationChallenge,
    PolicyAcceptanceRecord,
    User,
    UserSession,
    new_id,
)
from mirror_api.providers.base import AgeAssuranceProvider, SmsProvider
from mirror_api.rate_limit import RateLimiter
from mirror_api.security import (
    HMACPurpose,
    SecurityValidationError,
    create_refresh_token,
    generate_otp,
    hmac_digest,
    issue_access_token,
    normalize_china_phone,
    verify_access_token,
    verify_hmac,
    verify_refresh_token,
)


class AuthService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        sms_provider: SmsProvider,
        age_provider: AgeAssuranceProvider,
        rate_limiter: RateLimiter,
        hmac_keyring: Mapping[str, str],
        hmac_active_kid: str,
        jwt_keyring: Mapping[str, str],
        jwt_active_kid: str,
        jwt_issuer: str,
        jwt_audience: str,
        required_policies: Sequence[PolicyRequirement] = (),
        otp_ttl_seconds: int = 300,
        otp_attempt_limit: int = 5,
        refresh_ttl_seconds: int = 2_592_000,
        access_ttl_seconds: int = 300,
        challenge_rate_window_seconds: int = 60,
        challenge_phone_rate_limit: int = 5,
        challenge_ip_rate_limit: int = 20,
        challenge_device_rate_limit: int = 10,
        allow_new_registrations: bool = True,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._sms = sms_provider
        self._age = age_provider
        self._limiter = rate_limiter
        self._hmac_keyring = hmac_keyring
        self._hmac_active_kid = hmac_active_kid
        self._jwt_keyring = jwt_keyring
        self._jwt_active_kid = jwt_active_kid
        self._jwt_issuer = jwt_issuer
        self._jwt_audience = jwt_audience
        self._required_policies = tuple(required_policies)
        self._otp_ttl_seconds = otp_ttl_seconds
        self._otp_attempt_limit = otp_attempt_limit
        self._refresh_ttl_seconds = refresh_ttl_seconds
        self._access_ttl_seconds = access_ttl_seconds
        self._challenge_rate_window_seconds = challenge_rate_window_seconds
        self._challenge_phone_rate_limit = challenge_phone_rate_limit
        self._challenge_ip_rate_limit = challenge_ip_rate_limit
        self._challenge_device_rate_limit = challenge_device_rate_limit
        self._allow_new_registrations = allow_new_registrations
        self._now = now or (lambda: datetime.now(UTC))

    def _hmac(self, value: str, purpose: HMACPurpose) -> str:
        return hmac_digest(
            value, purpose=purpose, keyring=self._hmac_keyring, key_id=self._hmac_active_kid
        )

    def _fingerprint(self, values: Mapping[str, str]) -> str:
        """Return a 64-character digest of only already-normalized or HMAC-safe values."""
        canonical = dumps(dict(values), ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return sha256(canonical.encode("utf-8")).hexdigest()

    def _idempotency_key(self, key: str) -> str:
        return self._hmac(key, "idempotency")

    def _scope_for(self, user: User) -> str:
        return "active" if user.status == "active" else "pending"

    def _session_result(self, user: User, session: UserSession) -> SessionResult:
        refresh = create_refresh_token(
            keyring=self._hmac_keyring,
            active_key_id=session.refresh_key_id,
            token_id=session.token_id,
        )
        scope = self._scope_for(user)
        return SessionResult(
            user_id=user.id,
            session_id=session.id,
            access_token=issue_access_token(
                subject=user.id,
                session_id=session.id,
                scope=scope,
                keyring=self._jwt_keyring,
                active_key_id=self._jwt_active_kid,
                issuer=self._jwt_issuer,
                audience=self._jwt_audience,
                ttl_seconds=self._access_ttl_seconds,
                now=self._now(),
            ),
            refresh_token=refresh.value,
            scope=scope,
        )

    def _replay_session_result(
        self, user: User, session: UserSession, now: datetime
    ) -> SessionResult:
        """Permit application-level replay only while its referenced session remains usable.

        The current persistence model stores a session reference, rather than the original
        access-token response. Therefore this deliberately issues a fresh access token only
        for a still-live session; HTTP exact-response cache semantics remain a future concern.
        """
        if (
            session.consumed_at is not None
            or session.revoked_at is not None
            or session.expires_at < now
        ):
            raise AuthFailure()
        return self._session_result(user, session)

    def _audit(
        self,
        session: AsyncSession,
        *,
        actor_type: str,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str,
        request_id: str,
        event: str,
    ) -> None:
        """Audit metadata is deliberately a static event label, never secret material."""
        session.add(
            AuditLog(
                id=new_id(),
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                request_id=request_id,
                metadata_json={"event": event},
                occurred_at=self._now(),
            )
        )

    @staticmethod
    def _invite_usable(invite: InviteCode | None, now: datetime) -> bool:
        return bool(
            invite is not None
            and invite.disabled_at is None
            and invite.use_count < invite.max_uses
            and (invite.expires_at is None or invite.expires_at >= now)
        )

    async def request_challenge(
        self,
        *,
        phone: str,
        invite_code: str | None,
        idempotency_key: str,
        request_id: str,
        ip_key: str,
        device_key: str,
    ) -> ChallengeResult:
        try:
            normalized_phone = normalize_china_phone(phone)
        except SecurityValidationError as exc:
            raise AuthFailure() from exc
        phone_hash = self._hmac(normalized_phone, "phone")
        invite_hash = self._hmac(invite_code, "invite") if invite_code is not None else ""
        request_fingerprint = self._fingerprint({"invite": invite_hash, "phone": phone_hash})
        for bucket, key, limit in (
            ("auth-phone", phone_hash, self._challenge_phone_rate_limit),
            ("auth-ip", self._hmac(ip_key, "idempotency"), self._challenge_ip_rate_limit),
            (
                "auth-device",
                self._hmac(device_key, "idempotency"),
                self._challenge_device_rate_limit,
            ),
        ):
            result = await self._limiter.check(
                bucket=bucket,
                key=key,
                limit=limit,
                window_seconds=self._challenge_rate_window_seconds,
            )
            if not result.allowed:
                raise AuthFailure("authentication_throttled")
        actor_key, scope = f"preauth:{phone_hash}", "auth.challenge"
        key_hash = self._idempotency_key(idempotency_key)
        async with transaction(self._sessions) as session:
            repo = AuthRepository(session)
            record, claimed = await repo.claim_idempotency(
                actor_key=actor_key,
                scope=scope,
                key_hash=key_hash,
                request_fingerprint=request_fingerprint,
                expires_at=self._now() + timedelta(hours=1),
            )
            if not claimed:
                if record.request_fingerprint != request_fingerprint:
                    raise AuthFailure("idempotency_conflict")
                if record.state == "completed" and record.response_reference is not None:
                    if record.response_status == 0 and record.completed_at is not None:
                        return ChallengeResult(
                            record.response_reference,
                            record.completed_at + timedelta(seconds=self._otp_ttl_seconds),
                        )
                    challenge = await repo.locked_challenge(record.response_reference)
                    if challenge is None:
                        raise AuthFailure()
                    return ChallengeResult(challenge.id, challenge.expires_at)
                if record.state == "in_progress":
                    raise AuthFailure()
                record.state = "in_progress"
            user = await repo.locked_user_for_phone(phone_hash)
            if user is None:
                invite = await session.scalar(
                    select(InviteCode).where(InviteCode.code_hash == invite_hash).with_for_update()
                )
                if not self._allow_new_registrations or not self._invite_usable(
                    invite, self._now()
                ):
                    accepted_at = self._now()
                    decoy_id = new_id()
                    (
                        record.response_reference,
                        record.response_status,
                        record.state,
                        record.completed_at,
                    ) = (decoy_id, 0, "completed", accepted_at)
                    self._audit(
                        session,
                        actor_type="preauth",
                        actor_id=None,
                        action="challenge_accepted",
                        target_type="auth_challenge",
                        target_id=decoy_id,
                        request_id=request_id,
                        event="challenge_accepted",
                    )
                    return ChallengeResult(
                        decoy_id, accepted_at + timedelta(seconds=self._otp_ttl_seconds)
                    )
        otp = generate_otp()
        try:
            provider_message_id = await self._sms.send_verification_code(
                destination_phone=normalized_phone,
                verification_code=otp,
                request_reference=request_id,
            )
        except Exception as exc:
            async with transaction(self._sessions) as session:
                failed_record = await AuthRepository(session).idempotency(
                    actor_key=actor_key, scope=scope, key_hash=key_hash, lock=True
                )
                if failed_record is not None and failed_record.state == "in_progress":
                    failed_record.state = "failed"
            raise AuthFailure() from exc
        try:
            async with transaction(self._sessions) as session:
                repo = AuthRepository(session)
                pending_record = await repo.idempotency(
                    actor_key=actor_key, scope=scope, key_hash=key_hash, lock=True
                )
                if pending_record is None or pending_record.state != "in_progress":
                    raise AuthFailure()
                user = await repo.locked_user_for_phone(phone_hash)
                invite_id: str | None = None
                if user is None:
                    if not self._allow_new_registrations:
                        raise AuthFailure()
                    invite = await session.scalar(
                        select(InviteCode)
                        .where(InviteCode.code_hash == invite_hash)
                        .with_for_update()
                    )
                    if not self._invite_usable(invite, self._now()):
                        raise AuthFailure()
                    assert invite is not None
                    invite_id = invite.id
                challenge = PhoneVerificationChallenge(
                    id=new_id(),
                    phone_hash=phone_hash,
                    code_hash=self._hmac(otp, "otp"),
                    invite_code_id=invite_id,
                    purpose="authenticate",
                    request_id=request_id,
                    provider_message_id=provider_message_id,
                    expires_at=self._now() + timedelta(seconds=self._otp_ttl_seconds),
                )
                session.add(challenge)
                await session.flush()
                (
                    pending_record.response_reference,
                    pending_record.response_status,
                    pending_record.state,
                    pending_record.completed_at,
                ) = (
                    challenge.id,
                    1,
                    "completed",
                    self._now(),
                )
                self._audit(
                    session,
                    actor_type="preauth",
                    actor_id=None,
                    action="challenge_accepted",
                    target_type="auth_challenge",
                    target_id=challenge.id,
                    request_id=request_id,
                    event="challenge_accepted",
                )
                return ChallengeResult(challenge.id, challenge.expires_at)
        except AuthFailure:
            async with transaction(self._sessions) as session:
                failed_record = await AuthRepository(session).idempotency(
                    actor_key=actor_key, scope=scope, key_hash=key_hash, lock=True
                )
                if failed_record is not None and failed_record.state == "in_progress":
                    failed_record.state = "failed"
            raise

    async def create_session(
        self, *, challenge_id: str, otp: str, idempotency_key: str, request_id: str
    ) -> SessionResult:
        key_hash = self._idempotency_key(idempotency_key)
        otp_fingerprint = self._fingerprint({"otp": self._hmac(otp, "otp")})
        async with transaction(self._sessions) as session:
            repo = AuthRepository(session)
            challenge = await repo.locked_challenge(challenge_id)
            if challenge is None:
                raise AuthFailure()
            actor_key = f"challenge:{challenge.id}"
            record = await repo.idempotency(
                actor_key=actor_key, scope="auth.session", key_hash=key_hash, lock=True
            )
            if record is not None:
                if record.request_fingerprint != otp_fingerprint:
                    raise AuthFailure("idempotency_conflict")
                if record.state != "completed" or record.response_reference is None:
                    raise AuthFailure()
                replay = await session.get(UserSession, record.response_reference)
                user = await session.get(User, replay.user_id) if replay is not None else None
                if replay is None or user is None:
                    raise AuthFailure()
                return self._replay_session_result(user, replay, self._now())
            now = self._now()
            if (
                challenge.consumed_at is not None
                or challenge.invalidated_at is not None
                or challenge.expires_at < now
            ):
                raise AuthFailure()
            if challenge.attempts >= self._otp_attempt_limit or not verify_hmac(
                otp, challenge.code_hash, purpose="otp", keyring=self._hmac_keyring
            ):
                challenge.attempts += 1
                if challenge.attempts >= self._otp_attempt_limit:
                    challenge.invalidated_at = now
                raise PersistedAuthFailure(AuthFailure())
            user = await repo.locked_user_for_phone(challenge.phone_hash)
            if user is None:
                if challenge.invite_code_id is None:
                    raise AuthFailure()
                invite = await repo.locked_invite(challenge.invite_code_id)
                if not self._invite_usable(invite, now):
                    raise AuthFailure()
                assert invite is not None
                user = User(id=new_id(), phone_hash=challenge.phone_hash, status="pending")
                session.add(user)
                await session.flush()
                invite.use_count += 1
                redemption = InviteRedemption(
                    id=new_id(),
                    invite_code_id=invite.id,
                    user_id=user.id,
                    challenge_id=challenge.id,
                    request_id=request_id,
                )
                session.add(redemption)
                self._audit(
                    session,
                    actor_type="user",
                    actor_id=user.id,
                    action="invite_redeemed",
                    target_type="invite_redemption",
                    target_id=redemption.id,
                    request_id=request_id,
                    event="invite_redeemed",
                )
            challenge.consumed_at = now
            refresh = create_refresh_token(
                keyring=self._hmac_keyring, active_key_id=self._hmac_active_kid
            )
            created = UserSession(
                id=new_id(),
                user_id=user.id,
                family_id=new_id(),
                token_id=refresh.token_id,
                refresh_token_hash=refresh.hmac_value,
                refresh_key_id=refresh.key_id,
                expires_at=now + timedelta(seconds=self._refresh_ttl_seconds),
            )
            session.add(created)
            await session.flush()
            session.add(
                IdempotencyRecord(
                    id=new_id(),
                    actor_key=actor_key,
                    scope="auth.session",
                    key_hash=key_hash,
                    request_fingerprint=otp_fingerprint,
                    state="completed",
                    completed_at=now,
                    response_reference=created.id,
                    expires_at=now + timedelta(hours=1),
                )
            )
            self._audit(
                session,
                actor_type="user",
                actor_id=user.id,
                action="session_created",
                target_type="user_session",
                target_id=created.id,
                request_id=request_id,
                event="session_created",
            )
            return self._session_result(user, created)

    async def refresh_session(
        self, *, refresh_token: str, idempotency_key: str, request_id: str
    ) -> SessionResult:
        parts = refresh_token.split(".")
        if len(parts) != 4:
            raise AuthFailure()
        token_id, key_hash = parts[2], self._idempotency_key(idempotency_key)
        async with transaction(self._sessions) as session:
            repo = AuthRepository(session)
            current = await repo.locked_session(token_id)
            if current is None or not verify_refresh_token(
                refresh_token, current.refresh_token_hash, keyring=self._hmac_keyring
            ):
                raise AuthFailure()
            fingerprint = self._fingerprint({"session": self._hmac(current.id, "idempotency")})
            record = await repo.idempotency(
                actor_key=f"session:{current.id}",
                scope="auth.refresh",
                key_hash=key_hash,
                lock=True,
            )
            if record is not None:
                if record.request_fingerprint != fingerprint:
                    raise AuthFailure("idempotency_conflict")
                if record.state == "completed" and record.response_reference is not None:
                    replay = await session.get(UserSession, record.response_reference)
                    user = await session.get(User, replay.user_id) if replay is not None else None
                    if replay is None or user is None:
                        raise AuthFailure()
                    return self._replay_session_result(user, replay, self._now())
                raise AuthFailure()
            now = self._now()
            if (
                current.consumed_at is not None
                or current.revoked_at is not None
                or current.expires_at < now
            ):
                await repo.revoke_family(current.family_id, reason="refresh_reuse", now=now)
                self._audit(
                    session,
                    actor_type="user",
                    actor_id=current.user_id,
                    action="refresh_reuse_revoked",
                    target_type="session_family",
                    target_id=current.family_id,
                    request_id=request_id,
                    event="refresh_reuse_revoked",
                )
                raise PersistedAuthFailure(AuthFailure())
            current.consumed_at, current.last_seen_at = now, now
            refresh = create_refresh_token(
                keyring=self._hmac_keyring, active_key_id=self._hmac_active_kid
            )
            rotated = UserSession(
                id=new_id(),
                user_id=current.user_id,
                family_id=current.family_id,
                token_id=refresh.token_id,
                refresh_token_hash=refresh.hmac_value,
                refresh_key_id=refresh.key_id,
                rotated_from_id=current.id,
                expires_at=now + timedelta(seconds=self._refresh_ttl_seconds),
            )
            session.add(rotated)
            await session.flush()
            current.replaced_by_id = rotated.id
            session.add(
                IdempotencyRecord(
                    id=new_id(),
                    actor_key=f"session:{current.id}",
                    scope="auth.refresh",
                    key_hash=key_hash,
                    request_fingerprint=fingerprint,
                    state="completed",
                    completed_at=now,
                    response_reference=rotated.id,
                    expires_at=now + timedelta(hours=1),
                )
            )
            user = await session.get(User, current.user_id)
            if user is None:
                raise AuthFailure()
            self._audit(
                session,
                actor_type="user",
                actor_id=user.id,
                action="refresh_rotated",
                target_type="user_session",
                target_id=rotated.id,
                request_id=request_id,
                event="refresh_rotated",
            )
            return self._session_result(user, rotated)

    async def logout_family(self, *, session_id: str, request_id: str) -> None:
        async with transaction(self._sessions) as session:
            current = await session.get(UserSession, session_id, with_for_update=True)
            if current is None:
                raise AuthFailure()
            await AuthRepository(session).revoke_family(
                current.family_id, reason="logout", now=self._now()
            )
            self._audit(
                session,
                actor_type="user",
                actor_id=current.user_id,
                action="session_family_logged_out",
                target_type="session_family",
                target_id=current.family_id,
                request_id=request_id,
                event="session_family_logged_out",
            )

    async def authenticate_access_token(self, *, access_token: str) -> AuthenticatedActor:
        """Validate a short-lived bearer token against its current user and session state."""
        try:
            claims = verify_access_token(
                access_token,
                keyring=self._jwt_keyring,
                issuer=self._jwt_issuer,
                audience=self._jwt_audience,
            )
            user_id = claims["sub"]
            session_id = claims["sid"]
            scope = claims["scope"]
        except (KeyError, SecurityValidationError) as exc:
            raise AuthFailure() from exc
        if not all(isinstance(value, str) for value in (user_id, session_id, scope)):
            raise AuthFailure()
        async with self._sessions() as session:
            user = await session.get(User, user_id)
            current_session = await session.get(UserSession, session_id)
            if (
                user is None
                or current_session is None
                or current_session.user_id != user.id
                or current_session.revoked_at is not None
                or current_session.expires_at < self._now()
                or scope != self._scope_for(user)
            ):
                raise AuthFailure()
            return AuthenticatedActor(
                user_id=user.id,
                session_id=current_session.id,
                status=user.status,
                scope=scope,
            )

    def required_policy(self, *, code: str, version: str, digest: str) -> PolicyRequirement:
        """Return an approved policy requirement, otherwise fail closed."""
        for requirement in self._required_policies:
            if (
                requirement.document_code == code
                and requirement.document_version == version
                and requirement.document_digest == digest
            ):
                return requirement
        raise AuthFailure()

    async def onboarding_requirements(self, *, user_id: str) -> tuple[str, ...]:
        """Return only the current age and policy gates still missing for this user."""
        async with self._sessions() as session:
            user = await session.get(User, user_id)
            if user is None:
                raise AuthFailure()
            if user.status == "active":
                return ()
            repo = AuthRepository(session)
            requirements: list[str] = []
            if not await repo.has_current_verified_assurance(user.id, self._now()):
                requirements.append("age_assurance")
            for requirement in self._required_policies:
                if not await repo.has_policy(
                    user.id,
                    code=requirement.document_code,
                    version=requirement.document_version,
                    digest=requirement.document_digest,
                ):
                    requirements.append("policy_acceptance")
                    break
            return tuple(requirements)

    async def record_age_assurance(
        self, *, user_id: str, credential: str, idempotency_key: str, request_id: str
    ) -> AgeAssuranceOutcome:
        actor_key, scope = f"user:{user_id}", "auth.age_assurance"
        key_hash = self._idempotency_key(idempotency_key)
        fingerprint = self._fingerprint(
            {
                "credential": self._hmac(credential, "idempotency"),
                "user": self._hmac(user_id, "idempotency"),
            }
        )
        async with transaction(self._sessions) as session:
            repo = AuthRepository(session)
            user = await session.get(User, user_id, with_for_update=True)
            if user is None:
                raise AuthFailure()
            claim, claimed = await repo.claim_idempotency(
                actor_key=actor_key,
                scope=scope,
                key_hash=key_hash,
                request_fingerprint=fingerprint,
                expires_at=self._now() + timedelta(hours=1),
                user_id=user_id,
            )
            if not claimed:
                if claim.request_fingerprint != fingerprint:
                    raise AuthFailure("idempotency_conflict")
                if claim.state == "completed" and claim.response_reference is not None:
                    evidence = await session.get(AgeAssuranceRecord, claim.response_reference)
                    if evidence is None:
                        raise AuthFailure()
                    return AgeAssuranceOutcome(
                        evidence.id, evidence.result, claim.response_status == 1
                    )
                if claim.state == "in_progress":
                    raise AuthFailure()
                claim.state = "in_progress"
        try:
            provider_result = await self._age.verify_credential(
                credential=credential, request_reference=request_id
            )
        except Exception as exc:
            async with transaction(self._sessions) as session:
                failed_claim = await AuthRepository(session).idempotency(
                    actor_key=actor_key, scope=scope, key_hash=key_hash, lock=True
                )
                if failed_claim is not None and failed_claim.state == "in_progress":
                    failed_claim.state = "failed"
            raise AuthFailure() from exc
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = AuthRepository(session)
            pending_claim = await repo.idempotency(
                actor_key=actor_key, scope=scope, key_hash=key_hash, lock=True
            )
            if pending_claim is None or pending_claim.state != "in_progress":
                raise AuthFailure()
            user = await session.get(User, user_id, with_for_update=True)
            if user is None:
                raise AuthFailure()
            evidence = AgeAssuranceRecord(
                id=new_id(),
                user_id=user_id,
                provider="age_assurance",
                provider_reference_hash=self._hmac(
                    provider_result.provider_reference, "provider-reference"
                ),
                result=provider_result.status,
                provider_version=provider_result.provider_version,
                policy_version=provider_result.policy_version,
                verified_at=now,
                expires_at=provider_result.expires_at,
                request_id=request_id,
            )
            session.add(evidence)
            await session.flush()
            activated = await self._activate_if_ready(session, user, now, request_id)
            (
                pending_claim.response_reference,
                pending_claim.response_status,
                pending_claim.state,
                pending_claim.completed_at,
            ) = (
                evidence.id,
                int(activated),
                "completed",
                now,
            )
            self._audit(
                session,
                actor_type="user",
                actor_id=user.id,
                action="age_assurance_recorded",
                target_type="age_assurance_record",
                target_id=evidence.id,
                request_id=request_id,
                event="age_assurance_recorded",
            )
            return AgeAssuranceOutcome(evidence.id, provider_result.status, activated)

    async def accept_policy(
        self,
        *,
        user_id: str,
        requirement: PolicyRequirement,
        source: str,
        idempotency_key: str,
        request_id: str,
    ) -> bool:
        actor_key = f"user:{user_id}"
        key_hash = self._idempotency_key(idempotency_key)
        fingerprint = self._fingerprint(
            {
                "code": self._hmac(requirement.document_code, "idempotency"),
                "digest": self._hmac(requirement.document_digest, "idempotency"),
                "source": self._hmac(source, "idempotency"),
                "user": self._hmac(user_id, "idempotency"),
                "version": self._hmac(requirement.document_version, "idempotency"),
            }
        )
        now = self._now()
        async with transaction(self._sessions) as session:
            repo = AuthRepository(session)
            user = await session.get(User, user_id, with_for_update=True)
            if user is None:
                raise AuthFailure()
            claim, claimed = await repo.claim_idempotency(
                actor_key=actor_key,
                scope="auth.policy_acceptance",
                key_hash=key_hash,
                request_fingerprint=fingerprint,
                expires_at=now + timedelta(hours=1),
                user_id=user_id,
            )
            if not claimed:
                if claim.request_fingerprint != fingerprint:
                    raise AuthFailure("idempotency_conflict")
                if claim.state == "completed":
                    return claim.response_status == 1
                raise AuthFailure()
            evidence = PolicyAcceptanceRecord(
                id=new_id(),
                user_id=user_id,
                document_code=requirement.document_code,
                document_version=requirement.document_version,
                document_digest=requirement.document_digest,
                accepted_at=now,
                source=source,
                request_id=request_id,
            )
            session.add(evidence)
            await session.flush()
            activated = await self._activate_if_ready(session, user, now, request_id)
            claim.response_reference, claim.response_status, claim.state, claim.completed_at = (
                evidence.id,
                int(activated),
                "completed",
                now,
            )
            self._audit(
                session,
                actor_type="user",
                actor_id=user.id,
                action="policy_accepted",
                target_type="policy_acceptance_record",
                target_id=evidence.id,
                request_id=request_id,
                event="policy_accepted",
            )
            return activated

    async def _activate_if_ready(
        self, session: AsyncSession, user: User, now: datetime, request_id: str
    ) -> bool:
        if user.status == "active" or not self._required_policies:
            return False
        repo = AuthRepository(session)
        if not await repo.has_current_verified_assurance(user.id, now):
            return False
        for policy in self._required_policies:
            if not await repo.has_policy(
                user.id,
                code=policy.document_code,
                version=policy.document_version,
                digest=policy.document_digest,
            ):
                return False
        user.status, user.age_confirmed_at = "active", now
        self._audit(
            session,
            actor_type="user",
            actor_id=user.id,
            action="user_activated",
            target_type="user",
            target_id=user.id,
            request_id=request_id,
            event="age_and_policy_gate_satisfied",
        )
        return True
