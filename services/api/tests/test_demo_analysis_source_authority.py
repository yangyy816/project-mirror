from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from mirror_api.demo_analysis_source_authority import (
    AdmittedD02SourceReference,
    DemoAnalysisSourceAuthorityError,
    LocalAdmittedD02SourceLoader,
    materialize_admitted_d02_source,
    resolve_admitted_d02_source,
)
from mirror_api.demo_editing_storage import DemoLocalPrivateObjectStorage
from mirror_api.demo_measurement_quality import mirror_demo_digest
from mirror_api.demo_models import (
    D02SelectedSourceManifest,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
)
from mirror_api.models import Asset


def _jpeg(size: tuple[int, int] = (4, 3)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color=(1, 2, 3)).save(output, format="JPEG")
    return output.getvalue()


def _reference(content: bytes, *, asset_id: str = "a" * 32) -> AdmittedD02SourceReference:
    return AdmittedD02SourceReference(
        asset_id=asset_id,
        storage_key=f"internal-synthetic/v1/d02/source/{asset_id}",
        sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        mime_type="image/jpeg",
        width=4,
        height=3,
        source_authority_digest="b" * 64,
        source_output_id="source-1",
        source_ordinal=1,
        generation_request_identity="c" * 64,
        source_provenance_digest="d" * 64,
        source_authority_key="e" * 64,
        source_schema_version="mirror.demo/D02GenericSourceAuthorityRecord/v1",
    )


class _Session:
    def __init__(
        self,
        source: Asset | None,
        rows: list[object],
        objects: dict[tuple[object, str], object] | None = None,
    ) -> None:
        self.source = source
        self.rows = rows
        self.objects = objects or {}

    async def get(self, model: object, identifier: str) -> object | None:
        if model is Asset:
            return self.source
        return self.objects.get((model, identifier))

    async def scalars(self, _: object) -> list[object]:
        return self.rows


def _projection_rows(
    reference: AdmittedD02SourceReference,
) -> tuple[object, dict[tuple[object, str], object]]:
    candidate_id = "c" * 32
    manifest_id = "d" * 32
    run_id = "e" * 32
    cohort_id = "f" * 32
    candidate_payload: dict[str, object] = {}
    manifest_payload: dict[str, object] = {}
    run_payload: dict[str, object] = {}
    candidate = SimpleNamespace(
        id=candidate_id,
        acquisition_run_id=run_id,
        cohort_spec_id=cohort_id,
        output_id="source-1",
        candidate_state="QA_ACCEPTED",
        qa_state="ACCEPTED",
        schema_version="mirror.demo/D02SourceCandidate/v1",
        canonical_payload=candidate_payload,
        content_digest=mirror_demo_digest("mirror.demo/D02SourceCandidate/v1", candidate_payload),
    )
    manifest = SimpleNamespace(
        id=manifest_id,
        acquisition_run_id=run_id,
        cohort_spec_id=cohort_id,
        ordered_candidate_ids=[candidate_id, "1" * 32, "2" * 32, "3" * 32],
        schema_version="mirror.demo/D02SelectedSourceManifest/v1",
        canonical_payload=manifest_payload,
        content_digest=mirror_demo_digest(
            "mirror.demo/D02SelectedSourceManifest/v1", manifest_payload
        ),
    )
    run = SimpleNamespace(
        id=run_id,
        cohort_spec_id=cohort_id,
        run_state="ADMITTED",
        schema_version="mirror.demo/D02SourceAcquisitionRun/v1",
        canonical_payload=run_payload,
        content_digest=mirror_demo_digest("mirror.demo/D02SourceAcquisitionRun/v1", run_payload),
    )
    authority = SimpleNamespace(
        source_asset_id=reference.asset_id,
        source_asset_sha256=reference.sha256,
        source_asset_byte_size=reference.byte_size,
        source_asset_mime_type="image/jpeg",
        source_asset_width=4,
        source_asset_height=3,
        source_authority_digest="b" * 64,
        source_output_id="source-1",
        source_ordinal=1,
        source_provenance_digest="c" * 64,
        source_authority_key="d" * 64,
        schema_version="mirror.demo/D02GenericSourceAuthorityRecord/v1",
        acquisition_candidate_id=candidate_id,
        selected_source_manifest_id=manifest_id,
        manifest_position=1,
    )
    return authority, {
        (D02SourceCandidate, candidate_id): candidate,
        (D02SelectedSourceManifest, manifest_id): manifest,
        (D02SourceAcquisitionRun, run_id): run,
    }


@pytest.mark.asyncio
async def test_resolver_returns_only_public_typed_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _jpeg()
    reference = _reference(content)
    source = Asset(
        id=reference.asset_id,
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key=reference.storage_key,
        mime_type="image/jpeg",
        byte_size=reference.byte_size,
        width=reference.width,
        height=reference.height,
        sha256=reference.sha256,
        synthetic=True,
        is_ai_generated=True,
        is_ai_modified=False,
    )
    authority, objects = _projection_rows(reference)
    called = False

    async def require(_: object, __: Asset) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        "mirror_api.demo_analysis_source_authority.require_d02_source_authority_if_applicable",
        require,
    )
    actual = await resolve_admitted_d02_source(
        _Session(source, [authority], objects),
        asset_id=source.id,  # type: ignore[arg-type]
    )

    assert called is True
    assert actual.asset_id == reference.asset_id
    assert actual.durable_descriptor().source_id == reference.asset_id
    assert (
        actual.durable_descriptor().generation_request_identity
        == objects[(D02SourceCandidate, "c" * 32)].content_digest
    )
    assert "path" not in actual.__dataclass_fields__
    assert "content" not in actual.__dataclass_fields__


