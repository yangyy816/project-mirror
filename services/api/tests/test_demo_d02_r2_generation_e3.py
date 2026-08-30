from __future__ import annotations

from copy import deepcopy

import pytest

from mirror_api.demo_d02_r2_generation_e3 import (
    E3_CONTEXT,
    E3_CONTRACT_SCHEMA,
    E4_CONTEXT,
    Epoch3GenerationError,
    GenerationExecutionContext,
    build_epoch3_allocation,
    build_epoch3_generation_contract,
    validate_epoch3_generation_contract,
)


def _contract(
    context: GenerationExecutionContext = E3_CONTEXT,
) -> dict[str, object]:
    return build_epoch3_generation_contract(
        allocations=[
            build_epoch3_allocation(
                ordinal=ordinal,
                source_output_id=f"e3-source-{ordinal}",
                provenance_output_id=f"e3-provenance-{ordinal}",
                normalized_jpeg_output_id=f"e3-jpeg-{ordinal}",
                context=context,
            )
            for ordinal in range(1, 5)
        ],
        context=context,
    )


def test_e3_contract_replays_with_four_unique_allocations() -> None:
    contract = _contract()
    assert contract["schema_version"] == E3_CONTRACT_SCHEMA
    assert validate_epoch3_generation_contract(contract) == contract
    assert build_epoch3_generation_contract(allocations=contract["allocations"]) == contract
    profiles = [allocation["source_policy_profile"] for allocation in contract["allocations"]]
    age_bands = [profile["declared_age_band"] for profile in profiles]
    assert age_bands.count("ADULT_20_25") == 3
    assert age_bands.count("ADULT_18_19") == 1
    assert len({profile["base_identity_family"] for profile in profiles}) == 4


def test_e3_contract_rejects_private_and_cross_version_shapes() -> None:
    contract = _contract()
    foreign = deepcopy(contract)
    foreign["schema_version"] = "mirror.demo/D02R2Epoch2GenerationRequestPolicy/v1"
    with pytest.raises(Epoch3GenerationError, match="E2"):
        validate_epoch3_generation_contract(foreign)
    tampered = deepcopy(contract)
    tampered["prompt_locator"] = "forbidden"
    with pytest.raises(Epoch3GenerationError, match="private"):
        validate_epoch3_generation_contract(tampered)


def test_e3_contract_rejects_duplicate_preallocated_ids() -> None:
    allocations = [
        build_epoch3_allocation(
            ordinal=ordinal,
            source_output_id=f"source-{ordinal}",
            provenance_output_id=f"provenance-{ordinal}",
            normalized_jpeg_output_id="shared-jpeg" if ordinal in (1, 2) else f"jpeg-{ordinal}",
        )
        for ordinal in range(1, 5)
    ]
    with pytest.raises(Epoch3GenerationError, match="unique"):
        build_epoch3_generation_contract(allocations=allocations)


def test_e3_contract_rejects_minor_or_relabelled_policy_profile() -> None:
    contract = _contract()
    tampered = deepcopy(contract)
    tampered["allocations"][0]["source_policy_profile"]["declared_age_band"] = "UNDER_18"
    with pytest.raises(Epoch3GenerationError, match="profile"):
        validate_epoch3_generation_contract(tampered)


def test_e4_contract_is_distinct_and_cross_epoch_rejected() -> None:
    contract = _contract(E4_CONTEXT)
    assert contract["schema_version"] == E4_CONTEXT.contract_schema
    assert contract["task_id"] == E4_CONTEXT.task_id
    assert contract["root_id"] == E4_CONTEXT.root_id
    assert contract["dispatch_epoch"] == 4
    assert validate_epoch3_generation_contract(contract, context=E4_CONTEXT) == contract
    assert all(
        allocation["source_policy_profile"]["base_identity_family"].startswith("E4_")
        for allocation in contract["allocations"]
    )
    with pytest.raises(Epoch3GenerationError):
        validate_epoch3_generation_contract(contract)
    with pytest.raises(Epoch3GenerationError):
        validate_epoch3_generation_contract(_contract(), context=E4_CONTEXT)
