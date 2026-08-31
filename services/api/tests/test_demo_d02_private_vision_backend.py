from __future__ import annotations

import hashlib
import io
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from mirror_api import demo_d02_private_vision_backend as private_backend
from mirror_api import demo_d02_r2_authority as authority
from mirror_api import demo_d02_r2_runtime_forward as runtime


def _jpeg() -> bytes:
    image = Image.new("RGB", (64, 64), (80, 110, 140))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=95, subsampling=0)
    return output.getvalue()


def _descriptor(content: bytes) -> runtime.DurableSourceDescriptor:
    return runtime.DurableSourceDescriptor(
        source_id="a" * 32,
        source_output_id="d02-source-a",
        ordinal=1,
        content_sha256=hashlib.sha256(content).hexdigest(),
        media_type="image/jpeg",
        width=64,
        height=64,
        byte_length=len(content),
        generation_request_identity="b" * 64,
        provenance_identity="c" * 64,
        source_authority_key="d" * 64,
        source_schema_version="mirror.demo/TestSource/v1",
    )


def _stdout(*, invalid_token: bool = False, extra_face: bool = False) -> bytes:
    points = []
    for index in range(478):
        x = f"{(index % 20 + 1) / 30:.6f}"
        y = f"{(index // 20 + 1) / 30:.6f}"
        points.append(f"{x},{y},0.000000")
    if invalid_token:
        points[10] = "NaN,0.100000,0.000000"
    lines = [
        "create_status=ok",
        "detect_status=ok",
        "face_count=1",
        f"face_0_landmarks={';'.join(points)}",
        "close_status=ok",
    ]
    if extra_face:
        lines.insert(4, "face_1_landmarks=unexpected")
    return "\n".join(lines).encode("ascii")


def _runner(
    calls: list[tuple[str, ...]], *, stdout: bytes | None = None
) -> Callable[[tuple[str, ...], float, int], private_backend.ProcessOutcome]:
    def run(command: tuple[str, ...], _: float, __: int) -> private_backend.ProcessOutcome:
        calls.append(command)
        assert Path(command[2]).is_file()
        return private_backend.ProcessOutcome(returncode=0, stdout=stdout or _stdout(), stderr=b"")

    return run


def test_source_formal_group_runs_three_times_then_returns_cached_outputs(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    content = _jpeg()
    backend = private_backend.WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=tmp_path, runner=_runner(calls)
    )
    descriptor = _descriptor(content)

    first = backend.inspect_source(content=content, descriptor=descriptor, repeat_index=1)
    second = backend.inspect_source(content=content, descriptor=descriptor, repeat_index=2)
    third = backend.inspect_source(content=content, descriptor=descriptor, repeat_index=3)

    assert len(calls) == 3
    assert first.fields["landmark_digest"] == second.fields["landmark_digest"]
    assert first.fields["landmark_digest"] == third.fields["landmark_digest"]
    assert first.fields["execution_receipt_digest"] != second.fields["execution_receipt_digest"]
    assert not list(tmp_path.glob("*.rgb"))
    assert runtime.M3ExecutionOutput.create(first).payload_schema == first.payload_schema
    with pytest.raises(private_backend.PrivateVisionBackendError):
        backend.inspect_source(content=content, descriptor=descriptor, repeat_index=2)


def test_prepared_source_group_exposes_plan_landmarks_without_consuming_repeats(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []
    content = _jpeg()
    descriptor = _descriptor(content)
    backend = private_backend.WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=tmp_path,
        runner=_runner(calls),
    )

    prepared = backend.prepare_source_group(content=content, descriptor=descriptor)
    outputs = [
        backend.inspect_source(content=content, descriptor=descriptor, repeat_index=index)
        for index in (1, 2, 3)
    ]

    assert len(calls) == 3
    assert len(prepared.landmarks) == 478
    assert prepared.descriptor_digest == descriptor.descriptor_digest
    assert {output.fields["landmark_digest"] for output in outputs} == {prepared.landmark_digest}
    backend.rearm_prepared_source_group(prepared=prepared, descriptor=descriptor)
    replayed = [
        backend.inspect_source(content=content, descriptor=descriptor, repeat_index=index)
        for index in (1, 2, 3)
    ]
    assert len(calls) == 3
    assert replayed == outputs
    with pytest.raises(private_backend.PrivateVisionBackendError):
        backend.rearm_prepared_source_group(prepared=prepared, descriptor=descriptor)


