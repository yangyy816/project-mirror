# P2-M5 Acceptance Evidence

## Status

- Milestone: `P2-M5 — Variable Isolation, Duplicate and Diversity QA`
- State: `EXECUTING`
- Entry baseline: `5f2680e4d0724b409e13ac9cbe318b144cb0375f`
- Entry migration head: `0013_warp_plan_authority`
- Public API change: none
- M6 entry: closed pending technical Gate and P2-MVR-v1 PASS

This is an acceptance skeleton. `PENDING` is not PASS evidence.

## Entry evidence

- Local and remote P2-M4 freeze-state are `5f2680e4d0724b409e13ac9cbe318b144cb0375f`.
- GitHub Actions run `32171351357`, attempt 2, passed `quality-and-integration`, `secret-scan` and
  `docker-validation` on that exact SHA.
- Seven artifacts are present, readable, unexpired and exact-SHA bound. The frozen regression JSON reports migration
  head `0013_warp_plan_authority`, unchanged OpenAPI digest and zero M1/M2/M3 failures/errors/skips. Gitleaks SARIF
  contains zero results.
- Attempt 1 was cancelled after a 35-minute Playwright Chromium download stall; attempt 2 completed the same step in
  68 seconds without repository changes. This is bounded external-download evidence, not a product repair.
- P2-M4 remains `FROZEN`; `jaw_width` remains `EXPERIMENTAL` and N=2 remains
  `FURTHER_RESEARCH_FOR_M5_ISOLATION`.
- The tracked worktree was clean at branch creation except protected existing `.tmp/`, which remains outside scope.

## Mandatory evidence matrix

| Gate                | Required evidence                                                  | Status   |
| ------------------- | ------------------------------------------------------------------ | -------- |
| Architecture        | ADR-041 and rolling-wave contracts accepted                        | T01 PASS |
| Domain              | policy/isolation/cohort/result types deterministic and fail closed | T02 PASS |
| Ontology            | new immutable version binds non-sensitive region groups            | PENDING  |
| Database            | forward `0014`, lifecycle, invariants, concurrency, zero drift     | T03 PASS |
| Isolation           | actual target error and every non-target delta retained            | T02 PASS |
| Similarity          | exact SHA and first-party pHash/Hamming golden evidence            | T04 PASS |
| Threshold           | calibration distribution and pre-holdout version freeze            | PENDING  |
| Split               | calibration/M4-seen/holdout/cluster leakage rejected               | T02 PASS |
| Duplicate           | append-only cluster membership and review decision                 | PENDING  |
| Diversity           | continuous coverage, occupancy, NN/yield/mode-collapse evidence    | PENDING  |
| Anti-homogenization | no single-template, beauty or sensitive-trait optimization         | PENDING  |
| Recovery            | retry/cancel/duplicate/reconcile and lock-order evidence           | PENDING  |
| Synthetic-only      | no User relation, real-person fixture or live AI CI                | PENDING  |
| Contracts           | public OpenAPI/generated TypeScript unchanged                      | PENDING  |
| Full Gate           | Python/TS/PG/Redis/Celery/Docker/Gitleaks/SBOM/same-SHA CI         | PENDING  |
| Review              | independent security and final review                              | PENDING  |

## Separate outcome ledger

| Outcome                | Current value   | Evidence                                                      |
| ---------------------- | --------------- | ------------------------------------------------------------- |
| `P2_M5_TECHNICAL_GATE` | `PENDING`       | T02–T08 not executed                                          |
| `P2_MVR_V1_RESULT`     | `NOT_EVALUATED` | only four canonical identities and one N=2 M4 dimension exist |
| M6 release entry       | `CLOSED`        | requires both outcomes to PASS                                |

## T01 acceptance

- ADR-041 freezes separate technical/MVR results, immutable `SyntheticEvaluationPolicy`, new ontology-version
  `region_group`, per-dimension cluster-adjusted holdout N, 24→48→96 stop rules, first-party SHA/pHash/Hamming and
  append-only isolation/duplicate/diversity authority.
- `P2_M5_EVALUATION_PROTOCOL.md` freezes the evaluation order and mandatory negative controls without fabricating
  missing cohort or thresholds.
- `P2_M5_EXECUTION_PROTOCOL.md` defines T01–T08, collision domains, validation, Repair protocol and closure sequence.
- No code, migration, dependency, model/image artifact, public API or holdout result is added by T01.
- Owner download authorization is retained as permission for task-required private acquisition only; it is not
  adoption, license, distribution, production or real-user processing approval.

