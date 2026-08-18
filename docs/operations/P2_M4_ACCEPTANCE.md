# P2-M4 Acceptance Evidence

## Status

- Milestone: `P2-M4 — Deterministic Geometry Variant Research and Engine`
- State: `EXECUTING`
- Entry baseline: `6b86a665e845e113bbfa2820f906d3b78506b753`
- Entry migration head: `0011_offline_synth_source`
- Public API change: none
- M5 entry: closed until P2-M4 is FROZEN

This is the acceptance skeleton. `PENDING` means not yet executed and must never be interpreted as
PASS.

## Mandatory evidence matrix

| Gate             | Required evidence                                                   | Status         |
| ---------------- | ------------------------------------------------------------------- | -------------- |
| Architecture     | ADR-036 and rolling-wave contracts accepted                         | T01 PASS       |
| QA subject union | ADR-037 preserves M3 base authority and binds variant result QA     | ACCEPTED       |
| Domain           | immutable source-relative spec and fail-closed state machine        | T02 PASS       |
| Database         | forward `0012`, lifecycle, invariants, concurrency, zero drift      | T03 PASS       |
| Source authority | only QA-passed canonical synthetic Asset/identity/run               | T03 PASS       |
| Lineage          | source/spec/run/result/measurement chain immutable                  | T03 PASS       |
| Candidate        | exact source/version/license/SBOM/vulnerability/zero-network review | T04 PASS       |
| Transform        | bounded adapter, no absolute/global target, new Asset only          | T05 PASS       |
| Determinism      | preregistered same-platform and Windows/Linux evidence              | T05 PASS       |
| Safety           | bounds/foldover/malformed/second-decode and artifact negatives      | T05 PASS       |
| Measurement      | requested and actual target/control evidence retained               | PENDING        |
| Recovery         | retry/cancel/duplicate/reconcile and lock-order evidence            | T06 LOCAL PASS |
| Synthetic-only   | no User relation, real-person fixture or sensitive classifier       | T06 LOCAL PASS |
| Contracts        | public OpenAPI/generated TypeScript unchanged                       | T06 LOCAL PASS |
| Full Gate        | Python/TS/PG/Redis/Celery/Docker/Gitleaks/SBOM/same-SHA CI          | PENDING        |
| Review           | independent security and final review                               | PENDING        |

## Entry evidence

- P2-M3 freeze-state `6b86a665e845e113bbfa2820f906d3b78506b753` is the local and remote
  authoritative baseline.
- GitHub Actions run `32108427849` completed successfully for all three jobs on that exact SHA.
- Migration head is `0011_offline_synth_source`; M4 must not edit migrations `0001`–`0011`.
- Tracked worktree was clean at branch creation; protected untracked `.tmp/` remains outside M4 scope.
- M3 official MediaPipe wheels remain rejected, its model remains private-research-only, and its
  OpenCV 3.4.11 closure is not M4 adoption.

## T02 domain contract evidence

- `VariantSpecification` is an immutable canonical contract bound to source Asset, identity, QA run,
  ontology/version digest, one target, explicit controls, source-relative integer ppm magnitude,
  algorithm/runtime digest, output bounds and a declared determinism level. Direct construction and
  digest tampering fail closed without echoing references.
- M4 research admits only ontology dimensions classified `READY` or `EXPERIMENTAL`; unknown,
  `UNSUPPORTED`, `REQUIRES_3D` and `STYLE_ONLY` dimensions stop before any result-storage path. The
  contract does not promote an experimental dimension to READY.
- `TransformRunState` preserves monotonic execution with separate `REJECTED`, `FAILED` and
  `CANCELLED` terminals. Skipped states and terminal re-entry are rejected.
- Targeted domain regression passed 60 tests. Full API source Ruff format/lint covered 153 files and
  strict mypy covered 100 source files. OpenAPI/generated TypeScript drift remained zero through
  `pnpm.cmd contracts:check`.
- T02 added no ORM, migration, image/AI dependency, provider/storage/task-runner import, model/image
  artifact, public endpoint or real-person fixture.
