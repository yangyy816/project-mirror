# P2-M1 Acceptance Evidence

## Candidate status

- Milestone: `P2-M1 — Domain, Provenance, Governance and Research Baseline`
- State: `PASS`；等待 acceptance closure CI 后 `FROZEN`
- Local validation target: current working tree based on `f2fec9ece18c54f3952cc877ad18d2b70ec54e32`
- Candidate commit SHA: `a901337ca8e0ef1fc93e64638ef72abb56bc1d28`
- Same-SHA GitHub Actions evidence: run `31930761620` — all three jobs passed

## Machine-readable evidence contract

The `mirror.p2-m1.ci-evidence/v1` artifact contains only:

- the full candidate commit SHA;
- the single Alembic head `0008_synth_dataset_foundation`;
- the SHA-256 digest of the authoritative OpenAPI document;
- aggregate P2-M1 JUnit counts, duration and zero-failure/error/skip status;
- aggregate PASS status for synthetic-only, dependency/model-artifact, Provider/network/SDK,
  production fail-closed and public-contract boundary checks.

The artifact excludes raw JUnit XML, repository paths, database rows, prompts, object keys,
URLs, images, Provider payloads, environment values and credentials.

## Local gate record

T07 local validation ran against the current worktree based on the recorded Phase 1 freeze
commit. The machine-readable sample intentionally binds that base commit because the Principal
has not yet created the candidate commit; it is generator evidence, not same-SHA acceptance
evidence. Remote candidate and acceptance closure results must be recorded by the Principal only
after the committed candidate SHA completes all three `project-gates` jobs.

| Gate                       | Result | Evidence                                                                                                 |
| -------------------------- | ------ | -------------------------------------------------------------------------------------------------------- |
| Python format/lint/type    | PASS   | Ruff 142 files; strict mypy 90 source files                                                              |
| Python API/Worker tests    | PASS   | API 275; Worker 19; P2-M1 evidence 87; zero mandatory skip                                               |
| Migration lifecycle        | PASS   | isolated PostgreSQL fresh→`0007→0008→0007→0008`; `alembic check`                                         |
| TypeScript/contracts/build | PASS   | complete `pnpm check`; OpenAPI digest `8809c9c63c609cc270c211d3f8cca03f47d76243fa5aeb6304bb385653adfdb2` |
| Docker                     | PASS   | Compose config/build; five healthy services; three HTTP 200 responses; Celery ping                       |
| Supply chain               | PASS   | Python/Node audits; Python/Node licenses; Python SBOM; no dependency/model additions                     |
| Secret scan                | PASS   | Gitleaks 8.28.0 candidate snapshot and 63-commit full history; no leaks                                  |
| GitHub Actions             | PASS   | run `31930761620`; all three jobs passed on `a901337ca8e0ef1fc93e64638ef72abb56bc1d28`                   |

Candidate `6d9d97f3aa7f0aba5b7a3ea3f7eaf1c2a15a5440` run `31929764395` passed
secret-scan, Docker, and every quality step through contract drift, but the retained Phase 1
evidence step still expected frozen-era head `0007_account_quarantine_evidence`. `P2-M1-R05`
updates only that current-head expectation to `0008_synth_dataset_foundation`; the Phase 1
vertical JUnit, OpenAPI digest, full SHA and zero-skip requirements remain unchanged.

Repair candidate `f2fec9ece18c54f3952cc877ad18d2b70ec54e32` run `31930089028` passed
secret-scan and Docker. Its quality job reached the complete Python suite and exposed a retained
Phase 1 Asset-deletion concurrency deadlock: duplicate evidence insertion acquired the target
Asset trigger lock before `_complete()` acquired the deletion request lock, while the completion
transaction held the request lock before updating Assets. The failure was unrelated to R05 but is
a mandatory regression and is closed by `P2-M1-R06`; a new same-SHA run remains required.

The isolated migration and evidence databases were checked for zero active sessions and removed
after validation. Existing ACL-protected `.tmp` paths were not accessed or changed.

## Repair evidence

`P2-M1-R04` corrected one Worker test fixture that created production `Settings` without the new
synthetic storage field. With CI correctly setting `SYNTHETIC_STORAGE_PROVIDER=mock`, the fixture
inherited mock and failed at the production configuration gate before exercising its intended
LocalTaskRunner production rejection. The repair explicitly sets
`synthetic_storage_provider="disabled"` only in that production fixture. The targeted test and the
complete 19-test Worker suite pass with the CI mock environment; production code and fail-closed
semantics are unchanged.

`P2-M1-R05` updates the retained Phase 1 evidence invocation to validate the repository's current
single Alembic head `0008_synth_dataset_foundation`. It does not change the evidence schema or
remove the Phase 1 vertical test, OpenAPI digest, commit SHA, or zero-skip checks.