`P2_M5_T01: PASS`

`P2_M5_STATE: EXECUTION_READY`

`P2_M5_TECHNICAL_GATE: PENDING`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M6_ENTRY: CLOSED`

## T01 tracked acceptance

- Candidate `a39d9763f3a907bc7824994cd92fbe5c319b3acc` completed GitHub Actions run `32176583182` with
  `quality-and-integration`, `secret-scan` and `docker-validation` successful.
- Seven artifacts are present, readable and exact-SHA bound. Phase 1/M1/M2/M3 evidence reports
  1/98/52/46 tests with zero failures and skips, current migration head `0013_warp_plan_authority`, and the unchanged
  OpenAPI digest. Gitleaks SARIF contains zero results.
- The Playwright download completed successfully in 3 minutes 34 seconds. No product repair, retry or Gate waiver was
  used.
- Principal accepts T01 and advances M5 to `EXECUTING`. T02 and T04 are open with disjoint collision domains; T03
  remains dependency-gated on their integrated contract names.
- This acceptance does not approve any MVR threshold, dimension promotion, new dependency, production geometry,
  real-user facial processing or QuestionBank release.

`P2_M5_T01_TRACKED_ACCEPTANCE: PASS`

`P2_M5_STATE: EXECUTING`

## T02 local candidate

- Added a pure first-party M5 domain module with no ORM, HTTP, storage, task-runner, image-library or Provider import.
- `SyntheticEvaluationPolicy` has an independent schema/digest, fixed 24→48→96 cohort stages and sorted immutable
  per-dimension rules. Region groups reject sensitive, beauty, population and age/sexual classification tokens.
- Cohort assignments reject identity/Asset/checksum/duplicate-cluster leakage across calibration, M4-seen and holdout;
  effective N is computed per dimension and counts one unit per duplicate cluster.
- Isolation evaluation retains actual signed requested/measured target delta, target error, all control deltas,
  non-target drift, repeat/platform variance, automatic hard-gate failures and deterministic report digest.
- `TechnicalGateResult` and `MvrResult` are separate types; technical PASS with `FURTHER_RESEARCH` is valid, while
  technical FAIL with MVR PASS is rejected.
- 41 new tests and 101 adjacent domain tests passed. Ruff format/lint covered all 207 service files, strict mypy passed
  123 source files, generated contracts had zero drift, and `git diff --check` passed.
- This is `READY_FOR_TRACKED_EVIDENCE`, not T02 acceptance. No ORM/migration, dependency, threshold/holdout value,
  image/model artifact, public API or production/real-user capability was added.

`P2_M5_T02: READY_FOR_TRACKED_EVIDENCE`

## T02 tracked acceptance

- Candidate `9fb09fbc922406d5881950f355629c3108656a24` run `32178257563` passed
  `quality-and-integration`, `secret-scan` and `docker-validation` on the exact candidate SHA.
- Seven downloaded artifacts are present and readable. Phase 1/M1/M2/M3 evidence binds the exact candidate,
  migration head `0013_warp_plan_authority` and unchanged OpenAPI digest; the suites report 1/98/52/46 tests with
  zero failures, errors or skips. Gitleaks SARIF contains zero results.
- Principal accepts T02 domain, isolation and split contracts. This acceptance does not select a tolerance,
  near-duplicate threshold, holdout cohort, dimension promotion or MVR result, and it does not authorize production
  geometry, real-user facial processing or QuestionBank release.
- T04 remains independently open. T03 stays dependency-gated until the T04 signature contract receives tracked
  acceptance and Principal integrates both contract surfaces.

`P2_M5_T02_TRACKED_ACCEPTANCE: PASS`

## T04 local candidate

- Added a first-party, versioned `SimilaritySignature` over checksum-bound canonical synthetic JPEG bytes with exact
  normalized SHA-256, a deterministic 64-bit `phash-dct-nearest-v1` value and threshold-free Hamming distance.
- Exact SHA equality is the only automatic duplicate hard gate. The implementation contains no near-duplicate
  threshold, clustering decision or automatic near-duplicate rejection.
- Malformed, checksum-mismatched, wrong-shape, oversized and tampered inputs fail closed without echoing image bytes,
  paths or caller content. The existing bounded canonical JPEG decode boundary is reused.
- Eleven focused tests passed on Windows and Linux Docker. Both platforms produced golden pHash
  `a00d812ea37eff0b`; 124 combined adjacent tests, Ruff over 209 service files, strict mypy over 124 sources,
  contract drift and `git diff --check` passed.
- No dependency, model, network path, ORM/migration, public API, tracked image fixture or automatic policy threshold
  was added. `imagededup` remains rejected.

`P2_M5_T04: READY_FOR_TRACKED_EVIDENCE`

## T04 tracked acceptance

- Candidate `c80f32f6adb0c1ed17ac14e97b5552739abec57c` run `32179065826` passed
  `quality-and-integration`, `secret-scan` and `docker-validation` on the exact candidate SHA.
- Seven downloaded artifacts are present and readable. Phase 1/M1/M2/M3 evidence binds the exact candidate,
  migration head `0013_warp_plan_authority` and unchanged OpenAPI digest; the suites report 1/98/52/46 tests with
  zero failures, errors or skips. Gitleaks SARIF contains zero results.
- Principal accepts T04. The similarity contract contains no selected threshold and cannot automatically reject a
  near-duplicate before a future evaluation-policy version is preregistered.
- T02 and T04 names/contracts are now integrated. T03 is authorized to implement only the frozen forward
  `0014_m5_eval_authority` PostgreSQL authority; T05–T08, MVR evaluation and M6 release remain closed.

`P2_M5_T04_TRACKED_ACCEPTANCE: PASS`

`P2_M5_NEXT_TASK: T03_AUTHORIZED`

## T04 acceptance checkpoint

- Acceptance checkpoint `8640879c586afcbf72c9ea1e67bef82992525bdd` run `32179662032` passed all three
  jobs. Seven downloaded artifacts bind the exact checkpoint and migration head `0013_warp_plan_authority`;
  Phase 1/M1/M2/M3 evidence remains at 1/98/52/46 tests with zero failures, errors or skips, and Gitleaks reports
  zero results.
- This closes the T02/T04 contract-integration checkpoint and leaves only T03 authorized. It does not advance the M5
  technical Gate or MVR result.

`P2_M5_T02_T04_CONTRACT_CHECKPOINT: PASS`

## T03 local candidate and P2-M5-R01

- Added forward migration `0014_variable_isolation_coverage.py` with revision `0014_m5_eval_authority`; historical
  migrations `0001`–`0013` remain unchanged. The ORM and PostgreSQL schema add immutable evaluation policy/rules,
  cohort assignments, isolation reports, similarity signatures/pairs, duplicate clusters/memberships/decisions and
  diversity reports without a User relation or public API change.
- PostgreSQL recomputes policy, signature and isolation-result digests; binds isolation reports to completed M4
  transforms and passed variant QA; derives target error, non-target drift, conclusion and reason codes; rejects
  mutation, split leakage, unqualified assets, fabricated facts and prohibited beauty/sensitive authority.
- `P2-M5-R01` closes bounded implementation defects found during Principal review: qualified cluster membership,
  authoritative digest/derived-fact validation, serialization of cluster/finalization/split races, four stale
  migration-head regression assertions and a driver-dependent exact-duplicate concurrency test expectation.
- A fresh PostgreSQL run passed all 14 T03 authority tests. The exact-duplicate race passed ten consecutive replays;
  the complete Linux API/Worker suite collected 566 tests and completed at 100% with only existing optional
  environment-gated skips. Fresh upgrade, `0013→0014→0013→0014` and both `alembic check` runs passed.
- Ruff format/lint passed all 211 service files, strict mypy passed 124 source files, `pnpm.cmd check` passed 54 Web
  tests and the production build, generated contracts had zero drift, and `git diff --check` passed.
- This candidate remains `READY_FOR_TRACKED_EVIDENCE`. Exact-SHA GitHub Actions, seven artifact inspection and
  Principal acceptance are still mandatory before T03 PASS or T05 entry. No threshold, cohort, holdout, MVR result,
  dependency/model adoption, production geometry, real-user processing or QuestionBank release is approved.

`P2_M5_T03: READY_FOR_TRACKED_EVIDENCE`

`P2_M5_R01: LOCAL_PASS_PENDING_TRACKED_EVIDENCE`

`P2_M5_NEXT_TASK: T03_TRACKED_EVIDENCE`

## T03 tracked acceptance

- Candidate `277c69aad491e31241142990d94b843fd7b18700` run `32186155269` passed
  `quality-and-integration`, `secret-scan` and `docker-validation` on the exact candidate SHA.
- Seven artifacts are present, readable and unexpired. Phase 1/M1/M2/M3 evidence binds the exact SHA, migration head
  `0014_m5_eval_authority` and unchanged OpenAPI digest; the suites report 1/98/52/46 tests with zero failures,
  errors or skips. Gitleaks SARIF contains zero results.
- Docker and Celery logs contain no execution error; the only case-insensitive `error` match is Redis module
  configuration field `bf-error-rate`. License inventories and the 105-component Python SBOM are readable.
- Principal accepts T03 and R01. This acceptance establishes database authority only; it does not preregister a
  threshold or cohort, execute holdout/MVR, approve a new dependency/model, enable production geometry or real-user
  processing, or authorize QuestionBank release.
- T05 opens only for calibration/cohort/preregistration. T06–T08, the technical Gate, MVR result and M6 remain
  closed/pending.

`P2_M5_T03_TRACKED_ACCEPTANCE: PASS`

`P2_M5_R01: PASS`

`P2_M5_NEXT_TASK: T05_AUTHORIZED`

## T03 acceptance checkpoint

- Acceptance checkpoint `6efd2dce4f4205d76af156c65b78f36f6910f52b` run `32186910142` passed all
  three jobs. Seven artifacts are present, readable and exact-SHA bound; Phase 1/M1/M2/M3 evidence reports
  `0014_m5_eval_authority`, unchanged OpenAPI and 1/98/52/46 tests with zero failures/errors/skips. Gitleaks reports
  zero results.
- This checkpoint confirms the forward T03/R01 acceptance state and opens only T05.

`P2_M5_T03_ACCEPTANCE_CHECKPOINT: PASS`

## T05 local preregistration decision

- `P2_M5_T05_READINESS_EVIDENCE.json` binds the accepted M3 authority and M4 preregistration, calibration,
  evaluation and corrected split authority by SHA-256.
- All four canonical identities were already used in M4 and are classified `M4_SEEN`; M5 calibration and holdout
  counts are both zero. Current evidence has one `EXPERIMENTAL` `jaw_width`, zero READY dimensions and no frozen
  M5 region-group ontology version.
- T05 therefore selects no target/control tolerance, pHash threshold, new ontology/policy version or final cohort
  digest. It does not access or execute holdout and keeps T06 closed.
- Two deterministic tests verify source digests, exact M4 split reconstruction, M4-seen classification, zero holdout,
  canonical document digest, fail-closed booleans and absence of private/false authority fields. Ruff, Prettier and
  `git diff --check` pass.
- The honest T05 outcome is `FURTHER_RESEARCH`, while the global P2-MVR-v1 result remains `NOT_EVALUATED`. A forward
  research change control is required to acquire identity-disjoint calibration/holdout cohorts and candidate
  dimensions; this cannot be packaged as a Repair or silently expanded inside T05.

`P2_M5_T05: READY_FOR_TRACKED_EVIDENCE`

`P2_M5_T05_OUTCOME: FURTHER_RESEARCH`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M5_T06_ENTRY: CLOSED`

