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

## CC-P2-M5-02-A implementation and P2-M5-R04 tracked acceptance

- CC02-A implementation commit `5159c3f28ab8dcbb7db07c5bead3780a409ace25`
  added only the versioned diagnostic harness and its targeted tests. Its first
  run `32278984711` passed Docker and secret scan, but quality job `96152991638`
  was cancelled after the one-time Playwright system-dependency acquisition
  stopped making progress. Chromium download and Browser Integration never
  started, so this was not valid implementation acceptance evidence.
- The failed-run install artifact contained a system-dependency start record
  but no end record and stopped during Ubuntu `noble-updates` acquisition. The
  incident is classified as
  `TRANSIENT_EXTERNAL_SYSTEM_DEPENDENCY_ACQUISITION_STALL + CI_TIMEOUT_WRAPPER_DEFECT`,
  not a Chromium, browser-launch, assertion, lockfile, checksum or product
  defect.
- R04 commit `ee19ad6efe49decfa3a0c8f0dbf3f130b5c59460` moved each complete
  `pnpm | tee` pipeline into the GNU `timeout` child shell and added independent
  12/35-minute step watchdogs. It preserved the one-time system-dependency
  command, three 600-second Chromium attempts, 30/60-second backoff, official
  source, fail-closed terminal result and unchanged Browser Integration Gate.
- Exact-SHA run `32282614608` attempt 1 passed quality `96164640367`, Docker
  `96164640344` and secret scan `96164640053`. System dependencies completed in
  12 seconds, Chromium downloaded on attempt 1/3 in 12 seconds, the install
  evidence uploaded, and Browser Integration passed 5/5 in 13.1 seconds.
- Full Python was 642 PASS with one existing optional private-runtime skip.
  Phase 1/M1/M2/M3 evidence remained `1/98/52/46` with zero failure, error or
  skip, migration head `0014_m5_eval_authority` and unchanged OpenAPI digest
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`.
  Gitleaks reported zero results, dependency audits reported no known
  vulnerabilities, and the CycloneDX SBOM contained 105 components with zero
  non-null vulnerability entries.
- Eight readable, unexpired artifacts were inspected:

  | Artifact                      |           ID | API digest                                                         |
  | ----------------------------- | -----------: | ------------------------------------------------------------------ |
  | `gitleaks-results.sarif`      | `9376388807` | `f3c6b167b3d5ce7b43af3da239f6475238b07bd9c7d9faf2d1cf68a08c696488` |
  | `p2-m1-ci-evidence`           | `9376528295` | `a7c1b38c7cdb82e87e71f618a54ba2d322b42760bed0f0a1589eae0347dbb89c` |
  | `p2-m2-ci-evidence`           | `9376529060` | `082a4f070e3bc0798fd0b50dd60f72088242982f80cbc5c6be1872ac958b8257` |
  | `p2-m3-ci-evidence`           | `9376529768` | `0cb51e2817843408f0e8195c1d724a2771f5814bbecec0d3673939add5578ea4` |
  | `phase1-ci-evidence`          | `9376527560` | `fafde59e69cdc9795a752ce34b10c9f03d46dbbc8ecb26df35fabc8e82160ada` |
  | `playwright-install-evidence` | `9376516571` | `83fcede6c3c7ae45bf3aa7825fefaf1e14a5a99edd4df4f634e9e56afdfefd31` |
  | `project-audit-evidence`      | `9376537708` | `277f824bca887c1f9bcf72029d66ca99979aad5dac6054b79336d5b63156d6c2` |
  | `project-docker-evidence`     | `9376465587` | `9edd9507085c3793466d8c7b27f575027c38616f69e6e8b66f7b36039179071d` |

- The extracted Playwright install log has SHA-256
  `dc50b9aea95858178d994e13d76cb1b4e636c19dfee5652feb555432c5c2125d`.
  Targeted CC02-A validation passed 58 tests; its frozen authority, resource,
  taxonomy, redaction and negative-contract matrix passed independent review.
  Independent R04 security and Sol final reviews also found no mandatory issue.
- The Principal accepts the CC02-A implementation and R04 repair only. This
  opens preparation of a separate CC02-B bounded-task contract. Private input
  remains prohibited until that contract receives tracked acceptance; CC02-C–E,
  Stage D/E, T06–T08, MVR, production geometry, real-user processing, M6 and
  QuestionBank release remain closed.

`CC_P2_M5_02_A_IMPLEMENTATION: PASS_AT_EE19AD6_RUN_32282614608_ATTEMPT_1`

`CC_P2_M5_02_A_CLOSURE: PASS_AT_470849F_RUN_32284285946`

`P2_M5_R04: REPAIR_ACCEPTED_AT_EE19AD6_RUN_32282614608_ATTEMPT_1`

`CC_P2_M5_02_B: READY_FOR_BOUNDED_TASK_CONTRACT`

`CC_P2_M5_02_PRIVATE_INPUT: PROHIBITED_PENDING_CC02_B_TRACKED_ACCEPTANCE`

`CC_P2_M5_02_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