def test_candidate_inspection_cannot_be_constructed_by_a_caller() -> None:
    with pytest.raises(TypeError, match="must be issued"):
        private_backend.CandidateOneShotInspection(
            result=runtime.BackendM3Result(
                payload_schema=authority.R2_SOURCE_M3_SCHEMA,
                fields={},
            ),
            _factory_token=object(),
        )


def test_formal_group_rejects_out_of_order_and_candidate_cannot_certify(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    content = _jpeg()
    backend = private_backend.WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=tmp_path, runner=_runner(calls)
    )
    descriptor = _descriptor(content)
    with pytest.raises(private_backend.PrivateVisionBackendError):
        backend.inspect_source(content=content, descriptor=descriptor, repeat_index=2)

    provisional = backend.inspect_candidate_once(content=content, descriptor=descriptor)
    assert provisional.state == "PROVISIONAL_SINGLE_CANDIDATE_INSPECTION"
    assert len(calls) == 1
    with pytest.raises(private_backend.PrivateVisionBackendError):
        backend.inspect_source(content=content, descriptor=descriptor, repeat_index=1)


def test_result_group_has_result_schema_and_observation_state(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    content = _jpeg()
    backend = private_backend.WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=tmp_path, runner=_runner(calls)
    )
    case = {
        "case_id": "e" * 32,
        "case_specification_digest": "f" * 64,
        "output_width": 64,
        "output_height": 64,
    }
    result = backend.inspect_result(content=content, case_entry=case, repeat_index=1)
    assert result.payload_schema == authority.R2_RESULT_M3_SCHEMA
    assert result.fields["observation_state"] in {"SUPPORTED", "UNSUPPORTED_EXPLICIT"}
    assert len(calls) == 3


@pytest.mark.parametrize(
    "stdout",
    [_stdout(invalid_token=True), _stdout(extra_face=True), b"create_status=ok\n"],
)
def test_invalid_or_partial_process_output_fails_closed(tmp_path: Path, stdout: bytes) -> None:
    calls: list[tuple[str, ...]] = []
    content = _jpeg()
    backend = private_backend.WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=tmp_path, runner=_runner(calls, stdout=stdout)
    )
    with pytest.raises(private_backend.PrivateVisionBackendError) as error:
        backend.inspect_source(content=content, descriptor=_descriptor(content), repeat_index=1)
    assert str(tmp_path) not in str(error.value)
    assert len(calls) == 1
    assert not list(tmp_path.glob("*.rgb"))


def test_runner_timeout_and_artifact_digest_mismatch_fail_closed(tmp_path: Path) -> None:
    content = _jpeg()

    def timeout(_: tuple[str, ...], __: float, ___: int) -> private_backend.ProcessOutcome:
        raise TimeoutError("private-path-must-not-leak")

    backend = private_backend.WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=tmp_path, runner=timeout
    )
    with pytest.raises(private_backend.PrivateVisionBackendError) as error:
        backend.inspect_source(content=content, descriptor=_descriptor(content), repeat_index=1)
    assert "private-path" not in str(error.value)

    files = {}
    for name in ("wrapper.exe", "landmarker.dll", "core.dll", "imgproc.dll", "model.task"):
        path = tmp_path / name
        path.write_bytes(b"not-the-accepted-artifact")
        files[name] = path
    with pytest.raises(private_backend.PrivateVisionBackendError):
        private_backend.WindowsFaceLandmarkerOfflineM3Backend.from_accepted_windows_artifacts(
            executable=files["wrapper.exe"],
            face_landmarker_dll=files["landmarker.dll"],
            opencv_core_dll=files["core.dll"],
            opencv_imgproc_dll=files["imgproc.dll"],
            model=files["model.task"],
            staging_root=tmp_path,
        )
