from __future__ import annotations

import socket
from hashlib import sha256
from io import BytesIO
from typing import Literal, cast

import pytest
from PIL import Image

from mirror_api.providers.base import (
    MAX_SYNTHETIC_SEED,
    AgeAssuranceProvider,
    AgeAssuranceResult,
    AgeAssuranceStatus,
    GeneratedImagePayload,
    GenerationBudgetContext,
    GenerationParameter,
    NormalizedSyntheticImagePayload,
    ProviderProvenanceFact,
    SmsProvider,
    SyntheticGenerationRequest,
    SyntheticOutputSpecification,
    SyntheticStorageWriteRequest,
    SyntheticVisionRequest,
)
from mirror_api.providers.mock import (
    MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES,
    MockAgeAssuranceProvider,
    MockAgentProvider,
    MockImageGenerationProvider,
    MockSmsProvider,
    MockSyntheticObjectStorageProvider,
    MockVisionProvider,
)
from mirror_api.providers.tencent import (
    TencentAgeAssuranceCandidateProvider,
    TencentCosProvider,
    TencentImageCandidateProvider,
    TencentSmsProvider,
    TencentSyntheticObjectStorageCandidateProvider,
    TencentVisionCandidateProvider,
)
from mirror_api.storage_keys import internal_synthetic_generated_object_key
from mirror_api.synthetic_dataset.prompt_material import EphemeralPrompt


def _generation_request(
    *,
    request_reference: str,
    generation_parameters: tuple[GenerationParameter, ...] = (),
    seed: int | None = None,
) -> SyntheticGenerationRequest:
    return SyntheticGenerationRequest(
        request_reference=request_reference,
        generation_policy_reference="generation-policy-v1",
        prompt_template_reference="prompt-template-v1",
        output_specification=SyntheticOutputSpecification(
            media_type="image/png",
            width=1,
            height=1,
            max_byte_size=1024,
        ),
        generation_parameters=generation_parameters,
        seed=seed,
        budget=GenerationBudgetContext(
            currency="CNY",
            max_amount_micros=1_000_000,
            pricing_snapshot_reference="pricing-snapshot-v1",
        ),
    )


def _prompt() -> EphemeralPrompt:
    return EphemeralPrompt("clearly adult synthetic non-human fixture")


@pytest.mark.asyncio
async def test_provider_fakes_are_deterministic_and_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("provider attempted external network access")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    sms: SmsProvider = MockSmsProvider()
    vision = MockVisionProvider()
    image = MockImageGenerationProvider()
    agent = MockAgentProvider()

    assert await sms.send_verification_code(
        destination_phone="+8610000000000",
        verification_code="123456",
        request_reference="request-1",
    ) == (
        await sms.send_verification_code(
            destination_phone="+8610000000001",
            verification_code="different",
            request_reference="request-1",
        )
    )
    generation_request = _generation_request(request_reference="generation-request-001")
    generated = await image.generate_synthetic(request=generation_request, prompt=_prompt())
    generated_again = await image.generate_synthetic(request=generation_request, prompt=_prompt())
    assert generated == generated_again
    assert generated.payload.content == MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES
    assert generated.payload.byte_size == len(generated.payload.content)
    image_fixture = Image.open(BytesIO(generated.payload.content))
    image_fixture.load()
    assert (image_fixture.format, image_fixture.mode, image_fixture.size) == ("PNG", "L", (1, 1))
    assert generated.payload.media_type == "image/png"
    assert generated.safety.outcome == "passed"
    assert generated.cost.amount_micros == 0
    assert generated.provenance.retention_status == "not_retained"
    assert generated.provenance.model_version_reference == "mock-model-version-v1"
    assert generated.provider_actual_seed is None
    assert generated.provider_actual_parameters == ()
    assert generated.reproducibility_level == "BIT_EXACT"
    with pytest.raises(ValueError, match="does not support seed or generation parameters"):
        await image.generate_synthetic(
            request=_generation_request(
                request_reference="generation-request-with-seed",
                generation_parameters=(
                    GenerationParameter(parameter_key="guidance-scale", value=7.5),
                ),
                seed=42,
            ),
            prompt=_prompt(),
        )

    vision_request = SyntheticVisionRequest(
        request_reference="vision-request-001",
        normalized_image=NormalizedSyntheticImagePayload(
            normalized_asset_reference="normalized-asset-001",
            content=b"canonical-jpeg-fixture",
            sha256=sha256(b"canonical-jpeg-fixture").hexdigest(),
            media_type="image/jpeg",
        ),
        vision_policy_reference="vision-policy-v1",
    )
    observed = await vision.inspect_synthetic(request=vision_request)
    assert len(observed.observations) == 1
    assert observed.observations[0].landmarks.coordinate_system == "normalized_image_v1"
    assert observed.observations[0].pose.confidence == 1.0

    synthetic_storage = MockSyntheticObjectStorageProvider()
    stored = await synthetic_storage.store_generated_image_if_absent(
        request=SyntheticStorageWriteRequest(
            storage_reference="synthetic-storage-001",
            payload=generated.payload,
            provenance=generated.provenance,
        )
    )
    assert stored.namespace == "internal_synthetic_v1"
    assert stored.sha256 == sha256(generated.payload.content).hexdigest()
    assert "quarantine" not in repr(stored)
    assert "sanitized" not in repr(stored)
    assert (
        await synthetic_storage.inspect_generated_image(storage_reference=stored.storage_reference)
        == stored
    )
    assert (
        b"".join(
            [
                chunk
                async for chunk in synthetic_storage.stream_generated_image(
                    storage_reference=stored.storage_reference
                )
            ]
        )
        == generated.payload.content
    )
    assert (
        await synthetic_storage.delete_generated_image(storage_reference=stored.storage_reference)
        == "deleted"
    )
    assert (
        await synthetic_storage.delete_generated_image(storage_reference=stored.storage_reference)
        == "not_found"
    )
    assert (await agent.create_plan(intent="inspect")).operations == ("inspect_only",)