## CC-P2-M5-01 Stage C local stop candidate

- The accepted immutable manifest was executed on the exact Windows and qualified zero-network Linux runtimes. The
  first Debian 12 composition is retained as failed ABI evidence; the qualified Linux run used the existing Debian 13
  composition without changing the manifest, model, transform runtime or case set.
- The two qualified reports contain the same 288 cases. Combined evidence contains 1,032 successful transform/Vision
  rows, 232 failed platform cases, zero same-platform repeat variance and maximum cross-platform measurement difference
  `4.9965088934289525e-05`.
- The aggregate fixes a pre-checkpoint evidence defect: Windows/Linux copies of the same case are reproducibility pairs,
  not duplicate identities. Source and variant duplicate evidence now compare distinct identities within one platform;
  both report zero exact-duplicate pairs. No pHash threshold was selected.
- Manual review covers all 172 successful cross-platform repeat-1 pairs / 344 artifacts and finds no visible warp tear,
  duplicated feature, disconnected contour or background seam. It does not override automatic or completeness failure.
- All six candidates have at least one missing or direction-failed case. Under the preregistered complete-case rule,
  Stage D has zero eligible candidates versus four required. The honest local result is `FURTHER_RESEARCH`; no threshold,
  `READY`, holdout, MVR, production geometry, real-user processing, M6 or QuestionBank release opens.
