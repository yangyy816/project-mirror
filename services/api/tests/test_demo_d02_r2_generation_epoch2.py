from __future__ import annotations

import copy
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest

from mirror_api import demo_d02_r2_generation_epoch2 as epoch2
from mirror_api.demo_measurement_quality import mirror_demo_digest


@pytest.fixture(autouse=True)
def _isolate_epoch_lease_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(epoch2, "_LEASE_STATES", {})
    monkeypatch.setattr(epoch2, "_LEASE_EPOCH_ACTIVATION_DIGEST", None)
    yield


def _allocations() -> tuple[epoch2.Epoch2Allocation, ...]:
    return tuple(
        epoch2.Epoch2Allocation(
            candidate_ordinal=ordinal,
            source_output_id=f"e2-source-{ordinal}",
            source_name_receipt_digest=f"{ordinal}" * 64,
            provenance_output_id=f"e2-provenance-{ordinal}",
            provenance_name_receipt_digest=f"{ordinal + 4}" * 64,
            prompt_material_digest=f"{ordinal + 8:x}" * 64,
        )
        for ordinal in range(1, 5)
    )


def _activation(*, root_receipt_digest: str = "a" * 64) -> epoch2.JsonObject:
    return epoch2.build_reserve_activation_authority(
        terminal_binding=epoch2.expected_e1_terminal_binding(),
        root_name_receipt_digest=root_receipt_digest,
        allocations=_allocations(),
    )


def _request(
    activation: epoch2.JsonObject,
    *,
    candidate_ordinal: int,
) -> epoch2.JsonObject:
    return epoch2.build_generation_request(
        reserve_activation=activation,
        generation_preregistration_digest="b" * 64,
        candidate_ordinal=candidate_ordinal,
    )


def test_reserve_activation_replays_exactly() -> None:
    activation = _activation()

    assert epoch2.validate_reserve_activation_authority(activation) == activation
    assert activation["reserve_calls_authorized"] == 4
    assert activation["e1_actual_call_count"] == 1
    assert activation["total_actual_call_ceiling"] == 5
    assert activation["activation_state"] == "ACTIVATED_FOR_E2_ONLY"


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("terminal_head_digest", "0" * 64),
        ("event_count", 9),
        ("product_event_count", 1),
        ("actual_call_count", 0),
        ("state", "COMPLETED"),
    ),
)
def test_terminal_binding_mismatch_fails_closed(field: str, replacement: object) -> None:
    values = {
        name: getattr(epoch2.expected_e1_terminal_binding(), name)
        for name in epoch2.E1TerminalBinding.__dataclass_fields__
    }
    values[field] = replacement
    binding = epoch2.E1TerminalBinding(**values)

    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="PREDECESSOR_TERMINAL"):
        epoch2.build_reserve_activation_authority(
            terminal_binding=binding,
            root_name_receipt_digest="a" * 64,
            allocations=_allocations(),
        )


def test_exactly_four_ordered_allocations_are_required() -> None:
    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="exactly four"):
        epoch2.build_reserve_activation_authority(
            terminal_binding=epoch2.expected_e1_terminal_binding(),
            root_name_receipt_digest="a" * 64,
            allocations=_allocations()[:3],
        )
    reversed_allocations = tuple(reversed(_allocations()))
    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="ordered ordinals"):
        epoch2.build_reserve_activation_authority(
            terminal_binding=epoch2.expected_e1_terminal_binding(),
            root_name_receipt_digest="a" * 64,
            allocations=reversed_allocations,
        )


@pytest.mark.parametrize("collision", ("output", "receipt"))
def test_cross_allocation_collisions_fail_closed(collision: str) -> None:
    allocations = list(_allocations())
    original = allocations[1]
    first = allocations[0]
    allocations[1] = epoch2.Epoch2Allocation(
        candidate_ordinal=original.candidate_ordinal,
        source_output_id=first.source_output_id
        if collision == "output"
        else original.source_output_id,
        source_name_receipt_digest=(
            first.source_name_receipt_digest
            if collision == "receipt"
            else original.source_name_receipt_digest
        ),
        provenance_output_id=original.provenance_output_id,
        provenance_name_receipt_digest=original.provenance_name_receipt_digest,
        prompt_material_digest=original.prompt_material_digest,
    )

    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="collide"):
        epoch2.build_reserve_activation_authority(
            terminal_binding=epoch2.expected_e1_terminal_binding(),
            root_name_receipt_digest="a" * 64,
            allocations=allocations,
        )


def test_fully_resigned_activation_splice_is_rejected() -> None:
    forged = copy.deepcopy(_activation())
    forged["e2_root_id"] = "P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT"
    forged["reserve_activation_digest"] = mirror_demo_digest(
        epoch2.RESERVE_ACTIVATION_SCHEMA,
        {key: value for key, value in forged.items() if key != "reserve_activation_digest"},
    )

    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="activation drifted"):
        epoch2.validate_reserve_activation_authority(forged)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("e1_actual_call_count", True),
        ("retry_ceiling", False),
        ("concurrency", True),
    ),
)
def test_activation_rejects_bool_integer_substitution(
    field: str,
    replacement: epoch2.JsonValue,
) -> None:
    forged = copy.deepcopy(_activation())
    forged[field] = replacement

    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="digest does not replay"):
        epoch2.validate_reserve_activation_authority(forged)


