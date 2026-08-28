"""D02-R2 Epoch 02 reserve activation and per-call request authority.

The accepted E1 capability remains immutable with reserve state disabled.  This
module proves the four frozen activation predicates for the E2-only reserve
tranche and never performs network or filesystem I/O.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, NoReturn, cast

from mirror_api.demo_d02_r2_generation_capability import (
    build_generation_capability_authority,
    validate_generation_capability_authority,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class D02R2Epoch2GenerationError(ValueError):
    """An E2 reserve, allocation, request, or lease invariant failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _fail(code: str, message: str) -> NoReturn:
    raise D02R2Epoch2GenerationError(code, message)


EPOCH2_PLAN_PATH: Final = "docs/operations/P3_P7_D02_R2_EXECUTION_EPOCH_02.md"
EPOCH2_PLAN_SHA: Final = "3d3ce14556de8240cfb913a85bec2aaa8052aeae"
EPOCH2_PLAN_TREE: Final = "8632ea833b8b50afb90a4df39d22ea7f56c6d5d3"
EPOCH2_PLAN_FILE_SHA256: Final = "0c0b70d13329ca1c96eec18ddfb93d61ba573f98f8a83aa34518fc643fb6ff8c"
ACCEPTED_CAPABILITY_DIGEST: Final = (
    "891988bd0abe14c0c83c6750d63c36029b65053041049f1892819d75272b2696"
)

E1_ROOT_RECEIPT_DIGEST: Final = "c3ae43887d51d15347153e392ca092866dff890bdcda959572cc1dd07e6195c4"
E1_EXECUTION_CONTRACT_DIGEST: Final = (
    "d362c3fb25303ca9e1863bdf8fc4f92edb8c044cc42751280bec26595eaca388"
)
E1_TERMINAL_HEAD_DIGEST: Final = "4792ec870f1db3b1b8b9086a477eeb6369d4bfb3f2200bf8ab48d2af13320b66"
E1_TERMINAL_SNAPSHOT_DIGEST: Final = (
    "ebba32ed2645d175d4a3ae75b6b50a3c63a3e75d9a4019ef301cc7f8e8a3e70b"
)
E1_NEGATIVE_RECEIPT_AUTHORITY_DIGEST: Final = (
    "edfb8733e6742b986c8d14d061d3ac3106c72931ed48b85a9efe2e67105bf9b9"
)
E1_TERMINAL_EVENT_COUNT: Final = 10
E1_PRODUCT_EVENT_COUNT: Final = 0
E1_ACTUAL_CALL_COUNT: Final = 1

E2_TASK_ID: Final = "P3_P7_D02_R2_EXECUTION_02"
E2_PRODUCER_TASK_ID: Final = "P3_P7_D02_R2_SOURCE_COHORT_02"
E2_PRIVATE_NAMESPACE_ID: Final = "pm-p3p7-d02-r2-cc08-e2"
E2_ROOT_ID: Final = "P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT"
E2_DISPATCH_EPOCH: Final = 2
E2_RESERVE_CALLS: Final = 4
E2_RETRY_CEILING: Final = 0
E2_CONCURRENCY: Final = 1
TOTAL_ACTUAL_CALL_CEILING: Final = 5

RESERVE_ACTIVATION_SCHEMA: Final = "mirror.demo/D02R2Epoch2ReserveActivation/v1"
GENERATION_REQUEST_SCHEMA: Final = "mirror.demo/D02R2Epoch2GenerationRequestPolicy/v1"
CONTROL_PLANE_LEASE_SCHEMA: Final = "mirror.demo/D02R2Epoch2ControlPlaneLease/v1"

_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_LEASE_FACTORY_TOKEN: Final = object()
_LEASE_STATE_LOCK: Final = threading.Lock()
_LEASE_STATES: Final[dict[int, str]] = {}
_LEASE_EPOCH_ACTIVATION_DIGEST: str | None = None


