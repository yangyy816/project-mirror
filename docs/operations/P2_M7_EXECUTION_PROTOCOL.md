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

## Common bounded-task safety baseline

Every task begins with `BOOTSTRAP_STATUS: OK` only after it rereads the current branch/HEAD/status, this protocol,
acceptance evidence, ADR-051, relevant accepted service contracts and the current dependency/supply-chain record.

- Inputs and assumptions: P2-M2/M3/M4 accepted authorities are immutable inputs; M5 fresh-study and P2-M6 release
  remain closed. Missing evidence is never inferred or recreated.
- Security/privacy/data: synthetic-only; no User relation, real-person fixture, Prompt, object key, URL, bytes,
  provider payload, credential or private path in code output, logs, CI evidence or task message. PostgreSQL and
  append-only audit/evidence retain authority.
- License: no new package, model, weight, SDK or remote service is permitted unless a separate qualification/change
  control has passed. Existing deterministic Mock and numeric/JSON fixtures remain zero-network.
- Rollback: disable the unaccepted command path and preserve authoritative evidence. Schema downgrade is not an M7
  fallback; any necessary schema change is separately authorized.
- Output format: `TASK_ID; STATUS; SUMMARY; FILES_CHANGED; TESTS_RUN; TEST_RESULTS; ACCEPTANCE_CRITERIA; SECURITY_NOTES; PRIVACY_NOTES; DATA_NOTES; OSS_LICENSE_NOTES; ASSUMPTIONS; BLOCKERS; RISKS_FOUND; HANDOFF_NOTES; NEXT_READY_TASK`.
- Escalation: any new authority/schema, public API, role/authentication model, dependency, Provider/model, M5/M6
  behavior, production enablement, direct private-input requirement or invariant conflict stops the task and returns
  `ESCALATION_REQUIRED` to Principal.

## P2-M7-T01 — governance and operating contract

- Why delegated: Principal-owned architecture/governance refinement; no worker may choose its control-plane boundary.
- Scope / allowed files: ADR-051, this protocol, acceptance skeleton, MILESTONES and autonomous log only.
- Expected change: encode the already approved internal CLI/application-service, audit, cost, redaction and M5/M6
  exclusion boundary.
- Forbidden scope: all product code, migration, dependency/model acquisition, public API, Provider call, M5 research
  execution and M6 release/revoke.
- Dependencies: P2-M2 frozen contracts and current repository truth.
- Acceptance criteria: explicit scope, ownership, task DAG, collision domains, redaction/fail-closed rules, validation
  sequence and every bounded-task contract field are present without creating new authority.
- Validation commands: scoped Prettier, `pnpm.cmd format:check`, `git diff --check`, invariant/public-contract/dependency
  negative scan and same-SHA CI/artifact review.
- Recommended agent / model: Principal / Sol High.
- Current status: `PENDING_P2_M7_R01_CONTRACT_COMPLETENESS_REPAIR`.

## P2-M7-T02 — typed operation-service contract

- Why delegated: a bounded first-party domain/application contract can be implemented after Principal accepts T01.
- Scope / allowed files: new P2 operations domain/application modules and targeted API/Worker tests; no existing M2/M3/M5
  authority owner changes.
- Expected change: typed command request/result, actor/reason/expectation, redacted rendering and stable fail-closed
  error taxonomy around accepted services.
- Forbidden scope: direct database writes, CLI parsing, schema/migration, Provider calls, M5/M6 behavior and public API.
- Dependencies: accepted T01 and ADR-051.
- Acceptance criteria: invalid environment, missing actor/reason/expectation, secret-like output and unavailable target
  services fail closed and deterministically.
- Validation commands: Ruff, strict mypy and targeted deterministic positive/negative tests.
- Recommended agent / model: backend worker / Terra Medium.

## P2-M7-T03 — internal CLI adapter

- Why delegated: adapter implementation is separable only after T02 freezes the first-party service contract.
- Scope / allowed files: CLI entry point/adapter, command help and CLI tests.
- Expected change: `mirror-dataset` parses explicit non-secret environment/actor/reason/expected-state inputs and calls
  T02 services without direct SQL.
- Forbidden scope: HTTP, object-storage reads, Prompt/image output, release/revoke command, interactive credential
  acquisition or production enablement.
- Dependencies: accepted T02.
- Acceptance criteria: outputs are redacted, error codes stable and validation failure has no authority mutation.
- Validation commands: Ruff, strict mypy, CLI tests, source scan and deterministic no-network test.
- Recommended agent / model: backend worker / Terra Medium.

## P2-M7-T04 — cost and payload-free observability projection