## CC-P2-M5-02-B bounded-task contract candidate

- CC02-A acceptance closure `470849f0f42f151d1ec939e3b0d81ef4369ea86c` passed run `32284285946` with all three
  jobs, Browser Integration 5/5 and eight exact-SHA artifacts. This confirms the already accepted CC02-A implementation
  and R04 repair; it does not add diagnostic evidence or open private input.
- `P2_M5_CC02_B_TASK_CONTRACT.md` first freezes a versioned first-party deterministic builder and targeted synthetic
  tests, then a future create-once machine manifest at `P2_M5_CC02_DIAGNOSTIC_MANIFEST.json` and matching human
  preregistration. The manifest schema verifies two previously accepted canonical report digests, first-binds each
  validated presented byte stream with an explicit non-retroactive basis, and binds 288 logical/576 platform cases, 232
  failures, 344 successes with 1,032 accepted repeat-row bindings, plus the 14-case/42-measurement direction subset.
- The contract also freezes candidate/cohort/case/runtime/model/topology/algorithm/harness/taxonomy authority, canonical
  digest semantics, resource ceilings, complete key sets, private-field redaction and evidence-reconstruction stop
  rules. It contains no real report location, case digest, manifest, threshold, replay or mechanism result.
- This is `READY_FOR_TRACKED_CONTRACT_EVIDENCE` only. Private input remains prohibited until same-SHA contract evidence,
  independent review and Principal acceptance. Contract acceptance opens only builder/test implementation with
  synthetic inputs. Exact report locations/bytes remain prohibited until tracked builder acceptance and explicit
  Principal `CC02_B_BUILDER_PRE_READ_GATE: PASS`; CC02-C replay still requires its own later tracked contract and Windows
  child-process-inclusive outbound-deny Gate.
- CC02-C–E, Stage D/E, T06–T08, MVR, production geometry, real-user processing, M6 and QuestionBank release remain
  closed. P2-M5 remains `EXECUTING`, and old Stage C remains accepted `FURTHER_RESEARCH` with 0/4 eligibility.

`CC_P2_M5_02_B_CONTRACT: READY_FOR_TRACKED_CONTRACT_EVIDENCE`

`CC_P2_M5_02_B_BUILDER: NOT_IMPLEMENTED`

`CC02_B_BUILDER_PRE_READ_GATE: CLOSED_PENDING_TRACKED_BUILDER_ACCEPTANCE`

`CC_P2_M5_02_B_MANIFEST: NOT_CREATED`

`CC_P2_M5_02_PRIVATE_INPUT: PROHIBITED_PENDING_CC02_B_TRACKED_CONTRACT_ACCEPTANCE`

