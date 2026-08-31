"""E3 durable source-generation and terminal-normalization receipts.

The source receipt is the public projection consumed by source authority and
PostgreSQL admission.  The terminal receipt additionally proves that the same
PNG was deterministically normalized and bound to a durable source descriptor.
Neither schema carries a path, locator, Prompt, credential, or raw image byte.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, NoReturn, cast

from mirror_api.demo_d02_r2_generation_e3 import (
    E3_CONTEXT,
    Epoch3GenerationError,
    GenerationExecutionContext,
    validate_epoch3_generation_contract,
    validate_epoch3_source_policy_profile,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

SOURCE_GENERATION_RECEIPT_SCHEMA: Final = E3_CONTEXT.source_generation_receipt_schema
TERMINAL_SOURCE_RECEIPT_SCHEMA: Final = E3_CONTEXT.terminal_source_receipt_schema
PROMPT_POLICY_VERSION: Final = "project-mirror-synthetic-face-generation-v2"
E3_TERMINAL_SUCCESS: Final = "SUCCEEDED_DURABLE_PNG_AND_NORMALIZED_JPEG"
E3_TERMINAL_FAILURE: Final = "FAILED_CLOSED_ORDINAL_CONSUMED"

SOURCE_GENERATION_RECEIPT_KEYS: Final = (
    "schema_version",
    "candidate_ordinal",
    "producer_task_id",
    "source_producer_task_id",
    "dispatch_epoch",
    "execution_contract_digest",
    "evidence_root_id",
    "root_name_receipt_digest",
    "generation_preregistration_digest",
    "source_allocation_manifest_digest",
    "source_producer_dispatch_digest",
    "source_output_id",
    "source_policy_profile",
    "output_name_receipt_digest",
    "output_seal_receipt_digest",
    "registry_commit_receipt_digest",
    "generation_capability_authority_digest",
    "generation_request_policy_digest",
    "generation_result_provenance_digest",
    "source_provenance_output_id",
    "source_provenance_name_receipt_digest",
    "source_provenance_seal_receipt_digest",
    "source_provenance_registry_commit_receipt_digest",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "synthetic_only_attested",
    "real_person_reference_used",
    "receipt_digest",
)
_TERMINAL_RECEIPT_KEYS: Final = (
    "schema_version",
    "contract_digest",
    "source_generation_receipt_digest",
    "root_id",
    "ordinal",
    "terminal_state",
    "source_output_id",
    "provenance_output_id",
    "normalized_jpeg_output_id",
    "source_policy_profile_digest",
    "png_sha256",
    "png_byte_size",
    "png_width",
    "png_height",
    "png_media_type",
    "jpeg_sha256",
    "jpeg_byte_size",
    "jpeg_width",
    "jpeg_height",
    "jpeg_media_type",
    "normalization_receipt_digest",
    "durable_source_descriptor_digest",
    "prompt_material_digest",
    "prompt_policy_version",
    "receipt_digest",
)


def _fail(message: str) -> NoReturn:
    raise Epoch3GenerationError(message)


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        _fail(f"{label} must be a positive integer")
    return value


def _output_id(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or not value[0].isalnum()
        or any(not (character.isalnum() or character in "._-") for character in value)
    ):
        _fail(f"{label} must be an opaque output ID")
    return value


def _exact(value: object, *, keys: tuple[str, ...], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or tuple(value) != keys:
        _fail(f"{label} keys or key order are not exact")
    return cast(Mapping[str, object], value)


def _allocation(
    contract: Mapping[str, object], ordinal: int, *, context: GenerationExecutionContext
) -> Mapping[str, object]:
    allocations = contract["allocations"]
    if not isinstance(allocations, list):
        _fail(f"{context.cohort_label} contract allocations are invalid")
    allocation = allocations[ordinal - 1]
    if not isinstance(allocation, Mapping):
        _fail(f"{context.cohort_label} allocation is invalid")
    return cast(Mapping[str, object], allocation)


def build_epoch3_source_generation_receipt(
    *,
    contract: Mapping[str, object],
    ordinal: int,
    root_name_receipt_digest: str,
    generation_preregistration_digest: str,
    source_allocation_manifest_digest: str,
    source_producer_dispatch_digest: str,
    output_name_receipt_digest: str,
    output_seal_receipt_digest: str,
    registry_commit_receipt_digest: str,
    generation_capability_authority_digest: str,
    generation_request_digest: str,
    generation_result_provenance_digest: str,
    source_provenance_name_receipt_digest: str,
    source_provenance_seal_receipt_digest: str,
    source_provenance_registry_commit_receipt_digest: str,
    source_asset_sha256: str,
    source_asset_byte_size: int,
    source_asset_width: int,
    source_asset_height: int,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> JsonObject:
    """Build the raw PNG receipt after source and provenance are durable."""

    verified = validate_epoch3_generation_contract(contract, context=context)
    if type(ordinal) is not int or ordinal not in range(1, 5):
        _fail(f"{context.cohort_label} source receipt ordinal is invalid")
    allocation = _allocation(verified, ordinal, context=context)
    payload: JsonObject = {
        "schema_version": context.source_generation_receipt_schema,
        "candidate_ordinal": ordinal,
        "producer_task_id": context.task_id,
        "source_producer_task_id": context.producer_task_id,
        "dispatch_epoch": context.dispatch_epoch,
        "execution_contract_digest": cast(JsonScalar, verified["contract_digest"]),
        "evidence_root_id": context.root_id,
        "root_name_receipt_digest": _digest(root_name_receipt_digest, "root name receipt digest"),
        "generation_preregistration_digest": _digest(
            generation_preregistration_digest,
            "generation preregistration digest",
        ),
        "source_allocation_manifest_digest": _digest(
            source_allocation_manifest_digest,
            "source allocation manifest digest",
        ),
        "source_producer_dispatch_digest": _digest(
            source_producer_dispatch_digest, "source producer dispatch digest"
        ),
        "source_output_id": _output_id(allocation["source_output_id"], "source output ID"),
        "source_policy_profile": cast(
            JsonValue,
            dict(
                validate_epoch3_source_policy_profile(
                    allocation["source_policy_profile"], ordinal=ordinal, context=context
                )
            ),
        ),
        "output_name_receipt_digest": _digest(
            output_name_receipt_digest, "source name receipt digest"
        ),
        "output_seal_receipt_digest": _digest(
            output_seal_receipt_digest, "source seal receipt digest"
        ),
        "registry_commit_receipt_digest": _digest(
            registry_commit_receipt_digest, "source registry receipt digest"
        ),
        "generation_capability_authority_digest": _digest(
            generation_capability_authority_digest,
            "generation capability authority digest",
        ),
        "generation_request_policy_digest": _digest(
            generation_request_digest, "generation request digest"
        ),
        "generation_result_provenance_digest": _digest(
            generation_result_provenance_digest,
            "generation result provenance digest",
        ),
        "source_provenance_output_id": _output_id(
            allocation["provenance_output_id"], "source provenance output ID"
        ),
        "source_provenance_name_receipt_digest": _digest(
            source_provenance_name_receipt_digest,
            "provenance name receipt digest",
        ),
        "source_provenance_seal_receipt_digest": _digest(
            source_provenance_seal_receipt_digest,
            "provenance seal receipt digest",
        ),
        "source_provenance_registry_commit_receipt_digest": _digest(
            source_provenance_registry_commit_receipt_digest,
            "provenance registry receipt digest",
        ),
        "source_asset_sha256": _digest(source_asset_sha256, "source PNG digest"),
        "source_asset_byte_size": _positive_int(source_asset_byte_size, "source PNG byte size"),
        "source_asset_mime_type": "image/png",
        "source_asset_width": _positive_int(source_asset_width, "source PNG width"),
        "source_asset_height": _positive_int(source_asset_height, "source PNG height"),
        "synthetic_only_attested": True,
        "real_person_reference_used": False,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = mirror_demo_digest(
        context.source_generation_receipt_schema,
        {key: value for key, value in payload.items() if key != "receipt_digest"},
    )
    return payload


def validate_epoch3_source_generation_receipt(
    value: object,
    *,
    contract: Mapping[str, object] | None = None,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> Mapping[str, object]:
    receipt = _exact(
        value,
        keys=SOURCE_GENERATION_RECEIPT_KEYS,
        label=f"{context.cohort_label} source generation receipt",
    )
    if (
        receipt["schema_version"] != context.source_generation_receipt_schema
        or receipt["producer_task_id"] != context.task_id
        or receipt["source_producer_task_id"] != context.producer_task_id
        or receipt["dispatch_epoch"] != context.dispatch_epoch
        or receipt["evidence_root_id"] != context.root_id
        or receipt["source_asset_mime_type"] != "image/png"
        or receipt["synthetic_only_attested"] is not True
        or receipt["real_person_reference_used"] is not False
    ):
        if context == E3_CONTEXT:
            _fail("E2 or unknown source generation receipt is rejected")
        _fail(f"foreign source generation receipt is rejected by {context.cohort_label}")
    ordinal = receipt["candidate_ordinal"]
    if type(ordinal) is not int or ordinal not in range(1, 5):
        _fail(f"{context.cohort_label} source receipt ordinal is invalid")
    _output_id(receipt["source_output_id"], "source output ID")
    _output_id(receipt["source_provenance_output_id"], "source provenance output ID")
    validate_epoch3_source_policy_profile(
        receipt["source_policy_profile"], ordinal=ordinal, context=context
    )
    for key in SOURCE_GENERATION_RECEIPT_KEYS:
        if key.endswith("digest"):
            _digest(receipt[key], key)
    for key in (
        "source_asset_byte_size",
        "source_asset_width",
        "source_asset_height",
    ):
        _positive_int(receipt[key], key)
    expected_digest = mirror_demo_digest(
        context.source_generation_receipt_schema,
        cast(
            Mapping[str, JsonValue],
            {key: item for key, item in receipt.items() if key != "receipt_digest"},
        ),
    )
    if receipt["receipt_digest"] != expected_digest:
        _fail(f"{context.cohort_label} source generation receipt digest does not replay")
    if contract is not None:
        verified = validate_epoch3_generation_contract(contract, context=context)
        allocation = _allocation(verified, ordinal, context=context)
        if (
            receipt["execution_contract_digest"] != verified["contract_digest"]
            or receipt["source_output_id"] != allocation["source_output_id"]
            or receipt["source_provenance_output_id"] != allocation["provenance_output_id"]
            or receipt["source_policy_profile"] != allocation["source_policy_profile"]
        ):
            _fail(f"{context.cohort_label} source receipt differs from its allocation")
    return receipt


def build_epoch3_terminal_source_receipt(
    *,
    contract: Mapping[str, object],
    generation_receipt: Mapping[str, object],
    terminal_state: str,
    jpeg_sha256: str,
    jpeg_byte_size: int,
    jpeg_width: int,
    jpeg_height: int,
    normalization_receipt_digest: str,
    durable_source_descriptor_digest: str,
    prompt_material_digest: str,
    context: GenerationExecutionContext = E3_CONTEXT,
) -> JsonObject:
    """Bind raw generation, normalization, and descriptor before success."""

    verified_contract = validate_epoch3_generation_contract(contract, context=context)
    source = validate_epoch3_source_generation_receipt(
        generation_receipt, contract=verified_contract, context=context
    )
    if terminal_state != E3_TERMINAL_SUCCESS:
        _fail(f"success receipt requires the {context.cohort_label} success terminal state")
    ordinal = cast(int, source["candidate_ordinal"])
    allocation = _allocation(verified_contract, ordinal, context=context)
    width = _positive_int(jpeg_width, "JPEG width")
    height = _positive_int(jpeg_height, "JPEG height")
    if width != source["source_asset_width"] or height != source["source_asset_height"]:
        _fail("JPEG normalization dimensions must bind the received PNG")
    payload: JsonObject = {
        "schema_version": context.terminal_source_receipt_schema,
        "contract_digest": cast(JsonScalar, verified_contract["contract_digest"]),
        "source_generation_receipt_digest": cast(JsonScalar, source["receipt_digest"]),
        "root_id": context.root_id,
        "ordinal": ordinal,
        "terminal_state": terminal_state,
        "source_output_id": cast(JsonScalar, source["source_output_id"]),
        "provenance_output_id": cast(JsonScalar, source["source_provenance_output_id"]),
        "normalized_jpeg_output_id": cast(JsonScalar, allocation["normalized_jpeg_output_id"]),
        "source_policy_profile_digest": cast(
            JsonScalar,
            cast(Mapping[str, object], allocation["source_policy_profile"])["profile_digest"],
        ),
        "png_sha256": cast(JsonScalar, source["source_asset_sha256"]),
        "png_byte_size": cast(JsonScalar, source["source_asset_byte_size"]),
        "png_width": cast(JsonScalar, source["source_asset_width"]),
        "png_height": cast(JsonScalar, source["source_asset_height"]),
        "png_media_type": "image/png",
        "jpeg_sha256": _digest(jpeg_sha256, "JPEG digest"),
        "jpeg_byte_size": _positive_int(jpeg_byte_size, "JPEG byte size"),
        "jpeg_width": width,
        "jpeg_height": height,
        "jpeg_media_type": "image/jpeg",
        "normalization_receipt_digest": _digest(
            normalization_receipt_digest, "normalization receipt digest"
        ),
        "durable_source_descriptor_digest": _digest(
            durable_source_descriptor_digest, "durable source descriptor digest"
        ),
        "prompt_material_digest": _digest(prompt_material_digest, "prompt material digest"),
        "prompt_policy_version": PROMPT_POLICY_VERSION,
        "receipt_digest": "",
    }
    payload["receipt_digest"] = mirror_demo_digest(
        context.terminal_source_receipt_schema,
        {key: value for key, value in payload.items() if key != "receipt_digest"},
    )
    return payload


def validate_epoch3_terminal_source_receipt(
    value: object,
    *,
    contract: Mapping[str, object],
    generation_receipt: Mapping[str, object],
    context: GenerationExecutionContext = E3_CONTEXT,
) -> Mapping[str, object]:
    receipt = _exact(
        value,
        keys=_TERMINAL_RECEIPT_KEYS,
        label=f"{context.cohort_label} terminal source receipt",
    )
    if receipt["schema_version"] != context.terminal_source_receipt_schema:
        if context == E3_CONTEXT:
            _fail("E2 or unknown terminal source receipt is rejected")
        _fail(f"foreign terminal source receipt is rejected by {context.cohort_label}")
    rebuilt = build_epoch3_terminal_source_receipt(
        contract=contract,
        generation_receipt=generation_receipt,
        terminal_state=cast(str, receipt["terminal_state"]),
        jpeg_sha256=_digest(receipt["jpeg_sha256"], "JPEG digest"),
        jpeg_byte_size=_positive_int(receipt["jpeg_byte_size"], "JPEG byte size"),
        jpeg_width=_positive_int(receipt["jpeg_width"], "JPEG width"),
        jpeg_height=_positive_int(receipt["jpeg_height"], "JPEG height"),
        normalization_receipt_digest=_digest(
            receipt["normalization_receipt_digest"],
            "normalization receipt digest",
        ),
        durable_source_descriptor_digest=_digest(
            receipt["durable_source_descriptor_digest"],
            "durable source descriptor digest",
        ),
        prompt_material_digest=_digest(receipt["prompt_material_digest"], "prompt material digest"),
        context=context,
    )
    if dict(receipt) != rebuilt:
        _fail(f"{context.cohort_label} terminal source receipt does not replay")
    return receipt


@dataclass(frozen=True)
class Epoch3SequenceState:
    """Any terminal failure consumes its ordinal and stops the E3 cohort."""

    contract_digest: str
    context: GenerationExecutionContext = E3_CONTEXT
    completed_ordinals: tuple[int, ...] = ()
    failed_ordinal: int | None = None

    @classmethod
    def begin(
        cls,
        contract: Mapping[str, object],
        *,
        context: GenerationExecutionContext = E3_CONTEXT,
    ) -> Epoch3SequenceState:
        verified = validate_epoch3_generation_contract(contract, context=context)
        return cls(contract_digest=cast(str, verified["contract_digest"]), context=context)

    def next_ordinal(self) -> int:
        if self.failed_ordinal is not None:
            _fail(f"{self.context.cohort_label} cohort is failed closed")
        ordinal = len(self.completed_ordinals) + 1
        if ordinal > 4:
            _fail(f"{self.context.cohort_label} cohort has no remaining primary call")
        return ordinal

    def record_success(
        self,
        receipt: Mapping[str, object],
        *,
        contract: Mapping[str, object],
        generation_receipt: Mapping[str, object],
    ) -> Epoch3SequenceState:
        verified = validate_epoch3_terminal_source_receipt(
            receipt,
            contract=contract,
            generation_receipt=generation_receipt,
            context=self.context,
        )
        if (
            verified["contract_digest"] != self.contract_digest
            or verified["ordinal"] != self.next_ordinal()
        ):
            _fail(f"{self.context.cohort_label} success is not the next serial ordinal")
        return Epoch3SequenceState(
            self.contract_digest,
            self.context,
            (*self.completed_ordinals, verified["ordinal"]),
        )

    def record_failure(self, *, ordinal: int) -> Epoch3SequenceState:
        if ordinal != self.next_ordinal():
            _fail(f"{self.context.cohort_label} failure must consume the next ordinal")
        return Epoch3SequenceState(
            self.contract_digest, self.context, self.completed_ordinals, ordinal
        )
