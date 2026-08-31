"""Non-HTTP operator for one durable D02 Candidate qualification cycle."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO, Final, NoReturn, TextIO, cast

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from mirror_api.demo_d02_acquisition_operator import (
    D02LocalDurableIndex,
    D02OperatorError,
    _database_url,
    _emit,
    _require_database_head,
    _validate_workspace_authority,
)
from mirror_api.demo_d02_candidate_qualification import (
    CandidateManualReview,
    D02CandidateNormalizer,
    D02CandidateQualificationError,
    D02CandidateQualificationService,
    build_candidate_descriptor,
)
from mirror_api.demo_d02_private_vision_backend import PrivateVisionBackendError
from mirror_api.demo_d02_runtime_composition import (
    D02RuntimeCompositionError,
    compose_accepted_m3_backend,
    load_runtime_locators,
)
from mirror_api.demo_d02_source_acquisition import D02SourceAcquisitionError
from mirror_api.demo_models import D02SourceCandidate

CANDIDATE_REVIEW_COMMAND_SCHEMA: Final = "mirror.private/D02CandidateReviewCommand/v1"
_REJECTION = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_MAX_COMMAND_BYTES: Final = 32_768


class _DuplicateJsonKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey()
        value[key] = item
    return value


class D02CandidateOperatorError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class D02CandidateQualificationOperator:
    def __init__(
        self,
        *,
        sessions: sessionmaker[Session],
        durable_index: D02LocalDurableIndex,
        workspace_root: Path,
    ) -> None:
        self._sessions = sessions
        self._index = durable_index
        self._workspace_root = workspace_root

    def qualify(self, *, candidate_id: str, command: Mapping[str, object]) -> dict[str, object]:
        with self._sessions() as session:
            _require_database_head(session)
            candidate = session.get(D02SourceCandidate, candidate_id)
            if candidate is None or candidate.candidate_state != "DURABLE":
                _fail("CANDIDATE_NOT_READY_FOR_QUALIFICATION")
        normalizer = D02CandidateNormalizer(durable_index=self._index)
        material = normalizer.normalize(candidate)
        locators = load_runtime_locators(workspace_root=self._workspace_root)
        backend = compose_accepted_m3_backend(
            locators=locators,
            staging_root=self._index.objects_parent.parent / "runtime-staging",
        )
        inspection = backend.inspect_candidate_once(
            content=material.content,
            descriptor=build_candidate_descriptor(candidate=candidate, material=material),
        )
        review = _candidate_review(command, candidate=candidate, normalized_sha256=material.sha256)
        service = D02CandidateQualificationService(durable_index=self._index)
        authority = service.evaluate(
            candidate=candidate,
            material=material,
            inspection=inspection,
            manual_review=review,
        )
        with self._sessions.begin() as session:
            _require_database_head(session)
            manifest = service.apply_to_ledger(session=session, authority_value=authority)
        return {
            "status": "QA_ACCEPTED" if authority.qa_accepted else "QA_REJECTED",
            "candidate_id": authority.candidate_id,
            "m3_supported": authority.m3_supported,
            "qa_accepted": authority.qa_accepted,
            "rejection_code": authority.rejection_code,
            "selected_manifest_id": manifest.id if manifest is not None else None,
            "selected_source_count": manifest.source_count if manifest is not None else None,
        }


def _candidate_review(
    value: Mapping[str, object], *, candidate: D02SourceCandidate, normalized_sha256: str
) -> CandidateManualReview:
    expected = {
        "schema_version",
        "reviewer_role",
        "synthetic_adult_attested",
        "suspected_minor",
        "real_person_reference_used",
        "celebrity_imitation_suspected",
        "face_count",
        "front_facing",
        "features_unobstructed",
        "quality_sufficient",
        "style_context_match",
        "variable_contamination",
        "anti_homogenization_passed",
        "rejection_code",
    }
    if set(value) != expected or value.get("schema_version") != CANDIDATE_REVIEW_COMMAND_SCHEMA:
        _fail("CANDIDATE_REVIEW_COMMAND_INVALID")
    boolean_fields = expected - {
        "schema_version",
        "reviewer_role",
        "face_count",
        "rejection_code",
    }
    if (
        any(type(value.get(field)) is not bool for field in boolean_fields)
        or value.get("reviewer_role") != "D02_SUBSYSTEM_PRINCIPAL"
        or type(value.get("face_count")) is not int
    ):
        _fail("CANDIDATE_REVIEW_COMMAND_INVALID")
    rejection = value.get("rejection_code")
    if rejection is not None and (
        not isinstance(rejection, str) or _REJECTION.fullmatch(rejection) is None
    ):
        _fail("CANDIDATE_REVIEW_COMMAND_INVALID")
    try:
        return CandidateManualReview(
            candidate_id=candidate.id,
            candidate_content_digest=candidate.content_digest,
            normalized_sha256=normalized_sha256,
            selector_slot_id=candidate.selector_slot_id,
            reviewer_role=cast(str, value["reviewer_role"]),
            synthetic_adult_attested=cast(bool, value["synthetic_adult_attested"]),
            suspected_minor=cast(bool, value["suspected_minor"]),
            real_person_reference_used=cast(bool, value["real_person_reference_used"]),
            celebrity_imitation_suspected=cast(bool, value["celebrity_imitation_suspected"]),
            face_count=cast(int, value["face_count"]),
            front_facing=cast(bool, value["front_facing"]),
            features_unobstructed=cast(bool, value["features_unobstructed"]),
            quality_sufficient=cast(bool, value["quality_sufficient"]),
            style_context_match=cast(bool, value["style_context_match"]),
            variable_contamination=cast(bool, value["variable_contamination"]),
            anti_homogenization_passed=cast(bool, value["anti_homogenization_passed"]),
            rejection_code=rejection,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise D02CandidateOperatorError("CANDIDATE_REVIEW_COMMAND_INVALID") from error


def _read_command(stream: IO[bytes]) -> Mapping[str, object]:
    if stream.isatty():
        _fail("TTY_INPUT_FORBIDDEN")
    line = stream.readline(_MAX_COMMAND_BYTES + 1)
    if not line or len(line) > _MAX_COMMAND_BYTES or not line.endswith(b"\n"):
        _fail("CANDIDATE_REVIEW_COMMAND_INVALID")
    try:
        value = json.loads(line.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey) as error:
        raise D02CandidateOperatorError("CANDIDATE_REVIEW_COMMAND_INVALID") from error
    if not isinstance(value, Mapping):
        _fail("CANDIDATE_REVIEW_COMMAND_INVALID")
    return cast(Mapping[str, object], value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal D02 Candidate qualification operator")
    parser.add_argument("--database-env", default="D02_DATABASE_URL")
    parser.add_argument("--environment", required=True, choices=("development", "test", "ci"))
    parser.add_argument("--candidate-id", required=True)
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    input_stream: IO[bytes] | None = None,
    output: TextIO | None = None,
    error_output: TextIO | None = None,
) -> int:
    stream = output or sys.stdout
    errors = error_output or sys.stderr
    engine = None
    try:
        args = build_parser().parse_args(argv)
        workspace_root = Path.cwd()
        _validate_workspace_authority(
            workspace_root=workspace_root,
            environment=cast(str, args.environment),
        )
        command = _read_command(input_stream or sys.stdin.buffer)
        engine = create_engine(_database_url(cast(str, args.database_env)), pool_pre_ping=True)
        sessions = sessionmaker(engine, expire_on_commit=False)
        result = D02CandidateQualificationOperator(
            sessions=sessions,
            durable_index=D02LocalDurableIndex(workspace_root=workspace_root),
            workspace_root=workspace_root,
        ).qualify(candidate_id=cast(str, args.candidate_id), command=command)
        _emit(stream, result)
        return 0
    except (
        D02CandidateOperatorError,
        D02CandidateQualificationError,
        D02OperatorError,
        D02RuntimeCompositionError,
        D02SourceAcquisitionError,
        PrivateVisionBackendError,
    ) as error:
        _emit(errors, {"status": "FAILED", "code": getattr(error, "code", "RUNTIME_FAILED")})
        return 2
    except SQLAlchemyError:
        _emit(errors, {"status": "FAILED", "code": "DATABASE_OPERATION_FAILED"})
        return 2
    except Exception:
        _emit(errors, {"status": "FAILED", "code": "INTERNAL_OPERATOR_FAILURE"})
        return 2
    finally:
        if engine is not None:
            engine.dispose()


def _fail(code: str) -> NoReturn:
    raise D02CandidateOperatorError(code)


if __name__ == "__main__":
    raise SystemExit(run())