def test_synthetic_contract_rejects_user_assets_urls_and_unbounded_payloads() -> None:
    with pytest.raises(ValueError, match="only accepts synthetic subjects"):
        SyntheticGenerationRequest(
            request_reference="generation-request-002",
            generation_policy_reference="generation-policy-v1",
            prompt_template_reference="prompt-template-v1",
            output_specification=SyntheticOutputSpecification(
                media_type="image/png", width=1, height=1, max_byte_size=1024
            ),
            generation_parameters=(),
            seed=None,
            budget=GenerationBudgetContext(
                currency="CNY",
                max_amount_micros=1,
                pricing_snapshot_reference="pricing-snapshot-v1",
            ),
            subject_kind=cast(Literal["synthetic"], "user_asset"),
        )
    with pytest.raises(ValueError, match="opaque first-party reference"):
        _generation_request(request_reference="https://untrusted.example/image.jpg")
    with pytest.raises(ValueError, match="size boundary"):
        GeneratedImagePayload(content=b"", media_type="image/jpeg")
    with pytest.raises(ValueError, match="only accepts synthetic subjects"):
        GeneratedImagePayload(
            content=b"synthetic",
            media_type="image/jpeg",
            subject_kind=cast(Literal["synthetic"], "user_asset"),
        )
    with pytest.raises(ValueError, match="media type"):
        GeneratedImagePayload(
            content=b"synthetic", media_type=cast(Literal["image/jpeg"], "text/plain")
        )
    with pytest.raises(ValueError, match="unknown provider retention"):
        ProviderProvenanceFact(
            provider_reference="candidate-provider-v1",
            model_reference="candidate-model-v1",
            model_version_reference="candidate-model-version-v1",
            policy_reference="candidate-policy-v1",
            retention_status=cast(Literal["not_retained"], "unknown"),
            output_rights="internal_evaluation_only",
        )
    with pytest.raises(ValueError, match="generation parameter keys must be unique"):
        SyntheticGenerationRequest(
            request_reference="generation-request-duplicate",
            generation_policy_reference="generation-policy-v1",
            prompt_template_reference="prompt-template-v1",
            output_specification=SyntheticOutputSpecification(
                media_type="image/png", width=1, height=1, max_byte_size=1024
            ),
            generation_parameters=(
                GenerationParameter(parameter_key="guidance-scale", value=1.0),
                GenerationParameter(parameter_key="guidance-scale", value=2.0),
            ),
            seed=0,
            budget=GenerationBudgetContext(
                currency="CNY",
                max_amount_micros=1,
                pricing_snapshot_reference="pricing-snapshot-v1",
            ),
        )
    with pytest.raises(ValueError, match="finite"):
        GenerationParameter(parameter_key="guidance-scale", value=float("nan"))
    with pytest.raises(ValueError, match="bounded non-negative integer"):
        SyntheticGenerationRequest(
            request_reference="generation-request-seed",
            generation_policy_reference="generation-policy-v1",
            prompt_template_reference="prompt-template-v1",
            output_specification=SyntheticOutputSpecification(
                media_type="image/png", width=1, height=1, max_byte_size=1024
            ),
            generation_parameters=(),
            seed=MAX_SYNTHETIC_SEED + 1,
            budget=GenerationBudgetContext(
                currency="CNY",
                max_amount_micros=1,
                pricing_snapshot_reference="pricing-snapshot-v1",
            ),
        )