- Candidate `c173a46e43312c93b73c11462ee1adb115328fb2` was pushed normally. Same-SHA
  GitHub Actions run `32110263179` passed `quality-and-integration`, `secret-scan` and
  `docker-validation`; the non-blocking Node 20 action-runtime deprecation annotations remain visible.

## T03 PostgreSQL authority evidence

- Forward migration `0012_geometry_variant_authority` adds immutable `VariantSpecification` and
  monotonic `TransformRun` authority without editing `0001`–`0011`. ADR-037 extends the existing M3
  QA authority with the explicit `CANONICAL_BASE | GEOMETRY_VARIANT` subject union: a variant result
  never fabricates raw-source evidence or a `SyntheticAssetRecord`, and one result QA run uniquely
  reverse-binds its transform run.
- PostgreSQL rejects non-canonical or non-QA-passed sources, forged/mixed QA subject shapes,
  specification mutation, illegal or state-incomplete transitions, result reuse, source/result
  equality and duplicate successful lineage. The concurrency test confirms one successful lineage
  authority. Downgrade fails closed if a variant QA subject still exists.
- A fresh database upgrade, `0011→0012→0011→0012`, `alembic check`, six final M4 PostgreSQL tests and
  the complete API suite on a fresh dedicated PostgreSQL database passed. Full API/Worker tests,
  Ruff, strict mypy across 113 source files, contract drift and formatting also passed locally.
- Candidate `e6f45279b72258143a32bd131f5e91aecdaeedd4` exposed one historical-evidence generator defect:
  frozen P2-M3 evidence correctly records head `0011`, while the current repository head is `0012`.
  Repair `P2-M4-R01` in `e36ec5073e9fa5b1750642ff676dc102191b2c3f` preserves both authorities
  separately and does not rewrite frozen evidence or weaken a Gate. Sixteen focused evidence/head
  tests, Ruff and mypy passed.
- Same-SHA GitHub Actions run `32113760284` passed `quality-and-integration`, `secret-scan` and
  `docker-validation`. It executed the `0012` migration lifecycle, full Python/TypeScript/browser
  regression, frozen Phase 1/P2-M1–M3 evidence generation, dependency/license audits, SBOM and
  Gitleaks. Expected artifacts are present and unexpired. Principal accepts T03 and R01 only;
  P2-M4 remains `EXECUTING`, and the milestone Full Gate remains pending.

## T04 candidate evidence

- The general-purpose OpenCV Python wheel and the first two-module source candidate remain
  `FURTHER_RESEARCH`. They are not silently reclassified or reused.
- Candidate `OPENCV_5_0_0_BOUNDED_TRANSITIVE_SOURCE_V2` uses exact OpenCV `5.0.0`, actual modules
  `core;flann;geometry;imgproc`, bundled static zlib `1.3.2` and the narrow first-party C ABI.
- Two clean Linux `--network none` roots and two clean Windows roots are byte-identical per platform.
  All four reports share deterministic digest `ebfee6e9...`; both fixture outputs are byte-identical
  across platforms and all preregistered negative controls pass.
- R08 removes only MSVC PDB metadata under an explicit private build flag. Windows artifacts contain
  no RSDS/PDB, private path, `pthread` or network-capable import. Linux uses relative `$ORIGIN`, has
  zero network undefined symbols and no private paths.
- Windows process-specific outbound denial plus Filtering Platform capture records zero attempted
  egress during a complete harness run. The temporary rule and audit change were restored.
- Apache-2.0/BSD-3-Clause OpenCV notices and the zlib license are retained. The private CycloneDX 1.6
  SBOM is `2345cba1...`; offline Grype `0.117.0` with database v6.1.9 reports zero matches.
- Principal local disposition is `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`. The complete redacted report is
  `docs/research/P2_M4_T04_OPENCV_5_BOUNDED_SOURCE_V2_REPORT.md`. T05 remains closed until this
  tracked evidence checkpoint passes same-SHA GitHub Actions.