- Redacted evidence is `docs/research/P2_M5_CC01C_CALIBRATION_AGGREGATE.json`; the report and private review digests are
  recorded in `docs/research/P2_M5_CC01C_CALIBRATION_REPORT.md`. Images, landmarks, Vision logs and private paths remain
  outside Git.

`CC_P2_M5_01_C: LOCAL_FURTHER_RESEARCH_PENDING_TRACKED_EVIDENCE`

`CC_P2_M5_01_D_TO_E: CLOSED`

`P2_M5_T06_TO_T08_ENTRY: CLOSED`

`P2_M6_ENTRY: CLOSED`

## CC-P2-M5-01 Stage C tracked acceptance

- Candidate `042f77e4b6708be827f2033a9740e348ae778f69` completed GitHub Actions run `32237678569`, attempt 2, with
  `quality-and-integration`, `secret-scan` and `docker-validation` successful. Attempt 1 is retained as bounded external
  failure evidence: every product, migration, Python and TypeScript step before Playwright passed, but the Chromium
  download had no runner heartbeat for more than 60 minutes and was cancelled before a same-SHA retry. No repository
  repair or Gate change was made.
- Seven artifacts are present, readable, unexpired and exact-SHA bound. Phase 1/M1/M2/M3 evidence records migration head
  `0014_m5_eval_authority`, unchanged OpenAPI digest
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841` and `1/98/52/46` tests with zero
  failures, errors or skips. Gitleaks SARIF has one run and zero results; Docker and Celery logs have zero failure,
  traceback, deadlock or fatal matches.
- The full Python suite passed 582 tests with one existing optional private-runtime skip; five Playwright tests passed.
  Dependency/license and SBOM artifacts are readable. This remote evidence reproduces the committed Stage C aggregate
  and does not alter any candidate measurement or failure.
- Principal accepts Stage C only as an evidence-backed `FURTHER_RESEARCH` stop. All six candidates have failed/missing
  cases and zero satisfy the immutable complete-case rule versus four required. No threshold, READY dimension,
  ontology/policy freeze, Stage D/E, T06–T08, MVR execution, production geometry, real-user processing, M6 or
  QuestionBank release is authorized.

`CC_P2_M5_01_C: ACCEPTED_FURTHER_RESEARCH_AT_042F77E_RUN_32237678569_ATTEMPT_2`

`CC_P2_M5_01_D_TO_E: CLOSED_BY_STAGE_C_COMPLETE_CASE_RULE`

`P2_M5_T06_TO_T08_ENTRY: CLOSED`

`P2_M6_ENTRY: CLOSED`

## CC-P2-M5-01 Stage B tracked acceptance

- Candidate `7282094406b9754368709f543c4fda54b2e57490` run `32197326163` passed
  `quality-and-integration`, `secret-scan` and `docker-validation` on the exact candidate SHA.
- Seven artifacts are present, readable and unexpired. Phase 1/M1/M2/M3 evidence binds the exact SHA, migration head
  `0014_m5_eval_authority` and unchanged OpenAPI digest; the suites report 1/98/52/46 tests with zero failures,
  errors or skips. Gitleaks SARIF contains one run and zero results.
- Docker evidence completed its health/smoke path. Celery evidence contains no execution error; the Docker log's two
  case-insensitive error-like matches are PostgreSQL shutdown of its logical-replication launcher and Redis's
  `bf-error-rate` configuration field, not test failures.
- Principal accepts Stage B as bounded calibration acquisition evidence. This does not select a near-duplicate
  threshold, promote a dimension, authorize a transform, execute a holdout/MVR, approve production geometry or
  real-user processing, or authorize M6/QuestionBank release.
- Stage C opens only for the exact candidate-manifest checkpoint required before reading candidate measurements.
  Measurement, transform and threshold-calibration execution remain closed until that manifest passes tracked
  acceptance.

`CC_P2_M5_01_B: PASS_AT_7282094_RUN_32197326163`

`CC_P2_M5_01_C_MANIFEST: AUTHORIZED`

`CC_P2_M5_01_C_EXECUTION: CLOSED_PENDING_MANIFEST_ACCEPTANCE`

`CC_P2_M5_01_D_TO_E: CLOSED`

## CC-P2-M5-01 Stage C manifest tracked acceptance

- `docs/research/P2_M5_CC01C_CANDIDATE_MANIFEST.json` freezes the complete six-candidate family, four non-sensitive
  region groups, exact normalized-X/Y formulas, source-relative plan builders, `15_000/30_000 ppm` grid, two
  platforms, three repeats, all non-target controls, complete-case rules and failure interpretations. Its content
  digest is `eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4`.
- The manifest binds the accepted private Vision/model/topology and OpenCV runtime digests. It adds no dependency,
  model, binary, schema, public API or production path.
- The deterministic test verifies manifest content addressing, complete candidate/control coverage, redaction,
  synthetic-only boundaries and the absence of any Stage C threshold or READY claim.
- Candidate `b0b60eb29336d74a0f4c7628c9d1d1458d11d3f9` run `32199176469` passed
  `quality-and-integration`, `secret-scan` and `docker-validation`. All seven artifacts were readable, unexpired and
  exact-SHA bound. Evidence records migration head `0014_m5_eval_authority`, unchanged OpenAPI digest
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`, frozen-regression counts
  `1/98/52/46` with zero failure/error/skip and zero Gitleaks results.
