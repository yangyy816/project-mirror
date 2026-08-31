from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "research" / "p2_m5_cc08_builder_lock.py"


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


def test_private_manifest_rejects_reparse_input_without_reading_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    root = tmp_path / "input"
    root.mkdir()
    (root / "blocked.bin").write_bytes(b"do-not-read")
    monkeypatch.setattr(module, "_is_reparse", lambda _metadata: True)

    with pytest.raises(module.LockError, match="link or reparse point rejected"):
        module._manifest_payload(kind="fixture", inputs=[("source", root)], exclusions=[])


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