`CC_P2_M5_02_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

## CC-P2-M5-02-B bounded-task contract tracked acceptance

- Candidate `f69361e8d855fa6262b2d79560c456c8862df2f7` preserves the accepted contract content SHA-256
  `e82e0b83bd5ded0932dd547d2f46f0d229cf63c430637fedc736548ad9ccdc35`. Independent security/research-integrity and
  final reviews of that exact contract found no mandatory issue.
- Exact-SHA run `32287419743`, attempt 1, passed quality `96180144101`, Docker `96180143930` and secret scan
  `96180144180`. Full Python was 642 PASS with one existing optional private-runtime skip. Phase 1/M1/M2/M3 evidence
  remained `1/98/52/46` with zero failure, error or skip, migration head `0014_m5_eval_authority` and unchanged OpenAPI
  digest `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`.
- Playwright 1.62.1 system dependencies completed within the frozen 600-second bound in 452 seconds. Chromium downloaded
  from the official `cdn.playwright.dev` source on attempt 1/3 in 13 seconds, and Browser Integration passed 5/5 in 13.8
  seconds. The extracted install log SHA-256 is
  `530a09486a3a0e4959942ab8e1154b47f4e960dc236c86125ec5aa4a2b6a8320`.
- Dependency audits reported no known vulnerabilities, Gitleaks contained zero results, and the CycloneDX 1.6 SBOM
  contained 105 components with zero non-null vulnerability entries. Eight readable, unexpired, exact-SHA artifacts were
  inspected:

  | Artifact                      |           ID | API digest                                                         |
  | ----------------------------- | -----------: | ------------------------------------------------------------------ |
  | `gitleaks-results.sarif`      | `9378158014` | `a6c170aeb855f71518346b6a767176169273a73644c6f092f38e7bc39a12c1c4` |
  | `p2-m1-ci-evidence`           | `9378557805` | `79f01d12f825bb340d1e94f03258bc1edade26d651caec705e9f84f51c417e64` |
  | `p2-m2-ci-evidence`           | `9378558723` | `50beb49835809f9a748147290776ef8d672202c0b5aadb1a286e5fe3badce3f6` |
  | `p2-m3-ci-evidence`           | `9378559652` | `dfaeea0fe25d5079e4986617e2cf1fd5c8958857973e497174a31b2f11f8c760` |
  | `phase1-ci-evidence`          | `9378556884` | `c04a7f98fa0028d5d98ca406dcfcff409e7070d66d589093b1585758a9e9d4a3` |
  | `playwright-install-evidence` | `9378545103` | `ffb9a78c78a9b699dadeed0c97a26d1b0d1eec0e620a96bde36423331eb5dc7f` |
  | `project-audit-evidence`      | `9378567881` | `18796d0681649d7d4a2d9401e796f276dd2bf157d2b8052018653c012477f528` |
  | `project-docker-evidence`     | `9378208554` | `f9327b2c4db3e915e87e6c790eb06663cd937b32601194f86f4e85ee3765e6ca` |

- Principal accepts only the tracked CC02-B contract and sets the frozen first-party builder plus synthetic tests to
  `EXECUTION_READY`. No builder exists yet. Private report locations/bytes, real manifest creation, CC02-C–E, Stage D/E,
  T06–T08, MVR, production geometry, real-user processing, M6 and QuestionBank release remain closed. The accepted Stage
  C result remains `FURTHER_RESEARCH` with 0/4 eligibility.

`CC_P2_M5_02_B_CONTRACT: PASS_AT_F69361E_RUN_32287419743_ATTEMPT_1`

`CC_P2_M5_02_B_BUILDER: EXECUTION_READY`

`CC02_B_BUILDER_PRE_READ_GATE: CLOSED_PENDING_TRACKED_BUILDER_ACCEPTANCE`

`CC_P2_M5_02_B_MANIFEST: NOT_CREATED`

`CC_P2_M5_02_PRIVATE_INPUT: PROHIBITED_PENDING_CC02_B_BUILDER_PRE_READ_GATE`

`CC_P2_M5_02_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

