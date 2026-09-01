from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Callable, Generator
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from mirror_api import demo_d02_private_vision_backend as private_backend
from mirror_api.demo_d02_acquisition_identity import CANDIDATE_QA_POLICY_DIGEST
from mirror_api.demo_d02_acquisition_operator import (
    D02AcquisitionOperator,
    D02LocalDurableIndex,
)
from mirror_api.demo_d02_candidate_qualification import (
    MANUAL_REVIEW_POLICY_DIGEST,
    NORMALIZATION_POLICY_DIGEST,
    CandidateManualReview,
    D02CandidateNormalizer,
    D02CandidateQualificationError,
    D02CandidateQualificationService,
    build_candidate_descriptor,
)
from mirror_api.demo_d02_formal_source_evidence import (
    build_formal_measurement_evidence,
    build_formal_source_facts,
    build_normalization_receipt_digest,
)
from mirror_api.demo_d02_private_vision_backend import (
    ProcessOutcome,
    WindowsFaceLandmarkerOfflineM3Backend,
)
from mirror_api.demo_d02_r2_runtime_forward import M3ExecutionOutput
from mirror_api.demo_models import D02SourceCandidate

pytestmark = pytest.mark.integration


def _m3_stderr() -> bytes:
    lines = [f"INFO: synthetic diagnostic {index:02d}" for index in range(22)]
    lines[1] = "W0000 00:00:1234567890.123456 100 source.cc:10] synthetic warning one"
    lines[9] = "W0000 00:00:1234567890.234567 101 source.cc:20] synthetic warning two"
    lines[15] = "W0000 00:00:1234567890.345678 102 source.cc:30] synthetic warning three"
    return "\n".join(lines).encode("ascii")


@pytest.fixture(autouse=True)
def _synthetic_diagnostic_grammar(monkeypatch: pytest.MonkeyPatch) -> None:
    digests = tuple(
        hashlib.sha256(
            private_backend._ABSL_DIAGNOSTIC_PREFIX_RE.sub(b"<ABSL> ", line, count=1)
        ).hexdigest()
        for line in _m3_stderr().splitlines()
    )
    monkeypatch.setattr(private_backend, "_EXPECTED_DIAGNOSTIC_LINE_DIGESTS", digests)


@pytest.fixture
def qualification_context(
    tmp_path: Path,
) -> Generator[tuple[D02AcquisitionOperator, D02CandidateNormalizer, sessionmaker[Session], Path]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, "
                "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs CASCADE"
            )
        )
    workspace_root = tmp_path.resolve(strict=True)
    (workspace_root / ".private-handoff").mkdir()
    index = D02LocalDurableIndex(workspace_root=workspace_root)
    yield (
        D02AcquisitionOperator(session_factory=sessions, durable_index=index),
        D02CandidateNormalizer(durable_index=index),
        sessions,
        workspace_root,
    )
    with sessions.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, "
                "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs CASCADE"
            )
        )
    engine.dispose()


def _result_input() -> BytesIO:
    image = Image.new("RGB", (96, 96), (40, 90, 160))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    result = {
        "outcome": "RESULT",
        "result": {
            "image_url": "data:image/png;base64,"
            + base64.b64encode(buffer.getvalue()).decode("ascii")
        },
    }
    return BytesIO((json.dumps(result, separators=(",", ":")) + "\n").encode())


def _m3_stdout() -> bytes:
    points = ["0.500000,0.500000,0.000000" for _ in range(478)]
    anchors = {
        10: (0.50, 0.10),
        17: (0.50, 0.60),
        61: (0.40, 0.60),
        98: (0.45, 0.50),
        123: (0.30, 0.50),
        133: (0.40, 0.40),
        152: (0.50, 0.90),
        234: (0.25, 0.70),
        291: (0.60, 0.60),
        327: (0.55, 0.50),
        352: (0.70, 0.50),
        362: (0.60, 0.40),
        454: (0.75, 0.70),
    }
    for index, (x, y) in anchors.items():
        points[index] = f"{x:.6f},{y:.6f},0.000000"
    return "\n".join(
        (
            "detect_status=ok",
            "face_count=1",
            "detect_latency_us=12345",
            "face_0_landmark_count=478",
            f"face_0_landmarks={';'.join(points)}",
            "matrix_count=1",
            "matrix_0=" + ",".join("1.000000" for _ in range(18)),
            "close_status=ok",
        )
    ).encode("ascii")


