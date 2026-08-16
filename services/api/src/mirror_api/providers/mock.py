from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Final, Literal

from mirror_api.providers.base import (
    AgeAssuranceResult,
    AgeAssuranceStatus,
    AgentPlan,
    FaceLandmark,
    FaceLandmarkSet,
    FaceObservation,
    GeneratedImagePayload,
    GeometryMeasurement,
    PoseEstimate,
    ProviderCostFact,
    ProviderProvenanceFact,
    ProviderSafetyFact,
    SyntheticGenerationRequest,
    SyntheticGenerationResult,
    SyntheticOutputSpecification,
    SyntheticStorageWriteRequest,
    SyntheticStoredImage,
    SyntheticVisionRequest,
    SyntheticVisionResult,
)

# A 1x1 grayscale PNG. It is a valid, clearly non-human test pattern.
MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES: Final[bytes] = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x00\x00\x00\x00\x3a\x7e\x9b\x55\x00\x00\x00\x0aIDAT\x78\x9c\x63"
    b"\x00\x01\x00\x00\x05\x00\x01\x0d\x0a\x2d\xb4\x00\x00\x00\x00IEND\xae\x42\x60\x82"
)
MOCK_SYNTHETIC_IMAGE_MEDIA_TYPE: Final[Literal["image/png"]] = "image/png"
MOCK_SYNTHETIC_OUTPUT_SPECIFICATION: Final[SyntheticOutputSpecification] = (
    SyntheticOutputSpecification(
        media_type=MOCK_SYNTHETIC_IMAGE_MEDIA_TYPE,
        width=1,
        height=1,
        max_byte_size=len(MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES),
    )
)
MOCK_SYNTHETIC_SAFETY = ProviderSafetyFact(
    policy_reference="mock-safety-policy-v1",
    outcome="passed",
    reason_code="synthetic-nonhuman-test-pattern",
)
MOCK_SYNTHETIC_COST = ProviderCostFact(currency="CNY", amount_micros=0, status="final")
MOCK_SYNTHETIC_PROVENANCE = ProviderProvenanceFact(
    provider_reference="mock-provider-v1",
    model_reference="mock-model-v1",
    model_version_reference="mock-model-version-v1",
    policy_reference="mock-provenance-policy-v1",
    retention_status="not_retained",
    output_rights="internal_evaluation_only",
)


def _stable_id(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}:{value}".encode()).hexdigest()[:24]


class MockSmsProvider:
    """Development provider that records no phone number or verification code."""

    async def send_verification_code(
        self,
        *,
        destination_phone: str,
        verification_code: str,
        request_reference: str,
    ) -> str:
        del destination_phone, verification_code
        return f"local-sms-{_stable_id('sms', request_reference)}"


class MockAgeAssuranceProvider:
    """Deterministic test-only age provider that retains no credential plaintext."""

    def __init__(self, *, fixture_statuses: Mapping[str, AgeAssuranceStatus] | None = None) -> None:
        self._fixture_statuses = dict(fixture_statuses or {})

    @staticmethod
    def fixture_credential_key(credential: str) -> str:
        """Create a non-plaintext key for an explicit test fixture mapping."""

        return _stable_id("age-credential", credential)

    async def verify_credential(
        self, *, credential: str, request_reference: str
    ) -> AgeAssuranceResult:
        status = self._fixture_statuses.get(
            self.fixture_credential_key(credential), "indeterminate"
        )
        return AgeAssuranceResult(
            status=status,
            provider_reference=f"mock-age-{_stable_id('age-reference', request_reference)}",
            provider_version="mock-age-v1",
            policy_version="mock-policy-v1",
        )


class MockVisionProvider:
    async def inspect_synthetic(self, *, request: SyntheticVisionRequest) -> SyntheticVisionResult:
        observation = FaceObservation(
            observation_reference="mock-face-observation-v1",
            landmarks=FaceLandmarkSet(
                coordinate_system="normalized_image_v1",
                landmarks=(
                    FaceLandmark(
                        landmark_code="mock-landmark-center",
                        x=0.5,
                        y=0.5,
                        confidence=1.0,
                    ),
                ),
            ),
            pose=PoseEstimate(yaw_degrees=0.0, pitch_degrees=0.0, roll_degrees=0.0, confidence=1.0),
            geometry_measurements=(
                GeometryMeasurement(
                    measurement_code="mock-geometry-ratio",
                    value=1.0,
                    confidence=1.0,
                    measurement_version="mock-geometry-v1",
                ),
            ),
        )
        return SyntheticVisionResult(
            request_reference=request.request_reference,
            provider_run_reference=f"mock-vision-{_stable_id('vision', request.request_reference)}",
            observations=(observation,),
            safety=MOCK_SYNTHETIC_SAFETY,
            cost=MOCK_SYNTHETIC_COST,
            provenance=MOCK_SYNTHETIC_PROVENANCE,
        )


class MockImageGenerationProvider:
    async def generate_synthetic(
        self, *, request: SyntheticGenerationRequest
    ) -> SyntheticGenerationResult:
        output = request.output_specification
        if (
            output.media_type != MOCK_SYNTHETIC_OUTPUT_SPECIFICATION.media_type
            or output.width != MOCK_SYNTHETIC_OUTPUT_SPECIFICATION.width
            or output.height != MOCK_SYNTHETIC_OUTPUT_SPECIFICATION.height
            or output.max_byte_size < len(MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES)
        ):
            raise ValueError("mock generation does not support the requested output specification")
        if request.generation_parameters or request.seed is not None:
            raise ValueError("mock generation does not support seed or generation parameters")
        return SyntheticGenerationResult(
            request_reference=request.request_reference,
            provider_run_reference=f"mock-image-{_stable_id('image', request.request_reference)}",
            payload=GeneratedImagePayload(
                content=MOCK_SYNTHETIC_NON_HUMAN_PNG_BYTES,
                media_type=MOCK_SYNTHETIC_IMAGE_MEDIA_TYPE,
            ),
            safety=MOCK_SYNTHETIC_SAFETY,
            cost=MOCK_SYNTHETIC_COST,
            provenance=MOCK_SYNTHETIC_PROVENANCE,
            provider_actual_seed=None,
            provider_actual_parameters=(),
            reproducibility_level="BIT_EXACT",
        )


class MockSyntheticObjectStorageProvider:
    """Zero-network, deterministic P2 storage double with no user-object namespace."""

    def __init__(self) -> None:
        self._objects: dict[str, SyntheticStoredImage] = {}

    async def store_generated_image_if_absent(
        self, *, request: SyntheticStorageWriteRequest
    ) -> SyntheticStoredImage:
        payload = request.payload
        result = SyntheticStoredImage(
            storage_reference=request.storage_reference,
            byte_size=payload.byte_size,
            media_type=payload.media_type,
            sha256=hashlib.sha256(payload.content).hexdigest(),
        )
        existing = self._objects.get(request.storage_reference)
        if existing is not None and existing != result:
            raise ValueError("synthetic storage reference already contains different content")
        self._objects[request.storage_reference] = result
        return result


class MockAgentProvider:
    async def create_plan(self, *, intent: str) -> AgentPlan:
        return AgentPlan(
            intent=intent,
            operations=("inspect_only",),
            provider_run_id=f"mock-agent-{_stable_id('agent', intent)}",
        )
