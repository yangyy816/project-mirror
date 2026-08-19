"""Synthetic-only tests for the CC02-B manifest builder."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_BUILDER = Path(__file__).parents[3] / "scripts/research/build_p2_m5_cc02_manifest.py"
_SPEC = importlib.util.spec_from_file_location("cc02_manifest_builder", _BUILDER)
assert _SPEC is not None and _SPEC.loader is not None
cc02 = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = cc02
_SPEC.loader.exec_module(cc02)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _case(index: int, platform: str, failed: bool, direction_case: bool) -> dict[str, Any]:
    identity_index, descriptor_index = divmod(index, 24)
    candidate_index, direction_magnitude_index = divmod(descriptor_index, 4)
    direction_index, magnitude_index = divmod(direction_magnitude_index, 2)
    case = {
        "case_digest": _digest(f"case-{index}"),
        "identity_reference": f"private-{identity_index}",
        "candidate": cc02.CANDIDATES[candidate_index],
        "direction": cc02.DIRECTIONS[direction_index],
        "magnitude_ppm": cc02.MAGNITUDES[magnitude_index],
        "status": "FAILED" if failed else "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW",
        "executed_repeat_count": 0 if failed else 3,
    }
    if failed:
        case.update(
            {
                "failure_stage": "MEASUREMENT" if direction_case else "TRANSFORM",
                "failure_code": "TARGET_DIRECTION_MISMATCH"
                if direction_case
                else "TRANSFORM_RUNTIME_REJECTED",
            }
        )
    return case


def _row(case: dict[str, Any], repeat: int, platform: str) -> dict[str, Any]:
    seed = f"{case['case_digest']}-{repeat}-{platform}"
    return {
        "case_digest": case["case_digest"],
        "identity_reference": case["identity_reference"],
        "candidate": case["candidate"],
        "direction": case["direction"],
        "magnitude_ppm": case["magnitude_ppm"],
        "repeat": repeat,
        "status": "PASSED",
        "source_sha256": _digest(seed + "source"),
        "result_sha256": _digest(seed + "result"),
        "result_artifact": "private-artifact",
        "plan_digest": _digest(seed + "plan"),
        "source_measurements": {candidate: 1.0 for candidate in cc02.CANDIDATES},
        "result_measurements": {candidate: 1.1 for candidate in cc02.CANDIDATES},
        "vision_log_sha256": _digest(seed + "vision"),
        "vision_log_artifact": "private-log",
        "phash_hex": "0" * 16,
        "changed_pixel_count": 1,
    }


def _report(platform: str) -> dict[str, Any]:
    cases = [_case(index, platform, index < 116, index < 7) for index in range(288)]
    rows = [
        _row(case, repeat, platform)
        for case in cases
        if case["status"] != "FAILED"
        for repeat in (1, 2, 3)
    ]
    runtime = (
        "27b33d646d8587f76d5ca317ac9d6aec95bc04fd87d413bb3dd6394f9694bb7a"
        if platform == "windows_x86_64"
        else "5d0e9ee323d7daea78e8baaeec63917c7a1867301ec5f7c71685fa9cbed311d8"
    )
    report = {
        "schema": cc02.LEGACY_REPORT_SCHEMA,
        "platform": platform,
        "runtime_manifest_digest": runtime,
        "candidate_manifest_digest": cc02._CANDIDATE_MANIFEST_DIGEST,
        "model_sha256": cc02._MODEL_DIGEST,
        "topology_sha256": cc02._TOPOLOGY_DIGEST,
        "triangle_count": 852,
        "stage_b_evidence_sha256": cc02._STAGE_B_EVIDENCE_DIGEST,
        "cohort_digest": cc02._COHORT_DIGEST,
        "input_manifest_digest": cc02._CANDIDATE_MANIFEST_DIGEST,
        "case_set_digest": cc02._CASE_SET_DIGEST,
        "cases": cases,
        "rows": rows,
    }
    report["report_digest"] = cc02.canonical_digest(
        cc02.LEGACY_REPORT_SCHEMA, report, "report_digest"
    )
    return report


def _inputs() -> tuple[bytes, bytes, Any]:
    windows, linux = _report("windows_x86_64"), _report("linux_x86_64_network_none")
    windows_bytes = json.dumps(windows, sort_keys=True).encode()
    linux_bytes = json.dumps(linux, sort_keys=True).encode()
    authority = cc02._ManifestAuthority(
        windows_report_digest=windows["report_digest"], linux_report_digest=linux["report_digest"]
    )
    return windows_bytes, linux_bytes, authority


def _refreshed(report: dict[str, Any]) -> bytes:
    report["report_digest"] = cc02.canonical_digest(
        cc02.LEGACY_REPORT_SCHEMA, report, "report_digest"
    )
    return json.dumps(report, sort_keys=True).encode()


def _authority(windows: bytes, linux: bytes) -> Any:
    return cc02._ManifestAuthority(
        windows_report_digest=json.loads(windows)["report_digest"],
        linux_report_digest=json.loads(linux)["report_digest"],
    )


def test_full_synthetic_projection_is_deterministic_and_exact_byte_bound() -> None:
    windows, linux, authority = _inputs()
    manifest_bytes, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    assert (
        manifest_bytes,
        preregistration,
    ) == cc02._construct_manifest_and_preregistration_with_authority(windows, linux, authority)
    permuted = json.dumps(dict(reversed(list(json.loads(windows).items())))).encode()
    assert permuted != windows
    reordered_manifest_bytes, reordered_preregistration = (
        cc02._construct_manifest_and_preregistration_with_authority(permuted, linux, authority)
    )
    original_manifest, reordered_manifest = (
        json.loads(manifest_bytes),
        json.loads(reordered_manifest_bytes),
    )
    original_windows_binding = original_manifest["platform_report_bindings"][1]
    reordered_windows_binding = reordered_manifest["platform_report_bindings"][1]
    assert (
        original_windows_binding["legacy_report_digest"]
        == reordered_windows_binding["legacy_report_digest"]
    )
    assert (
        original_windows_binding["legacy_report_sha256"]
        != reordered_windows_binding["legacy_report_sha256"]
    )
    for manifest in (original_manifest, reordered_manifest):
        manifest.pop("platform_report_bindings")
        manifest.pop("manifest_content_digest")
    assert original_manifest == reordered_manifest
    assert manifest_bytes != reordered_manifest_bytes
    assert preregistration != reordered_preregistration
    manifest = json.loads(manifest_bytes)
    assert [
        len(manifest[key])
        for key in (
            "platform_report_bindings",
            "platform_case_bindings",
            "legacy_success_repeat_bindings",
            "direction_diagnostic_bindings",
        )
    ] == [2, 576, 1032, 14]
    assert preregistration == cc02._preregistration(manifest)
    assert b"12 identities; 6 candidates" in preregistration
    assert b"7,200 seconds per platform" in preregistration
    assert b"14,400 seconds total" in preregistration
    assert b"4,294,967,296 bytes per platform" in preregistration
    assert "private-0" not in manifest_bytes.decode()
    assert "private-artifact" not in manifest_bytes.decode()


@pytest.mark.parametrize(
    "mutation",
    (
        "schema",
        "authority",
        "digest",
        "extra_key",
        "missing_key",
        "private_field",
        "row_repeat_bool",
        "duplicate_case",
        "missing_row",
        "ambiguous_row",
        "outcome",
    ),
)
def test_schema_authority_and_membership_fail_closed(mutation: str) -> None:
    windows, linux, authority = _inputs()
    value = json.loads(windows)
    if mutation == "schema":
        value["schema"] = "wrong"
    elif mutation == "authority":
        value["cohort_digest"] = _digest("wrong")
    elif mutation == "digest":
        value["report_digest"] = _digest("wrong")
        with pytest.raises(cc02.ManifestBuildError):
            cc02._construct_manifest_and_preregistration_with_authority(
                json.dumps(value).encode(), linux, authority
            )
        return
    elif mutation == "extra_key":
        value["extra"] = "forbidden"
    elif mutation == "missing_key":
        value.pop("rows")
    elif mutation == "private_field":
        value["cases"][0]["private_unapproved"] = "forbidden"
    elif mutation == "row_repeat_bool":
        value["rows"][0]["repeat"] = True
    elif mutation == "duplicate_case":
        value["cases"].append(copy.deepcopy(value["cases"][0]))
    elif mutation == "missing_row":
        value["rows"].pop()
    elif mutation == "ambiguous_row":
        value["rows"].append(copy.deepcopy(value["rows"][0]))
    else:
        other = json.loads(linux)
        other["cases"][0]["status"] = "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW"
        other["cases"][0].pop("failure_stage")
        other["cases"][0].pop("failure_code")
        other["cases"][0]["executed_repeat_count"] = 3
        for repeat in (1, 2, 3):
            other["rows"].append(_row(other["cases"][0], repeat, "linux_x86_64_network_none"))
        other["report_digest"] = cc02.canonical_digest(
            cc02.LEGACY_REPORT_SCHEMA, other, "report_digest"
        )
        linux = json.dumps(other, sort_keys=True).encode()
        authority = cc02._ManifestAuthority(
            windows_report_digest=json.loads(windows)["report_digest"],
            linux_report_digest=other["report_digest"],
        )
    if mutation != "outcome":
        value["report_digest"] = cc02.canonical_digest(
            cc02.LEGACY_REPORT_SCHEMA, value, "report_digest"
        )
        authority = cc02._ManifestAuthority(
            windows_report_digest=value["report_digest"],
            linux_report_digest=json.loads(linux)["report_digest"],
        )
    with pytest.raises(cc02.ManifestBuildError) as error:
        cc02._construct_manifest_and_preregistration_with_authority(
            json.dumps(value, sort_keys=True).encode(), linux, authority
        )
    assert str(error.value) == cc02.STOP_OUTCOME
    assert "private-" not in str(error.value)


def test_parser_resource_and_writer_fail_closed_without_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    for payload in (b"", b"\xef\xbb\xbf{}", b'{"x":NaN}', b'{"x":1,"x":2}', b"[" * 17 + b"]" * 17):
        with pytest.raises(cc02.ManifestBuildError):
            cc02._construct_manifest_and_preregistration_with_authority(payload, linux, authority)
    manifest, prereg = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    target = tmp_path / "docs/research"
    target.mkdir(parents=True)
    cc02._write_outputs_once_with_authority(manifest, prereg, root=tmp_path, authority=authority)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, prereg, root=tmp_path, authority=authority
        )
    assert (tmp_path / cc02.REPORT_OUTPUT).read_bytes() == manifest
    assert (tmp_path / cc02.PREREG_OUTPUT).read_bytes() == prereg
    invalid_root = tmp_path / "invalid"
    (invalid_root / "docs/research").mkdir(parents=True)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest.rstrip(), prereg, root=invalid_root, authority=authority
        )
    assert not (invalid_root / cc02.REPORT_OUTPUT).exists()
    assert not (invalid_root / cc02.PREREG_OUTPUT).exists()
    collision_root = tmp_path / "collision"
    (collision_root / "docs/research").mkdir(parents=True)
    real_open = cc02.os.open

    def fail_second(path: object, flags: int, mode: int = 0o777, **kwargs: Any) -> int:
        if Path(path).name.endswith(f"{cc02.PREREG_OUTPUT.name}.cc02-staging"):
            raise FileExistsError
        return real_open(path, flags, mode, **kwargs)

    monkeypatch.setattr(cc02.os, "open", fail_second)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, prereg, root=collision_root, authority=authority
        )
    assert not (collision_root / cc02.REPORT_OUTPUT).exists()
    assert not (collision_root / cc02.PREREG_OUTPUT).exists()


def test_cooperating_concurrent_invocations_have_one_exact_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "cooperating-writers"
    research = root / "docs/research"
    research.mkdir(parents=True)
    first_staging = f".{cc02.REPORT_OUTPUT.name}.cc02-staging"
    barrier = threading.Barrier(2)
    real_open_exclusive = cc02._PublicationAnchor.open_exclusive

    def synchronized_first_create(anchor: Any, name: str) -> int:
        if name == first_staging:
            barrier.wait(timeout=10)
        return real_open_exclusive(anchor, name)

    def invoke() -> str:
        try:
            cc02._write_outputs_once_with_authority(
                manifest, preregistration, root=root, authority=authority
            )
        except cc02.ManifestBuildError:
            return "FAIL_CLOSED"
        return "PASS"

    monkeypatch.setattr(cc02._PublicationAnchor, "open_exclusive", synchronized_first_create)
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(lambda _: invoke(), range(2)))
    assert outcomes == ["FAIL_CLOSED", "PASS"]
    assert (root / cc02.REPORT_OUTPUT).read_bytes() == manifest
    assert (root / cc02.PREREG_OUTPUT).read_bytes() == preregistration
    assert not (research / cc02._INCOMPLETE_MARKER).exists()
    assert not list(research.glob(".*.cc02-staging"))


@pytest.mark.parametrize(
    "failure",
    (
        "first_open",
        "first_write",
        "second_write",
        "first_fsync",
        "first_close",
        "second_close",
    ),
)
def test_writer_removes_every_reserved_output_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / failure
    (root / "docs/research").mkdir(parents=True)
    real_open, real_write = cc02.os.open, cc02.os.write
    real_fsync, real_close = cc02.os.fsync, cc02.os.close
    opens = writes = syncs = closes = 0
    output_descriptors: set[int] = set()

    def failing_open(path: object, flags: int, mode: int = 0o777, **kwargs: Any) -> int:
        nonlocal opens
        if flags & cc02.os.O_CREAT:
            opens += 1
            if failure == "first_open" and opens == 1:
                raise OSError
            descriptor = real_open(path, flags, mode, **kwargs)
            output_descriptors.add(descriptor)
            return descriptor
        return real_open(path, flags, mode, **kwargs)

    def failing_write(descriptor: int, content: bytes) -> int:
        nonlocal writes
        writes += 1
        if (failure == "first_write" and writes == 1) or (
            failure == "second_write" and writes == 2
        ):
            raise OSError
        return real_write(descriptor, content)

    def failing_fsync(descriptor: int) -> None:
        nonlocal syncs
        syncs += 1
        if failure == "first_fsync" and syncs == 1:
            raise OSError
        real_fsync(descriptor)

    def failing_close(descriptor: int) -> None:
        nonlocal closes
        real_close(descriptor)
        if descriptor in output_descriptors:
            closes += 1
            if (failure == "first_close" and closes == 1) or (
                failure == "second_close" and closes == 2
            ):
                raise OSError

    monkeypatch.setattr(cc02.os, "open", failing_open)
    monkeypatch.setattr(cc02.os, "write", failing_write)
    monkeypatch.setattr(cc02.os, "fsync", failing_fsync)
    monkeypatch.setattr(cc02.os, "close", failing_close)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()


def test_writer_detects_staging_cleanup_failure_without_final_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "cleanup"
    (root / "docs/research").mkdir(parents=True)
    real_unlink = cc02.os.unlink
    failed = False

    def fail_first_staging_unlink(path: object, **kwargs: Any) -> None:
        nonlocal failed
        if not failed and str(path).endswith(".cc02-staging"):
            failed = True
            raise OSError
        real_unlink(path, **kwargs)

    monkeypatch.setattr(cc02.os, "unlink", fail_first_staging_unlink)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert failed
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()


def test_writer_close_before_release_leaves_no_fixed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "close-before-release"
    research = root / "docs/research"
    research.mkdir(parents=True)
    real_open, real_close = cc02.os.open, cc02.os.close
    output_descriptors: set[int] = set()
    retained: list[int] = []

    def track_output_open(path: object, flags: int, mode: int = 0o777, **kwargs: Any) -> int:
        descriptor = real_open(path, flags, mode, **kwargs)
        if flags & cc02.os.O_CREAT:
            output_descriptors.add(descriptor)
        return descriptor

    def fail_before_close(descriptor: int) -> None:
        if descriptor in output_descriptors and not retained:
            retained.append(descriptor)
            raise OSError
        real_close(descriptor)

    monkeypatch.setattr(cc02.os, "open", track_output_open)
    monkeypatch.setattr(cc02.os, "close", fail_before_close)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert retained
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()
    monkeypatch.setattr(cc02.os, "open", real_open)
    monkeypatch.setattr(cc02.os, "close", real_close)
    for descriptor in retained:
        real_close(descriptor)
    for staging in research.glob(".*.cc02-staging"):
        staging.unlink()


def test_writer_persistent_staging_cleanup_failure_has_no_fixed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "persistent-cleanup"
    research = root / "docs/research"
    research.mkdir(parents=True)
    real_unlink = cc02.os.unlink

    def always_fail_staging_unlink(path: object, **kwargs: Any) -> None:
        if str(path).endswith(".cc02-staging"):
            raise OSError
        real_unlink(path, **kwargs)

    monkeypatch.setattr(cc02.os, "unlink", always_fail_staging_unlink)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()
    residual = list(research.glob(".*.cc02-staging"))
    assert residual
    monkeypatch.setattr(cc02.os, "unlink", real_unlink)
    for staging in residual:
        real_unlink(staging)


def test_second_publication_failure_rolls_back_first_final_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "publish"
    (root / "docs/research").mkdir(parents=True)
    real_link = cc02.os.link

    def fail_second_link(source: object, target: object, **kwargs: Any) -> None:
        if Path(target).name == cc02.PREREG_OUTPUT.name:
            raise OSError
        real_link(source, target, **kwargs)

    monkeypatch.setattr(cc02.os, "link", fail_second_link)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()


def test_persistent_final_rollback_failure_keeps_incomplete_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "incomplete"
    research = root / "docs/research"
    research.mkdir(parents=True)
    real_link, real_unlink = cc02.os.link, cc02.os.unlink

    def fail_second_link(source: object, target: object, **kwargs: Any) -> None:
        if Path(target).name == cc02.PREREG_OUTPUT.name:
            raise OSError
        real_link(source, target, **kwargs)

    def fail_final_report_unlink(path: object, **kwargs: Any) -> None:
        if Path(path).name == cc02.REPORT_OUTPUT.name:
            raise OSError
        real_unlink(path, **kwargs)

    monkeypatch.setattr(cc02.os, "link", fail_second_link)
    monkeypatch.setattr(cc02.os, "unlink", fail_final_report_unlink)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    marker = research / cc02._INCOMPLETE_MARKER
    assert marker.read_bytes() == cc02._INCOMPLETE_MARKER_BYTES
    assert (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    monkeypatch.setattr(cc02.os, "link", real_link)
    monkeypatch.setattr(cc02.os, "unlink", real_unlink)
    real_unlink(root / cc02.REPORT_OUTPUT)
    real_unlink(marker)


@pytest.mark.parametrize("failure_at", (1, 2, 3, 4))
def test_precommit_directory_sync_failures_roll_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_at: int
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / f"sync-{failure_at}"
    research = root / "docs/research"
    research.mkdir(parents=True)
    real_sync = cc02._PublicationAnchor.sync_directory
    calls = 0

    def fail_one_sync(anchor: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == failure_at:
            raise OSError
        real_sync(anchor)

    monkeypatch.setattr(cc02._PublicationAnchor, "sync_directory", fail_one_sync)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert calls >= failure_at
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()
    assert not (research / cc02._INCOMPLETE_MARKER).exists()
    assert not list(research.glob(".*.cc02-staging"))


def test_directory_sync_failure_after_marker_unlink_does_not_start_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "post-commit-sync"
    research = root / "docs/research"
    research.mkdir(parents=True)
    real_sync = cc02._PublicationAnchor.sync_directory
    calls = 0

    def fail_commit_sync(anchor: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 5:
            raise OSError
        real_sync(anchor)

    monkeypatch.setattr(cc02._PublicationAnchor, "sync_directory", fail_commit_sync)
    cc02._write_outputs_once_with_authority(
        manifest, preregistration, root=root, authority=authority
    )
    assert calls == 5
    assert (root / cc02.REPORT_OUTPUT).read_bytes() == manifest
    assert (root / cc02.PREREG_OUTPUT).read_bytes() == preregistration
    assert not (research / cc02._INCOMPLETE_MARKER).exists()
    assert not list(research.glob(".*.cc02-staging"))


def test_anchor_acquisition_inode_mismatch_fails_before_child_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "inode-mismatch"
    research = root / "docs/research"
    external = tmp_path / "external-inode"
    research.mkdir(parents=True)
    external.mkdir()
    monkeypatch.setattr(cc02, "_directory_identity", lambda _: cc02._DirectoryIdentity(0, 0))
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert not list(external.iterdir())
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()
    assert not (research / cc02._INCOMPLETE_MARKER).exists()


def test_post_commit_anchor_close_error_does_not_override_committed_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "post-commit-close"
    research = root / "docs/research"
    research.mkdir(parents=True)
    close_name = "_close_windows_chain" if cc02.os.name == "nt" else "_close_posix_chain"
    real_close = getattr(cc02._PublicationAnchor, close_name)

    def close_then_raise(anchor: Any) -> None:
        real_close(anchor)
        raise cc02.ManifestBuildError(cc02.STOP_OUTCOME)

    monkeypatch.setattr(cc02._PublicationAnchor, close_name, close_then_raise)
    cc02._write_outputs_once_with_authority(
        manifest, preregistration, root=root, authority=authority
    )
    assert (root / cc02.REPORT_OUTPUT).read_bytes() == manifest
    assert (root / cc02.PREREG_OUTPUT).read_bytes() == preregistration
    assert not (research / cc02._INCOMPLETE_MARKER).exists()


def test_child_name_swap_before_link_never_commits_attacker_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "child-swap"
    research = root / "docs/research"
    research.mkdir(parents=True)
    real_link = cc02._PublicationAnchor.link
    swapped = False

    def swap_then_link(anchor: Any, source: str, target: str) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            anchor.unlink(source)
            descriptor = anchor.open_exclusive(source)
            try:
                assert cc02.os.write(descriptor, b"ATTACKER-CONTENT") == len(b"ATTACKER-CONTENT")
                cc02.os.fsync(descriptor)
            finally:
                cc02.os.close(descriptor)
        real_link(anchor, source, target)

    monkeypatch.setattr(cc02._PublicationAnchor, "link", swap_then_link)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert swapped
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()
    assert not (research / cc02._INCOMPLETE_MARKER).exists()


def test_exact_child_verification_rejects_reparse_with_matching_bytes(tmp_path: Path) -> None:
    root = tmp_path / "child-reparse"
    research = root / "docs/research"
    research.mkdir(parents=True)
    expected = b"EXACT-EXPECTED-BYTES"
    external = tmp_path / "external-exact-bytes.bin"
    external.write_bytes(expected)
    child = research / ".candidate.cc02-staging"
    child.symlink_to(external)
    assert child.read_bytes() == expected
    with cc02._PublicationAnchor(root) as anchor:
        with pytest.raises(OSError):
            anchor.verify_exact_file(child.name, expected)


def test_incomplete_marker_identity_swap_never_publishes_fixed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "marker-swap"
    research = root / "docs/research"
    research.mkdir(parents=True)
    real_link = cc02._PublicationAnchor.link
    swapped = False

    def swap_marker_then_link(anchor: Any, source: str, target: str) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            anchor.unlink(cc02._INCOMPLETE_MARKER)
            descriptor = anchor.open_exclusive(cc02._INCOMPLETE_MARKER)
            try:
                assert cc02.os.write(descriptor, cc02._INCOMPLETE_MARKER_BYTES) == len(
                    cc02._INCOMPLETE_MARKER_BYTES
                )
                cc02.os.fsync(descriptor)
            finally:
                cc02.os.close(descriptor)
            anchor.sync_directory()
        real_link(anchor, source, target)

    monkeypatch.setattr(cc02._PublicationAnchor, "link", swap_marker_then_link)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert swapped
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()
    assert (research / cc02._INCOMPLETE_MARKER).read_bytes() == cc02._INCOMPLETE_MARKER_BYTES


def test_writer_rejects_reparse_parent_and_parent_identity_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "contained"
    research = root / "docs/research"
    research.mkdir(parents=True)
    original_lstat = cc02.os.lstat
    original = original_lstat(research)
    reparse = SimpleNamespace(
        st_mode=original.st_mode,
        st_dev=original.st_dev,
        st_ino=original.st_ino,
        st_mtime_ns=original.st_mtime_ns,
        st_file_attributes=1,
    )
    monkeypatch.setattr(cc02.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1, raising=False)
    monkeypatch.setattr(
        cc02.os, "lstat", lambda path: reparse if Path(path) == research else original_lstat(path)
    )
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert not (root / cc02.REPORT_OUTPUT).exists()
    monkeypatch.setattr(cc02.os, "lstat", original_lstat)
    monkeypatch.setattr(cc02._PublicationAnchor, "unchanged", lambda _: False)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert not (root / cc02.REPORT_OUTPUT).exists()
    assert not (root / cc02.PREREG_OUTPUT).exists()


def test_parent_swap_after_anchor_cannot_create_in_external_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    root = tmp_path / "anchor-swap"
    research = root / "docs/research"
    external = tmp_path / "external"
    parked = root / "docs/research-held"
    research.mkdir(parents=True)
    external.mkdir()
    original_open = cc02._PublicationAnchor.open_exclusive
    attempted = False

    def swap_before_first_create(anchor: Any, name: str) -> int:
        nonlocal attempted
        if not attempted:
            attempted = True
            if cc02.os.name == "nt":
                with pytest.raises(OSError):
                    research.rename(parked)
                raise OSError
            research.rename(parked)
            research.symlink_to(external, target_is_directory=True)
        return original_open(anchor, name)

    monkeypatch.setattr(cc02._PublicationAnchor, "open_exclusive", swap_before_first_create)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._write_outputs_once_with_authority(
            manifest, preregistration, root=root, authority=authority
        )
    assert attempted
    assert not list(external.iterdir())
    if cc02.os.name != "nt":
        research.unlink()
        parked.rename(research)


def test_manifest_validation_rejects_tampered_status_binding_and_preregistration() -> None:
    windows, linux, authority = _inputs()
    manifest_bytes, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    for mutation in (
        "status",
        "report_binding",
        "direction_order",
        "resource",
        "resource_bool",
        "boundary_int",
        "repeat_bool",
    ):
        manifest = json.loads(manifest_bytes)
        if mutation == "status":
            manifest["status"] = "READY"
        elif mutation == "report_binding":
            manifest["platform_report_bindings"][0]["runtime_manifest_digest"] = _digest("wrong")
        elif mutation == "direction_order":
            manifest["direction_diagnostic_bindings"].reverse()
        elif mutation == "resource_bool":
            manifest["resource_envelope"]["maximum_concurrency"] = True
        elif mutation == "boundary_int":
            manifest["boundaries"]["real_user_processing"] = 0
        elif mutation == "repeat_bool":
            manifest["legacy_success_repeat_bindings"][0]["repeat_index"] = True
        else:
            manifest["resource_envelope"]["maximum_wall_clock_seconds_total"] = 14_401
        manifest["manifest_content_digest"] = cc02.canonical_digest(
            cc02.MANIFEST_SCHEMA, manifest, "manifest_content_digest"
        )
        with pytest.raises(cc02.ManifestBuildError):
            cc02._validate_manifest_bytes_with_authority(
                cc02._canonical_json(manifest), cc02._preregistration(manifest), authority
            )
    noncanonical = json.dumps(json.loads(manifest_bytes), sort_keys=True).encode()
    with pytest.raises(cc02.ManifestBuildError):
        cc02._validate_manifest_bytes_with_authority(noncanonical, preregistration, authority)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._validate_manifest_bytes_with_authority(
            manifest_bytes, preregistration + b"tamper", authority
        )


@pytest.mark.parametrize(
    "collection,index,mutation",
    (
        ("platform_report_bindings", 0, lambda value: value.pop("platform")),
        ("platform_case_bindings", 0, lambda value: value.__setitem__("case_digest", 7)),
        ("legacy_success_repeat_bindings", 0, lambda value: value.pop("repeat_index")),
        ("direction_diagnostic_bindings", 0, lambda value: value.__setitem__("platform", 7)),
    ),
)
def test_malformed_sort_fields_fail_closed(collection: str, index: int, mutation: Any) -> None:
    windows, linux, authority = _inputs()
    manifest_bytes, _ = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    manifest = json.loads(manifest_bytes)
    mutation(manifest[collection][index])
    manifest["manifest_content_digest"] = cc02.canonical_digest(
        cc02.MANIFEST_SCHEMA, manifest, "manifest_content_digest"
    )
    with pytest.raises(cc02.ManifestBuildError):
        cc02._validate_manifest_bytes_with_authority(
            cc02._canonical_json(manifest), cc02._preregistration(manifest), authority
        )


def test_non_bytes_and_invalid_authority_fail_without_raw_exceptions() -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    invalid_authorities = (
        object(),
        cc02._ManifestAuthority(
            windows_report_digest="not-a-digest", linux_report_digest=authority.linux_report_digest
        ),
    )
    for invalid_authority in invalid_authorities:
        with pytest.raises(cc02.ManifestBuildError):
            cc02._construct_manifest_and_preregistration_with_authority(
                windows, linux, invalid_authority
            )
        with pytest.raises(cc02.ManifestBuildError):
            cc02._validate_manifest_bytes_with_authority(
                manifest, preregistration, invalid_authority
            )
    with pytest.raises(cc02.ManifestBuildError):
        cc02._construct_manifest_and_preregistration_with_authority("not-bytes", linux, authority)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._validate_manifest_bytes_with_authority("not-bytes", preregistration, authority)


def test_production_entry_points_do_not_accept_authority_or_root_overrides() -> None:
    windows, linux, authority = _inputs()
    manifest, preregistration = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    assert tuple(inspect.signature(cc02.validate_cc01c_report_pair_for_manifest).parameters) == (
        "windows_report_bytes",
        "linux_report_bytes",
    )
    assert tuple(inspect.signature(cc02.construct_manifest_and_preregistration).parameters) == (
        "windows_report_bytes",
        "linux_report_bytes",
    )
    assert tuple(inspect.signature(cc02.validate_manifest_bytes).parameters) == (
        "manifest_bytes",
        "preregistration_bytes",
    )
    assert tuple(inspect.signature(cc02.write_outputs_once).parameters) == (
        "manifest_bytes",
        "preregistration_bytes",
    )
    with pytest.raises(TypeError):
        cc02.construct_manifest_and_preregistration(windows, linux, authority)
    with pytest.raises(TypeError):
        cc02.validate_manifest_bytes(manifest, preregistration, authority)
    with pytest.raises(cc02.ManifestBuildError):
        cc02.construct_manifest_and_preregistration(windows, linux)
    with pytest.raises(cc02.ManifestBuildError):
        cc02.validate_manifest_bytes(manifest, preregistration)


def test_failed_executed_prefix_rows_validate_but_never_project_as_success() -> None:
    windows, linux, _ = _inputs()
    values = [json.loads(windows), json.loads(linux)]
    for platform, report in zip(
        ("windows_x86_64", "linux_x86_64_network_none"), values, strict=True
    ):
        failed = report["cases"][10]
        failed["executed_repeat_count"] = 1
        report["rows"].append(_row(failed, 1, platform))
    windows, linux = (_refreshed(values[0]), _refreshed(values[1]))
    authority = _authority(windows, linux)
    manifest_bytes, _ = cc02._construct_manifest_and_preregistration_with_authority(
        windows, linux, authority
    )
    manifest = json.loads(manifest_bytes)
    failed_digest = values[0]["cases"][10]["case_digest"]
    assert all(
        item["case_digest"] != failed_digest for item in manifest["legacy_success_repeat_bindings"]
    )


def test_held_read_rejects_resource_and_filesystem_adversaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty.json"
    empty.write_bytes(b"")
    with pytest.raises(cc02.ManifestBuildError):
        cc02._read_held_report(empty)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._read_held_report(tmp_path)
    source = tmp_path / "source.json"
    source.write_bytes(b"{}")
    original_lstat = cc02.os.lstat
    before = original_lstat(source)
    oversized = SimpleNamespace(
        **{name: getattr(before, name) for name in ("st_mode", "st_dev", "st_ino", "st_mtime_ns")},
        st_size=cc02.MAX_REPORT_BYTES + 1,
        st_file_attributes=0,
    )
    monkeypatch.setattr(cc02.os, "lstat", lambda _: oversized)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._read_held_report(source)
    monkeypatch.setattr(cc02.os, "lstat", original_lstat)
    calls = 0

    def changing_lstat(path: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            return SimpleNamespace(
                **{
                    name: getattr(before, name)
                    for name in ("st_mode", "st_dev", "st_ino", "st_mtime_ns")
                },
                st_size=before.st_size + 1,
                st_file_attributes=0,
            )
        return original_lstat(path)

    monkeypatch.setattr(cc02.os, "lstat", changing_lstat)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._read_held_report(source)
    reparse = SimpleNamespace(
        **{
            name: getattr(before, name)
            for name in ("st_mode", "st_dev", "st_ino", "st_mtime_ns", "st_size")
        },
        st_file_attributes=1,
    )
    monkeypatch.setattr(cc02.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1, raising=False)
    monkeypatch.setattr(cc02.os, "lstat", lambda _: reparse)
    with pytest.raises(cc02.ManifestBuildError):
        cc02._read_held_report(source)
    source_text = _BUILDER.read_text(encoding="utf-8").lower()
    for forbidden in ("import subprocess", "import urllib", "import requests", "import socket"):
        assert forbidden not in source_text
    tree = ast.parse(source_text)
    forbidden_modules = {"http", "requests", "socket", "subprocess", "urllib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name.split(".", maxsplit=1)[0] not in forbidden_modules
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert node.module.split(".", maxsplit=1)[0] not in forbidden_modules
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                assert node.func.attr not in {
                    "popen",
                    "spawnl",
                    "spawnle",
                    "spawnv",
                    "spawnve",
                    "system",
                }
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert not any(token in node.func.id for token in ("replay", "transform", "vision"))