@dataclass(frozen=True, slots=True)
class E1TerminalBinding:
    root_receipt_digest: str
    execution_contract_digest: str
    terminal_head_digest: str
    terminal_snapshot_digest: str
    negative_receipt_authority_digest: str
    event_count: int
    product_event_count: int
    actual_call_count: int
    state: str


@dataclass(frozen=True, slots=True)
class Epoch2Allocation:
    candidate_ordinal: int
    source_output_id: str
    source_name_receipt_digest: str
    provenance_output_id: str
    provenance_name_receipt_digest: str
    prompt_material_digest: str


def expected_e1_terminal_binding() -> E1TerminalBinding:
    return E1TerminalBinding(
        root_receipt_digest=E1_ROOT_RECEIPT_DIGEST,
        execution_contract_digest=E1_EXECUTION_CONTRACT_DIGEST,
        terminal_head_digest=E1_TERMINAL_HEAD_DIGEST,
        terminal_snapshot_digest=E1_TERMINAL_SNAPSHOT_DIGEST,
        negative_receipt_authority_digest=E1_NEGATIVE_RECEIPT_AUTHORITY_DIGEST,
        event_count=E1_TERMINAL_EVENT_COUNT,
        product_event_count=E1_PRODUCT_EVENT_COUNT,
        actual_call_count=E1_ACTUAL_CALL_COUNT,
        state="FAILED_CLOSED",
    )


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail("E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP", f"{label} is invalid")
    return value


def _require_output_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _OUTPUT_ID_RE.fullmatch(value) is None:
        _fail("E2_OUTPUT_NAME_OR_ID_COLLISION_STOP", f"{label} is invalid")
    return value


def _require_exact_mapping(
    value: object, keys: tuple[str, ...], label: str
) -> Mapping[str, object]:
    if not isinstance(value, dict) or tuple(value) != keys:
        _fail("E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP", f"{label} keys drifted")
    return cast(Mapping[str, object], value)


def _validate_capability() -> Mapping[str, object]:
    capability = validate_generation_capability_authority(build_generation_capability_authority())
    digest = _require_digest(
        capability["generation_capability_authority_digest"],
        "accepted capability digest",
    )
    if digest != ACCEPTED_CAPABILITY_DIGEST:
        _fail("GENERATION_CAPABILITY_AUTHORITY_MISMATCH_STOP", "capability digest drifted")
    budget = capability["execution_budget"]
    if not isinstance(budget, dict):
        _fail("GENERATION_CAPABILITY_AUTHORITY_MISMATCH_STOP", "capability budget is invalid")
    if (
        budget.get("maximum_total_call_capacity") != 8
        or budget.get("reserve_call_capacity") != 4
        or budget.get("reserve_calls_authorized") != 0
        or budget.get("reserve_state") != "DISABLED"
        or budget.get("ordered_reserve_activation_requirements")
        != [
            "ACCEPTED_FORWARD_CHANGE_CONTROL",
            "NEW_DISPATCH_EPOCH",
            "NEW_OUTPUT_IDS",
            "NEW_ALLOCATIONS",
        ]
    ):
        _fail("GENERATION_CAPABILITY_AUTHORITY_MISMATCH_STOP", "reserve capacity drifted")
    return capability


def _validate_terminal(binding: E1TerminalBinding) -> None:
    expected = expected_e1_terminal_binding()
    exact = all(
        type(getattr(binding, name)) is type(getattr(expected, name))
        and getattr(binding, name) == getattr(expected, name)
        for name in E1TerminalBinding.__dataclass_fields__
    )
    if not exact:
        _fail(
            "E2_PREDECESSOR_TERMINAL_DIGEST_MISMATCH_STOP",
            "E1 terminal binding does not replay exactly",
        )


def _strict_json_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        right_mapping = cast(dict[object, object], right)
        return tuple(left) == tuple(right_mapping) and all(
            _strict_json_equal(value, right_mapping[key]) for key, value in left.items()
        )
    if isinstance(left, list):
        right_items = cast(list[object], right)
        return len(left) == len(right_items) and all(
            _strict_json_equal(value, right_value)
            for value, right_value in zip(left, right_items, strict=True)
        )
    return left == right


