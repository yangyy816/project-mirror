"""Worker-only public authority and byte boundary for admitted D02 sources."""

from __future__ import annotations

import hashlib
import hmac
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api import demo_d02_generic_admission as d02_generic
from mirror_api.demo_d02_r2_runtime_forward import DurableSourceDescriptor
from mirror_api.demo_editing_repository import (
    DemoEditingRepositoryError,
    require_d02_source_authority_if_applicable,
)
from mirror_api.demo_editing_storage import DemoEditingStorageError, DemoLocalPrivateObjectStorage
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest
from mirror_api.demo_models import (
    D02SelectedSourceManifest,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
    DemoD02R2SourceAuthority,
)
from mirror_api.models import Asset

_ASSET_ID_RE: Final = re.compile(r"[0-9a-f]{32}\Z")
_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_KEY_RE: Final = re.compile(r"internal-synthetic/v1/d02/source/[0-9a-f]{32}\Z")
_OUTPUT_ID_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_SOURCE_CANDIDATE_SCHEMA: Final = "mirror.demo/D02SourceCandidate/v1"
_MANIFEST_SCHEMA: Final = "mirror.demo/D02SelectedSourceManifest/v1"
_RUN_SCHEMA: Final = "mirror.demo/D02SourceAcquisitionRun/v1"


