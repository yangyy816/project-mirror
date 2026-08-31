from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "research" / "p2_m5_cc08_builder_lock.py"
DOCKERFILE_PATH = ROOT / "scripts" / "research" / "p2_m5_cc08_linux_builder.Dockerfile"
LOCK_PATH = ROOT / "docs" / "research" / "P2_M5_CC08_BUILDER_INPUT_LOCK_V1.json"
BASE_REFERENCE = "python@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a"
INPUT_AUTHORITY_DIGEST = "1" * 64


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("p2_m5_cc08_builder_lock", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    executable = shutil.which("git")
    assert executable is not None
    return subprocess.run(  # noqa: S603 - test-owned repository and arguments.
        [executable, *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _write_dockerfile(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _private_invocation_fixture(module: ModuleType, tmp_path: Path) -> dict[str, Any]:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_bytes(DOCKERFILE_PATH.read_bytes())
    context = tmp_path / "context"
    context.mkdir()
    docker_executable = tmp_path / ("docker.exe" if os.name == "nt" else "docker")
    docker_executable.write_bytes(b"test-docker-executable")
    return module._builder_invocation_payload(
        authorized_parent=tmp_path,
        task_root=tmp_path,
        docker_executable=docker_executable,
        docker_client_version="29.7.2",
        docker_server_version="29.7.2",
        dockerfile=dockerfile,
        context_root=context,
        base_reference=BASE_REFERENCE,
        base_image_id=f"sha256:{'2' * 64}",
        input_authority_content_sha256=INPUT_AUTHORITY_DIGEST,
    )


def test_private_manifest_is_deterministic_sealed_and_detects_mutation(tmp_path: Path) -> None:
    module = _module()
    root = tmp_path / "input"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "alpha.txt").write_bytes(b"alpha\n")
    (nested / "beta.bin").write_bytes(b"\x00\x01\x02")

    first = module._manifest_payload(kind="fixture", inputs=[("source", root)], exclusions=[])
    second = module._manifest_payload(kind="fixture", inputs=[("source", root)], exclusions=[])

    assert first == second
    assert first["entry_count"] == 2
    assert first["total_bytes"] == 9
    assert [entry["relative_path"] for entry in first["entries"]] == [
        "source/alpha.txt",
        "source/nested/beta.bin",
    ]
    module._verify_seal(first, expected_schema=module.MANIFEST_SCHEMA)

    mutated = dict(first)
    mutated["total_bytes"] = 10
    with pytest.raises(module.LockError, match="content digest mismatch"):
        module._verify_seal(mutated, expected_schema=module.MANIFEST_SCHEMA)


def test_tracked_lock_recomputes_stable_prebuild_input_authority() -> None:
    module = _module()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    module._verify_seal(lock, expected_schema=module.LOCK_SCHEMA)
    authority = module._builder_input_authority_payload(lock)
    assert authority["content_sha256"] == lock["input_authority"]["content_sha256"]


def test_private_manifest_rejects_reparse_root_without_reading_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    root = tmp_path / "input"
    root.mkdir()
    (root / "blocked.bin").write_bytes(b"do-not-read")
    monkeypatch.setattr(module, "_is_reparse", lambda _metadata: True)

    with pytest.raises(module.LockError, match="link or reparse point rejected"):
        module._manifest_payload(kind="fixture", inputs=[("source", root)], exclusions=[])


def test_private_manifest_rejects_reparse_child_without_reading_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    root = tmp_path / "input"
    root.mkdir()
    (root / "blocked.bin").write_bytes(b"do-not-read")
    monkeypatch.setattr(
        module,
        "_is_reparse",
        lambda metadata: stat.S_ISREG(metadata.st_mode),
    )

    with pytest.raises(module.LockError, match="link or reparse point rejected"):
        module._manifest_payload(kind="fixture", inputs=[("source", root)], exclusions=[])


def test_linux_builder_dockerfile_forces_network_none_for_every_run() -> None:
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
    assert "# syntax=" not in dockerfile
    run_lines = [line for line in dockerfile.splitlines() if line.startswith("RUN ")]
    assert len(run_lines) == 2
    assert all(line.startswith("RUN --network=none ") for line in run_lines)

    module = _module()
    proof = module._verify_builder_dockerfile(
        DOCKERFILE_PATH,
        expected_base_reference=BASE_REFERENCE,
    )
    assert proof["run_count"] == 2
    assert proof["run_network"] == "NONE_PER_RUN"
    assert proof["remote_add"] is False
    assert proof["network_acquisition_commands"] is False


@pytest.mark.parametrize("run_index", [0, 1])
def test_dockerfile_rejects_each_run_without_network_none(tmp_path: Path, run_index: int) -> None:
    module = _module()
    lines = DOCKERFILE_PATH.read_text(encoding="utf-8").splitlines()
    run_lines = [index for index, line in enumerate(lines) if line.startswith("RUN ")]
    lines[run_lines[run_index]] = lines[run_lines[run_index]].replace(
        "RUN --network=none ", "RUN ", 1
    )
    dockerfile = tmp_path / "Dockerfile"
    _write_dockerfile(dockerfile, "\n".join(lines) + "\n")

    with pytest.raises(module.LockError, match="RUN is missing network none"):
        module._verify_builder_dockerfile(
            dockerfile,
            expected_base_reference=BASE_REFERENCE,
        )


def test_dockerfile_rejects_remote_add_network_fetch_and_noncanonical_bytes(
    tmp_path: Path,
) -> None:
    module = _module()
    original = DOCKERFILE_PATH.read_text(encoding="utf-8")
    remote_add = tmp_path / "remote-add.Dockerfile"
    _write_dockerfile(remote_add, original + "ADD https://example.invalid/archive /tmp/archive\n")
    with pytest.raises(module.LockError, match="remote ADD"):
        module._verify_builder_dockerfile(remote_add, expected_base_reference=BASE_REFERENCE)

    network_fetch = tmp_path / "network-fetch.Dockerfile"
    _write_dockerfile(network_fetch, original + "RUN --network=none curl example.invalid\n")
    with pytest.raises(module.LockError, match="network acquisition command"):
        module._verify_builder_dockerfile(network_fetch, expected_base_reference=BASE_REFERENCE)

    crlf = tmp_path / "crlf.Dockerfile"
    crlf.write_bytes(original.replace("\n", "\r\n").encode("utf-8"))
    with pytest.raises(module.LockError, match="canonical UTF-8 LF"):
        module._verify_builder_dockerfile(crlf, expected_base_reference=BASE_REFERENCE)


def test_locked_invocation_binds_required_flags_dockerfile_base_and_identity(
    tmp_path: Path,
) -> None:
    module = _module()
    invocation = _private_invocation_fixture(module, tmp_path)
    module._verify_builder_invocation_payload(
        invocation,
        expected_input_authority_content_sha256=INPUT_AUTHORITY_DIGEST,
    )
    for build in invocation["builds"]:
        assert build["argv"][1] == "build"
        assert "--network=none" in build["argv"]
        assert "--pull=false" in build["argv"]
        assert "--no-cache" in build["argv"]
        assert "--provenance=false" in build["argv"]

    records = [
        {
            "role": role,
            "image_id": f"sha256:{digit * 64}",
            "semantic_content_sha256": "5" * 64,
        }
        for role, digit in (("AUTHORITY", "3"), ("RECONSTRUCTION", "4"))
    ]
    identity = module._builder_identity_payload(
        invocation=invocation,
        image_records=records,
    )
    module._verify_builder_identity(identity, invocation=invocation)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("--network=none", "--network=default"),
        ("--pull=false", "--pull=true"),
        ("--no-cache", "--cache-from=unsafe"),
        ("--provenance=false", "--provenance=true"),
    ],
)
def test_locked_invocation_rejects_required_flag_drift(tmp_path: Path, old: str, new: str) -> None:
    module = _module()
    invocation = _private_invocation_fixture(module, tmp_path)
    mutated = copy.deepcopy(invocation)
    mutated.pop("content_sha256")
    mutated["builds"][0]["argv"][mutated["builds"][0]["argv"].index(old)] = new
    mutated = module._sealed(mutated)

    with pytest.raises(module.LockError, match="argv mismatch"):
        module._verify_builder_invocation_payload(
            mutated,
            expected_input_authority_content_sha256=INPUT_AUTHORITY_DIGEST,
        )


def test_dockerfile_invocation_and_base_digest_drift_fail_closed(tmp_path: Path) -> None:
    module = _module()
    invocation = _private_invocation_fixture(module, tmp_path)
    dockerfile = Path(invocation["dockerfile_path"])
    dockerfile.write_bytes(dockerfile.read_bytes() + b"# mutation\n")
    with pytest.raises(module.LockError, match="Dockerfile digest mismatch"):
        module._verify_builder_invocation_payload(
            invocation,
            expected_input_authority_content_sha256=INPUT_AUTHORITY_DIGEST,
        )

    dockerfile.write_bytes(DOCKERFILE_PATH.read_bytes())
    base_mutation = copy.deepcopy(invocation)
    base_mutation.pop("content_sha256")
    base_mutation["base_reference"] = f"python@sha256:{'9' * 64}"
    base_mutation["base_digest"] = "9" * 64
    base_mutation = module._sealed(base_mutation)
    with pytest.raises(module.LockError, match="base authority mismatch"):
        module._verify_builder_invocation_payload(
            base_mutation,
            expected_input_authority_content_sha256=INPUT_AUTHORITY_DIGEST,
        )


def test_invocation_mutation_cannot_inherit_builder_identity(tmp_path: Path) -> None:
    module = _module()
    invocation = _private_invocation_fixture(module, tmp_path)
    identity = module._builder_identity_payload(
        invocation=invocation,
        image_records=[
            {
                "role": "AUTHORITY",
                "image_id": f"sha256:{'3' * 64}",
                "semantic_content_sha256": "5" * 64,
            },
            {
                "role": "RECONSTRUCTION",
                "image_id": f"sha256:{'4' * 64}",
                "semantic_content_sha256": "5" * 64,
            },
        ],
    )
    mutated = copy.deepcopy(invocation)
    mutated.pop("content_sha256")
    mutated["docker_client_version"] = "29.7.3"
    mutated = module._sealed(mutated)

    with pytest.raises(module.LockError, match="authority binding mismatch"):
        module._verify_builder_identity(identity, invocation=mutated)


def test_exact_root_chain_normal_directory_and_fresh_process_verify(tmp_path: Path) -> None:
    module = _module()
    root = tmp_path / "task" / "nested"
    root.mkdir(parents=True)
    proof = module._verify_exact_root_chain_no_reparse(tmp_path, root)
    module._verify_root_chain_unchanged(proof, tmp_path, root)

    completed = subprocess.run(  # noqa: S603 - task-owned verifier and roots.
        [
            sys.executable,
            str(SCRIPT_PATH),
            "verify-exact-root-chain",
            "--authorized-parent",
            str(tmp_path),
            "--root",
            str(root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "EXACT_ROOT_CHAIN_VERIFIED" in completed.stdout


@pytest.mark.parametrize("reparse_call", [1, 2, 3])
def test_exact_root_chain_rejects_parent_intermediate_and_root_reparse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reparse_call: int,
) -> None:
    module = _module()
    root = tmp_path / "middle" / "root"
    root.mkdir(parents=True)
    calls = 0

    def simulated_reparse(_metadata: os.stat_result) -> bool:
        nonlocal calls
        calls += 1
        return calls == reparse_call

    monkeypatch.setattr(module, "_is_reparse", simulated_reparse)
    with pytest.raises(module.LockError, match="reparse point rejected"):
        module._verify_exact_root_chain_no_reparse(tmp_path, root)


def test_exact_root_chain_rejects_root_symlink_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    root = tmp_path / "root"
    root.mkdir()
    original_lstat = Path.lstat

    def symlink_root_lstat(path: Path) -> os.stat_result:
        if path == root:
            return os.stat_result((stat.S_IFLNK | 0o777,) + (0,) * 9)
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", symlink_root_lstat)
    with pytest.raises(module.LockError, match="link or reparse point rejected"):
        module._verify_exact_root_chain_no_reparse(tmp_path, root)


def test_exact_root_chain_detects_post_create_and_pre_seal_replacement(tmp_path: Path) -> None:
    module = _module()
    root = tmp_path / "root"
    proof = module._create_new_exact_root(tmp_path, root)
    (root / module._ROOT_MARKER_NAME).unlink()
    root.rmdir()
    root.mkdir()

    with pytest.raises(module.LockError, match="changed after initial verification"):
        module._verify_root_chain_unchanged(proof, tmp_path, root)


def test_fresh_process_root_proof_rejects_replaced_root(tmp_path: Path) -> None:
    module = _module()
    root = tmp_path / "root"
    proof = module._create_new_exact_root(tmp_path, root)
    proof_path = tmp_path / "root-proof.json"
    module._write_new_json(proof_path, proof)
    (root / module._ROOT_MARKER_NAME).unlink()
    root.rmdir()
    root.mkdir()

    completed = subprocess.run(  # noqa: S603 - task-owned verifier and roots.
        [
            sys.executable,
            str(SCRIPT_PATH),
            "verify-exact-root-proof",
            "--authorized-parent",
            str(tmp_path),
            "--root",
            str(root),
            "--proof",
            str(proof_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "changed after initial verification" in completed.stderr
    assert str(tmp_path) not in completed.stderr


def test_exact_root_chain_rejects_path_escape(tmp_path: Path) -> None:
    module = _module()
    authorized = tmp_path / "authorized"
    authorized.mkdir()
    escaped = authorized / ".." / "outside"

    with pytest.raises(module.LockError, match="without traversal"):
        module._verify_exact_root_chain_no_reparse(authorized, escaped)


def test_private_root_failures_do_not_echo_path_or_entry_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    root = tmp_path / "private-root"
    root.mkdir()
    private_name = "never-echo-this-entry.bin"
    (root / private_name).write_bytes(b"do-not-read")
    monkeypatch.setattr(
        module,
        "_is_reparse",
        lambda metadata: stat.S_ISREG(metadata.st_mode),
    )

    with pytest.raises(module.LockError) as captured:
        module._manifest_payload(kind="fixture", inputs=[("source", root)], exclusions=[])
    message = str(captured.value)
    assert private_name not in message
    assert str(tmp_path) not in message


def test_create_new_json_is_create_once(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence.json"
    module._write_new_json(output, {"value": "first"})
    with pytest.raises(module.LockError, match="already exists"):
        module._write_new_json(output, {"value": "second"})


def test_materialize_source_uses_exact_commit_ordered_patch_and_local_git_config(
    tmp_path: Path,
) -> None:
    module = _module()
    base = tmp_path / "base"
    base.mkdir()
    _git("init", cwd=base)
    _git("config", "user.email", "cc08@example.invalid", cwd=base)
    _git("config", "user.name", "CC08 Test", cwd=base)
    source_file = base / "source.txt"
    source_file.write_text("before\n", encoding="utf-8")
    _git("add", "source.txt", cwd=base)
    _git("commit", "-m", "base", cwd=base)
    commit = _git("rev-parse", "HEAD", cwd=base).stdout.decode().strip()

    source_file.write_text("after\n", encoding="utf-8")
    patch_bytes = _git("diff", "--binary", cwd=base).stdout
    _git("checkout", "--", "source.txt", cwd=base)
    patch_path = tmp_path / "change.patch"
    patch_path.write_bytes(patch_bytes)
    patch_sha256 = module._sha256_file(patch_path)
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(
        json.dumps(
            {
                "source": {"commit": commit},
                "patches": [
                    {
                        "order": 1,
                        "path": "change.patch",
                        "sha256": patch_sha256,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "materialized"

    module._materialize_source_command(
        SimpleNamespace(
            authorized_parent=str(tmp_path),
            lock=str(lock_path),
            project_root=str(tmp_path),
            base_repository=str(base),
            destination=str(destination),
        )
    )

    assert (destination / "source.txt").read_text(encoding="utf-8") == "after\n"
    assert _git("rev-parse", "HEAD", cwd=destination).stdout.decode().strip() == commit
    assert _git("config", "--local", "core.autocrlf", cwd=destination).stdout.strip() == b"false"
    assert _git("config", "--local", "core.eol", cwd=destination).stdout.strip() == b"lf"
    assert _git("config", "--local", "core.longpaths", cwd=destination).stdout.strip() == b"true"
