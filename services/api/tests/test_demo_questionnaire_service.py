from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from mirror_api.demo_idempotency import DemoIdempotencyInputError
from mirror_api.demo_models import DemoQuestionnaireRun, DemoSelfState
from mirror_api.demo_posterior import (
    PairwiseChoice,
    PairwiseObservation,
    PosteriorConfig,
    infer_pairwise_posterior,
)
from mirror_api.demo_questionnaire_bank import (
    AdmittedQuestionBank,
    QuestionPairPresentation,
    QuestionSidePresentation,
)
from mirror_api.demo_questionnaire_routing import QuestionPair
from mirror_api.demo_questionnaire_service import (
    DEMO_QUESTIONNAIRE_RUN_SCHEMA,
    CreateDemoQuestionnaireResponse,
    DemoQuestionnaireAuthorityCorruption,
    DemoQuestionnaireConfiguration,
    _authority_digest,
    _initial_posterior,
    _posterior_from_initial,
    _posterior_snapshot,
    _progress,
    _replay_state,
    _require_only_target_dimension_changed,
    _routing_policy_for_run,
)

NOW = datetime(2026, 8, 29, tzinfo=UTC)
ACTOR = "a" * 32
SESSION = "b" * 32
SELF_STATE = "c" * 32
RUN = "d" * 32


def _bank() -> AdmittedQuestionBank:
    config = PosteriorConfig()
    pairs = (
        QuestionPair(
            "pair-jaw-source-a-low",
            "jaw_width",
            15_000,
            "source-a",
            {"jaw_width": 0, "chin_height": 0},
            250_000,
            900_000,
        ),
        QuestionPair(
            "pair-jaw-source-b-high",
            "jaw_width",
            30_000,
            "source-b",
            {"jaw_width": 5_000, "chin_height": 4_000},
            1_000_000,
            900_000,
        ),
        QuestionPair(
            "pair-chin-source-a-low",
            "chin_height",
            15_000,
            "source-a",
            {"jaw_width": 0, "chin_height": 0},
            250_000,
            900_000,
        ),
        QuestionPair(
            "pair-chin-source-b-high",
            "chin_height",
            30_000,
            "source-b",
            {"jaw_width": 5_000, "chin_height": 4_000},
            1_000_000,
            900_000,
        ),
    )
    presentations = {
        pair.pair_id: QuestionPairPresentation(
            question_pair_digest="3" * 64,
            source_asset_id="4" * 32,
            source_checksum="5" * 64,
            left=QuestionSidePresentation(
                result_asset_id="6" * 32,
                result_checksum="7" * 64,
                result_lineage_digest="8" * 64,
                requested_direction="NEGATIVE",
                measured_delta_ppm=-pair.magnitude_ppm,
            ),
            right=QuestionSidePresentation(
                result_asset_id="9" * 32,
                result_checksum="a" * 64,
                result_lineage_digest="b" * 64,
                requested_direction="POSITIVE",
                measured_delta_ppm=pair.magnitude_ppm,
            ),
        )
        for pair in pairs
    }
    return AdmittedQuestionBank(
        pairs,
        MappingProxyType({"jaw_width": 1_000, "chin_height": 1_000}),
        1_000,
        config.posterior_config_digest,
        "e" * 64,
        MappingProxyType({"bank_id": "f" * 32}),
        MappingProxyType(presentations),
    )


def _self_state() -> DemoSelfState:
    payload = {
        "baseline_face_model_id": "1" * 32,
        "demo_actor_id": ACTOR,
        "demo_session_id": SESSION,
        "derivation_version": "demo-self-state-v1",
        "measurements": {"jaw_width": 500, "chin_height": 250},
        "ontology_version": "demo-ontology-v1",
        "reliability": {"jaw_width": 900_000, "chin_height": 800_000},
        "routing_eligibility": {
            "jaw_width": "ROUTING_ELIGIBLE",
            "chin_height": "ROUTING_ELIGIBLE",
        },
        "uncertainty": {"jaw_width": 10_000, "chin_height": 10_000},
        "version": 1,
    }
    return DemoSelfState(
        id=SELF_STATE,
        schema_version="mirror.demo/DemoSelfState/v1",
        canonical_payload=payload,
        content_digest="2" * 64,
        created_at=NOW,
        **payload,
    )


