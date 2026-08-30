from __future__ import annotations

import pytest

from mirror_api import demo_d02_r2_e3_admission as e3
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api.demo_d02_r2_generation_e3 import E4_CONTEXT


def test_e3_runtime_descriptor_rejects_epoch2_shape() -> None:
    """No E2 packet may cross the newly explicit E3 constructor boundary."""

    with pytest.raises((e3.D02R2Epoch3AdmissionError, runtime.RuntimeForwardError)):
        runtime.DurableSourceDescriptor.from_epoch3_packet({})


def test_e4_runtime_recipe_reuses_frozen_backends_with_e4_preprocessing() -> None:
    recipe = runtime.build_epoch3_runtime_recipe(context=E4_CONTEXT)
    assert recipe.recipe_version == E4_CONTEXT.runtime_recipe_version
    assert recipe.preprocessing_version == E4_CONTEXT.source_normalization_version
    assert recipe.m3_algorithm_version == runtime.M3_ALGORITHM_VERSION
    assert recipe.m4_algorithm_version == runtime.M4_ALGORITHM_VERSION
