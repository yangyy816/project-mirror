from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from test_demo_d02_final_orchestrator import _prepared_runtime

from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_targeted_m4_repair_backend as backend_module
from mirror_api import demo_d02_targeted_m4_repair_execution as execution
from mirror_api.demo_d02_private_vision_backend import WindowsFaceLandmarkerOfflineM3Backend
from mirror_api.demo_d02_targeted_m4_repair_backend import (
    D02TargetedM4RepairBackend,
    TargetedJawRepairConfig,
)


def _unused_runner(*_: object, **__: object) -> object:
    raise AssertionError("factory construction must not execute M3")


@pytest.fixture(autouse=True)
def _allow_small_synthetic_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    def decode(content: bytes, *, expected_width: int, expected_height: int) -> object:
        with Image.open(BytesIO(content)) as image:
            image.load()
            rgb = image.convert("RGB")
            try:
                assert rgb.size == (expected_width, expected_height)
                return SimpleNamespace(
                    bytes_value=rgb.tobytes(),
                    width=expected_width,
                    height=expected_height,
                )
            finally:
                rgb.close()

    monkeypatch.setattr(backend_module, "decode_canonical_rgb_image", decode)


def _context(
    tmp_path: Path, *, strength_ppm: int = 100_000
) -> execution.TargetedM4ExecutionContext:
    prepared, _, _ = _prepared_runtime()
    staging = tmp_path / "staging"
    staging.mkdir(parents=True)
    m3 = WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=staging,
        runner=_unused_runner,  # type: ignore[arg-type]
    )
    m4 = D02TargetedM4RepairBackend(
        material=prepared.source_materials[2],
        config=TargetedJawRepairConfig(strength_ppm=strength_ppm),
    )
    return execution.prepare_targeted_execution(
        predecessor=prepared,
        m3_backend=m3,
        m4_backend=m4,
    )


def test_targeted_factory_keeps_v1_allowlist_closed(tmp_path: Path) -> None:
    context = _context(tmp_path)

    assert context.recipe.m4_algorithm_version == "d02-targeted-jaw-repair-v1"
    assert (
        context.recipe.runtime_manifest_digest
        == runtime.build_default_runtime_recipe().runtime_manifest_digest
    )
    assert context.replacement_case["case_ordinal"] == 25
    assert context.replacement_case["source_ordinal"] == 3
    assert context.replacement_case["dimension_key"] == "jaw_width"
    assert context.replacement_case["direction"] == "DECREASE"
    assert context.replacement_case["magnitude_ppm"] == 15_000
    with pytest.raises(ValueError, match="accepted Demo-only recipe"):
        runtime.mint_runtime_handles(
            context.executor.manifest,
            recipe=context.recipe,
            model_identity=context.executor.model_identity,
        )


def test_targeted_factory_executes_only_two_bound_m4_replays(tmp_path: Path) -> None:
    context = _context(tmp_path)

    first, second = execution.execute_target_m4(context)

    assert first.case_id == context.replacement_case["case_id"]
    assert second.case_id == first.case_id
    assert (first.replay_index, second.replay_index) == (1, 2)
    assert first.content == second.content
    assert first.result_sha256 == second.result_sha256
    assert first.result_sha256 != context.source_material.descriptor.content_sha256
    with pytest.raises(ValueError, match="D02_TARGETED_M4_REPAIR_FAILED"):
        context.executor.transform(
            material=context.source_material,
            case_entry=context.replacement_case,
            replay_index=2,
        )


def test_configuration_digest_changes_successor_case_identity(tmp_path: Path) -> None:
    first = _context(tmp_path / "first", strength_ppm=750)
    second = _context(tmp_path / "second", strength_ppm=1_000)

    assert (
        first.replacement_case["runtime_config_digest"]
        != second.replacement_case["runtime_config_digest"]
    )
    assert first.replacement_case["case_id"] != second.replacement_case["case_id"]
    assert (
        first.replacement_case["case_specification_digest"]
        != second.replacement_case["case_specification_digest"]
    )


def test_targeted_recipe_rejects_non_v1_predecessor() -> None:
    original = runtime.build_default_runtime_recipe()
    altered = replace(original, recipe_version="foreign-recipe-v1")
    with pytest.raises(
        execution.D02TargetedM4RepairExecutionError,
        match="TARGETED_PREDECESSOR_RECIPE_INVALID",
    ):
        execution.build_targeted_runtime_recipe(
            predecessor_recipe=altered,
            algorithm_version="d02-targeted-jaw-repair-v1",
        )
