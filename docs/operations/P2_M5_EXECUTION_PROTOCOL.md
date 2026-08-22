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

## CC-P2-M5-02 — Stage C failure-mechanism isolation

Stage C candidate `042f77e4b6708be827f2033a9740e348ae778f69` and run `32237678569` attempt 2 remain
immutably accepted as `FURTHER_RESEARCH`. ADR-047 adds a diagnosis-only forward path because the old runner collapsed
plan-construction, warp-plan and transform `ValueError` failures into `PLAN_BUILD_FAILED`:

```text
02-G governance and closed-Gate contract
→ 02-A versioned diagnostic harness
→ 02-B immutable private-report/case manifest
→ 02-C serial Windows/Linux private replay
→ 02-D redacted failure-mechanism decision
→ 02-E independent reviews
→ separate redesign change control or FURTHER_RESEARCH
```

- CC02 does not create a threshold, algorithm-v2, formula-v2, new identity, holdout or READY dimension.
- The CC01C manifest, six candidates, 12 calibration identities, two platforms, two directions, two magnitudes and all
  accepted digests remain immutable.
- CC02-A cannot access private inputs. CC02-B tracked acceptance is mandatory before private replay.
- The replay is capped at 576 transforms, 604 Vision executions, zero generation, zero retry and global concurrency 1.
- The exhaustive `p2-m5-cc02-terminal-taxonomy-v1` has eight stages through `RESULT_SIGNATURE`; an unlisted stage,
  reason or stage/code pair hard-stops as `UNCLASSIFIED_TERMINAL_FAILURE`.
- Windows private replay requires a pre-read verified outbound deny covering the runner and every child Vision/runtime
  process. Capture alone is not containment; Linux remains `--network none`.
- The 14 direction mismatches have no accepted legacy result artifact. Their one recomputed result per platform case is
  new diagnostic evidence and cannot be represented as a legacy-success drift comparison.
- Missing accepted private reports or digest mismatch ends as `FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE`.
- Diagnostic completion does not change old 0/4 eligibility or open Stage D/E, T06–T08, MVR or M6.
- CC02-G candidate `137157c41e7b1436ae47fe7dfcf34a7127789166` passed run `32267510703` attempt 1 with all three
  jobs and eight readable exact-SHA artifacts. Independent security and final reviews passed. Principal acceptance only
  opens a separate CC02-A bounded-task contract; it does not execute the harness or permit private input.
- CC02-A contract candidate `d8659ae88fb32c99220d522fc6dbf94a8fc588ac` passed run `32271571196` attempt 1 with all
  three jobs and eight readable exact-SHA artifacts. Independent security and final reviews passed. Principal acceptance
  makes only the frozen bounded implementation `EXECUTION_READY`; it does not execute the harness or permit private
  input.
- CC02-A implementation plus R04 candidate `ee19ad6efe49decfa3a0c8f0dbf3f130b5c59460` passed run
  `32282614608` attempt 1 with all three jobs, eight readable exact-SHA artifacts and Browser Integration 5/5. The
  diagnostic harness passed its 58-test targeted contract matrix, and independent implementation/security/final review
  found no mandatory issue. Principal acceptance opens only preparation of a separate CC02-B contract; private input
  remains prohibited until CC02-B tracked acceptance.
- Acceptance closure `470849f0f42f151d1ec939e3b0d81ef4369ea86c` passed run `32284285946` with all three jobs,
  Browser Integration 5/5 and eight exact-SHA artifacts. CC02-A is complete; the current candidate is only the separate
  CC02-B bounded-task contract. It neither reads private input nor creates the real manifest.
- CC02-B builder/R05 candidate `298420fcc362851b96c1005e25608f37b2016373` passed run `32299835326`, attempt 1,
  with all three jobs, Browser Integration 5/5 and eight readable exact-SHA artifacts. Fresh ADR-048 security/privacy and
  final reviews passed. Principal accepts the builder and records the exact pre-read Gate; private input remains absent and
  can be released only during a separately established ADR-048 exclusive-custody window.

The exact authority, reason taxonomy, integrity Gates, resources and stop rules are in
`P2_M5_CC02_FAILURE_MECHANISM_PROTOCOL.md`.

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

`P2_M5_IMPLEMENTATION: CC_P2_M5_01_C_ACCEPTED_FURTHER_RESEARCH`

`P2_M5_T05_DISPOSITION: ACCEPTED_FURTHER_RESEARCH`

`CC_P2_M5_01_A: PASS_AT_9993e01_RUN_32189725291`

