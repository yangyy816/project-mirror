"""Pure, deterministic P5 profile compiler for Demo-only authority inputs.

The compiler intentionally emits self-relative deltas only.  ``SelfState``
anchors are included in the authority digest and output for provenance, but
are never added to a desired delta to make an absolute facial target.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from mirror_api.demo_posterior import PPM, PosteriorResult, canonical_json_bytes

COMPILER_VERSION: Final = "demo-profile-compiler-v1"
COMPILATION_SCHEMA_VERSION: Final = "mirror.demo/ProfileCompilation/v1"
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_OPERATION_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,47}$")


class ProfileCompilerError(ValueError):
    """A profile compilation input is malformed or internally inconsistent."""


class EventType(StrEnum):
    EXPLICIT_STYLE_SELECTION = "EXPLICIT_STYLE_SELECTION"
    FEATURE_LOCKED = "FEATURE_LOCKED"
    FEATURE_UNLOCKED = "FEATURE_UNLOCKED"
    TEMPORARY_SESSION_OVERRIDE = "TEMPORARY_SESSION_OVERRIDE"
    MAXIMUM_INTENSITY_CHANGED = "MAXIMUM_INTENSITY_CHANGED"
    PROHIBITED_OPERATION_ADDED = "PROHIBITED_OPERATION_ADDED"


class EventSource(StrEnum):
    EXPLICIT_USER_ACTION = "EXPLICIT_USER_ACTION"
    QUESTIONNAIRE = "QUESTIONNAIRE"
    SELF_TRANSFER = "SELF_TRANSFER"


class SelfTransferOutcome(StrEnum):
    PASS = "PASS"  # noqa: S105 - verifier outcome, not a credential.
    FAIL = "FAIL"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class DeltaEvidenceKind(StrEnum):
    QUESTIONNAIRE = "QUESTIONNAIRE"
    SELF_TRANSFER = "SELF_TRANSFER"
    RESTRAINED = "RESTRAINED"


class DeltaRestraint(StrEnum):
    NONE = "NONE"
    NO_RESPONSE = "NO_RESPONSE"
    TIE_ONLY = "TIE_ONLY"
    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"


class ConstraintMode(StrEnum):
    PRESERVE = "PRESERVE"
    ALLOW_CHANGE = "ALLOW_CHANGE"


@dataclass(frozen=True)
class SelfStateDimension:
    dimension_key: str
    anchor_ppm: int

    def __post_init__(self) -> None:
        _require_key(self.dimension_key, "dimension_key")
        _require_int(self.anchor_ppm, "anchor_ppm", minimum=-PPM, maximum=PPM)

    def canonical_payload(self) -> dict[str, object]:
        return {"anchor_ppm": self.anchor_ppm, "dimension_key": self.dimension_key}


@dataclass(frozen=True)
class SelfStateAnchor:
    self_state_digest: str
    dimensions: tuple[SelfStateDimension, ...]

    def __post_init__(self) -> None:
        _require_digest(self.self_state_digest, "self_state_digest")
        if not isinstance(self.dimensions, tuple) or any(
            not isinstance(item, SelfStateDimension) for item in self.dimensions
        ):
            raise ProfileCompilerError(
                "self state dimensions must be a tuple of SelfStateDimension values"
            )
        _require_unique_dimensions(self.dimensions, "self state dimensions")
        _require_sorted_keys(
            (item.dimension_key for item in self.dimensions), "self state dimensions"
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "dimensions": [item.canonical_payload() for item in self.dimensions],
            "self_state_digest": self.self_state_digest,
        }


@dataclass(frozen=True)
class QuestionnaireEvidence:
    dimension_key: str
    posterior: PosteriorResult
    directional_response_count: int
    indistinguishable_response_count: int

    def __post_init__(self) -> None:
        _require_key(self.dimension_key, "dimension_key")
        if not isinstance(self.posterior, PosteriorResult):
            raise ProfileCompilerError("questionnaire posterior must be a PosteriorResult")
        _require_int(
            self.directional_response_count,
            "directional_response_count",
            minimum=0,
            maximum=2**31 - 1,
        )
        _require_int(
            self.indistinguishable_response_count,
            "indistinguishable_response_count",
            minimum=0,
            maximum=2**31 - 1,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "dimension_key": self.dimension_key,
            "directional_response_count": self.directional_response_count,
            "indistinguishable_response_count": self.indistinguishable_response_count,
            "posterior": self.posterior.canonical_payload(),
        }


@dataclass(frozen=True)
class SelfTransferEvidence:
    dimension_key: str
    desired_delta_ppm: int
    confidence_ppm: int
    accepted: bool
    verifier_outcome: SelfTransferOutcome
    evidence_digest: str

    def __post_init__(self) -> None:
        _require_key(self.dimension_key, "dimension_key")
        _require_int(self.desired_delta_ppm, "desired_delta_ppm", minimum=-PPM, maximum=PPM)
        _require_int(self.confidence_ppm, "confidence_ppm", minimum=0, maximum=PPM)
        if type(self.accepted) is not bool:
            raise ProfileCompilerError("accepted must be a bool")
        if not isinstance(self.verifier_outcome, SelfTransferOutcome):
            raise ProfileCompilerError("verifier_outcome is unsupported")
        _require_digest(self.evidence_digest, "evidence_digest")

    @property
    def is_accepted_authority(self) -> bool:
        return self.accepted and self.verifier_outcome is SelfTransferOutcome.PASS

    def canonical_payload(self) -> dict[str, object]:
        return {
            "acceptance": "ACCEPTED" if self.accepted else "REJECTED",
            "confidence_ppm": self.confidence_ppm,
            "desired_delta_ppm": self.desired_delta_ppm,
            "dimension_key": self.dimension_key,
            "evidence_digest": self.evidence_digest,
            "verifier_outcome": self.verifier_outcome.value,
        }


@dataclass(frozen=True)
class AuthorityEvent:
    """A canonical explicit action; signals are deliberately scalar-only."""

    sequence: int
    event_type: EventType
    source: EventSource
    session_id: str | None
    signal: Mapping[str, object]
    source_authority_digest: str
    event_digest: str

    def __post_init__(self) -> None:
        _require_int(self.sequence, "sequence", minimum=1, maximum=2**63 - 1)
        if not isinstance(self.event_type, EventType) or not isinstance(self.source, EventSource):
            raise ProfileCompilerError("event type or source is unsupported")
        if self.session_id is not None:
            _require_identifier(self.session_id, "session_id")
        if not isinstance(self.signal, Mapping):
            raise ProfileCompilerError("event signal must be a mapping")
        normalized = _normalize_signal(self.signal)
        object.__setattr__(self, "signal", MappingProxyType(normalized))
        _require_digest(self.source_authority_digest, "source_authority_digest")
        _require_digest(self.event_digest, "event_digest")
        if self.event_digest != self.expected_digest:
            raise ProfileCompilerError("event digest does not match its canonical payload")

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        event_type: EventType,
        source: EventSource,
        session_id: str | None,
        signal: Mapping[str, object],
        source_authority_digest: str,
    ) -> AuthorityEvent:
        payload = _event_payload(
            sequence,
            event_type,
            source,
            session_id,
            _normalize_signal(signal),
            source_authority_digest,
        )
        return cls(
            sequence=sequence,
            event_type=event_type,
            source=source,
            session_id=session_id,
            signal=signal,
            source_authority_digest=source_authority_digest,
            event_digest=hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
        )

    @property
    def expected_digest(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.canonical_payload())).hexdigest()

    def canonical_payload(self) -> dict[str, object]:
        return _event_payload(
            self.sequence,
            self.event_type,
            self.source,
            self.session_id,
            self.signal,
            self.source_authority_digest,
        )


@dataclass(frozen=True)
class ProfileCompilerInput:
    actor_id: str
    self_state: SelfStateAnchor
    questionnaire: tuple[QuestionnaireEvidence, ...]
    self_transfer: tuple[SelfTransferEvidence, ...]
    authority_events: tuple[AuthorityEvent, ...]
    compilation_session_id: str | None
    as_of_event_sequence: int

    def __post_init__(self) -> None:
        _require_identifier(self.actor_id, "actor_id")
        if not isinstance(self.self_state, SelfStateAnchor):
            raise ProfileCompilerError("self_state must be a SelfStateAnchor")
        if self.compilation_session_id is not None:
            _require_identifier(self.compilation_session_id, "compilation_session_id")
        if not isinstance(self.questionnaire, tuple) or any(
            not isinstance(item, QuestionnaireEvidence) for item in self.questionnaire
        ):
            raise ProfileCompilerError(
                "questionnaire evidence must be a tuple of QuestionnaireEvidence values"
            )
        if not isinstance(self.self_transfer, tuple) or any(
            not isinstance(item, SelfTransferEvidence) for item in self.self_transfer
        ):
            raise ProfileCompilerError(
                "self-transfer evidence must be a tuple of SelfTransferEvidence values"
            )
        if not isinstance(self.authority_events, tuple):
            raise ProfileCompilerError("authority events must be a tuple")
        _require_unique_values(
            (item.dimension_key for item in self.questionnaire), "questionnaire dimensions"
        )
        _require_sorted_keys(
            (item.dimension_key for item in self.questionnaire), "questionnaire dimensions"
        )
        _require_unique_values(
            (item.dimension_key for item in self.self_transfer), "self-transfer dimensions"
        )
        _require_sorted_keys(
            (item.dimension_key for item in self.self_transfer), "self-transfer dimensions"
        )
        _require_int(
            self.as_of_event_sequence, "as_of_event_sequence", minimum=0, maximum=2**63 - 1
        )
        _validate_events(self.authority_events, self.as_of_event_sequence)
        anchor_keys = {item.dimension_key for item in self.self_state.dimensions}
        evidence_keys = {item.dimension_key for item in self.questionnaire} | {
            item.dimension_key for item in self.self_transfer
        }
        if not evidence_keys <= anchor_keys:
            raise ProfileCompilerError(
                "questionnaire and self-transfer dimensions must exist in SelfState"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "actor_id": self.actor_id,
            "as_of_event_sequence": self.as_of_event_sequence,
            "authority_events": [
                item.canonical_payload() | {"event_digest": item.event_digest}
                for item in self.authority_events
            ],
            "compilation_session_id": self.compilation_session_id,
            "questionnaire": [item.canonical_payload() for item in self.questionnaire],
            "self_state": self.self_state.canonical_payload(),
            "self_transfer": [item.canonical_payload() for item in self.self_transfer],
        }


@dataclass(frozen=True)
class DesiredDeltaDimension:
    dimension_key: str
    desired_delta_ppm: int
    confidence_ppm: int
    evidence_kind: DeltaEvidenceKind
    restraint: DeltaRestraint
    evidence_digest: str
    self_state_anchor_ppm: int

    def __post_init__(self) -> None:
        _require_key(self.dimension_key, "dimension_key")
        _require_int(self.desired_delta_ppm, "desired_delta_ppm", minimum=-PPM, maximum=PPM)
        _require_int(self.confidence_ppm, "confidence_ppm", minimum=0, maximum=PPM)
        _require_int(self.self_state_anchor_ppm, "self_state_anchor_ppm", minimum=-PPM, maximum=PPM)
        if not isinstance(self.evidence_kind, DeltaEvidenceKind) or not isinstance(
            self.restraint, DeltaRestraint
        ):
            raise ProfileCompilerError("desired delta evidence or restraint is unsupported")
        _require_digest(self.evidence_digest, "evidence_digest")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "confidence_ppm": self.confidence_ppm,
            "desired_delta_ppm": self.desired_delta_ppm,
            "dimension_key": self.dimension_key,
            "evidence_digest": self.evidence_digest,
            "evidence_kind": self.evidence_kind.value,
            "restraint": self.restraint.value,
            "self_state_anchor_ppm": self.self_state_anchor_ppm,
        }


@dataclass(frozen=True)
class FeatureConstraint:
    dimension_key: str
    mode: ConstraintMode
    minimum_ppm: int | None
    maximum_ppm: int | None

    def __post_init__(self) -> None:
        _require_key(self.dimension_key, "dimension_key")
        if not isinstance(self.mode, ConstraintMode):
            raise ProfileCompilerError("feature constraint mode is unsupported")
        if self.minimum_ppm is not None:
            _require_int(self.minimum_ppm, "minimum_ppm", minimum=-PPM, maximum=PPM)
        if self.maximum_ppm is not None:
            _require_int(self.maximum_ppm, "maximum_ppm", minimum=-PPM, maximum=PPM)
        if (
            self.minimum_ppm is not None
            and self.maximum_ppm is not None
            and self.minimum_ppm > self.maximum_ppm
        ):
            raise ProfileCompilerError("minimum_ppm must not exceed maximum_ppm")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "dimension_key": self.dimension_key,
            "maximum_ppm": self.maximum_ppm,
            "minimum_ppm": self.minimum_ppm,
            "mode": self.mode.value,
        }


@dataclass(frozen=True)
class ConstraintSet:
    locks: tuple[FeatureConstraint, ...]
    maximum_intensity_ppm: tuple[tuple[str, int], ...]
    prohibited_operations: tuple[str, ...]

    def __post_init__(self) -> None:
        lock_keys = tuple(item.dimension_key for item in self.locks)
        if lock_keys != tuple(sorted(lock_keys)) or len(set(lock_keys)) != len(lock_keys):
            raise ProfileCompilerError("constraint locks must be unique and sorted")
        if self.maximum_intensity_ppm != tuple(sorted(self.maximum_intensity_ppm)):
            raise ProfileCompilerError("maximum intensity constraints must be sorted")
        for key, value in self.maximum_intensity_ppm:
            _require_key(key, "maximum intensity key")
            _require_int(value, "maximum_intensity_ppm", minimum=0, maximum=PPM)
        if self.prohibited_operations != tuple(sorted(set(self.prohibited_operations))):
            raise ProfileCompilerError("prohibited operations must be unique and sorted")
        for operation in self.prohibited_operations:
            if _OPERATION_PATTERN.fullmatch(operation) is None:
                raise ProfileCompilerError("prohibited operation is invalid")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "locks": [item.canonical_payload() for item in self.locks],
            "maximum_intensity_ppm": [[key, value] for key, value in self.maximum_intensity_ppm],
            "prohibited_operations": list(self.prohibited_operations),
        }


@dataclass(frozen=True)
class ProfileCompilation:
    actor_id: str
    as_of_event_sequence: int
    desired_deltas: tuple[DesiredDeltaDimension, ...]
    style_preferences: tuple[str, ...]
    negative_style_evidence: tuple[str, ...]
    persistent_constraints: ConstraintSet
    session_override_constraints: ConstraintSet
    compilation_watermark: str
    compiler_digest: str
    config_digest: str
    input_digest: str
    compilation_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.actor_id, "actor_id")
        _require_int(
            self.as_of_event_sequence, "as_of_event_sequence", minimum=0, maximum=2**63 - 1
        )
        _require_digest(self.compilation_watermark, "compilation_watermark")
        for digest_name, digest in (
            ("compiler_digest", self.compiler_digest),
            ("config_digest", self.config_digest),
            ("input_digest", self.input_digest),
            ("compilation_digest", self.compilation_digest),
        ):
            _require_digest(digest, digest_name)
        keys = tuple(item.dimension_key for item in self.desired_deltas)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ProfileCompilerError("desired delta dimensions must be unique and sorted")
        if self.style_preferences != tuple(sorted(set(self.style_preferences))):
            raise ProfileCompilerError("style preferences must be unique and sorted")
        if self.negative_style_evidence != tuple(sorted(set(self.negative_style_evidence))):
            raise ProfileCompilerError("negative style evidence must be unique and sorted")
        if not isinstance(self.persistent_constraints, ConstraintSet) or not isinstance(
            self.session_override_constraints, ConstraintSet
        ):
            raise ProfileCompilerError("compilation constraints must be ConstraintSet values")
        if (
            self.compilation_digest
            != hashlib.sha256(canonical_json_bytes(self.canonical_payload())).hexdigest()
        ):
            raise ProfileCompilerError("compilation digest does not match canonical payload")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "actor_id": self.actor_id,
            "as_of_event_sequence": self.as_of_event_sequence,
            "compilation_watermark": self.compilation_watermark,
            "compiler_digest": self.compiler_digest,
            "config_digest": self.config_digest,
            "desired_deltas": [item.canonical_payload() for item in self.desired_deltas],
            "input_digest": self.input_digest,
            "negative_style_evidence": list(self.negative_style_evidence),
            "persistent_constraints": self.persistent_constraints.canonical_payload(),
            "session_override_constraints": self.session_override_constraints.canonical_payload(),
            "style_preferences": list(self.style_preferences),
        }


def compile_profile(profile_input: ProfileCompilerInput) -> ProfileCompilation:
    """Compile bounded authority without mutation, time, floats, or population priors."""

    if not isinstance(profile_input, ProfileCompilerInput):
        raise ProfileCompilerError("profile_input must be a ProfileCompilerInput")
    compiler_digest = hashlib.sha256(
        canonical_json_bytes(
            {"compiler_version": COMPILER_VERSION, "schema_version": COMPILATION_SCHEMA_VERSION}
        )
    ).hexdigest()
    config_digest = hashlib.sha256(
        canonical_json_bytes(
            {
                "compiler_version": COMPILER_VERSION,
                "policy": "self-relative-explicit-authority-no-population-prior-v1",
            }
        )
    ).hexdigest()
    input_digest = hashlib.sha256(
        canonical_json_bytes(profile_input.canonical_payload())
    ).hexdigest()
    watermark = hashlib.sha256(
        canonical_json_bytes(
            {
                "actor_id": profile_input.actor_id,
                "as_of_event_sequence": profile_input.as_of_event_sequence,
                "compiler_version": COMPILER_VERSION,
                "config_digest": config_digest,
                "input_digest": input_digest,
            }
        )
    ).hexdigest()
    anchors = {item.dimension_key: item.anchor_ppm for item in profile_input.self_state.dimensions}
    questionnaire = {item.dimension_key: item for item in profile_input.questionnaire}
    transfer = {item.dimension_key: item for item in profile_input.self_transfer}
    dimensions = tuple(sorted(anchors))
    desired_deltas = tuple(
        _compile_dimension(key, anchors[key], questionnaire.get(key), transfer.get(key))
        for key in dimensions
    )
    persistent, session = _compile_constraints(
        profile_input.authority_events, profile_input.compilation_session_id
    )
    style_preferences, negative_styles = _compile_styles(profile_input.authority_events)
    provisional = {
        "actor_id": profile_input.actor_id,
        "as_of_event_sequence": profile_input.as_of_event_sequence,
        "compilation_watermark": watermark,
        "compiler_digest": compiler_digest,
        "config_digest": config_digest,
        "desired_deltas": [item.canonical_payload() for item in desired_deltas],
        "input_digest": input_digest,
        "negative_style_evidence": list(negative_styles),
        "persistent_constraints": persistent.canonical_payload(),
        "session_override_constraints": session.canonical_payload(),
        "style_preferences": list(style_preferences),
    }
    compilation_digest = hashlib.sha256(canonical_json_bytes(provisional)).hexdigest()
    return ProfileCompilation(
        actor_id=profile_input.actor_id,
        as_of_event_sequence=profile_input.as_of_event_sequence,
        desired_deltas=desired_deltas,
        style_preferences=style_preferences,
        negative_style_evidence=negative_styles,
        persistent_constraints=persistent,
        session_override_constraints=session,
        compilation_watermark=watermark,
        compiler_digest=compiler_digest,
        config_digest=config_digest,
        input_digest=input_digest,
        compilation_digest=compilation_digest,
    )


def _compile_dimension(
    dimension_key: str,
    anchor_ppm: int,
    questionnaire: QuestionnaireEvidence | None,
    transfer: SelfTransferEvidence | None,
) -> DesiredDeltaDimension:
    if transfer is not None and transfer.is_accepted_authority and transfer.confidence_ppm > 0:
        return DesiredDeltaDimension(
            dimension_key,
            transfer.desired_delta_ppm,
            transfer.confidence_ppm,
            DeltaEvidenceKind.SELF_TRANSFER,
            DeltaRestraint.NONE,
            transfer.evidence_digest,
            anchor_ppm,
        )
    if questionnaire is None:
        digest = hashlib.sha256(
            canonical_json_bytes({"dimension_key": dimension_key, "reason": "no_response"})
        ).hexdigest()
        return DesiredDeltaDimension(
            dimension_key,
            0,
            0,
            DeltaEvidenceKind.RESTRAINED,
            DeltaRestraint.NO_RESPONSE,
            digest,
            anchor_ppm,
        )
    posterior = questionnaire.posterior
    if (
        questionnaire.directional_response_count == 0
        and questionnaire.indistinguishable_response_count == 0
    ):
        return DesiredDeltaDimension(
            dimension_key,
            0,
            0,
            DeltaEvidenceKind.RESTRAINED,
            DeltaRestraint.NO_RESPONSE,
            posterior.evidence_digest,
            anchor_ppm,
        )
    if questionnaire.directional_response_count == 0:
        return DesiredDeltaDimension(
            dimension_key,
            0,
            0,
            DeltaEvidenceKind.RESTRAINED,
            DeltaRestraint.TIE_ONLY,
            posterior.evidence_digest,
            anchor_ppm,
        )
    if posterior.confidence_ppm == 0:
        return DesiredDeltaDimension(
            dimension_key,
            0,
            0,
            DeltaEvidenceKind.RESTRAINED,
            DeltaRestraint.INSUFFICIENT_CONFIDENCE,
            posterior.evidence_digest,
            anchor_ppm,
        )
    return DesiredDeltaDimension(
        dimension_key,
        posterior.posterior_mean_ppm,
        posterior.confidence_ppm,
        DeltaEvidenceKind.QUESTIONNAIRE,
        DeltaRestraint.NONE,
        posterior.evidence_digest,
        anchor_ppm,
    )


def _compile_styles(events: tuple[AuthorityEvent, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    styles: set[str] = set()
    negatives: set[str] = set()
    for event in events:
        if event.event_type is EventType.EXPLICIT_STYLE_SELECTION:
            _require_explicit(event)
            style = _signal_key(event.signal, "style_key")
            styles.add(style)
            negative = event.signal.get("negative_style_key")
            if negative is not None:
                negatives.add(_require_key_value(negative, "negative_style_key"))
    return tuple(sorted(styles)), tuple(sorted(negatives))


def _compile_constraints(
    events: tuple[AuthorityEvent, ...], session_id: str | None
) -> tuple[ConstraintSet, ConstraintSet]:
    persistent_locks: dict[str, FeatureConstraint] = {}
    persistent_intensity: dict[str, int] = {}
    persistent_prohibited: set[str] = set()
    session_locks: dict[str, FeatureConstraint] = {}
    session_intensity: dict[str, int] = {}
    session_prohibited: set[str] = set()
    for event in events:
        if event.event_type in {EventType.FEATURE_LOCKED, EventType.FEATURE_UNLOCKED}:
            _require_explicit(event)
            target = _constraint_scope(event, session_id)
            if target is None:
                continue
            locks = persistent_locks if target == "persistent" else session_locks
            key = _signal_key(event.signal, "dimension_key")
            if event.event_type is EventType.FEATURE_UNLOCKED:
                locks.pop(key, None)
            else:
                locks[key] = _feature_constraint(event.signal, key, ConstraintMode.PRESERVE)
        elif event.event_type is EventType.TEMPORARY_SESSION_OVERRIDE:
            _require_explicit(event)
            if session_id is None or event.session_id != session_id:
                continue
            key = _signal_key(event.signal, "dimension_key")
            session_locks[key] = _feature_constraint(event.signal, key, ConstraintMode.ALLOW_CHANGE)
        elif event.event_type is EventType.MAXIMUM_INTENSITY_CHANGED:
            _require_explicit(event)
            target = _constraint_scope(event, session_id)
            if target is None:
                continue
            intensity = persistent_intensity if target == "persistent" else session_intensity
            intensity[_signal_key(event.signal, "target_key")] = _signal_int(
                event.signal, "maximum_intensity_ppm", 0, PPM
            )
        elif event.event_type is EventType.PROHIBITED_OPERATION_ADDED:
            _require_explicit(event)
            target = _constraint_scope(event, session_id)
            if target is None:
                continue
            prohibited = persistent_prohibited if target == "persistent" else session_prohibited
            operation = event.signal.get("operation")
            if not isinstance(operation, str) or _OPERATION_PATTERN.fullmatch(operation) is None:
                raise ProfileCompilerError("operation must be an uppercase operation key")
            prohibited.add(operation)
    return (
        _constraint_set(persistent_locks, persistent_intensity, persistent_prohibited),
        _constraint_set(session_locks, session_intensity, session_prohibited),
    )


def _constraint_scope(event: AuthorityEvent, session_id: str | None) -> str | None:
    scope = event.signal.get("constraint_scope")
    if scope == "PERSISTENT":
        return "persistent"
    if scope == "SESSION_OVERRIDE":
        if event.session_id is None:
            raise ProfileCompilerError("session override constraint requires an event session")
        if session_id is not None and event.session_id == session_id:
            return "session"
        return None
    if scope not in {"PERSISTENT", "SESSION_OVERRIDE"}:
        raise ProfileCompilerError("constraint_scope must be PERSISTENT or SESSION_OVERRIDE")
    raise ProfileCompilerError("session override constraint must match the compilation session")


def _constraint_set(
    locks: Mapping[str, FeatureConstraint], intensity: Mapping[str, int], prohibited: set[str]
) -> ConstraintSet:
    return ConstraintSet(
        locks=tuple(locks[key] for key in sorted(locks)),
        maximum_intensity_ppm=tuple(sorted(intensity.items())),
        prohibited_operations=tuple(sorted(prohibited)),
    )


def _feature_constraint(
    signal: Mapping[str, object], key: str, mode: ConstraintMode
) -> FeatureConstraint:
    minimum = _optional_signal_int(signal, "minimum_ppm", -PPM, PPM)
    maximum = _optional_signal_int(signal, "maximum_ppm", -PPM, PPM)
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ProfileCompilerError("minimum_ppm must not exceed maximum_ppm")
    return FeatureConstraint(key, mode, minimum, maximum)


def _require_explicit(event: AuthorityEvent) -> None:
    if event.source is not EventSource.EXPLICIT_USER_ACTION:
        raise ProfileCompilerError("constraint and style authority must be an explicit user action")


def _signal_key(signal: Mapping[str, object], name: str) -> str:
    return _require_key_value(signal.get(name), name)


def _require_key_value(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ProfileCompilerError(f"{name} must be a key")
    _require_key(value, name)
    return value


def _signal_int(signal: Mapping[str, object], name: str, minimum: int, maximum: int) -> int:
    value = signal.get(name)
    _require_int(value, name, minimum=minimum, maximum=maximum)
    assert type(value) is int
    return value


def _optional_signal_int(
    signal: Mapping[str, object], name: str, minimum: int, maximum: int
) -> int | None:
    value = signal.get(name)
    if value is None:
        return None
    _require_int(value, name, minimum=minimum, maximum=maximum)
    assert type(value) is int
    return value


def _event_payload(
    sequence: int,
    event_type: EventType,
    source: EventSource,
    session_id: str | None,
    signal: Mapping[str, object],
    source_authority_digest: str,
) -> dict[str, object]:
    return {
        "event_type": event_type.value,
        "sequence": sequence,
        "session_id": session_id,
        "signal": dict(signal),
        "source": source.value,
        "source_authority_digest": source_authority_digest,
    }


def _normalize_signal(signal: Mapping[str, object]) -> dict[str, object]:
    try:
        normalized = json.loads(canonical_json_bytes(dict(signal)))
    except (TypeError, ValueError) as exc:
        raise ProfileCompilerError("event signal is not canonical authority") from exc
    if not isinstance(normalized, dict) or any(
        isinstance(value, (dict, list, bool)) or value is None for value in normalized.values()
    ):
        raise ProfileCompilerError("event signal values must be scalar strings or true integers")
    if any(type(value) is not int and not isinstance(value, str) for value in normalized.values()):
        raise ProfileCompilerError("event signal contains an unsupported value")
    return normalized


def _validate_events(events: tuple[AuthorityEvent, ...], as_of_event_sequence: int) -> None:
    previous_sequence = 0
    seen_digests: set[str] = set()
    seen_source_digests: set[str] = set()
    for event in events:
        if not isinstance(event, AuthorityEvent):
            raise ProfileCompilerError("authority events must contain AuthorityEvent values")
        if event.sequence <= previous_sequence or event.sequence > as_of_event_sequence:
            raise ProfileCompilerError(
                "authority event sequence must be strictly increasing and within as-of"
            )
        if event.event_digest in seen_digests:
            raise ProfileCompilerError("authority event digest is duplicated")
        if event.source_authority_digest in seen_source_digests:
            raise ProfileCompilerError("authority source event digest is duplicated")
        seen_digests.add(event.event_digest)
        seen_source_digests.add(event.source_authority_digest)
        previous_sequence = event.sequence


def _require_unique_dimensions(values: tuple[SelfStateDimension, ...], name: str) -> None:
    _require_unique_values((item.dimension_key for item in values), name)


def _require_unique_values(values: Iterable[str], name: str) -> None:
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ProfileCompilerError(f"{name} contains an invalid key")
        if value in seen:
            raise ProfileCompilerError(f"{name} contains a duplicate key")
        seen.add(value)


def _require_sorted_keys(values: Iterable[str], name: str) -> None:
    actual = tuple(values)
    if actual != tuple(sorted(actual)):
        raise ProfileCompilerError(f"{name} must be sorted by dimension_key")


def _require_key(value: str, name: str) -> None:
    if not isinstance(value, str) or _KEY_PATTERN.fullmatch(value) is None:
        raise ProfileCompilerError(f"{name} must be a lowercase authority key")


def _require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ProfileCompilerError(f"{name} must be a bounded identifier")


def _require_digest(value: str, name: str) -> None:
    if not isinstance(value, str) or _DIGEST_PATTERN.fullmatch(value) is None:
        raise ProfileCompilerError(f"{name} must be a lowercase SHA-256 digest")


def _require_int(value: object, name: str, *, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ProfileCompilerError(f"{name} must be a true integer within the authority range")