- Principal accepts the immutable premeasurement manifest. Only the exact Stage C execution encoded by that manifest
  is now open. Stage D-E, thresholds, dimension promotion, T06-T08, MVR, production geometry, real-user processing,
  M6 and QuestionBank release remain closed.

`CC_P2_M5_01_C_MANIFEST: PASS_AT_B0B60EB_RUN_32199176469`

`CC_P2_M5_01_C_EXECUTION: OPEN_EXACT_MANIFEST_ONLY`

## T05 tracked disposition

- Candidate `e46d7a9d19eee536c2f57cac6de224cccf27f2be` run `32187946640` passed
  `quality-and-integration`, `secret-scan` and `docker-validation` on the exact candidate SHA.
- Seven artifacts are present, readable and unexpired. Phase 1/M1/M2/M3 evidence binds the exact SHA, migration head
  `0014_m5_eval_authority` and unchanged OpenAPI digest; the suites report 1/98/52/46 tests with zero failures,
  errors or skips. Gitleaks SARIF contains zero results.
- Docker evidence contains no execution failure; the only case-insensitive `error` match is the Redis module
  configuration field `bf-error-rate`.
- Principal accepts T05 as an evidence-backed stop decision. Its accepted outcome is `FURTHER_RESEARCH`; the global
  P2-MVR-v1 result remains `NOT_EVALUATED`. This is not an MVR PASS and does not authorize a threshold, holdout run,
  T06–T08, production geometry, real-user facial processing, M6 or QuestionBank release.
