from __future__ import annotations

import json
from pathlib import Path

from mirror_api import demo_d02_authority as authority
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_acquisition_identity import (
    APPROVED_ENDPOINT_POLICY_DIGEST,
    CREDENTIAL_PROCESS_BOUNDARY_DIGEST,
    M3_PRESCREEN_POLICY_DIGEST,
    PROMPT_POLICY_DIGEST,
    PROVIDER_IDENTITY_DIGEST,
    PROVIDER_RETENTION_POLICY_DIGEST,
    RUN_KEY_DIGEST,
    canonical_digest,
    default_spec_identity,
    m3_prescreen_policy_payload,
    provider_identity_payload,
    run_key_payload,
)
from mirror_api.demo_d02_r2_runtime_forward import build_default_model_identity


def test_default_acquisition_identities_are_exact_and_replayable() -> None:
    identity = default_spec_identity()

    assert PROVIDER_IDENTITY_DIGEST == (
        "e3d94667886b21f80ae30fce1f49bb5a072dd3678506d21091d48ab88029bc05"
    )
    assert M3_PRESCREEN_POLICY_DIGEST == (
        "52b626baf6cd2a0f2867dc3b8bf92446973cafd851752cd5abab04433bee472d"
    )
    assert RUN_KEY_DIGEST == (
        "04c4dacd3199bed812aeef542cea12b52"
        "1689aa58796dd2f0ea20f8a9683e1a2"
    )
    assert PROVIDER_IDENTITY_DIGEST == canonical_digest(
        "mirror.demo/D02AcquisitionProviderIdentity/v1", provider_identity_payload()
    )
    assert M3_PRESCREEN_POLICY_DIGEST == canonical_digest(
        "mirror.demo/D02CandidateM3PrescreenPolicy/v1", m3_prescreen_policy_payload()
    )
    assert RUN_KEY_DIGEST == canonical_digest(
        "mirror.demo/D02AutonomousAcquisitionRunKey/v1", run_key_payload()
    )
    assert identity.runtime_identity_digest == measurement.RUNTIME_MANIFEST_DIGEST
    assert identity.model_identity_digest == build_default_model_identity().identity_digest
    assert identity.qa_policy_digest == authority.RECOVERED_LEGACY_QA_POLICY_CONTENT_DIGEST


def test_provider_identity_replays_only_budget_independent_public_policies() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    authority_path = (
        repository_root
        / "docs"
        / "operations"
        / "P3_P7_D02_R2_GENERATION_CAPABILITY_AUTHORITY.json"
    )
    document = json.loads(authority_path.read_text(encoding="utf-8"))

    assert document["approved_endpoint_policy_digest"] == APPROVED_ENDPOINT_POLICY_DIGEST
    assert document["credential_process_boundary_digest"] == CREDENTIAL_PROCESS_BOUNDARY_DIGEST
    assert document["provider_retention_policy_digest"] == PROVIDER_RETENTION_POLICY_DIGEST
    assert document["prompt_policy_digest"] == PROMPT_POLICY_DIGEST
    payload = provider_identity_payload()
    assert "execution_budget" not in payload
    assert "generation_capability_authority_digest" not in payload


def test_candidate_prescreen_is_provisional_and_requires_formal_reexecution() -> None:
    payload = m3_prescreen_policy_payload()

    assert payload["source_m3_repeat_indices"] == [1]
    assert payload["provisional_only"] is True
    assert payload["formal_source_repeat_count"] == 3
    assert payload["formal_reexecution_required_after_manifest_selection"] is True
    assert payload["admission_authority"] is False
