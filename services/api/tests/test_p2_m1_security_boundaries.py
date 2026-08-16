from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from dataclasses import fields
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from mirror_api.config import Settings
from mirror_api.main import app
from mirror_api.providers.base import (
    GeneratedImagePayload,
    SyntheticGenerationRequest,
    SyntheticStorageWriteRequest,
    SyntheticVisionRequest,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
MANIFEST_PATH = FIXTURE_ROOT / "p2_m1_fixture_manifest.json"
P2_SOURCE_PATHS = (
    ROOT / "services/api/src/mirror_api/synthetic_dataset/domain.py",
    ROOT / "services/api/src/mirror_api/providers/base.py",
    ROOT / "services/api/src/mirror_api/providers/mock.py",
    ROOT / "services/api/src/mirror_api/providers/tencent.py",
    ROOT / "services/api/src/mirror_api/storage_keys.py",
)
PROHIBITED_RUNTIME_PACKAGES = frozenset({"cv2", "imagededup", "mediapipe", "opencv"})
MODEL_ARTIFACT_SUFFIXES = frozenset(
    {".bin", ".ckpt", ".onnx", ".pt", ".pth", ".safetensors", ".task", ".tflite"}
)
REAL_FACE_FIXTURE_SUFFIXES = frozenset(
    {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
)


def _repository_files() -> tuple[Path, ...]:
    git_executable = shutil.which("git")
    if git_executable is None:
        copied_roots = (ROOT / "services/api", ROOT / "packages/contracts")
        return tuple(
            path
            for copied_root in copied_roots
            if copied_root.is_dir()
            for path in copied_root.rglob("*")
            if path.is_file()
        )
    result = subprocess.run(  # noqa: S603 - fixed executable and fixed argument vector
        [git_executable, "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(ROOT / line for line in result.stdout.splitlines() if line)


def _load_manifest() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def _admit_fixture_manifest(manifest: dict[str, Any]) -> tuple[Path, ...]:
    if manifest.get("schema_version") != "mirror.p2-m1.fixture-manifest/v1":
        raise ValueError("unsupported fixture manifest schema")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("fixture manifest entries must be non-empty")

    admitted: list[Path] = []
    for untyped_entry in entries:
        if not isinstance(untyped_entry, dict):
            raise ValueError("fixture manifest entry must be an object")
        entry = cast(dict[str, object], untyped_entry)
        if entry.get("classification") != "non_human_numeric":
            raise ValueError("only non-human numeric fixtures are admitted in P2-M1")
        if entry.get("source") != "first_party_deterministic":
            raise ValueError("fixture source is not approved")
        if entry.get("license") != "project_mirror_test_fixture":
            raise ValueError("fixture license is not approved")
        relative_path = entry.get("path")
        checksum = entry.get("sha256")
        if not isinstance(relative_path, str) or not re.fullmatch(
            r"[a-z0-9_.-]+\.json", relative_path
        ):
            raise ValueError("fixture path must be one local JSON filename")
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            raise ValueError("fixture checksum must be lowercase SHA-256")
        fixture_path = (FIXTURE_ROOT / relative_path).resolve()
        if fixture_path.parent != FIXTURE_ROOT.resolve() or not fixture_path.is_file():
            raise ValueError("fixture path must remain inside the fixture root")
        if sha256(fixture_path.read_bytes()).hexdigest() != checksum:
            raise ValueError("fixture checksum mismatch")
        admitted.append(fixture_path)
    return tuple(admitted)


def _production_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://service:nondefault@db.internal/mirror",
        "redis_url": "rediss://redis.internal/0",
        "cors_origins": ["https://mirror.invalid"],
        "auth_token_secret": "x" * 64,
        "auth_jwt_keyring": {"prod-v1": "j" * 64},
        "auth_jwt_active_kid": "prod-v1",
        "auth_hmac_keyring": {"prod-v1": "h" * 64},
        "auth_hmac_active_kid": "prod-v1",
        "auth_callback_url": "https://mirror.invalid/auth/callback",
        "auth_required_policies": [
            {"document_code": "privacy", "document_version": "v1", "document_digest": "d" * 64}
        ],
        "facial_data_purpose": {"policy_digest": "f" * 64},
        "sms_provider": "tencent",
        "storage_provider": "tencent_cos",
        "task_runner": "celery",
        "vision_provider": "disabled",
        "image_generation_provider": "disabled",
        "synthetic_storage_provider": "disabled",
        "agent_provider": "disabled",
        "tencent_secret_id": "secret-manager-reference-id",
        "tencent_secret_key": "secret-manager-reference-key",
        "tencent_region": "ap-beijing",
        "tencent_cos_bucket": "private-bucket",
        "tencent_sms_app_id": "secret-manager-reference-app",
        "tencent_sms_sign_name": "approved-sign-name",
    }
    values.update(overrides)
    return values


def test_fixture_manifest_admits_only_checksum_bound_non_human_numeric_json() -> None:
    admitted = _admit_fixture_manifest(_load_manifest())
    assert admitted == (FIXTURE_ROOT / "p2_m1_numeric_fixture.json",)
    fixture = json.loads(admitted[0].read_text(encoding="utf-8"))
    assert fixture == {
        "schema_version": "mirror.p2-m1.numeric-fixture/v1",
        "values": [0.0, 0.25, -0.25, 1.0],
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("classification", "synthetic_face", "non-human numeric"),
        ("source", "unknown", "source"),
        ("license", "unknown", "license"),
        ("path", "../outside.json", "path"),
        ("sha256", "0" * 64, "checksum mismatch"),
    ],
)
def test_fixture_manifest_rejects_unapproved_or_unverifiable_entries(
    field: str, value: str, message: str
) -> None:
    manifest = _load_manifest()
    manifest["entries"][0][field] = value
    with pytest.raises(ValueError, match=message):
        _admit_fixture_manifest(manifest)


def test_0008_static_schema_contract_is_forward_only_and_contains_database_guards() -> None:
    migration = (
        ROOT / "services/api/migrations/versions/0008_synthetic_dataset_foundation.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "0008_synth_dataset_foundation"' in migration
    assert 'down_revision: str | None = "0007_account_quarantine_evidence"' in migration
    for table_name in (
        "synthetic_generation_policies",
        "synthetic_prompt_templates",
        "synthetic_qa_policies",
        "geometry_ontology_versions",
    ):
        assert migration.count(f'"{table_name}"') >= 2
    for guard in (
        "mirror_validate_synthetic_authority_record",
        "mirror_reject_mutation",
        "mirror_protect_original_asset",
    ):
        assert guard in migration


@pytest.mark.parametrize(
    "override",
    [
        {"image_generation_provider": "mock"},
        {"vision_provider": "mock"},
        {"synthetic_storage_provider": "mock"},
        {"sensitive_processing_enabled": True},
    ],
)
def test_p2_production_capabilities_fail_closed(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(_production_settings(**override))


def test_public_openapi_is_unchanged_by_internal_p2_contracts() -> None:
    committed = json.loads((ROOT / "packages/contracts/openapi.json").read_text(encoding="utf-8"))
    assert committed == app.openapi()
    assert not any("synthetic" in path.lower() for path in committed["paths"])


def test_p2_ports_have_no_plaintext_prompt_url_secret_or_user_asset_fields() -> None:
    request_fields = {field.name for field in fields(SyntheticGenerationRequest)}
    assert "prompt_template_reference" in request_fields
    assert "prompt" not in request_fields
    for contract in (
        GeneratedImagePayload,
        SyntheticGenerationRequest,
        SyntheticVisionRequest,
        SyntheticStorageWriteRequest,
    ):
        names = {field.name.lower() for field in fields(contract)}
        assert not names & {
            "credential",
            "object_key",
            "prompt",
            "secret",
            "token",
            "url",
            "user_id",
        }


def test_p2_source_has_no_external_url_sdk_import_or_sensitive_logging_path() -> None:
    forbidden_logging_terms = {
        "content",
        "credential",
        "object_key",
        "prompt",
        "secret",
        "token",
        "url",
    }
    logging_methods = {"critical", "debug", "error", "exception", "info", "log", "warning"}
    for source_path in P2_SOURCE_PATHS:
        source = source_path.read_text(encoding="utf-8")
        assert not re.search(r"https?://", source, flags=re.IGNORECASE), source_path
        tree = ast.parse(source, filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                roots = {name.split(".", 1)[0].lower() for name in imported}
                assert roots.isdisjoint(PROHIBITED_RUNTIME_PACKAGES), (source_path, roots)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in logging_methods
            ):
                rendered = ast.unparse(node).lower()
                assert not any(term in rendered for term in forbidden_logging_terms), (
                    source_path,
                    rendered,
                )


def test_repository_has_no_unapproved_p2_dependency_model_or_face_fixture() -> None:
    repository_files = _repository_files()
    dependency_files = [
        path
        for path in repository_files
        if path.name in {"package.json", "pnpm-lock.yaml", "pyproject.toml"}
        or "requirements" in path.name.lower()
    ]
    dependency_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore").lower() for path in dependency_files
    )
    for package in PROHIBITED_RUNTIME_PACKAGES:
        assert not re.search(rf"(?<![a-z0-9_-]){re.escape(package)}(?![a-z0-9_-])", dependency_text)

    assert not [path for path in repository_files if path.suffix.lower() in MODEL_ARTIFACT_SUFFIXES]
    fixture_media = [
        path
        for path in repository_files
        if "services/api/tests/fixtures" in path.as_posix()
        and path.suffix.lower() in REAL_FACE_FIXTURE_SUFFIXES
    ]
    assert fixture_media == []
