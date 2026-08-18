# P2-M5 Execution Protocol

## Authority and state

- Milestone: `P2-M5 — Variable Isolation, Duplicate and Diversity QA`
- Entry baseline: P2-M4 freeze-state `5f2680e4d0724b409e13ac9cbe318b144cb0375f`
- Entry run: `32171351357`, attempt 2; all three jobs passed on the exact SHA
- Branch: `codex/phase2-m5-variable-isolation`
- State: `EXECUTING`
- Migration head at entry: `0013_warp_plan_authority`
- Architecture authority: ADR-021–041
- Public API impact: none
- Real-user facial processing: prohibited
- QuestionBank release: prohibited

This rolling-wave refinement authorizes only the bounded tasks below. It does not claim that the repository already
has four dimensions, three region groups, 24 holdout identities per dimension or frozen isolation/duplicate
thresholds. Principal accepted T01 after candidate `a39d9763f3a907bc7824994cd92fbe5c319b3acc` completed
same-SHA run `32176583182` with three successful jobs and seven verified artifacts. T02 candidate `9fb09fbc...` run
`32178257563` and T04 candidate `c80f32f6...` run `32179065826` subsequently passed the same three jobs with seven
verified exact-SHA artifacts each. Principal accepts both frozen contract surfaces and authorizes T03 only.

## Objective and non-goals

M5 builds replayable authority for target/non-target isolation, exact/near duplicate evidence and continuous
diversity/coverage reporting, then evaluates the preregistered P2-MVR-v1 target without weakening failure semantics.

M5 excludes:

- real-user photos, SelfState, questionnaire runtime, DesiredDelta and editing;
- beauty scores, sensitive classification, celebrity similarity or a population-standard face;
- new image/Vision/generation Provider selection or production enablement;
- prompt-only geometry, unversioned thresholds and post-holdout tuning;
- QuestionBank manifest/release/revoke, public/internal HTTP and M7 CLI;
- silently manufacturing missing identities, dimensions or region groups to force MVR PASS.

## Frozen contracts

```text
M3 canonical identity/Asset/QA
→ M4 specification/run/result/measurements
→ immutable SyntheticEvaluationPolicy
→ append-only IsolationReport
→ exact SHA + first-party pHash/Hamming SimilaritySignature
→ append-only DuplicateCluster decision
→ immutable DiversityReport / effective cohort counts
→ separate technical Gate and P2-MVR-v1 result
```

`P2_M5_TECHNICAL_GATE` and `P2_MVR_V1_RESULT` are independent. M6 release remains closed unless both are PASS.

The planned forward migration is `0014_variable_isolation_coverage.py`, revision
`0014_m5_eval_authority`, down revision `0013_warp_plan_authority`. T03 must prove the final schema on real
PostgreSQL; T01 does not create or migrate tables.

## Common bounded-task contract

Every delegated task starts with `BOOTSTRAP_STATUS: OK` and includes all repository-required packet fields.

- `INPUTS_AND_ASSUMPTIONS`: ADR-041, this protocol, the M5 research protocol, P2-M4 frozen evidence and unchanged
  Product Invariants. Missing research evidence must remain missing, not inferred.
- `SECURITY_NOTES`: private synthetic-only inputs, bounded resources, zero arbitrary URL/network, no committed binary
  or private payload and production fail closed.
- `PRIVACY_NOTES`: no User relation, real-person reference, sensitive classifier or real-user facial processing.
- `DATA_NOTES`: policy, split, report, signature, cluster and diversity evidence are versioned/immutable or append-only;
  no image, landmark array, Prompt, path, object key or Provider payload enters committed evidence.
- `LICENSE_NOTES`: first-party pHash/Hamming uses existing approved image decode boundary; `imagededup` remains rejected.
  Any download stays private and is not adoption approval.
- `ROLLBACK`: disable M5 execution and preserve evidence; schema downgrade is test/development-only before durable M5
  rows, otherwise use forward repair.
- `OUTPUT_FORMAT`: repository bounded-task report with status, files, validation, security/privacy/data/license,
  blockers, risks and handoff.
- `ESCALATION_CONDITION`: architecture, schema ownership, public API, Product Invariant, security/privacy boundary,
  dependency disposition, threshold semantics or task objective changes return to Principal.

## Execution tasks

### P2-M5-T01 — Freeze M5 authority and execution protocol

- Objective/why: separate technical correctness from research sufficiency and freeze evaluation ordering before code.
- Why delegated: retained by Principal because this is architecture and Milestone refinement.
- Scope/allowed files: ADR-041, M5 research/execution/acceptance docs, MILESTONES, architecture, AGENTS and MEMORY.
- Expected change: governance only; M5 advances `COMMITTED → EXECUTION_READY`.
- Forbidden: production code, migration, dependency install, threshold choice, holdout execution and image generation.
- Dependencies: P2-M4 FROZEN and exact-SHA freeze evidence.
- Acceptance: authority, split/count rules, task DAG, stop rules and M6 blocker are unambiguous.
- Validation: `pnpm.cmd format:check`, `git diff --check`, Markdown/invariant/conflict scan.
- Agent/model: Principal / Sol High.