`CC_P2_M5_01_B_ENTRY: PASS_AT_7282094_RUN_32197326163`

`CC_P2_M5_01_C_MANIFEST: PASS_AT_B0B60EB_RUN_32199176469`

`CC_P2_M5_01_C_EXECUTION: ACCEPTED_FURTHER_RESEARCH_AT_042F77E_RUN_32237678569_ATTEMPT_2`

`CC_P2_M5_01_D_TO_E: CLOSED_BY_STAGE_C_COMPLETE_CASE_RULE`

`CC_P2_M5_02_G: PASS_AT_137157C_RUN_32267510703_ATTEMPT_1`

`CC_P2_M5_02_A: IMPLEMENTATION_ACCEPTED_AT_EE19AD6_RUN_32282614608_ATTEMPT_1`

`CC_P2_M5_02_A_CONTRACT: PASS_AT_D8659AE_RUN_32271571196_ATTEMPT_1`

`CC_P2_M5_02_A_IMPLEMENTATION: PASS_AT_EE19AD6_RUN_32282614608_ATTEMPT_1`

`CC_P2_M5_02_A_CLOSURE: PASS_AT_470849F_RUN_32284285946`

`CC_P2_M5_02_B_CONTRACT: PASS_AT_F69361E_RUN_32287419743_ATTEMPT_1`

`CC_P2_M5_02_B_BUILDER: PASS_AT_298420F_RUN_32299835326_ATTEMPT_1`

`P2_M5_R05: REPAIR_ACCEPTED_AT_298420F_RUN_32299835326_ATTEMPT_1`

`CC_P2_M5_03_LOCAL_PUBLICATION_TRUST_BOUNDARY: ACCEPTED_AT_298420F_RUN_32299835326_ATTEMPT_1`

`LOCAL_PUBLICATION_CUSTODY_GATE: REQUIRED_FOR_REAL_BUILDER_INVOCATION`

`CC02_B_BUILDER_PRE_READ_GATE: PASS_AT_298420F_RUN_32299835326_ATTEMPT_1`

`HISTORICAL_CC_P2_M5_02_B_MANIFEST: NOT_CREATED_SUPERSEDED_BY_LOCAL_PASS`

`HISTORICAL_CC_P2_M5_02_PRIVATE_INPUT: PRIVATE_INPUT_RELEASE_REQUIRED_SUPERSEDED_BY_RECOVERY_PASS`

`CC_P2_M5_02_C_TO_E: CLOSED`

`HISTORICAL_P2_M5_NEXT_ACTION: COMPLETE_LOCAL_VALIDATION_THEN_CANDIDATE_CI`

`HISTORICAL_P2_M5_NEXT_ACTION: SECURE_FIXED_PRIVATE_INPUT_RELEASE_THEN_REPEAT_CUSTODY_PREFLIGHT`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

## Principal-managed private-input delegation alignment

ADR-049 applies forward without changing ADR-048 or any M5 research authority. The two CC02 legacy reports are
`PRIVATE_SENSITIVE_INPUT`; Owner releases each unchanged input to Principal once, and Principal retains registry,
digest/type/scope validation, custody, cleanup and Gate authority. Because the shared Agent workspace cannot prove
ADR-048 immediate Principal snapshot across a delegated writer, the default unique executor is
`PRINCIPAL_EXECUTES_SENSITIVE_STEP`. Reviewers receive only tracked manifest/preregistration plus redacted status;
ordinary CI never receives either report.

The original Stage C task receipt proved both task-owned locators without broad disk discovery. Principal recovered and
validated the exact original reports, established ADR-048 exclusive custody, invoked the accepted builder exactly once
and took the immediate canonical/path/type/hash/diff snapshot before clearing the injected environment. The manifest
snapshot digest is `5a0479a21556498d259572a050d659a0e3617429f83e5fd313c842a35591e0a3`. Exact-SHA run
`32332408245` and both independent reviews accepted the CC02-B tracked evidence; that acceptance does not open CC02-C
or any downstream Gate.

`PRIVATE_INPUT_DELEGATION_GOVERNANCE: PASS_AT_96CA439_RUN_32332408245_ATTEMPT_1`

`PRIOR_PRINCIPAL_OUTPUT_RECOVERY: PASS`

`CC02_UNIQUE_BUILDER_EXECUTOR: PRINCIPAL_COMPLETED_EXACTLY_ONCE`

