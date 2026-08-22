# P2-M7 Execution Protocol

## Authority and current state

- Milestone: `P2-M7 — Internal Operations, Cost and Observability`
- Rolling-wave branch: `codex/phase2-m7-internal-operations`
- Planning baseline: `fd64a313c3f2da534e3e019991f1cdb8352f5a74`
- Baseline CI: run `32586638200`, all three jobs passed; eight unexpired exact-SHA artifacts exist.
- Migration head: `0014_m5_eval_authority`
- Architecture authority: ADR-022, ADR-025, ADR-043, ADR-049 and ADR-051.
- Public API impact: none.
- State: `COMMITTED`; this document is a T01 local governance candidate, not an implementation authorization.

## Objective

Provide the smallest internal control plane for accepted P2 synthetic research authorities: auditable operator actions,
redacted status/provenance inspection, cost aggregation and payload-free operational evidence. The control plane must
consume application services and PostgreSQL authority instead of becoming a competing operational database.

## Non-goals and closed boundaries

- no public or admin HTTP, Web UI, OpenAPI change or direct SQL;
- no production Provider, real-user facial processing, real data, credentials, model artifact or external network call;
- no QuestionBank release/revoke command before P2-M6 establishes those services;
- no M5 threshold, holdout, fresh-study, replay, source acquisition or private-input action;
- no telemetry collector, dashboard, pager, alert deployment or claim of production observability.

## Frozen control-plane rules

```text
mirror-dataset CLI
  -> typed application service
  -> PostgreSQL authority / append-only audit evidence
  -> payload-free operational event projection
```

1. Every mutation requires explicit DB environment, actor, reason, request correlation and expected immutable target
   state/reference. A stale or absent expectation fails closed.
2. The CLI may print opaque IDs and allowlisted aggregates, but never Prompt, object key, URL, image or landmark bytes,
   raw Provider payload, private path, credential or user data.
3. PostgreSQL remains authority. Celery, CLI stdout and operational events are projections and cannot override a failed
   hard gate or a terminal evidence state.
4. Cost keeps `actual`, `estimated` and `unavailable` distinct. Native offline request counts never become a monetary
   cost fact.
5. The production boundary rejects unsupported CLI configuration and all development/local/Mock paths. CI remains
   deterministic and zero-network.

## Bounded task DAG

```text
T01 governance / ADR / acceptance skeleton
  -> T02 operation-service and authorization contract
  -> T03 CLI adapter and redacted rendering
  -> T04 cost and operational-event projections
  -> T05 recovery / concurrency / fail-closed integration
  -> T06 independent deterministic evaluation
  -> T07 CI evidence and same-SHA candidate Gate
  -> T08 security + final review / closure
```

No task may modify public API, generated TypeScript, historic migrations, M5 research policy, M6 release authority or
production enablement. A new persistence authority, role model, dependency, model, Provider, public contract or
schema requirement is a change-control boundary, not a repair.

## T01 — governance and operating contract

- Objective: encode the approved internal-CLI, audit, cost and observability boundary before implementation.
- Scope: ADR-051, this protocol, acceptance skeleton, MILESTONES and durable autonomous log only.
- Acceptance: M7 has explicit scope, ownership, task DAG, collision domains, redaction rules, fail-closed behavior,
  validation sequence and a clear M5/M6 exclusion.
- Validation: Markdown formatting, `pnpm.cmd format:check`, `git diff --check`, invariant / public-contract / dependency
  negative scan.
- Status: `READY_FOR_TRACKED_EVIDENCE`.

## T02 — typed operation-service contract

- Objective: define first-party command request/result, actor/reason/expectation and redaction types around already
  accepted services.
- Scope: new P2 operations domain/application modules and tests.
- Forbidden: direct database writes, CLI parsing, schema/migration, Provider calls, M5/M6 behavior and public API.
- Acceptance: invalid environment, missing actor/reason/expectation, secret-like output and unavailable target services
  fail closed and deterministically.
- Validation: Ruff, strict mypy and targeted deterministic negative tests.