- Why delegated: read-only aggregate and event work is isolated once the operation contract is frozen.
- Scope / allowed files: operations projection/event modules, tests and a P2 operations runbook.
- Expected change: reproducible aggregates over accepted cost authority and allowlisted operational-event projection.
- Forbidden scope: monetary inference, dashboard/collector, raw payload logging, Provider SDK and new data authority.
- Dependencies: accepted T02; T03 may proceed independently once its contract is frozen.
- Acceptance criteria: actual/estimated/unavailable remain distinct, unsafe fields are rejected and audit/event correlation
  is preserved.
- Validation commands: targeted unit/integration tests, redaction scan and PostgreSQL-backed read-model tests.
- Recommended agent / model: backend worker / Terra Medium.

## P2-M7-T05 — recovery and concurrency integration

- Why delegated: recovery and locking behavior are difficult but bounded by the accepted command/service contracts.
- Scope / allowed files: application/repository integration plus real PostgreSQL/Redis/Celery tests.
- Expected change: duplicate, cancellation, stale-expectation, crash and concurrent operator paths preserve one
  authoritative outcome or stable terminal evidence.
- Forbidden scope: M2 budget semantics, M5 research execution, M6 release/revoke, public API and new Provider.
- Dependencies: accepted T02–T04.
- Acceptance criteria: no orphaned command effect, lock-order violation or unredacted diagnostic.
- Validation commands: real PostgreSQL, Redis/Celery, duplicate/concurrency/recovery tests and full affected regression.
- Recommended agent / model: Terra High worker / Terra High.

## P2-M7-T06 — independent deterministic evaluation

- Why delegated: independent test ownership prevents implementer-only proof of redaction and fail-closed behavior.
- Scope / allowed files: tests, numeric/JSON fixtures and source scans.
- Expected change: deterministic positive/negative evidence for every M7 hard boundary.
- Forbidden scope: production repair, private input, image fixture, live network and policy/threshold changes.
- Dependencies: accepted T02–T05.
- Acceptance criteria: zero mandatory skip; synthetic-only, authorization, redaction, production fail-closed and no
  contract/dependency drift are all directly covered.
- Validation commands: targeted plus full Python/TypeScript/contract tests, migration check, Docker/Compose and Gitleaks.
- Recommended agent / model: test worker / Terra Medium.

## P2-M7-T07 — CI evidence

- Why delegated: CI evidence is isolated from implementation and must preserve prior Gates.
- Scope / allowed files: CI evidence generator/tests, workflow wiring if necessary and acceptance evidence only.
- Expected change: machine-readable `mirror.p2-m7.ci-evidence/v1` with allowlisted aggregates.
- Forbidden scope: weakening existing Gates, artifact payload/path leakage, live service dependency and product behavior.
- Dependencies: accepted T06.
- Acceptance criteria: evidence binds SHA, migration head, OpenAPI digest, M7 summary and zero mandatory skip; all eight
  artifacts are readable and content-inspected.
- Validation commands: full existing CI matrix, artifact inspection, source scan and `git diff --check`.
- Recommended agent / model: infra worker / Terra Medium.

## P2-M7-T08 — independent review and closure

- Why delegated: Gate judgment must be separated from implementation.
- Scope / allowed files: read-only review reports, acceptance evidence and bounded repair records only.
- Expected change: evidence-backed security/privacy/license and final dispositions; no implementation in review tasks.
- Forbidden scope: Gate weakening, unreviewed repair, M5/M6 scope change or production enablement.
- Dependencies: accepted T07 and readable same-SHA artifacts.
- Acceptance criteria: no direct-SQL/API/secret/private-payload/M5-M6 bypass; every unverified item remains explicit;
  closure may occur only after Principal reviews actual evidence.
- Validation commands: diff/schema/source/evidence/artifact review; unexecuted checks must read `NOT VERIFIED`.
- Recommended agent / model: security reviewer / Terra High, then final reviewer / Sol High.

## P2-M7-R01 — bounded-task contract completeness repair

- Objective: make the T01 candidate conform to the standing bounded-task contract without changing M7 architecture.
- Why delegated: Principal-owned governance repair; it is not a substitute for a new T09/T10 task.
- Scope / allowed files: this protocol, acceptance evidence and autonomous log only.
- Expected change: add the missing task-level objective/rationale/scope/dependency/validation/security/data/license/rollback/
  model/escalation/output fields, and retain every prior M5/M6/production boundary.
- Forbidden scope: ADR decision change, schema, code, migration, dependency, Provider/model, public API, M5 execution or
  M6 release/revoke.
- Dependencies: current unaccepted T01 candidate and the goal objective's bounded-task requirements.
- Acceptance criteria: each T01–T08 card contains all required fields or explicitly inherits a named common baseline;
  no contract authorizes work previously closed.
- Validation commands: scoped Prettier, `pnpm.cmd format:check`, `git diff --check`, contract-field completeness scan and
  same-SHA CI/artifact review.
- Recommended agent / model: Principal / Sol High.

`P2_M7_R01: READY_FOR_TRACKED_EVIDENCE`

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