`P2-M1-R06` establishes one lock order for Asset-deletion evidence: lock the matching
owner-bound `AssetDeletionRequest` with `FOR UPDATE`, then insert append-only deletion evidence,
after which the existing PostgreSQL trigger validates and locks the target Asset. Missing or
owner-mismatched requests fail closed before evidence insertion. The repair changes no migration,
trigger, state machine or deletion semantics. The implementation agent recorded 20/20 concurrent
PostgreSQL passes, 6/6 Asset-deletion passes and a fresh PostgreSQL/Redis full API run with zero
skips. Principal review independently passed the complete six-test Asset-deletion file on a fresh
Compose PostgreSQL database, Ruff format/lint, strict mypy and `git diff --check`.

`P2-M1-R06_TASK_ACCEPTED: PASS`

## Candidate remote evidence

Run `31930761620` completed on candidate
`a901337ca8e0ef1fc93e64638ef72abb56bc1d28` with `quality-and-integration`,
`secret-scan` and `docker-validation` all passing. The quality job executed Python quality,
the PostgreSQL migration lifecycle, the complete Python suite, retained Phase 1 vertical and
recovery coverage, P2-M1 deterministic boundary tests, TypeScript/build, browser integration,
contract drift, both evidence generators, dependency/license audits and the SBOM.

The downloaded artifacts were present and unexpired:

- `p2-m1-ci-evidence` artifact `9259243734` binds the exact candidate SHA, migration head
  `0008_synth_dataset_foundation`, Git-blob OpenAPI SHA-256
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`, 87 tests with
  zero failures/errors/skips and five passing boundary scan classes;
- `phase1-ci-evidence` artifact `9259243527` binds the same SHA, current head and OpenAPI digest,
  with the retained vertical test passing and zero failures/errors/skips;
- `project-docker-evidence` artifact `9259220684` records the healthy Linux topology and successful
  Celery/Redis probe;
- `project-audit-evidence` artifact `9259246877` contains license summaries and the Python SBOM;
- Gitleaks artifact `9259193639` contains zero SARIF results.

The Windows working-tree OpenAPI file has CRLF-byte digest
`8809c9c63c609cc270c211d3f8cca03f47d76243fa5aeb6304bb385653adfdb2`; the evidence digest above
was independently reproduced from the committed Git blob and is the authoritative same-SHA value.

`P2_M1_CANDIDATE_GATE: PASS`

The independent T08 review subsequently found mandatory database/domain authority defects despite
the green candidate run. The review is recorded in `P2_M1_T08_REVIEW.md`; R07 and R08 must pass and
a new same-SHA remote Gate is required before this Milestone can advance.

`P2_M1_T08_REVIEW: FAIL`

R07 and R08 subsequently passed Principal diff review, 32 domain tests, 10 isolated real-
PostgreSQL migration/invariant tests, scoped Ruff, strict mypy and `git diff --check`. The repairs
enforce bank-independent identities, immutable authority identity evidence and fail-closed direct
`CanonicalPolicy` construction. The independent review now passes locally, but the repair SHA and
new same-SHA GitHub Actions evidence remain pending.

`P2_M1_R07_TASK_ACCEPTED: PASS`

`P2_M1_R08_TASK_ACCEPTED: PASS`

`P2_M1_T08_REPAIR_REVIEW: PASS`

## Repair candidate remote evidence

Repair candidate `9f3ca343223478f60a8eb0aed1b6d2342235f497` completed run `31932052115`
with `quality-and-integration`, `secret-scan` and `docker-validation` all passing. Every mandatory
quality step completed: Python format/lint/type, real PostgreSQL migration lifecycle, Linux Celery,
complete Python and retained Phase 1 recovery tests, P2-M1 boundary evidence, TypeScript/build,
browser integration, contract drift, dependency/license audits and SBOM.

Downloaded, unexpired artifacts were independently inspected:

- `p2-m1-ci-evidence` `9259615693`: exact SHA, head `0008_synth_dataset_foundation`, OpenAPI
  SHA-256 `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`, 94 tests with
  zero failures/errors/skips and five passing boundary classes;
- `phase1-ci-evidence` `9259615509`: same SHA/head/OpenAPI digest and retained vertical evidence
  with zero failures/errors/skips;
- `project-docker-evidence` `9259595719`: healthy PostgreSQL/Redis/API/Worker/Web topology,
  successful HTTP probes and Celery evidence;
- `project-audit-evidence` `9259618402`: license summaries and Python SBOM;
- `gitleaks-results.sarif` `9259575389`: one SARIF run and zero results.

The skipped artifact-upload step in the quality job is the workflow's conditional browser-failure
upload path; the browser integration itself passed and all mandatory evidence uploads succeeded.

`P2_M1_REPAIR_CANDIDATE_GATE: PASS`

`P2_M1_T08_FINAL_STATUS: PASS`

`P2_M1_MILESTONE_GATE: PASS`

Acceptance closure must bind the forward status/evidence commit to a new all-green three-job run
before the Milestone is declared `FROZEN`.

`P2_M1_T07_LOCAL_GATE: PASS`
`P2_M1_T07_STATUS: PASS`
