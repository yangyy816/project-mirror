"""Typed private storage receipt for deterministic synthetic geometry variants."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from .geometry_transform import GeometryTransformResult

VARIANT_STORAGE_RECEIPT_SCHEMA = "mirror.synthetic-storage/variant-receipt/v1"
_REFERENCE = re.compile(r"variant-[0-9a-f]{56}\Z")
_VERSION = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class VariantStorageWriteRequest:
    storage_reference: str
    transform_run_reference: str
    specification_digest: str
    output_policy_version: str
    result: GeometryTransformResult

    def __post_init__(self) -> None:
        if _REFERENCE.fullmatch(self.storage_reference) is None:
            raise ValueError("variant storage reference is invalid")
        if re.fullmatch(r"[0-9a-f]{32}", self.transform_run_reference) is None:
            raise ValueError("transform run reference must be opaque")
        if _SHA256.fullmatch(self.specification_digest) is None:
            raise ValueError("variant specification digest is invalid")
        if _VERSION.fullmatch(self.output_policy_version) is None:
            raise ValueError("variant output policy version is invalid")


@dataclass(frozen=True)
class VariantStoredImage:
    storage_reference: str
    storage_key: str
    transform_run_reference: str
    specification_digest: str
    sha256: str
    byte_size: int
    width: int
    height: int
    changed_pixel_count: int
    runtime_version: str
    runtime_manifest_digest: str
    warp_plan_digest: str
    output_policy_version: str
    receipt_digest: str
    media_type: Literal["image/jpeg"] = "image/jpeg"
    schema_version: str = VARIANT_STORAGE_RECEIPT_SCHEMA

    @classmethod
    def create(
        cls,
        *,
        storage_reference: str,
        storage_key: str,
        transform_run_reference: str,
        specification_digest: str,
        result: GeometryTransformResult,
        output_policy_version: str,
    ) -> VariantStoredImage:
        facts: dict[str, object] = {
            "byte_size": len(result.content),
            "changed_pixel_count": result.changed_pixel_count,
            "height": result.height,
            "media_type": result.media_type,
            "output_policy_version": output_policy_version,
            "runtime_manifest_digest": result.runtime_manifest_digest,
            "runtime_version": result.runtime_version,
            "sha256": result.sha256,
            "specification_digest": specification_digest,
            "storage_key": storage_key,
            "storage_reference": storage_reference,
            "transform_run_reference": transform_run_reference,
            "warp_plan_digest": result.warp_plan_digest,
            "width": result.width,
        }
        return cls(
            storage_reference=storage_reference,
            storage_key=storage_key,
            transform_run_reference=transform_run_reference,
            specification_digest=specification_digest,
            sha256=result.sha256,
            byte_size=len(result.content),
            width=result.width,
            height=result.height,
            changed_pixel_count=result.changed_pixel_count,
            runtime_version=result.runtime_version,
            runtime_manifest_digest=result.runtime_manifest_digest,
            warp_plan_digest=result.warp_plan_digest,
            output_policy_version=output_policy_version,
            receipt_digest=_digest_facts(facts),
        )

    def __post_init__(self) -> None:
        if self.schema_version != VARIANT_STORAGE_RECEIPT_SCHEMA:
            raise ValueError("variant receipt schema is unsupported")
        if _REFERENCE.fullmatch(self.storage_reference) is None:
            raise ValueError("variant storage reference is invalid")
        if re.fullmatch(r"internal-synthetic/v1/variants/[0-9a-f]{64}", self.storage_key) is None:
            raise ValueError("variant storage key is outside the private namespace")
        if re.fullmatch(r"[0-9a-f]{32}", self.transform_run_reference) is None:
            raise ValueError("transform run reference must be opaque")
        for digest in (
            self.specification_digest,
            self.sha256,
            self.runtime_manifest_digest,
            self.warp_plan_digest,
            self.receipt_digest,
        ):
            if _SHA256.fullmatch(digest) is None:
                raise ValueError("variant receipt digest is invalid")
        if self.media_type != "image/jpeg" or any(
            type(value) is not int or value <= 0
            for value in (
                self.byte_size,
                self.width,
                self.height,
                self.changed_pixel_count,
            )
        ):
            raise ValueError("variant receipt image facts are invalid")
        if self.changed_pixel_count > self.width * self.height:
            raise ValueError("variant changed-pixel count exceeds image bounds")
        if _VERSION.fullmatch(self.output_policy_version) is None:
            raise ValueError("variant output policy version is invalid")
        if self.receipt_digest != variant_receipt_digest(self):
            raise ValueError("variant receipt digest does not match its facts")


def variant_receipt_digest(receipt: VariantStoredImage) -> str:
    facts = {
        "byte_size": receipt.byte_size,
        "changed_pixel_count": receipt.changed_pixel_count,
        "height": receipt.height,
        "media_type": receipt.media_type,
        "output_policy_version": receipt.output_policy_version,
        "runtime_manifest_digest": receipt.runtime_manifest_digest,
        "runtime_version": receipt.runtime_version,
        "sha256": receipt.sha256,
        "specification_digest": receipt.specification_digest,
        "storage_key": receipt.storage_key,
        "storage_reference": receipt.storage_reference,
        "transform_run_reference": receipt.transform_run_reference,
        "warp_plan_digest": receipt.warp_plan_digest,
        "width": receipt.width,
    }
    return _digest_facts(facts)


def _digest_facts(facts: dict[str, object]) -> str:
    canonical = json.dumps(
        facts, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(f"{VARIANT_STORAGE_RECEIPT_SCHEMA}\n{canonical}".encode()).hexdigest()


class VariantStorageProvider(Protocol):
    async def store_variant_if_absent(
        self, *, request: VariantStorageWriteRequest
    ) -> VariantStoredImage: ...

    async def inspect_variant(self, *, storage_reference: str) -> VariantStoredImage | None: ...

    def stream_variant(self, *, storage_reference: str) -> AsyncIterator[bytes]: ...

    async def delete_variant(
        self, *, storage_reference: str
    ) -> Literal["deleted", "not_found"]: ...


class CanonicalSyntheticAssetReader(Protocol):
    def stream_canonical_asset(self, *, storage_key: str) -> AsyncIterator[bytes]: ...