def _require_replayed_digest(
    authority: Mapping[str, object],
    *,
    schema: str,
    digest_key: str,
    label: str,
) -> str:
    claimed = _require_digest(authority[digest_key], f"{label} digest")
    payload = cast(
        JsonObject,
        {key: value for key, value in authority.items() if key != digest_key},
    )
    try:
        observed = mirror_demo_digest(schema, payload)
    except (TypeError, ValueError) as error:
        raise D02R2Epoch2GenerationError(
            "E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP",
            f"{label} is not canonical JSON",
        ) from error
    if observed != claimed:
        _fail(
            "E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP",
            f"{label} digest does not replay",
        )
    return claimed


def _allocation_payload(allocation: Epoch2Allocation) -> JsonObject:
    if type(allocation.candidate_ordinal) is not int or allocation.candidate_ordinal not in {
        1,
        2,
        3,
        4,
    }:
        _fail("E2_CALL_CEILING_STOP", "candidate ordinal is outside E2")
    return {
        "candidate_ordinal": allocation.candidate_ordinal,
        "source_output_id": _require_output_id(allocation.source_output_id, "source output ID"),
        "source_name_receipt_digest": _require_digest(
            allocation.source_name_receipt_digest,
            "source name receipt digest",
        ),
        "provenance_output_id": _require_output_id(
            allocation.provenance_output_id,
            "provenance output ID",
        ),
        "provenance_name_receipt_digest": _require_digest(
            allocation.provenance_name_receipt_digest,
            "provenance name receipt digest",
        ),
        "prompt_material_digest": _require_digest(
            allocation.prompt_material_digest,
            "prompt material digest",
        ),
    }


def _validated_allocations(allocations: Sequence[Epoch2Allocation]) -> list[JsonValue]:
    if len(allocations) != 4:
        _fail(
            "GENERATION_RESERVE_CALL_NOT_AUTHORIZED_STOP", "exactly four allocations are required"
        )
    payloads = [_allocation_payload(item) for item in allocations]
    if [item["candidate_ordinal"] for item in payloads] != [1, 2, 3, 4]:
        _fail("E2_CALL_CEILING_STOP", "allocations must be ordered ordinals 1 through 4")
    output_ids = [
        cast(str, item[key])
        for item in payloads
        for key in ("source_output_id", "provenance_output_id")
    ]
    receipt_digests = [
        cast(str, item[key])
        for item in payloads
        for key in ("source_name_receipt_digest", "provenance_name_receipt_digest")
    ]
    if len(set(output_ids)) != 8 or len(set(receipt_digests)) != 8:
        _fail("E2_OUTPUT_NAME_OR_ID_COLLISION_STOP", "E2 outputs or name receipts collide")
    return cast(list[JsonValue], payloads)


