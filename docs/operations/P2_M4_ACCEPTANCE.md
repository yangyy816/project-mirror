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
| Domain           | immutable source-relative spec and fail-closed state machine        | T02 PASS |
| Database         | forward `0012`, lifecycle, invariants, concurrency, zero drift      | PENDING  |
| Source authority | only QA-passed canonical synthetic Asset/identity/run               | PENDING  |
| Lineage          | source/spec/run/result/measurement chain immutable                  | PENDING  |
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

## Exit rule

P2-M4 can pass only when every mandatory row has actual evidence, all candidate claims are bounded to
private synthetic M4, same-SHA CI and artifacts are verified, and independent reviews pass. A useful
but insufficient PoC is `FURTHER_RESEARCH`, not PASS. Only Principal can update this document to
`PASS` and later `FROZEN` through separate closure checkpoints.
