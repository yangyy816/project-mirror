from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from mirror_api.auth import AuthFailure, PolicyRequirement
from mirror_api.auth.types import (
    AgeAssuranceOutcome,
    AuthenticatedActor,
    ChallengeResult,
    SessionResult,
)
from mirror_api.auth_dependencies import CSRF_COOKIE_NAME, get_auth_service
from mirror_api.main import app
from mirror_api.security import refresh_cookie_policy


class FakeAuthService:
    def __init__(self) -> None:
        self.actor = AuthenticatedActor(
            user_id="a" * 32,
            session_id="b" * 32,
            status="pending",
            scope="pending",
        )
        self.refresh_tokens: list[str] = []
        self.logout_session_id: str | None = None
        self.onboarding = ("age_assurance",)
        self.policy = PolicyRequirement("privacy", "v1", "d" * 64)

    async def request_challenge(self, **_: str | None) -> ChallengeResult:
        return ChallengeResult("c" * 32, datetime.now(UTC) + timedelta(minutes=5))

    async def create_session(self, **_: str) -> SessionResult:
        return SessionResult(
            user_id=self.actor.user_id,
            session_id=self.actor.session_id,
            access_token="access-created",  # noqa: S106
            refresh_token="refresh-created",  # noqa: S106
            scope=self.actor.scope,
        )

    async def refresh_session(self, *, refresh_token: str, **_: str) -> SessionResult:
        self.refresh_tokens.append(refresh_token)
        return SessionResult(
            user_id=self.actor.user_id,
            session_id=self.actor.session_id,
            access_token="access-refreshed",  # noqa: S106
            refresh_token="refresh-rotated",  # noqa: S106
            scope=self.actor.scope,
        )

    async def authenticate_access_token(self, *, access_token: str) -> AuthenticatedActor:
        if access_token != "access-created":  # noqa: S105
            raise AuthFailure()
        return self.actor

    async def logout_family(self, *, session_id: str, request_id: str) -> None:
        del request_id
        self.logout_session_id = session_id

    async def onboarding_requirements(self, *, user_id: str) -> tuple[str, ...]:
        assert user_id == self.actor.user_id
        return self.onboarding

    async def record_age_assurance(self, **_: str) -> AgeAssuranceOutcome:
        return AgeAssuranceOutcome("e" * 32, "verified", False)

    def required_policy(self, *, code: str, version: str, digest: str) -> PolicyRequirement:
        if (code, version, digest) != (
            self.policy.document_code,
            self.policy.document_version,
            self.policy.document_digest,
        ):
            raise AuthFailure()
        return self.policy

    async def accept_policy(self, **_: object) -> bool:
        return False


class DisabledRegistrationAuthService(FakeAuthService):
    def __init__(self) -> None:
        super().__init__()
        self.challenge_calls = 0

    async def request_challenge(self, **_: str | None) -> ChallengeResult:
        self.challenge_calls += 1
        return ChallengeResult("d" * 32, datetime.now(UTC) + timedelta(minutes=5))


def install_fake_auth_service(client: TestClient) -> FakeAuthService:
    service = FakeAuthService()
    client.app.dependency_overrides[get_auth_service] = lambda: service
    return service


def create_session(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/sessions",
        headers={"Idempotency-Key": "session-key-0001"},
        json={"challenge_id": "c" * 32, "otp": "123456"},
    )
    assert response.status_code == 201


def test_auth_routes_return_public_shapes_and_never_return_refresh(client: TestClient) -> None:
    install_fake_auth_service(client)
    challenge = client.post(
        "/api/v1/auth/sms-challenges",
        headers={"Idempotency-Key": "challenge-key-0001", "X-Device-ID": "device-test"},
        json={"phone": "+8610000000000", "invite_code": "invite-fixture"},
    )
    assert challenge.status_code == 202
    assert set(challenge.json()) == {"challenge_id", "expires_at"}

    create_session(client)
    created = client.get("/api/v1/users/me", headers={"Authorization": "Bearer access-created"})
    assert created.status_code == 200
    assert created.json() == {
        "user_id": "a" * 32,
        "status": "pending",
        "scope": "pending",
        "onboarding_requirements": ["age_assurance"],
    }
    session_response = client.post(
        "/api/v1/auth/sessions",
        headers={"Idempotency-Key": "session-key-0002"},
        json={"challenge_id": "c" * 32, "otp": "123456"},
    )
    assert "refresh" not in session_response.json()
    assert "httponly" in session_response.headers["set-cookie"].lower()
    assert "samesite=lax" in session_response.headers["set-cookie"].lower()


