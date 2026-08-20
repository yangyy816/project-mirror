"""Synthetic reference state machine for Principal-managed private input handoff.

This module is deliberately not a cross-process secret broker. It gives governance tests a
first-party, fail-closed model without granting filesystem discovery or production authority.
"""

from __future__ import annotations

import hashlib
import os
import stat
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class InputClassification(StrEnum):
    PRIVATE_NONSENSITIVE_INPUT = "PRIVATE_NONSENSITIVE_INPUT"
    PRIVATE_SENSITIVE_INPUT = "PRIVATE_SENSITIVE_INPUT"
    SECRET_CREDENTIAL = "SECRET_CREDENTIAL"  # noqa: S105 - classification label, not a value
    REAL_USER_SENSITIVE_INPUT = "REAL_USER_SENSITIVE_INPUT"


class HandoffOutcome(StrEnum):
    OWNER_ACTION_REQUIRED = "OWNER_ACTION_REQUIRED"
    PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED = "PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED"
    PRIVATE_INPUT_VALIDATION_FAILED = "PRIVATE_INPUT_VALIDATION_FAILED"
    PRIVATE_INPUT_HANDOFF_DENIED = "PRIVATE_INPUT_HANDOFF_DENIED"
    PRIVATE_INPUT_CLEANUP_FAILED = "PRIVATE_INPUT_CLEANUP_FAILED"


class PrivateInputError(RuntimeError):
    """Allowlisted failure without source path or payload disclosure."""

    def __init__(self, outcome: HandoffOutcome) -> None:
        super().__init__(outcome.value)
        self.outcome = outcome


@dataclass(frozen=True, slots=True)
class PrivateInputSpec:
    input_id: str
    classification: InputClassification
    authority: str
    expected_digest: str
    maximum_bytes: int
    allowed_task_id: str
    allowed_agent_role: str
    allowed_operation: str


@dataclass(frozen=True, slots=True)
class HandoffReceipt:
    input_id: str
    task_id: str
    agent_role: str
    digest: str
    byte_size: int
    handoff_status: str


@dataclass(slots=True)
class _RegisteredInput:
    spec: PrivateInputSpec
    source_bytes: bytes


@dataclass(slots=True)
class _Lease:
    input_id: str
    task_id: str
    agent_role: str
    operation: str
    handoff_directory: Path
    handoff_file: Path
    digest: str
    byte_size: int


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _valid_digest(value: str) -> bool:
    return (
        len(value) == 64 and value == value.lower() and all(c in "0123456789abcdef" for c in value)
    )


def _read_exact_regular_file(source: Path, maximum_bytes: int) -> bytes:
    try:
        before = source.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size <= 0
            or before.st_size > maximum_bytes
        ):
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
        if getattr(before, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
        ):
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
        with source.open("rb") as stream:
            value = stream.read(maximum_bytes + 1)
            descriptor = os.fstat(stream.fileno())
        after = source.lstat()
    except FileNotFoundError as error:
        raise PrivateInputError(HandoffOutcome.OWNER_ACTION_REQUIRED) from error
    except PrivateInputError:
        raise
    except OSError as error:
        raise PrivateInputError(HandoffOutcome.OWNER_ACTION_REQUIRED) from error
    if len(value) == 0 or len(value) > maximum_bytes:
        raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
    identity = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(getattr(before, name) != getattr(after, name) for name in identity):
        raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
    if any(
        getattr(before, name) != getattr(descriptor, name)
        for name in ("st_dev", "st_ino", "st_size")
    ):
        raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
    return value


class PrivateInputCustodian:
    """Principal-only in-process registry and synthetic handoff controller."""

    def __init__(self, handoff_root: Path) -> None:
        self._handoff_root = handoff_root
        self._registry: dict[str, _RegisteredInput] = {}
        self._leases: dict[str, _Lease] = {}

    def register_owner_input(self, spec: PrivateInputSpec, source: Path) -> None:
        if spec.classification in {
            InputClassification.SECRET_CREDENTIAL,
            InputClassification.REAL_USER_SENSITIVE_INPUT,
        }:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_HANDOFF_DENIED)
        if not spec.input_id or not spec.authority or spec.maximum_bytes <= 0:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
        if not _valid_digest(spec.expected_digest):
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
        value = _read_exact_regular_file(source, spec.maximum_bytes)
        if _digest(value) != spec.expected_digest:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
        if spec.input_id in self._registry:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
        self._registry[spec.input_id] = _RegisteredInput(spec=spec, source_bytes=value)

    def create_handoff(
        self,
        *,
        input_id: str,
        task_id: str,
        agent_role: str,
        operation: str,
    ) -> HandoffReceipt:
        registered = self._registry.get(input_id)
        if registered is None:
            raise PrivateInputError(HandoffOutcome.OWNER_ACTION_REQUIRED)
        spec = registered.spec
        if task_id != spec.allowed_task_id or agent_role != spec.allowed_agent_role:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_HANDOFF_DENIED)
        if operation != spec.allowed_operation:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED)
        if input_id in self._leases:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_HANDOFF_DENIED)
        directory = self._handoff_root / uuid.uuid4().hex
        handoff_file = directory / "input-01"
        try:
            directory.mkdir(parents=True, exist_ok=False)
            with handoff_file.open("xb") as stream:
                stream.write(registered.source_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            if _digest(handoff_file.read_bytes()) != spec.expected_digest:
                raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
            handoff_file.chmod(stat.S_IREAD)
        except PrivateInputError:
            self._remove_directory(directory)
            raise
        except OSError as error:
            self._remove_directory(directory)
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED) from error
        lease = _Lease(
            input_id=input_id,
            task_id=task_id,
            agent_role=agent_role,
            operation=operation,
            handoff_directory=directory,
            handoff_file=handoff_file,
            digest=spec.expected_digest,
            byte_size=len(registered.source_bytes),
        )
        self._leases[input_id] = lease
        return HandoffReceipt(
            input_id=input_id,
            task_id=task_id,
            agent_role=agent_role,
            digest=lease.digest,
            byte_size=lease.byte_size,
            handoff_status="HANDOFF_COMPLETE",
        )

    def read_for_agent(
        self,
        *,
        input_id: str,
        task_id: str,
        agent_role: str,
        operation: str,
    ) -> bytes:
        lease = self._leases.get(input_id)
        if lease is None:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_HANDOFF_DENIED)
        if (task_id, agent_role) != (lease.task_id, lease.agent_role):
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_HANDOFF_DENIED)
        if operation != lease.operation:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED)
        try:
            value = lease.handoff_file.read_bytes()
        except OSError as error:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED) from error
        if len(value) != lease.byte_size or _digest(value) != lease.digest:
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_VALIDATION_FAILED)
        return value

    def cleanup(self, *, input_id: str, task_id: str, agent_role: str) -> str:
        lease = self._leases.get(input_id)
        if lease is None or (task_id, agent_role) != (lease.task_id, lease.agent_role):
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_HANDOFF_DENIED)
        self._remove_directory(lease.handoff_directory)
        if lease.handoff_directory.exists():
            raise PrivateInputError(HandoffOutcome.PRIVATE_INPUT_CLEANUP_FAILED)
        del self._leases[input_id]
        del self._registry[input_id]
        return "CLEANUP_COMPLETE"

    @staticmethod
    def _remove_directory(directory: Path) -> None:
        try:
            if directory.exists():
                for child in directory.iterdir():
                    child.chmod(stat.S_IWRITE | stat.S_IREAD)
                    child.unlink()
                directory.rmdir()
        except OSError:
            return
