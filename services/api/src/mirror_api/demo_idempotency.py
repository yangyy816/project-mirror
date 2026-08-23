"""PostgreSQL-backed semantic idempotency for synchronous Demo commands.

Target creators must only write through the supplied database session.  The
coordinator can roll back a losing candidate target, but it cannot undo an
external side effect performed by a callback.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_models import DemoCommandBinding
from mirror_api.models import new_id, utcnow

DEMO_COMMAND_BINDING_SCHEMA_VERSION = "mirror.demo/DemoCommandBinding/v1"
IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD = "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"

_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_JsonValue = None | bool | int | str | list["_JsonValue"] | dict[str, "_JsonValue"]
T = TypeVar("T")


@dataclass(frozen=True)
class DemoOperationResponse:
    response_type: str
    response_status: int


SUPPORTED_DEMO_OPERATIONS: Mapping[str, DemoOperationResponse] = {
    "session.create": DemoOperationResponse("DEMO_SESSION", 201),
    "questionnaire.response.create": DemoOperationResponse("QUESTIONNAIRE_STEP", 201),
    "style_feedback.create": DemoOperationResponse("PREFERENCE_EVENT", 201),
    "constraint.create": DemoOperationResponse("IDENTITY_CONSTRAINTS", 201),
    "image_version.feedback": DemoOperationResponse("PREFERENCE_EVENT", 201),
    "job.cancel": DemoOperationResponse("JOB", 200),
}


class DemoIdempotencyError(RuntimeError):
    """Base error for the Demo command-idempotency coordinator."""


class DemoIdempotencyInputError(DemoIdempotencyError):
    """The caller did not supply a canonicalizable semantic request."""


class DemoIdempotencyAuthorityCorruption(DemoIdempotencyError):
    """The persisted winner or its typed target cannot be trusted."""


class DemoIdempotencyPayloadConflict(DemoIdempotencyError):
    """An idempotency key is already bound to a different semantic request."""

    code = IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True)
class DemoIdempotencyTarget[T]:
    """Typed response authority created or loaded by a command callback."""

    value: T
    response_id: str
    demo_session_id: str | None


@dataclass(frozen=True)
class DemoIdempotencyResult[T]:
    value: T
    target_id: str
    binding_id: str
    response_status: int
    replayed: bool


DemoTargetCreator = Callable[[AsyncSession], Awaitable[DemoIdempotencyTarget[T]]]
DemoTargetLoader = Callable[
    [AsyncSession, DemoCommandBinding], Awaitable[DemoIdempotencyTarget[T] | None]
]


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Return compact, UTF-8, sorted JSON after rejecting non-JSON inputs."""

    normalized = _normalize_json_object(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def semantic_request_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def idempotency_key_hash(idempotency_key: str) -> str:
    if not isinstance(idempotency_key, str):
        raise DemoIdempotencyInputError("idempotency key must be a string")
    if len(idempotency_key) < 8 or len(idempotency_key) > 128:
        raise DemoIdempotencyInputError("idempotency key must be between 8 and 128 characters")
    if any(ord(character) < 0x21 or ord(character) > 0x7E for character in idempotency_key):
        raise DemoIdempotencyInputError("idempotency key must contain visible ASCII characters")
    return hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()


def binding_content_digest(canonical_payload: Mapping[str, Any]) -> str:
    authority = DEMO_COMMAND_BINDING_SCHEMA_VERSION.encode("utf-8") + b"\n"
    return hashlib.sha256(authority + canonical_json_bytes(canonical_payload)).hexdigest()


class DemoSemanticIdempotencyCoordinator:
    """Create a typed response and its immutable binding in one transaction."""

    def __init__(self, *, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(
        self,
        *,
        demo_actor_id: str,
        endpoint_operation: str,
        idempotency_key: str,
        semantic_request: Mapping[str, Any],
        create_target: DemoTargetCreator[T],
        load_target: DemoTargetLoader[T],
    ) -> DemoIdempotencyResult[T]:
        operation_response = _operation_response(endpoint_operation)
        _require_id(demo_actor_id, "demo actor id")
        key_hash = idempotency_key_hash(idempotency_key)
        request_digest = semantic_request_digest(semantic_request)

        async with self._session_factory() as session:
            async with session.begin():
                savepoint = await session.begin_nested()
                candidate = await create_target(session)
                _validate_target(candidate)
                await session.flush()

                binding_id = new_id()
                canonical_payload = _binding_payload(
                    demo_actor_id=demo_actor_id,
                    demo_session_id=candidate.demo_session_id,
                    endpoint_operation=endpoint_operation,
                    idempotency_key_hash_value=key_hash,
                    request_digest=request_digest,
                    response_type=operation_response.response_type,
                    response_id=candidate.response_id,
                    response_status=operation_response.response_status,
                )
                inserted_id = await session.scalar(
                    insert(DemoCommandBinding)
                    .values(
                        id=binding_id,
                        schema_version=DEMO_COMMAND_BINDING_SCHEMA_VERSION,
                        canonical_payload=canonical_payload,
                        content_digest=binding_content_digest(canonical_payload),
                        created_at=utcnow(),
                        demo_actor_id=demo_actor_id,
                        demo_session_id=candidate.demo_session_id,
                        endpoint_operation=endpoint_operation,
                        idempotency_key_hash=key_hash,
                        request_digest=request_digest,
                        response_type=operation_response.response_type,
                        response_id=candidate.response_id,
                        response_status=operation_response.response_status,
                    )
                    .on_conflict_do_nothing(
                        index_elements=(
                            DemoCommandBinding.demo_actor_id,
                            DemoCommandBinding.endpoint_operation,
                            DemoCommandBinding.idempotency_key_hash,
                        )
                    )
                    .returning(DemoCommandBinding.id)
                )
                if inserted_id is not None:
                    await savepoint.commit()
                    return DemoIdempotencyResult(
                        value=candidate.value,
                        target_id=candidate.response_id,
                        binding_id=binding_id,
                        response_status=operation_response.response_status,
                        replayed=False,
                    )

                await savepoint.rollback()
                binding = await session.scalar(
                    select(DemoCommandBinding).where(
                        DemoCommandBinding.demo_actor_id == demo_actor_id,
                        DemoCommandBinding.endpoint_operation == endpoint_operation,
                        DemoCommandBinding.idempotency_key_hash == key_hash,
                    )
                )
                if binding is None:
                    raise DemoIdempotencyAuthorityCorruption(
                        "unique-conflict winner was not reloadable"
                    )
                _validate_binding(binding, operation_response)
                if binding.request_digest != request_digest:
                    raise DemoIdempotencyPayloadConflict()

                loaded_target = await load_target(session, binding)
                if loaded_target is None:
                    raise DemoIdempotencyAuthorityCorruption("winner response target is missing")
                _validate_target(loaded_target)
                if (
                    loaded_target.response_id != binding.response_id
                    or loaded_target.demo_session_id != binding.demo_session_id
                ):
                    raise DemoIdempotencyAuthorityCorruption(
                        "winner response target does not match its command binding"
                    )
                return DemoIdempotencyResult(
                    value=loaded_target.value,
                    target_id=binding.response_id,
                    binding_id=binding.id,
                    response_status=binding.response_status,
                    replayed=True,
                )


def _normalize_json_object(value: Mapping[str, Any]) -> dict[str, _JsonValue]:
    if not isinstance(value, Mapping):
        raise DemoIdempotencyInputError("semantic request must be a JSON object")
    normalized = _normalize_json(value)
    if not isinstance(normalized, dict):  # pragma: no cover - guarded by Mapping above.
        raise DemoIdempotencyInputError("semantic request must be a JSON object")
    return normalized


def _normalize_json(value: Any) -> _JsonValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise DemoIdempotencyInputError(
            "semantic request cannot contain raw floats; use a quantized integer"
        )
    if isinstance(value, Mapping):
        normalized: dict[str, _JsonValue] = {}
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise DemoIdempotencyInputError("semantic request object keys must be strings")
            normalized[key] = _normalize_json(nested_value)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_normalize_json(item) for item in value]
    raise DemoIdempotencyInputError("semantic request contains a non-JSON value")


def _operation_response(endpoint_operation: str) -> DemoOperationResponse:
    operation_response = SUPPORTED_DEMO_OPERATIONS.get(endpoint_operation)
    if operation_response is None:
        raise DemoIdempotencyInputError("unsupported Demo endpoint operation")
    return operation_response


def _require_id(value: str, description: str) -> None:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise DemoIdempotencyInputError(f"{description} must be a lowercase hexadecimal ID")


def _validate_target(target: DemoIdempotencyTarget[Any]) -> None:
    _require_id(target.response_id, "response id")
    if target.demo_session_id is not None:
        _require_id(target.demo_session_id, "demo session id")


def _binding_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str | None,
    endpoint_operation: str,
    idempotency_key_hash_value: str,
    request_digest: str,
    response_type: str,
    response_id: str,
    response_status: int,
) -> dict[str, _JsonValue]:
    return {
        "demo_actor_id": demo_actor_id,
        "demo_session_id": demo_session_id,
        "endpoint_operation": endpoint_operation,
        "idempotency_key_hash": idempotency_key_hash_value,
        "request_digest": request_digest,
        "response_id": response_id,
        "response_status": response_status,
        "response_type": response_type,
    }


