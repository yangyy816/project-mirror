from __future__ import annotations

import ast
import json
import re
from dataclasses import fields
from pathlib import Path

from mirror_api.config import Settings
from mirror_api.main import app
from mirror_api.synthetic_dataset.task_contract import SyntheticGenerationTaskMessage

ROOT = Path(__file__).resolve().parents[3]
M2_REPOSITORY_SOURCE_PATHS = (
    *sorted((ROOT / "services/api/src/mirror_api/synthetic_dataset").glob("*.py")),
    ROOT / "services/worker/src/mirror_worker/synthetic_generation.py",
    ROOT / "services/worker/src/mirror_worker/runtime.py",
    ROOT / "services/worker/src/mirror_worker/celery_adapter.py",
)
M2_SOURCE_PATHS = tuple(path for path in M2_REPOSITORY_SOURCE_PATHS if path.is_file())
M2_PHASE_BOUNDARY_SOURCE_PATHS = (
    ROOT / "services/api/src/mirror_api/synthetic_dataset/codex_native_source.py",
    ROOT / "services/api/src/mirror_api/synthetic_dataset/generation_repository.py",
    ROOT / "services/api/src/mirror_api/synthetic_dataset/generation_service.py",
    ROOT / "services/api/src/mirror_api/synthetic_dataset/generation_types.py",
    ROOT / "services/api/src/mirror_api/synthetic_dataset/prompt_material.py",
    ROOT / "services/api/src/mirror_api/synthetic_dataset/raw_storage.py",
    ROOT / "services/worker/src/mirror_worker/synthetic_generation.py",
)
M3_SOURCE_PATHS = tuple(
    sorted((ROOT / "services/api/src/mirror_api/synthetic_dataset").glob("normalization*.py"))
    + sorted((ROOT / "services/api/src/mirror_api/synthetic_dataset").glob("qa*.py"))
)
FORBIDDEN_NETWORK_IMPORTS = frozenset(
    {"aiohttp", "boto3", "httpx", "requests", "tencentcloud", "urllib", "urllib3"}
)
FORBIDDEN_TASK_FIELDS = frozenset(
    {
        "bytes",
        "content",
        "credential",
        "image",
        "object_key",
        "policy",
        "prompt",
        "provider_url",
        "secret",
        "token",
        "url",
    }
)
FORBIDDEN_LOG_TERMS = frozenset(
    {"credential", "image", "object_key", "prompt", "provider_response", "secret", "url"}
)
LOG_METHODS = frozenset({"critical", "debug", "error", "exception", "info", "log", "warning"})


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


def test_generation_task_message_is_exactly_reference_only() -> None:
    assert {field.name for field in fields(SyntheticGenerationTaskMessage)} == {
        "item_id",
        "job_id",
        "request_id",
        "schema_version",
    }
    message = SyntheticGenerationTaskMessage(
        item_id="a" * 32,
        job_id="b" * 32,
        request_id="m2-reference-only",
    ).to_message()
    assert set(message).isdisjoint(FORBIDDEN_TASK_FIELDS)

    for forbidden in FORBIDDEN_TASK_FIELDS:
        invalid = {**message, forbidden: "must-not-cross-task-boundary"}
        try:
            SyntheticGenerationTaskMessage.from_message(invalid)
        except ValueError as exc:
            assert str(exc) == "synthetic generation task message has an invalid shape"
        else:  # pragma: no cover - the assertion describes a hard security boundary
            raise AssertionError(f"task contract accepted forbidden field: {forbidden}")


def test_m2_pipeline_has_no_network_sdk_url_or_sensitive_logging_path() -> None:
    assert all(path.is_file() for path in M2_SOURCE_PATHS)
    assert any("synthetic_dataset" in path.parts for path in M2_SOURCE_PATHS)
    for source_path in M2_SOURCE_PATHS:
        source = source_path.read_text(encoding="utf-8")
        assert not re.search(r"https?://", source, flags=re.IGNORECASE), source_path
        tree = ast.parse(source, filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                roots = {name.split(".", 1)[0].lower() for name in names}
                assert roots.isdisjoint(FORBIDDEN_NETWORK_IMPORTS), (source_path, roots)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in LOG_METHODS
            ):
                rendered = ast.unparse(node).lower()
                assert not any(term in rendered for term in FORBIDDEN_LOG_TERMS), (
                    source_path,
                    rendered,
                )


def test_m2_does_not_cross_into_m3_or_public_api_scope() -> None:
    assert M3_SOURCE_PATHS
    assert all(path.is_file() for path in M2_PHASE_BOUNDARY_SOURCE_PATHS)
    assert set(M2_PHASE_BOUNDARY_SOURCE_PATHS).isdisjoint(M3_SOURCE_PATHS)
    committed = json.loads((ROOT / "packages/contracts/openapi.json").read_text(encoding="utf-8"))
    assert committed == app.openapi()
    assert not any("synthetic" in path.lower() for path in committed["paths"])

    m2_source = "\n".join(
        path.read_text(encoding="utf-8") for path in M2_PHASE_BOUNDARY_SOURCE_PATHS
    )
    for forbidden_symbol in (
        "BaselineFaceModel",
        "QuestionBankManifest",
        "SyntheticIdentity",
        "SyntheticQARun",
        "VariantSpecification",
    ):
        assert forbidden_symbol not in m2_source


def test_production_generation_pipeline_remains_disabled_and_fail_closed() -> None:
    settings = Settings.model_validate(_production_settings())
    assert settings.image_generation_provider == "disabled"
    assert settings.synthetic_storage_provider == "disabled"