### P2-M5-T02 — Evaluation domain contracts

- Objective/why: encode immutable policy, isolation formula, result taxonomy, region-group and cohort-count rules.
- Why delegated: bounded implementation after T01 acceptance.
- Scope/allowed modules: new M5 first-party domain modules and unit tests.
- Expected change: typed `SyntheticEvaluationPolicy`, `IsolationReport` input/result, split/cohort and state/reason types.
- Forbidden: ORM/migration, pHash implementation, orchestration, thresholds/holdout values and public API.
- Dependencies: accepted T01.
- Acceptance: canonical digests are stable; unknown/missing/non-finite/leaking inputs fail closed; technical/MVR results
  cannot be conflated.
- Validation: Ruff, strict mypy, targeted deterministic/negative pytest.
- Agent/model: backend worker / Terra Medium.

### P2-M5-T03 — PostgreSQL evaluation authority

- Objective/why: persist policy/report/signature/cluster/diversity and split authority under immutable PostgreSQL rules.
- Why delegated: frozen but transaction/concurrency-heavy schema implementation.
- Scope/allowed files: ORM, forward `0014`, database repositories and PostgreSQL lifecycle/invariant/concurrency tests.
- Expected change: new M5 authority only; no modification of `0001`–`0013`.
- Forbidden: algorithm implementation, Worker orchestration, release tables and routes.
- Dependencies: T02 names integrated; T04 signature contract frozen.
- Acceptance: PostgreSQL rejects mutation, split leakage, duplicate final authority, invalid transitions and cluster race;
  downgrade is explicit and zero schema drift remains.
- Validation: fresh upgrade, `0013→0014→0013→0014`, `alembic check`, real PostgreSQL tests, Ruff/mypy.
- Agent/model: data worker / Terra High.

### P2-M5-T04 — First-party exact and perceptual duplicate core

- Objective/why: provide the minimal deterministic SHA-256/pHash/Hamming primitive without a heavyweight dependency.
- Why delegated: bounded numeric/image implementation isolated from policy decisions.
- Scope/allowed modules: first-party similarity module, non-human/golden numeric fixtures and unit tests.
- Expected change: versioned bounded pHash bitstring and Hamming distance; no threshold constant.
- Forbidden: `imagededup`, network/model dependency, ORM, clustering policy and automatic near-duplicate rejection.
- Dependencies: accepted T01; existing approved bounded image decode boundary.
- Acceptance: exact duplicates are exact; golden pHash/Hamming are deterministic across Windows/Linux; malformed/bomb/
  wrong-size inputs fail closed.
- Validation: Ruff, strict mypy, golden/negative pytest, platform replay, dependency/network scan.
- Agent/model: backend worker / Terra Medium.

### P2-M5-T05 — Cohort, calibration and preregistration

- Objective/why: measure variance/distributions and freeze exact policy/splits before final holdout.
- Why delegated: independent evaluation design after authority is implemented.
- Scope/allowed files: ignored private cohort manifests, redacted calibration evidence, exact policy/ontology versions,
  threshold and holdout preregistration docs/fixtures.
- Expected change: evidence-backed threshold versions or an explicit `FURTHER_RESEARCH` blocker.
- Forbidden: holdout execution before commit, identity reuse, silent asset replacement, threshold relaxation after access.
- Dependencies: T02–T04 accepted; sufficient QA-passed identities and M4 transform evidence exist.
- Acceptance: calibration/M4-seen/holdout disjoint by identity/Asset/SHA/cluster; per-dimension effective N and 24→48→96
  stop rule are machine-verifiable.
- Validation: manifest digests, overlap/cluster negative controls, repeated/platform variance, source/redaction scan.
- Agent/model: test worker / Terra Medium.

### P2-M5-T06 — Evaluation orchestration and recovery

- Objective/why: execute reports/signatures/clusters/diversity under at-least-once delivery without moving authority into
  Celery.
- Why delegated: complex but frozen recovery, lock-order and concurrency control flow.
- Scope/allowed modules: application/repository services, reference-only task, Job/Attempt integration and tests.
- Expected change: idempotent evaluation/reconcile/cancel/retry flow with append-only evidence.
- Forbidden: generation, new Provider, release/CLI/API or threshold selection.
- Dependencies: T03–T05 accepted and exact policy/cohort digests frozen.
- Acceptance: duplicate/crash/cancel/retry/concurrent cluster paths produce one valid authority or explicit terminal
  evidence; no orphan ambiguity.
- Validation: real PostgreSQL, Redis/Celery, duplicate delivery, lock order, recovery, zero-network and full regression.
- Agent/model: Terra High worker.

### P2-M5-T07 — Holdout, MVR result and complete integration Gate

