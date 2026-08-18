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

| Gate             | Required evidence                                                   | Status   |
| ---------------- | ------------------------------------------------------------------- | -------- |
| Architecture     | ADR-036 and rolling-wave contracts accepted                         | T01 PASS |
| QA subject union | ADR-037 preserves M3 base authority and binds variant result QA     | ACCEPTED |
| Domain           | immutable source-relative spec and fail-closed state machine        | T02 PASS |
| Database         | forward `0012`, lifecycle, invariants, concurrency, zero drift      | T03 PASS |
| Source authority | only QA-passed canonical synthetic Asset/identity/run               | T03 PASS |
| Lineage          | source/spec/run/result/measurement chain immutable                  | T03 PASS |
| Candidate        | exact source/version/license/SBOM/vulnerability/zero-network review | T04 PASS |
| Transform        | bounded adapter, no absolute/global target, new Asset only          | PENDING  |
| Determinism      | preregistered same-platform and Windows/Linux evidence              | PENDING  |
| Safety           | bounds/foldover/malformed/second-decode and artifact negatives      | PENDING  |
| Measurement      | requested and actual target/control evidence retained               | PENDING  |
| Recovery         | retry/cancel/duplicate/reconcile and lock-order evidence            | PENDING  |
| Synthetic-only   | no User relation, real-person fixture or sensitive classifier       | PENDING  |
| Contracts        | public OpenAPI/generated TypeScript unchanged                       | PENDING  |
| Full Gate        | Python/TS/PG/Redis/Celery/Docker/Gitleaks/SBOM/same-SHA CI          | PENDING  |
| Review           | independent security and final review                               | PENDING  |

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
- This is local candidate evidence only. `CC-P2-M4-03-A` remains pending tracked commit and same-SHA
  GitHub Actions/artifact inspection; T06 remains blocked, and T07/T08/Milestone Gate remain closed.

## Exit rule

P2-M4 can pass only when every mandatory row has actual evidence, all candidate claims are bounded to
private synthetic M4, same-SHA CI and artifacts are verified, and independent reviews pass. A useful
but insufficient PoC is `FURTHER_RESEARCH`, not PASS. Only Principal can update this document to
`PASS` and later `FROZEN` through separate closure checkpoints.
