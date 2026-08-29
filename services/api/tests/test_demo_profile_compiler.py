"""Focused authority tests for the pure Demo P5 profile compiler."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from mirror_api.demo_posterior import (
    ALGORITHM_VERSION,
    RESULT_SCHEMA_VERSION,
    MapLocation,
    PosteriorResult,
)
from mirror_api.demo_profile_compiler import (
    AuthorityEvent,
    ConstraintMode,
    DeltaEvidenceKind,
    DeltaRestraint,
    EventSource,
    EventType,
    ProfileCompilerError,
    ProfileCompilerInput,
    QuestionnaireEvidence,
    SelfStateAnchor,
    SelfStateDimension,
    SelfTransferEvidence,
    SelfTransferOutcome,
    compile_profile,
)


def _digest(value: str) -> str:
    return (value * 64)[:64]


def _posterior(mean: int, confidence: int) -> PosteriorResult:
    return PosteriorResult(
        result_schema_version=RESULT_SCHEMA_VERSION,
        algorithm_version=ALGORITHM_VERSION,
        posterior_config_digest=_digest("a"),
        evidence_digest=_digest("b"),
        posterior_mean_ppm=mean,
        map_location=MapLocation.INTERIOR,
        laplace_sd_ppm=100,
        posterior_sd_ppm=100,
        confidence_ppm=confidence,
        consistency_ppm=1_000_000,
    )


def _input(**changes: object) -> ProfileCompilerInput:
    baseline = ProfileCompilerInput(
        actor_id="actor-a",
        self_state=SelfStateAnchor(_digest("c"), (SelfStateDimension("jaw_width", 12345),)),
        questionnaire=(QuestionnaireEvidence("jaw_width", _posterior(12000, 800000), 1, 0),),
        self_transfer=(),
        authority_events=(),
        compilation_session_id="session-a",
        as_of_event_sequence=10,
    )
    return replace(baseline, **changes)


def _event(
    sequence: int, event_type: EventType, signal: dict[str, object], session: str | None = None
) -> AuthorityEvent:
    return AuthorityEvent.create(
        sequence=sequence,
        event_type=event_type,
        source=EventSource.EXPLICIT_USER_ACTION,
        session_id=session,
        signal=signal,
        source_authority_digest=hashlib.sha256(f"source-{sequence}".encode()).hexdigest(),
    )


def test_questionnaire_delta_is_self_relative_not_absolute_target() -> None:
    result = compile_profile(_input())
    dimension = result.desired_deltas[0]
    assert dimension.desired_delta_ppm == 12000
    assert dimension.self_state_anchor_ppm == 12345
    assert (
        dimension.desired_delta_ppm != dimension.self_state_anchor_ppm + dimension.desired_delta_ppm
    )
    assert dimension.evidence_kind is DeltaEvidenceKind.QUESTIONNAIRE


@pytest.mark.parametrize(
    ("posterior", "directional", "ties", "restraint"),
    [
        (_posterior(0, 0), 0, 0, DeltaRestraint.NO_RESPONSE),
        (_posterior(0, 0), 0, 1, DeltaRestraint.TIE_ONLY),
        (_posterior(12000, 0), 1, 0, DeltaRestraint.INSUFFICIENT_CONFIDENCE),
    ],
)
def test_no_valid_or_tie_only_questionnaire_is_restrained(
    posterior: PosteriorResult, directional: int, ties: int, restraint: DeltaRestraint
) -> None:
    result = compile_profile(
        _input(questionnaire=(QuestionnaireEvidence("jaw_width", posterior, directional, ties),))
    )
    dimension = result.desired_deltas[0]
    assert (dimension.desired_delta_ppm, dimension.confidence_ppm, dimension.restraint) == (
        0,
        0,
        restraint,
    )


def test_accepted_verified_self_transfer_overrides_conflicting_questionnaire() -> None:
    transfer = SelfTransferEvidence(
        "jaw_width", -7000, 900000, True, SelfTransferOutcome.PASS, _digest("d")
    )
    result = compile_profile(_input(self_transfer=(transfer,)))
    dimension = result.desired_deltas[0]
    assert (dimension.desired_delta_ppm, dimension.evidence_kind) == (
        -7000,
        DeltaEvidenceKind.SELF_TRANSFER,
    )


@pytest.mark.parametrize("outcome", (SelfTransferOutcome.FAIL, SelfTransferOutcome.HUMAN_REVIEW))
def test_rejected_or_unverified_self_transfer_does_not_strengthen_profile(
    outcome: SelfTransferOutcome,
) -> None:
    transfer = SelfTransferEvidence("jaw_width", -7000, 900000, False, outcome, _digest("d"))
    result = compile_profile(_input(self_transfer=(transfer,)))
    assert result.desired_deltas[0].desired_delta_ppm == 12000


def test_only_explicit_style_selection_creates_style_preferences() -> None:
    events = (
        _event(
            1,
            EventType.EXPLICIT_STYLE_SELECTION,
            {"style_key": "editorial", "negative_style_key": "retro"},
        ),
    )
    result = compile_profile(_input(authority_events=events))
    assert result.style_preferences == ("editorial",)
    assert result.negative_style_evidence == ("retro",)


def test_persistent_lock_requires_explicit_unlock_and_session_does_not_remove_it() -> None:
    events = (
        _event(
            1,
            EventType.FEATURE_LOCKED,
            {
                "constraint_scope": "PERSISTENT",
                "dimension_key": "jaw_width",
                "minimum_ppm": -1,
                "maximum_ppm": 1,
            },
        ),
        _event(
            2,
            EventType.TEMPORARY_SESSION_OVERRIDE,
            {"dimension_key": "jaw_width", "minimum_ppm": 0, "maximum_ppm": 0},
            "session-a",
        ),
    )
    result = compile_profile(_input(authority_events=events))
    assert result.persistent_constraints.locks[0].minimum_ppm == -1
    assert result.persistent_constraints.locks[0].mode is ConstraintMode.PRESERVE
    assert result.session_override_constraints.locks[0].minimum_ppm == 0
    assert result.session_override_constraints.locks[0].mode is ConstraintMode.ALLOW_CHANGE
    unlocked = compile_profile(
        _input(
            authority_events=(
                *events,
                _event(
                    3,
                    EventType.FEATURE_UNLOCKED,
                    {"constraint_scope": "PERSISTENT", "dimension_key": "jaw_width"},
                ),
            )
        )
    )
    assert unlocked.persistent_constraints.locks == ()


def test_session_overrides_only_apply_to_matching_session() -> None:
    events = (
        _event(
            1,
            EventType.FEATURE_LOCKED,
            {"constraint_scope": "SESSION_OVERRIDE", "dimension_key": "jaw_width"},
            "session-b",
        ),
    )
    assert compile_profile(_input(authority_events=events)).session_override_constraints.locks == ()


def test_session_override_without_event_session_fails_closed() -> None:
    event = _event(
        1,
        EventType.FEATURE_LOCKED,
        {"constraint_scope": "SESSION_OVERRIDE", "dimension_key": "jaw_width"},
    )
    with pytest.raises(ProfileCompilerError, match="requires an event session"):
        compile_profile(_input(authority_events=(event,)))


def test_explicit_intensity_and_prohibited_operation_are_preserved() -> None:
    events = (
        _event(
            1,
            EventType.MAXIMUM_INTENSITY_CHANGED,
            {
                "constraint_scope": "PERSISTENT",
                "target_key": "geometry",
                "maximum_intensity_ppm": 500000,
            },
        ),
        _event(
            2,
            EventType.PROHIBITED_OPERATION_ADDED,
            {"constraint_scope": "PERSISTENT", "operation": "GENERATIVE"},
        ),
    )
    constraints = compile_profile(_input(authority_events=events)).persistent_constraints
    assert constraints.maximum_intensity_ppm == (("geometry", 500000),)
    assert constraints.prohibited_operations == ("GENERATIVE",)


@pytest.mark.parametrize("bad", [True, 1.5])
def test_integer_authority_rejects_bool_and_float(bad: object) -> None:
    with pytest.raises(ProfileCompilerError):
        SelfStateDimension("jaw_width", bad)  # type: ignore[arg-type]


def test_digest_sequence_and_conflicting_authority_fail_closed() -> None:
    second = _event(
        2,
        EventType.FEATURE_LOCKED,
        {"constraint_scope": "PERSISTENT", "dimension_key": "jaw_width"},
    )
    assert compile_profile(_input(authority_events=(second,))).compilation_watermark
    with pytest.raises(ProfileCompilerError, match="strictly increasing"):
        _input(authority_events=(second, second))
    with pytest.raises(ProfileCompilerError, match="digest"):
        AuthorityEvent(
            sequence=1,
            event_type=EventType.FEATURE_LOCKED,
            source=EventSource.EXPLICIT_USER_ACTION,
            session_id=None,
            signal={"dimension_key": "jaw_width"},
            source_authority_digest=_digest("f"),
            event_digest=_digest("e"),
        )


def test_source_authority_digest_is_bound_and_cannot_be_reused() -> None:
    first = _event(
        1,
        EventType.FEATURE_LOCKED,
        {"constraint_scope": "PERSISTENT", "dimension_key": "jaw_width"},
    )
    rebound = AuthorityEvent.create(
        sequence=1,
        event_type=first.event_type,
        source=first.source,
        session_id=first.session_id,
        signal=first.signal,
        source_authority_digest=_digest("a"),
    )
    assert rebound.event_digest != first.event_digest
    duplicate_source = AuthorityEvent.create(
        sequence=2,
        event_type=EventType.FEATURE_UNLOCKED,
        source=EventSource.EXPLICIT_USER_ACTION,
        session_id=None,
        signal={"constraint_scope": "PERSISTENT", "dimension_key": "jaw_width"},
        source_authority_digest=first.source_authority_digest,
    )
    with pytest.raises(ProfileCompilerError, match="source event digest is duplicated"):
        _input(authority_events=(first, duplicate_source))


def test_replay_is_byte_identical_and_input_mutation_changes_digest() -> None:
    profile_input = _input(
        authority_events=(
            _event(1, EventType.EXPLICIT_STYLE_SELECTION, {"style_key": "editorial"}),
        )
    )
    first = compile_profile(profile_input)
    second = compile_profile(profile_input)
    assert first == second
    assert first.compilation_digest == second.compilation_digest
    changed = compile_profile(
        _input(questionnaire=(QuestionnaireEvidence("jaw_width", _posterior(13000, 800000), 1, 0),))
    )
    assert changed.input_digest != first.input_digest


def test_zero_map_with_directional_confidence_remains_questionnaire_evidence() -> None:
    result = compile_profile(
        _input(questionnaire=(QuestionnaireEvidence("jaw_width", _posterior(0, 500000), 1, 0),))
    )
    assert result.desired_deltas[0].evidence_kind is DeltaEvidenceKind.QUESTIONNAIRE
    assert result.desired_deltas[0].restraint is DeltaRestraint.NONE


def test_zero_confidence_transfer_falls_back_to_questionnaire() -> None:
    transfer = SelfTransferEvidence(
        "jaw_width", -7000, 0, True, SelfTransferOutcome.PASS, _digest("d")
    )
    result = compile_profile(_input(self_transfer=(transfer,)))
    assert result.desired_deltas[0].evidence_kind is DeltaEvidenceKind.QUESTIONNAIRE


def test_evidence_dimension_must_be_present_in_self_state() -> None:
    with pytest.raises(ProfileCompilerError, match="must exist in SelfState"):
        _input(questionnaire=(QuestionnaireEvidence("nose_width", _posterior(1000, 1000), 1, 0),))


def test_persistent_scope_does_not_depend_on_event_session() -> None:
    event = _event(
        1,
        EventType.FEATURE_LOCKED,
        {"constraint_scope": "PERSISTENT", "dimension_key": "jaw_width"},
        "session-a",
    )
    result = compile_profile(_input(authority_events=(event,)))
    assert result.persistent_constraints.locks[0].mode is ConstraintMode.PRESERVE
    assert result.session_override_constraints.locks == ()


def test_actor_and_as_of_change_watermark_and_compilation_digest() -> None:
    baseline = compile_profile(_input())
    different_actor = compile_profile(_input(actor_id="actor-b"))
    different_as_of = compile_profile(_input(as_of_event_sequence=11))
    assert baseline.compilation_watermark != different_actor.compilation_watermark
    assert baseline.compilation_watermark != different_as_of.compilation_watermark
    assert baseline.compilation_digest != different_actor.compilation_digest


def test_reordered_authority_collections_fail_closed() -> None:
    dimensions = (
        SelfStateDimension("nose_width", 0),
        SelfStateDimension("jaw_width", 0),
    )
    with pytest.raises(ProfileCompilerError, match="sorted"):
        SelfStateAnchor(_digest("e"), dimensions)
    with pytest.raises(ProfileCompilerError, match="sorted"):
        _input(
            self_state=SelfStateAnchor(
                _digest("e"),
                (SelfStateDimension("jaw_width", 0), SelfStateDimension("nose_width", 0)),
            ),
            questionnaire=(
                QuestionnaireEvidence("nose_width", _posterior(1000, 1000), 1, 0),
                QuestionnaireEvidence("jaw_width", _posterior(1000, 1000), 1, 0),
            ),
        )
