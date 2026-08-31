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
import re
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
INVOCATION_SCHEMA = "mirror.p2-m5.cc08-builder-invocation/v2"
BUILDER_IDENTITY_SCHEMA = "mirror.p2-m5.cc08-builder-identity/v2"
BUILDER_DOCKERFILE_VERSION = "p2-m5-cc08-builder-dockerfile-v2-run-network-none"
LOCKED_INVOCATION_VERSION = "p2-m5-cc08-builder-invocation-v2-run-network-none"
ROOT_VALIDATION_ALGORITHM_VERSION = "p2-m5-exact-root-chain-no-reparse-v2"
_REPARSE_POINT = 0x0400
_ROOT_MARKER_NAME = ".mirror-cc08-root-authority"
_NETWORK_FETCH = re.compile(
    r"(?:^|[;&|()\s])(?:curl|wget|git|npm|pnpm|yarn|pip|pip3|apt|apt-get)(?:$|\s)",
    re.IGNORECASE,
)
_REMOTE_REFERENCE = re.compile(r"(?:https?|git|ssh)://|git@", re.IGNORECASE)


class LockError(RuntimeError):
    """Raised when a builder/input authority fails closed."""


def _fail(message: str) -> NoReturn:
    raise LockError(message)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    _require_regular_file(path, label="input file")
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
    _require_regular_file(path, label="JSON input")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LockError("JSON input is unreadable") from exc
    if not isinstance(value, dict):
        _fail("JSON authority must be an object")
    return value


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    if os.path.lexists(path):
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


