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
| Candidate        | exact source/version/license/SBOM/vulnerability/zero-network review | PENDING  |
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

## Exit rule

P2-M4 can pass only when every mandatory row has actual evidence, all candidate claims are bounded to
private synthetic M4, same-SHA CI and artifacts are verified, and independent reviews pass. A useful
but insufficient PoC is `FURTHER_RESEARCH`, not PASS. Only Principal can update this document to
`PASS` and later `FROZEN` through separate closure checkpoints.
