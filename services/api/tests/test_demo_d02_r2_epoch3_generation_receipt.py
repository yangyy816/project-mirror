from __future__ import annotations

from copy import deepcopy

import pytest
from test_demo_d02_r2_generation_e3 import _contract

from mirror_api.demo_d02_r2_epoch3_generation_receipt import (
    E3_TERMINAL_SUCCESS,
    Epoch3SequenceState,
    build_epoch3_source_generation_receipt,
    build_epoch3_terminal_source_receipt,
    validate_epoch3_source_generation_receipt,
    validate_epoch3_terminal_source_receipt,
)
from mirror_api.demo_d02_r2_generation_e3 import (
    E3_CONTEXT,
    E4_CONTEXT,
    Epoch3GenerationError,
    GenerationExecutionContext,
)


def _digest(character: str) -> str:
    return character * 64


def _source_receipt(
    contract: dict[str, object],
    ordinal: int,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> dict[str, object]:
    return build_epoch3_source_generation_receipt(
        contract=contract,
        ordinal=ordinal,
        root_name_receipt_digest=_digest("a"),
        generation_preregistration_digest=_digest("b"),
        source_allocation_manifest_digest=_digest("c"),
        source_producer_dispatch_digest=_digest("d"),
        output_name_receipt_digest=_digest("e"),
        output_seal_receipt_digest=_digest("f"),
        registry_commit_receipt_digest=_digest("1"),
        generation_capability_authority_digest=_digest("2"),
        generation_request_digest=_digest("3"),
        generation_result_provenance_digest=_digest("4"),
        source_provenance_name_receipt_digest=_digest("5"),
        source_provenance_seal_receipt_digest=_digest("6"),
        source_provenance_registry_commit_receipt_digest=_digest("7"),
        source_asset_sha256=_digest("8"),
        source_asset_byte_size=100,
        source_asset_width=128,
        source_asset_height=128,
        context=context,
    )


def _terminal_receipt(
    contract: dict[str, object],
    source_receipt: dict[str, object],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> dict[str, object]:
    return build_epoch3_terminal_source_receipt(
        contract=contract,
        generation_receipt=source_receipt,
        terminal_state=E3_TERMINAL_SUCCESS,
        jpeg_sha256=_digest("b"),
        jpeg_byte_size=80,
        jpeg_width=128,
        jpeg_height=128,
        normalization_receipt_digest=_digest("c"),
        durable_source_descriptor_digest=_digest("d"),
        prompt_material_digest=_digest("e"),
        context=context,
    )


def test_e3_receipt_replays_and_binds_png_jpeg_without_paths() -> None:
    contract = _contract()
    source_receipt = _source_receipt(contract, 1)
    receipt = _terminal_receipt(contract, source_receipt)
    assert (
        validate_epoch3_source_generation_receipt(source_receipt, contract=contract)
        == source_receipt
    )
    assert (
        validate_epoch3_terminal_source_receipt(
            receipt,
            contract=contract,
            generation_receipt=source_receipt,
        )
        == receipt
    )
    assert all("path" not in key and "locator" not in key for key in receipt)


def test_e3_receipt_rejects_tamper_and_e2_schema() -> None:
    contract = _contract()
    source_receipt = _source_receipt(contract, 1)
    receipt = _terminal_receipt(contract, source_receipt)
    tampered = deepcopy(receipt)
    tampered["jpeg_width"] = 129
    with pytest.raises(Epoch3GenerationError):
        validate_epoch3_terminal_source_receipt(
            tampered,
            contract=contract,
            generation_receipt=source_receipt,
        )
    foreign = deepcopy(receipt)
    foreign["schema_version"] = "mirror.demo/D02R2Epoch2SourceGenerationReceipt/v1"
    with pytest.raises(Epoch3GenerationError, match="E2"):
        validate_epoch3_terminal_source_receipt(
            foreign,
            contract=contract,
            generation_receipt=source_receipt,
        )


def test_e3_sequence_is_serial_and_failure_stops_future_calls() -> None:
    contract = _contract()
    state = Epoch3SequenceState.begin(contract)
    source_one = _source_receipt(contract, 1)
    state = state.record_success(
        _terminal_receipt(contract, source_one),
        contract=contract,
        generation_receipt=source_one,
    )
    assert state.next_ordinal() == 2
    failed = state.record_failure(ordinal=2)
    with pytest.raises(Epoch3GenerationError, match="failed closed"):
        failed.next_ordinal()
    with pytest.raises(Epoch3GenerationError, match="serial ordinal"):
        source_three = _source_receipt(contract, 3)
        state.record_success(
            _terminal_receipt(contract, source_three),
            contract=contract,
            generation_receipt=source_three,
        )


def test_e4_receipts_serialize_all_four_ordinals_and_reject_e3() -> None:
    contract = _contract(E4_CONTEXT)
    state = Epoch3SequenceState.begin(contract, context=E4_CONTEXT)
    for ordinal in range(1, 5):
        source = _source_receipt(contract, ordinal, E4_CONTEXT)
        terminal = _terminal_receipt(contract, source, E4_CONTEXT)
        assert terminal["schema_version"] == E4_CONTEXT.terminal_source_receipt_schema
        assert (
            validate_epoch3_source_generation_receipt(source, contract=contract, context=E4_CONTEXT)
            == source
        )
        state = state.record_success(terminal, contract=contract, generation_receipt=source)
    assert state.completed_ordinals == (1, 2, 3, 4)
    with pytest.raises(Epoch3GenerationError):
        validate_epoch3_source_generation_receipt(source, contract=contract)