class DemoAnalysisSourceAuthorityError(RuntimeError):
    """Stable, non-sensitive error for the D03 worker-only source boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AdmittedD02SourceReference:
    """Public metadata only; never contains a locator, path, or source bytes."""

    asset_id: str
    storage_key: str
    sha256: str
    byte_size: int
    mime_type: str
    width: int
    height: int
    source_authority_digest: str
    source_output_id: str
    source_ordinal: int
    generation_request_identity: str
    source_provenance_digest: str
    source_authority_key: str
    source_schema_version: str

    def __post_init__(self) -> None:
        if (
            _ASSET_ID_RE.fullmatch(self.asset_id) is None
            or self.storage_key != f"internal-synthetic/v1/d02/source/{self.asset_id}"
            or _SOURCE_KEY_RE.fullmatch(self.storage_key) is None
            or _DIGEST_RE.fullmatch(self.sha256) is None
            or _DIGEST_RE.fullmatch(self.source_authority_digest) is None
            or _DIGEST_RE.fullmatch(self.generation_request_identity) is None
            or _DIGEST_RE.fullmatch(self.source_provenance_digest) is None
            or _DIGEST_RE.fullmatch(self.source_authority_key) is None
            or _OUTPUT_ID_RE.fullmatch(self.source_output_id) is None
            or self.source_ordinal not in {1, 2, 3, 4}
            or self.source_schema_version != d02_generic.SOURCE_SCHEMA
            or self.mime_type != "image/jpeg"
            or any(
                type(value) is not int or value <= 0
                for value in (self.byte_size, self.width, self.height)
            )
        ):
            raise DemoAnalysisSourceAuthorityError(
                "D02_SOURCE_REFERENCE_INVALID", "D02 source reference is invalid"
            )

    def durable_descriptor(self) -> DurableSourceDescriptor:
        """Project the fully revalidated public reference into the accepted runtime type."""

        return DurableSourceDescriptor(
            source_id=self.asset_id,
            source_output_id=self.source_output_id,
            ordinal=self.source_ordinal,
            content_sha256=self.sha256,
            media_type=self.mime_type,
            width=self.width,
            height=self.height,
            byte_length=self.byte_size,
            generation_request_identity=self.generation_request_identity,
            provenance_identity=self.source_provenance_digest,
            source_authority_key=self.source_authority_key,
            source_schema_version=self.source_schema_version,
        )


async def resolve_admitted_d02_source(
    session: AsyncSession, *, asset_id: str
) -> AdmittedD02SourceReference:
    """Resolve exactly one completed generic D02 SOURCE through public DB authority."""

    if _ASSET_ID_RE.fullmatch(asset_id) is None:
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_AUTHORITY_UNAVAILABLE", "D02 source authority is unavailable"
        )
    source = await session.get(Asset, asset_id)
    if source is None:
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_AUTHORITY_UNAVAILABLE", "D02 source authority is unavailable"
        )
    expected_key = f"internal-synthetic/v1/d02/source/{asset_id}"
    if (
        source.deleted_at is not None
        or source.storage_key != expected_key
        or not source.synthetic
        or source.asset_role != "synthetic"
        or source.internal_purpose != "synthetic_dataset"
        or source.mime_type != "image/jpeg"
    ):
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_AUTHORITY_MISMATCH", "D02 source Asset is invalid"
        )
    try:
        await require_d02_source_authority_if_applicable(session, source)
    except DemoEditingRepositoryError as error:
        raise DemoAnalysisSourceAuthorityError(
            error.code, "D02 source authority is unavailable"
        ) from error
    rows = list(
        await session.scalars(
            select(DemoD02R2SourceAuthority).where(
                DemoD02R2SourceAuthority.source_asset_id == source.id,
                DemoD02R2SourceAuthority.schema_version == d02_generic.SOURCE_SCHEMA,
            )
        )
    )
    if len(rows) != 1:
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_AUTHORITY_UNAVAILABLE", "D02 source authority is unavailable"
        )
    authority = rows[0]
    if (
        authority.source_asset_sha256 != source.sha256
        or authority.source_asset_byte_size != source.byte_size
        or authority.source_asset_mime_type != source.mime_type
        or authority.source_asset_width != source.width
        or authority.source_asset_height != source.height
        or authority.source_asset_id != source.id
    ):
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_AUTHORITY_MISMATCH", "D02 source authority is invalid"
        )
    candidate = await _resolve_projection_candidate(session, authority)
    return AdmittedD02SourceReference(
        asset_id=source.id,
        storage_key=source.storage_key,
        sha256=source.sha256,
        byte_size=source.byte_size,
        mime_type=source.mime_type,
        width=source.width,
        height=source.height,
        source_authority_digest=authority.source_authority_digest,
        source_output_id=authority.source_output_id,
        source_ordinal=authority.source_ordinal,
        generation_request_identity=candidate.content_digest,
        source_provenance_digest=authority.source_provenance_digest,
        source_authority_key=authority.source_authority_key,
        source_schema_version=authority.schema_version,
    )


async def _resolve_projection_candidate(
    session: AsyncSession, authority: DemoD02R2SourceAuthority
) -> D02SourceCandidate:
    candidate_id = authority.acquisition_candidate_id
    manifest_id = authority.selected_source_manifest_id
    if candidate_id is None or manifest_id is None:
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_AUTHORITY_MISMATCH", "D02 source authority is invalid"
        )
    candidate = await session.get(D02SourceCandidate, candidate_id)
    manifest = await session.get(D02SelectedSourceManifest, manifest_id)
    if candidate is None or manifest is None:
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_AUTHORITY_UNAVAILABLE", "D02 source authority is unavailable"
        )
    run = await session.get(D02SourceAcquisitionRun, candidate.acquisition_run_id)
    if (
        run is None
        or candidate.id != candidate_id
        or candidate.acquisition_run_id != manifest.acquisition_run_id
        or candidate.cohort_spec_id != manifest.cohort_spec_id
        or candidate.output_id != authority.source_output_id
        or candidate.candidate_state != "QA_ACCEPTED"
        or candidate.qa_state != "ACCEPTED"
        or authority.manifest_position != authority.source_ordinal
        or authority.manifest_position is None
        or not isinstance(manifest.ordered_candidate_ids, list)
        or len(manifest.ordered_candidate_ids) != 4
        or manifest.ordered_candidate_ids[authority.manifest_position - 1] != candidate.id
        or run.id != manifest.acquisition_run_id
        or run.cohort_spec_id != manifest.cohort_spec_id
        or run.run_state != "ADMITTED"
        or not _canonical_matches(candidate, _SOURCE_CANDIDATE_SCHEMA)
        or not _canonical_matches(manifest, _MANIFEST_SCHEMA)
        or not _canonical_matches(run, _RUN_SCHEMA)
    ):
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_AUTHORITY_MISMATCH", "D02 source authority is invalid"
        )
    return candidate


def _canonical_matches(row: object, schema: str) -> bool:
    payload = getattr(row, "canonical_payload", None)
    return (
        getattr(row, "schema_version", None) == schema
        and isinstance(payload, Mapping)
        and getattr(row, "content_digest", None)
        == mirror_demo_digest(schema, cast(Mapping[str, JsonValue], payload))
    )


async def materialize_admitted_d02_source(
    *, storage: DemoLocalPrivateObjectStorage, reference: AdmittedD02SourceReference, content: bytes
) -> None:
    """Put Principal-injected bytes under the exact immutable D02 SOURCE key."""

    _verify_content(reference, content)
    try:
        await storage.put_if_absent(
            key=reference.storage_key, content=content, sha256=reference.sha256
        )
    except DemoEditingStorageError as error:
        raise DemoAnalysisSourceAuthorityError(
            error.code, "D02 source bytes are unavailable"
        ) from error


class LocalAdmittedD02SourceLoader:
    """Load only a materialized D02 SOURCE and verify it again before returning bytes."""

    def __init__(self, *, storage: DemoLocalPrivateObjectStorage) -> None:
        self._storage = storage

    async def load(self, reference: AdmittedD02SourceReference) -> bytes:
        try:
            content = await self._storage.read(key=reference.storage_key)
        except DemoEditingStorageError as error:
            raise DemoAnalysisSourceAuthorityError(
                error.code, "D02 source bytes are unavailable"
            ) from error
        if content is None:
            raise DemoAnalysisSourceAuthorityError(
                "D02_SOURCE_BYTES_UNAVAILABLE", "D02 source bytes are unavailable"
            )
        _verify_content(reference, content)
        return content


def _verify_content(reference: AdmittedD02SourceReference, content: bytes) -> None:
    if type(content) is not bytes or len(content) != reference.byte_size:
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_SIZE_MISMATCH", "D02 source bytes mismatch authority"
        )
    if not content.startswith(b"\xff\xd8\xff"):
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_IMAGE_INVALID", "D02 source bytes are invalid"
        )
    actual = hashlib.sha256(content).hexdigest()
    if not hmac.compare_digest(actual, reference.sha256):
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_DIGEST_MISMATCH", "D02 source bytes mismatch authority"
        )
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            if image.format != "JPEG" or image.size != (reference.width, reference.height):
                raise DemoAnalysisSourceAuthorityError(
                    "D02_SOURCE_IMAGE_INVALID", "D02 source bytes are invalid"
                )
    except DemoAnalysisSourceAuthorityError:
        raise
    except (OSError, UnidentifiedImageError) as error:
        raise DemoAnalysisSourceAuthorityError(
            "D02_SOURCE_IMAGE_INVALID", "D02 source bytes are invalid"
        ) from error


__all__ = [
    "AdmittedD02SourceReference",
    "DemoAnalysisSourceAuthorityError",
    "LocalAdmittedD02SourceLoader",
    "materialize_admitted_d02_source",
    "resolve_admitted_d02_source",
]