## P2-M5-R05 CC02-B builder contract-fidelity repair candidate

- Principal review of the untracked synthetic-only builder found four implementation acceptance defects: incomplete
  preregistration resource summary, caller-injectable production authority/root, missing canonical-byte/direction-order
  validation, and missing `fsync`/close cleanup coverage.
- The review also found one wording conflict in the accepted contract. Exact presented report-byte SHA authority means
  semantically equivalent JSON with different key ordering must produce a different report binding and final digest;
  only the safe semantic projection remains invariant. `P2_M5_R05_REPAIR.md` records this forward correction without
  changing schema, accepted evidence, thresholds, algorithms or later Gates.
- The repaired local candidate has only synthetic/numeric tests. It has not read private input or created either future
  tracked output. R05 and the builder remain pending full diff review, local/full validation, same-SHA Actions, artifacts
  and independent security/final review.
- The first independent security/final review rejected the candidate for malformed-sort raw exceptions, missing output
  parent containment and close/unlink cleanup behavior. The forward repair now uses validated parent identities and
  hidden non-authoritative staging. Because two fixed paths are not a portable filesystem transaction, persistent cleanup
  failure is an explicit recovery-required stop and can never be accepted as output; fresh reviews remain mandatory.
- Security rereview then supplied two narrower counterexamples, so the earlier local final-review PASS was not accepted.
  R2 replaces path-only publication with held POSIX `dir_fd` / Windows no-delete-share directory anchors and writes a
  hidden incomplete-publication marker before the first fixed link. A persistent rollback residue is therefore
  explicitly non-authoritative, blocks create-once and requires exact-path recovery; it cannot advance any Gate.
- R3–R5 close the remaining platform and recovery counterexamples. Windows child file reparse is rejected by pre/open/post
  identity, regular-file and reparse checks even when target bytes match. The incomplete marker is bound by exact bytes and
  file identity throughout precommit publication. All final links, directory syncs, staging cleanup, held-anchor and exact
  final checks precede successful marker unlink, which is the logical commit; a later directory-sync error is best-effort
  and cannot start destructive rollback or turn committed exact outputs into a false failure.
- Native Windows and standard Linux `--network none` targeted suites each pass 46 tests. The complete local Python
  regression is 527 passed / 162 skipped; Ruff format/check, strict mypy, `pnpm.cmd check` and scoped
  `git diff --check` pass. The builder entry point was not run, private inputs were not read and neither future tracked
  output was created.
- Final R5 review reproduced an active same-credential final replacement in the last validation-to-marker-unlink window.
  ADR-048 / `CC-P2-M5-03` accepts the portability proof and freezes trusted exclusive `docs/research` custody as an
  invocation prerequisite. The builder is not a hostile-local-writer security boundary; Git hash/same-SHA CI remains a
  later snapshot authority, not a retroactive fix. The cooperative duplicate-invocation regressions now require exactly
  one exact winner and one fail-closed loser without marker/staging residue. Fresh independent security/privacy and Sol
  final reviews both pass under ADR-048. Principal accepts only the local implementation evidence; same-SHA Actions and
  eight readable artifacts remain mandatory before tracked acceptance.
