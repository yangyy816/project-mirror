"""Build the first CC02 diagnostic manifest from two validated CC01C reports.

This module intentionally has no replay, image, network, or subprocess entry point.
It is a fail-closed projection from bounded legacy-report bytes to public authority.
Publication requires the trusted exclusive workspace custody frozen by ADR-048; this
ordinary-file writer is not a hostile same-credential mutation boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import sys
from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, NoReturn, cast

_SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if _SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPT_DIRECTORY)

from run_p2_m5_cc02_diagnostic import canonical_digest, legacy_row_digest  # noqa: E402

BUILDER_VERSION: Final = "p2-m5-cc02-manifest-builder-v1"
MANIFEST_SCHEMA: Final = "mirror.p2-m5/CC02DiagnosticManifest/v1"
LEGACY_REPORT_SCHEMA: Final = "mirror.p2-m5/CC01C-private-platform-report/v2"
MAX_REPORT_BYTES: Final = 67_108_864
MAX_JSON_DEPTH: Final = 16
PLATFORMS: Final = ("linux_x86_64_network_none", "windows_x86_64")
CANDIDATES: Final = (
    "cheekbone_width",
    "chin_height",
    "eye_spacing",
    "jaw_width",
    "mouth_width",
    "nose_width",
)
DIRECTIONS: Final = ("DECREASE", "INCREASE")
MAGNITUDES: Final = (15_000, 30_000)
STOP_OUTCOME: Final = "FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE"
_CANDIDATE_MANIFEST_DIGEST: Final = (
    "eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4"
)
_STAGE_B_EVIDENCE_DIGEST: Final = "a71206d99a08a1372694175ec537282bae1f662b6a77ac35dfe097ae8e8e3908"
_COHORT_DIGEST: Final = "618b993f81f282367719173119ff109fbbb8131d26cb41f5c803805a92c52358"
_CASE_SET_DIGEST: Final = "79cbaf4ad14f8b0ee3aa2fb2360e507740c2bf0737242356b601df5f23f7093f"
_MODEL_DIGEST: Final = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
_TOPOLOGY_DIGEST: Final = "85eea84eef15dd963e06382d6e61f7357029d9901acc935731ecaa7eab856b63"
_REDACTED_AGGREGATE_DIGEST: Final = (
    "272e473b16b8af346a3e8b516aef1de13f2359583694e6db0bff79b1b472e3bb"
)
REPORT_OUTPUT: Final = Path("docs/research/P2_M5_CC02_DIAGNOSTIC_MANIFEST.json")
PREREG_OUTPUT: Final = Path("docs/research/P2_M5_CC02_DIAGNOSTIC_PREREGISTRATION.md")
REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
_INCOMPLETE_MARKER: Final = ".p2-m5-cc02-publication-incomplete"
_INCOMPLETE_MARKER_BYTES: Final = b"CC02_INCOMPLETE_PUBLICATION_NON_AUTHORITATIVE\n"

_SHA256 = __import__("re").compile(r"[0-9a-f]{64}\Z")
_CASE_COMMON = {
    "case_digest",
    "identity_reference",
    "candidate",
    "direction",
    "magnitude_ppm",
    "status",
    "executed_repeat_count",
}
_ROW_KEYS = {
    "case_digest",
    "identity_reference",
    "candidate",
    "direction",
    "magnitude_ppm",
    "repeat",
    "status",
    "source_sha256",
    "result_sha256",
    "result_artifact",
    "plan_digest",
    "source_measurements",
    "result_measurements",
    "vision_log_sha256",
    "vision_log_artifact",
    "phash_hex",
    "changed_pixel_count",
}
_BOUNDARIES = {
    "synthetic_only": True,
    "private_reports_remain_untracked": True,
    "source_and_result_assets_remain_untracked": True,
    "real_user_processing": False,
    "production_geometry": False,
    "public_api_change": False,
    "schema_or_migration_change": False,
    "dependency_or_model_change": False,
    "network_during_manifest_construction": False,
    "replay_during_manifest_construction": False,
    "generation": False,
    "question_bank_release": False,
}
_STOP_RULES = [
    "FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE",
    "DIGEST_MISMATCH",
    "SCHEMA_OR_AUTHORITY_MISMATCH",
    "CASE_MEMBERSHIP_NOT_EXACT",
    "LEGACY_ROW_AUTHORITY_NOT_EXACT",
    "PRIVATE_FIELD_REDACTION_FAILED",
    "RESOURCE_ENVELOPE_MISMATCH",
    "CANONICAL_DIGEST_MISMATCH",
]
_TOP_LEVEL_KEYS = {
    "schema",
    "platform",
    "runtime_manifest_digest",
    "candidate_manifest_digest",
    "model_sha256",
    "topology_sha256",
    "triangle_count",
    "stage_b_evidence_sha256",
    "cohort_digest",
    "input_manifest_digest",
    "case_set_digest",
    "cases",
    "rows",
    "report_digest",
}


class ManifestBuildError(ValueError):
    """A safe, non-disclosing construction stop."""

    outcome = STOP_OUTCOME


@dataclass(frozen=True)
class _DirectoryIdentity:
    device: int
    inode: int


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    size: int
    modified_ns: int


class _PublicationAnchor(AbstractContextManager["_PublicationAnchor"]):
    """Hold the root/docs/research chain while publishing fixed child names."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._paths = (root, root / "docs", root / "docs/research")
        self._identities: tuple[_DirectoryIdentity, ...] = ()
        self._fds: list[int] = []
        self._windows_handles: list[int] = []

    def __enter__(self) -> _PublicationAnchor:
        if os.name == "nt":
            self._open_windows_chain()
        else:
            self._open_posix_chain()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        # Marker unlink plus its directory sync is the irreversible commit point.
        # Directory descriptor/handle close is post-commit best effort: a late close
        # error must not turn committed final files without a marker into a false FAIL.
        try:
            if os.name == "nt":
                self._close_windows_chain()
            else:
                self._close_posix_chain()
        except ManifestBuildError:
            pass

    @property
    def research_path(self) -> Path:
        return self._paths[-1]

    def _open_posix_chain(self) -> None:
        expected: list[_DirectoryIdentity] = []
        parent_fd: int | None = None
        try:
            for index, path in enumerate(self._paths):
                listed = _directory_identity(path)
                flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                if index == 0:
                    descriptor = os.open(path, flags)
                else:
                    assert parent_fd is not None
                    descriptor = os.open(path.name, flags, dir_fd=parent_fd)
                held = os.fstat(descriptor)
                if (held.st_dev, held.st_ino) != (listed.device, listed.inode):
                    os.close(descriptor)
                    _fail()
                self._fds.append(descriptor)
                parent_fd = descriptor
                expected.append(listed)
            self._identities = tuple(expected)
        except (ManifestBuildError, OSError):
            self._close_posix_chain()
            _fail()

    def _close_posix_chain(self) -> None:
        failures = False
        for descriptor in reversed(self._fds):
            try:
                os.close(descriptor)
            except OSError:
                failures = True
        self._fds.clear()
        if failures:
            _fail()

    def _open_windows_chain(self) -> None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        get_info = kernel32.GetFileInformationByHandle
        get_info.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        get_info.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        class _FileInformation(ctypes.Structure):
            _fields_ = [
                ("attributes", wintypes.DWORD),
                ("creation_low", wintypes.DWORD),
                ("creation_high", wintypes.DWORD),
                ("access_low", wintypes.DWORD),
                ("access_high", wintypes.DWORD),
                ("write_low", wintypes.DWORD),
                ("write_high", wintypes.DWORD),
                ("volume", wintypes.DWORD),
                ("size_high", wintypes.DWORD),
                ("size_low", wintypes.DWORD),
                ("links", wintypes.DWORD),
                ("index_high", wintypes.DWORD),
                ("index_low", wintypes.DWORD),
            ]

        generic_read_write = 0x80000000 | 0x40000000
        share_read_write = 0x00000001 | 0x00000002
        open_existing = 3
        file_attribute_directory = 0x10
        file_attribute_reparse = 0x400
        backup_semantics = 0x02000000
        open_reparse = 0x00200000
        invalid_handle = ctypes.c_void_p(-1).value
        try:
            identities: list[_DirectoryIdentity] = []
            for path in self._paths:
                listed = _directory_identity(path)
                handle = create_file(
                    str(path),
                    generic_read_write,
                    share_read_write,
                    None,
                    open_existing,
                    backup_semantics | open_reparse,
                    None,
                )
                if handle == invalid_handle:
                    _fail()
                info = _FileInformation()
                if (
                    not get_info(handle, ctypes.byref(info))
                    or not info.attributes & file_attribute_directory
                    or info.attributes & file_attribute_reparse
                ):
                    close_handle(handle)
                    _fail()
                identity = _DirectoryIdentity(
                    int(info.volume), int((info.index_high << 32) | info.index_low)
                )
                if identity.inode != listed.inode:
                    close_handle(handle)
                    _fail()
                self._windows_handles.append(int(handle))
                identities.append(identity)
            self._identities = tuple(identities)
        except (ManifestBuildError, OSError):
            self._close_windows_chain()
            _fail()

    def _close_windows_chain(self) -> None:
        if not self._windows_handles:
            return
        import ctypes
        from ctypes import wintypes

        close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        failures = False
        for handle in reversed(self._windows_handles):
            if not close_handle(handle):
                failures = True
        self._windows_handles.clear()
        if failures:
            _fail()

    def _windows_path_identity(self, path: Path) -> _DirectoryIdentity:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        get_info = kernel32.GetFileInformationByHandle
        get_info.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        get_info.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        class _FileInformation(ctypes.Structure):
            _fields_ = [
                ("attributes", wintypes.DWORD),
                ("creation_low", wintypes.DWORD),
                ("creation_high", wintypes.DWORD),
                ("access_low", wintypes.DWORD),
                ("access_high", wintypes.DWORD),
                ("write_low", wintypes.DWORD),
                ("write_high", wintypes.DWORD),
                ("volume", wintypes.DWORD),
                ("size_high", wintypes.DWORD),
                ("size_low", wintypes.DWORD),
                ("links", wintypes.DWORD),
                ("index_high", wintypes.DWORD),
                ("index_low", wintypes.DWORD),
            ]

        handle = create_file(
            str(path),
            0x80000000 | 0x40000000,
            0x00000001 | 0x00000002,
            None,
            3,
            0x02000000 | 0x00200000,
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            _fail()
        try:
            info = _FileInformation()
            if (
                not get_info(handle, ctypes.byref(info))
                or not info.attributes & 0x10
                or info.attributes & 0x400
            ):
                _fail()
            return _DirectoryIdentity(
                int(info.volume), int((info.index_high << 32) | info.index_low)
            )
        finally:
            if not close_handle(handle):
                _fail()

    def unchanged(self) -> bool:
        try:
            if os.name == "nt":
                return (
                    tuple(self._windows_path_identity(path) for path in self._paths)
                    == self._identities
                )
            return tuple(_directory_identity(path) for path in self._paths) == self._identities
        except ManifestBuildError:
            return False

    def sync_directory(self) -> None:
        if os.name != "nt":
            os.fsync(self._fds[-1])
            return
        import ctypes
        from ctypes import wintypes

        flush = ctypes.WinDLL("kernel32", use_last_error=True).FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL
        if not flush(self._windows_handles[-1]):
            raise OSError(ctypes.get_last_error(), "directory sync failed")

    def exists(self, name: str) -> bool:
        try:
            if os.name == "nt":
                os.lstat(self.research_path / name)
            else:
                os.stat(name, dir_fd=self._fds[-1], follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False
        except OSError:
            _fail()

    def open_exclusive(self, name: str) -> int:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        if os.name == "nt":
            return os.open(self.research_path / name, flags, 0o600)
        return os.open(name, flags, 0o600, dir_fd=self._fds[-1])

    def link(self, source: str, target: str) -> None:
        if os.name == "nt":
            os.link(self.research_path / source, self.research_path / target)
        else:
            os.link(source, target, src_dir_fd=self._fds[-1], dst_dir_fd=self._fds[-1])

    def unlink(self, name: str) -> None:
        if os.name == "nt":
            os.unlink(self.research_path / name)
        else:
            os.unlink(name, dir_fd=self._fds[-1])

    def verify_exact_file(self, name: str, expected: bytes) -> _FileIdentity:
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if os.name == "nt":
            listed = os.lstat(self.research_path / name)
        else:
            listed = os.stat(name, dir_fd=self._fds[-1], follow_symlinks=False)
        listed_attributes = getattr(listed, "st_file_attributes", 0)
        listed_identity = _FileIdentity(
            listed.st_dev, listed.st_ino, listed.st_size, listed.st_mtime_ns
        )
        if (
            not stat.S_ISREG(listed.st_mode)
            or stat.S_ISLNK(listed.st_mode)
            or listed_attributes & reparse
            or listed.st_size != len(expected)
        ):
            raise OSError
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        if os.name == "nt":
            descriptor = os.open(self.research_path / name, flags)
        else:
            descriptor = os.open(name, flags, dir_fd=self._fds[-1])
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_size != len(expected):
                raise OSError
            content = bytearray()
            while len(content) < len(expected):
                chunk = os.read(descriptor, len(expected) - len(content))
                if not chunk:
                    raise OSError
                content.extend(chunk)
            if os.read(descriptor, 1) or bytes(content) != expected:
                raise OSError
            after = os.fstat(descriptor)
            before_identity = _FileIdentity(
                before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
            )
            after_identity = _FileIdentity(
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
            )
            if os.name == "nt":
                final_path = os.lstat(self.research_path / name)
            else:
                final_path = os.stat(name, dir_fd=self._fds[-1], follow_symlinks=False)
            final_attributes = getattr(final_path, "st_file_attributes", 0)
            final_identity = _FileIdentity(
                final_path.st_dev,
                final_path.st_ino,
                final_path.st_size,
                final_path.st_mtime_ns,
            )
            if (
                listed_identity != before_identity
                or before_identity != after_identity
                or final_identity != before_identity
                or not stat.S_ISREG(final_path.st_mode)
                or stat.S_ISLNK(final_path.st_mode)
                or final_attributes & reparse
            ):
                raise OSError
            return before_identity
        finally:
            os.close(descriptor)


@dataclass(frozen=True)
class _ManifestAuthority:
    windows_report_digest: str
    linux_report_digest: str
    windows_runtime_digest: str = "27b33d646d8587f76d5ca317ac9d6aec95bc04fd87d413bb3dd6394f9694bb7a"
    linux_runtime_digest: str = "5d0e9ee323d7daea78e8baaeec63917c7a1867301ec5f7c71685fa9cbed311d8"


_DEFAULT_AUTHORITY: Final = _ManifestAuthority(
    windows_report_digest="0eac3ef8f7fa10fc4c1b13c685e5d7534716fe011dce702402266987fc947861",
    linux_report_digest="916ff02cf47d9677b62b57f66aff68364e7aa15f53018941545621d15e453884",
)


def _fail() -> NoReturn:
    raise ManifestBuildError(STOP_OUTCOME)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _matches_frozen_value(value: object, expected: object) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (
            isinstance(value, dict)
            and set(value) == set(expected)
            and all(_matches_frozen_value(value[key], expected[key]) for key in expected)
        )
    if isinstance(expected, list):
        return (
            isinstance(value, list)
            and len(value) == len(expected)
            and all(
                _matches_frozen_value(item, frozen)
                for item, frozen in zip(value, expected, strict=True)
            )
        )
    return value == expected


def _validated_authority(authority: object) -> _ManifestAuthority:
    if type(authority) is not _ManifestAuthority or not all(
        _is_digest(value)
        for value in (
            authority.windows_report_digest,
            authority.linux_report_digest,
            authority.windows_runtime_digest,
            authority.linux_runtime_digest,
        )
    ):
        _fail()
    return authority


def _safe_json_loads(content: object) -> dict[str, Any]:
    if (
        not isinstance(content, bytes)
        or not content
        or len(content) > MAX_REPORT_BYTES
        or content.startswith(b"\xef\xbb\xbf")
    ):
        _fail()
    try:
        text = content.decode("utf-8", "strict")
    except UnicodeDecodeError:
        _fail()
    depth = 0
    quoted = False
    escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                _fail()
        elif character in "]}":
            depth -= 1
            if depth < 0:
                _fail()
    if quoted or escaped or depth != 0:
        _fail()

    def no_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                _fail()
            result[key] = value
        return result

    def reject_constant(_: str) -> None:
        _fail()

    try:
        parsed = json.loads(text, object_pairs_hook=no_pairs, parse_constant=reject_constant)
    except (TypeError, ValueError, json.JSONDecodeError):
        _fail()
    if not isinstance(parsed, dict):
        _fail()
    return cast(dict[str, Any], parsed)


def _expected_report_digest(platform: str, authority: _ManifestAuthority) -> str:
    if platform == "windows_x86_64":
        return authority.windows_report_digest
    if platform == "linux_x86_64_network_none":
        return authority.linux_report_digest
    _fail()


def _expected_runtime_digest(platform: str, authority: _ManifestAuthority) -> str:
    if platform == "windows_x86_64":
        return authority.windows_runtime_digest
    if platform == "linux_x86_64_network_none":
        return authority.linux_runtime_digest
    _fail()


def _validate_authority(report: Mapping[str, Any], authority: _ManifestAuthority) -> None:
    platform = report.get("platform")
    expected = {
        "schema": LEGACY_REPORT_SCHEMA,
        "candidate_manifest_digest": _CANDIDATE_MANIFEST_DIGEST,
        "model_sha256": _MODEL_DIGEST,
        "topology_sha256": _TOPOLOGY_DIGEST,
        "stage_b_evidence_sha256": _STAGE_B_EVIDENCE_DIGEST,
        "cohort_digest": _COHORT_DIGEST,
        "case_set_digest": _CASE_SET_DIGEST,
    }
    if (
        not isinstance(platform, str)
        or platform not in PLATFORMS
        or any(report.get(key) != value for key, value in expected.items())
    ):
        _fail()
    if report.get("runtime_manifest_digest") != _expected_runtime_digest(platform, authority):
        _fail()
    if not _is_digest(report.get("input_manifest_digest")):
        _fail()
    if report.get("triangle_count") != 852:
        _fail()
    if report.get("report_digest") != canonical_digest(
        LEGACY_REPORT_SCHEMA, report, "report_digest"
    ):
        _fail()
    if report.get("report_digest") != _expected_report_digest(platform, authority):
        _fail()


def _validate_measurements(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(CANDIDATES)
        and all(
            isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item)
            for item in value.values()
        )
    )


def _validate_report(report_bytes: bytes, authority: _ManifestAuthority) -> dict[str, Any]:
    report = _safe_json_loads(report_bytes)
    if set(report) != _TOP_LEVEL_KEYS:
        _fail()
    _validate_authority(report, authority)
    cases = report.get("cases")
    rows = report.get("rows")
    if not isinstance(cases, list) or not isinstance(rows, list) or len(cases) != 288:
        _fail()
    parsed_cases = cast(list[object], cases)
    parsed_rows = cast(list[object], rows)
    cases_by_digest: dict[str, dict[str, Any]] = {}
    for case in parsed_cases:
        if not isinstance(case, dict):
            _fail()
        status = case.get("status")
        if status not in {"PASSED_PENDING_MANUAL_ARTIFACT_REVIEW", "FAILED"}:
            _fail()
        keys = (
            _CASE_COMMON
            if status == "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW"
            else _CASE_COMMON | {"failure_stage", "failure_code"}
        )
        if (
            set(case) != keys
            or not _is_digest(case.get("case_digest"))
            or not isinstance(case.get("identity_reference"), str)
        ):
            _fail()
        if (
            case.get("candidate") not in CANDIDATES
            or case.get("direction") not in DIRECTIONS
            or case.get("magnitude_ppm") not in MAGNITUDES
        ):
            _fail()
        if (
            not _is_int(case.get("executed_repeat_count"))
            or not 0 <= case["executed_repeat_count"] <= 3
        ):
            _fail()
        if status == "PASSED_PENDING_MANUAL_ARTIFACT_REVIEW" and case["executed_repeat_count"] != 3:
            _fail()
        if status == "FAILED" and (
            not isinstance(case.get("failure_stage"), str)
            or not isinstance(case.get("failure_code"), str)
        ):
            _fail()
        if case["case_digest"] in cases_by_digest:
            _fail()
        cases_by_digest[case["case_digest"]] = case
    rows_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for row in parsed_rows:
        if not isinstance(row, dict) or set(row) != _ROW_KEYS:
            _fail()
        if not _is_digest(row.get("case_digest")) or row.get("status") != "PASSED":
            _fail()
        if (
            row.get("candidate") not in CANDIDATES
            or row.get("direction") not in DIRECTIONS
            or row.get("magnitude_ppm") not in MAGNITUDES
            or not _is_int(row.get("repeat"))
            or row.get("repeat") not in (1, 2, 3)
        ):
            _fail()
        if not isinstance(row.get("identity_reference"), str) or not all(
            _is_digest(row.get(key))
            for key in ("source_sha256", "result_sha256", "plan_digest", "vision_log_sha256")
        ):
            _fail()
        if (
            not isinstance(row.get("result_artifact"), str)
            or not isinstance(row.get("vision_log_artifact"), str)
            or not isinstance(row.get("phash_hex"), str)
        ):
            _fail()
        if (
            not _is_int(row.get("changed_pixel_count"))
            or not _validate_measurements(row.get("source_measurements"))
            or not _validate_measurements(row.get("result_measurements"))
        ):
            _fail()
        case = cases_by_digest.get(row["case_digest"])
        if case is None or any(
            row[key] != case[key]
            for key in ("identity_reference", "candidate", "direction", "magnitude_ppm")
        ):
            _fail()
        key = (row["case_digest"], row["repeat"])
        if key in rows_by_key:
            _fail()
        rows_by_key[key] = row
    for digest, case in cases_by_digest.items():
        repeats = {repeat for row_digest, repeat in rows_by_key if row_digest == digest}
        if repeats != set(range(1, case["executed_repeat_count"] + 1)):
            _fail()
    descriptors_by_identity: dict[str, set[tuple[str, str, int]]] = {}
    for case in cases_by_digest.values():
        identity = case["identity_reference"]
        descriptors_by_identity.setdefault(identity, set()).add(
            (case["candidate"], case["direction"], case["magnitude_ppm"])
        )
    expected_descriptors = {
        (candidate, direction, magnitude)
        for candidate in CANDIDATES
        for direction in DIRECTIONS
        for magnitude in MAGNITUDES
    }
    if len(descriptors_by_identity) != 12 or any(
        descriptors != expected_descriptors for descriptors in descriptors_by_identity.values()
    ):
        _fail()
    return {
        "report": report,
        "cases": cases_by_digest,
        "rows": rows_by_key,
        "sha256": hashlib.sha256(report_bytes).hexdigest(),
    }


def _validate_cc01c_report_pair_for_manifest_with_authority(
    windows_report_bytes: object,
    linux_report_bytes: object,
    authority: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Synthetic-test seam for the otherwise frozen report authority."""
    checked_authority = _validated_authority(authority)
    reports = (
        _validate_report(cast(bytes, windows_report_bytes), checked_authority),
        _validate_report(cast(bytes, linux_report_bytes), checked_authority),
    )
    by_platform = {item["report"]["platform"]: item for item in reports}
    if set(by_platform) != set(PLATFORMS):
        _fail()
    windows, linux = by_platform["windows_x86_64"], by_platform["linux_x86_64_network_none"]
    if set(windows["cases"]) != set(linux["cases"]):
        _fail()
    failure_count = success_count = direction_count = repeat_count = 0
    for platform_report in (windows, linux):
        for digest, case in platform_report["cases"].items():
            other = (linux if platform_report is windows else windows)["cases"][digest]
            if tuple(
                case[key] for key in ("candidate", "direction", "magnitude_ppm", "status")
            ) != tuple(other[key] for key in ("candidate", "direction", "magnitude_ppm", "status")):
                _fail()
            if case["status"] == "FAILED":
                failure_count += 1
                if (
                    case["failure_stage"] == "MEASUREMENT"
                    and case["failure_code"] == "TARGET_DIRECTION_MISMATCH"
                ):
                    direction_count += 1
            else:
                success_count += 1
                repeat_count += sum(
                    1 for row_digest, _ in platform_report["rows"] if row_digest == digest
                )
    if (failure_count, success_count, repeat_count, direction_count) != (232, 344, 1032, 14):
        _fail()
    return windows, linux


def validate_cc01c_report_pair_for_manifest(
    windows_report_bytes: object,
    linux_report_bytes: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate legacy reports against only the frozen accepted authority."""
    return _validate_cc01c_report_pair_for_manifest_with_authority(
        windows_report_bytes, linux_report_bytes, _DEFAULT_AUTHORITY
    )


def _authority_document() -> dict[str, Any]:
    return {
        "accepted_stage_c_commit": "042f77e4b6708be827f2033a9740e348ae778f69",
        "accepted_stage_c_run": 32237678569,
        "accepted_stage_c_attempt": 2,
        "candidate_manifest_digest": _CANDIDATE_MANIFEST_DIGEST,
        "stage_b_redacted_evidence_sha256": _STAGE_B_EVIDENCE_DIGEST,
        "cohort_digest": _COHORT_DIGEST,
        "case_set_digest": _CASE_SET_DIGEST,
        "redacted_aggregate_sha256": _REDACTED_AGGREGATE_DIGEST,
        "builder_version": BUILDER_VERSION,
        "harness_version": "p2-m5-cc02-diagnostic-harness-v1",
        "taxonomy_version": "p2-m5-cc02-terminal-taxonomy-v1",
        "private_report_schema": "mirror.p2-m5/CC02-private-platform-diagnostic-report/v1",
        "legacy_report_schema": LEGACY_REPORT_SCHEMA,
        "vision_model_sha256": _MODEL_DIGEST,
        "topology_sha256": _TOPOLOGY_DIGEST,
        "algorithm_version": "opencv-piecewise-affine-v1",
        "platforms": list(PLATFORMS),
        "candidates": list(CANDIDATES),
        "directions": list(DIRECTIONS),
        "magnitudes_ppm": list(MAGNITUDES),
        "terminal_stages": [
            "SOURCE_ADMISSION",
            "SPECIFICATION",
            "CONTROL_POINT_BUILD",
            "WARP_PLAN_AUTHORITY",
            "TRANSFORM",
            "RESULT_VISION_QA",
            "MEASUREMENT_DIRECTION",
            "RESULT_SIGNATURE",
        ],
    }


def _resource_envelope() -> dict[str, Any]:
    return {
        "identity_count": 12,
        "candidate_count": 6,
        "logical_case_count": 288,
        "platform_case_count": 576,
        "legacy_terminal_failure_platform_case_count": 232,
        "legacy_success_platform_case_count": 344,
        "legacy_success_repeat_binding_count": 1032,
        "direction_diagnostic_platform_case_count": 14,
        "direction_measurement_count": 42,
        "maximum_transform_executions": 576,
        "maximum_vision_executions": 604,
        "generation_attempt_count": 0,
        "retry_count": 0,
        "download_count": 0,
        "maximum_concurrency": 1,
        "execution_mode": "WINDOWS_AND_LINUX_SERIAL",
        "maximum_wall_clock_seconds_per_platform": 7200,
        "maximum_wall_clock_seconds_total": 14400,
        "maximum_private_output_bytes_per_platform": 4294967296,
        "maximum_legacy_report_bytes_per_platform": MAX_REPORT_BYTES,
        "maximum_legacy_report_json_depth": MAX_JSON_DEPTH,
    }


def _manifest_from_validated(reports: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    platform_reports = sorted(reports, key=lambda value: value["report"]["platform"])
    case_bindings: list[dict[str, Any]] = []
    repeat_bindings: list[dict[str, Any]] = []
    direction_bindings: list[dict[str, Any]] = []
    report_bindings: list[dict[str, Any]] = []
    for item in platform_reports:
        report = item["report"]
        platform = report["platform"]
        report_bindings.append(
            {
                "platform": platform,
                "legacy_report_sha256": item["sha256"],
                "legacy_report_sha256_basis": "FIRST_BOUND_AFTER_ACCEPTED_CANONICAL_VALIDATION",
                "legacy_report_digest": report["report_digest"],
                "runtime_manifest_digest": report["runtime_manifest_digest"],
            }
        )
        for digest, case in item["cases"].items():
            direction = (
                case.get("failure_stage") == "MEASUREMENT"
                and case.get("failure_code") == "TARGET_DIRECTION_MISMATCH"
            )
            outcome = "TERMINAL_FAILURE" if case["status"] == "FAILED" else "LEGACY_SUCCESS"
            case_bindings.append(
                {
                    "platform": platform,
                    "case_digest": digest,
                    "candidate": case["candidate"],
                    "direction": case["direction"],
                    "magnitude_ppm": case["magnitude_ppm"],
                    "legacy_outcome": outcome,
                    "direction_diagnostic": direction,
                }
            )
            if direction:
                direction_bindings.append(
                    {"platform": platform, "case_digest": digest, "measurement_count": 3}
                )
            if outcome == "LEGACY_SUCCESS":
                for repeat in (1, 2, 3):
                    row = item["rows"][(digest, repeat)]
                    repeat_bindings.append(
                        {
                            "platform": platform,
                            "case_digest": digest,
                            "repeat_index": repeat,
                            "legacy_row_digest": legacy_row_digest(row),
                            "source_sha256": row["source_sha256"],
                            "accepted_result_sha256": row["result_sha256"],
                            "plan_digest": row["plan_digest"],
                        }
                    )
    case_bindings.sort(key=lambda value: (value["platform"], value["case_digest"]))
    repeat_bindings.sort(
        key=lambda value: (value["platform"], value["case_digest"], value["repeat_index"])
    )
    direction_bindings.sort(key=lambda value: (value["platform"], value["case_digest"]))
    return {
        "schema_version": MANIFEST_SCHEMA,
        "status": "PREREGISTERED_NOT_EXECUTED",
        "change_control": "CC-P2-M5-02",
        "task_id": "CC-P2-M5-02-B",
        "authority": _authority_document(),
        "platform_report_bindings": report_bindings,
        "platform_case_bindings": case_bindings,
        "legacy_success_repeat_bindings": repeat_bindings,
        "direction_diagnostic_bindings": direction_bindings,
        "resource_envelope": _resource_envelope(),
        "boundaries": _BOUNDARIES,
        "stop_rules": _STOP_RULES,
    }


def _canonical_json(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            document, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )
        + "\n"
    ).encode()


def _preregistration(manifest: Mapping[str, Any]) -> bytes:
    digest = manifest["manifest_content_digest"]
    text = "\n".join(
        (
            "# P2-M5 CC02 Diagnostic Preregistration",
            "",
            f"- Machine-readable authority: `{REPORT_OUTPUT.as_posix()}`",
            f"- Human authority: `{PREREG_OUTPUT.as_posix()}`",
            f"- Schema: `{MANIFEST_SCHEMA}`",
            "- Status: `PREREGISTERED_NOT_EXECUTED`",
            "- Coverage basis: 12 identities; 6 candidates.",
            "- Counts: 288 logical cases; 576 platform cases; 232 terminal failures;",
            "  344 legacy successes;",
            "  1,032 success-repeat bindings; 14 direction diagnostics; 42 future measurements.",
            "- Resource envelope: maximum transform executions 576; maximum Vision executions 604;",
            "  generation attempts 0; retries 0; downloads 0; maximum concurrency 1;",
            "  Windows and Linux serial execution; maximum wall clock 7,200 seconds per platform",
            "  and 14,400 seconds total; maximum private output 4,294,967,296 bytes per platform;",
            "  legacy report input bounded to 67,108,864 bytes per platform and JSON depth 16.",
            "- Closed gates: CC02-C–E; Stage D/E; T06–T08; MVR; M6; replay; generation; network;",
            "  production geometry; real-user processing; public API; schema/migration;",
            "  dependency/model;",
            "  and QuestionBank release.",
            f"- manifest_content_digest: `{digest}`",
            "",
        )
    )
    return text.encode("utf-8")


def _validate_manifest_bytes_with_authority(
    manifest_bytes: object,
    preregistration_bytes: object,
    authority: object,
) -> None:
    checked_authority = _validated_authority(authority)
    manifest = _safe_json_loads(manifest_bytes)
    expected_keys = {
        "schema_version",
        "status",
        "change_control",
        "task_id",
        "authority",
        "platform_report_bindings",
        "platform_case_bindings",
        "legacy_success_repeat_bindings",
        "direction_diagnostic_bindings",
        "resource_envelope",
        "boundaries",
        "stop_rules",
        "manifest_content_digest",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != expected_keys
        or manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("status") != "PREREGISTERED_NOT_EXECUTED"
        or manifest.get("change_control") != "CC-P2-M5-02"
        or manifest.get("task_id") != "CC-P2-M5-02-B"
        or manifest.get("manifest_content_digest")
        != canonical_digest(MANIFEST_SCHEMA, manifest, "manifest_content_digest")
    ):
        _fail()
    if manifest_bytes != _canonical_json(manifest):
        _fail()
    if not all(
        isinstance(value, list)
        for value in (
            manifest["platform_report_bindings"],
            manifest["platform_case_bindings"],
            manifest["legacy_success_repeat_bindings"],
            manifest["direction_diagnostic_bindings"],
        )
    ):
        _fail()
    report_bindings = manifest["platform_report_bindings"]
    report_keys = {
        "platform",
        "legacy_report_sha256",
        "legacy_report_sha256_basis",
        "legacy_report_digest",
        "runtime_manifest_digest",
    }
    if any(
        not isinstance(value, dict)
        or set(value) != report_keys
        or value.get("platform") not in PLATFORMS
        or value.get("legacy_report_sha256_basis")
        != "FIRST_BOUND_AFTER_ACCEPTED_CANONICAL_VALIDATION"
        or not all(
            _is_digest(value.get(key))
            for key in ("legacy_report_sha256", "legacy_report_digest", "runtime_manifest_digest")
        )
        for value in report_bindings
    ) or report_bindings != sorted(report_bindings, key=lambda value: value["platform"]):
        _fail()
    if [value["platform"] for value in report_bindings] != list(PLATFORMS) or any(
        value["legacy_report_digest"]
        != _expected_report_digest(value["platform"], checked_authority)
        or value["runtime_manifest_digest"]
        != _expected_runtime_digest(value["platform"], checked_authority)
        for value in report_bindings
    ):
        _fail()
    cases = manifest["platform_case_bindings"]
    case_keys = {
        "platform",
        "case_digest",
        "candidate",
        "direction",
        "magnitude_ppm",
        "legacy_outcome",
        "direction_diagnostic",
    }
    if any(
        not isinstance(value, dict)
        or set(value) != case_keys
        or value.get("platform") not in PLATFORMS
        or not _is_digest(value.get("case_digest"))
        or value.get("candidate") not in CANDIDATES
        or value.get("direction") not in DIRECTIONS
        or value.get("magnitude_ppm") not in MAGNITUDES
        or value.get("legacy_outcome") not in {"TERMINAL_FAILURE", "LEGACY_SUCCESS"}
        or type(value.get("direction_diagnostic")) is not bool
        for value in cases
    ) or cases != sorted(
        cases, key=lambda value: (value.get("platform", ""), value.get("case_digest", ""))
    ):
        _fail()
    successes = failures = directions = 0
    cases_by_platform_digest: dict[tuple[str, str], dict[str, Any]] = {}
    by_case: dict[str, list[dict[str, Any]]] = {}
    for value in cases:
        if not isinstance(value, dict) or set(value) != {
            "platform",
            "case_digest",
            "candidate",
            "direction",
            "magnitude_ppm",
            "legacy_outcome",
            "direction_diagnostic",
        }:
            _fail()
        if (
            value.get("platform") not in PLATFORMS
            or not _is_digest(value.get("case_digest"))
            or value.get("candidate") not in CANDIDATES
            or value.get("direction") not in DIRECTIONS
            or value.get("magnitude_ppm") not in MAGNITUDES
            or value.get("legacy_outcome") not in {"TERMINAL_FAILURE", "LEGACY_SUCCESS"}
            or type(value.get("direction_diagnostic")) is not bool
        ):
            _fail()
        if value["direction_diagnostic"] and value["legacy_outcome"] != "TERMINAL_FAILURE":
            _fail()
        platform_digest = (value["platform"], value["case_digest"])
        if platform_digest in cases_by_platform_digest:
            _fail()
        cases_by_platform_digest[platform_digest] = value
        successes += value["legacy_outcome"] == "LEGACY_SUCCESS"
        failures += value["legacy_outcome"] == "TERMINAL_FAILURE"
        directions += value["direction_diagnostic"]
        by_case.setdefault(value["case_digest"], []).append(value)
    if (successes, failures, directions) != (344, 232, 14) or any(
        len(values) != 2
        or values[0]["platform"] == values[1]["platform"]
        or any(
            values[0][key] != values[1][key]
            for key in (
                "candidate",
                "direction",
                "magnitude_ppm",
                "legacy_outcome",
                "direction_diagnostic",
            )
        )
        for values in by_case.values()
    ):
        _fail()
    repeats = manifest["legacy_success_repeat_bindings"]
    repeat_keys = {
        "platform",
        "case_digest",
        "repeat_index",
        "legacy_row_digest",
        "source_sha256",
        "accepted_result_sha256",
        "plan_digest",
    }
    if any(
        not isinstance(value, dict)
        or set(value) != repeat_keys
        or value.get("platform") not in PLATFORMS
        or not _is_int(value.get("repeat_index"))
        or value.get("repeat_index") not in (1, 2, 3)
        or not all(
            _is_digest(value.get(key))
            for key in (
                "case_digest",
                "legacy_row_digest",
                "source_sha256",
                "accepted_result_sha256",
                "plan_digest",
            )
        )
        for value in repeats
    ) or repeats != sorted(
        repeats,
        key=lambda value: (
            value.get("platform", ""),
            value.get("case_digest", ""),
            value.get("repeat_index", 0),
        ),
    ):
        _fail()
    repeats_by_case: dict[tuple[str, str], set[int]] = {}
    if any(
        not isinstance(value, dict)
        or set(value)
        != {
            "platform",
            "case_digest",
            "repeat_index",
            "legacy_row_digest",
            "source_sha256",
            "accepted_result_sha256",
            "plan_digest",
        }
        or value.get("platform") not in PLATFORMS
        or value.get("repeat_index") not in (1, 2, 3)
        or not all(
            _is_digest(value.get(key))
            for key in (
                "case_digest",
                "legacy_row_digest",
                "source_sha256",
                "accepted_result_sha256",
                "plan_digest",
            )
        )
        for value in repeats
    ):
        _fail()
    for value in repeats:
        key = (value["platform"], value["case_digest"])
        if cases_by_platform_digest.get(key, {}).get("legacy_outcome") != "LEGACY_SUCCESS":
            _fail()
        repeats_by_case.setdefault(key, set()).add(value["repeat_index"])
    if set(repeats_by_case) != {
        key
        for key, value in cases_by_platform_digest.items()
        if value["legacy_outcome"] == "LEGACY_SUCCESS"
    } or any(indices != {1, 2, 3} for indices in repeats_by_case.values()):
        _fail()
    directions_bound = manifest["direction_diagnostic_bindings"]
    direction_keys = {"platform", "case_digest", "measurement_count"}
    if any(
        not isinstance(value, dict)
        or set(value) != direction_keys
        or value.get("platform") not in PLATFORMS
        or not _is_digest(value.get("case_digest"))
        or value.get("measurement_count") != 3
        for value in directions_bound
    ) or directions_bound != sorted(
        directions_bound,
        key=lambda value: (value.get("platform", ""), value.get("case_digest", "")),
    ):
        _fail()
    if any(
        not isinstance(value, dict)
        or set(value) != {"platform", "case_digest", "measurement_count"}
        or value.get("measurement_count") != 3
        for value in directions_bound
    ):
        _fail()
    if {(value["platform"], value["case_digest"]) for value in directions_bound} != {
        key for key, value in cases_by_platform_digest.items() if value["direction_diagnostic"]
    }:
        _fail()
    if (
        len(manifest["platform_report_bindings"]),
        len(manifest["platform_case_bindings"]),
        len(manifest["legacy_success_repeat_bindings"]),
        len(manifest["direction_diagnostic_bindings"]),
    ) != (2, 576, 1032, 14):
        _fail()
    if (
        not _matches_frozen_value(manifest["authority"], _authority_document())
        or not _matches_frozen_value(manifest["resource_envelope"], _resource_envelope())
        or not _matches_frozen_value(manifest["boundaries"], _BOUNDARIES)
        or not _matches_frozen_value(manifest["stop_rules"], _STOP_RULES)
    ):
        _fail()
    if not isinstance(preregistration_bytes, bytes) or preregistration_bytes != _preregistration(
        manifest
    ):
        _fail()


def validate_manifest_bytes(
    manifest_bytes: object,
    preregistration_bytes: object,
) -> None:
    """Validate outputs against only the frozen accepted authority."""
    _validate_manifest_bytes_with_authority(
        manifest_bytes, preregistration_bytes, _DEFAULT_AUTHORITY
    )


def _construct_manifest_and_preregistration_with_authority(
    windows_report_bytes: object,
    linux_report_bytes: object,
    authority: object,
) -> tuple[bytes, bytes]:
    """Synthetic-test seam for deterministic construction with placeholder digests."""
    checked_authority = _validated_authority(authority)
    reports = _validate_cc01c_report_pair_for_manifest_with_authority(
        windows_report_bytes, linux_report_bytes, checked_authority
    )
    manifest = _manifest_from_validated(reports)
    manifest["manifest_content_digest"] = canonical_digest(
        MANIFEST_SCHEMA, manifest, "manifest_content_digest"
    )
    manifest_bytes = _canonical_json(manifest)
    preregistration_bytes = _preregistration(manifest)
    _validate_manifest_bytes_with_authority(
        manifest_bytes, preregistration_bytes, checked_authority
    )
    return manifest_bytes, preregistration_bytes


def construct_manifest_and_preregistration(
    windows_report_bytes: object,
    linux_report_bytes: object,
) -> tuple[bytes, bytes]:
    """Return deterministic outputs bound only to the frozen accepted authority."""
    return _construct_manifest_and_preregistration_with_authority(
        windows_report_bytes, linux_report_bytes, _DEFAULT_AUTHORITY
    )


def _read_held_report(path: Path) -> bytes:
    try:
        before = os.lstat(path)
        attributes = getattr(before, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or attributes & reparse
            or before.st_size <= 0
            or before.st_size > MAX_REPORT_BYTES
        ):
            _fail()
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            held = os.fstat(descriptor)
            held_attributes = getattr(held, "st_file_attributes", 0)
            if (
                not stat.S_ISREG(held.st_mode)
                or held_attributes & reparse
                or held.st_dev != before.st_dev
                or held.st_ino != before.st_ino
                or held.st_size != before.st_size
                or held.st_mtime_ns != before.st_mtime_ns
            ):
                _fail()
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(1_048_576, MAX_REPORT_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_REPORT_BYTES:
                    _fail()
                chunks.append(chunk)
            if total != held.st_size or os.read(descriptor, 1):
                _fail()
            after = os.fstat(descriptor)
            final_path = os.lstat(path)
            final_attributes = getattr(final_path, "st_file_attributes", 0)
            if (
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (
                    held.st_dev,
                    held.st_ino,
                    held.st_size,
                    held.st_mtime_ns,
                )
                or (
                    final_path.st_dev,
                    final_path.st_ino,
                    final_path.st_size,
                    final_path.st_mtime_ns,
                )
                != (held.st_dev, held.st_ino, held.st_size, held.st_mtime_ns)
                or not stat.S_ISREG(final_path.st_mode)
                or final_attributes & reparse
            ):
                _fail()
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except (ManifestBuildError, OSError):
        _fail()


def _directory_identity(path: Path) -> _DirectoryIdentity:
    try:
        value = os.lstat(path)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            not stat.S_ISDIR(value.st_mode)
            or stat.S_ISLNK(value.st_mode)
            or getattr(value, "st_file_attributes", 0) & reparse
        ):
            _fail()
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
        except PermissionError:
            # Windows does not permit descriptor opens for ordinary directories.
            return _DirectoryIdentity(value.st_dev, value.st_ino)
        try:
            held = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(held.st_mode)
                or getattr(held, "st_file_attributes", 0) & reparse
                or (held.st_dev, held.st_ino) != (value.st_dev, value.st_ino)
            ):
                _fail()
        finally:
            os.close(descriptor)
        return _DirectoryIdentity(value.st_dev, value.st_ino)
    except (ManifestBuildError, OSError):
        _fail()


def _cleanup_created(anchor: _PublicationAnchor, names: list[str]) -> bool:
    clean = True
    try:
        for name in names:
            try:
                anchor.unlink(name)
            except FileNotFoundError:
                pass
            except OSError:
                clean = False
    finally:
        try:
            anchor.sync_directory()
        except OSError:
            clean = False
    return clean


def _write_incomplete_marker(anchor: _PublicationAnchor) -> _FileIdentity:
    descriptor = anchor.open_exclusive(_INCOMPLETE_MARKER)
    try:
        if os.write(descriptor, _INCOMPLETE_MARKER_BYTES) != len(_INCOMPLETE_MARKER_BYTES):
            raise OSError
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    anchor.sync_directory()
    return anchor.verify_exact_file(_INCOMPLETE_MARKER, _INCOMPLETE_MARKER_BYTES)


def _write_outputs_once_with_authority(
    manifest_bytes: object,
    preregistration_bytes: object,
    *,
    root: Path,
    authority: object,
) -> None:
    """Synthetic-test seam for the fixed-path create-once writer."""
    checked_authority = _validated_authority(authority)
    _validate_manifest_bytes_with_authority(
        manifest_bytes, preregistration_bytes, checked_authority
    )
    final_names = (REPORT_OUTPUT.name, PREREG_OUTPUT.name)
    staging_names = tuple(f".{name}.cc02-staging" for name in final_names)
    with _PublicationAnchor(root) as anchor:
        if any(anchor.exists(name) for name in (*final_names, *staging_names, _INCOMPLETE_MARKER)):
            _fail()
        created_staging: list[str] = []
        descriptors: list[tuple[int, bytes]] = []
        failed = False
        try:
            for name, content in zip(
                staging_names, (manifest_bytes, preregistration_bytes), strict=True
            ):
                descriptor = anchor.open_exclusive(name)
                created_staging.append(name)
                descriptors.append((descriptor, cast(bytes, content)))
            for descriptor, content in descriptors:
                offset = 0
                while offset < len(content):
                    written = os.write(descriptor, content[offset:])
                    if written <= 0:
                        raise OSError
                    offset += written
                os.fsync(descriptor)
        except OSError:
            failed = True
        finally:
            for descriptor, _ in descriptors:
                try:
                    os.close(descriptor)
                except OSError:
                    failed = True
        if failed or not anchor.unchanged():
            _cleanup_created(anchor, created_staging)
            _fail()
        try:
            staging_records = {
                name: anchor.verify_exact_file(name, content)
                for name, content in zip(
                    staging_names,
                    (cast(bytes, manifest_bytes), cast(bytes, preregistration_bytes)),
                    strict=True,
                )
            }
        except OSError:
            _cleanup_created(anchor, created_staging)
            _fail()
        published: list[str] = []
        final_records: dict[str, _FileIdentity] = {}
        marker_created = False
        marker_record: _FileIdentity | None = None
        try:
            marker_created = True
            marker_record = _write_incomplete_marker(anchor)
            if not anchor.unchanged():
                raise OSError
            for staging, final, content in zip(
                staging_names,
                final_names,
                (cast(bytes, manifest_bytes), cast(bytes, preregistration_bytes)),
                strict=True,
            ):
                if (
                    marker_record is None
                    or anchor.verify_exact_file(_INCOMPLETE_MARKER, _INCOMPLETE_MARKER_BYTES)
                    != marker_record
                ):
                    raise OSError
                if anchor.verify_exact_file(staging, content) != staging_records[staging]:
                    raise OSError
                anchor.link(staging, final)
                published.append(final)
                final_record = anchor.verify_exact_file(final, content)
                if final_record != staging_records[staging]:
                    raise OSError
                final_records[final] = final_record
                anchor.sync_directory()
            if (
                marker_record is None
                or anchor.verify_exact_file(_INCOMPLETE_MARKER, _INCOMPLETE_MARKER_BYTES)
                != marker_record
            ):
                raise OSError
            if not anchor.unchanged() or not _cleanup_created(anchor, created_staging):
                raise OSError
            for final, content in zip(
                final_names,
                (cast(bytes, manifest_bytes), cast(bytes, preregistration_bytes)),
                strict=True,
            ):
                if anchor.verify_exact_file(final, content) != final_records[final]:
                    raise OSError
            if (
                marker_record is None
                or anchor.verify_exact_file(_INCOMPLETE_MARKER, _INCOMPLETE_MARKER_BYTES)
                != marker_record
                or not anchor.unchanged()
            ):
                raise OSError
            anchor.unlink(_INCOMPLETE_MARKER)
            marker_created = False
            try:
                anchor.sync_directory()
            except OSError:
                # Marker unlink is the logical commit transition. Every final link and
                # staging cleanup was already directory-synced. Rolling back after this
                # point can turn two exact outputs into an unmarked partial residue.
                # A crash before the unlink is durable can only restore the already
                # durable conservative marker, so a post-commit sync error is not a
                # reason to start a second transaction or report a false failure.
                pass
        except OSError:
            cleanup_succeeded = _cleanup_created(anchor, [*published, *created_staging])
            if marker_created and marker_record is None and not published:
                try:
                    marker_record = anchor.verify_exact_file(
                        _INCOMPLETE_MARKER, _INCOMPLETE_MARKER_BYTES
                    )
                except OSError:
                    pass
            if marker_created and cleanup_succeeded:
                try:
                    if (
                        marker_record is None
                        or anchor.verify_exact_file(_INCOMPLETE_MARKER, _INCOMPLETE_MARKER_BYTES)
                        != marker_record
                    ):
                        raise OSError
                    anchor.unlink(_INCOMPLETE_MARKER)
                    marker_created = False
                    anchor.sync_directory()
                except OSError:
                    if not anchor.exists(_INCOMPLETE_MARKER):
                        try:
                            marker_record = _write_incomplete_marker(anchor)
                            marker_created = True
                        except OSError:
                            pass
                    cleanup_succeeded = False
            if not cleanup_succeeded:
                _fail()
            _fail()


def write_outputs_once(
    manifest_bytes: object,
    preregistration_bytes: object,
) -> None:
    """Create both fixed outputs under frozen authority and ADR-048 custody."""
    _write_outputs_once_with_authority(
        manifest_bytes,
        preregistration_bytes,
        root=REPOSITORY_ROOT,
        authority=_DEFAULT_AUTHORITY,
    )


def main() -> int:
    windows_path = os.environ.get("CC02_WINDOWS_LEGACY_REPORT_PATH")
    linux_path = os.environ.get("CC02_LINUX_LEGACY_REPORT_PATH")
    if not windows_path or not linux_path:
        print(f"FAIL {STOP_OUTCOME}")
        return 1
    try:
        manifest, preregistration = construct_manifest_and_preregistration(
            _read_held_report(Path(windows_path)), _read_held_report(Path(linux_path))
        )
        write_outputs_once(manifest, preregistration)
    except ManifestBuildError:
        print(f"FAIL {STOP_OUTCOME}")
        return 1
    print("PASS CC02_MANIFEST_CREATED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