def _run(bank: AdmittedQuestionBank) -> DemoQuestionnaireRun:
    initial = _initial_posterior(bank, PosteriorConfig())
    payload = {
        "algorithm_config_digest": PosteriorConfig().posterior_config_digest,
        "demo_actor_id": ACTOR,
        "demo_session_id": SESSION,
        "initial_posterior": initial,
        "max_questions": 12,
        "question_bank_id": "f" * 32,
        "seed": 7,
        "self_state_id": SELF_STATE,
    }
    return DemoQuestionnaireRun(
        id=RUN,
        schema_version=DEMO_QUESTIONNAIRE_RUN_SCHEMA,
        canonical_payload=payload,
        content_digest=_authority_digest(DEMO_QUESTIONNAIRE_RUN_SCHEMA, payload),
        created_at=NOW,
        **payload,
    )


def test_initial_posterior_is_integer_canonical_and_replays() -> None:
    bank = _bank()
    initial = _initial_posterior(bank, PosteriorConfig())

    assert set(initial) == {"chin_height", "jaw_width"}
    replayed = _posterior_from_initial(initial, ("chin_height", "jaw_width"), PosteriorConfig())
    assert _posterior_snapshot(replayed) == initial
    assert all(result.posterior_mean_ppm == 0 for result in replayed.values())


def test_replay_rejects_tampered_initial_posterior() -> None:
    bank = _bank()
    initial = _initial_posterior(bank, PosteriorConfig())
    initial["jaw_width"] = dict(initial["jaw_width"], posterior_mean_ppm=1)

    with pytest.raises(DemoQuestionnaireAuthorityCorruption):
        _posterior_from_initial(initial, ("chin_height", "jaw_width"), PosteriorConfig())


def test_single_target_response_changes_only_its_dimension() -> None:
    bank = _bank()
    run = _run(bank)
    configuration = DemoQuestionnaireConfiguration()
    state = _replay_state(run, _self_state(), (), bank, configuration)
    before = _posterior_snapshot(state.posteriors)
    pair = bank.pairs[0]
    updated = dict(state.posteriors)
    updated[pair.dimension_id] = infer_pairwise_posterior(
        (
            PairwiseObservation(
                dimension_key=pair.dimension_id,
                left_delta_ppm=-pair.magnitude_ppm,
                right_delta_ppm=pair.magnitude_ppm,
                magnitude_ppm=pair.magnitude_ppm,
                stimulus_config_version=bank.config_digest,
                posterior_config_digest=configuration.posterior.posterior_config_digest,
                choice=PairwiseChoice.RIGHT,
            ),
        ),
        configuration.posterior,
    )
    after = _posterior_snapshot(updated)

    _require_only_target_dimension_changed(before, after, pair.dimension_id)
    assert before["chin_height"] == after["chin_height"]
    assert before["jaw_width"] != after["jaw_width"]


def test_skip_is_excluded_from_posterior_and_coverage() -> None:
    bank = _bank()
    config = PosteriorConfig()
    pair = bank.pairs[0]
    observation = PairwiseObservation(
        dimension_key=pair.dimension_id,
        left_delta_ppm=-pair.magnitude_ppm,
        right_delta_ppm=pair.magnitude_ppm,
        magnitude_ppm=pair.magnitude_ppm,
        stimulus_config_version=bank.config_digest,
        posterior_config_digest=config.posterior_config_digest,
        choice=PairwiseChoice.SKIP,
    )
    posterior = infer_pairwise_posterior((observation,), config)
    progress = _progress(
        ("jaw_width",),
        {"jaw_width": posterior},
        {"jaw_width": (observation,)},
        {"jaw_width": (pair,)},
    )

    assert posterior.posterior_mean_ppm == 0
    assert progress["jaw_width"].valid_answers == 0
    assert progress["jaw_width"].magnitude_ppm_seen == ()
    assert progress["jaw_width"].source_identity_ids_seen == ()


def test_run_question_budget_overrides_global_routing_maximum() -> None:
    bank = _bank()
    run = _run(bank)
    configuration = DemoQuestionnaireConfiguration()

    policy = _routing_policy_for_run(run, configuration.routing)

    assert policy.minimum_questions == 12
    assert policy.maximum_questions == 12
    assert configuration.routing.maximum_questions == 16


def test_response_command_rejects_invalid_public_boundary() -> None:
    with pytest.raises(DemoIdempotencyInputError):
        CreateDemoQuestionnaireResponse(
            ACTOR,
            RUN,
            PairwiseChoice.RIGHT,
            1,
            1,
            0,
            "short",
        ).validate()


def test_authority_digest_rejects_raw_float() -> None:
    with pytest.raises(DemoIdempotencyInputError):
        _authority_digest("mirror.demo/test/v1", {"raw_float": 0.1})