- Tracked evidence commit `28e5ae8ab9350fe44fa1e14aa1ae9c15436717fa` completed GitHub Actions run
  `32125987000`; `quality-and-integration`, `secret-scan` and `docker-validation` all passed.
  Downloaded artifact `9320466783` binds the exact SHA, current migration head `0012`, 46 M3 tests
  with zero failures/errors/skips and unchanged private-synthetic boundaries. Project audit, Docker
  and Gitleaks artifacts are present and readable. Principal accepts T04 and opens T05 only.

## T05 compatibility finding

- The first-party port, dense source-relative map, canonical JPEG/RGB boundary, exact-hash loader and
  deterministic fake/native tests are implemented locally but are not yet accepted.
- Exact Windows R08 runtime smoke passed twice. The exact Linux runtime in its qualified builder
  produced the same canonical result SHA-256 `5f7868d5...` with zero network.
- The repository's real Debian 12 API image rejected that Linux binary because it requires
  `GLIBC_2.38` and `CXXABI_1.3.15`, while the image provides glibc 2.36. Therefore Transform,
  Determinism and Full Gate remain `PENDING`.
- `CC-P2-M4-02` reopens only the Linux deployment-compatible candidate identity. T05/T06 cannot use
  a base-image upgrade or an unverified fallback to bypass this Gate.
- Candidate checkpoint `cd25013` exposed `P2-M4-R09`: Linux strict mypy does not expose the
  Windows-only `os.add_dll_directory` attribute even though Windows mypy correctly platform-pruned
  that path. The repair uses a fail-closed runtime capability lookup and does not change accepted
  file hashes, DLL search scope or native execution behavior.
- R09 commit `8332d9341ac06776008755f282fb0814c3cdca9f` completed same-SHA GitHub Actions run
  `32128839492`; `quality-and-integration`, `secret-scan` and `docker-validation` all passed.
- `CC-P2-M4-02` and R10 qualified the deployment-compatible Linux runtime in two byte-identical
  Debian 12 roots. Private-path and network-symbol scans are zero, maximum required glibc is 2.35,
  the updated private SBOM/Grype result has zero matches, and the standard API image produced the
  same canonical T05 output SHA-256 `5f7868d5...` as Windows under `--network none`.
- The exact Linux file hashes and runtime manifest digest `5d0e9ee3...` are frozen in the loader and
  `docs/research/P2_M4_CC02_DEBIAN12_RUNTIME_COMPATIBILITY.md`. T05 remains pending complete local
  regression and a tracked same-SHA candidate checkpoint; T06 is still closed.
- T05 local candidate validation passes Ruff format/lint across 192 files, strict mypy for 115
  API/Worker sources on both Linux and Windows targets, six focused transform tests, all 444 Linux
  API/Worker tests that ran against a fresh PostgreSQL `0012` schema with four existing optional
  skips, the complete pnpm check/build/contract matrix, and the Compose build/health/API/Web/Celery/
  Worker/Alembic behavior matrix. The temporary test databases were dropped after each attempt.
- Two intermediate container-test attempts are preserved as execution evidence: the first lacked
  repository-only files from the runtime image, and the second/third exposed the intentionally
  read-only storage mount and a missing `DATABASE_URL` mirror. No production code or Docker image
  scope was changed to conceal those harness conditions; the corrected full-repository run passed.
- At the local candidate checkpoint, status was `READY_FOR_TRACKED_EVIDENCE`; Principal acceptance
  and T06 remained blocked on same-SHA GitHub Actions and artifact inspection.

## T05 tracked acceptance

- Candidate commit `75c0ccbaeab5ae4e1a8e66054f2225f701e221eb` was pushed to the existing M4
  branch without persistent proxy or Git configuration changes.
- Same-SHA GitHub Actions run `32131383622` passed `quality-and-integration`, `secret-scan` and
  `docker-validation`. The only annotations are the existing non-blocking Node 20 action-runtime
  deprecation notices.
