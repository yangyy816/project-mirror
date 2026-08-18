"""Transactional application service for one deterministic private synthetic transform."""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.models import (
    Asset,
    GeometryOntologyVersion,
    SyntheticAssetRecord,
    SyntheticIdentity,
    SyntheticQAPolicy,
    SyntheticQARun,
    TransformRun,
)
from mirror_api.models import (
    LandmarkWarpPlanAuthority as LandmarkWarpPlanAuthorityModel,
)
from mirror_api.models import (
    VariantSpecification as VariantSpecificationModel,
)
from mirror_api.providers.base import (
    SyntheticNormalizedStorageProvider,
    SyntheticStorageConflictError,
    SyntheticStorageOperationError,
)
from mirror_api.storage_keys import (
    internal_synthetic_normalized_object_key,
    synthetic_normalized_storage_reference,
    synthetic_variant_storage_reference,
)

from .domain import (
    CanonicalPolicy,
    DomainValidationError,
    GeometryDimension,
    GeometryDimensionClassification,
    GeometryOntology,
    PolicyKind,
    ReasonCode,
)
from .geometry_transform import (
    CanonicalTransformSource,
    GeometryTransform,
    GeometryTransformRequest,
)
from .geometry_variant import DeterminismLevel, TransformDirection, VariantSpecification
from .landmark_warp_plan_authority import (
    LandmarkWarpPlanAuthority,
    LandmarkWarpPlanOrigin,
)
from .variant_storage import (
    VariantStorageProvider,
    VariantStorageWriteRequest,
    VariantStoredImage,
)

_ID = re.compile(r"[0-9a-f]{32}\Z")
_MAX_SOURCE_BYTES = 20 * 1024 * 1024


def _utcnow() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager
async def _transaction(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


class TransformExecutionRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code) else "transform_rejected"
        super().__init__("synthetic transform was rejected")


class TransformExecutionRetryable(Exception):
    def __init__(self, code: str = "transform_execution_unavailable") -> None:
        self.code = (
            code
            if re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code)
            else "transform_execution_unavailable"
        )
        super().__init__("synthetic transform remains retryable")


@dataclass(frozen=True)
class TransformApplicationResult:
    transform_run_id: str
    result_asset_id: str
    qa_run_id: str
    stored: bool


@dataclass(frozen=True)
class _TransformClaim:
    run_id: str
    specification: VariantSpecification
    plan_authority: LandmarkWarpPlanAuthority
    source_asset_id: str
    source_storage_reference: str
    source_sha256: str
    source_byte_size: int
    source_width: int
    source_height: int
    source_vision_provider_reference: str | None
    source_vision_algorithm_reference: str | None
    qa_policy_id: str


