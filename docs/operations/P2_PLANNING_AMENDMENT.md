# Phase 2 Planning Review Consolidated Amendment

## Status and unchanged scope

- `PLAN_AMENDMENT_STATUS: INCORPORATED`
- `PHASE_2_DEFINITION_CONFLICT: NONE`
- Phase 2 remains the synthetic-only Synthetic Dataset Engine.
- Phase 2 Milestones remain `COMMITTED`; separate execution authorization advances P2-M1 to `EXECUTING` for T01 only.
- The accepted M1–M9 Milestone DAG and T01–T08 task graph are unchanged.
- This amendment authorizes documentation/governance correction only. It does not authorize T01, migration `0008`, production code, dependencies, models, Provider calls or generated assets.

## P2 architecture authority

The accepted conceptual chain remains:

```text
Synthetic generation
→ raw Provider evidence
→ deterministic normalization
→ immutable synthetic Asset
→ versioned synthetic Vision QA
→ bank-independent SyntheticIdentity
→ deterministic geometry variant
→ isolation / duplicate / diversity evidence
→ immutable QuestionBank manifest
→ append-only revocation evidence
```

Provider output remains untrusted raw source evidence. It is never directly an Asset, SyntheticIdentity or QuestionBank entry. QuestionBank never owns `SyntheticIdentity`; immutable manifest entries later reference identity, asset checksums and evidence versions. Released manifests cannot be silently mutated, and append-only revocation stops new selection without deleting historical provenance. Automated hard QA failures cannot be erased or converted to eligible evidence by manual review.

The adult synthetic policy remains “clearly adult-appearing synthetic subject”: generation policy, Provider safety evidence and human review where required; ambiguous or minor-looking output is rejected. P2 does not use age estimation or claim exact biological age.

## T01 authority and mandatory Principal checkpoint

`T01_AUTHORITY = ENCODE_APPROVED_DECISIONS_ONLY`

T01 may only translate already approved decisions into ADRs, architecture/research/operations documents, Milestone state and governance records. It may not choose or change domain authority, entity ownership, lifecycle, QA hard/soft semantics, Provider/storage architecture, release/revocation, migration strategy, identity or QuestionBank ownership, adult policy, license decisions, or public/internal API strategy. Ambiguity at any of these boundaries requires:

```text
STATUS: BLOCKED
ESCALATE_TO: PRINCIPAL_SOL_HIGH
```

After T01 reports PASS, `P2-M1-PR1 — Principal Architecture Review` is mandatory. The Principal independently reviews the actual diff for approved-decision fidelity, Phase 0/1 invariants, evidence-layer separation, hard QA, fail-closed behavior, P3 exclusion and zero dependency/model additions. Only `PRINCIPAL_ARCHITECTURE_REVIEW: PASS` unlocks T02–T05.

## P2-MVR-v1 research floor

`P2-MVR-v1 — PROVISIONAL MINIMUM VIABILITY RESEARCH FLOOR`

The planned minimum of four bidirectional READY 2D geometry dimensions across three region groups and 24 independent QA-passed identities demonstrates only technical feasibility. It does not establish population-level validity, questionnaire validity, sufficient preference coverage, universal geometry reliability or final statistical sufficiency. These counts and all future numerical tolerances remain operational research targets, not Product Invariants.

Every dimension proposed as `READY` must record dimension, algorithm and QAPolicy versions; sample and independent-identity counts; requested and measured target-delta distributions; target-error and non-target-drift distributions; holdout pass rate; repeated-run and cross-platform variance; artifact failure rate; unsupported/failure cases; and a confidence interval or another explicitly justified uncertainty representation.

### Pre-registration and cohort escalation

For each dimension: measure repeated-run, re-encode and platform variance; construct synthetic calibration samples; estimate target/non-target distributions; define and freeze a versioned tolerance policy; then evaluate on identities excluded from calibration. Holdout thresholds cannot be relaxed after results are seen merely to force PASS. Failure yields `FURTHER_RESEARCH` or a new algorithm/QAPolicy version.

The cohort sequence is `24 → 48 → 96`. At N=24, unstable variance, error, drift, uncertainty or holdout behavior requires N=48; continued instability requires N=96. Continued instability at N=96 results in `EXPERIMENTAL`, `UNSUPPORTED_IN_P2` or `REQUIRES_3D_RESEARCH`, not indefinite scaling to force PASS.

