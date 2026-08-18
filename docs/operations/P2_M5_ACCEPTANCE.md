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
| Domain              | policy/isolation/cohort/result types deterministic and fail closed | PENDING  |
| Ontology            | new immutable version binds non-sensitive region groups            | PENDING  |
| Database            | forward `0014`, lifecycle, invariants, concurrency, zero drift     | PENDING  |
| Isolation           | actual target error and every non-target delta retained            | PENDING  |
| Similarity          | exact SHA and first-party pHash/Hamming golden evidence            | PENDING  |
| Threshold           | calibration distribution and pre-holdout version freeze            | PENDING  |
| Split               | calibration/M4-seen/holdout/cluster leakage rejected               | PENDING  |
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