def _m3_runner(
    calls: list[tuple[str, ...]],
) -> Callable[[tuple[str, ...], float, int], ProcessOutcome]:
    def run(command: tuple[str, ...], _timeout: float, _limit: int) -> ProcessOutcome:
        calls.append(command)
        assert Path(command[2]).is_file()
        return ProcessOutcome(returncode=0, stdout=_m3_stdout(), stderr=_m3_stderr())

    return run


def test_candidate_normalization_is_two_copy_deterministic_and_recoverable(
    qualification_context: tuple[
        D02AcquisitionOperator, D02CandidateNormalizer, sessionmaker[Session], Path
    ],
) -> None:
    operator, normalizer, sessions, workspace_root = qualification_context
    run_id = str(operator.bootstrap()["run_id"])
    assert (
        operator.call_session(
            run_id=run_id,
            input_stream=_result_input(),
            output=StringIO(),
        )
        == 0
    )
    with sessions.begin() as session:
        candidate = session.scalar(select(D02SourceCandidate))
        assert candidate is not None

    normalized = normalizer.normalize(candidate)
    recovered = normalizer.recover(candidate)

    assert normalized.content == recovered.content
    assert normalized.sha256 == recovered.sha256 == hashlib.sha256(normalized.content).hexdigest()
    assert normalized.normalization_policy_digest == NORMALIZATION_POLICY_DIGEST
    assert normalized.public_payload()["media_type"] == "image/jpeg"
    assert "content" not in normalized.public_payload()
    assert ".private-handoff" not in json.dumps(normalized.public_payload())
    checkpoint = json.loads(
        (workspace_root / ".private-handoff" / "D02_CURRENT_CHECKPOINT.json").read_text()
    )
    entry = checkpoint["entries"][0]
    assert entry["normalized_primary"]["sha256"] == normalized.sha256
    assert entry["normalized_backup"]["sha256"] == normalized.sha256
    assert (
        entry["normalized_primary"]["file_identity"] != entry["normalized_backup"]["file_identity"]
    )


def test_manual_review_requires_complete_adult_synthetic_acceptance() -> None:
    accepted = CandidateManualReview(
        candidate_id="a" * 32,
        candidate_content_digest="b" * 64,
        normalized_sha256="c" * 64,
        selector_slot_id="D02_SLOT_01",
        reviewer_role="D02_SUBSYSTEM_PRINCIPAL",
        synthetic_adult_attested=True,
        suspected_minor=False,
        real_person_reference_used=False,
        celebrity_imitation_suspected=False,
        face_count=1,
        front_facing=True,
        features_unobstructed=True,
        quality_sufficient=True,
        style_context_match=True,
        variable_contamination=False,
        anti_homogenization_passed=True,
    )

    assert accepted.accepted is True
    assert accepted.private_payload()["decision"] == "ACCEPT"
    assert accepted.private_payload()["manual_review_policy_digest"] == MANUAL_REVIEW_POLICY_DIGEST
    assert len(accepted.evidence_digest) == 64


def test_manual_review_cannot_reject_without_allowlisted_reason() -> None:
    with pytest.raises(
        D02CandidateQualificationError, match="MANUAL_REVIEW_REJECTION_REASON_REQUIRED"
    ):
        rejected = CandidateManualReview(
            candidate_id="a" * 32,
            candidate_content_digest="b" * 64,
            normalized_sha256="c" * 64,
            selector_slot_id="D02_SLOT_01",
            reviewer_role="D02_SUBSYSTEM_PRINCIPAL",
            synthetic_adult_attested=False,
            suspected_minor=True,
            real_person_reference_used=False,
            celebrity_imitation_suspected=False,
            face_count=1,
            front_facing=True,
            features_unobstructed=True,
            quality_sufficient=True,
            style_context_match=True,
            variable_contamination=False,
            anti_homogenization_passed=True,
        )
        _ = rejected.accepted


