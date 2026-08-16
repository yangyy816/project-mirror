from __future__ import annotations

import hashlib
import io
import re
import warnings
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal, Protocol

from PIL import Image, UnidentifiedImageError

from mirror_api.providers.base import (
    GeneratedImagePayload,
    OfflineSyntheticSourceProvenanceFact,
    SyntheticOutputSpecification,
    SyntheticStorageWriteRequest,
    SyntheticStoredImage,
)

_REFERENCE = re.compile(r"[a-z][a-z0-9_-]{2,63}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MEDIA_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class CodexNativeAdmissionRejected(ValueError):
    """A fail-closed offline admission error without paths, prompts, or image bytes."""

    def __init__(self, code: str) -> None:
        if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code) is None:
            code = "codex_native_admission_rejected"
        self.code = code
        super().__init__("Codex native synthetic source admission was rejected")


class _SyntheticRawStorage(Protocol):
    async def store_generated_image_if_absent(
        self, *, request: SyntheticStorageWriteRequest
    ) -> SyntheticStoredImage: ...


@dataclass(frozen=True)
class CodexNativeGenerationSpecification:
    schema_version: Literal["mirror.synthetic-dataset/CodexNativeGenerationSpecification/v1"]
    specification_reference: str
    specification_version: str
    generation_policy_reference: str
    prompt_template_reference: str
    prompt_digest: str
    requested_pose_reference: str
    requested_expression_reference: str
    styling_constraints_reference: str
    output_specification: SyntheticOutputSpecification
    requested_quantity: int
    max_attempts: int
    retry_ceiling: int
    concurrency_ceiling: int
    stop_condition_reference: str
    coverage_pack_reference: str | None = None
    coverage_cell_reference: str | None = None
    synthetic_only: Literal[True] = True
    real_person_reference_used: Literal[False] = False

    def __post_init__(self) -> None:
        if self.schema_version != (
            "mirror.synthetic-dataset/CodexNativeGenerationSpecification/v1"
        ):
            raise ValueError("Codex native specification schema version is not supported")
        references = (
            self.specification_reference,
            self.specification_version,
            self.generation_policy_reference,
            self.prompt_template_reference,
            self.requested_pose_reference,
            self.requested_expression_reference,
            self.styling_constraints_reference,
            self.stop_condition_reference,
        )
        optional_references = (self.coverage_pack_reference, self.coverage_cell_reference)
        if any(_REFERENCE.fullmatch(reference) is None for reference in references):
            raise ValueError("Codex native specification references must be opaque")
        if any(
            reference is not None and _REFERENCE.fullmatch(reference) is None
            for reference in optional_references
        ):
            raise ValueError("Codex native optional references must be opaque")
        if _DIGEST.fullmatch(self.prompt_digest) is None:
            raise ValueError("Codex native prompt digest must be lowercase SHA-256")
        if not 1 <= self.requested_quantity <= 24:
            raise ValueError("Codex native requested quantity exceeds the Principal boundary")
        if not self.requested_quantity <= self.max_attempts <= 36:
            raise ValueError("Codex native attempt budget is outside the bounded range")
        if not 0 <= self.retry_ceiling <= 1:
            raise ValueError("Codex native retry ceiling is outside the bounded range")
        if self.concurrency_ceiling != 1:
            raise ValueError("Codex native generation must remain serial")
        if self.synthetic_only is not True or self.real_person_reference_used is not False:
            raise ValueError("Codex native specification must exclude real-person references")


@dataclass(frozen=True)
class CodexNativeAdmissionEvidence:
    schema_version: Literal["mirror.synthetic-dataset/CodexNativeAdmissionEvidence/v1"]
    specification_reference: str
    specification_version: str
    item_reference: str
    attempt: int
    source_kind: Literal["CODEX_NATIVE_IMAGEGEN"]
    provenance_level: Literal["PROVENANCE_ONLY"]
    generation_policy_reference: str
    prompt_template_reference: str
    prompt_digest: str
    coverage_pack_reference: str | None
    coverage_cell_reference: str | None
    generated_at: datetime
    admitted_at: datetime
    sha256: str
    media_type: Literal["image/jpeg", "image/png", "image/webp"]
    byte_size: int
    width: int
    height: int
    requested_width: int
    requested_height: int
    dimensions_match_requested: bool
    storage_reference: str
    synthetic_only: Literal[True]
    real_person_reference_used: Literal[False]
    cost_accounting_mode: Literal["REQUEST_COUNT_ONLY"]
    credit_source: Literal["CODEX_NATIVE_ENTITLEMENT"]
    model_reference: None
    model_version_reference: None
    provider_request_reference: None
    provider_actual_seed: None
    provider_usage: None
    provider_cost: None

    def to_document(self) -> dict[str, object]:
        document = asdict(self)
        document["generated_at"] = self.generated_at.isoformat()
        document["admitted_at"] = self.admitted_at.isoformat()
        return document


def codex_native_raw_storage_reference(
    *, specification_reference: str, item_reference: str, sha256: str
) -> str:
    if _REFERENCE.fullmatch(specification_reference) is None:
        raise CodexNativeAdmissionRejected("invalid_specification_reference")
    if _REFERENCE.fullmatch(item_reference) is None:
        raise CodexNativeAdmissionRejected("invalid_item_reference")
    if _DIGEST.fullmatch(sha256) is None:
        raise CodexNativeAdmissionRejected("invalid_source_digest")
    digest = hashlib.sha256(
        f"codex-native:{specification_reference}:{item_reference}:{sha256}".encode()
    ).hexdigest()[:40]
    return f"native-{digest}"