- Objective/why: run the preregistered identity-disjoint holdout and report technical/MVR results separately.
- Why delegated: independent test/evidence responsibility.
- Scope/allowed files: evaluation harness/fixtures, redacted evidence, M5 CI generator and acceptance evidence.
- Expected change: actual per-dimension target/control, duplicate and diversity evidence; no production repair.
- Forbidden: post-holdout policy edits, invented N, M6 release, real data and live network AI.
- Dependencies: T02–T06 accepted; T05 exact preregistration committed.
- Acceptance: zero mandatory skip; effective N/region/direction calculations are reconstructable; full local and exact-SHA
  three-job CI/artifacts pass. MVR may honestly remain `FURTHER_RESEARCH`.
- Validation: full Python/TS/PG/Redis/Celery/Docker/contracts/Gitleaks/license/SBOM/Actions matrix.
- Agent/model: test + infra workers / Terra Medium, sequential ownership.

### P2-M5-T08 — Independent security and final review

- Objective/why: independently verify authority, data boundary, non-sensitive evaluation and honest result semantics.
- Why delegated: separation of implementation and Gate judgment.
- Scope/allowed files: read-only complete diff, schema, logs, artifacts and evidence; review reports only.
- Expected change: PASS/CONDITIONAL/FAIL findings; defects become `P2-M5-Rxx`.
- Forbidden: implementation repair, Gate weakening, M6 entry or result reclassification without evidence.
- Dependencies: T07 candidate complete.
- Acceptance: independent reviews confirm exact-SHA evidence, no holdout leakage, no sensitive/beauty logic, no new
  dependency/model/real data and correct technical/MVR separation.
- Validation: source/diff/schema/evidence/CI artifact review; unexecuted items remain `NOT VERIFIED`.
- Agent/model: security reviewer Terra High + final reviewer Sol High.

## DAG and collision domains

```text
M4 freeze PASS → T01 → Principal checkpoint
                         ├─ T02 domain ─┐
                         └─ T04 hash ──┴→ T03 data → T05 preregistration → T06 orchestration
                                                                        → T07 holdout/full Gate
                                                                        → T08 reviews/closure
```

T02 owns new domain modules, T04 owns similarity core, and their tests must be disjoint. T03 owns the only migration,
models and database tests. T05–T08 are sequential. No two write tasks may own the same protocol, migration, CI workflow,
acceptance state or evidence generator.

## CC-P2-M5-01 — Forward research evidence expansion

T05 candidate `e46d7a9d19eee536c2f57cac6de224cccf27f2be` and run `32187946640` were accepted as an honest
`FURTHER_RESEARCH` stop decision. That decision remains immutable. ADR-042 defines a new serial change-control path:

```text
01-A governance/resource/candidate contract
→ 01-B 12-identity calibration-only cohort
→ 01-C candidate measurement/transform/threshold calibration
→ 01-D ontology/policy/split preregistration checkpoint
→ 01-E 24-identity sealed holdout
→ T06/T07 only after every prerequisite passes
```

- This is not a Repair Task and does not create T09/T10.
- Stage A changes governance only and does not generate images, install dependencies or change schema/OpenAPI.
- Stage B is bounded to 12 accepted identities, 18 total attempts, one retry per item and concurrency 1.
- Stage C must report the complete candidate family, including failures; no dimension is READY by construction.
- Stage D must freeze at least four bidirectional candidates across three non-sensitive region groups and every
  threshold/algorithm/runtime/model/split digest before holdout.
- Stage E remains closed until a tracked Stage D acceptance. Its first envelope is 24 effective identities and at most
  36 generation attempts.
- The official MediaPipe wheels remain rejected; only exact-manifest private synthetic runtimes may be used.
- Current age/style authority is ADR-028–030 and `P2_AGE_PRESENTATION_CONTROL_V2.md`.

Complete acquisition, candidate, blindness, negative-control and stop rules are in
`P2_M5_EVIDENCE_EXPANSION_PROTOCOL.md`.

## Repair, closure and stop protocol

Implementation defects use `P2-M5-R01...`. Architecture, privacy, schema ownership, dependency adoption, research
objective or Phase-boundary changes require forward change control.

```text
targeted validation
→ full local Gate
→ candidate commit/push
→ exact-SHA Actions and artifact inspection
→ independent security/final review
→ bounded Rxx repairs
→ Principal technical and MVR decisions
→ acceptance closure CI
→ freeze-state CI
```

Only Principal may declare M5 PASS/FROZEN. A technical PASS with MVR `FURTHER_RESEARCH` may freeze the reusable M5
engine, but M6 entry remains closed and the missing research evidence stays durable.

`P2_M5_STATE: EXECUTING`

`P2_M5_IMPLEMENTATION: CC_P2_M5_01_B_EXECUTION_READY`

`P2_M5_T05_DISPOSITION: ACCEPTED_FURTHER_RESEARCH`

`CC_P2_M5_01_A: PASS_AT_9993e01_RUN_32189725291`

`CC_P2_M5_01_B_ENTRY: OPEN`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`