`CC_P2_M5_02_B_MANIFEST: PASS_AT_96CA439_RUN_32332408245_ATTEMPT_1`

`CC_P2_M5_02_C_TO_E: CLOSED`

`CC_P2_M5_02_C_ENTRY: CLOSED_PENDING_SEPARATE_BOUNDED_CONTRACT`

`P2_M5_NEXT_ACTION: PREPARE_SEPARATE_CC02_C_BOUNDED_CONTRACT_NO_EXECUTION`

## CC02-C bounded-task contract local candidate

Closure checkpoint `3338b263eb3bdcd507ed6007c20b35d8f2070685` passed exact-SHA run `32333890093` with all
three jobs and eight inspected artifacts. It confirms the CC02-B acceptance state only; it does not authorize replay.

The new `P2_M5_CC02_C_TASK_CONTRACT.md` is a governance-only local candidate. It freezes a non-private tracked driver
implementation Gate followed by a separate Principal pre-read Gate. Only after both Gate checkpoints pass may
Principal execute Linux and Windows serial private replay under ADR-048/049 custody and platform containment. The
contract candidate itself creates no driver, report, receipt, transform or Vision evidence and reads no private input.

`CC_P2_M5_02_C_CONTRACT: READY_FOR_TRACKED_CONTRACT_EVIDENCE`

`CC_P2_M5_02_C_ENTRY: CLOSED_PENDING_TRACKED_CONTRACT_ACCEPTANCE`

`CC_P2_M5_02_C_DRIVER: CLOSED_PENDING_CONTRACT_ACCEPTANCE`

`CC02_C_RUNNER_PRE_READ_GATE: CLOSED_PENDING_TRACKED_DRIVER_ACCEPTANCE`

`CC_P2_M5_02_C_REPLAY: NOT_EXECUTED`

`CC_P2_M5_02_D_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_M5_NEXT_ACTION: VALIDATE_AND_TRACK_CC02_C_CONTRACT_CANDIDATE_NO_REPLAY`

## CC02-C bounded-task contract tracked acceptance

Candidate `bdba03b6abbb4ac849076976afa30e2b0ca2f055` passed run `32335732640` and independent security review. Final
review found one stale Phase 2 summary, so Principal created bounded repair R07 without modifying the contract blob.
Repair `8213b401a28c873e92d813eda4f40dc24983dd4f` passed run `32336519837`, eight-artifact inspection and independent
security/final reviews. Principal accepts R07 and the contract-only checkpoint.

Only the future first-party driver and synthetic/numeric tests are now execution-ready. The implementation worker may
not receive a private locator or byte. Principal cannot record the pre-read Gate until that exact driver receives its
own full local, same-SHA artifact and independent-review acceptance.

`P2_M5_R07: REPAIR_ACCEPTED_AT_8213B40_RUN_32336519837_ATTEMPT_1`

`CC_P2_M5_02_C_CONTRACT: PASS_AT_8213B40_RUN_32336519837_ATTEMPT_1`

`CC_P2_M5_02_C_DRIVER: EXECUTION_READY_SYNTHETIC_ONLY_NO_PRIVATE_INPUT`

`CC02_C_RUNNER_PRE_READ_GATE: CLOSED_PENDING_TRACKED_DRIVER_ACCEPTANCE`

`CC_P2_M5_02_C_REPLAY: NOT_EXECUTED`

`CC_P2_M5_02_D_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

`P2_M5_NEXT_ACTION: IMPLEMENT_CC02_C_DRIVER_SYNTHETIC_ONLY_NO_PRIVATE_INPUT`

## CC02-C driver R08 tracked acceptance and pre-read checkpoint

Initial driver candidate `0b8690ae19c3d375d89734140f6da9c6a0cd9438` passed same-SHA CI but independent
final review found that its redacted receipt omitted the contract-required containment outcome. Principal classified
the defect as bounded repair `P2-M5-R08`; no private input was read and the pre-read Gate remained closed.

Repair `410dcb99a35b2a327405ae91b9ca51d1a2aba488` changes only the driver and its synthetic/numeric test. Each
platform now records fixed allowlisted `ESTABLISHED` only after its custody containment Gate succeeds. Receipt
projection requires the exact Linux/Windows mapping, rejects missing/unknown/extra outcomes, and is constructed before
the create-once sink. Run `32343563224`, attempt 1, all eight artifacts and both independent reviews passed.

Principal accepts R08 and the exact driver/test blobs. The pre-read Gate disposition is recorded here, but no private
input may be recovered or read until this governance checkpoint itself passes same-SHA CI, artifact inspection and
independent review. CC02-C replay is not executed in this checkpoint.

`P2_M5_R08: REPAIR_ACCEPTED_AT_410DCB9_RUN_32343563224_ATTEMPT_1`

`CC_P2_M5_02_C_DRIVER: PASS_AT_410DCB9_RUN_32343563224_ATTEMPT_1`

`CC02_C_RUNNER_PRE_READ_GATE: PASS_PENDING_ACCEPTANCE_CHECKPOINT_CI`

`CC_P2_M5_02_C_REPLAY: NOT_EXECUTED`

`CC_P2_M5_02_D_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

