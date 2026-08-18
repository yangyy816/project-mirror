# P2-M4 Execution Protocol

## Authority and state

- Milestone: `P2-M4 — Deterministic Geometry Variant Research and Engine`
- Entry baseline: P2-M3 freeze-state `6b86a665e845e113bbfa2820f906d3b78506b753`
- Entry run: `32108427849`; all three jobs passed on the exact SHA
- Branch: `codex/phase2-m4-geometry-variants`
- State: `EXECUTING`
- Migration head at entry: `0011_offline_synth_source`
- Architecture authority: ADR-021–036
- Public API impact: none
- Real-user facial processing: prohibited
- QuestionBank release: not authorized

P2-M4 begins only after P2-M3 is FROZEN. This protocol authorizes bounded implementation after the
Principal refinement checkpoint; it does not approve any transform library, production Vision,
real-user processing, M5 isolation conclusion or M6 release.

## Objective and non-goals

M4 builds auditable source-relative geometry transform authority and determines whether a bounded
2D candidate can produce reproducible synthetic variants whose requested and measured effects can
be evaluated later by M5.

M4 excludes:

- real user photos, SelfState, DesiredDelta, questionnaire runtime and editing products;
- Prompt-only geometry claims, global ideal faces and sensitive-trait routing;
- final variable-isolation thresholds, duplicate/diversity decisions and P2-MVR-v1 PASS;
- QuestionBank manifest/release/revoke and public/internal HTTP or M7 CLI;
- silent adoption of MediaPipe/OpenCV artifacts from M3.

## Frozen contracts

The authority chain is:

```text
QA-passed canonical source Asset + SyntheticIdentity + source QARun
→ immutable VariantSpecification
→ append-only TransformRun / attempts
→ GeometryTransform port
→ new immutable private variant Asset
→ result QA measurement authority
→ transform evidence ready for M5 isolation
```

`VariantSpecification` is source-relative and versioned. It binds target direction/magnitude and
control dimensions but never stores an absolute target face. Only `EXPERIMENTAL` or `READY`
dimensions may enter research execution; M4 alone cannot promote a dimension to `READY`.

`TransformRun` distinguishes infrastructure failure, deterministic content rejection and completed
measurement. Cancellation stops new work but preserves attempts and produced evidence. A successful
run never overwrites source or result bytes and never aliases the source checksum.

## Supply-chain and candidate Gate

- Pinned Pillow 12.3.0 remains approved for its existing P2 scopes only. Any transform-specific use
  must be declared in the candidate PoC and accepted forward; approval is not inferred.
- M3 OpenCV 3.4.11 artifacts are evidence for the V03 Vision closure only and are unavailable as the
  M4 runtime.
- A new candidate must use an exact trusted upstream, checksums, private ignored storage, license and
  transitive-dependency inventory, SBOM, vulnerability disposition, Python 3.13 where applicable,
  Windows/Linux/Docker parity, deterministic replay, resource bounds, zero-network and replacement
  boundary.
- User authorization permits required downloads. It does not waive these Gates or authorize lockfile,
  production, distribution or real-user use.

Candidate progression:

```text
RESEARCH_CANDIDATE
→ ISOLATED_POC
→ BENCHMARKED
→ APPROVED_FOR_PRIVATE_SYNTHETIC_M4 | REJECTED | FURTHER_RESEARCH
```

## Execution tasks

Every delegated task uses the repository bounded-task report format and starts with
`BOOTSTRAP_STATUS: OK`.

Common packet fields for T01–T08:

- `INPUTS_AND_ASSUMPTIONS`: ADR-036, this protocol, the research protocol, P2-M3 frozen evidence and
  unchanged Product Invariants. No task may infer an unrecorded dependency, threshold or production
  approval.
- `SECURITY_NOTES`: synthetic-only, bounded resources, private storage, zero arbitrary URL/network and
  production fail-closed.
- `PRIVACY_NOTES`: no User Asset, real-person reference, sensitive inference or real-user facial
  processing.
- `DATA_NOTES`: source/spec/run/result/measurement facts remain separate and immutable; no Prompt,
  image bytes, private path or object key in committed evidence.
- `LICENSE_NOTES`: downloads require trusted exact source, checksum and private ignored storage;
  adoption requires explicit forward approval.
- `ROLLBACK`: disable the new M4 path and preserve evidence; schema downgrade is test/development-only
  before durable M4 rows, otherwise use forward repair.
