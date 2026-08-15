from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class AuthFailure(RuntimeError):
    """Stable, non-enumerating application failure for an authentication boundary."""

    def __init__(self, code: str = "authentication_failed") -> None:
        super().__init__(code)
        self.code = code


class PersistedAuthFailure(RuntimeError):
    """Signal that one deliberately selected security state change must commit."""

    def __init__(self, failure: AuthFailure) -> None:
        super().__init__(failure.code)
        self.failure = failure


@dataclass(frozen=True)
class PolicyRequirement:
    document_code: str
    document_version: str
    document_digest: str


@dataclass(frozen=True)
class ChallengeResult:
    challenge_id: str
    expires_at: datetime


@dataclass(frozen=True)
class SessionResult:
    user_id: str
    session_id: str
    access_token: str
    refresh_token: str
    scope: str


@dataclass(frozen=True)
class AgeAssuranceOutcome:
    record_id: str
    result: str
    activated: bool