def build_reserve_activation_authority(
    *,
    terminal_binding: E1TerminalBinding,
    root_name_receipt_digest: str,
    allocations: Sequence[Epoch2Allocation],
) -> JsonObject:
    """Bind the accepted capability, exact E1 terminal state, and all new E2 allocations."""

    _validate_capability()
    _validate_terminal(terminal_binding)
    payload: JsonObject = {
        "schema_version": RESERVE_ACTIVATION_SCHEMA,
        "authority_id": "P3_P7_D02_R2_EPOCH_02_RESERVE_ACTIVATION_01",
        "accepted_capability_digest": ACCEPTED_CAPABILITY_DIGEST,
        "accepted_e2_plan_sha": EPOCH2_PLAN_SHA,
        "accepted_e2_plan_tree": EPOCH2_PLAN_TREE,
        "accepted_e2_plan_file_sha256": EPOCH2_PLAN_FILE_SHA256,
        "e1_terminal_head_digest": terminal_binding.terminal_head_digest,
        "e1_terminal_event_count": terminal_binding.event_count,
        "e1_actual_call_count": terminal_binding.actual_call_count,
        "e2_dispatch_epoch": E2_DISPATCH_EPOCH,
        "e2_root_id": E2_ROOT_ID,
        "e2_root_name_receipt_digest": _require_digest(
            root_name_receipt_digest,
            "E2 root name receipt digest",
        ),
        "e2_task_id": E2_TASK_ID,
        "e2_producer_task_id": E2_PRODUCER_TASK_ID,
        "e2_private_namespace_id": E2_PRIVATE_NAMESPACE_ID,
        "reserve_calls_authorized": E2_RESERVE_CALLS,
        "retry_ceiling": E2_RETRY_CEILING,
        "concurrency": E2_CONCURRENCY,
        "total_actual_call_ceiling": TOTAL_ACTUAL_CALL_CEILING,
        "allocations": _validated_allocations(allocations),
        "egress_lease_policy": "DEFAULT_DENY_SINGLE_USE_ORDINAL_SCOPED_FINALLY_REVOKED",
        "activation_state": "ACTIVATED_FOR_E2_ONLY",
    }
    payload["reserve_activation_digest"] = mirror_demo_digest(
        RESERVE_ACTIVATION_SCHEMA,
        payload,
    )
    return payload


def validate_reserve_activation_authority(value: object) -> Mapping[str, object]:
    keys = (
        "schema_version",
        "authority_id",
        "accepted_capability_digest",
        "accepted_e2_plan_sha",
        "accepted_e2_plan_tree",
        "accepted_e2_plan_file_sha256",
        "e1_terminal_head_digest",
        "e1_terminal_event_count",
        "e1_actual_call_count",
        "e2_dispatch_epoch",
        "e2_root_id",
        "e2_root_name_receipt_digest",
        "e2_task_id",
        "e2_producer_task_id",
        "e2_private_namespace_id",
        "reserve_calls_authorized",
        "retry_ceiling",
        "concurrency",
        "total_actual_call_ceiling",
        "allocations",
        "egress_lease_policy",
        "activation_state",
        "reserve_activation_digest",
    )
    authority = _require_exact_mapping(value, keys, "reserve activation")
    _require_replayed_digest(
        authority,
        schema=RESERVE_ACTIVATION_SCHEMA,
        digest_key="reserve_activation_digest",
        label="reserve activation",
    )
    allocations_value = authority["allocations"]
    if not isinstance(allocations_value, list):
        _fail("E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP", "allocations are invalid")
    allocations: list[Epoch2Allocation] = []
    for item in allocations_value:
        item_map = _require_exact_mapping(
            item,
            (
                "candidate_ordinal",
                "source_output_id",
                "source_name_receipt_digest",
                "provenance_output_id",
                "provenance_name_receipt_digest",
                "prompt_material_digest",
            ),
            "allocation",
        )
        ordinal = item_map["candidate_ordinal"]
        if type(ordinal) is not int:
            _fail("E2_CALL_CEILING_STOP", "allocation ordinal is invalid")
        allocations.append(
            Epoch2Allocation(
                candidate_ordinal=ordinal,
                source_output_id=cast(str, item_map["source_output_id"]),
                source_name_receipt_digest=cast(str, item_map["source_name_receipt_digest"]),
                provenance_output_id=cast(str, item_map["provenance_output_id"]),
                provenance_name_receipt_digest=cast(
                    str,
                    item_map["provenance_name_receipt_digest"],
                ),
                prompt_material_digest=cast(str, item_map["prompt_material_digest"]),
            )
        )
    rebuilt = build_reserve_activation_authority(
        terminal_binding=expected_e1_terminal_binding(),
        root_name_receipt_digest=_require_digest(
            authority["e2_root_name_receipt_digest"],
            "E2 root name receipt digest",
        ),
        allocations=allocations,
    )
    if not _strict_json_equal(dict(authority), rebuilt):
        _fail("E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP", "reserve activation drifted")
    return authority