- Candidate `298420fcc362851b96c1005e25608f37b2016373` passed exact-SHA run `32299835326`, attempt 1: quality
  `96219610867`, Docker `96219611030` and secret scan `96219610747` all succeeded. Full Python was 688 PASS with one
  existing optional private-runtime skip. Phase 1/M1/M2/M3 evidence remained `1/98/52/46` with zero failure, error or
  skip, migration head `0014_m5_eval_authority` and unchanged OpenAPI digest
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`.
- Playwright 1.62.1 system dependencies completed in 212 seconds, Chromium downloaded from official
  `cdn.playwright.dev` on attempt 1/3 in 12 seconds, and Browser Integration passed 5/5 in 13.0 seconds. The extracted
  install log SHA-256 is `1e06d3162ae4e9579a13d67ccd82db8b01e382a2d6960dcfef329080b4115416`.
- Dependency audits reported no known vulnerabilities, Gitleaks contained zero results, and the CycloneDX 1.6 SBOM
  contained 105 components with no vulnerability section. Eight readable, unexpired, exact-SHA artifacts were inspected:

  | Artifact                      |           ID | API digest                                                         |
  | ----------------------------- | -----------: | ------------------------------------------------------------------ |
  | `gitleaks-results.sarif`      | `9382574745` | `afc534d251efefbc4b77b159013b56cfc6a704e276e65312a2c7a99ec93d85a0` |
  | `p2-m1-ci-evidence`           | `9382817418` | `bcf18d82bfb43d25876420ab25d2ec180b9d02ca5b0ca7202e48c0bc1cefeda2` |
  | `p2-m2-ci-evidence`           | `9382818138` | `86c60f0bc14dbef8dc2f8dd7928f1f2ada11c189ade6b77fc282960861c31f64` |
  | `p2-m3-ci-evidence`           | `9382818792` | `5bb04f05cabf90b43f124218e578d44bcf7e1e9fd5d4d7281aa63b85c37f7e98` |
  | `phase1-ci-evidence`          | `9382816679` | `373318e106e1111ea67a9bf2ecf5f959ad037f606599025f1e63d1f0aff4ed67` |
  | `playwright-install-evidence` | `9382806652` | `2eff44ea98168b22f55dfca1646e29dd92a6f9424929bff863a9ea0b3a70723a` |
  | `project-audit-evidence`      | `9382826039` | `90916cd5f8b308d7bd3cc9cc7e3b774fb2f4cf40842a1f0dc1a31312b726af5e` |
  | `project-docker-evidence`     | `9382624832` | `5c7e82fc9cc0857ddba0512409988da4189e0d87d9e016afdce33b654838e6db` |

- Principal accepts R05 and the tracked CC02-B builder. The explicit pre-read Gate now permits only the two frozen private
  report byte streams to be released to this exact accepted builder during an ADR-048 exclusive-custody window. No private
  environment variable is present, the builder entry point has not run and neither real output exists. This does not open
  CC02-C–E, Stage D/E, T06–T08, MVR, production geometry, real-user processing, M6 or QuestionBank release.

`CC_P2_M5_03_LOCAL_PUBLICATION_TRUST_BOUNDARY: ACCEPTED_AT_298420F_RUN_32299835326_ATTEMPT_1`

`LOCAL_PUBLICATION_CUSTODY_GATE: REQUIRED_FOR_REAL_BUILDER_INVOCATION`

`P2_M5_R05: REPAIR_ACCEPTED_AT_298420F_RUN_32299835326_ATTEMPT_1`

`CC_P2_M5_02_B_BUILDER: PASS_AT_298420F_RUN_32299835326_ATTEMPT_1`

`CC02_B_BUILDER_PRE_READ_GATE: PASS_AT_298420F_RUN_32299835326_ATTEMPT_1`

`CC_P2_M5_02_PRIVATE_INPUT: NOT_RELEASED_ENVIRONMENT_ABSENT`

`P2_M5_NEXT_ACTION: VERIFY_CC02_B_ACCEPTANCE_CHECKPOINT_BEFORE_PRIVATE_CUSTODY`

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
- Candidate `137157c41e7b1436ae47fe7dfcf34a7127789166` and run `32267510703` attempt 1 completed all three real-runner
  jobs: quality `96115516046`, Docker `96115516188` and secret scan `96115516219`. Eight artifacts were downloaded,
  readable, unexpired and exact-SHA bound; migration head remained `0014_m5_eval_authority`, OpenAPI digest remained
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`, Phase 1/M1/M2/M3 evidence was
  `1/98/52/46` with zero failure/error/skip, and Gitleaks had zero results.