def test_real_typed_one_shot_and_manual_review_are_required_for_ledger_acceptance(
    qualification_context: tuple[
        D02AcquisitionOperator, D02CandidateNormalizer, sessionmaker[Session], Path
    ],
) -> None:
    operator, normalizer, sessions, workspace_root = qualification_context
    run_id = str(operator.bootstrap()["run_id"])
    assert (
        operator.call_session(
            run_id=run_id,
            input_stream=_result_input(),
            output=StringIO(),
        )
        == 0
    )
    with sessions.begin() as session:
        candidate = session.scalar(select(D02SourceCandidate))
        assert candidate is not None
    material = normalizer.normalize(candidate)
    descriptor = build_candidate_descriptor(candidate=candidate, material=material)
    calls: list[tuple[str, ...]] = []
    backend = WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=workspace_root / ".private-handoff" / "d02-acquisition" / "runtime-staging",
        runner=_m3_runner(calls),
    )
    inspection = backend.inspect_candidate_once(content=material.content, descriptor=descriptor)
    review = CandidateManualReview(
        candidate_id=candidate.id,
        candidate_content_digest=candidate.content_digest,
        normalized_sha256=material.sha256,
        selector_slot_id=candidate.selector_slot_id,
        reviewer_role="D02_SUBSYSTEM_PRINCIPAL",
        synthetic_adult_attested=True,
        suspected_minor=False,
        real_person_reference_used=False,
        celebrity_imitation_suspected=False,
        face_count=1,
        front_facing=True,
        features_unobstructed=True,
        quality_sufficient=True,
        style_context_match=True,
        variable_contamination=False,
        anti_homogenization_passed=True,
    )
    qualifier = D02CandidateQualificationService(
        durable_index=D02LocalDurableIndex(workspace_root=workspace_root)
    )
    authority = qualifier.evaluate(
        candidate=candidate,
        material=material,
        inspection=inspection,
        manual_review=review,
    )
    with sessions.begin() as session:
        manifest = qualifier.apply_to_ledger(session=session, authority_value=authority)
        accepted = session.get(D02SourceCandidate, candidate.id)
        assert manifest is None
        assert accepted is not None and accepted.candidate_state == "QA_ACCEPTED"
    assert len(calls) == 1
    evidence_path = (
        workspace_root
        / ".private-handoff"
        / "d02-acquisition"
        / "qualification"
        / f"d02-c{candidate.id}-qualification.json"
    )
    assert evidence_path.is_file()
    assert ".private-handoff" not in json.dumps(
        {
            "m3": authority.m3_evidence_digest,
            "qa": authority.qa_evidence_digest,
            "family": authority.identity_family_digest,
        }
    )

    formal_backend = WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=workspace_root / ".private-handoff" / "d02-acquisition" / "runtime-staging",
        runner=_m3_runner(calls),
    )
    formal_outputs = [
        M3ExecutionOutput.create(
            formal_backend.inspect_source(
                content=material.content,
                descriptor=descriptor,
                repeat_index=index,
            )
        )
        for index in (1, 2, 3)
    ]
    measurement_evidence = build_formal_measurement_evidence(formal_outputs)
    normalization_receipt = build_normalization_receipt_digest(
        candidate=candidate,
        material=material,
    )
    facts = build_formal_source_facts(
        candidate=candidate,
        material=material,
        measurement_evidence=measurement_evidence,
        normalization_receipt_digest=normalization_receipt,
        source_authority_digest=hashlib.sha256(b"formal-source-authority").hexdigest(),
        source_qa_snapshot_digest=hashlib.sha256(b"formal-source-qa").hexdigest(),
        source_provenance_digest=hashlib.sha256(b"formal-source-provenance").hexdigest(),
        qa_policy_digest=CANDIDATE_QA_POLICY_DIGEST,
    )
    assert facts["source_asset_sha256"] == material.sha256
    assert facts["source_repeat_certification_digest"] == measurement_evidence.certificate_digest
    assert facts["source_measurement_projection_digest"] == measurement_evidence.projection_digest
    assert len(calls) == 4