`P2_M5_NEXT_ACTION: VALIDATE_PRE_READ_ACCEPTANCE_CHECKPOINT_NO_PRIVATE_READ`

## CC02-C pre-read acceptance and evidence-location stop

Pre-read checkpoint `d134517fa97132b180a82c69c617b8f65d3b282e` passed run `32345071728`, all eight
exact-SHA artifacts and both independent reviews. Principal accepts the checkpoint and the exact previously accepted
driver/test blobs.

Bounded recovery used the original Codex task receipt only. It recovered the exact Stage B authority root, 12
normalized-source nodes, 12 Vision/landmark-log nodes, the accepted Windows Vision/model nodes and the Windows legacy
report without recording a locator. The qualified Linux legacy-report capability was not recoverable from the retained
receipt/registry state; prior environment references were absent, the accepted Debian 13 image was no longer present
and current PostgreSQL contained no surviving Stage B Asset rows.

ADR-049 forbids scanning parents, disks or Docker volumes to rediscover the missing capability. ADR-047 forbids
rebuilding the legacy report or inferring it from the redacted aggregate. Recovery therefore stops before any platform
private-byte read, transform, Vision call or output creation.

`CC02_C_RUNNER_PRE_READ_GATE: PASS_AT_D134517_RUN_32345071728_ATTEMPT_1`

`CC02_C_INPUT_RECOVERY: EVIDENCE_LOCATION_LOST`

`CC_P2_M5_02_C_REPLAY: NOT_EXECUTED_FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE`

`CC02_C_TRACKED_RECEIPT: NOT_CREATED`