- `OUTPUT_FORMAT`: repository bounded-task report with status, changed files, validations, security,
  privacy, data, license, blockers, risks and handoff.
- `ESCALATION_CONDITION`: any need to change architecture, schema ownership, public API, Product
  Invariant, security/privacy boundary, dependency disposition or task objective returns to Principal.

### P2-M4-T01 — Freeze M4 architecture and research contracts

- Objective/why: make authority and stop rules unambiguous before implementation; retained by
  Principal because this is architecture work.
- Scope: ADR-036, this protocol, research protocol, acceptance skeleton, milestone and memory state.
- Expected change: governance documents only; state advances from refinement-open to
  `EXECUTION_READY`.
- Forbidden: production code, migration, dependency install, model/image generation and M5 work.
- Dependencies: P2-M3 FROZEN and exact-SHA entry evidence.
- Acceptance: no undecided authority remains for T02–T04; conflicts and stale active-state references
  are zero.
- Validation: Markdown format, `git diff --check`, invariant/conflict scan.
- Agent: Principal / Sol High.

### P2-M4-T02 — Domain contracts and state machine

- Objective/why: encode the frozen first-party contract without coupling it to ORM or a candidate;
  delegated only if bounded implementation improves throughput.
- Scope: first-party `VariantSpecification`, directions/magnitude, researchable-dimension guard,
  deterministic-level taxonomy, transform states/reasons and unit tests.
- Expected change: deterministic pure-domain types and exhaustive transition/validation tests.
- Forbidden: ORM/migration, algorithm adapter, storage/Worker and threshold selection.
- Dependencies: T01 and Principal refinement checkpoint PASS.
- Acceptance: canonical input is stable across runs; all unknown/unsupported states and dimensions
  fail closed without leaking payloads.
- Validation: Ruff, strict mypy, targeted deterministic/negative unit tests.
- Agent: backend worker, Terra Medium.

### P2-M4-T03 — PostgreSQL transform authority

- Objective/why: persist immutable lineage and recovery state under PostgreSQL authority; delegated
  because the frozen transaction design has complex failure paths.
- Scope: forward `0012` migration, ORM models and PostgreSQL invariant/concurrency tests for immutable
  specification, monotonic run/attempt state and source/result lineage.
- Expected change: one new forward migration plus models/tests; no public contract change.
- Forbidden: historical migration edits, algorithm implementation, M5 report/release tables.
- Dependencies: T01 checkpoint; exact names and enums integrated with T02 before merge.
- Acceptance: PostgreSQL rejects mutation, illegal transition, invalid source authority and duplicate
  successful lineage; lifecycle/check is zero drift.
- Validation: fresh upgrade, `0011→0012→0011→0012`, `alembic check`, PostgreSQL tests, Ruff/mypy.
- Agent: data worker, Terra High because transaction and immutable-lineage boundaries are frozen but
  failure paths are complex.

### P2-M4-T04 — Candidate preregistration and isolated PoC

- Objective/why: produce evidence before selecting a transform implementation; delegated for isolated
  supply-chain and platform research.
- Scope: exact candidate acquisition in ignored private storage, algorithm fixtures, license/SBOM/
  vulnerability evidence, deterministic/zero-network/platform/footprint/performance benchmark.
- Expected change: preregistration and redacted research/supply-chain evidence only; project manifests
  remain unchanged until a later explicit adoption decision.
- Forbidden: project manifest adoption, production dependency, real faces, threshold changes after
  holdout, M3 OpenCV authority reuse.
- Dependencies: T01 checkpoint; T02 contract names are inputs to the harness but not the candidate.
- Acceptance: one candidate receives an evidence-backed disposition and every failed attempt remains
  visible; absence of a passing candidate is an honest `FURTHER_RESEARCH` result.
- Validation: exact checksums, negative controls, two clean same-platform runs, Windows/Linux/Docker
  comparison and source/network scans.
- Agent: infra worker, Terra Medium; security review is independent.

### P2-M4-T05 — Approved deterministic transform adapter

- Objective/why: implement only the benchmark-selected adapter behind the first-party port; delegated
  because numeric bounds and failure paths are difficult but the contract is frozen.
- Dependency: T04 candidate is explicitly `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`.
- Scope: first-party port and the selected private synthetic adapter, bounded pixel/landmark handling,
  canonical encode and deterministic replay.
- Expected change: adapter and golden tests, plus only the dependency lock explicitly approved by the
  T04 change control.