def test_request_binds_one_exact_allocation() -> None:
    activation = _activation()
    request = _request(activation, candidate_ordinal=3)

    assert epoch2.validate_generation_request(request, reserve_activation=activation) == request
    assert request["candidate_ordinal"] == 3
    assert request["source_output_id"] == "e2-source-3"
    assert request["dispatch_epoch"] == 2
    assert request["retry_ceiling"] == 0
    assert request["concurrency"] == 1


@pytest.mark.parametrize("ordinal", (0, 5, True))
def test_request_rejects_out_of_epoch_ordinal(ordinal: int) -> None:
    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="ordinal"):
        epoch2.build_generation_request(
            reserve_activation=_activation(),
            generation_preregistration_digest="b" * 64,
            candidate_ordinal=ordinal,
        )


def test_fully_resigned_request_splice_is_rejected() -> None:
    activation = _activation()
    forged = copy.deepcopy(_request(activation, candidate_ordinal=2))
    forged["source_output_id"] = "e2-source-forged"
    forged["generation_request_digest"] = mirror_demo_digest(
        epoch2.GENERATION_REQUEST_SCHEMA,
        {key: value for key, value in forged.items() if key != "generation_request_digest"},
    )

    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="request drifted"):
        epoch2.validate_generation_request(forged, reserve_activation=activation)


def test_lease_is_single_use_and_revoked_on_success() -> None:
    activation = _activation(root_receipt_digest="c" * 64)
    request = _request(activation, candidate_ordinal=1)
    lease = epoch2.acquire_ordinal_control_plane_lease(
        reserve_activation=activation,
        generation_request=request,
    )

    with lease:
        assert lease.active is True
    assert lease.active is False
    assert lease.used is True
    lease.assert_revoked()
    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="not reusable"):
        with lease:
            pass
    with pytest.raises(epoch2.D02R2Epoch2GenerationError, match="already been consumed"):
        epoch2.acquire_ordinal_control_plane_lease(
            reserve_activation=activation,
            generation_request=request,
        )


def test_lease_is_revoked_on_exception_and_base_exception() -> None:
    activation = _activation(root_receipt_digest="4" * 64)
    for index, error in enumerate((RuntimeError("failure"), KeyboardInterrupt()), start=1):
        lease = epoch2.acquire_ordinal_control_plane_lease(
            reserve_activation=activation,
            generation_request=_request(activation, candidate_ordinal=index),
        )
        with pytest.raises(type(error)):
            with lease:
                raise error
        lease.assert_revoked()


def test_lease_context_always_returns_default_deny() -> None:
    activation = _activation(root_receipt_digest="f" * 64)
    lease = epoch2.acquire_ordinal_control_plane_lease(
        reserve_activation=activation,
        generation_request=_request(activation, candidate_ordinal=4),
    )

    def run() -> Iterator[bool]:
        with lease:
            yield lease.active
        yield lease.active

    assert list(run()) == [True, False]


def test_concurrent_lease_acquisition_has_one_canonical_winner() -> None:
    activation = _activation(root_receipt_digest="9" * 64)
    request = _request(activation, candidate_ordinal=3)

    def acquire() -> str:
        try:
            epoch2.acquire_ordinal_control_plane_lease(
                reserve_activation=activation,
                generation_request=request,
            )
        except epoch2.D02R2Epoch2GenerationError as error:
            return error.code
        return "WINNER"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: acquire(), range(2)))

    assert sorted(results) == ["E2_CALL_CEILING_STOP", "WINNER"]


def test_second_valid_activation_cannot_reallocate_the_same_epoch() -> None:
    first_activation = _activation(root_receipt_digest="e" * 64)
    alternate_allocations = tuple(
        epoch2.Epoch2Allocation(
            candidate_ordinal=item.candidate_ordinal,
            source_output_id=f"e2-alternate-source-{item.candidate_ordinal}",
            source_name_receipt_digest=item.source_name_receipt_digest,
            provenance_output_id=f"e2-alternate-provenance-{item.candidate_ordinal}",
            provenance_name_receipt_digest=item.provenance_name_receipt_digest,
            prompt_material_digest=item.prompt_material_digest,
        )
        for item in _allocations()
    )
    second_activation = epoch2.build_reserve_activation_authority(
        terminal_binding=epoch2.expected_e1_terminal_binding(),
        root_name_receipt_digest="e" * 64,
        allocations=alternate_allocations,
    )
    assert (
        first_activation["reserve_activation_digest"]
        != second_activation["reserve_activation_digest"]
    )

    first_lease = epoch2.acquire_ordinal_control_plane_lease(
        reserve_activation=first_activation,
        generation_request=_request(first_activation, candidate_ordinal=1),
    )
    with first_lease:
        pass
    first_lease.assert_revoked()

    with pytest.raises(
        epoch2.D02R2Epoch2GenerationError,
        match="frozen E2 epoch authority",
    ):
        epoch2.acquire_ordinal_control_plane_lease(
            reserve_activation=second_activation,
            generation_request=_request(second_activation, candidate_ordinal=2),
        )


def test_lease_constructor_rejects_unvalidated_authority() -> None:
    with pytest.raises(
        epoch2.D02R2Epoch2GenerationError,
        match="validated request",
    ):
        epoch2.OrdinalControlPlaneLease(
            candidate_ordinal=1,
            reserve_activation_digest="0" * 64,
            generation_request_digest="1" * 64,
            _factory_token=object(),
        )