def _write_new_bytes(path: Path, value: bytes) -> None:
    if os.path.lexists(path):
        _fail("output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
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


def _lstat(path: Path, *, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise LockError(f"{label} metadata is unreadable") from exc
    if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
        _fail(f"{label} link or reparse point rejected")
    return metadata


def _require_directory(path: Path, *, label: str) -> os.stat_result:
    metadata = _lstat(path, label=label)
    if not stat.S_ISDIR(metadata.st_mode):
        _fail(f"{label} is not a directory")
    return metadata


def _require_regular_file(path: Path, *, label: str) -> os.stat_result:
    metadata = _lstat(path, label=label)
    if not stat.S_ISREG(metadata.st_mode):
        _fail(f"{label} is not a regular file")
    return metadata


def _root_validation_algorithm_sha256() -> str:
    specification = {
        "version": ROOT_VALIDATION_ALGORITHM_VERSION,
        "path_semantics": "absolute-lexical-no-parent-segment",
        "containment": "authorized-parent-commonpath-before-content-read",
        "metadata": "lstat-no-follow-every-chain-component",
        "windows_rejections": ["symlink", "file-attribute-reparse-point"],
        "posix_rejections": ["symlink", "non-directory", "nested-mount-point"],
        "lifecycle": ["post-create", "pre-seal", "fresh-process-verify"],
        "path_disclosure": "sha256-only",
    }
    return _sha256_bytes(_canonical_bytes(specification))


def _lexical_absolute(path: Path, *, label: str) -> Path:
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        _fail(f"{label} must be an absolute path without traversal")
    normalized = Path(os.path.abspath(os.fspath(path)))
    if normalized != path:
        _fail(f"{label} must be lexically canonical")
    return normalized


def _contained_chain(authorized_parent: Path, exact_root: Path) -> list[Path]:
    parent = _lexical_absolute(authorized_parent, label="authorized parent")
    root = _lexical_absolute(exact_root, label="exact root")
    try:
        common = os.path.commonpath((os.fspath(parent), os.fspath(root)))
    except ValueError as exc:
        raise LockError("exact root containment cannot be established") from exc
    if os.path.normcase(common) != os.path.normcase(os.fspath(parent)):
        _fail("exact root escapes authorized parent")
    relative = os.path.relpath(os.fspath(root), os.fspath(parent))
    if relative == ".":
        return [parent]
    relative_path = Path(relative)
    if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
        _fail("exact root relative chain is invalid")
    chain = [parent]
    current = parent
    for part in relative_path.parts:
        current = current / part
        chain.append(current)
    return chain


def _verify_exact_root_chain_no_reparse(
    authorized_parent: Path,
    exact_root: Path,
) -> dict[str, Any]:
    chain = _contained_chain(authorized_parent, exact_root)
    records: list[dict[str, int]] = []
    for index, component in enumerate(chain):
        metadata = _lstat(component, label="authorized root-chain component")
        if not stat.S_ISDIR(metadata.st_mode):
            _fail("authorized root-chain component is not a directory")
        if os.name != "nt" and os.path.ismount(component):
            _fail("mount point rejected in authorized root chain")
        records.append(
            {
                "index": index,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
                "file_type": int(stat.S_IFMT(metadata.st_mode)),
                "file_attributes": int(getattr(metadata, "st_file_attributes", 0)),
            }
        )
    parent = _lexical_absolute(authorized_parent, label="authorized parent")
    root = _lexical_absolute(exact_root, label="exact root")
    marker_path = root / _ROOT_MARKER_NAME
    marker_sha256: str | None = None
    if os.path.lexists(marker_path):
        marker_sha256 = _sha256_file(marker_path)
    return _sealed(
        {
            "schema_version": "mirror.p2-m5.cc08-root-chain-proof/v2",
            "algorithm_version": ROOT_VALIDATION_ALGORITHM_VERSION,
            "algorithm_sha256": _root_validation_algorithm_sha256(),
            "authorized_parent_sha256": _sha256_bytes(
                os.path.normcase(os.fspath(parent)).encode("utf-8")
            ),
            "exact_root_sha256": _sha256_bytes(os.path.normcase(os.fspath(root)).encode("utf-8")),
            "chain_depth": len(records),
            "records": records,
            "creation_marker_sha256": marker_sha256,
        }
    )


def _verify_root_chain_unchanged(
    expected: Mapping[str, Any],
    authorized_parent: Path,
    exact_root: Path,
) -> None:
    _verify_seal(expected, expected_schema="mirror.p2-m5.cc08-root-chain-proof/v2")
    if _verify_exact_root_chain_no_reparse(authorized_parent, exact_root) != expected:
        _fail("authorized root chain changed after initial verification")


def _create_new_exact_root(authorized_parent: Path, exact_root: Path) -> dict[str, Any]:
    parent = exact_root.parent
    _verify_exact_root_chain_no_reparse(authorized_parent, parent)
    if os.path.lexists(exact_root):
        _fail("exact root already exists")
    try:
        exact_root.mkdir()
    except OSError as exc:
        raise LockError("exact root creation failed") from exc
    _verify_exact_root_chain_no_reparse(authorized_parent, exact_root)
    _write_new_bytes(exact_root / _ROOT_MARKER_NAME, os.urandom(32))
    return _verify_exact_root_chain_no_reparse(authorized_parent, exact_root)


def _excluded(relative: str, exclusions: Sequence[str]) -> bool:
    return any(relative == item or relative.startswith(f"{item}/") for item in exclusions)


def _walk_files(root: Path, exclusions: Sequence[str]) -> list[tuple[str, Path]]:
    _require_directory(root, label="input root")
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
                _fail("input entry link or reparse point rejected")
            if stat.S_ISDIR(metadata.st_mode):
                pending.append((relative, child))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                _fail("input entry special file rejected")
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


def _canonical_lf_text(path: Path, *, label: str) -> tuple[str, str]:
    _require_regular_file(path, label=label)
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise LockError(f"{label} is unreadable") from exc
    if not raw or b"\r" in raw or not raw.endswith(b"\n") or text.startswith("\ufeff"):
        _fail(f"{label} must use canonical UTF-8 LF bytes")
    return text, _sha256_bytes(raw)


def _dockerfile_instructions(text: str) -> list[tuple[str, str]]:
    instructions: list[tuple[str, str]] = []
    pending = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        pending = f"{pending} {stripped}".strip() if pending else stripped
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
            continue
        verb, separator, body = pending.partition(" ")
        if not separator or not body.strip():
            _fail("Dockerfile instruction is malformed")
        instructions.append((verb.upper(), body.strip()))
        pending = ""
    if pending:
        _fail("Dockerfile has an unterminated continuation")
    if not instructions:
        _fail("Dockerfile has no executable instructions")
    return instructions


def _verify_builder_dockerfile(
    path: Path,
    *,
    expected_base_reference: str,
) -> dict[str, Any]:
    text, file_sha256 = _canonical_lf_text(path, label="builder Dockerfile")
    if "# syntax=" in text:
        _fail("external Dockerfile frontend directive is not authorized")
    instructions = _dockerfile_instructions(text)
    from_values = [body.split()[0] for verb, body in instructions if verb == "FROM"]
    if from_values != [expected_base_reference]:
        _fail("builder Dockerfile base authority mismatch")
    run_bodies = [body for verb, body in instructions if verb == "RUN"]
    if not run_bodies:
        _fail("builder Dockerfile has no RUN instruction")
    for body in run_bodies:
        if not body.startswith("--network=none "):
            _fail("builder Dockerfile RUN is missing network none")
        if _NETWORK_FETCH.search(body):
            _fail("builder Dockerfile contains a network acquisition command")
    for verb, body in instructions:
        if verb == "ADD" and _REMOTE_REFERENCE.search(body):
            _fail("builder Dockerfile contains remote ADD")
    if "@sha256:" not in expected_base_reference:
        _fail("builder Dockerfile base reference is not digest pinned")
    base_digest = expected_base_reference.rsplit("@sha256:", 1)[1]
    if not re.fullmatch(r"[0-9a-f]{64}", base_digest):
        _fail("builder Dockerfile base digest is invalid")
    return _sealed(
        {
            "schema_version": "mirror.p2-m5.cc08-builder-dockerfile-proof/v2",
            "dockerfile_version": BUILDER_DOCKERFILE_VERSION,
            "file_sha256": file_sha256,
            "base_reference": expected_base_reference,
            "base_digest": base_digest,
            "instruction_count": len(instructions),
            "run_count": len(run_bodies),
            "run_network": "NONE_PER_RUN",
            "remote_add": False,
            "network_acquisition_commands": False,
            "frontend": "DOCKER_ENGINE_BUNDLED_NO_EXTERNAL_DIRECTIVE",
            "canonical_lf": True,
        }
    )


def _validate_digest(value: object, *, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _build_argv(
    *,
    docker_executable: Path,
    dockerfile: Path,
    context_root: Path,
    output_tag: str,
) -> list[str]:
    if re.fullmatch(r"mirror-cc08-r58-builder-(?:authority|reconstruction):v2", output_tag) is None:
        _fail("builder output tag is not allowlisted")
    return [
        os.fspath(docker_executable),
        "build",
        "--network=none",
        "--pull=false",
        "--no-cache",
        "--provenance=false",
        "--progress=plain",
        "--file",
        os.fspath(dockerfile),
        "--tag",
        output_tag,
        os.fspath(context_root),
    ]


def _builder_invocation_payload(
    *,
    authorized_parent: Path,
    task_root: Path,
    docker_executable: Path,
    docker_client_version: str,
    docker_server_version: str,
    dockerfile: Path,
    context_root: Path,
    base_reference: str,
    base_image_id: str,
    input_authority_content_sha256: str,
) -> dict[str, Any]:
    task_proof = _verify_exact_root_chain_no_reparse(authorized_parent, task_root)
    context_proof = _verify_exact_root_chain_no_reparse(authorized_parent, context_root)
    dockerfile_parent_proof = _verify_exact_root_chain_no_reparse(
        authorized_parent, dockerfile.parent
    )
    dockerfile_proof = _verify_builder_dockerfile(
        dockerfile,
        expected_base_reference=base_reference,
    )
    executable_sha256 = _sha256_file(docker_executable)
    input_digest = _validate_digest(
        input_authority_content_sha256,
        label="input authority content digest",
    )
    if not docker_client_version or not docker_server_version:
        _fail("Docker client/server identity is incomplete")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", base_image_id) is None:
        _fail("base image ID is invalid")
    builds: list[dict[str, Any]] = []
    for role, tag in (
        ("AUTHORITY", "mirror-cc08-r58-builder-authority:v2"),
        ("RECONSTRUCTION", "mirror-cc08-r58-builder-reconstruction:v2"),
    ):
        builds.append(
            {
                "role": role,
                "output_tag": tag,
                "argv": _build_argv(
                    docker_executable=docker_executable,
                    dockerfile=dockerfile,
                    context_root=context_root,
                    output_tag=tag,
                ),
            }
        )
    return _sealed(
        {
            "schema_version": INVOCATION_SCHEMA,
            "invocation_version": LOCKED_INVOCATION_VERSION,
            "task_id": "P2-M5-R58",
            "authorized_parent": os.fspath(authorized_parent),
            "task_root": os.fspath(task_root),
            "context_root": os.fspath(context_root),
            "dockerfile_path": os.fspath(dockerfile),
            "dockerfile_version": BUILDER_DOCKERFILE_VERSION,
            "dockerfile_sha256": dockerfile_proof["file_sha256"],
            "docker_executable": os.fspath(docker_executable),
            "docker_executable_sha256": executable_sha256,
            "docker_client_version": docker_client_version,
            "docker_server_version": docker_server_version,
            "base_reference": base_reference,
            "base_digest": dockerfile_proof["base_digest"],
            "base_image_id": base_image_id,
            "input_authority_content_sha256": input_digest,
            "root_validation_algorithm_version": ROOT_VALIDATION_ALGORITHM_VERSION,
            "root_validation_algorithm_sha256": _sha256_file(Path(__file__)),
            "root_validation_spec_sha256": _root_validation_algorithm_sha256(),
            "root_proofs": {
                "task_root": task_proof,
                "context_root": context_proof,
                "dockerfile_parent": dockerfile_parent_proof,
            },
            "builds": builds,
            "base_acquisition_classification": (
                "BOUNDED_PUBLIC_ACQUISITION_OR_PRELOADED_EXACT_BASE_AUTHORITY"
            ),
            "dockerfile_run_network": "NONE",
            "docker_build_fully_offline_claimed": False,
        }
    )


def _verify_builder_invocation_payload(
    value: Mapping[str, Any],
    *,
    expected_input_authority_content_sha256: str,
) -> None:
    _verify_seal(value, expected_schema=INVOCATION_SCHEMA)
    if value.get("invocation_version") != LOCKED_INVOCATION_VERSION:
        _fail("builder invocation version mismatch")
    if value.get("dockerfile_version") != BUILDER_DOCKERFILE_VERSION:
        _fail("builder Dockerfile version mismatch")
    if value.get("root_validation_algorithm_sha256") != _sha256_file(Path(__file__)):
        _fail("root validation algorithm digest mismatch")
    if value.get("root_validation_spec_sha256") != _root_validation_algorithm_sha256():
        _fail("root validation specification digest mismatch")
    expected_input_digest = _validate_digest(
        expected_input_authority_content_sha256,
        label="expected input authority content digest",
    )
    if value.get("input_authority_content_sha256") != expected_input_digest:
        _fail("builder input authority digest mismatch")
    authorized_parent = _lexical_absolute(
        Path(str(value.get("authorized_parent", ""))),
        label="authorized parent",
    )
    task_root = _lexical_absolute(Path(str(value.get("task_root", ""))), label="task root")
    context_root = _lexical_absolute(
        Path(str(value.get("context_root", ""))),
        label="context root",
    )
    dockerfile = _lexical_absolute(
        Path(str(value.get("dockerfile_path", ""))),
        label="Dockerfile path",
    )
    docker_executable = _lexical_absolute(
        Path(str(value.get("docker_executable", ""))),
        label="Docker executable path",
    )
    proofs = value.get("root_proofs")
    if not isinstance(proofs, dict):
        _fail("builder invocation root proofs missing")
    for key, root in (
        ("task_root", task_root),
        ("context_root", context_root),
        ("dockerfile_parent", dockerfile.parent),
    ):
        proof = proofs.get(key)
        if not isinstance(proof, dict):
            _fail("builder invocation root proof missing")
        _verify_root_chain_unchanged(proof, authorized_parent, root)
    dockerfile_proof = _verify_builder_dockerfile(
        dockerfile,
        expected_base_reference=str(value.get("base_reference", "")),
    )
    if dockerfile_proof.get("file_sha256") != value.get("dockerfile_sha256"):
        _fail("builder Dockerfile digest mismatch")
    if _sha256_file(docker_executable) != value.get("docker_executable_sha256"):
        _fail("Docker executable digest mismatch")
    if dockerfile_proof.get("base_digest") != value.get("base_digest"):
        _fail("base digest binding mismatch")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", str(value.get("base_image_id", ""))) is None:
        _fail("base image identity binding missing")
    builds = value.get("builds")
    if not isinstance(builds, list) or len(builds) != 2:
        _fail("builder invocation must contain two clean builds")
    expected = (
        ("AUTHORITY", "mirror-cc08-r58-builder-authority:v2"),
        ("RECONSTRUCTION", "mirror-cc08-r58-builder-reconstruction:v2"),
    )
    for item, (role, tag) in zip(builds, expected, strict=True):
        if not isinstance(item, dict) or item.get("role") != role or item.get("output_tag") != tag:
            _fail("builder invocation role or output tag mismatch")
        argv = item.get("argv")
        if argv != _build_argv(
            docker_executable=docker_executable,
            dockerfile=dockerfile,
            context_root=context_root,
            output_tag=tag,
        ):
            _fail("builder invocation argv mismatch")
    if value.get("base_acquisition_classification") != (
        "BOUNDED_PUBLIC_ACQUISITION_OR_PRELOADED_EXACT_BASE_AUTHORITY"
    ):
        _fail("base acquisition classification mismatch")
    if value.get("dockerfile_run_network") != "NONE":
        _fail("Dockerfile RUN network classification mismatch")
    if value.get("docker_build_fully_offline_claimed") is not False:
        _fail("Docker build must not be misclassified as fully offline")


def _builder_identity_payload(
    *,
    invocation: Mapping[str, Any],
    image_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _verify_seal(invocation, expected_schema=INVOCATION_SCHEMA)
    if len(image_records) != 2:
        _fail("builder identity requires two image records")
    normalized: list[dict[str, Any]] = []
    expected_roles = ("AUTHORITY", "RECONSTRUCTION")
    for role, record in zip(expected_roles, image_records, strict=True):
        image_id = record.get("image_id")
        semantic_digest = record.get("semantic_content_sha256")
        if record.get("role") != role:
            _fail("builder image record role mismatch")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", str(image_id)) is None:
            _fail("builder image record ID invalid")
        normalized.append(
            {
                "role": role,
                "image_id": image_id,
                "semantic_content_sha256": _validate_digest(
                    semantic_digest,
                    label="builder semantic inventory digest",
                ),
            }
        )
    if normalized[0]["semantic_content_sha256"] != normalized[1]["semantic_content_sha256"]:
        _fail("builder semantic inventories differ")
    return _sealed(
        {
            "schema_version": BUILDER_IDENTITY_SCHEMA,
            "identity_version": "p2-m5-cc08-builder-identity-v2",
            "historical_predecessor_disposition": ("HISTORICAL_NOT_ACCEPTED_SECURITY_FINDING"),
            "dockerfile_sha256": invocation["dockerfile_sha256"],
            "invocation_content_sha256": invocation["content_sha256"],
            "base_digest": invocation["base_digest"],
            "base_image_id": invocation["base_image_id"],
            "root_validation_algorithm_sha256": invocation["root_validation_algorithm_sha256"],
            "root_validation_spec_sha256": invocation["root_validation_spec_sha256"],
            "input_authority_content_sha256": invocation["input_authority_content_sha256"],
            "images": normalized,
            "semantic_content_sha256": normalized[0]["semantic_content_sha256"],
        }
    )


def _verify_builder_identity(
    identity: Mapping[str, Any],
    *,
    invocation: Mapping[str, Any],
) -> None:
    _verify_seal(identity, expected_schema=BUILDER_IDENTITY_SCHEMA)
    _verify_seal(invocation, expected_schema=INVOCATION_SCHEMA)
    expected_bindings = {
        "dockerfile_sha256": invocation.get("dockerfile_sha256"),
        "invocation_content_sha256": invocation.get("content_sha256"),
        "base_digest": invocation.get("base_digest"),
        "base_image_id": invocation.get("base_image_id"),
        "root_validation_algorithm_sha256": invocation.get("root_validation_algorithm_sha256"),
        "root_validation_spec_sha256": invocation.get("root_validation_spec_sha256"),
        "input_authority_content_sha256": invocation.get("input_authority_content_sha256"),
    }
    if any(identity.get(key) != value for key, value in expected_bindings.items()):
        _fail("builder identity authority binding mismatch")


def _builder_input_authority_payload(lock: Mapping[str, Any]) -> dict[str, Any]:
    source = lock.get("source")
    patches = lock.get("patches")
    public_artifacts = lock.get("public_artifacts")
    builder_algorithm = lock.get("builder_algorithm")
    linux_builder = lock.get("linux_builder")
    windows_builder = lock.get("windows_builder")
    bindings = lock.get("private_manifest_bindings")
    if not all(
        isinstance(value, expected_type)
        for value, expected_type in (
            (source, dict),
            (patches, list),
            (public_artifacts, list),
            (builder_algorithm, dict),
            (linux_builder, dict),
            (windows_builder, dict),
            (bindings, list),
        )
    ):
        _fail("builder input authority fields are incomplete")
    assert isinstance(builder_algorithm, dict)
    assert isinstance(linux_builder, dict)
    assert isinstance(windows_builder, dict)
    assert isinstance(bindings, list)
    stable_binding_ids = {
        "source_tree",
        "public_artifacts",
        "linux_debs",
        "windows_toolchain",
        "repository_cache",
    }
    stable_bindings = [
        item for item in bindings if isinstance(item, dict) and item.get("id") in stable_binding_ids
    ]
    if {item.get("id") for item in stable_bindings} != stable_binding_ids:
        _fail("stable private input manifest bindings are incomplete")
    stable_bindings.sort(key=lambda item: str(item["id"]))
    return _sealed(
        {
            "schema_version": "mirror.p2-m5.cc08-builder-input-authority/v2",
            "algorithm": "canonical-stable-prebuild-inputs-v2",
            "source": source,
            "patches": patches,
            "public_artifacts": public_artifacts,
            "target": builder_algorithm.get("target"),
            "common_bazel_flags": builder_algorithm.get("common_bazel_flags"),
            "windows_action_environment": (
                builder_algorithm.get("windows", {}).get("action_environment")
                if isinstance(builder_algorithm.get("windows"), dict)
                else None
            ),
            "linux_base_image": linux_builder.get("base_image"),
            "linux_deb_bundle": linux_builder.get("deb_bundle"),
            "windows_toolchain": {
                key: value
                for key, value in windows_builder.items()
                if key not in {"runtime_builds", "offline_fetch"}
            },
            "private_manifest_bindings": stable_bindings,
        }
    )


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
            size = _require_regular_file(path, label="manifest input file").st_size
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
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    inputs = [
        (label, _lexical_absolute(root, label="manifest input root"))
        for label, root in _parse_inputs(args.input)
    ]
    input_proofs = [
        (root, _verify_exact_root_chain_no_reparse(authorized_parent, root))
        for _label, root in inputs
    ]
    output = _lexical_absolute(Path(args.output), label="manifest output path")
    output_proof = _verify_exact_root_chain_no_reparse(authorized_parent, output.parent)
    manifest = _manifest_payload(
        kind=args.kind,
        inputs=inputs,
        exclusions=args.exclude,
    )
    for root, proof in input_proofs:
        _verify_root_chain_unchanged(proof, authorized_parent, root)
    _verify_root_chain_unchanged(output_proof, authorized_parent, output.parent)
    _write_new_json(output, manifest)
    print(
        "MANIFEST_CREATED "
        f"kind={manifest['kind']} entries={manifest['entry_count']} "
        f"bytes={manifest['total_bytes']} content_sha256={manifest['content_sha256']}"
    )


def _verify_manifest_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    manifest_path = _lexical_absolute(Path(args.manifest), label="manifest path")
    manifest_root_proof = _manifest_root_before_read(authorized_parent, manifest_path)
    expected = _load_json(manifest_path)
    _verify_seal(expected, expected_schema=MANIFEST_SCHEMA)
    inputs = [
        (label, _lexical_absolute(root, label="manifest input root"))
        for label, root in _parse_inputs(args.input)
    ]
    input_proofs = [
        (root, _verify_exact_root_chain_no_reparse(authorized_parent, root))
        for _label, root in inputs
    ]
    if [label for label, _root in inputs] != expected.get("input_labels"):
        _fail("manifest input labels mismatch")
    actual = _manifest_payload(
        kind=str(expected.get("kind")),
        inputs=inputs,
        exclusions=list(expected.get("excluded_relative_prefixes", [])),
    )
    if actual != expected:
        _fail("manifest entries mismatch")
    _verify_root_chain_unchanged(manifest_root_proof, authorized_parent, manifest_path.parent)
    for root, proof in input_proofs:
        _verify_root_chain_unchanged(proof, authorized_parent, root)
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
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    lock_path = _lexical_absolute(Path(args.lock), label="input lock path")
    lock_root_proof = _manifest_root_before_read(authorized_parent, lock_path)
    lock = _load_json(lock_path)
    source = lock.get("source")
    patches = lock.get("patches")
    if not isinstance(source, dict) or not isinstance(patches, list):
        _fail("lock source or patches missing")
    commit = source.get("commit")
    if not isinstance(commit, str) or len(commit) != 40:
        _fail("source commit invalid")
    destination = _lexical_absolute(Path(args.destination), label="source destination")
    if os.path.lexists(destination):
        _fail("source destination already exists")
    base = _lexical_absolute(Path(args.base_repository), label="base repository")
    project_root = _lexical_absolute(Path(args.project_root), label="project root")
    base_root_proof = _verify_exact_root_chain_no_reparse(authorized_parent, base)
    project_root_proof = _verify_exact_root_chain_no_reparse(authorized_parent, project_root)
    destination_parent_proof = _verify_exact_root_chain_no_reparse(
        authorized_parent, destination.parent
    )
    _verify_root_chain_unchanged(lock_root_proof, authorized_parent, lock_path.parent)
    if _run_git(["rev-parse", "HEAD"], cwd=base) != commit:
        _fail("base source commit mismatch")
    _run_git(["clone", "--local", "--no-hardlinks", "--no-checkout", str(base), str(destination)])
    destination_root_proof = _verify_exact_root_chain_no_reparse(authorized_parent, destination)
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
            patch_path = project_root / _normalized_relative(relative_path)
            _verify_exact_root_chain_no_reparse(authorized_parent, patch_path.parent)
            if _sha256_file(patch_path) != expected_sha:
                _fail("patch digest mismatch")
            _run_git(["apply", "--check", str(patch_path)], cwd=destination)
            _run_git(["apply", str(patch_path)], cwd=destination)
    except BaseException:
        # The destination is task-owned but may contain forensic failure evidence.
        # Never delete it automatically.
        raise
    _verify_root_chain_unchanged(base_root_proof, authorized_parent, base)
    _verify_root_chain_unchanged(project_root_proof, authorized_parent, project_root)
    _verify_root_chain_unchanged(destination_parent_proof, authorized_parent, destination.parent)
    _verify_root_chain_unchanged(destination_root_proof, authorized_parent, destination)
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
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    root = _lexical_absolute(Path(args.root), label="Debian package root")
    root_proof = _verify_exact_root_chain_no_reparse(authorized_parent, root)
    output = _lexical_absolute(Path(args.output), label="Debian inventory output")
    output_proof = _verify_exact_root_chain_no_reparse(authorized_parent, output.parent)
    packages: list[dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(root.glob("*.deb"), key=lambda item: item.name):
        size = _require_regular_file(path, label="Debian package").st_size
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
    _verify_root_chain_unchanged(root_proof, authorized_parent, root)
    _verify_root_chain_unchanged(output_proof, authorized_parent, output.parent)
    _write_new_json(output, value)
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


def _linux_builder_inventory_payload(image_reference: str) -> dict[str, Any]:
    image_json = _run_text(["docker", "image", "inspect", image_reference])
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
            image_reference,
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
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                image_reference,
                *command,
            ]
        ).splitlines()[0]
    semantic_payload = {
        "architecture": image.get("Architecture"),
        "os": image.get("Os"),
        "tools": tools,
        "entries": packages,
    }
    return _sealed(
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


def _linux_builder_inventory_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    output = _lexical_absolute(Path(args.output), label="builder inventory output")
    output_proof = _verify_exact_root_chain_no_reparse(authorized_parent, output.parent)
    value = _linux_builder_inventory_payload(args.image)
    _verify_root_chain_unchanged(output_proof, authorized_parent, output.parent)
    _write_new_json(output, value)
    print(
        "LINUX_BUILDER_INVENTORY_CREATED "
        f"entries={value['entry_count']} image_id={value['image_id']} "
        f"content_sha256={value['content_sha256']}"
    )


def _run_exact_text(executable: Path, arguments: Sequence[str]) -> str:
    _require_regular_file(executable, label="external executable")
    try:
        result = subprocess.run(  # noqa: S603 - digest-bound executable and fixed argv.
            [os.fspath(executable), *arguments],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LockError("digest-bound external command failed") from exc
    return result.stdout.strip()


def _docker_live_identity(docker_executable: Path, base_reference: str) -> dict[str, str]:
    version = _run_exact_text(
        docker_executable,
        ["version", "--format", "{{.Client.Version}}|{{.Server.Version}}"],
    )
    fields = version.split("|")
    if len(fields) != 2 or not all(fields):
        _fail("Docker client/server version output is invalid")
    base_image_id = _run_exact_text(
        docker_executable,
        ["image", "inspect", "--format", "{{.Id}}", base_reference],
    )
    if re.fullmatch(r"sha256:[0-9a-f]{64}", base_image_id) is None:
        _fail("preloaded base image authority is unavailable")
    return {
        "client_version": fields[0],
        "server_version": fields[1],
        "base_image_id": base_image_id,
    }


def _require_docker_tag_absent(docker_executable: Path, tag: str) -> None:
    try:
        completed = subprocess.run(  # noqa: S603 - digest-bound executable and fixed argv.
            [os.fspath(docker_executable), "image", "inspect", tag],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise LockError("Docker image create-new check failed") from exc
    if completed.returncode == 0:
        _fail("builder output tag already exists")
    if completed.returncode != 1:
        _fail("Docker image create-new check was indeterminate")


def _manifest_root_before_read(authorized_parent: Path, path: Path) -> dict[str, Any]:
    return _verify_exact_root_chain_no_reparse(authorized_parent, path.parent)


def _create_builder_invocation_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    task_root = _lexical_absolute(Path(args.task_root), label="task root")
    dockerfile = _lexical_absolute(Path(args.dockerfile), label="Dockerfile path")
    context_root = _lexical_absolute(Path(args.context_root), label="context root")
    output = _lexical_absolute(Path(args.output), label="invocation output path")
    output_root_proof = _verify_exact_root_chain_no_reparse(authorized_parent, output.parent)
    executable_value = shutil.which("docker")
    if executable_value is None:
        _fail("docker executable unavailable")
    docker_executable = _lexical_absolute(Path(executable_value), label="Docker executable path")
    live = _docker_live_identity(docker_executable, args.base_reference)
    value = _builder_invocation_payload(
        authorized_parent=authorized_parent,
        task_root=task_root,
        docker_executable=docker_executable,
        docker_client_version=live["client_version"],
        docker_server_version=live["server_version"],
        dockerfile=dockerfile,
        context_root=context_root,
        base_reference=args.base_reference,
        base_image_id=live["base_image_id"],
        input_authority_content_sha256=args.input_authority_content_sha256,
    )
    _verify_builder_invocation_payload(
        value,
        expected_input_authority_content_sha256=args.input_authority_content_sha256,
    )
    _verify_root_chain_unchanged(output_root_proof, authorized_parent, output.parent)
    _write_new_json(output, value)
    print(f"BUILDER_INVOCATION_CREATED content_sha256={value['content_sha256']}")


def _load_and_verify_live_invocation(
    *,
    authorized_parent: Path,
    invocation_path: Path,
    expected_input_authority_content_sha256: str,
) -> dict[str, Any]:
    manifest_root_proof = _manifest_root_before_read(authorized_parent, invocation_path)
    value = _load_json(invocation_path)
    _verify_builder_invocation_payload(
        value,
        expected_input_authority_content_sha256=expected_input_authority_content_sha256,
    )
    docker_executable = Path(str(value["docker_executable"]))
    live = _docker_live_identity(docker_executable, str(value["base_reference"]))
    if (
        live["client_version"] != value.get("docker_client_version")
        or live["server_version"] != value.get("docker_server_version")
        or live["base_image_id"] != value.get("base_image_id")
    ):
        _fail("live Docker or base-image identity drifted")
    _verify_root_chain_unchanged(manifest_root_proof, authorized_parent, invocation_path.parent)
    return value


def _verify_builder_invocation_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    value = _load_and_verify_live_invocation(
        authorized_parent=authorized_parent,
        invocation_path=_lexical_absolute(Path(args.invocation), label="invocation manifest path"),
        expected_input_authority_content_sha256=args.input_authority_content_sha256,
    )
    print(f"BUILDER_INVOCATION_VERIFIED content_sha256={value['content_sha256']}")


def _verify_output_parent(
    *,
    authorized_parent: Path,
    task_root: Path,
    output: Path,
) -> dict[str, Any]:
    chain = _contained_chain(task_root, output.parent)
    if not chain:
        _fail("output parent containment unavailable")
    return _verify_exact_root_chain_no_reparse(authorized_parent, output.parent)


def _execute_builder_invocation_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    invocation_path = _lexical_absolute(Path(args.invocation), label="invocation manifest path")
    value = _load_and_verify_live_invocation(
        authorized_parent=authorized_parent,
        invocation_path=invocation_path,
        expected_input_authority_content_sha256=args.input_authority_content_sha256,
    )
    task_root = _lexical_absolute(Path(str(value["task_root"])), label="task root")
    log_root = _lexical_absolute(Path(args.log_root), label="build log root")
    _verify_exact_root_chain_no_reparse(authorized_parent, log_root)
    output_paths = {
        "AUTHORITY": _lexical_absolute(
            Path(args.authority_inventory), label="authority inventory output"
        ),
        "RECONSTRUCTION": _lexical_absolute(
            Path(args.reconstruction_inventory), label="reconstruction inventory output"
        ),
    }
    result_path = _lexical_absolute(Path(args.result), label="execution result output")
    output_proofs = {
        role: _verify_output_parent(
            authorized_parent=authorized_parent,
            task_root=task_root,
            output=path,
        )
        for role, path in output_paths.items()
    }
    result_proof = _verify_output_parent(
        authorized_parent=authorized_parent,
        task_root=task_root,
        output=result_path,
    )
    builds = value["builds"]
    inventory_values: list[dict[str, Any]] = []
    for item in builds:
        role = str(item["role"])
        tag = str(item["output_tag"])
        docker_executable = Path(str(value["docker_executable"]))
        _require_docker_tag_absent(docker_executable, tag)
        _load_and_verify_live_invocation(
            authorized_parent=authorized_parent,
            invocation_path=invocation_path,
            expected_input_authority_content_sha256=args.input_authority_content_sha256,
        )
        argv = [str(part) for part in item["argv"]]
        try:
            completed = subprocess.run(  # noqa: S603 - exact verified argv, never shell.
                argv,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            raise LockError("locked Docker build invocation could not start") from exc
        log_path = log_root / f"{role.lower()}-docker-build.log"
        _verify_exact_root_chain_no_reparse(authorized_parent, log_root)
        _write_new_bytes(log_path, completed.stdout)
        if completed.returncode != 0:
            _fail("locked Docker build invocation failed")
        inventory = _linux_builder_inventory_payload(tag)
        inventory_values.append(inventory)
        _verify_root_chain_unchanged(
            output_proofs[role], authorized_parent, output_paths[role].parent
        )
        _write_new_json(output_paths[role], inventory)
    result = _sealed(
        {
            "schema_version": "mirror.p2-m5.cc08-builder-execution-result/v2",
            "task_id": "P2-M5-R58",
            "invocation_content_sha256": value["content_sha256"],
            "build_count": 2,
            "runtime_builds": 0,
            "model_loads": 0,
            "vision_calls": 0,
            "canary_reads": 0,
            "decode_calls": 0,
            "m3_calls": 0,
            "imagegen_calls": 0,
            "images": [
                {
                    "role": role,
                    "image_id": inventory["image_id"],
                    "inventory_content_sha256": inventory["content_sha256"],
                    "semantic_content_sha256": inventory["semantic_content_sha256"],
                    "entry_count": inventory["entry_count"],
                }
                for role, inventory in zip(
                    ("AUTHORITY", "RECONSTRUCTION"),
                    inventory_values,
                    strict=True,
                )
            ],
            "result": "PASS_TWO_CLEAN_LOCKED_INVOCATIONS",
        }
    )
    _verify_root_chain_unchanged(result_proof, authorized_parent, result_path.parent)
    _write_new_json(result_path, result)
    print(f"BUILDER_INVOCATION_EXECUTED content_sha256={result['content_sha256']}")


def _create_builder_identity_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    invocation_path = _lexical_absolute(Path(args.invocation), label="invocation manifest path")
    invocation = _load_json_after_root_check(authorized_parent, invocation_path)
    records: list[dict[str, Any]] = []
    for role, raw_path in (
        ("AUTHORITY", args.authority_inventory),
        ("RECONSTRUCTION", args.reconstruction_inventory),
    ):
        path = _lexical_absolute(Path(raw_path), label="builder inventory path")
        inventory = _load_json_after_root_check(authorized_parent, path)
        _verify_seal(inventory, expected_schema=MANIFEST_SCHEMA)
        if inventory.get("kind") != "linux-builder-image-inventory":
            _fail("builder inventory kind mismatch")
        records.append(
            {
                "role": role,
                "image_id": inventory.get("image_id"),
                "semantic_content_sha256": inventory.get("semantic_content_sha256"),
            }
        )
    identity = _builder_identity_payload(invocation=invocation, image_records=records)
    output = _lexical_absolute(Path(args.output), label="builder identity output")
    proof = _verify_exact_root_chain_no_reparse(authorized_parent, output.parent)
    _verify_root_chain_unchanged(proof, authorized_parent, output.parent)
    _write_new_json(output, identity)
    print(f"BUILDER_IDENTITY_CREATED content_sha256={identity['content_sha256']}")


def _load_json_after_root_check(authorized_parent: Path, path: Path) -> dict[str, Any]:
    proof = _manifest_root_before_read(authorized_parent, path)
    value = _load_json(path)
    _verify_root_chain_unchanged(proof, authorized_parent, path.parent)
    return value


def _verify_builder_identity_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    invocation = _load_json_after_root_check(
        authorized_parent,
        _lexical_absolute(Path(args.invocation), label="invocation manifest path"),
    )
    identity = _load_json_after_root_check(
        authorized_parent,
        _lexical_absolute(Path(args.identity), label="builder identity path"),
    )
    _verify_builder_identity(identity, invocation=invocation)
    print(f"BUILDER_IDENTITY_VERIFIED content_sha256={identity['content_sha256']}")


def _verify_exact_root_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    root = _lexical_absolute(Path(args.root), label="exact root")
    value = _verify_exact_root_chain_no_reparse(authorized_parent, root)
    if args.output is not None:
        output = _lexical_absolute(Path(args.output), label="root proof output")
        output_proof = _verify_exact_root_chain_no_reparse(authorized_parent, output.parent)
        _verify_root_chain_unchanged(value, authorized_parent, root)
        _verify_root_chain_unchanged(output_proof, authorized_parent, output.parent)
        _write_new_json(output, value)
    print(
        "EXACT_ROOT_CHAIN_VERIFIED "
        f"depth={value['chain_depth']} algorithm_sha256={value['algorithm_sha256']}"
    )


def _verify_exact_root_proof_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    root = _lexical_absolute(Path(args.root), label="exact root")
    proof_path = _lexical_absolute(Path(args.proof), label="root proof path")
    proof = _load_json_after_root_check(authorized_parent, proof_path)
    _verify_root_chain_unchanged(proof, authorized_parent, root)
    print(
        "EXACT_ROOT_PROOF_VERIFIED "
        f"depth={proof['chain_depth']} algorithm_sha256={proof['algorithm_sha256']}"
    )


def _verify_public_artifacts(lock: Mapping[str, Any], root: Path) -> None:
    _require_directory(root, label="public artifact root")
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
        metadata = _require_regular_file(path, label="public artifact")
        if metadata.st_size != expected_size or _sha256_file(path) != expected_sha:
            _fail("public artifact mismatch")


def _verify_lock_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    lock_path = _lexical_absolute(Path(args.lock), label="builder input lock path")
    lock_root_proof = _manifest_root_before_read(authorized_parent, lock_path)
    lock = _load_json(lock_path)
    _verify_seal(lock, expected_schema=LOCK_SCHEMA)
    patches = lock.get("patches")
    if not isinstance(patches, list):
        _fail("patch lock missing")
    for expected_order, item in enumerate(patches, start=1):
        if not isinstance(item, dict) or item.get("order") != expected_order:
            _fail("patch order mismatch")
        project_root = _lexical_absolute(Path(args.project_root), label="project root")
        patch_path = project_root / _normalized_relative(str(item.get("path", "")))
        _verify_exact_root_chain_no_reparse(authorized_parent, patch_path.parent)
        if _sha256_file(patch_path) != item.get("sha256"):
            _fail("tracked patch mismatch")
    project_root = _lexical_absolute(Path(args.project_root), label="project root")
    public_root = _lexical_absolute(Path(args.public_root), label="public artifact root")
    project_root_proof = _verify_exact_root_chain_no_reparse(authorized_parent, project_root)
    public_root_proof = _verify_exact_root_chain_no_reparse(authorized_parent, public_root)
    _verify_public_artifacts(lock, public_root)
    private_manifests = lock.get("private_manifest_bindings")
    supplied = {
        label: _lexical_absolute(path, label="private manifest path")
        for label, path in _parse_inputs(args.private_manifest)
    }
    if not isinstance(private_manifests, list):
        _fail("private manifest bindings missing")
    if {item.get("id") for item in private_manifests if isinstance(item, dict)} != set(supplied):
        _fail("private manifest set mismatch")
    for item in private_manifests:
        if not isinstance(item, dict):
            _fail("private manifest binding invalid")
        manifest_id = item.get("id")
        manifest_path = supplied.get(str(manifest_id))
        if manifest_path is None:
            _fail("private manifest unavailable")
        value = _load_json_after_root_check(authorized_parent, manifest_path)
        _verify_seal(value, expected_schema=MANIFEST_SCHEMA)
        if (
            _sha256_file(manifest_path) != item.get("file_sha256")
            or value.get("content_sha256") != item.get("content_sha256")
            or value.get("entry_count") != item.get("entry_count")
            or value.get("total_bytes") != item.get("total_bytes")
        ):
            _fail("private manifest binding mismatch")
    _verify_root_chain_unchanged(lock_root_proof, authorized_parent, lock_path.parent)
    _verify_root_chain_unchanged(project_root_proof, authorized_parent, project_root)
    _verify_root_chain_unchanged(public_root_proof, authorized_parent, public_root)
    print(
        "BUILDER_INPUT_LOCK_VERIFIED "
        f"version={lock.get('lock_version')} content_sha256={lock['content_sha256']}"
    )


def _seal_json_command(args: argparse.Namespace) -> None:
    authorized_parent = _lexical_absolute(Path(args.authorized_parent), label="authorized parent")
    input_path = _lexical_absolute(Path(args.input), label="JSON seal input")
    output_path = _lexical_absolute(Path(args.output), label="JSON seal output")
    input_root_proof = _manifest_root_before_read(authorized_parent, input_path)
    output_root_proof = _verify_exact_root_chain_no_reparse(authorized_parent, output_path.parent)
    value = _load_json(input_path)
    if value.get("content_sha256") not in {None, ""}:
        _fail("input JSON is already sealed")
    value.pop("content_sha256", None)
    sealed = _sealed(value)
    _verify_root_chain_unchanged(input_root_proof, authorized_parent, input_path.parent)
    _verify_root_chain_unchanged(output_root_proof, authorized_parent, output_path.parent)
    _write_new_json(output_path, sealed)
    print(f"JSON_SEALED content_sha256={sealed['content_sha256']}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_authorized_parent(command: argparse.ArgumentParser) -> None:
        command.add_argument("--authorized-parent", required=True)

    manifest = subparsers.add_parser("manifest")
    add_authorized_parent(manifest)
    manifest.add_argument("--kind", required=True)
    manifest.add_argument("--input", action="append", required=True)
    manifest.add_argument("--exclude", action="append", default=[])
    manifest.add_argument("--output", required=True)
    manifest.set_defaults(handler=_manifest_command)

    verify_manifest = subparsers.add_parser("verify-manifest")
    add_authorized_parent(verify_manifest)
    verify_manifest.add_argument("--manifest", required=True)
    verify_manifest.add_argument("--input", action="append", required=True)
    verify_manifest.set_defaults(handler=_verify_manifest_command)

    materialize = subparsers.add_parser("materialize-source")
    add_authorized_parent(materialize)
    materialize.add_argument("--lock", required=True)
    materialize.add_argument("--project-root", required=True)
    materialize.add_argument("--base-repository", required=True)
    materialize.add_argument("--destination", required=True)
    materialize.set_defaults(handler=_materialize_source_command)

    deb_inventory = subparsers.add_parser("deb-inventory")
    add_authorized_parent(deb_inventory)
    deb_inventory.add_argument("--root", required=True)
    deb_inventory.add_argument("--output", required=True)
    deb_inventory.set_defaults(handler=_deb_inventory_command)

    linux_builder_inventory = subparsers.add_parser("linux-builder-inventory")
    add_authorized_parent(linux_builder_inventory)
    linux_builder_inventory.add_argument("--image", required=True)
    linux_builder_inventory.add_argument("--output", required=True)
    linux_builder_inventory.set_defaults(handler=_linux_builder_inventory_command)

    seal_json = subparsers.add_parser("seal-json")
    add_authorized_parent(seal_json)
    seal_json.add_argument("--input", required=True)
    seal_json.add_argument("--output", required=True)
    seal_json.set_defaults(handler=_seal_json_command)

    verify_lock = subparsers.add_parser("verify-lock")
    add_authorized_parent(verify_lock)
    verify_lock.add_argument("--lock", required=True)
    verify_lock.add_argument("--project-root", required=True)
    verify_lock.add_argument("--public-root", required=True)
    verify_lock.add_argument("--private-manifest", action="append", required=True)
    verify_lock.set_defaults(handler=_verify_lock_command)

    verify_root = subparsers.add_parser("verify-exact-root-chain")
    add_authorized_parent(verify_root)
    verify_root.add_argument("--root", required=True)
    verify_root.add_argument("--output")
    verify_root.set_defaults(handler=_verify_exact_root_command)

    verify_root_proof = subparsers.add_parser("verify-exact-root-proof")
    add_authorized_parent(verify_root_proof)
    verify_root_proof.add_argument("--root", required=True)
    verify_root_proof.add_argument("--proof", required=True)
    verify_root_proof.set_defaults(handler=_verify_exact_root_proof_command)

    create_invocation = subparsers.add_parser("create-builder-invocation")
    add_authorized_parent(create_invocation)
    create_invocation.add_argument("--task-root", required=True)
    create_invocation.add_argument("--dockerfile", required=True)
    create_invocation.add_argument("--context-root", required=True)
    create_invocation.add_argument("--base-reference", required=True)
    create_invocation.add_argument("--input-authority-content-sha256", required=True)
    create_invocation.add_argument("--output", required=True)
    create_invocation.set_defaults(handler=_create_builder_invocation_command)

    verify_invocation = subparsers.add_parser("verify-builder-invocation")
    add_authorized_parent(verify_invocation)
    verify_invocation.add_argument("--invocation", required=True)
    verify_invocation.add_argument("--input-authority-content-sha256", required=True)
    verify_invocation.set_defaults(handler=_verify_builder_invocation_command)

    execute_invocation = subparsers.add_parser("execute-builder-invocation")
    add_authorized_parent(execute_invocation)
    execute_invocation.add_argument("--invocation", required=True)
    execute_invocation.add_argument("--input-authority-content-sha256", required=True)
    execute_invocation.add_argument("--log-root", required=True)
    execute_invocation.add_argument("--authority-inventory", required=True)
    execute_invocation.add_argument("--reconstruction-inventory", required=True)
    execute_invocation.add_argument("--result", required=True)
    execute_invocation.set_defaults(handler=_execute_builder_invocation_command)

    create_identity = subparsers.add_parser("create-builder-identity")
    add_authorized_parent(create_identity)
    create_identity.add_argument("--invocation", required=True)
    create_identity.add_argument("--authority-inventory", required=True)
    create_identity.add_argument("--reconstruction-inventory", required=True)
    create_identity.add_argument("--output", required=True)
    create_identity.set_defaults(handler=_create_builder_identity_command)

    verify_identity = subparsers.add_parser("verify-builder-identity")
    add_authorized_parent(verify_identity)
    verify_identity.add_argument("--invocation", required=True)
    verify_identity.add_argument("--identity", required=True)
    verify_identity.set_defaults(handler=_verify_builder_identity_command)
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