- The next viable work is a forward research change control for identity-disjoint calibration/holdout cohorts,
  at least four bidirectional candidate dimensions across three non-sensitive region groups, and calibration
  distributions before any threshold freeze. It must not be represented as a Repair Task.

`P2_M5_T05_TRACKED_DISPOSITION: ACCEPTED_FURTHER_RESEARCH`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M5_T06_ENTRY: CLOSED`

## CC-P2-M5-01 Stage A local candidate

- ADR-042 preserves the accepted T05 `FURTHER_RESEARCH` result and defines a forward change-control path rather than
  a Repair or new numbered implementation task.
- `P2_M5_EVIDENCE_EXPANSION_PROTOCOL.md` serializes governance, calibration-only acquisition, complete candidate
  screening, preregistration and sealed holdout. Stage A generates no image and opens only Stage B after exact-SHA CI.
- The first calibration envelope is 12 accepted identities, 18 attempts maximum, one retry per item and concurrency
  1. The future holdout remains separately closed at 24 effective identities and 36 attempts maximum.
- Candidate dimensions and region groups are explicitly non-sensitive research hypotheses. All candidate failures
  must be retained; no threshold, READY promotion, MVR result, production geometry, real-user processing, M6 or
  QuestionBank release is approved.
- Existing rejected MediaPipe wheels remain rejected. Download authorization does not change adoption, license,
  distribution, production or real-user-processing status.

`CC_P2_M5_01_A: READY_FOR_TRACKED_EVIDENCE`

`CC_P2_M5_01_B: CLOSED_PENDING_STAGE_A_TRACKED_ACCEPTANCE`

`P2_M5_T06_ENTRY: CLOSED`

## CC-P2-M5-01 Stage A tracked acceptance

- Candidate `9993e019ad4267dd2521c2988b881bfdf0ec1558` run `32189725291` passed all three jobs.
- Seven artifacts are present, readable and unexpired. Phase 1/M1/M2/M3 evidence binds the exact SHA,
  `0014_m5_eval_authority` and unchanged OpenAPI; the suites report 1/98/52/46 tests with zero failures, errors or
  skips. Gitleaks SARIF contains zero results. Docker evidence has no execution failure.
- Principal accepts ADR-042 and the expansion protocol. This opens only Stage B's 12-identity calibration envelope;
  Stage C–E, holdout access, T06–T08, MVR execution, production geometry, real-user processing, M6 and QuestionBank
  release remain closed.

`CC_P2_M5_01_A: PASS`

`CC_P2_M5_01_B: EXECUTION_READY`

`CC_P2_M5_01_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