- Unexpired artifacts are present for project audit (`9322446221`), P2-M3 (`9322438906`), P2-M2
  (`9322438065`), P2-M1 (`9322437285`), Phase 1 (`9322436502`), Docker evidence (`9322364021`) and
  Gitleaks SARIF (`9322303145`).
- Principal reviewed the actual diff, build/runtime hashes, private-path/network scans, standard
  image smoke, SBOM/Grype result, local matrix and same-SHA remote result. T05 and R09/R10 are
  accepted. This opens T06 only; P2-M4 remains `EXECUTING`, and T07/T08/Milestone Gate remain open.

`P2_M4_T05: TASK_ACCEPTED`

The forward acceptance checkpoint `2afc084d8dade07d28da3c3d68d87006d4a94f49` completed GitHub
Actions run `32131954633` with all three jobs successful. Its seven unexpired artifacts are bound to
the exact checkpoint SHA: project audit `9322654356`, P2-M3 `9322647301`, P2-M2 `9322646550`,
P2-M1 `9322645828`, Phase 1 `9322645021`, Docker evidence `9322570536`, and Gitleaks SARIF
`9322513368`. This closure confirms the accepted T05 governance checkpoint; it does not complete
T06, T07, T08, or the P2-M4 Milestone Gate.

## T06 authority change control

T06 entry review stopped before implementation because `0012` cannot reconstruct the immutable
`LandmarkWarpPlan` required by the accepted transform port. ADR-038 / `CC-P2-M4-03` accepts a minimal
1:1 `landmark_warp_plans` PostgreSQL authority with the only origin
`PREREGISTERED_M4_RESEARCH_PLAN`. `CC-P2-M4-03-A` must implement and verify the first-party canonical
serialization, ORM, forward `0013` migration and PostgreSQL invariants before T06 resumes. This is a
forward architecture correction, not an Rxx repair, and does not approve a general plan generator.

## CC-P2-M4-03-A local candidate evidence

- The migration file is `0013_landmark_warp_plan_authority.py`; the actual Alembic revision/head is
  `0013_warp_plan_authority`. Governance and runtime evidence must use the revision value when they
  report `migration_head`.
- The implementation adds one immutable ORM/PostgreSQL plan authority per specification, typed
  canonical serialization and parsing, closed origin/builder grammars, unique plan/authority
  digests, and a TransformRun insert guard that locks and requires the plan.
- Principal negative review found that the first trigger version rejected stale digests but could
  accept duplicate JSON keys or integerized coordinates when both digests were recomputed. Before
  commit, the trigger was strengthened to validate the original JSON key order and duplicates,
  reject escapes, and require Python-compatible canonical float text. Four direct-SQL adversarial
  cases now fail closed.
- Local validation passes Ruff format/lint across 159 API files, strict mypy across 116 API/Worker
  sources, 22 domain/PostgreSQL authority tests, OpenAPI contract drift, fresh PostgreSQL upgrade,
  `0013→0012→0013`, and `alembic check` with zero drift. The full Linux API/Worker suite completed
  with every executed test passing and seven existing optional skips; the full pnpm format/lint/
  typecheck/test/contracts/build gate also passes.
- Candidate `4af3a8a3ff3264887ac8752a581180049cb6d240` passed `secret-scan` and
  `docker-validation` in run `32137671571`; all implementation, migration, Python, TypeScript and
  browser steps also passed. `quality-and-integration` then failed only because four evidence steps
  still passed the old `0012_geometry_variant_authority` head. `P2-M4-R11` updates those workflow
  arguments and regression expectations to the actual `0013_warp_plan_authority` without weakening
  any frozen Gate. CC03-A remains pending the R11 exact-SHA run and artifact inspection; T06 remains
  blocked, and T07/T08/Milestone Gate remain closed.

## CC-P2-M4-03-A tracked acceptance

- Repair candidate `741752d82bf22434aed2ffe37d6310452db2e51c` completed run `32138493874`;
  `quality-and-integration`, `secret-scan` and `docker-validation` all passed. The only annotations
  are the existing non-blocking Node action-runtime deprecation notices.