class SyntheticTransformService:
    """Rebuilds transform input from PostgreSQL and commits one immutable result authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        transform: GeometryTransform,
        normalized_storage: SyntheticNormalizedStorageProvider,
        variant_storage: VariantStorageProvider,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._sessions = session_factory
        self._transform = transform
        self._normalized_storage = normalized_storage
        self._variant_storage = variant_storage
        self._now = now

    async def execute(
        self,
        *,
        transform_run_id: str,
        completion_guard: Callable[[AsyncSession], Awaitable[None]] | None = None,
    ) -> TransformApplicationResult:
        self._require_id(transform_run_id)
        existing = await self._existing_result(transform_run_id)
        if existing is not None:
            return existing
        claim = await self._claim(transform_run_id)
        source_content = await self._read_source(claim)
        try:
            result = await asyncio.to_thread(
                partial(
                    self._transform.transform,
                    request=GeometryTransformRequest(
                        specification=claim.specification,
                        source=CanonicalTransformSource(
                            asset_reference=claim.source_asset_id,
                            content=source_content,
                            sha256=claim.source_sha256,
                            width=claim.source_width,
                            height=claim.source_height,
                        ),
                        warp_plan=claim.plan_authority.plan,
                    ),
                )
            )
        except DomainValidationError as error:
            raise TransformExecutionRejected(error.reason_code.value.lower()) from None
        except Exception:
            raise TransformExecutionRetryable("transform_runtime_unavailable") from None
        if (
            result.runtime_manifest_digest != claim.specification.runtime_manifest_digest
            or result.warp_plan_digest != claim.plan_authority.warp_plan_digest
            or result.sha256 == claim.source_sha256
            or (result.width, result.height)
            != (claim.specification.output_width, claim.specification.output_height)
        ):
            raise TransformExecutionRejected("transform_evidence_mismatch")
        storage_reference = synthetic_variant_storage_reference(
            claim.run_id, claim.specification.content_digest
        )
        try:
            receipt = await self._variant_storage.store_variant_if_absent(
                request=VariantStorageWriteRequest(
                    storage_reference=storage_reference,
                    transform_run_reference=claim.run_id,
                    specification_digest=claim.specification.content_digest,
                    output_policy_version=claim.specification.output_policy_version,
                    result=result,
                )
            )
        except SyntheticStorageConflictError:
            raise TransformExecutionRejected("variant_storage_conflict") from None
        except SyntheticStorageOperationError as error:
            raise TransformExecutionRetryable(error.reason) from None
        except Exception:
            raise TransformExecutionRetryable("variant_storage_unavailable") from None
        try:
            return await self._commit_result(
                claim=claim, receipt=receipt, completion_guard=completion_guard
            )
        except Exception:
            # The receipt is deterministic and intentionally retained for storage-before-DB
            # recovery unless authority has already been cancelled.
            await self._delete_if_cancelled(claim)
            raise

    async def ensure_qa_handoff(self, *, transform_run_id: str) -> str | None:
        """Repair the only admissible output-stored/no-QA gap without re-running transform I/O."""
        self._require_id(transform_run_id)
        async with _transaction(self._sessions) as session:
            specification, _, run = await self._locked_authority_chain(session, transform_run_id)
            if run.status != "OUTPUT_STORED":
                return None
            if run.result_asset_id is None:
                raise TransformExecutionRejected("transform_result_authority_missing")
            source_run = await self._locked_source_run(session, specification.source_qa_run_id)
            if source_run is None:
                raise TransformExecutionRejected("source_qa_authority_missing")
            return await self._ensure_variant_qa(
                session=session,
                run=run,
                specification=specification,
                source_run=source_run,
            )

    async def _existing_result(self, transform_run_id: str) -> TransformApplicationResult | None:
        async with _transaction(self._sessions) as session:
            specification, _, run = await self._locked_authority_chain(session, transform_run_id)
            if run.status not in {"OUTPUT_STORED", "MEASURING", "COMPLETED"}:
                return None
            if run.result_asset_id is None:
                raise TransformExecutionRejected("transform_result_authority_missing")
            asset = cast(
                Asset | None,
                await session.scalar(
                    select(Asset)
                    .where(Asset.id == run.result_asset_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            qa_run = await self._variant_qa(session, run.id)
            if asset is None or qa_run is None:
                raise TransformExecutionRejected("transform_result_authority_missing")
            if qa_run.qa_policy_id != specification.tolerance_policy_id:
                raise TransformExecutionRejected("variant_qa_authority_conflict")
            return TransformApplicationResult(run.id, asset.id, qa_run.id, False)

    async def delete_cancelled_orphan(self, *, transform_run_id: str) -> bool:
        self._require_id(transform_run_id)
        async with self._sessions() as session:
            run = await session.get(TransformRun, transform_run_id)
            if run is None or run.status != "CANCELLED" or run.result_asset_id is not None:
                return False
            specification = await session.get(
                VariantSpecificationModel, run.variant_specification_id
            )
            if specification is None:
                raise TransformExecutionRejected("variant_specification_not_found")
            reference = synthetic_variant_storage_reference(run.id, specification.content_digest)
        return await self._variant_storage.delete_variant(storage_reference=reference) == "deleted"

    async def _claim(self, transform_run_id: str) -> _TransformClaim:
        async with _transaction(self._sessions) as session:
            specification, plan_model, run = await self._locked_authority_chain(
                session, transform_run_id
            )
            ontology = cast(
                GeometryOntologyVersion | None,
                await session.scalar(
                    select(GeometryOntologyVersion)
                    .where(GeometryOntologyVersion.id == specification.geometry_ontology_version_id)
                    .execution_options(populate_existing=True)
                ),
            )
            if ontology is None or ontology.approval_status != "APPROVED":
                raise TransformExecutionRejected("geometry_ontology_not_approved")
            source_asset = cast(
                Asset | None,
                await session.scalar(
                    select(Asset)
                    .where(Asset.id == specification.source_asset_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            source_run = await self._locked_source_run(session, specification.source_qa_run_id)
            if source_asset is None or source_run is None:
                raise TransformExecutionRejected("source_authority_missing")
            record = cast(
                SyntheticAssetRecord | None,
                await session.scalar(
                    select(SyntheticAssetRecord)
                    .where(SyntheticAssetRecord.id == source_run.synthetic_asset_record_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            identity = cast(
                SyntheticIdentity | None,
                await session.scalar(
                    select(SyntheticIdentity)
                    .where(SyntheticIdentity.id == specification.source_identity_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            policy = cast(
                SyntheticQAPolicy | None,
                await session.scalar(
                    select(SyntheticQAPolicy)
                    .where(SyntheticQAPolicy.id == specification.tolerance_policy_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            if record is None or identity is None or policy is None:
                raise TransformExecutionRejected("source_authority_missing")
            self._validate_source_authority(
                specification=specification,
                source_asset=source_asset,
                source_run=source_run,
                record=record,
                identity=identity,
                policy=policy,
            )
            try:
                domain_specification = self._domain_specification(specification, ontology)
            except (DomainValidationError, TypeError, ValueError):
                raise TransformExecutionRejected("variant_specification_not_researchable") from None
            plan_authority = self._domain_plan(plan_model, domain_specification.content_digest)
            if run.status == "SPECIFIED":
                run.status = "RUNNING"
                run.started_at = self._now()
                run.updated_at = self._now()
                await session.flush()
            elif run.status != "RUNNING":
                raise TransformExecutionRejected("transform_run_not_executable")
            storage_reference = synthetic_normalized_storage_reference(
                record.id, record.normalizer_config_digest
            )
            if source_asset.storage_key != internal_synthetic_normalized_object_key(
                storage_reference
            ):
                raise TransformExecutionRejected("source_storage_authority_mismatch")
            return _TransformClaim(
                run_id=run.id,
                specification=domain_specification,
                plan_authority=plan_authority,
                source_asset_id=source_asset.id,
                source_storage_reference=storage_reference,
                source_sha256=source_asset.sha256,
                source_byte_size=source_asset.byte_size,
                source_width=source_asset.width,
                source_height=source_asset.height,
                source_vision_provider_reference=source_run.vision_provider_reference,
                source_vision_algorithm_reference=source_run.vision_algorithm_reference,
                qa_policy_id=policy.id,
            )

    async def _read_source(self, claim: _TransformClaim) -> bytes:
        content = bytearray()
        try:
            async for chunk in self._normalized_storage.stream_normalized_image(
                storage_reference=claim.source_storage_reference
            ):
                if not chunk or len(content) + len(chunk) > _MAX_SOURCE_BYTES:
                    raise TransformExecutionRejected("source_image_bounds_invalid")
                content.extend(chunk)
        except TransformExecutionRejected:
            raise
        except SyntheticStorageOperationError as error:
            raise TransformExecutionRetryable(error.reason) from None
        payload = bytes(content)
        if (
            len(payload) != claim.source_byte_size
            or hashlib.sha256(payload).hexdigest() != claim.source_sha256
        ):
            raise TransformExecutionRejected("source_checksum_mismatch")
        return payload

    async def _commit_result(
        self,
        *,
        claim: _TransformClaim,
        receipt: VariantStoredImage,
        completion_guard: Callable[[AsyncSession], Awaitable[None]] | None,
    ) -> TransformApplicationResult:
        async with _transaction(self._sessions) as session:
            specification, _, run = await self._locked_authority_chain(session, claim.run_id)
            if completion_guard is not None:
                await completion_guard(session)
            existing_qa = await self._variant_qa(session, run.id)
            if run.status in {"OUTPUT_STORED", "MEASURING", "COMPLETED"}:
                if run.result_asset_id is None or existing_qa is None:
                    raise TransformExecutionRejected("transform_result_authority_missing")
                asset = await session.get(Asset, run.result_asset_id)
                if asset is None or not self._asset_matches_receipt(asset, receipt):
                    raise TransformExecutionRejected("transform_result_authority_conflict")
                return TransformApplicationResult(run.id, asset.id, existing_qa.id, False)
            if run.status != "RUNNING":
                raise TransformExecutionRejected("transform_run_not_executable")
            asset_id = hashlib.sha256(
                f"mirror.synthetic-variant-asset/v1:{receipt.receipt_digest}".encode()
            ).hexdigest()[:32]
            asset = cast(
                Asset | None,
                await session.scalar(
                    select(Asset)
                    .where(Asset.id == asset_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ),
            )
            if asset is None:
                asset = Asset(
                    id=asset_id,
                    owner_user_id=None,
                    asset_role="synthetic",
                    storage_key=receipt.storage_key,
                    mime_type=receipt.media_type,
                    byte_size=receipt.byte_size,
                    width=receipt.width,
                    height=receipt.height,
                    sha256=receipt.sha256,
                    synthetic=True,
                    is_ai_generated=False,
                    is_ai_modified=True,
                    internal_purpose="synthetic_dataset",
                    created_at=self._now(),
                    updated_at=self._now(),
                )
                session.add(asset)
                await session.flush()
            elif not self._asset_matches_receipt(asset, receipt):
                raise TransformExecutionRejected("transform_result_authority_conflict")
            run.status = "OUTPUT_STORED"
            run.result_asset_id = asset.id
            run.output_stored_at = self._now()
            run.updated_at = self._now()
            await session.flush()
            source_run = await self._locked_source_run(session, specification.source_qa_run_id)
            if source_run is None:
                raise TransformExecutionRejected("source_qa_authority_missing")
            qa_run_id = await self._ensure_variant_qa(
                session=session,
                run=run,
                specification=specification,
                source_run=source_run,
            )
            return TransformApplicationResult(run.id, asset.id, qa_run_id, True)

    async def _ensure_variant_qa(
        self,
        *,
        session: AsyncSession,
        run: TransformRun,
        specification: VariantSpecificationModel,
        source_run: SyntheticQARun,
    ) -> str:
        existing = await self._variant_qa(session, run.id)
        if existing is not None:
            if existing.normalized_asset_id != run.result_asset_id:
                raise TransformExecutionRejected("variant_qa_authority_conflict")
            return existing.id
        if run.result_asset_id is None:
            raise TransformExecutionRejected("transform_result_authority_missing")
        qa_run_id = hashlib.sha256(f"mirror.synthetic-variant-qa/v1:{run.id}".encode()).hexdigest()[
            :32
        ]
        session.add(
            SyntheticQARun(
                id=qa_run_id,
                schema_version="mirror.synthetic-dataset/SyntheticQARun/v2",
                subject_kind="GEOMETRY_VARIANT",
                synthetic_asset_record_id=None,
                transform_run_id=run.id,
                normalized_asset_id=run.result_asset_id,
                qa_policy_id=specification.tolerance_policy_id,
                vision_provider_reference=source_run.vision_provider_reference,
                vision_algorithm_reference=source_run.vision_algorithm_reference,
                status="PENDING",
                created_at=self._now(),
                updated_at=self._now(),
            )
        )
        await session.flush()
        return qa_run_id

    async def _delete_if_cancelled(self, claim: _TransformClaim) -> None:
        async with self._sessions() as session:
            run = await session.get(TransformRun, claim.run_id)
            cancelled = (
                run is not None and run.status == "CANCELLED" and run.result_asset_id is None
            )
        if cancelled:
            reference = synthetic_variant_storage_reference(
                claim.run_id, claim.specification.content_digest
            )
            await self._variant_storage.delete_variant(storage_reference=reference)

    @staticmethod
    async def _locked_authority_chain(
        session: AsyncSession, run_id: str
    ) -> tuple[
        VariantSpecificationModel,
        LandmarkWarpPlanAuthorityModel,
        TransformRun,
    ]:
        specification_id = cast(
            str | None,
            await session.scalar(
                select(TransformRun.variant_specification_id).where(TransformRun.id == run_id)
            ),
        )
        if specification_id is None:
            raise TransformExecutionRejected("transform_run_not_found")
        specification = cast(
            VariantSpecificationModel | None,
            await session.scalar(
                select(VariantSpecificationModel)
                .where(VariantSpecificationModel.id == specification_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if specification is None:
            raise TransformExecutionRejected("variant_specification_not_found")
        plan = cast(
            LandmarkWarpPlanAuthorityModel | None,
            await session.scalar(
                select(LandmarkWarpPlanAuthorityModel)
                .where(LandmarkWarpPlanAuthorityModel.variant_specification_id == specification.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if plan is None:
            raise TransformExecutionRejected("warp_plan_not_found")
        run = cast(
            TransformRun | None,
            await session.scalar(
                select(TransformRun)
                .where(
                    TransformRun.id == run_id,
                    TransformRun.variant_specification_id == specification.id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )
        if run is None:
            raise TransformExecutionRejected("transform_run_authority_conflict")
        return specification, plan, run

    @staticmethod
    async def _locked_source_run(session: AsyncSession, run_id: str) -> SyntheticQARun | None:
        return cast(
            SyntheticQARun | None,
            await session.scalar(
                select(SyntheticQARun)
                .where(SyntheticQARun.id == run_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    async def _variant_qa(session: AsyncSession, run_id: str) -> SyntheticQARun | None:
        return cast(
            SyntheticQARun | None,
            await session.scalar(
                select(SyntheticQARun)
                .where(SyntheticQARun.transform_run_id == run_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    @staticmethod
    def _domain_specification(
        row: VariantSpecificationModel, ontology: GeometryOntologyVersion
    ) -> VariantSpecification:
        domain_ontology = SyntheticTransformService._domain_ontology(ontology)
        specification = VariantSpecification.create(
            ontology=domain_ontology,
            source_asset_reference=row.source_asset_id,
            source_identity_reference=row.source_identity_id,
            source_qa_run_reference=row.source_qa_run_id,
            target_dimension=row.target_dimension,
            direction=TransformDirection(row.direction),
            relative_magnitude_ppm=row.relative_magnitude_ppm,
            control_dimensions=tuple(row.control_dimensions),
            algorithm_version=row.algorithm_version,
            runtime_manifest_digest=row.runtime_manifest_digest,
            tolerance_policy_reference=row.tolerance_policy_id,
            output_width=row.output_width,
            output_height=row.output_height,
            output_policy_version=row.output_policy_version,
            determinism_level=DeterminismLevel(row.determinism_level),
        )
        if specification.content_digest != row.content_digest:
            raise DomainValidationError(ReasonCode.INVALID_VARIANT_SPECIFICATION)
        return specification

    @staticmethod
    def _domain_ontology(row: GeometryOntologyVersion) -> GeometryOntology:
        authority = CanonicalPolicy.create(
            kind=PolicyKind.GEOMETRY_ONTOLOGY_VERSION,
            version=row.version,
            content=row.content,
        )
        if authority.content_digest != row.content_digest:
            raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
        dimensions_value = row.content.get("dimensions")
        if not isinstance(dimensions_value, dict) or not dimensions_value:
            raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
        dimensions: list[GeometryDimension] = []
        for key in sorted(dimensions_value):
            value = dimensions_value[key]
            if (
                type(key) is not str
                or not isinstance(value, dict)
                or set(value) != {"classification"}
                or type(value["classification"]) is not str
            ):
                raise DomainValidationError(ReasonCode.INVALID_POLICY_CONTENT)
            classification = GeometryDimensionClassification(value["classification"])
            reason_codes: tuple[ReasonCode, ...]
            if classification is GeometryDimensionClassification.READY:
                reason_codes = ()
            elif classification is GeometryDimensionClassification.EXPERIMENTAL:
                reason_codes = (ReasonCode.FURTHER_RESEARCH,)
            elif classification is GeometryDimensionClassification.UNSUPPORTED:
                reason_codes = (ReasonCode.UNSUPPORTED_DIMENSION,)
            elif classification is GeometryDimensionClassification.REQUIRES_3D:
                reason_codes = (ReasonCode.REQUIRES_3D_RESEARCH,)
            else:
                reason_codes = (ReasonCode.STYLE_ONLY_DIMENSION,)
            dimensions.append(GeometryDimension(key, classification, reason_codes))
        return GeometryOntology(authority=authority, dimensions=tuple(dimensions))

    @staticmethod
    def _domain_plan(
        row: LandmarkWarpPlanAuthorityModel, specification_digest: str
    ) -> LandmarkWarpPlanAuthority:
        return LandmarkWarpPlanAuthority.from_persisted(
            specification_digest=specification_digest,
            canonical_payload=row.canonical_payload,
            origin_kind=LandmarkWarpPlanOrigin(row.origin_kind),
            origin_reference=row.origin_reference,
            origin_digest=row.origin_digest,
            builder_version=row.builder_version,
            builder_manifest_digest=row.builder_manifest_digest,
            warp_plan_digest=row.warp_plan_digest,
            authority_digest=row.authority_digest,
            plan_schema_version=row.plan_schema_version,
            schema_version=row.schema_version,
        )

    @staticmethod
    def _validate_source_authority(
        *,
        specification: VariantSpecificationModel,
        source_asset: Asset,
        source_run: SyntheticQARun,
        record: SyntheticAssetRecord,
        identity: SyntheticIdentity,
        policy: SyntheticQAPolicy,
    ) -> None:
        if (
            source_asset.owner_user_id is not None
            or source_asset.asset_role != "synthetic"
            or not source_asset.synthetic
            or source_asset.internal_purpose != "synthetic_dataset"
            or source_asset.deleted_at is not None
            or source_asset.id != specification.source_asset_id
            or (source_asset.width, source_asset.height)
            != (specification.output_width, specification.output_height)
            or source_run.status != "PASSED"
            or source_run.subject_kind != "CANONICAL_BASE"
            or source_run.normalized_asset_id != source_asset.id
            or record.id != source_run.synthetic_asset_record_id
            or record.normalized_asset_id != source_asset.id
            or record.status != "IDENTITY_REGISTERED"
            or identity.canonical_asset_id != source_asset.id
            or identity.accepted_qa_run_id != source_run.id
            or not identity.adult_synthetic_attested
            or policy.approval_status != "APPROVED"
        ):
            raise TransformExecutionRejected("source_authority_invalid")

    @staticmethod
    def _asset_matches_receipt(asset: Asset, receipt: VariantStoredImage) -> bool:
        return bool(
            asset.owner_user_id is None
            and asset.asset_role == "synthetic"
            and asset.synthetic
            and asset.is_ai_modified
            and asset.internal_purpose == "synthetic_dataset"
            and asset.deleted_at is None
            and asset.storage_key == receipt.storage_key
            and asset.mime_type == receipt.media_type
            and asset.byte_size == receipt.byte_size
            and asset.width == receipt.width
            and asset.height == receipt.height
            and asset.sha256 == receipt.sha256
        )

    @staticmethod
    def _require_id(value: str) -> None:
        if _ID.fullmatch(value) is None:
            raise ValueError("transform run identifier must be opaque")