def build_generation_request(
    *,
    reserve_activation: Mapping[str, object],
    generation_preregistration_digest: str,
    candidate_ordinal: int,
) -> JsonObject:
    activation = validate_reserve_activation_authority(dict(reserve_activation))
    allocations = cast(list[object], activation["allocations"])
    if type(candidate_ordinal) is not int or candidate_ordinal not in {1, 2, 3, 4}:
        _fail("E2_CALL_CEILING_STOP", "candidate ordinal is outside E2")
    allocation = cast(dict[str, JsonValue], allocations[candidate_ordinal - 1])
    request: JsonObject = {
        "schema_version": GENERATION_REQUEST_SCHEMA,
        "reserve_activation_digest": _require_digest(
            activation["reserve_activation_digest"],
            "reserve activation digest",
        ),
        "generation_capability_authority_digest": ACCEPTED_CAPABILITY_DIGEST,
        "generation_preregistration_digest": _require_digest(
            generation_preregistration_digest,
            "generation preregistration digest",
        ),
        "e2_root_id": E2_ROOT_ID,
        "e2_root_name_receipt_digest": _require_digest(
            activation["e2_root_name_receipt_digest"],
            "E2 root name receipt digest",
        ),
        "producer_task_id": E2_PRODUCER_TASK_ID,
        "dispatch_epoch": E2_DISPATCH_EPOCH,
        "candidate_ordinal": candidate_ordinal,
        "source_output_id": allocation["source_output_id"],
        "source_name_receipt_digest": allocation["source_name_receipt_digest"],
        "provenance_output_id": allocation["provenance_output_id"],
        "provenance_name_receipt_digest": allocation["provenance_name_receipt_digest"],
        "prompt_material_digest": allocation["prompt_material_digest"],
        "requested_call_count": 1,
        "retry_ceiling": 0,
        "concurrency": 1,
        "source_expected_media_type": "image/png",
        "source_maximum_bytes": 20_971_520,
        "request_state": "AUTHORIZED_E2_RESERVE_CREATE_NEW_ONLY",
    }
    request["generation_request_digest"] = mirror_demo_digest(
        GENERATION_REQUEST_SCHEMA,
        request,
    )
    return request


def validate_generation_request(
    value: object,
    *,
    reserve_activation: Mapping[str, object],
) -> Mapping[str, object]:
    keys = (
        "schema_version",
        "reserve_activation_digest",
        "generation_capability_authority_digest",
        "generation_preregistration_digest",
        "e2_root_id",
        "e2_root_name_receipt_digest",
        "producer_task_id",
        "dispatch_epoch",
        "candidate_ordinal",
        "source_output_id",
        "source_name_receipt_digest",
        "provenance_output_id",
        "provenance_name_receipt_digest",
        "prompt_material_digest",
        "requested_call_count",
        "retry_ceiling",
        "concurrency",
        "source_expected_media_type",
        "source_maximum_bytes",
        "request_state",
        "generation_request_digest",
    )
    request = _require_exact_mapping(value, keys, "generation request")
    _require_replayed_digest(
        request,
        schema=GENERATION_REQUEST_SCHEMA,
        digest_key="generation_request_digest",
        label="generation request",
    )
    ordinal = request["candidate_ordinal"]
    if type(ordinal) is not int:
        _fail("E2_CALL_CEILING_STOP", "request ordinal is invalid")
    rebuilt = build_generation_request(
        reserve_activation=reserve_activation,
        generation_preregistration_digest=_require_digest(
            request["generation_preregistration_digest"],
            "generation preregistration digest",
        ),
        candidate_ordinal=ordinal,
    )
    if not _strict_json_equal(dict(request), rebuilt):
        _fail("E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP", "generation request drifted")
    return request