- Seven expected artifacts are present and unexpired: project audit `9325076833`, P2-M3 evidence
  `9325067283`, P2-M2 evidence `9325066429`, P2-M1 evidence `9325065551`, Phase 1 evidence
  `9325064577`, Docker evidence `9324975508`, and Gitleaks SARIF `9324912211`.
- Downloaded Phase 1/P2-M1/P2-M2/P2-M3 evidence binds the exact candidate SHA and actual
  `0013_warp_plan_authority` head. P2-M3 records 46 tests with zero failures/errors/skips; Gitleaks
  records zero results. No new dependency, model, binary, external call, public API, user Asset or
  real facial-processing authority was introduced.
- Principal accepts `CC-P2-M4-03-A` and `P2-M4-R11`. This establishes the immutable preregistered
  warp-plan authority needed by T06; T06 opens after this acceptance checkpoint passes same-SHA CI.
  T07/T08 and the P2-M4 Milestone Gate remain closed.

`CC_P2_M4_03_A: TASK_ACCEPTED`

`P2_M4_R11: REPAIR_ACCEPTED`

## CC-P2-M4-04 runtime composition change control

After CC03-A acceptance, T06 read-only integration review found no typed composition path from Worker
settings to the exact-hash private OpenCV loader. Hardcoded paths, raw environment reads or task
payload paths would violate the accepted adapter and reference-only boundaries. ADR-039 accepts the
minimal forward correction: `disabled | private_opencv` typed configuration, an absolute private
runtime root, one manifest-verifying factory, and production fail-closed. No schema, dependency,
binary, public API, production geometry or real-user authority is added. Implementation and local/
same-SHA validation are pending; T06 remains blocked until Principal acceptance.

`CC_P2_M4_04: IMPLEMENTING`

## CC-P2-M4-04 local candidate evidence

- ADR-039, typed settings and `create_geometry_transform_provider` implement one composition path:
  `private_opencv` requires an absolute root and always enters the T05 exact-hash loader; disabled,
  missing, relative, mismatched and production configurations fail closed without fallback.
- The implementation adds no migration, dependency, binary, public API, network path, User Asset or
  production/real-user geometry authority. M3 runtime behavior remains unchanged.
- Windows targeted config/factory/adapter regression passed 40 tests. Full Ruff format/lint covered
  196 files, strict mypy covered 117 sources, and the no-infrastructure suite passed 332 tests; its
  136 infrastructure skips were not used as final evidence.
- A fresh isolated Linux harness used a task-owned PostgreSQL database, Redis DB, four-queue Celery
  Worker and writable ignored synthetic storage. Fresh `→0013` migration and all API/Worker tests
  passed: 468 passed, zero skipped. `alembic check` reported no upgrade operations.
- `pnpm.cmd check` passed formatting, lint, strict typecheck, 56 TypeScript tests, contract drift and
  production build. Compose config, API/Worker image build, health and targeted Linux tests passed.
- Two earlier harness attempts are not product failures: one reused durable P2 data and omitted
  repository-only source-scan files; another omitted the frozen four-queue Celery routing and
  `LOCAL_STORAGE_ROOT`. The corrected isolated full run closed both conditions without code changes.
- Status is `READY_FOR_TRACKED_EVIDENCE`. T06 remains paused until the exact candidate SHA completes
  all three GitHub Actions jobs and Principal inspects the artifacts.

`CC_P2_M4_04: READY_FOR_TRACKED_EVIDENCE`

## CC-P2-M4-04 tracked acceptance

- Candidate `38e4755e87718ccddc5be81d45177fc37c5caae6` was pushed normally without a
  persistent proxy, force push or history rewrite. Same-SHA run `32142005006` passed
  `quality-and-integration`, `secret-scan` and `docker-validation`; only the existing non-blocking
  Node 20 action-runtime deprecation annotations remain.
- Seven artifacts are present, readable and unexpired: project audit `9326412825`, P2-M3 evidence
  `9326404299`, P2-M2 evidence `9326403612`, P2-M1 evidence `9326402997`, Phase 1 evidence
  `9326402268`, Docker evidence `9326312899`, and Gitleaks SARIF `9326243254`.