@pytest.mark.asyncio
async def test_resolver_rejects_wrong_namespace_and_metadata_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _jpeg()
    reference = _reference(content)
    source = Asset(
        id=reference.asset_id,
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key="internal-synthetic/v1/d02/result/" + reference.asset_id,
        mime_type="image/jpeg",
        byte_size=reference.byte_size,
        width=4,
        height=3,
        sha256=reference.sha256,
        synthetic=True,
        is_ai_generated=True,
        is_ai_modified=False,
    )

    async def unexpected(_: object, __: Asset) -> None:
        raise AssertionError("authority helper must not receive RESULT")

    monkeypatch.setattr(
        "mirror_api.demo_analysis_source_authority.require_d02_source_authority_if_applicable",
        unexpected,
    )
    with pytest.raises(DemoAnalysisSourceAuthorityError, match="D02 source Asset") as error:
        await resolve_admitted_d02_source(_Session(source, []), asset_id=source.id)  # type: ignore[arg-type]
    assert error.value.code == "D02_SOURCE_AUTHORITY_MISMATCH"


@pytest.mark.asyncio
async def test_resolver_rejects_tampered_projection_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _jpeg()
    reference = _reference(content)
    source = Asset(
        id=reference.asset_id,
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key=reference.storage_key,
        mime_type="image/jpeg",
        byte_size=reference.byte_size,
        width=reference.width,
        height=reference.height,
        sha256=reference.sha256,
        synthetic=True,
        is_ai_generated=True,
        is_ai_modified=False,
    )
    authority, objects = _projection_rows(reference)
    objects[(D02SourceCandidate, "c" * 32)].content_digest = None

    async def require(_: object, __: Asset) -> None:
        return None

    monkeypatch.setattr(
        "mirror_api.demo_analysis_source_authority.require_d02_source_authority_if_applicable",
        require,
    )
    with pytest.raises(DemoAnalysisSourceAuthorityError) as error:
        await resolve_admitted_d02_source(
            _Session(source, [authority], objects),
            asset_id=source.id,  # type: ignore[arg-type]
        )
    assert error.value.code == "D02_SOURCE_AUTHORITY_MISMATCH"


@pytest.mark.asyncio
async def test_materialization_replay_load_and_tamper_rejection(tmp_path: Path) -> None:
    content = _jpeg()
    reference = _reference(content)
    storage = DemoLocalPrivateObjectStorage(root=tmp_path)

    await materialize_admitted_d02_source(storage=storage, reference=reference, content=content)
    await materialize_admitted_d02_source(storage=storage, reference=reference, content=content)
    assert await LocalAdmittedD02SourceLoader(storage=storage).load(reference) == content

    with pytest.raises(DemoAnalysisSourceAuthorityError) as error:
        await materialize_admitted_d02_source(
            storage=storage,
            reference=reference,
            content=content[:-1] + bytes([content[-1] ^ 1]),
        )
    assert error.value.code == "D02_SOURCE_DIGEST_MISMATCH"

    payload = tmp_path.joinpath(*reference.storage_key.split("/"), "payload")
    payload.write_bytes(b"not-a-jpeg")
    with pytest.raises(DemoAnalysisSourceAuthorityError) as error:
        await LocalAdmittedD02SourceLoader(storage=storage).load(reference)
    assert error.value.code == "D02_SOURCE_SIZE_MISMATCH"


@pytest.mark.asyncio
async def test_materializer_rejects_existing_path_collision_without_overwrite(
    tmp_path: Path,
) -> None:
    content = _jpeg()
    reference = _reference(content)
    storage = DemoLocalPrivateObjectStorage(root=tmp_path)
    payload = tmp_path.joinpath(*reference.storage_key.split("/"), "payload")
    payload.parent.mkdir(parents=True)
    payload.mkdir()

    with pytest.raises(DemoAnalysisSourceAuthorityError) as error:
        await materialize_admitted_d02_source(storage=storage, reference=reference, content=content)
    assert error.value.code == "STORAGE_OBJECT_INVALID"
    assert payload.is_dir()


@pytest.mark.asyncio
async def test_materializer_rejects_symlink_collision_without_overwrite(tmp_path: Path) -> None:
    content = _jpeg()
    reference = _reference(content)
    storage = DemoLocalPrivateObjectStorage(root=tmp_path)
    payload = tmp_path.joinpath(*reference.storage_key.split("/"), "payload")
    payload.parent.mkdir(parents=True)
    destination = tmp_path / "outside"
    destination.write_bytes(b"outside")
    try:
        os.symlink(destination, payload)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(DemoAnalysisSourceAuthorityError) as error:
        await materialize_admitted_d02_source(storage=storage, reference=reference, content=content)
    assert error.value.code == "STORAGE_OBJECT_INVALID"
    assert destination.read_bytes() == b"outside"


def test_reference_rejects_non_source_namespace() -> None:
    content = _jpeg()
    with pytest.raises(DemoAnalysisSourceAuthorityError):
        _reference(content, asset_id="not-an-asset-id")
