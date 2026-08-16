from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mirror_api.providers.base import (
    OfflineSyntheticSourceProvenanceFact,
    SyntheticOutputSpecification,
)
from mirror_api.providers.mock import MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.scripts import codex_native_source_admission as admission_cli
from mirror_api.scripts.codex_native_source_admission import ManifestError, admit_manifest
from mirror_api.synthetic_dataset.codex_native_source import (
    CodexNativeAdmissionRejected,
    CodexNativeGenerationSpecification,
    CodexNativeSourceAdmissionService,
)

NOW = datetime(2026, 8, 16, tzinfo=UTC)


def _specification(**overrides: object) -> CodexNativeGenerationSpecification:
    values: dict[str, object] = {
        "schema_version": "mirror.synthetic-dataset/CodexNativeGenerationSpecification/v1",
        "specification_reference": "v01-category-a",
        "specification_version": "v01-spec-v1",
        "generation_policy_reference": "p2-codex-native-v1",
        "prompt_template_reference": "v01-canonical-frontal-v1",
        "prompt_digest": "1" * 64,
        "requested_pose_reference": "frontal-v1",
        "requested_expression_reference": "neutral-v1",
        "styling_constraints_reference": "minimal-makeup-v1",
        "output_specification": SyntheticOutputSpecification(
            media_type="image/png",
            width=1,
            height=1,
            max_byte_size=1024,
        ),
        "requested_quantity": 2,
        "max_attempts": 3,
        "retry_ceiling": 1,
        "concurrency_ceiling": 1,
        "stop_condition_reference": "v01-bounded-completion-v1",
        "coverage_pack_reference": "china-first-v1",
        "coverage_cell_reference": "canonical-frontal-v1",
        "synthetic_only": True,
        "real_person_reference_used": False,
    }
    values.update(overrides)
    return CodexNativeGenerationSpecification(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_codex_native_source_admits_only_known_facts_to_private_raw_storage(
    tmp_path: Path,
) -> None:
    storage = LocalSyntheticRawStorageProvider(root=tmp_path / "private")
    evidence = await CodexNativeSourceAdmissionService(storage=storage, now=lambda: NOW).admit(
        specification=_specification(),
        item_reference="v01-category-a-01",
        attempt=1,
        generated_at=NOW,
        content=MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES,
        media_type="image/png",
    )
    assert evidence.source_kind == "CODEX_NATIVE_IMAGEGEN"
    assert evidence.provenance_level == "PROVENANCE_ONLY"
    assert evidence.cost_accounting_mode == "REQUEST_COUNT_ONLY"
    assert evidence.model_reference is None
    assert evidence.model_version_reference is None
    assert evidence.provider_request_reference is None
    assert evidence.provider_actual_seed is None
    assert evidence.provider_usage is None
    assert evidence.provider_cost is None
    assert evidence.dimensions_match_requested
    assert evidence.requested_width == 1
    assert evidence.requested_height == 1
    assert evidence.synthetic_only
    assert not evidence.real_person_reference_used
    assert (
        await storage.inspect_generated_image(storage_reference=evidence.storage_reference)
        is not None
    )
    serialized = json.dumps(evidence.to_document(), sort_keys=True)
    assert "source_path" not in serialized
    assert "prompt_text" not in serialized
    assert "internal-synthetic" not in serialized


@pytest.mark.asyncio
async def test_codex_native_source_rejects_unbounded_or_mismatched_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exclude real-person"):
        _specification(real_person_reference_used=True)
    with pytest.raises(ValueError, match="serial"):
        _specification(concurrency_ceiling=2)
    service = CodexNativeSourceAdmissionService(
        storage=LocalSyntheticRawStorageProvider(root=tmp_path / "private"),
        now=lambda: NOW,
    )
    with pytest.raises(CodexNativeAdmissionRejected) as rejected:
        await service.admit(
            specification=_specification(),
            item_reference="v01-category-a-01",
            attempt=1,
            generated_at=NOW,
            content=b"not-an-image",
            media_type="image/png",
        )
    assert rejected.value.code == "source_decode_rejected"
    assert "not-an-image" not in str(rejected.value)

    with pytest.raises(CodexNativeAdmissionRejected) as retry_rejected:
        await service.admit(
            specification=_specification(),
            item_reference="v01-category-a-01",
            attempt=3,
            generated_at=NOW,
            content=MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES,
            media_type="image/png",
        )
    assert retry_rejected.value.code == "attempt_budget_exceeded"


@pytest.mark.asyncio
async def test_codex_native_manifest_rejects_attempt_sum_above_specification_budget(
    tmp_path: Path,
) -> None:
    source_paths: list[Path] = []
    for index in range(2):
        source = tmp_path / f"source-{index}.png"
        source.write_bytes(MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES)
        source_paths.append(source)
    specification = asdict(_specification())
    manifest = {
        "schema_version": "mirror.synthetic-dataset/CodexNativeAdmissionManifest/v1",
        "validation_reference": "bounded-attempt-negative",
        "specifications": [
            {
                "specification": specification,
                "items": [
                    {
                        "item_reference": f"bounded-item-{index}",
                        "attempt": 2,
                        "generated_at": NOW.isoformat(),
                        "source_path": str(source),
                        "expected_sha256": hashlib.sha256(
                            MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES
                        ).hexdigest(),
                    }
                    for index, source in enumerate(source_paths, start=1)
                ],
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError, match="attempt budget"):
        await admit_manifest(
            manifest_path=manifest_path,
            source_root=tmp_path,
            storage_root=tmp_path / "private",
            evidence_output=tmp_path / "evidence.json",
        )

    for item in manifest["specifications"][0]["items"]:  # type: ignore[index]
        item["attempt"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    approved_source_root = tmp_path / "approved-source"
    approved_source_root.mkdir()
    with pytest.raises(ManifestError, match="approved source root"):
        await admit_manifest(
            manifest_path=manifest_path,
            source_root=approved_source_root,
            storage_root=tmp_path / "private",
            evidence_output=tmp_path / "evidence.json",
        )

    for item in manifest["specifications"][0]["items"]:  # type: ignore[index]
        item["source_path"] = str(source_paths[0])
        item["expected_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError, match="checksum does not match"):
        await admit_manifest(
            manifest_path=manifest_path,
            source_root=tmp_path,
            storage_root=tmp_path / "private",
            evidence_output=tmp_path / "evidence.json",
        )

    for item in manifest["specifications"][0]["items"]:  # type: ignore[index]
        item["source_path"] = r"\\server\share\synthetic.png"
        item["expected_sha256"] = hashlib.sha256(MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError) as unc_rejected:
        await admit_manifest(
            manifest_path=manifest_path,
            source_root=tmp_path,
            storage_root=tmp_path / "private",
            evidence_output=tmp_path / "evidence.json",
        )
    assert "server" not in str(unc_rejected.value)

    symlink_root = tmp_path / "symlink-source"
    symlink_root.mkdir()
    symlink = symlink_root / "linked.png"
    symlink.symlink_to(source_paths[0])
    for item in manifest["specifications"][0]["items"]:  # type: ignore[index]
        item["source_path"] = str(symlink)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError, match="approved source root"):
        await admit_manifest(
            manifest_path=manifest_path,
            source_root=symlink_root,
            storage_root=tmp_path / "private",
            evidence_output=tmp_path / "evidence.json",
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "model_reference",
        "model_version_reference",
        "provider_request_reference",
        "provider_actual_seed",
        "provider_usage",
        "provider_cost",
    ),
)
def test_offline_provenance_rejects_fabricated_unknown_facts(field_name: str) -> None:
    values: dict[str, object] = {
        "source_kind": "CODEX_NATIVE_IMAGEGEN",
        "provenance_level": "PROVENANCE_ONLY",
        "generation_policy_reference": "p2-codex-native-v1",
        "prompt_template_reference": "v01-canonical-frontal-v1",
        "prompt_digest": "1" * 64,
        "generated_at": NOW,
        field_name: "fabricated",
    }
    with pytest.raises(ValueError, match="must remain null"):
        OfflineSyntheticSourceProvenanceFact(**values)  # type: ignore[arg-type]


def test_codex_native_cli_redacts_os_error_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    async def fail_with_path(**_: object) -> dict[str, object]:
        raise OSError(str(tmp_path / "sensitive-operator-path"))

    monkeypatch.setattr(admission_cli, "admit_manifest", fail_with_path)
    result = admission_cli.run(
        [
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--source-root",
            str(tmp_path / "source"),
            "--storage-root",
            str(tmp_path / "storage"),
            "--evidence-output",
            str(tmp_path / "evidence.json"),
        ]
    )
    assert result == 1
    stderr = capsys.readouterr().err
    assert "offline_source_io_failed" in stderr
    assert "sensitive-operator-path" not in stderr


def test_codex_native_source_is_not_a_runtime_provider_or_production_option() -> None:
    repo = Path(__file__).resolve().parents[3]
    config = (repo / "services/api/src/mirror_api/config.py").read_text(encoding="utf-8")
    runtime = (repo / "services/worker/src/mirror_worker/runtime.py").read_text(encoding="utf-8")
    providers = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (repo / "services/api/src/mirror_api/providers").glob("*.py")
    )
    assert "CODEX_NATIVE_IMAGEGEN" not in config
    assert "CODEX_NATIVE_IMAGEGEN" not in runtime
    assert "CodexImageGenerationProvider" not in providers