- Phase 1 and P2-M1–M3 evidence all bind the candidate SHA, migration head
  `0013_warp_plan_authority` and unchanged OpenAPI digest `a9ee1e0a...`. P2-M1 records 98 tests,
  P2-M2 52 tests and P2-M3 46 tests with zero failures/errors/skips. Gitleaks records zero results.
- Principal reviewed the actual diff, local full matrix, production fail-closed behavior, same-SHA
  jobs and downloaded artifacts. `CC-P2-M4-04` is accepted. T06 resumes only after this forward
  acceptance checkpoint completes its own same-SHA CI; T07/T08 and the Milestone Gate remain closed.

`CC_P2_M4_04: TASK_ACCEPTED`

## T06 local candidate evidence

- A closed `SyntheticTransformTaskMessage` carries only `transform_run_id`, `job_id`, `request_id`
  and schema version. The generic Job payload remains `{}`; plan, image, policy, storage key and
  runtime path are reconstructed only from PostgreSQL authority and typed private providers.
- The transform service locks and validates `TransformRun → VariantSpecification →
LandmarkWarpPlanAuthority → passed canonical source QA/record/identity/Asset`, reads only the
  private normalized namespace, verifies output/runtime/plan evidence and creates exactly one
  immutable synthetic variant Asset plus one `SyntheticQARun/v2` handoff.
- The private variant namespace is `internal-synthetic/v1/variants/<digest>`. Its create-if-absent
  receipt binds checksum, dimensions, specification, runtime, plan and output-policy facts; malformed
  metadata, payload mismatch, symlink/path escape and conflicting replay fail closed. A deterministic
  receipt survives storage-before-database failure and is reused without duplicate Asset authority.
- Job/Attempt integration covers at-least-once duplicate delivery, four-attempt retry exhaustion,
  cancellation and orphan removal, reconciliation, committed-result envelope recovery and M3
  `OUTPUT_STORED → MEASURING → COMPLETED | REJECTED | FAILED` QA handoff. Bare pending variant QA is
  not auto-evaluated before T07 supplies measurement evidence.
- Worker composition uses only `create_geometry_transform_provider(settings)`. Disabled or missing
  private runtime configuration fails before storage composition/source reads. Local and Celery
  routes preserve late acknowledgement and the runtime path never enters message or result contracts.
- A real Linux Redis/Celery four-queue round trip loaded the accepted exact-hash Debian 12 OpenCV
  runtime, consumed only the reference message and committed one `variant_qa_pending` result. The
  returned result, Job payload and checked evidence contain no runtime path.
- On a fresh task-owned PostgreSQL database migrated `→0013`, fresh private storage and isolated Redis
  DBs, all 481 API/Worker tests passed with zero skip, including the real M4 round trip. Ruff format/
  lint covered 204 files, strict mypy covered 122 sources, Alembic check reported zero drift, and the
  complete pnpm format/lint/typecheck/test/contracts/build Gate passed with unchanged public contracts.
- Earlier full-run failures were harness evidence only: reused P2 rows correctly blocked destructive
  downgrade, copied build symlinks did not initially match the accepted runtime shape, and globally
  injecting geometry settings contaminated fail-closed config tests. Fresh isolation and a test-only
  runtime mount corrected all three without weakening or changing product behavior.
- T06 adds no migration, dependency, model/image artifact, public API, production geometry, User Asset
  path, real-person fixture or external network call. Candidate commit, normal push, same-SHA Actions
  and artifact inspection remain mandatory before Principal task acceptance; T07/T08 stay closed.

`P2_M4_T06: READY_FOR_TRACKED_EVIDENCE`

## Exit rule

P2-M4 can pass only when every mandatory row has actual evidence, all candidate claims are bounded to
private synthetic M4, same-SHA CI and artifacts are verified, and independent reviews pass. A useful
but insufficient PoC is `FURTHER_RESEARCH`, not PASS. Only Principal can update this document to
`PASS` and later `FROZEN` through separate closure checkpoints.