class CodexNativeSourceAdmissionService:
    """Operator-only source admission; it never invokes Codex or a runtime Provider."""

    def __init__(self, *, storage: _SyntheticRawStorage, now: Callable[[], datetime]) -> None:
        self._storage = storage
        self._now = now

    async def admit(
        self,
        *,
        specification: CodexNativeGenerationSpecification,
        item_reference: str,
        attempt: int,
        generated_at: datetime,
        content: bytes,
        media_type: Literal["image/jpeg", "image/png", "image/webp"],
    ) -> CodexNativeAdmissionEvidence:
        if _REFERENCE.fullmatch(item_reference) is None:
            raise CodexNativeAdmissionRejected("invalid_item_reference")
        if attempt < 1 or attempt > 1 + specification.retry_ceiling:
            raise CodexNativeAdmissionRejected("attempt_budget_exceeded")
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise CodexNativeAdmissionRejected("invalid_generation_timestamp")
        width, height = self._validate_image(
            content=content,
            media_type=media_type,
            output=specification.output_specification,
        )
        digest = hashlib.sha256(content).hexdigest()
        storage_reference = codex_native_raw_storage_reference(
            specification_reference=specification.specification_reference,
            item_reference=item_reference,
            sha256=digest,
        )
        provenance = OfflineSyntheticSourceProvenanceFact(
            source_kind="CODEX_NATIVE_IMAGEGEN",
            provenance_level="PROVENANCE_ONLY",
            generation_policy_reference=specification.generation_policy_reference,
            prompt_template_reference=specification.prompt_template_reference,
            prompt_digest=specification.prompt_digest,
            generated_at=generated_at,
            coverage_pack_reference=specification.coverage_pack_reference,
            coverage_cell_reference=specification.coverage_cell_reference,
        )
        stored = await self._storage.store_generated_image_if_absent(
            request=SyntheticStorageWriteRequest(
                storage_reference=storage_reference,
                payload=GeneratedImagePayload(content=content, media_type=media_type),
                provenance=provenance,
            )
        )
        admitted_at = self._now()
        if admitted_at.tzinfo is None or admitted_at.utcoffset() is None:
            raise CodexNativeAdmissionRejected("invalid_admission_timestamp")
        return CodexNativeAdmissionEvidence(
            schema_version="mirror.synthetic-dataset/CodexNativeAdmissionEvidence/v1",
            specification_reference=specification.specification_reference,
            specification_version=specification.specification_version,
            item_reference=item_reference,
            attempt=attempt,
            source_kind="CODEX_NATIVE_IMAGEGEN",
            provenance_level="PROVENANCE_ONLY",
            generation_policy_reference=specification.generation_policy_reference,
            prompt_template_reference=specification.prompt_template_reference,
            prompt_digest=specification.prompt_digest,
            coverage_pack_reference=specification.coverage_pack_reference,
            coverage_cell_reference=specification.coverage_cell_reference,
            generated_at=generated_at,
            admitted_at=admitted_at,
            sha256=stored.sha256,
            media_type=stored.media_type,
            byte_size=stored.byte_size,
            width=width,
            height=height,
            requested_width=specification.output_specification.width,
            requested_height=specification.output_specification.height,
            dimensions_match_requested=(
                width == specification.output_specification.width
                and height == specification.output_specification.height
            ),
            storage_reference=stored.storage_reference,
            synthetic_only=True,
            real_person_reference_used=False,
            cost_accounting_mode="REQUEST_COUNT_ONLY",
            credit_source="CODEX_NATIVE_ENTITLEMENT",
            model_reference=None,
            model_version_reference=None,
            provider_request_reference=None,
            provider_actual_seed=None,
            provider_usage=None,
            provider_cost=None,
        )

    @staticmethod
    def _validate_image(
        *,
        content: bytes,
        media_type: Literal["image/jpeg", "image/png", "image/webp"],
        output: SyntheticOutputSpecification,
    ) -> tuple[int, int]:
        if media_type != output.media_type or not content or len(content) > output.max_byte_size:
            raise CodexNativeAdmissionRejected("source_output_mismatch")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    width, height = image.size
                    image_format = image.format
                    frame_count = getattr(image, "n_frames", 1)
                    if width * height > 40_000_000:
                        raise CodexNativeAdmissionRejected("source_pixel_limit_exceeded")
                    if frame_count != 1:
                        raise CodexNativeAdmissionRejected("source_multiframe_rejected")
                    image.verify()
        except CodexNativeAdmissionRejected:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise CodexNativeAdmissionRejected("source_pixel_limit_exceeded") from None
        except (OSError, UnidentifiedImageError, ValueError):
            raise CodexNativeAdmissionRejected("source_decode_rejected") from None
        if image_format != _MEDIA_FORMATS[media_type]:
            raise CodexNativeAdmissionRejected("source_media_type_mismatch")
        if width * output.height != height * output.width:
            raise CodexNativeAdmissionRejected("source_aspect_ratio_mismatch")
        return width, height