## CC-P2-M5-02 failure-mechanism governance candidate

- ADR-047 preserves the accepted Stage C `FURTHER_RESEARCH` result and creates a diagnosis-only forward change
  control. It is not a Repair Task and does not create a new numbered Milestone task.
- The existing runner collapses plan-construction, warp-plan and transform `ValueError` failures into the coarse
  `PLAN_BUILD_FAILED` reason. Current evidence therefore cannot honestly classify those candidates as unsupported or
  choose an algorithm repair.
- `P2_M5_CC02_FAILURE_MECHANISM_PROTOCOL.md` freezes the old manifest/cohort/case/runtime/model/topology authority,
  zero-threshold policy, exhaustive versioned eight-stage terminal taxonomy, 576-transform/604-Vision ceiling, zero
  generation/retry, child-process-inclusive Windows outbound deny, serial execution and evidence-reconstruction stop
  rule.
- The 344 successful platform cases bind three accepted repeat artifacts/rows each (1,032 total). The 14 direction
  mismatches have no accepted legacy result artifact because the old runner rejected them before artifact write; CC02-C
  may only create new diagnostic bytes from frozen authority and must not claim legacy-success drift comparison.
- This local governance candidate does not access private input or implement the harness. Missing private reports,
  digest mismatch, legacy-success drift or unresolved coarse reasons must stop as explicit FAIL/FURTHER_RESEARCH.
- Stage D/E, T06–T08, MVR, production geometry, real-user processing, M6 and QuestionBank release remain closed.
- Local validation and independent architecture review are required before a candidate commit. Same-SHA Actions and
  artifacts remain mandatory before Principal may open CC02-A.

`CC_P2_M5_02_G: LOCAL_GOVERNANCE_CANDIDATE_PENDING_VALIDATION`