def test_refresh_and_logout_require_origin_and_double_submit_csrf(client: TestClient) -> None:
    service = install_fake_auth_service(client)
    create_session(client)
    csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token is not None

    rejected_refresh = client.post(
        "/api/v1/auth/token/refresh",
        headers={"Idempotency-Key": "refresh-key-0001"},
    )
    assert rejected_refresh.status_code == 401

    refreshed = client.post(
        "/api/v1/auth/token/refresh",
        headers={
            "Idempotency-Key": "refresh-key-0001",
            "Origin": "http://127.0.0.1:3000",
            "X-CSRF-Token": csrf_token,
        },
    )
    assert refreshed.status_code == 200
    assert refreshed.json() == {
        "access_token": "access-refreshed",
        "token_type": "Bearer",
        "scope": "pending",
    }
    assert service.refresh_tokens == ["refresh-created"]
    assert "refresh" not in refreshed.json()

    rotated_csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert rotated_csrf is not None and rotated_csrf != csrf_token
    logout = client.delete(
        "/api/v1/auth/sessions/current",
        headers={
            "Authorization": "Bearer access-created",
            "Origin": "http://127.0.0.1:3000",
            "X-CSRF-Token": rotated_csrf,
        },
    )
    assert logout.status_code == 204
    assert service.logout_session_id == "b" * 32
    assert "max-age=0" in logout.headers["set-cookie"].lower()


def test_pending_user_may_submit_age_and_required_policy_but_not_unconfigured_policy(
    client: TestClient,
) -> None:
    install_fake_auth_service(client)
    headers = {"Authorization": "Bearer access-created", "Idempotency-Key": "age-key-0001"}
    age = client.post(
        "/api/v1/users/me/age-assurances",
        headers=headers,
        json={"credential": "test-age-credential"},
    )
    assert age.status_code == 201
    assert age.json() == {"record_id": "e" * 32, "result": "verified", "activated": False}

    rejected_policy = client.post(
        "/api/v1/users/me/policy-acceptances",
        headers={"Authorization": "Bearer access-created", "Idempotency-Key": "policy-key-0001"},
        json={"document_code": "other", "document_version": "v1", "document_digest": "d" * 64},
    )
    assert rejected_policy.status_code == 401

    accepted_policy = client.post(
        "/api/v1/users/me/policy-acceptances",
        headers={"Authorization": "Bearer access-created", "Idempotency-Key": "policy-key-0002"},
        json={"document_code": "privacy", "document_version": "v1", "document_digest": "d" * 64},
    )
    assert accepted_policy.status_code == 201
    assert accepted_policy.json() == {"activated": False}


def test_sensitive_validation_errors_do_not_echo_request_input(client: TestClient) -> None:
    marker = "do-not-return-this-secret"
    response = client.post(
        "/api/v1/auth/sms-challenges",
        headers={"Idempotency-Key": "challenge-key-0002"},
        json={"phone": {"raw": marker}, "invite_code": marker},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_failed"
    assert marker not in response.text


def test_new_registration_gate_has_the_same_public_acceptance_shape(client: TestClient) -> None:
    install_fake_auth_service(client)
    real = client.post(
        "/api/v1/auth/sms-challenges",
        headers={"Idempotency-Key": "existing-user-0001"},
        json={"phone": "+8610000000000"},
    )
    service = DisabledRegistrationAuthService()
    client.app.dependency_overrides[get_auth_service] = lambda: service
    decoy = client.post(
        "/api/v1/auth/sms-challenges",
        headers={"Idempotency-Key": "disabled-registration-0001"},
        json={"phone": "+8610000000000", "invite_code": "fixture"},
    )
    assert real.status_code == decoy.status_code == 202
    assert set(real.json()) == set(decoy.json()) == {"challenge_id", "expires_at"}
    assert service.challenge_calls == 1


def test_production_refresh_cookie_policy_is_httponly_secure_and_lax() -> None:
    policy = refresh_cookie_policy(
        app_env="production", name="mirror_refresh", ttl_seconds=2_592_000
    )
    assert policy.httponly
    assert policy.secure
    assert policy.samesite == "lax"
    assert policy.path == "/api/v1/auth"


def test_logout_cors_preflight_allows_delete_and_security_headers(client: TestClient) -> None:
    response = client.options(
        "/api/v1/auth/sessions/current",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization,x-csrf-token",
        },
    )

    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "x-csrf-token" in allowed_headers


def test_auth_openapi_requires_idempotency_and_hides_refresh_response() -> None:
    schema = app.openapi()
    posts = {
        "/api/v1/auth/sms-challenges": "202",
        "/api/v1/auth/sessions": "201",
        "/api/v1/auth/token/refresh": "200",
        "/api/v1/users/me/age-assurances": "201",
        "/api/v1/users/me/policy-acceptances": "201",
    }
    for path, success_status in posts.items():
        operation = schema["paths"][path]["post"]
        assert success_status in operation["responses"]
        assert any(
            parameter["in"] == "header"
            and parameter["name"] == "Idempotency-Key"
            and parameter["required"]
            for parameter in operation["parameters"]
        )
    components = schema["components"]["schemas"]
    assert "refresh_token" not in str(components["AccessTokenResponse"])