- Full Python was 582 PASS with one existing optional private-runtime skip. Playwright 1.62.1 system dependencies
  completed in 11 seconds, Chromium download succeeded on attempt 1/3 in 12 seconds, and Browser Integration passed
  5/5. The only skipped upload was the expected `if: failure()` browser-failure artifact path.
- Independent security/privacy/research-integrity and Sol final reviews found no mandatory issue. Principal therefore
  accepts CC02-G as tracked diagnosis-only governance. This opens only preparation of a separate CC02-A bounded-task
  contract; CC02-A is not implemented or executed and has no private-input permission.

`CC_P2_M5_02_G: PASS_AT_137157C_RUN_32267510703_ATTEMPT_1`

`CC_P2_M5_02_A: READY_FOR_BOUNDED_TASK_CONTRACT`

`CC_P2_M5_02_B_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

## CC-P2-M5-02-A bounded-task contract tracked acceptance

- `P2_M5_CC02_A_TASK_CONTRACT.md` freezes the implementation to one new versioned diagnostic harness, one targeted
  test surface and an optional non-image taxonomy fixture.
- The contract requires exact eight-stage reason mapping, raw-exception redaction, create-once output, 576-transform/
  604-Vision ceilings, the full identity/case/time/storage/download envelope, an exact fail-closed private-report JSON
  contract with separate terminal, legacy-repeat and direction-measurement collections, zero generation/retry,
  concurrency 1 and deterministic golden negative cases.
- The old runner/evidence, private input, algorithm/formula, schema/API, dependency/model and all later Gates remain
  forbidden. Candidate `d8659ae88fb32c99220d522fc6dbf94a8fc588ac` changed only the four contract-governance
  documents and passed run `32271571196` attempt 1 on quality `96129032763`, Docker `96129032868` and secret scan
  `96129032519`.
- Quality completed in 334 seconds, Docker in 112 seconds and secret scan in 10 seconds. PostgreSQL completed its full
  lifecycle at `0014_m5_eval_authority`; Python was 582 PASS with one existing optional skip; Phase 1/M1/M2/M3 were
  `1/98/52/46` with zero mandatory skip; OpenAPI remained
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`.
- Playwright 1.62.1 system dependencies completed in 78 seconds, Chromium downloaded from the official source on
  attempt 1/3 in 12 seconds, and Browser Integration passed 5/5 in 14 seconds. The sole skipped step was the expected
  `if: failure()` artifact path. Dependency audits found no known vulnerabilities, the CycloneDX 1.6 SBOM contained
  105 components and no non-null vulnerability entry, and Gitleaks had zero results.
- Eight readable, unexpired, exact-SHA artifacts were inspected. Their GitHub artifact IDs and API SHA-256 digests are:

  | Artifact                      |           ID | API digest                                                         |
  | ----------------------------- | -----------: | ------------------------------------------------------------------ |
  | `gitleaks-results.sarif`      | `9372352559` | `42c2a69c7ac6706e7543f02b53ee2ca153320d4e44586760ee824ecec966a5ee` |
  | `p2-m1-ci-evidence`           | `9372533932` | `ea79c6e3b4b78dafc95cb4f6921b1cd4dc1c1b776e7d51e220239e0382871fa5` |
  | `p2-m2-ci-evidence`           | `9372534857` | `3168022cf066009dfcea7f7b4bc562ef24b4a955ab1e7ef54df0e5b65339f307` |
  | `p2-m3-ci-evidence`           | `9372535745` | `9d40b01cf15aee05df5979cade7716c1e26154c6ae50c219d11c02c8de75d25b` |
  | `phase1-ci-evidence`          | `9372533072` | `4f938b7e94337c0d35fd8e6b477d9487ce703821fc9a0f96c71dc338c783bd95` |
  | `playwright-install-evidence` | `9372521282` | `79ef275256c34f2847cf5d36232e7a96d6636f0e2dcfe2b6239a9dbb25f4a718` |
  | `project-audit-evidence`      | `9372544946` | `a7e0a0d460419c98000905dcbfd6061b082f22fd32e216d63e219a35d0fd213f` |
  | `project-docker-evidence`     | `9372407461` | `4aca74d37aa944b36b3982cf3c44d1af421268b7523ff0d6c57d22fee5432915` |

