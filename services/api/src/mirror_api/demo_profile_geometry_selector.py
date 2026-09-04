"""Pure, fail-closed selection for the D06 profile-guided D08 preview.

The selector deliberately consumes only already-derived public facts.  It
does not look up a source, create a plan, or access a D02 private registry.
Those responsibilities stay with the caller's transactional authority layer.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from mirror_api.demo_idempotency import canonical_json_bytes

DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION: Final = "demo-profile-guided-d08-step-v1"
DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST: Final = (
    "d66875008d6145c5c5ca381f9024bdba40aa7df4b752766a9e15d04dd994468d"
)
DEMO_PROFILE_GUIDED_STEP_DIMENSIONS: Final = (
    "chin_height",
    "eye_spacing",
    "jaw_width",
)
DEMO_PROFILE_GUIDED_STEP_MAGNITUDES_PPM: Final = (15_000, 30_000)

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_DIMENSION = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_PPM = 1_000_000

GeometryDirection = Literal["INCREASE", "DECREASE"]


class DemoProfileGeometrySelectionError(RuntimeError):
    """A caller supplied an invalid or non-replayable selection universe."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DemoProfileGeometryStepUnavailable(DemoProfileGeometrySelectionError):
    """No selected D08 case is eligible for the exact D05 profile."""


@dataclass(frozen=True, slots=True)
class DemoProfileGeometryDimension:
    """The one D05 projection needed for a candidate dimension."""

    dimension_key: str
    desired_delta_ppm: int
    confidence_ppm: int
    restraint: str
    geometry_prohibited: bool
    d02_selected_dimension: bool
    persistent_preserve_lock: bool
    current_session_allow_change: bool

    def validate(self) -> None:
        _dimension(self.dimension_key)
        _ppm(self.desired_delta_ppm, "desired_delta_ppm")
        _confidence(self.confidence_ppm)
        if self.restraint != "NONE":
            # Unknown restraint values fail closed at the same boundary.
            if not isinstance(self.restraint, str):
                raise DemoProfileGeometrySelectionError(
                    "INVALID_RESTRAINT", "profile restraint is invalid"
                )
        if (
            type(self.geometry_prohibited) is not bool
            or type(self.d02_selected_dimension) is not bool
        ):
            raise DemoProfileGeometrySelectionError(
                "INVALID_SELECTION_FACT", "selection facts must be boolean"
            )
        if (
            type(self.persistent_preserve_lock) is not bool
            or type(self.current_session_allow_change) is not bool
        ):
            raise DemoProfileGeometrySelectionError(
                "INVALID_LOCK_FACT", "lock facts must be boolean"
            )


@dataclass(frozen=True, slots=True)
class DemoProfileGeometryCase:
    """The selected-side D08 case projection; never a runtime capability."""

    dimension_key: str
    direction: GeometryDirection
    magnitude_ppm: int
    case_digest: str
    selected: bool = True

    def validate(self) -> None:
        _dimension(self.dimension_key)
        if self.direction not in {"INCREASE", "DECREASE"}:
            raise DemoProfileGeometrySelectionError(
                "INVALID_DIRECTION", "case direction is invalid"
            )
        if self.magnitude_ppm not in DEMO_PROFILE_GUIDED_STEP_MAGNITUDES_PPM:
            raise DemoProfileGeometrySelectionError(
                "INVALID_CASE_MAGNITUDE", "case magnitude is outside the fixed policy"
            )
        if not isinstance(self.case_digest, str) or _DIGEST.fullmatch(self.case_digest) is None:
            raise DemoProfileGeometrySelectionError("INVALID_CASE_DIGEST", "case digest is invalid")
        if type(self.selected) is not bool:
            raise DemoProfileGeometrySelectionError(
                "INVALID_CASE_SELECTION", "case selection is invalid"
            )


@dataclass(frozen=True, slots=True)
class DemoProfileGeometrySelection:
    dimension_key: str
    profile_desired_delta_ppm: int
    execution_delta_ppm: int
    selection_policy_version: str
    selection_policy_digest: str
    selected_case_digest: str