def test_internal_synthetic_storage_namespace_is_disjoint_from_user_asset_namespaces() -> None:
    key = internal_synthetic_generated_object_key("a" * 32)
    assert key == f"internal-synthetic/v1/{'a' * 32}"
    assert not key.startswith(("quarantine/", "sanitized/", "exports/"))
    with pytest.raises(ValueError, match="opaque 32-character"):
        internal_synthetic_generated_object_key("quarantine/v1/user-asset")


@pytest.mark.asyncio
async def test_mock_age_assurance_is_deterministic_and_minimal() -> None:
    credential = "test-credential-verified"
    rejected_credential = "test-credential-rejected"
    age: AgeAssuranceProvider = MockAgeAssuranceProvider(
        fixture_statuses={
            MockAgeAssuranceProvider.fixture_credential_key(credential): "verified",
            MockAgeAssuranceProvider.fixture_credential_key(rejected_credential): "not_verified",
        }
    )

    result = await age.verify_credential(credential=credential, request_reference="request-1")
    same_request_result = await age.verify_credential(
        credential="a-different-credential", request_reference="request-1"
    )

    assert result.status == "verified"
    assert (
        await age.verify_credential(credential=rejected_credential, request_reference="request-2")
    ).status == "not_verified"
    assert (
        await age.verify_credential(
            credential="unmapped-test-credential", request_reference="request-3"
        )
    ).status == "indeterminate"
    assert result.provider_reference == same_request_result.provider_reference
    assert result.provider_version == "mock-age-v1"
    assert result.policy_version == "mock-policy-v1"
    assert result.expires_at is None
    assert set(AgeAssuranceResult.__dataclass_fields__) == {
        "status",
        "provider_reference",
        "provider_version",
        "policy_version",
        "expires_at",
    }
    assert credential not in repr(vars(age))
    with pytest.raises(ValueError, match="age assurance status"):
        AgeAssuranceResult(
            status=cast(AgeAssuranceStatus, "unknown"),
            provider_reference="reference",
            provider_version="version",
            policy_version="policy",
        )


@pytest.mark.asyncio
async def test_unverified_tencent_candidates_fail_closed_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("provider attempted external network access")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentSmsProvider().send_verification_code(
            destination_phone="+8610000000000",
            verification_code="123456",
            request_reference="request-1",
        )

    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentAgeAssuranceCandidateProvider().verify_credential(
            credential="test-credential", request_reference="request-1"
        )

    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentCosProvider().create_private_upload_grant(
            object_key=f"quarantine/v1/{'b' * 64}",
            content_type="image/png",
            content_length=10,
            checksum_sha256="c" * 64,
        )

    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentCosProvider().create_private_download_grant(
            object_key=f"sanitized/v1/{'d' * 32}", request_reference="asset-reference"
        )

    generation_request = _generation_request(request_reference="generation-request-003")
    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentImageCandidateProvider().generate_synthetic(
            request=generation_request, prompt=_prompt()
        )

    vision_request = SyntheticVisionRequest(
        request_reference="vision-request-003",
        normalized_image=NormalizedSyntheticImagePayload(
            normalized_asset_reference="normalized-asset-003",
            content=b"synthetic",
            sha256=sha256(b"synthetic").hexdigest(),
            media_type="image/jpeg",
        ),
        vision_policy_reference="vision-policy-v1",
    )
    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentVisionCandidateProvider().inspect_synthetic(request=vision_request)

    with pytest.raises(NotImplementedError, match="not verified"):
        await TencentSyntheticObjectStorageCandidateProvider().store_generated_image_if_absent(
            request=SyntheticStorageWriteRequest(
                storage_reference="synthetic-storage-003",
                payload=GeneratedImagePayload(content=b"synthetic", media_type="image/jpeg"),
                provenance=(
                    await MockImageGenerationProvider().generate_synthetic(
                        request=generation_request, prompt=_prompt()
                    )
                ).provenance,
            )
        )