def _validate_binding(
    binding: DemoCommandBinding, operation_response: DemoOperationResponse
) -> None:
    _require_id(binding.id, "binding id")
    _require_id(binding.demo_actor_id, "binding actor id")
    _require_id(binding.response_id, "binding response id")
    if binding.demo_session_id is not None:
        _require_id(binding.demo_session_id, "binding demo session id")
    if (
        _DIGEST_PATTERN.fullmatch(binding.idempotency_key_hash) is None
        or _DIGEST_PATTERN.fullmatch(binding.request_digest) is None
        or _DIGEST_PATTERN.fullmatch(binding.content_digest) is None
    ):
        raise DemoIdempotencyAuthorityCorruption("binding digest has an invalid shape")
    if binding.schema_version != DEMO_COMMAND_BINDING_SCHEMA_VERSION:
        raise DemoIdempotencyAuthorityCorruption("binding schema version is unsupported")
    if (
        binding.response_type != operation_response.response_type
        or binding.response_status != operation_response.response_status
    ):
        raise DemoIdempotencyAuthorityCorruption("binding operation response mapping is invalid")
    expected_payload = _binding_payload(
        demo_actor_id=binding.demo_actor_id,
        demo_session_id=binding.demo_session_id,
        endpoint_operation=binding.endpoint_operation,
        idempotency_key_hash_value=binding.idempotency_key_hash,
        request_digest=binding.request_digest,
        response_type=binding.response_type,
        response_id=binding.response_id,
        response_status=binding.response_status,
    )
    if binding.canonical_payload != expected_payload:
        raise DemoIdempotencyAuthorityCorruption("binding canonical payload is invalid")
    if binding.content_digest != binding_content_digest(expected_payload):
        raise DemoIdempotencyAuthorityCorruption("binding content digest is invalid")