def profile_guided_step_policy_payload() -> dict[str, Any]:
    """Return the frozen, canonical policy input used by the published digest."""

    return {
        "allowed_dimensions": list(DEMO_PROFILE_GUIDED_STEP_DIMENSIONS),
        "allowed_magnitudes_ppm": list(DEMO_PROFILE_GUIDED_STEP_MAGNITUDES_PPM),
        "candidate_requirements": [
            "CONFIDENCE_POSITIVE",
            "GEOMETRY_NOT_PROHIBITED",
            "PROFILE_DELTA_NONZERO",
            "RESTRAINT_NONE",
            "SELECTED_D02_DIMENSION",
            "SELECTED_D08_CASE",
            "SESSION_OVERRIDE_FOR_PRESERVE",
        ],
        "dimension_order": ["ABS_PROFILE_DELTA_DESC", "DIMENSION_KEY_ASC"],
        "magnitude_order": ["ABS_DISTANCE_ASC", "MAGNITUDE_ASC", "CASE_DIGEST_ASC"],
        "policy_version": DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
        "sign_rule": "INHERIT_NONZERO_PROFILE_DELTA",
        "source_scope": "CURRENT_D02_SELECTED_SIDE_CASE_ONLY",
    }


def require_profile_guided_step_policy(*, policy_version: str, policy_digest: str) -> None:
    """Recompute rather than trust a caller's policy/version projection."""

    actual = hashlib.sha256(canonical_json_bytes(profile_guided_step_policy_payload())).hexdigest()
    if actual != DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST:
        raise DemoProfileGeometrySelectionError(
            "SELECTION_POLICY_CORRUPTED", "frozen selection policy digest is inconsistent"
        )
    if (
        policy_version != DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION
        or policy_digest != DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST
    ):
        raise DemoProfileGeometrySelectionError(
            "UNSUPPORTED_SELECTION_POLICY", "profile-guided selection policy is unsupported"
        )


def select_profile_guided_geometry_step(
    *,
    dimensions: Sequence[DemoProfileGeometryDimension],
    cases: Sequence[DemoProfileGeometryCase],
    policy_version: str = DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
    policy_digest: str = DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
) -> DemoProfileGeometrySelection:
    """Select one eligible dimension and one exact selected D08 step.

    Eligibility is evaluated before ranking.  A duplicate selected case is
    authority corruption, not an opportunity to choose an arbitrary winner.
    """

    require_profile_guided_step_policy(policy_version=policy_version, policy_digest=policy_digest)
    if not isinstance(dimensions, Sequence) or isinstance(dimensions, (str, bytes)):
        raise DemoProfileGeometrySelectionError("INVALID_DIMENSIONS", "dimensions are invalid")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise DemoProfileGeometrySelectionError("INVALID_CASES", "cases are invalid")
    by_dimension: dict[str, DemoProfileGeometryDimension] = {}
    for item in dimensions:
        if not isinstance(item, DemoProfileGeometryDimension):
            raise DemoProfileGeometrySelectionError("INVALID_DIMENSION", "dimension is invalid")
        item.validate()
        if item.dimension_key in by_dimension:
            raise DemoProfileGeometrySelectionError(
                "DUPLICATE_PROFILE_DIMENSION", "profile dimension is ambiguous"
            )
        by_dimension[item.dimension_key] = item
    parsed_cases: list[DemoProfileGeometryCase] = []
    for case in cases:
        if not isinstance(case, DemoProfileGeometryCase):
            raise DemoProfileGeometrySelectionError("INVALID_CASE", "case is invalid")
        case.validate()
        parsed_cases.append(case)

    eligible: list[DemoProfileGeometryDimension] = []
    for item in by_dimension.values():
        if (
            item.dimension_key in DEMO_PROFILE_GUIDED_STEP_DIMENSIONS
            and item.desired_delta_ppm != 0
            and item.confidence_ppm > 0
            and item.restraint == "NONE"
            and not item.geometry_prohibited
            and item.d02_selected_dimension
            and (not item.persistent_preserve_lock or item.current_session_allow_change)
        ):
            eligible.append(item)
    eligible.sort(key=lambda item: (-abs(item.desired_delta_ppm), item.dimension_key))
    for dimension in eligible:
        direction: GeometryDirection = "INCREASE" if dimension.desired_delta_ppm > 0 else "DECREASE"
        matches = [
            item
            for item in parsed_cases
            if item.selected
            and item.dimension_key == dimension.dimension_key
            and item.direction == direction
        ]
        # A selected-side case must be unique at its complete selector; a
        # duplicated case is never resolved by an incidental list order.
        selector_keys = [
            (item.dimension_key, item.direction, item.magnitude_ppm) for item in matches
        ]
        if len(selector_keys) != len(set(selector_keys)):
            raise DemoProfileGeometrySelectionError(
                "DUPLICATE_SELECTED_CASE", "selected D08 case is ambiguous"
            )
        if not matches:
            continue
        chosen = min(
            matches,
            key=lambda item: (
                abs(item.magnitude_ppm - abs(dimension.desired_delta_ppm)),
                item.magnitude_ppm,
                item.case_digest,
            ),
        )
        execution_delta = chosen.magnitude_ppm if direction == "INCREASE" else -chosen.magnitude_ppm
        return DemoProfileGeometrySelection(
            dimension_key=dimension.dimension_key,
            profile_desired_delta_ppm=dimension.desired_delta_ppm,
            execution_delta_ppm=execution_delta,
            selection_policy_version=DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
            selection_policy_digest=DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
            selected_case_digest=chosen.case_digest,
        )
    raise DemoProfileGeometryStepUnavailable(
        "DEMO_PROFILE_GEOMETRY_STEP_UNAVAILABLE",
        "no eligible selected D08 geometry step is available",
    )