## T03 — internal CLI adapter

- Objective: implement `mirror-dataset` command parsing and rendering solely through T02 services.
- Scope: package entry point, CLI adapter and CLI tests.
- Forbidden: direct SQL, HTTP, object storage reads, Prompt/image output, release/revoke command, interactive credential
  acquisition or production enablement.
- Acceptance: explicit environment is required; outputs are redacted; commands return stable error codes and do not
  mutate authority on validation failure.
- Validation: Ruff, strict mypy, CLI unit tests, source scan and deterministic no-network test.

## T04 — cost and payload-free observability projection

- Objective: expose bounded aggregate cost/status and allowlisted events from accepted authority.
- Scope: operations projection/event modules, tests and a P2 operations runbook.
- Forbidden: new monetary inference, dashboard/collector, raw payload logging and Provider SDK.
- Acceptance: actual/estimated/unavailable remain distinct; aggregation is reproducible from authority; unsafe fields are
  rejected; audit/event correlation is preserved.
- Validation: targeted unit/integration tests, redaction scan and PostgreSQL-backed read-model tests.

## T05 — recovery and concurrency integration

- Objective: prove commands preserve PostgreSQL/Job authority through duplicate submission, cancellation, stale
  expectation, crash and concurrent operator paths.
- Scope: application/repository integration and real PostgreSQL/Redis/Celery tests only.
- Forbidden: changing M2 budget semantics, M5 research execution, M6 release/revoke, public API or a new Provider.
- Acceptance: one valid authority transition or one stable terminal evidence outcome; no orphaned command effect or
  unredacted diagnostic.
- Validation: real PostgreSQL, Redis/Celery, duplicate/concurrency/recovery tests and full affected regression.

## T06 — independent deterministic evaluation

- Objective: independently prove synthetic-only, operator authorization, redaction, production fail-closed and no
  contract/dependency drift.
- Scope: tests, numeric/JSON fixtures and source scans.
- Forbidden: production repair, private input, image fixture, live network and policy/threshold changes.
- Acceptance: every M7 hard boundary has positive and negative deterministic evidence with zero mandatory skip.
- Validation: targeted + full Python/TypeScript/contract tests, migration check, Docker/Compose and Gitleaks.

## T07 — CI evidence

- Objective: add machine-readable `mirror.p2-m7.ci-evidence/v1` and obtain same-SHA three-job evidence.
- Scope: CI evidence generator/tests and acceptance evidence only.
- Forbidden: weakening existing gates, artifact payload/path leakage or live service dependency.
- Acceptance: evidence binds SHA, migration head, OpenAPI digest, M7 summary, zero mandatory skip and redacted
  aggregates; eight CI artifacts are present and readable.

## T08 — independent review and closure

- Objective: security/privacy/license and final review of the complete M7 candidate, then acceptance closure.
- Scope: read-only review reports and bounded repair records.
- Acceptance: no direct-SQL/API/secret/private-payload/M5-M6 scope bypass; every unverified item is stated; final
  disposition is evidence-backed.

## Collision domains and entry rules

| Area                             | Owner     | Collision rule                                               |
| -------------------------------- | --------- | ------------------------------------------------------------ |
| ADR/protocol/acceptance/CI state | Principal | Serial only; no concurrent M5/M6 governance edits.           |
| Operations domain/application    | T02       | No migration or existing M2/M3/M5 service ownership changes. |
| CLI adapter                      | T03       | Depends on T02; cannot define new authority.                 |
| Cost/events/runbook              | T04       | Depends on T02; no collector or dashboard.                   |
| Recovery integration             | T05       | Depends on T02–T04; real infrastructure only.                |
| Tests/evidence/reviews           | T06–T08   | Sequential after implementation.                             |

`P2_M7_T01: PENDING_ARTIFACT_CONTENT_INSPECTION`

`P2_M7_STATE: COMMITTED`

`P2_M7_NEXT_ACTION: RESTORE_READ_ONLY_ARTIFACT_ACCESS_THEN_INSPECT_T01_ARCHIVES`
