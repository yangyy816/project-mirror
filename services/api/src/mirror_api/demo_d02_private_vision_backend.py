"""Private, fail-closed Windows Face Landmarker adapter for the D02 runtime.

This module deliberately receives every private path from its caller.  It does
not discover, log, return, or persist a private locator, image byte, landmark,
or process payload.  Its only public result is the existing ``BackendM3Result``
shape consumed by the tracked D02-R2 executor.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import stat
import subprocess
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, NoReturn, cast

from mirror_api import demo_d02_r2_authority as authority
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_measurement_quality as measurement
from mirror_api.image_sanitizer import decode_canonical_rgb_image

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_ID_RE: Final = re.compile(r"[0-9a-f]{32}\Z")
_DECIMAL_RE: Final = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_MAX_STDOUT_BYTES: Final = 256_000
_MAX_STDERR_BYTES: Final = 64_000
_DEFAULT_TIMEOUT_SECONDS: Final = 30.0
_REPARSE_POINT: Final = 0x0400
_LANDMARK_SCHEMA: Final = "mirror.demo/D02FaceLandmarkerRawLandmarks/v1"
_RECEIPT_SCHEMA: Final = "mirror.demo/D02PrivateFaceLandmarkerExecutionReceipt/v1"
_PROVISIONAL_STATE: Final = "PROVISIONAL_SINGLE_CANDIDATE_INSPECTION"
_CANDIDATE_INSPECTION_SCHEMA: Final = "mirror.demo/D02CandidateM3Inspection/v1"
_CANDIDATE_INSPECTION_FACTORY_TOKEN: Final = object()
_PREPARED_SOURCE_FACTORY_TOKEN: Final = object()

_ACCEPTED_ARTIFACT_DIGESTS: Final[dict[str, str]] = {
    "executable": "d7d656252b4311fc617802340bd81f0350805f481092f28774f32f9496794e83",
    "face_landmarker_dll": "1c67ae02b90a5b00b58018c3c04db411134d781c6f53b195e68a6ce6136615ef",
    "opencv_core_dll": "e0415de8bd7dd97f1c2bcccfba627fe6efe4da9441c9b4c9772f3f4faa8f4343",
    "opencv_imgproc_dll": "1aa54040e263be7685f2b8a379cf1f34a275b0718cc8b3a823a1f935c28592b4",
    "model": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
}


class PrivateVisionBackendError(ValueError):
    """A private runtime precondition or execution failed without disclosure."""


def _fail() -> NoReturn:
    raise PrivateVisionBackendError("private face landmarker execution failed")


@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    """Redacted process result supplied by the bounded runner seam."""

    returncode: int
    stdout: bytes
    stderr: bytes


ProcessRunner = Callable[[tuple[str, ...], float, int], ProcessOutcome]


@dataclass(frozen=True, slots=True, init=False)
class CandidateOneShotInspection:
    """A deliberately non-certifying candidate pre-screen result."""

    result: runtime.BackendM3Result
    state: str
    inspection_digest: str

    def __init__(
        self,
        *,
        result: runtime.BackendM3Result,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _CANDIDATE_INSPECTION_FACTORY_TOKEN:
            raise TypeError("CandidateOneShotInspection must be issued by the private backend")
        digest = measurement.mirror_demo_digest(
            _CANDIDATE_INSPECTION_SCHEMA,
            {
                "state": _PROVISIONAL_STATE,
                "payload_schema": result.payload_schema,
                "fields": cast(dict[str, measurement.JsonValue], dict(result.fields)),
            },
        )
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "state", _PROVISIONAL_STATE)
        object.__setattr__(self, "inspection_digest", digest)


@dataclass(frozen=True, slots=True, init=False)
class PreparedSourceM3Group:
    """Three real source executions prepared before case-plan construction."""

    descriptor_digest: str
    landmark_digest: str
    landmarks: tuple[tuple[float, float, float], ...]
    outputs: tuple[runtime.BackendM3Result, runtime.BackendM3Result, runtime.BackendM3Result]

    def __init__(
        self,
        *,
        descriptor_digest: str,
        landmark_digest: str,
        landmarks: tuple[tuple[float, float, float], ...],
        outputs: tuple[runtime.BackendM3Result, runtime.BackendM3Result, runtime.BackendM3Result],
        _factory_token: object,
    ) -> None:
        if _factory_token is not _PREPARED_SOURCE_FACTORY_TOKEN:
            raise TypeError("PreparedSourceM3Group must be issued by the private backend")
        if (
            _DIGEST_RE.fullmatch(descriptor_digest) is None
            or _DIGEST_RE.fullmatch(landmark_digest) is None
        ):
            _fail()
        if len(landmarks) != 478:
            _fail()
        object.__setattr__(self, "descriptor_digest", descriptor_digest)
        object.__setattr__(self, "landmark_digest", landmark_digest)
        object.__setattr__(self, "landmarks", landmarks)
        object.__setattr__(self, "outputs", outputs)


@dataclass(slots=True)
class _RepeatGroup:
    canonical_digest: str
    outputs: tuple[runtime.BackendM3Result, runtime.BackendM3Result, runtime.BackendM3Result]
    landmarks: tuple[tuple[float, float, float], ...]
    delivered: set[int]
    rearm_used: bool


class WindowsFaceLandmarkerOfflineM3Backend:
    """Accepted private Windows runtime with exactly-three formal M3 repeats.

    The accepted constructor validates fixed tracked digests.  ``for_testing``
    is intentionally separate and only exists to inject a deterministic runner
    without requiring private artifacts in repository tests.
    """

    execution_runtime_set_digest: str = measurement.RUNTIME_MANIFEST_DIGEST
    model_identity_digest: str
    model_config_digest: str
    weights_digest_or_no_weights: str = measurement.VISION_MODEL_MANIFEST_DIGEST
    network_policy: str = runtime.NETWORK_POLICY

    def __init__(
        self,
        *,
        executable: Path,
        model: Path,
        staging_root: Path,
        runner: ProcessRunner,
    ) -> None:
        model_identity = runtime.build_default_model_identity()
        self.model_identity_digest = model_identity.identity_digest
        self.model_config_digest = model_identity.config_digest
        self._executable = executable
        self._model = model
        self._staging_root = staging_root
        self._runner = runner
        self._timeout_seconds = _DEFAULT_TIMEOUT_SECONDS
        self._source_groups: dict[object, _RepeatGroup] = {}
        self._result_groups: dict[object, _RepeatGroup] = {}
        self._candidate_seen: set[tuple[str, str, str]] = set()
        self._accepted_artifacts: tuple[tuple[Path, str], ...] = ()
        self._landmarks_by_receipt: dict[str, tuple[tuple[float, float, float], ...]] = {}
        self._lock = threading.RLock()

    @classmethod
    def from_accepted_windows_artifacts(
        cls,
        *,
        executable: Path,
        face_landmarker_dll: Path,
        opencv_core_dll: Path,
        opencv_imgproc_dll: Path,
        model: Path,
        staging_root: Path,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> WindowsFaceLandmarkerOfflineM3Backend:
        if os.name != "nt":
            _fail()
        if (
            not isinstance(timeout_seconds, float)
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            _fail()
        artifacts = {
            "executable": executable,
            "face_landmarker_dll": face_landmarker_dll,
            "opencv_core_dll": opencv_core_dll,
            "opencv_imgproc_dll": opencv_imgproc_dll,
            "model": model,
        }
        validated = {
            name: _validate_accepted_file(path, _ACCEPTED_ARTIFACT_DIGESTS[name])
            for name, path in artifacts.items()
        }
        root = _validate_private_directory(staging_root)
        backend = cls(
            executable=validated["executable"],
            model=validated["model"],
            staging_root=root,
            runner=_subprocess_runner,
        )
        backend._accepted_artifacts = tuple(
            (validated[name], _ACCEPTED_ARTIFACT_DIGESTS[name]) for name in sorted(validated)
        )
        backend._timeout_seconds = timeout_seconds
        return backend

    @classmethod
    def for_testing(
        cls,
        *,
        staging_root: Path,
        runner: ProcessRunner,
    ) -> WindowsFaceLandmarkerOfflineM3Backend:
        """Create a test-only backend; never use it for a private runtime."""

        backend = cls(
            executable=_validate_private_directory(staging_root) / "test-wrapper.exe",
            model=_validate_private_directory(staging_root) / "test-model.task",
            staging_root=_validate_private_directory(staging_root),
            runner=runner,
        )
        backend._timeout_seconds = _DEFAULT_TIMEOUT_SECONDS
        return backend

    def inspect_source(
        self,
        *,
        content: bytes,
        descriptor: runtime.DurableSourceDescriptor,
        repeat_index: int,
    ) -> runtime.BackendM3Result:
        if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
            _fail()
        canonical_digest = _canonical_source(content, descriptor)
        subject = {
            "schema_version": measurement.SOURCE_SUBJECT_SCHEMA,
            "source_output_id": descriptor.source_output_id,
            "source_asset_id": descriptor.source_id,
            "source_asset_sha256": canonical_digest,
        }
        key = (descriptor.source_output_id, descriptor.source_id, canonical_digest)
        return self._formal_repeat(
            groups=self._source_groups,
            key=key,
            repeat_index=repeat_index,
            content=content,
            width=descriptor.width,
            height=descriptor.height,
            role="SOURCE",
            subject=subject,
        )

    def inspect_result(
        self,
        *,
        content: bytes,
        case_entry: Mapping[str, object],
        repeat_index: int,
    ) -> runtime.BackendM3Result:
        if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
            _fail()
        case_id = _require_id(case_entry.get("case_id"))
        specification = _require_digest(case_entry.get("case_specification_digest"))
        width = _require_positive_int(case_entry.get("output_width"))
        height = _require_positive_int(case_entry.get("output_height"))
        canonical_digest = _canonical_result(content, width=width, height=height)
        result_output_id = f"m4-{case_id}"
        subject = {
            "schema_version": measurement.RESULT_SUBJECT_SCHEMA,
            "case_id": case_id,
            "case_specification_digest": specification,
            "result_output_id": result_output_id,
            "result_sha256": canonical_digest,
        }
        key = (case_id, specification, result_output_id, canonical_digest)
        return self._formal_repeat(
            groups=self._result_groups,
            key=key,
            repeat_index=repeat_index,
            content=content,
            width=width,
            height=height,
            role="RESULT",
            subject=subject,
        )

    def inspect_candidate_once(
        self,
        *,
        content: bytes,
        descriptor: runtime.DurableSourceDescriptor,
    ) -> CandidateOneShotInspection:
        """Run one provisional candidate pre-screen; it cannot certify repeats."""

        canonical_digest = _canonical_source(content, descriptor)
        subject = {
            "schema_version": measurement.SOURCE_SUBJECT_SCHEMA,
            "source_output_id": descriptor.source_output_id,
            "source_asset_id": descriptor.source_id,
            "source_asset_sha256": canonical_digest,
        }
        key = (descriptor.source_output_id, descriptor.source_id, canonical_digest)
        with self._lock:
            if key in self._candidate_seen or key in self._source_groups:
                _fail()
            self._candidate_seen.add(key)
        result = self._execute(
            content=content,
            width=descriptor.width,
            height=descriptor.height,
            role="SOURCE",
            subject=subject,
            repeat_index=1,
        )
        return CandidateOneShotInspection(
            result=result,
            _factory_token=_CANDIDATE_INSPECTION_FACTORY_TOKEN,
        )

    def prepare_source_group(
        self,
        *,
        content: bytes,
        descriptor: runtime.DurableSourceDescriptor,
    ) -> PreparedSourceM3Group:
        """Execute exactly three source repeats without marking any as delivered."""

        canonical_digest = _canonical_source(content, descriptor)
        subject = {
            "schema_version": measurement.SOURCE_SUBJECT_SCHEMA,
            "source_output_id": descriptor.source_output_id,
            "source_asset_id": descriptor.source_id,
            "source_asset_sha256": canonical_digest,
        }
        key = (descriptor.source_output_id, descriptor.source_id, canonical_digest)
        with self._lock:
            if key in self._candidate_seen:
                _fail()
            group = self._ensure_formal_group(
                groups=self._source_groups,
                key=key,
                content=content,
                width=descriptor.width,
                height=descriptor.height,
                role="SOURCE",
                subject=subject,
            )
            if group.delivered:
                _fail()
            return PreparedSourceM3Group(
                descriptor_digest=descriptor.descriptor_digest,
                landmark_digest=cast(str, group.outputs[0].fields["landmark_digest"]),
                landmarks=group.landmarks,
                outputs=group.outputs,
                _factory_token=_PREPARED_SOURCE_FACTORY_TOKEN,
            )

    def rearm_prepared_source_group(
        self,
        *,
        prepared: PreparedSourceM3Group,
        descriptor: runtime.DurableSourceDescriptor,
    ) -> None:
        """Permit one cached replay after formal facts are built from the first cycle."""

        if type(prepared) is not PreparedSourceM3Group:
            _fail()
        key = (descriptor.source_output_id, descriptor.source_id, descriptor.content_sha256)
        with self._lock:
            group = self._source_groups.get(key)
            if (
                group is None
                or group.outputs != prepared.outputs
                or group.delivered != {1, 2, 3}
                or group.rearm_used
            ):
                _fail()
            group.delivered.clear()
            group.rearm_used = True

    def _formal_repeat(
        self,
        *,
        groups: dict[object, _RepeatGroup],
        key: object,
        repeat_index: int,
        content: bytes,
        width: int,
        height: int,
        role: Literal["SOURCE", "RESULT"],
        subject: Mapping[str, object],
    ) -> runtime.BackendM3Result:
        with self._lock:
            group = groups.get(key)
            if group is None and (
                repeat_index != 1
                or (role == "SOURCE" and cast(tuple[str, str, str], key) in self._candidate_seen)
            ):
                _fail()
            group = self._ensure_formal_group(
                groups=groups,
                key=key,
                content=content,
                width=width,
                height=height,
                role=role,
                subject=subject,
            )
            if repeat_index in group.delivered:
                _fail()
            group.delivered.add(repeat_index)
            return group.outputs[repeat_index - 1]

    def _ensure_formal_group(
        self,
        *,
        groups: dict[object, _RepeatGroup],
        key: object,
        content: bytes,
        width: int,
        height: int,
        role: Literal["SOURCE", "RESULT"],
        subject: Mapping[str, object],
    ) -> _RepeatGroup:
        group = groups.get(key)
        if group is not None:
            return group
        canonical_digest = _require_digest(
            subject.get("source_asset_sha256") if role == "SOURCE" else subject.get("result_sha256")
        )
        outputs = cast(
            tuple[runtime.BackendM3Result, runtime.BackendM3Result, runtime.BackendM3Result],
            tuple(
                self._execute(
                    content=content,
                    width=width,
                    height=height,
                    role=role,
                    subject=subject,
                    repeat_index=index,
                )
                for index in (1, 2, 3)
            ),
        )
        if len({output.fields["landmark_digest"] for output in outputs}) != 1:
            _fail()
        first_receipt = cast(str, outputs[0].fields["execution_receipt_digest"])
        landmarks = self._landmarks_by_receipt.get(first_receipt)
        if landmarks is None:
            _fail()
        group = _RepeatGroup(
            canonical_digest=canonical_digest,
            outputs=outputs,
            landmarks=landmarks,
            delivered=set(),
            rearm_used=False,
        )
        groups[key] = group
        return group

    def _execute(
        self,
        *,
        content: bytes,
        width: int,
        height: int,
        role: Literal["SOURCE", "RESULT"],
        subject: Mapping[str, object],
        repeat_index: int,
    ) -> runtime.BackendM3Result:
        self._revalidate_private_runtime()
        decoded = decode_canonical_rgb_image(content, expected_width=width, expected_height=height)
        rgb_path = self._create_rgb_file(decoded.bytes_value)
        try:
            outcome = self._runner(
                (str(self._executable), str(self._model), str(rgb_path), str(width), str(height)),
                self._timeout_seconds,
                _MAX_STDOUT_BYTES,
            )
            tokens = _parse_success(outcome)
        except PrivateVisionBackendError:
            raise
        except Exception:
            _fail()
        finally:
            _remove_exact(rgb_path)
        landmark_digest = measurement.mirror_demo_digest(
            _LANDMARK_SCHEMA,
            {"landmarks": [dict(item) for item in tokens]},
        )
        xy = {index: {"x": token["x"], "y": token["y"]} for index, token in enumerate(tokens)}
        bindings = measurement.default_authority_bindings()
        canonical_digest = _require_digest(
            subject.get("source_asset_sha256") if role == "SOURCE" else subject.get("result_sha256")
        )
        try:
            observation = measurement.build_measurement_observation(
                observation_role=role,
                subject=subject,
                canonical_output_digest=canonical_digest,
                landmark_digest=landmark_digest,
                bindings=bindings,
                measurement_landmarks=xy,
                ordered_observability_repeats=(xy, xy, xy),
            )
        except (TypeError, ValueError):
            _fail()
        receipt = measurement.mirror_demo_digest(
            _RECEIPT_SCHEMA,
            {
                "role": role,
                "repeat_index": repeat_index,
                "canonical_output_digest": canonical_digest,
                "landmark_digest": landmark_digest,
                "runtime_manifest_digest": measurement.RUNTIME_MANIFEST_DIGEST,
                "vision_model_manifest_digest": measurement.VISION_MODEL_MANIFEST_DIGEST,
            },
        )
        self._landmarks_by_receipt[receipt] = tuple(
            (float(token["x"]), float(token["y"]), float(token["z"])) for token in tokens
        )
        fields: dict[str, object] = {
            "execution_receipt_digest": receipt,
            "vision_model_manifest_digest": measurement.VISION_MODEL_MANIFEST_DIGEST,
            "topology_digest": measurement.TOPOLOGY_DIGEST,
            "canonical_output_digest": canonical_digest,
            "landmark_digest": landmark_digest,
            "measurement_observation": observation,
            "measurement_observation_digest": observation["measurement_observation_digest"],
            "face_count": 1,
            "landmark_count": 478,
            "coordinates_finite": True,
            "coordinates_in_bounds": True,
            "repeat_gate_passed": True,
        }
        if role == "SOURCE":
            fields["runtime_manifest_digest"] = measurement.RUNTIME_MANIFEST_DIGEST
            schema = authority.R2_SOURCE_M3_SCHEMA
        else:
            fields["observation_state"] = _observation_state(observation)
            schema = authority.R2_RESULT_M3_SCHEMA
        return runtime.BackendM3Result(payload_schema=schema, fields=fields)

    def _revalidate_private_runtime(self) -> None:
        if not self._accepted_artifacts:
            return
        _validate_private_directory(self._staging_root)
        for path, digest in self._accepted_artifacts:
            _validate_accepted_file(path, digest)

    def _create_rgb_file(self, rgb: bytes) -> Path:
        if type(rgb) is not bytes or not rgb:
            _fail()
        path = self._staging_root / f"d02-{uuid.uuid4().hex}.rgb"
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(rgb)
                handle.flush()
                os.fsync(handle.fileno())
            return path
        except (OSError, ValueError):
            _remove_exact(path)
            _fail()


def _canonical_source(content: bytes, descriptor: runtime.DurableSourceDescriptor) -> str:
    if (
        type(content) is not bytes
        or hashlib.sha256(content).hexdigest() != descriptor.content_sha256
    ):
        _fail()
    try:
        decode_canonical_rgb_image(
            content, expected_width=descriptor.width, expected_height=descriptor.height
        )
    except ValueError:
        _fail()
    return descriptor.content_sha256


def _canonical_result(content: bytes, *, width: int, height: int) -> str:
    if type(content) is not bytes:
        _fail()
    try:
        decode_canonical_rgb_image(content, expected_width=width, expected_height=height)
    except ValueError:
        _fail()
    return hashlib.sha256(content).hexdigest()


def _parse_success(outcome: object) -> tuple[dict[str, str], ...]:
    if not isinstance(outcome, ProcessOutcome) or outcome.returncode != 0:
        _fail()
    if (
        type(outcome.stdout) is not bytes
        or type(outcome.stderr) is not bytes
        or len(outcome.stdout) > _MAX_STDOUT_BYTES
        or len(outcome.stderr) > _MAX_STDERR_BYTES
    ):
        _fail()
    _validate_bounded_stderr(outcome.stderr)
    try:
        lines = outcome.stdout.decode("ascii", errors="strict").splitlines()
    except UnicodeDecodeError:
        _fail()
    if len(lines) != 8:
        _fail()
    if (
        lines[0] != "detect_status=ok"
        or lines[1] != "face_count=1"
        or not lines[2].startswith("detect_latency_us=")
        or lines[3] != "face_0_landmark_count=478"
        or not lines[4].startswith("face_0_landmarks=")
        or lines[5] != "matrix_count=1"
        or not lines[6].startswith("matrix_0=")
        or lines[7] != "close_status=ok"
    ):
        _fail()
    latency = lines[2].removeprefix("detect_latency_us=")
    if not latency.isascii() or not latency.isdecimal() or not 0 <= int(latency) <= 30_000_000:
        _fail()
    matrix_tokens = lines[6].removeprefix("matrix_0=").split(",")
    if len(matrix_tokens) != 18 or any(
        _DECIMAL_RE.fullmatch(token) is None for token in matrix_tokens
    ):
        _fail()
    try:
        matrix = tuple(measurement.parse_raw_decimal_token(token) for token in matrix_tokens)
    except ValueError:
        _fail()
    if not all(value.is_finite() for value in matrix):
        _fail()
    points = lines[4].removeprefix("face_0_landmarks=").split(";")
    if len(points) != 478 or any(not point for point in points):
        _fail()
    parsed: list[dict[str, str]] = []
    for point in points:
        values = point.split(",")
        if len(values) != 3 or any(_DECIMAL_RE.fullmatch(value) is None for value in values):
            _fail()
        try:
            numeric = tuple(measurement.parse_raw_decimal_token(value) for value in values)
        except ValueError:
            _fail()
        if not all(value.is_finite() for value in numeric) or not (
            0 <= numeric[0] <= 1 and 0 <= numeric[1] <= 1
        ):
            _fail()
        parsed.append({"x": values[0], "y": values[1], "z": values[2]})
    return tuple(parsed)


def _validate_bounded_stderr(value: bytes) -> None:
    if b"\x00" in value:
        _fail()
    try:
        text = value.decode("ascii", errors="strict")
    except UnicodeDecodeError:
        _fail()
    lines = text.splitlines()
    if len(lines) > 64 or any(len(line) > 1024 for line in lines):
        _fail()
    if any(character not in "\t\r\n" and not 32 <= ord(character) <= 126 for character in text):
        _fail()


def _observation_state(observation: Mapping[str, object]) -> str:
    entries = observation.get("ordered_measurements")
    if not isinstance(entries, Sequence):
        _fail()
    return (
        "UNSUPPORTED_EXPLICIT"
        if any(
            isinstance(entry, Mapping) and entry.get("support_state") == "UNSUPPORTED"
            for entry in entries
        )
        else "SUPPORTED"
    )


def _require_digest(value: object) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail()
    return value


def _require_id(value: object) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        _fail()
    return value


def _require_positive_int(value: object) -> int:
    if type(value) is not int or value < 1:
        _fail()
    return value


def _validate_private_directory(path: Path) -> Path:
    resolved = _validate_path(path, directory=True)
    return resolved


def _validate_accepted_file(path: Path, expected_digest: str) -> Path:
    resolved = _validate_path(path, directory=False)
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(resolved, flags)
        try:
            opened = os.fstat(descriptor)
            after = os.stat(resolved, follow_symlinks=False)
            if not stat.S_ISREG(opened.st_mode) or not _same_file_identity(opened, after):
                _fail()
            digest = hashlib.sha256()
            while block := os.read(descriptor, 1024 * 1024):
                digest.update(block)
        finally:
            os.close(descriptor)
    except PrivateVisionBackendError:
        raise
    except OSError:
        _fail()
    if digest.hexdigest() != expected_digest:
        _fail()
    return resolved


def _validate_path(path: Path, *, directory: bool) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        _fail()
    try:
        lexical = Path(os.path.abspath(os.fspath(path)))
        resolved = lexical.resolve(strict=True)
        if os.path.normcase(str(lexical)) != os.path.normcase(str(resolved)):
            _fail()
        for component in _path_components(lexical):
            metadata = os.lstat(component)
            if (
                stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
            ):
                _fail()
        metadata = os.stat(resolved, follow_symlinks=False)
        if directory:
            if not stat.S_ISDIR(metadata.st_mode):
                _fail()
        elif not stat.S_ISREG(metadata.st_mode):
            _fail()
        return resolved
    except PrivateVisionBackendError:
        raise
    except (OSError, RuntimeError, ValueError):
        _fail()


def _path_components(path: Path) -> tuple[Path, ...]:
    parts = path.parts
    if not parts:
        _fail()
    current = Path(parts[0])
    components = [current]
    for part in parts[1:]:
        current = current / part
        components.append(current)
    return tuple(components)


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and left.st_size == right.st_size
        and stat.S_ISREG(left.st_mode)
        and stat.S_ISREG(right.st_mode)
    )


def _remove_exact(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        _fail()


def _subprocess_runner(command: tuple[str, ...], timeout: float, _: int) -> ProcessOutcome:
    try:
        completed = subprocess.run(  # noqa: S603 - accepted fixed executable is digest-verified
            command,
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        _fail()
    return ProcessOutcome(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
