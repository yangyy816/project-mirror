"""Pure, append-only D07-B demo ImageVersion domain slice.

This is deliberately an in-memory domain authority for deterministic unit tests.  It
does not read or write bytes, storage, an ORM, or a real D02 asset.  Consequently it
is implementation-ready only: real-asset replay remains deferred until an actual
runtime integration or acceptance Gate requires it.
"""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from mirror_api.demo_operation_graph import (
    ImageVersionReference,
    OperationGraph,
    OperationLineageError,
    OperationType,
    canonical_json_bytes,
    graph_content_digest,
    plan_restore_transition,
    plan_rollback_transition,
    validate_for_execution,
    validate_operation_graph,
    validate_result_asset_id,
)

IMPLEMENTATION_STATUS: Final = "IMPLEMENTATION_READY"
REAL_ASSET_INTEGRATION_STATUS: Final = "REAL_ASSET_INTEGRATION_DEFERRED_PENDING_EVIDENCE"
_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class ImageVersionKind(StrEnum):
    ORIGINAL = "ORIGINAL"
    EDIT = "EDIT"
    RESTORED = "RESTORED"
    ROLLED_BACK = "ROLLED_BACK"


class DemoImageVersionError(ValueError):
    """Fail-closed D07-B domain error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DemoImageVersion:
    """An immutable published fact; no object-storage byte is represented here."""

    image_version_id: str
    image_version_digest: str
    actor_id: str
    demo_session_id: str
    editing_session_id: str
    sequence: int
    parent_image_version_id: str | None
    source_image_version_id: str | None
    source_image_version_digest: str | None
    target_image_version_id: str | None
    target_image_version_digest: str | None
    result_asset_id: str
    result_asset_sha256: str
    operation_graph_digest: str | None
    kind: ImageVersionKind

    def reference(self) -> ImageVersionReference:
        return ImageVersionReference(
            image_version_id=self.image_version_id,
            image_version_digest=self.image_version_digest,
            actor_id=self.actor_id,
            demo_session_id=self.demo_session_id,
            editing_session_id=self.editing_session_id,
            result_asset_id=self.result_asset_id,
            result_asset_sha256=self.result_asset_sha256,
            sequence=self.sequence,
            parent_image_version_id=self.parent_image_version_id,
        )


@dataclass(frozen=True)
class PublishEditRequest:
    idempotency_key: str
    source_image_version_id: str
    source_image_version_digest: str
    operation_graph: OperationGraph
    result_asset_id: str
    result_asset_sha256: str


@dataclass(frozen=True)
class PublishTransitionRequest:
    idempotency_key: str
    source_image_version_id: str
    source_image_version_digest: str
    target_image_version_id: str
    target_image_version_digest: str
    operation_graph: OperationGraph
    result_asset_id: str
    result_asset_sha256: str


class InMemoryImageVersionAuthority:
    """Thread-safe append-only authority used only by the D07-B unit-test fixture."""

    def __init__(self, original: DemoImageVersion) -> None:
        self._lock = threading.RLock()
        self._versions: dict[str, DemoImageVersion] = {}
        self._idempotent: dict[tuple[str, str, str, str, str], tuple[str, str]] = {}
        self._publish_original(original)

    @property
    def integration_status(self) -> str:
        return REAL_ASSET_INTEGRATION_STATUS

    def history(self) -> tuple[DemoImageVersion, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._versions.values(), key=lambda item: (item.sequence, item.image_version_id)
                )
            )

    def get(self, image_version_id: str) -> DemoImageVersion:
        with self._lock:
            try:
                return self._versions[image_version_id]
            except KeyError as exc:
                raise DemoImageVersionError(
                    "SOURCE_NOT_FOUND", "image version is not published"
                ) from exc

    def publish_edit(self, request: PublishEditRequest) -> DemoImageVersion:
        with self._lock:
            source = self._source(
                request.source_image_version_id, request.source_image_version_digest
            )
            validate_operation_graph(request.operation_graph)
            validate_for_execution(request.operation_graph)
            if (
                request.operation_graph.input_image_version_id != source.image_version_id
                or request.operation_graph.input_image_version_digest != source.image_version_digest
            ):
                raise DemoImageVersionError(
                    "OPERATION_GRAPH_SOURCE_MISMATCH", "graph input must bind source"
                )
            _require_id(request.result_asset_id, "result asset id")
            _require_digest(request.result_asset_sha256, "result asset sha256")
            if request.result_asset_id == source.result_asset_id:
                raise DemoImageVersionError(
                    "RESULT_ASSET_NOT_DISTINCT", "edit result asset must be distinct"
                )
            graph_digest = graph_content_digest(request.operation_graph)
            fingerprint = _request_digest(
                {
                    "kind": ImageVersionKind.EDIT.value,
                    "source_image_version_digest": source.image_version_digest,
                    "source_image_version_id": source.image_version_id,
                    "result_asset_id": request.result_asset_id,
                    "result_asset_sha256": request.result_asset_sha256,
                    "operation_graph_digest": graph_digest,
                }
            )
            return self._replay_or_publish(
                source,
                request.idempotency_key,
                fingerprint,
                kind=ImageVersionKind.EDIT,
                target=None,
                result_asset_id=request.result_asset_id,
                result_asset_sha256=request.result_asset_sha256,
                operation_graph_digest=graph_digest,
            )

    def restore(self, request: PublishTransitionRequest) -> DemoImageVersion:
        return self._publish_transition(request, ImageVersionKind.RESTORED)

    def rollback(self, request: PublishTransitionRequest) -> DemoImageVersion:
        return self._publish_transition(request, ImageVersionKind.ROLLED_BACK)

    def _publish_transition(
        self, request: PublishTransitionRequest, kind: ImageVersionKind
    ) -> DemoImageVersion:
        with self._lock:
            source = self._source(
                request.source_image_version_id, request.source_image_version_digest
            )
            validate_operation_graph(request.operation_graph)
            expected_operation = (
                OperationType.RESTORE
                if kind is ImageVersionKind.RESTORED
                else OperationType.ROLLBACK
            )
            if len(request.operation_graph.nodes) != 1 or (
                request.operation_graph.nodes[0].spec.operation_type is not expected_operation
            ):
                raise DemoImageVersionError(
                    "TRANSITION_OPERATION_MISMATCH", "graph must contain one matching transition"
                )
            if (
                request.operation_graph.input_image_version_id != source.image_version_id
                or request.operation_graph.input_image_version_digest != source.image_version_digest
            ):
                raise DemoImageVersionError(
                    "OPERATION_GRAPH_SOURCE_MISMATCH", "graph input must bind source"
                )
            history = tuple(item.reference() for item in self.history())
            try:
                planner = (
                    plan_restore_transition
                    if kind is ImageVersionKind.RESTORED
                    else plan_rollback_transition
                )
                intent = planner(
                    source.reference(),
                    history,
                    request.target_image_version_id,
                    request.target_image_version_digest,
                )
                validate_result_asset_id(intent, request.result_asset_id)
            except OperationLineageError as exc:
                raise DemoImageVersionError(exc.code, str(exc)) from exc
            if request.result_asset_sha256 != intent.expected_result_asset_sha256:
                raise DemoImageVersionError(
                    "RESULT_DIGEST_MISMATCH", "transition must preserve target bytes"
                )
            parameters = request.operation_graph.nodes[0].spec.parameters
            if (
                parameters["target_image_version_id"] != request.target_image_version_id
                or parameters["target_image_version_digest"] != request.target_image_version_digest
            ):
                raise DemoImageVersionError(
                    "TRANSITION_GRAPH_TARGET_MISMATCH", "graph target must bind transition"
                )
            graph_digest = graph_content_digest(request.operation_graph)
            fingerprint = _request_digest(
                {
                    "kind": kind.value,
                    "source_image_version_digest": source.image_version_digest,
                    "source_image_version_id": source.image_version_id,
                    "target_image_version_digest": request.target_image_version_digest,
                    "target_image_version_id": request.target_image_version_id,
                    "result_asset_id": request.result_asset_id,
                    "result_asset_sha256": request.result_asset_sha256,
                    "operation_graph_digest": graph_digest,
                }
            )
            target = self._source(
                request.target_image_version_id, request.target_image_version_digest
            )
            return self._replay_or_publish(
                source,
                request.idempotency_key,
                fingerprint,
                kind=kind,
                target=target,
                result_asset_id=request.result_asset_id,
                result_asset_sha256=request.result_asset_sha256,
                operation_graph_digest=graph_digest,
            )

    def _publish_original(self, original: DemoImageVersion) -> None:
        _validate_version(original)
        if original.kind is not ImageVersionKind.ORIGINAL or original.sequence != 0:
            raise DemoImageVersionError("INVALID_ORIGINAL", "original must be sequence zero")
        if any(
            value is not None
            for value in (
                original.parent_image_version_id,
                original.source_image_version_id,
                original.source_image_version_digest,
                original.target_image_version_id,
                original.target_image_version_digest,
                original.operation_graph_digest,
            )
        ):
            raise DemoImageVersionError("INVALID_ORIGINAL", "original cannot have lineage or graph")
        self._versions[original.image_version_id] = original

    def _source(self, image_version_id: str, image_version_digest: str) -> DemoImageVersion:
        _require_id(image_version_id, "source image version id")
        _require_digest(image_version_digest, "source image version digest")
        source = self.get(image_version_id)
        if source.image_version_digest != image_version_digest:
            raise DemoImageVersionError(
                "SOURCE_DIGEST_MISMATCH", "source digest does not bind source id"
            )
        return source

    def _replay_or_publish(
        self,
        source: DemoImageVersion,
        idempotency_key: str,
        fingerprint: str,
        *,
        kind: ImageVersionKind,
        target: DemoImageVersion | None,
        result_asset_id: str,
        result_asset_sha256: str,
        operation_graph_digest: str,
    ) -> DemoImageVersion:
        _require_idempotency_key(idempotency_key)
        key = (
            source.actor_id,
            source.demo_session_id,
            source.editing_session_id,
            kind.value,
            idempotency_key,
        )
        replay = self._idempotent.get(key)
        if replay is not None:
            known_fingerprint, image_version_id = replay
            if known_fingerprint != fingerprint:
                raise DemoImageVersionError(
                    "IDEMPOTENCY_CONFLICT", "idempotency key has another semantic request"
                )
            return self._versions[image_version_id]
        image_version_id = _image_version_id(fingerprint)
        if image_version_id in self._versions:
            raise DemoImageVersionError(
                "VERSION_ID_COLLISION", "canonical version id is already published"
            )
        version = DemoImageVersion(
            image_version_id=image_version_id,
            image_version_digest="",
            actor_id=source.actor_id,
            demo_session_id=source.demo_session_id,
            editing_session_id=source.editing_session_id,
            sequence=max(item.sequence for item in self._versions.values()) + 1,
            parent_image_version_id=source.image_version_id,
            source_image_version_id=source.image_version_id,
            source_image_version_digest=source.image_version_digest,
            target_image_version_id=None if target is None else target.image_version_id,
            target_image_version_digest=None if target is None else target.image_version_digest,
            result_asset_id=result_asset_id,
            result_asset_sha256=result_asset_sha256,
            operation_graph_digest=operation_graph_digest,
            kind=kind,
        )
        digest = _version_digest(version)
        published = DemoImageVersion(**{**version.__dict__, "image_version_digest": digest})
        _validate_version(published)
        # The two mutations occur only after every fail-closed validation above.
        self._versions[published.image_version_id] = published
        self._idempotent[key] = (fingerprint, published.image_version_id)
        return published


def _version_digest(version: DemoImageVersion) -> str:
    payload = {
        "actor_id": version.actor_id,
        "demo_session_id": version.demo_session_id,
        "editing_session_id": version.editing_session_id,
        "image_version_id": version.image_version_id,
        "kind": version.kind.value,
        "operation_graph_digest": version.operation_graph_digest,
        "parent_image_version_id": version.parent_image_version_id,
        "result_asset_id": version.result_asset_id,
        "result_asset_sha256": version.result_asset_sha256,
        "sequence": version.sequence,
        "source_image_version_digest": version.source_image_version_digest,
        "source_image_version_id": version.source_image_version_id,
        "target_image_version_digest": version.target_image_version_digest,
        "target_image_version_id": version.target_image_version_id,
    }
    return _request_digest({key: value for key, value in payload.items() if value is not None})


def _request_digest(payload: object) -> str:
    return hashlib.sha256(
        b"mirror.demo/ImageVersion/v1\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _image_version_id(fingerprint: str) -> str:
    return hashlib.sha256(
        b"mirror.demo/ImageVersion/id/v1\n" + fingerprint.encode("ascii")
    ).hexdigest()[:32]


def _validate_version(version: DemoImageVersion) -> None:
    _require_id(version.image_version_id, "image version id")
    _require_digest(version.image_version_digest, "image version digest")
    _require_id(version.actor_id, "actor id")
    _require_id(version.demo_session_id, "demo session id")
    _require_id(version.editing_session_id, "editing session id")
    _require_id(version.result_asset_id, "result asset id")
    _require_digest(version.result_asset_sha256, "result asset sha256")
    if (
        not isinstance(version.kind, ImageVersionKind)
        or type(version.sequence) is not int
        or version.sequence < 0
    ):
        raise DemoImageVersionError("INVALID_VERSION", "version kind or sequence is invalid")


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoImageVersionError(
            "INVALID_ID", f"{name} must be 32 lowercase hexadecimal characters"
        )


def _require_digest(value: str, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise DemoImageVersionError(
            "INVALID_DIGEST", f"{name} must be 64 lowercase hexadecimal characters"
        )


def _require_idempotency_key(value: str) -> None:
    if not isinstance(value, str) or _IDEMPOTENCY_KEY.fullmatch(value) is None:
        raise DemoImageVersionError("INVALID_IDEMPOTENCY_KEY", "idempotency key is invalid")
