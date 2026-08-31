"""Deterministic CC08 builder/input-lock materializer and verifier.

This tool handles public build inputs and private, task-owned manifests only.
It never reads image bytes for inference, loads a model, invokes Vision, or
prints an absolute path. Private roots are supplied explicitly by the
Principal and are represented in outputs only by logical labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

MANIFEST_SCHEMA = "mirror.p2-m5.cc08-private-input-manifest/v1"
LOCK_SCHEMA = "mirror.p2-m5.cc08-builder-input-lock/v1"
_REPARSE_POINT = 0x0400


class LockError(RuntimeError):
    """Raised when a builder/input authority fails closed."""


def _fail(message: str) -> NoReturn:
    raise LockError(message)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _sealed(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    payload.pop("content_sha256", None)
    result = dict(payload)
    result["content_sha256"] = _sha256_bytes(_canonical_bytes(payload))
    return result


def _verify_seal(value: Mapping[str, Any], *, expected_schema: str) -> None:
    if value.get("schema_version") != expected_schema:
        _fail("schema version mismatch")
    expected = value.get("content_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        _fail("content digest missing")
    payload = dict(value)
    payload.pop("content_sha256", None)
    if _sha256_bytes(_canonical_bytes(payload)) != expected:
        _fail("content digest mismatch")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LockError("JSON input is unreadable") from exc
    if not isinstance(value, dict):
        _fail("JSON authority must be an object")
    return value


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        _fail("output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(value)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _normalized_relative(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace("\\", "/"))
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        _fail("non-canonical relative path")
    if normalized != path.as_posix():
        _fail("relative path normalization mismatch")
    return normalized


def _is_reparse(stat_result: os.stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(attributes & _REPARSE_POINT)


def _excluded(relative: str, exclusions: Sequence[str]) -> bool:
    return any(relative == item or relative.startswith(f"{item}/") for item in exclusions)


def _walk_files(root: Path, exclusions: Sequence[str]) -> list[tuple[str, Path]]:
    if not root.is_dir():
        _fail("input root is not a directory")
    results: list[tuple[str, Path]] = []
    pending: list[tuple[str, Path]] = [("", root)]
    seen_casefold: set[str] = set()
    while pending:
        prefix, directory = pending.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise LockError("input directory is unreadable") from exc
        for child in children:
            relative = _normalized_relative(f"{prefix}/{child.name}".lstrip("/"))
            if _excluded(relative, exclusions):
                continue
            folded = relative.casefold()
            if folded in seen_casefold:
                _fail("case-insensitive path collision")
            seen_casefold.add(folded)
            try:
                metadata = child.lstat()
            except OSError as exc:
                raise LockError("input entry metadata is unreadable") from exc
            if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
                _fail(f"link or reparse point rejected: {relative}")
            if stat.S_ISDIR(metadata.st_mode):
                pending.append((relative, child))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                _fail(f"special file rejected: {relative}")
            results.append((relative, child))
    results.sort(key=lambda item: item[0])
    return results


def _parse_inputs(values: Sequence[str]) -> list[tuple[str, Path]]:
    parsed: list[tuple[str, Path]] = []
    labels: set[str] = set()
    for value in values:
        label, separator, path_value = value.partition("=")
        if not separator or not label or not path_value:
            _fail("input must use LABEL=PATH")
        label = _normalized_relative(label)
        if "/" in label or label in labels:
            _fail("input label must be unique and single-segment")
        labels.add(label)
        parsed.append((label, Path(path_value)))
    if not parsed:
        _fail("at least one input is required")
    return sorted(parsed, key=lambda item: item[0])


def _manifest_payload(
    *,
    kind: str,
    inputs: Sequence[tuple[str, Path]],
    exclusions: Sequence[str],
) -> dict[str, Any]:
    normalized_exclusions = sorted({_normalized_relative(item) for item in exclusions})
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    all_paths: set[str] = set()
    for label, root in inputs:
        for relative, path in _walk_files(root, normalized_exclusions):
            logical = _normalized_relative(f"{label}/{relative}")
            if logical in all_paths:
                _fail("logical input path collision")
            all_paths.add(logical)
            size = path.stat().st_size
            entries.append(
                {
                    "relative_path": logical,
                    "byte_size": size,
                    "sha256": _sha256_file(path),
                }
            )
            total_bytes += size
    entries.sort(key=lambda item: item["relative_path"])
    return _sealed(
        {
            "schema_version": MANIFEST_SCHEMA,
            "kind": kind,
            "algorithm": "sorted-nfc-posix-relative-path-size-sha256-v1",
            "input_labels": [label for label, _root in inputs],
            "excluded_relative_prefixes": normalized_exclusions,
            "entry_count": len(entries),
            "total_bytes": total_bytes,
            "entries": entries,
        }
    )


def _manifest_command(args: argparse.Namespace) -> None:
    manifest = _manifest_payload(
        kind=args.kind,
        inputs=_parse_inputs(args.input),
        exclusions=args.exclude,
    )
    _write_new_json(Path(args.output), manifest)
    print(
        "MANIFEST_CREATED "
        f"kind={manifest['kind']} entries={manifest['entry_count']} "
        f"bytes={manifest['total_bytes']} content_sha256={manifest['content_sha256']}"
    )


def _verify_manifest_command(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    expected = _load_json(manifest_path)
    _verify_seal(expected, expected_schema=MANIFEST_SCHEMA)
    inputs = _parse_inputs(args.input)
    if [label for label, _root in inputs] != expected.get("input_labels"):
        _fail("manifest input labels mismatch")
    actual = _manifest_payload(
        kind=str(expected.get("kind")),
        inputs=inputs,
        exclusions=list(expected.get("excluded_relative_prefixes", [])),
    )
    if actual != expected:
        _fail("manifest entries mismatch")
    print(
        "MANIFEST_VERIFIED "
        f"kind={expected['kind']} entries={expected['entry_count']} "
        f"bytes={expected['total_bytes']} content_sha256={expected['content_sha256']}"
    )


def _run_git(arguments: Sequence[str], *, cwd: Path | None = None) -> str:
    executable = shutil.which("git")
    if executable is None:
        _fail("git executable unavailable")
    try:
        result = subprocess.run(  # noqa: S603 - executable and arguments are task-owned.
            [executable, *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LockError("git operation failed") from exc
    return result.stdout.strip()


def _materialize_source_command(args: argparse.Namespace) -> None:
    lock = _load_json(Path(args.lock))
    source = lock.get("source")
    patches = lock.get("patches")
    if not isinstance(source, dict) or not isinstance(patches, list):
        _fail("lock source or patches missing")
    commit = source.get("commit")
    if not isinstance(commit, str) or len(commit) != 40:
        _fail("source commit invalid")
    destination = Path(args.destination)
    if destination.exists():
        _fail("source destination already exists")
    base = Path(args.base_repository)
    if not base.is_dir():
        _fail("base repository unavailable")
    if _run_git(["rev-parse", "HEAD"], cwd=base) != commit:
        _fail("base source commit mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run_git(["clone", "--local", "--no-hardlinks", "--no-checkout", str(base), str(destination)])
    try:
        _run_git(["config", "--local", "core.autocrlf", "false"], cwd=destination)
        _run_git(["config", "--local", "core.eol", "lf"], cwd=destination)
        _run_git(["config", "--local", "core.longpaths", "true"], cwd=destination)
        _run_git(["checkout", "--detach", commit], cwd=destination)
        if _run_git(["rev-parse", "HEAD"], cwd=destination) != commit:
            _fail("materialized source commit mismatch")
        for expected_order, item in enumerate(patches, start=1):
            if not isinstance(item, dict) or item.get("order") != expected_order:
                _fail("patch order is not contiguous")
            relative_path = item.get("path")
            expected_sha = item.get("sha256")
            if not isinstance(relative_path, str) or not isinstance(expected_sha, str):
                _fail("patch authority incomplete")
            patch_path = Path(args.project_root) / relative_path
            if not patch_path.is_file() or _sha256_file(patch_path) != expected_sha:
                _fail("patch digest mismatch")
            _run_git(["apply", "--check", str(patch_path)], cwd=destination)
            _run_git(["apply", str(patch_path)], cwd=destination)
    except BaseException:
        # The destination is task-owned but may contain forensic failure evidence.
        # Never delete it automatically.
        raise
    print(f"SOURCE_MATERIALIZED commit={commit} patch_count={len(patches)}")


def _dpkg_field(path: Path, field: str) -> str:
    executable = shutil.which("dpkg-deb")
    if executable is None:
        _fail("dpkg-deb executable unavailable")
    try:
        result = subprocess.run(  # noqa: S603 - exact local package and fixed field only.
            [executable, "--field", str(path), field],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LockError("Debian package metadata inspection failed") from exc
    value = result.stdout.strip()
    if not value or "\n" in value or "\r" in value:
        _fail("Debian package field invalid")
    return value


def _deb_inventory_command(args: argparse.Namespace) -> None:
    root = Path(args.root)
    if not root.is_dir():
        _fail("Debian package root unavailable")
    packages: list[dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(root.glob("*.deb"), key=lambda item: item.name):
        if path.is_symlink() or _is_reparse(path.lstat()):
            _fail("Debian package link rejected")
        size = path.stat().st_size
        packages.append(
            {
                "filename": path.name,
                "package": _dpkg_field(path, "Package"),
                "version": _dpkg_field(path, "Version"),
                "architecture": _dpkg_field(path, "Architecture"),
                "byte_size": size,
                "sha256": _sha256_file(path),
            }
        )
        total_bytes += size
    if not packages:
        _fail("Debian package bundle empty")
    value = _sealed(
        {
            "schema_version": MANIFEST_SCHEMA,
            "kind": "linux-builder-debian-package-bundle",
            "algorithm": "dpkg-field-filename-size-sha256-v1",
            "input_labels": ["debs"],
            "excluded_relative_prefixes": [],
            "entry_count": len(packages),
            "total_bytes": total_bytes,
            "entries": packages,
        }
    )
    _write_new_json(Path(args.output), value)
    print(
        "DEB_INVENTORY_CREATED "
        f"entries={value['entry_count']} bytes={value['total_bytes']} "
        f"content_sha256={value['content_sha256']}"
    )


def _run_text(arguments: Sequence[str]) -> str:
    if not arguments or arguments[0] != "docker":
        _fail("external inventory executable not allowlisted")
    executable = shutil.which("docker")
    if executable is None:
        _fail("docker executable unavailable")
    try:
        result = subprocess.run(  # noqa: S603 - fixed Docker inventory commands only.
            [executable, *arguments[1:]],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LockError("external inventory command failed") from exc
    return result.stdout.strip()


def _linux_builder_inventory_command(args: argparse.Namespace) -> None:
    image_json = _run_text(["docker", "image", "inspect", args.image])
    try:
        inspected = json.loads(image_json)
    except json.JSONDecodeError as exc:
        raise LockError("Docker image inspection is invalid") from exc
    if not isinstance(inspected, list) or len(inspected) != 1 or not isinstance(inspected[0], dict):
        _fail("Docker image inspection shape invalid")
    image = inspected[0]
    package_output = _run_text(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            args.image,
            "dpkg-query",
            "--show",
            "--showformat=${Package}\\t${Version}\\t${Architecture}\\t${Installed-Size}\\n",
        ]
    )
    packages: list[dict[str, Any]] = []
    installed_kib = 0
    for line in package_output.splitlines():
        fields = line.split("\t")
        if len(fields) != 4:
            _fail("installed package inventory line invalid")
        name, version, architecture, size_value = fields
        try:
            size_kib = int(size_value)
        except ValueError as exc:
            raise LockError("installed package size invalid") from exc
        packages.append(
            {
                "package": name,
                "version": version,
                "architecture": architecture,
                "installed_size_kib": size_kib,
            }
        )
        installed_kib += size_kib
    packages.sort(key=lambda item: (item["package"], item["architecture"]))
    tools: dict[str, str] = {}
    commands = {
        "python": ["python", "--version"],
        "gcc": ["gcc", "-dumpfullversion"],
        "cmake": ["cmake", "--version"],
        "ninja": ["ninja", "--version"],
        "bazel": ["bazel", "--version"],
    }
    for name, command in commands.items():
        tools[name] = _run_text(
            ["docker", "run", "--rm", "--network", "none", "--read-only", args.image, *command]
        ).splitlines()[0]
    semantic_payload = {
        "architecture": image.get("Architecture"),
        "os": image.get("Os"),
        "tools": tools,
        "entries": packages,
    }
    value = _sealed(
        {
            "schema_version": MANIFEST_SCHEMA,
            "kind": "linux-builder-image-inventory",
            "algorithm": "docker-image-id-plus-dpkg-query-v1",
            "input_labels": ["linux_builder_image"],
            "excluded_relative_prefixes": [],
            "image_id": image.get("Id"),
            "architecture": image.get("Architecture"),
            "os": image.get("Os"),
            "image_size_bytes": image.get("Size"),
            "tools": tools,
            "semantic_content_sha256": _sha256_bytes(_canonical_bytes(semantic_payload)),
            "entry_count": len(packages),
            "total_bytes": installed_kib * 1024,
            "entries": packages,
        }
    )
    _write_new_json(Path(args.output), value)
    print(
        "LINUX_BUILDER_INVENTORY_CREATED "
        f"entries={value['entry_count']} image_id={value['image_id']} "
        f"content_sha256={value['content_sha256']}"
    )


def _verify_public_artifacts(lock: Mapping[str, Any], root: Path) -> None:
    artifacts = lock.get("public_artifacts")
    if not isinstance(artifacts, list):
        _fail("public artifact lock missing")
    for item in artifacts:
        if not isinstance(item, dict):
            _fail("public artifact entry invalid")
        filename = item.get("filename")
        expected_sha = item.get("sha256")
        expected_size = item.get("byte_size")
        if not isinstance(filename, str) or not isinstance(expected_sha, str):
            _fail("public artifact entry incomplete")
        path = root / filename
        if (
            not path.is_file()
            or path.stat().st_size != expected_size
            or _sha256_file(path) != expected_sha
        ):
            _fail("public artifact mismatch")


def _verify_lock_command(args: argparse.Namespace) -> None:
    lock = _load_json(Path(args.lock))
    _verify_seal(lock, expected_schema=LOCK_SCHEMA)
    patches = lock.get("patches")
    if not isinstance(patches, list):
        _fail("patch lock missing")
    for expected_order, item in enumerate(patches, start=1):
        if not isinstance(item, dict) or item.get("order") != expected_order:
            _fail("patch order mismatch")
        patch_path = Path(args.project_root) / str(item.get("path", ""))
        if not patch_path.is_file() or _sha256_file(patch_path) != item.get("sha256"):
            _fail("tracked patch mismatch")
    _verify_public_artifacts(lock, Path(args.public_root))
    private_manifests = lock.get("private_manifest_bindings")
    supplied = dict(_parse_inputs(args.private_manifest))
    if not isinstance(private_manifests, list):
        _fail("private manifest bindings missing")
    if {item.get("id") for item in private_manifests if isinstance(item, dict)} != set(supplied):
        _fail("private manifest set mismatch")
    for item in private_manifests:
        if not isinstance(item, dict):
            _fail("private manifest binding invalid")
        manifest_id = item.get("id")
        manifest_path = supplied.get(str(manifest_id))
        if manifest_path is None or not manifest_path.is_file():
            _fail("private manifest unavailable")
        value = _load_json(manifest_path)
        _verify_seal(value, expected_schema=MANIFEST_SCHEMA)
        if (
            _sha256_file(manifest_path) != item.get("file_sha256")
            or value.get("content_sha256") != item.get("content_sha256")
            or value.get("entry_count") != item.get("entry_count")
            or value.get("total_bytes") != item.get("total_bytes")
        ):
            _fail("private manifest binding mismatch")
    print(
        "BUILDER_INPUT_LOCK_VERIFIED "
        f"version={lock.get('lock_version')} content_sha256={lock['content_sha256']}"
    )


def _seal_json_command(args: argparse.Namespace) -> None:
    value = _load_json(Path(args.input))
    if value.get("content_sha256") not in {None, ""}:
        _fail("input JSON is already sealed")
    value.pop("content_sha256", None)
    sealed = _sealed(value)
    _write_new_json(Path(args.output), sealed)
    print(f"JSON_SEALED content_sha256={sealed['content_sha256']}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("--kind", required=True)
    manifest.add_argument("--input", action="append", required=True)
    manifest.add_argument("--exclude", action="append", default=[])
    manifest.add_argument("--output", required=True)
    manifest.set_defaults(handler=_manifest_command)

    verify_manifest = subparsers.add_parser("verify-manifest")
    verify_manifest.add_argument("--manifest", required=True)
    verify_manifest.add_argument("--input", action="append", required=True)
    verify_manifest.set_defaults(handler=_verify_manifest_command)

    materialize = subparsers.add_parser("materialize-source")
    materialize.add_argument("--lock", required=True)
    materialize.add_argument("--project-root", required=True)
    materialize.add_argument("--base-repository", required=True)
    materialize.add_argument("--destination", required=True)
    materialize.set_defaults(handler=_materialize_source_command)

    deb_inventory = subparsers.add_parser("deb-inventory")
    deb_inventory.add_argument("--root", required=True)
    deb_inventory.add_argument("--output", required=True)
    deb_inventory.set_defaults(handler=_deb_inventory_command)

    linux_builder_inventory = subparsers.add_parser("linux-builder-inventory")
    linux_builder_inventory.add_argument("--image", required=True)
    linux_builder_inventory.add_argument("--output", required=True)
    linux_builder_inventory.set_defaults(handler=_linux_builder_inventory_command)

    seal_json = subparsers.add_parser("seal-json")
    seal_json.add_argument("--input", required=True)
    seal_json.add_argument("--output", required=True)
    seal_json.set_defaults(handler=_seal_json_command)

    verify_lock = subparsers.add_parser("verify-lock")
    verify_lock.add_argument("--lock", required=True)
    verify_lock.add_argument("--project-root", required=True)
    verify_lock.add_argument("--public-root", required=True)
    verify_lock.add_argument("--private-manifest", action="append", required=True)
    verify_lock.set_defaults(handler=_verify_lock_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except LockError as exc:
        print(f"CC08_BUILDER_LOCK_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