- Forbidden: unapproved fallback, global target face, public API, M5 isolation conclusion.
- Acceptance: declared determinism level and all safety negatives pass; adapter types do not leak into
  domain.
- Validation: golden numeric/image fixtures, bounds/foldover/artifact negatives, determinism, parity,
  Ruff/mypy/pytest.
- Agent: Terra High because the contract is frozen and numeric failure paths are deep.

### P2-M4-T06 — Application, storage and Worker integration

- Objective/why: make execution recoverable under at-least-once delivery without moving domain
  authority into Celery; delegated for complex concurrency/recovery control flow.
- Scope: reference-only task, Job/Attempt envelope, private variant namespace, create-if-absent,
  idempotency, cancellation/retry/reconcile and result QA handoff.
- Expected change: application/repository/storage/Worker adapters and integration tests.
- Forbidden: Prompt/image generation, CLI, release or User Asset path.
- Dependencies: T02, T03 and T05 accepted.
- Acceptance: duplicate/crash/cancel/retry paths produce one immutable successful authority or explicit
  terminal evidence with no orphan ambiguity.
- Validation: PostgreSQL, Redis/Celery, crash recovery, duplicate delivery, lock order, zero-network.
- Agent: Terra High.

### P2-M4-T07 — Integrated deterministic evaluation

- Objective/why: independently test the assembled engine against the preregistered protocol;
  delegated to a test worker for implementation-independent evidence.
- Scope: approved synthetic identities, bidirectional candidate variants, repeated-run/platform
  evidence, actual target/control measurements and unsupported-dimension controls.
- Expected change: evaluation fixtures/harness and redacted evidence; no production logic repair.
- Forbidden: M5 tolerance freeze, P2-MVR PASS, silent replacement of failed assets.
- Dependencies: T02–T06 accepted and candidate/runtime digests frozen.
- Acceptance: calibration/holdout separation, actual measurements, deterministic evidence and every
  negative control are reproducible with zero mandatory skip.
- Validation: preregistered evaluation, no calibration/holdout overlap, zero mandatory skip, redacted
  evidence with no image/path/object key.
- Agent: test worker, Terra Medium.

### P2-M4-T08 — CI, security and final review

- Objective/why: prove integrated correctness and boundaries on the exact candidate SHA; separated
  into infra, security and final review responsibilities for independent evidence.
- Scope: same-SHA M4 evidence, full local/remote Gate, artifact inspection, independent security and
  final review, bounded repairs and closure/freeze sequence.
- Expected change: CI evidence generator, acceptance/review records and only bounded `P2-M4-Rxx`
  repairs returned to their owning module.
- Forbidden: lowering Phase 1/M1–M3 Gates or entering M5 implementation.
- Dependencies: T01–T07 accepted.
- Acceptance: all mandatory acceptance rows, three GitHub jobs, artifacts and independent reviews pass
  on the same SHA; otherwise state remains EXECUTING/FAIL/FURTHER_RESEARCH.
- Validation: full Python/TS/PG/Redis/Celery/Docker/contracts/Gitleaks/SBOM/Actions matrix.
- Agent: infra worker plus independent security/final reviewers.

## Dependency DAG and collision domains

```text
T01 → Principal checkpoint
       ├─ T02 domain ─┐
       ├─ T03 data   ├→ integration → T05 → T06 → T07 → T08
       └─ T04 PoC ───┘
```

T02 owns new domain modules, T03 owns models/migration/database tests, and T04 owns ignored PoC plus
supply-chain/research evidence. They may run in parallel only after names and contracts from T01 are
frozen. T05–T08 are sequential. No two write tasks may own the same migration, execution protocol,
CI workflow or acceptance state.

## Repair and checkpoint protocol

Implementation defects use `P2-M4-R01...`. Architecture, privacy, schema ownership, dependency
adoption, algorithm objective or Phase-boundary changes require forward change control and cannot be
packaged as Repair Tasks.

Closure sequence:

```text
targeted validation
→ full local Gate
→ candidate commit/push
→ same-SHA GitHub Actions and artifact inspection
→ independent security/final review
→ bounded Rxx repairs
→ Principal PASS decision
→ acceptance closure CI
→ freeze-state CI
```

Only Principal may declare `P2-M4: PASS/FROZEN`. A failed candidate may yield
`FURTHER_RESEARCH` without weakening Gates; M5 entry remains closed until M4 is FROZEN.