`CC_P2_M5_02_D_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

`P2_M5_NEXT_ACTION: PREPARE_FORWARD_RECOVERY_FAILURE_CHANGE_CONTROL_NO_REGENERATION`

## P2-M5-R09 — CI pip security correction

Same-SHA run `32579872468` exposed a new supply-chain finding after its repository, migration, Python, TypeScript,
Docker, Playwright and browser steps had proceeded: `pip-audit --local` reported `PYSEC-2026-3721` for the locked
CI/build tool `pip==26.1.2`, with a minimum fixed version of `26.2`. This is a bounded forward repair, not a change
to any P2 algorithm, policy, private input, model, schema, API, runtime or acceptance threshold.

- Allowed change: replace only the exact existing `pip` pin in `requirements.lock` with the current official fixed
  release `26.2.1`, and update that lock's reviewed date.
- Required evidence: official-index availability, unchanged MIT license classification, requirements audit with no
  known vulnerability, `git diff --check`, locked-install compatibility and exact-SHA CI/artifact inspection.
- Forbidden: broad dependency upgrade, `--no-deps` CI bypass, audit suppression/ignore, workflow weakening, model or
  data download, private replay, threshold/research change, or reclassification of the CC02-C recovery stop.
- Gate effect: until the repair receives its own same-SHA CI evidence, the recovery-stop checkpoint remains
  `PENDING_SAME_SHA_RERUN_AFTER_EXTERNAL_REMEDIATION`; CC02-D/E, T06, MVR and M6 remain closed.

R09 completed its exact-SHA run `32580630760` on `b179c193b3a719142139b6d42e5be0c22ef4b225`: all three jobs and
eight artifacts passed inspection, the SBOM records `pip 26.2.1`, and independent security/final reviews passed.
Principal accepts this bounded repair and the unchanged recovery-stop content carried by the same SHA. It does not
open private replay, CC02-D/E, T06, MVR, M6, production geometry or real-user processing.

## CC-P2-M5-04 — Fresh evidence line after recovery stop

ADR-050 establishes a new, independent research line because CC02-C cannot be reconstructed without violating
ADR-047/049. `04-G` is governance only: it preserves the legacy stop, prohibits legacy input/output reuse and freezes
that future evidence must have new authority/digest/custody. It does not generate or process anything.

```text
04-G governance/separation
→ 04-A new resource/candidate proposal
→ 04-B fresh calibration
→ 04-C fresh calibration/diagnostic evidence
→ 04-D preregistration
→ 04-E holdout/review
→ separate M5 disposition
```

`CC_P2_M5_04_G: GOVERNANCE_ACCEPTED_AT_3AC41C3_RUN_32582621932_ATTEMPT_1`

`CC_P2_M5_04_A_PROPOSAL_PLANNING: ELIGIBLE_NOT_EXECUTION_AUTHORIZATION`

`CC_P2_M5_04_A_EXECUTION: CLOSED`

`CC_P2_M5_04_B_TO_E: CLOSED`

`P2_M5_NEXT_ACTION: PREPARE_CC04_A_PROPOSAL_NO_EXECUTION_OR_LEGACY_REUSE`

## CC-P2-M5-04-A — Fresh study proposal contract candidate

`P2_M5_CC04_A_PROPOSAL_TASK_CONTRACT.md` is the only current candidate work item under the accepted CC04-G boundary.
It is a Principal-owned, governance-only bounded-task contract. It contains no actual candidate, source, resource
count, algorithm, runtime, policy, ontology, threshold, split, budget, provider or private custody locator, and it
does not authorize execution, acquisition, generation, private-input access, model/download/install or `04-B` work.

The contract can be accepted only after its own local validation, normal non-force push, exact-SHA CI/eight-artifact
inspection and independent security/final review. Acceptance opens only a separate proposal-writing task with its own
explicit decision authority; it does not open proposal execution or any later CC04/M5 Gate.

`CC_P2_M5_04_A_CONTRACT: READY_FOR_TRACKED_CONTRACT_EVIDENCE`

`CC_P2_M5_04_A_PROPOSAL_WRITING: CLOSED_PENDING_CONTRACT_ACCEPTANCE`

`CC_P2_M5_04_A_EXECUTION: CLOSED`

`CC_P2_M5_04_B_TO_E: CLOSED`

## P2-M5-R11 — CC04-A contract-disposition ordering correction

Independent final review of `e61ae7dbe3e81636237cb615a53cd29989869d9c` found that the latest
machine-readable next action could be read as direct preparation of the CC04-A proposal even though the new contract
correctly kept proposal writing closed pending Principal disposition. This repair changes no contract field, ADR,
research decision, source, candidate, resource count, algorithm, runtime, policy, ontology, threshold, split, budget,
custody, schema, API, workflow, dependency, model or private evidence.

R11 makes the contract-disposition checkpoint the sole current next action. It does not accept the contract itself and
does not open proposal writing, 04-A execution, 04-B–E, T06, MVR, M6, production geometry or real-user processing.

`P2_M5_R11: READY_FOR_TRACKED_EVIDENCE`

`CC_P2_M5_04_A_CONTRACT: READY_FOR_TRACKED_CONTRACT_EVIDENCE`

`CC_P2_M5_04_A_PROPOSAL_WRITING: CLOSED_PENDING_CONTRACT_ACCEPTANCE`

`CC_P2_M5_04_A_EXECUTION: CLOSED`

`CC_P2_M5_04_B_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

`P2_M5_NEXT_ACTION: COMPLETE_CC04_A_CONTRACT_DISPOSITION_BEFORE_PROPOSAL_WRITING_NO_EXECUTION`

## CC04-A contract acceptance after P2-M5-R11

R11 `10931438912410b235977bf79debde7d980a7e70` passed exact-SHA run `32584548148`: all three jobs succeeded and all
eight artifacts were readable and unexpired. Principal inspected the artifact evidence and accepted both independent
R11 reviews. Principal accepts the CC04-A proposal-only contract, not a fresh study or execution authority.

This opens exactly one governance-writing task: create its versioned fresh-study proposal and decision register, or
return an explicit stop. The task remains prohibited from selecting or executing a source/candidate/resource envelope,
algorithm/runtime, policy/ontology, threshold/split, budget or private custody. It opens neither `04-A` study execution
nor `04-B` through `04-E`.

`P2_M5_R11: REPAIR_ACCEPTED_AT_1093143_RUN_32584548148_ATTEMPT_1`

`CC_P2_M5_04_A_CONTRACT: PASS_AT_1093143_RUN_32584548148_ATTEMPT_1`

`CC_P2_M5_04_A_PROPOSAL_WRITING: EXECUTION_READY_PROPOSAL_ONLY`