- Independent security/privacy/supply-chain and Sol final reviews found no mandatory issue. Principal accepts only the
  tracked bounded-task contract and sets one implementation worker to `EXECUTION_READY`; this is not implementation,
  execution, private replay, mechanism evidence or a P2-M5 Gate decision.

`CC_P2_M5_02_A_CONTRACT: PASS_AT_D8659AE_RUN_32271571196_ATTEMPT_1`

`CC_P2_M5_02_A_IMPLEMENTATION: PASS_AT_EE19AD6_RUN_32282614608_ATTEMPT_1`

`CC_P2_M5_02_B: READY_FOR_BOUNDED_TASK_CONTRACT`

`CC_P2_M5_02_PRIVATE_INPUT: PROHIBITED_PENDING_CC02_B_TRACKED_ACCEPTANCE`

`CC_P2_M5_02_C_TO_E: CLOSED`

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

## P2-M5-R06 Playwright system-dependency retry tracked acceptance

- Acceptance checkpoint `aa32c8b912aa0a5196f2615a1ed4b651ef17166d` run `32300981951` failed twice at the
  same stage and SHA. Each quality attempt reached the existing 600-second timeout while the official Playwright
  `install-deps chromium` command was still acquiring Ubuntu `noble-updates` indexes; Chromium download and Browser
  Integration never started. The incident is therefore
  `REPEATED_EXTERNAL_APT_REPOSITORY_ACQUISITION_STALL`, not a browser-download, launch, lockfile, checksum, assertion or
  product defect.
- R06 candidate `09c77be149e05c074dcc4e038882be0fdad5b3a9` preserves the official command and adds three bounded
  600-second attempts with 30/60-second backoff. Per-attempt timeout plus kill/backoff is 1,980 seconds, below the
  independent 2,100-second Actions watchdog. Three failures still fail closed; Chromium acquisition remains separate,
  its official source override protection is unchanged, and Browser Integration is never skipped.
- Exact-SHA run `32304931584`, attempt 1, passed quality `96235526799`, Docker `96235526513` and secret scan
  `96235526810`. The system-dependency artifact recorded attempt 1/3 success in 420 seconds; Chromium attempt 1/3
  succeeded in 11 seconds; Browser Integration then passed 5/5 in 14.2 seconds.
- Full Python was 689 passed with one existing optional private-runtime skip. Phase 1/M1/M2/M3 evidence remained
  `1/98/52/46` with zero failure, error or skip and bound the exact SHA, migration head `0014_m5_eval_authority` and
  unchanged OpenAPI digest. All eight artifacts were readable and unexpired; their IDs/digests and the extracted
  Playwright log SHA-256 are recorded in `P2_M5_R06_REPAIR.md`. Gitleaks reported zero results, both dependency audits
  found no known vulnerability, the CycloneDX 1.6 SBOM contained 105 components and Docker/Celery evidence was healthy.
- Principal accepts only R06. P2-M5 remains `EXECUTING`; Stage/research results, private-input authority, CC02-C–E,
  T06–T08, MVR, production geometry, real-user processing, M6 and QuestionBank release are unchanged and remain governed
  by their existing Gates.

`P2_M5_R06: REPAIR_ACCEPTED_AT_09C77BE_RUN_32304931584_ATTEMPT_1`

`P2_M5_STATE: EXECUTING`