def selection_from_envelope(value: Mapping[str, Any]) -> DemoProfileGeometrySelection:
    """Strictly replay the v2 shared immutable envelope projection."""

    required = {
        "dimension_key",
        "profile_desired_delta_ppm",
        "execution_delta_ppm",
        "selection_policy_version",
        "selection_policy_digest",
        "selected_case_digest",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise DemoProfileGeometrySelectionError(
            "INVALID_STEPPED_ENVELOPE", "stepped selection envelope is invalid"
        )
    dimension_key = value["dimension_key"]
    profile_delta = value["profile_desired_delta_ppm"]
    execution_delta = value["execution_delta_ppm"]
    version = value["selection_policy_version"]
    digest = value["selection_policy_digest"]
    case_digest = value["selected_case_digest"]
    if not isinstance(dimension_key, str):
        raise DemoProfileGeometrySelectionError("INVALID_STEPPED_ENVELOPE", "dimension is invalid")
    _dimension(dimension_key)
    _ppm(profile_delta, "profile_desired_delta_ppm")
    _ppm(execution_delta, "execution_delta_ppm")
    if profile_delta == 0 or abs(execution_delta) not in DEMO_PROFILE_GUIDED_STEP_MAGNITUDES_PPM:
        raise DemoProfileGeometrySelectionError("INVALID_STEPPED_ENVELOPE", "step is invalid")
    if (profile_delta > 0) != (execution_delta > 0):
        raise DemoProfileGeometrySelectionError("INVALID_STEPPED_ENVELOPE", "step sign is invalid")
    if (
        not isinstance(version, str)
        or not isinstance(digest, str)
        or not isinstance(case_digest, str)
    ):
        raise DemoProfileGeometrySelectionError(
            "INVALID_STEPPED_ENVELOPE", "envelope types are invalid"
        )
    require_profile_guided_step_policy(policy_version=version, policy_digest=digest)
    if _DIGEST.fullmatch(case_digest) is None:
        raise DemoProfileGeometrySelectionError(
            "INVALID_STEPPED_ENVELOPE", "case digest is invalid"
        )
    return DemoProfileGeometrySelection(
        dimension_key,
        profile_delta,
        execution_delta,
        version,
        digest,
        case_digest,
    )


def _dimension(value: str) -> None:
    if not isinstance(value, str) or _DIMENSION.fullmatch(value) is None:
        raise DemoProfileGeometrySelectionError("INVALID_DIMENSION", "dimension key is invalid")


def _ppm(value: object, name: str) -> None:
    if type(value) is not int or not -_PPM <= value <= _PPM:
        raise DemoProfileGeometrySelectionError("INVALID_PPM", f"{name} is invalid")


def _confidence(value: object) -> None:
    if type(value) is not int or not 0 <= value <= _PPM:
        raise DemoProfileGeometrySelectionError("INVALID_CONFIDENCE", "confidence is invalid")


__all__ = [
    "DEMO_PROFILE_GUIDED_STEP_DIMENSIONS",
    "DEMO_PROFILE_GUIDED_STEP_MAGNITUDES_PPM",
    "DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST",
    "DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION",
    "DemoProfileGeometryCase",
    "DemoProfileGeometryDimension",
    "DemoProfileGeometrySelection",
    "DemoProfileGeometrySelectionError",
    "DemoProfileGeometryStepUnavailable",
    "profile_guided_step_policy_payload",
    "require_profile_guided_step_policy",
    "select_profile_guided_geometry_step",
    "selection_from_envelope",
]
