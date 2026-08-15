"""Authentication application layer; HTTP adapters intentionally live elsewhere."""

from mirror_api.auth.service import AuthService
from mirror_api.auth.types import AuthFailure, PolicyRequirement

__all__ = ["AuthFailure", "AuthService", "PolicyRequirement"]