## Duplicate and supply-chain boundary

- `imagededup`: `REJECT`; later `REIMPLEMENT_SMALL_CORE` is limited to exact SHA-256, perceptual hash, Hamming distance, candidate generation, deterministic threshold evaluation and cluster evidence. Future deterministic fixtures cover identical, re-encoded, brightness, resize, crop, geometry variant, clearly different identity, threshold-boundary and Hamming-distance cases. Thresholds follow measured distributions, never a magic constant.
- Pillow 12.3.0: `APPROVE_FOR_P2` purpose extension only; no version change. Explicit sanitation and second-decode evidence remain required.
- OpenCV: `POC_REQUIRED`; no P2-M1 install or frozen production version. M4 PoC must evaluate Python 3.13, Windows/Linux/Docker, wheel/native footprint, SBOM, performance, deterministic transforms, platform parity and replacement cost.
- MediaPipe: `LICENSE_REVIEW_REQUIRED`; source code, package/runtime, Face Landmarker artifact and model/data distribution terms are four separate reviews. Transition is `LICENSE_REVIEW_REQUIRED → POC_APPROVED → RUNTIME_CANDIDATE → APPROVED`.

### MediaPipe upstream discrepancy

Authoritative GitHub API verification on 2026-08-16 confirms that `v0.10.35` exists and was published on 2026-04-28. The same upstream `releases/latest` endpoint currently returns tag `v1.0.0`, whose release notes state “Bump MediaPipe version to 0.10.36.” Therefore this amendment records `v0.10.35` as the requested P2 candidate snapshot, not as an unqualified current-latest fact. A later PoC must lock and independently review the exact source tag, package/runtime and model artifact.

## Execution waves and stop rule

The execution sequence remains Wave 0 Principal → T01 → mandatory PR1 → T02/T03/T04/T05 → Principal integration → T06 → T07 → T08 → bounded `P2-M1-Rxx` repairs and final Principal Gate. Architecture, privacy, security, license or Phase changes are change control, never Repair Tasks. Terra PASS is evidence only; only the Principal accepts tasks and decides `P2-M1: PASS|CONDITIONAL|FAIL`, and only PASS may become FROZEN.

No Phase-wide authorization exists. After a future M1 Gate, work stops before M2 and repository reality is re-read for rolling-wave refinement. P2 does not authorize real-user facial processing, SelfState, questionnaire inference, DesiredDelta, editing, makeup transfer, Visual Memory OS or billing.

This amendment stops at `PLAN_STATUS: READY_FOR_EXECUTION`. T01 now has separate execution authorization; no Phase-wide or T02–T08 authorization follows from it.

## Amendment outcome

- `MEDIAPIPE_UPSTREAM_CORRECTION: DISCREPANCY_RECORDED`
- `MEDIAPIPE_LICENSE_STATUS: LICENSE_REVIEW_REQUIRED`
- `T01_AUTHORITY_CHANGE: ENCODE_APPROVED_DECISIONS_ONLY`
- `PRINCIPAL_REVIEW_CHECKPOINT: P2-M1-PR1_REQUIRED`
- `VARIABLE_ISOLATION_GATE_CHANGE: RECLASSIFIED_AS_PROVISIONAL_RESEARCH_FLOOR`
- `P2_MVR_V1_DEFINITION: TECHNICAL_FEASIBILITY_ONLY`
- `COHORT_ESCALATION_RULE: 24_TO_48_TO_96_THEN_RECLASSIFY`
- `IMAGEDUP_DECISION: REJECT_REIMPLEMENT_SMALL_CORE`
- `PILLOW_DECISION: APPROVE_FOR_P2_NO_VERSION_CHANGE`
- `OPENCV_DECISION: POC_REQUIRED`
- `DEPENDENCIES_ADDED: NONE`
- `MODEL_ARTIFACTS_ADDED: NONE`
- `MILESTONE_DAG_CHANGED: NO`
- `P2_M1_TASK_GRAPH_CHANGED: CONTRACT_ONLY`
- `CHANGE_CONTROL_ITEMS: T01_AUTHORITY_PR1_MVR_MEDIAPIPE_FACT_SPLIT`
- `PLAN_STATUS: READY_FOR_EXECUTION`