@dataclass(slots=True, init=False)
class OrdinalControlPlaneLease:
    """One in-memory, single-use lease that always returns to default deny."""

    candidate_ordinal: int
    reserve_activation_digest: str
    generation_request_digest: str
    _active: bool = field(default=False, init=False, repr=False)
    _used: bool = field(default=False, init=False, repr=False)
    _lease_key: int = field(init=False, repr=False)

    def __init__(
        self,
        *,
        candidate_ordinal: int,
        reserve_activation_digest: str,
        generation_request_digest: str,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _LEASE_FACTORY_TOKEN:
            _fail(
                "GENERATION_RESERVE_CALL_NOT_AUTHORIZED_STOP",
                "control-plane leases must come from a validated request",
            )
        object.__setattr__(self, "candidate_ordinal", candidate_ordinal)
        object.__setattr__(self, "reserve_activation_digest", reserve_activation_digest)
        object.__setattr__(self, "generation_request_digest", generation_request_digest)
        object.__setattr__(self, "_active", False)
        object.__setattr__(self, "_used", False)
        object.__setattr__(self, "_lease_key", candidate_ordinal)

    @property
    def active(self) -> bool:
        return self._active

    @property
    def used(self) -> bool:
        return self._used

    def __enter__(self) -> OrdinalControlPlaneLease:
        with _LEASE_STATE_LOCK:
            if self._used or self._active or _LEASE_STATES.get(self._lease_key) != "RESERVED":
                _fail("E2_CALL_CEILING_STOP", "control-plane lease is not reusable")
            _LEASE_STATES[self._lease_key] = "ACTIVE"
            self._used = True
            self._active = True
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        with _LEASE_STATE_LOCK:
            self._active = False
            _LEASE_STATES[self._lease_key] = "REVOKED"

    def assert_revoked(self) -> None:
        with _LEASE_STATE_LOCK:
            state = _LEASE_STATES.get(self._lease_key)
        if self._active or state != "REVOKED":
            _fail("E2_FORWARD_AUTHORITY_MISSING_OR_MISMATCH_STOP", "egress lease remains active")


def acquire_ordinal_control_plane_lease(
    *,
    reserve_activation: Mapping[str, object],
    generation_request: Mapping[str, object],
) -> OrdinalControlPlaneLease:
    global _LEASE_EPOCH_ACTIVATION_DIGEST

    activation = validate_reserve_activation_authority(dict(reserve_activation))
    request = validate_generation_request(
        dict(generation_request),
        reserve_activation=activation,
    )
    activation_digest = _require_digest(
        activation["reserve_activation_digest"],
        "reserve activation digest",
    )
    request_activation_digest = _require_digest(
        request["reserve_activation_digest"],
        "request reserve activation digest",
    )
    if request_activation_digest != activation_digest:
        _fail(
            "GENERATION_RESERVE_CALL_NOT_AUTHORIZED_STOP",
            "request is not bound to the accepted reserve activation",
        )
    ordinal = request["candidate_ordinal"]
    if type(ordinal) is not int or ordinal not in {1, 2, 3, 4}:
        _fail("E2_CALL_CEILING_STOP", "lease ordinal is outside E2")
    with _LEASE_STATE_LOCK:
        if _LEASE_EPOCH_ACTIVATION_DIGEST is None:
            _LEASE_EPOCH_ACTIVATION_DIGEST = activation_digest
        elif _LEASE_EPOCH_ACTIVATION_DIGEST != activation_digest:
            _fail(
                "GENERATION_RESERVE_CALL_NOT_AUTHORIZED_STOP",
                "reserve activation differs from the frozen E2 epoch authority",
            )
        if ordinal in _LEASE_STATES:
            _fail("E2_CALL_CEILING_STOP", "E2 ordinal has already been consumed")
        _LEASE_STATES[ordinal] = "RESERVED"
    return OrdinalControlPlaneLease(
        candidate_ordinal=ordinal,
        reserve_activation_digest=activation_digest,
        generation_request_digest=_require_digest(
            request["generation_request_digest"],
            "generation request digest",
        ),
        _factory_token=_LEASE_FACTORY_TOKEN,
    )