`CC_P2_M5_04_A_EXECUTION: CLOSED`

`CC_P2_M5_04_B_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

`P2_M5_NEXT_ACTION: EXECUTE_CC04_A_PROPOSAL_WRITING_PER_ACCEPTED_CONTRACT_NO_STUDY_EXECUTION`

## CC04-A proposal-writing local candidate

Principal has created only the versioned CC04 fresh-study proposal and unresolved-decision register permitted by the
accepted CC04-A contract. They enumerate future admission evidence and honest stop conditions without selecting a
source, candidate, resource envelope, algorithm/runtime, policy/ontology, threshold/split, budget or custody
arrangement. No network, private input, asset, identity, model, Provider, generation, measurement, transform or
downstream Gate is involved.

`CC_P2_M5_04_A_PROPOSAL_WRITING: LOCAL_CANDIDATE_PENDING_VALIDATION`

`CC_P2_M5_04_A_EXECUTION: CLOSED`

`CC_P2_M5_04_B_TO_E: CLOSED`

`P2_M5_NEXT_ACTION: VALIDATE_CC04_A_PROPOSAL_ONLY_CANDIDATE_NO_STUDY_EXECUTION`

## CC04-A proposal-writing accepted

Candidate `ae8abd30b7de11e27ba9b7af04c53b2f79afef2a` passed local scoped governance validation, Python/static and
TypeScript/contract/build checks, and same-SHA run `32585964173` with all three jobs and eight inspected artifacts.
Independent security and final reviews both passed. Principal accepts only the versioned proposal and unresolved-decision
register: they provide a reviewable fresh-study planning boundary, not a resource, candidate, technical or execution
decision.

No currently unresolved register item has inherited authority. Any attempt to select a source, candidate, resource
envelope, algorithm/runtime, policy/ontology, threshold/split, budget or custody arrangement requires a new bounded
decision task and explicit authority. Until then, the honest next state is `OWNER_DECISION_REQUIRED`, not a default
execution path.

`CC_P2_M5_04_A_PROPOSAL_WRITING: PASS_AT_AE8ABD3_RUN_32585964173_ATTEMPT_1`

`CC_P2_M5_04_A_EXECUTION: CLOSED_PENDING_SEPARATE_DECISION_AUTHORITY`

`CC_P2_M5_04_B_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED_PENDING_TECHNICAL_AND_MVR_PASS`

`P2_M5_NEXT_ACTION: OWNER_DECISION_REQUIRED_BEFORE_ANY_CC04_A_STUDY_EXECUTION`

## CC-P2-M5-04-A-D01 — Owner Decision Closure contract candidate

The supplied Owner decision is first encoded through the Principal-owned D01 governance contract. Before D01 obtains
its own exact-SHA acceptance, no decision pack, fresh study, image generation, private-input access, cohort, runtime
qualification, measurement, transform, threshold, holdout, MVR evaluation, or `04-B` contract may begin.

`CC_P2_M5_04_A_D01_CONTRACT: LOCAL_CANDIDATE_PENDING_VALIDATION`

`CC04_A_OWNER_DECISION_CLOSURE: CLOSED_PENDING_D01_CONTRACT_ACCEPTANCE`

`CC04_B_CONTRACT_WRITING: CLOSED_PENDING_OWNER_DECISION_CLOSURE`

`CC04_B_CONTRACT: NOT_CREATED`

`CC04_B_EXECUTION: CLOSED_PENDING_SEPARATE_CONTRACT_ACCEPTANCE`

## CC-P2-M5-04-A-D01 accepted; Owner Decision Closure candidate

D01 was accepted at `7659eed48917b1491fd5fc8d18180c28f35944ec` after exact-SHA run `32592430642`, artifact inspection, and independent Security/Sol High reviews. The only next work item is the Owner Decision Closure candidate: record supplied Owner constraints in the decision pack and CC04 governance records. This is documentation only and cannot execute or otherwise prepare a fresh study.

`CC_P2_M5_04_A_D01_CONTRACT: PASS_AT_7659EED_RUN_32592430642`

`CC04_A_OWNER_DECISION_CLOSURE: LOCAL_CANDIDATE_PENDING_VALIDATION`

`CC04_B_CONTRACT_WRITING: CLOSED_PENDING_OWNER_DECISION_CLOSURE`

`CC04_B_CONTRACT: NOT_CREATED`

`CC04_B_EXECUTION: CLOSED_PENDING_SEPARATE_CONTRACT_ACCEPTANCE`