`CC_P2_M5_02_A_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

## P2-M5-R03 Playwright acquisition resilience tracked acceptance

- Exact job logs for run `32237678569`, attempt 1, show the combined
  `playwright install --with-deps chromium` step stopped producing progress after Ubuntu repository fetches and was
  cancelled after 3,768 seconds. The log never reached a Chromium binary download line, so the precise classification
  is `TRANSIENT_EXTERNAL_SYSTEM_DEPENDENCY_ACQUISITION_STALL`, not a Browser Integration, lockfile, product or browser
  launch defect. Same-SHA attempt 2 installed successfully in 25 seconds and Browser Integration passed in 18 seconds.
- R03 separates `playwright install-deps chromium` from `playwright install chromium`. System dependencies run once
  with a 600-second hard timeout. Chromium binary acquisition uses the official Playwright endpoints, at most three
  600-second attempts and 30/60-second backoff, and fails the job after the third unsuccessful attempt. Every attempt
  records exact Playwright version, UTC start/end, elapsed seconds and exit status in a redacted text artifact.
- Candidate `d3f0597019bc0b4de37a058159a74a26ea1fc046` run `32245119767` passed
  `quality-and-integration`, `secret-scan` and `docker-validation`. The system-dependency step passed in 20 seconds,
  Chromium downloaded on attempt 1/3 in 17 seconds, the evidence artifact uploaded successfully and Browser
  Integration passed in 20 seconds.
- Eight artifacts are readable, unexpired and include `playwright-install-evidence`. Frozen Phase 1/M1/M2/M3
  evidence binds the exact SHA, `0014_m5_eval_authority` and unchanged OpenAPI digest; Gitleaks has zero results and
  Docker evidence has no traceback, deadlock or fatal match.
- R03 changes only CI acquisition resilience. It does not skip Browser Integration, add a browser cache, change a
  dependency/lockfile, alter Stage C research evidence or open Stage D/E, T06–T08, MVR, production geometry,
  real-user processing, M6 or QuestionBank release.

`P2_M5_R03: REPAIR_ACCEPTED`

`PLAYWRIGHT_ACQUISITION_POLICY: BOUNDED_FAIL_CLOSED`

## Stage A acceptance checkpoint failure and P2-M5-R02 local repair

- Acceptance checkpoint `d3158c03e0843e5a504531dd407eafea534630de` run `32190386366` passed
  `secret-scan` and `docker-validation`, but `quality-and-integration` failed with 566 passed, one existing optional
  skip and one PostgreSQL deadlock in the Phase 1 data-rights HTTP vertical test's final
  `TRUNCATE TABLE users CASCADE`.
- The failing test combined live Celery dispatch with direct synchronous processing of the same data-export,
  asset-deletion and account-deletion workflow. A dedicated PostgreSQL/Redis/Celery replay confirmed that suppressing
  only data-rights dispatch was insufficient: asset deletion could still race teardown and deadlocked on iteration 2.
- `P2-M5-R02` composes this synchronous vertical test with the existing recoverable data-rights and asset-deletion
  dispatchers. No production service, lock order, schema, trigger, API, authorization or deletion behavior changes.
- The repaired isolated replay passed 20/20 while the live maintenance worker received zero tasks. Full local Python,
  migration, TypeScript/contracts, Docker and Gitleaks Gates also passed; exact-SHA remote Actions and artifacts remain
  required before accepting R02 or reopening Stage B.

`P2_M5_R02: READY_FOR_TRACKED_EVIDENCE`

`CC_P2_M5_01_B: CLOSED_PENDING_REPAIRED_ACCEPTANCE_CHECKPOINT`

## P2-M5-R02 tracked acceptance and Stage B recovery

- Repair candidate `9946a43d771c2cb27d764243bda047e943ad5c99` run `32192316257` passed
  `quality-and-integration`, `secret-scan` and `docker-validation` on the exact candidate SHA.
- Seven artifacts are present, readable and unexpired. Phase 1/M1/M2/M3 evidence binds the exact SHA,
  `0014_m5_eval_authority` and unchanged OpenAPI; the suites report 1/98/52/46 tests with zero failures, errors or
  skips. Gitleaks SARIF contains zero results.
- The full Python suite reports `567 passed, 1 skipped`; the skip is the existing optional private-runtime Gate.
  Celery evidence has no execution error, traceback or deadlock. The Docker log's only case-insensitive `error` match
  is Redis field `bf-error-rate`.
- Principal accepts R02. Its scope remains the synchronous test composition only; production dispatch, data-rights
  semantics, schema, public contracts and P2 research authority are unchanged.
- Stage B returns to `EXECUTION_READY` under the accepted 12 identities, 18 total attempts, one retry per
  item and concurrency-1 envelope. Stage C–E, final holdout, T06–T08, MVR execution, production geometry, real-user
  processing, M6 and QuestionBank release remain closed.

`P2_M5_R02: REPAIR_ACCEPTED`

`CC_P2_M5_01_B: EXECUTION_READY`

`P2_M5_NEXT_ACTION: CC_P2_M5_01_B_CALIBRATION_ONLY_ACQUISITION`

## CC-P2-M5-01 Stage B local candidate

- The frozen 12-identity calibration wave used 12 of 18 allowed attempts, no retries and concurrency one. All source
  outputs remain private and use `CODEX_NATIVE_IMAGEGEN` with `PROVENANCE_ONLY`; unavailable provider/model/request/
  seed/usage/cost facts remain null.
- All 12 sources passed bounded PNG admission and deterministic canonical JPEG normalization. Exact normalized SHA-256
  duplicate count is zero. The first-party `phash-dct-nearest-v1` produced 66 pair candidates with an observed minimum
  Hamming distance of 12; no near-duplicate threshold was selected and no automatic near-duplicate rejection occurred.
- The accepted source-built private Vision runtime and exact model bundle SHA-256
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` reported exactly one face and 478 landmarks
  for every normalized asset. Human categorical review found no clear pre-16 presentation, child/student-minor context,
  real-person likeness concern or nonsexual-context violation. It used no age estimator, attractiveness score or rank.
- Real PostgreSQL contains 12 offline admissions, 12 source objects, 12 passed canonical QA runs and 12 bank-independent
  identities. A second complete registration replay remained at exactly 12 identities, proving operator-path
  idempotency. `cal-b-06` is retained with `REQUESTED_CELL_VISUAL_MATCH_WEAK`; this is honest calibration evidence and
  not a hard-gate failure or fabricated coverage claim.
- Redacted evidence is `docs/research/P2_M5_CC01B_CALIBRATION_EVIDENCE.json`; image bytes, Prompt text, private paths,
  storage references, landmark arrays and raw Vision logs remain outside Git.
- This is local evidence only. Stage B needs candidate same-SHA Actions and artifact inspection before Principal
  acceptance can open Stage C. Stage C–E, T06–T08, MVR execution, production geometry, real-user processing, M6 and
  QuestionBank release remain closed.

`CC_P2_M5_01_B: LOCAL_PASS_PENDING_TRACKED_EVIDENCE`

`CC_P2_M5_01_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`
