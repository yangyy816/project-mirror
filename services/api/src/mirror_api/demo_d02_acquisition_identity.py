"""Public, replayable identities for the D02 autonomous acquisition run.

The acquisition ledger must never be bootstrapped with ad-hoc or test-only
digests.  This module binds the already accepted ImageGen control-plane
policies and M3 runtime/model authority to three small D02-only canonical
payloads.  It performs no filesystem, network, Provider, or database access.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Final

from mirror_api import demo_d02_authority as d02_authority
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_r2_runtime_forward import build_default_model_identity
from mirror_api.demo_d02_source_acquisition import D02SpecIdentity
from mirror_api.demo_idempotency import canonical_json_bytes

PROVIDER_IDENTITY_SCHEMA: Final = "mirror.demo/D02AcquisitionProviderIdentity/v1"
M3_PRESCREEN_POLICY_SCHEMA: Final = "mirror.demo/D02CandidateM3PrescreenPolicy/v1"
RUN_KEY_SCHEMA: Final = "mirror.demo/D02AutonomousAcquisitionRunKey/v1"

# These four public digests bind the accepted, prompt-free slices of
# P3_P7_D02_R2_GENERATION_CAPABILITY_AUTHORITY.json.  The obsolete historical
# four-call budget is intentionally not part of the provider identity; ADR-052
# is the authority for the current 50-call pool.
APPROVED_ENDPOINT_POLICY_DIGEST: Final = (
    "dac1c3dcb96732187ae0831b22060451839e86085123ae6030de4357dc12874f"
)
CREDENTIAL_PROCESS_BOUNDARY_DIGEST: Final = (
    "d97603f825b78674f40c4d41da3f7dc3e95ac27057c6b288ba1a1a0964c58866"
)
PROVIDER_RETENTION_POLICY_DIGEST: Final = (
    "2734305501c3d2236d236db25022efbd1d0abd362b4fe343e656ccf2806f5f22"
)
PROMPT_POLICY_DIGEST: Final = "fb32c5b86c45a113084e731a991a4bd70f026837d2cbe5bc6209fdf1c707a87b"


def provider_identity_payload() -> dict[str, object]:
    """Return the budget-independent ImageGen control-plane identity."""

    return {
        "schema_version": PROVIDER_IDENTITY_SCHEMA,
        "provider_interface": "image_gen.imagegen",
        "tool": "CODEX_NATIVE_IMAGEGEN",
        "control_plane_kind": "CODEX_BUILTIN_REMOTE_CONTROL_PLANE",
        "adapter_classification": "OPERATOR_ASSISTED_PRE_RUNTIME_TOOL_NOT_RUNTIME_PROVIDER",
        "input_mode": "TEXT_ONLY_CREATE_NEW",
        "referenced_image_paths_allowed": False,
        "num_last_images_to_include_allowed": False,
        "provider_disclosure_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "model_disclosure_state": "OPAQUE_ACCEPTED_FOR_DEMO_ONLY",
        "production_provider": False,
        "formal_phase_authority": False,
        "approved_endpoint_policy_digest": APPROVED_ENDPOINT_POLICY_DIGEST,
        "credential_process_boundary_digest": CREDENTIAL_PROCESS_BOUNDARY_DIGEST,
        "provider_retention_policy_digest": PROVIDER_RETENTION_POLICY_DIGEST,
        "prompt_policy_digest": PROMPT_POLICY_DIGEST,
    }


def m3_prescreen_policy_payload() -> dict[str, object]:
    """Return the provisional, single-execution Candidate M3 policy."""

    model = build_default_model_identity()
    return {
        "schema_version": M3_PRESCREEN_POLICY_SCHEMA,
        "purpose": "CANDIDATE_LOCAL_PROVISIONAL_SUPPORT_CHECK",
        "runtime_manifest_digest": measurement.RUNTIME_MANIFEST_DIGEST,
        "model_identity_digest": model.identity_digest,
        "model_config_digest": model.config_digest,
        "vision_model_manifest_digest": measurement.VISION_MODEL_MANIFEST_DIGEST,
        "topology_digest": measurement.TOPOLOGY_DIGEST,
        "measurement_config_digest": measurement.MEASUREMENT_CONFIG_DIGEST,
        "source_m3_repeat_indices": [1],
        "required_face_count": 1,
        "required_landmark_count": 478,
        "coordinates_finite_required": True,
        "coordinates_in_bounds_required": True,
        "unsupported_is_content_rejection": True,
        "technical_failure_preserves_candidate": True,
        "provisional_only": True,
        "formal_source_repeat_count": 3,
        "formal_reexecution_required_after_manifest_selection": True,
        "admission_authority": False,
    }


def run_key_payload() -> dict[str, object]:
    """Return the stable preimage for the sole autonomous D02 run."""

    return {
        "schema_version": RUN_KEY_SCHEMA,
        "authorization_id": "D02_AUTONOMOUS_EXECUTION_ENVELOPE_V1",
        "purpose": "D02_FINAL_RUNTIME_GATE",
        "budget_pool_version": "D02_SOURCE_ACQUISITION_BUDGET_POOL_V1",
        "run_cardinality": "POSTGRESQL_SINGLETON",
        "legacy_e3_state": "FAILED_CLOSED",
        "legacy_e4_state": "FAILED_CLOSED",
        "legacy_source_reuse": "FORBIDDEN",
        "history_policy": "FORWARD_REPAIR_ONLY",
    }


def canonical_digest(schema_version: str, payload: Mapping[str, object]) -> str:
    """Hash one D02 identity using the repository canonical JSON boundary."""

    return hashlib.sha256(
        schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


PROVIDER_IDENTITY_DIGEST: Final = canonical_digest(
    PROVIDER_IDENTITY_SCHEMA, provider_identity_payload()
)
M3_PRESCREEN_POLICY_DIGEST: Final = canonical_digest(
    M3_PRESCREEN_POLICY_SCHEMA, m3_prescreen_policy_payload()
)
RUN_KEY_DIGEST: Final = canonical_digest(RUN_KEY_SCHEMA, run_key_payload())


def default_spec_identity() -> D02SpecIdentity:
    """Return the only tracked identity accepted by the autonomous operator."""

    return D02SpecIdentity(
        provider_identity_digest=PROVIDER_IDENTITY_DIGEST,
        runtime_identity_digest=measurement.RUNTIME_MANIFEST_DIGEST,
        model_identity_digest=build_default_model_identity().identity_digest,
        m3_prescreen_policy_digest=M3_PRESCREEN_POLICY_DIGEST,
        qa_policy_digest=d02_authority.RECOVERED_LEGACY_QA_POLICY_CONTENT_DIGEST,
    )
