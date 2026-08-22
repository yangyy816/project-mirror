# P2-M7 Acceptance Evidence

## Status

- Milestone: `P2-M7 — Internal Operations, Cost and Observability`
- State: `COMMITTED`
- Planning baseline: `fd64a313c3f2da534e3e019991f1cdb8352f5a74`
- Migration head: `0014_m5_eval_authority`
- Public API / OpenAPI: unchanged by T01.
- Production telemetry / CLI enablement: `NOT_DEPLOYED`.

## Mandatory evidence matrix

| Gate               | Required evidence                                                   | Current status      |
| ------------------ | ------------------------------------------------------------------- | ------------------- |
| Scope              | internal CLI/application boundary; no public API/M5/M6 bypass       | T01 local candidate |
| Authority          | PostgreSQL + accepted services remain source of truth               | pending T02–T05     |
| Operator safety    | actor/reason/expected state and explicit environment                | pending T02–T06     |
| Redaction          | no Prompt, key, URL, bytes, payload, path, secret or user data      | pending T02–T06     |
| Cost               | actual/estimated/unavailable distinction and reproducible aggregate | pending T04–T06     |
| Observability      | fixed allowlist, correlation, no collector overclaim                | pending T04–T06     |
| Recovery           | duplicate, stale, cancel/crash/concurrency evidence                 | pending T05–T06     |
| Contracts          | OpenAPI/generated TypeScript unchanged                              | pending T06–T07     |
| CI                 | exact SHA, three jobs, eight readable artifacts                     | pending T07         |
| Independent review | security/privacy/license and final review                           | pending T08         |

## T01 local candidate

- ADR-051 establishes a CLI-only, application-service-only internal control plane.
- The proposal intentionally has no schema, runtime dependency, model artifact, public API, Provider call, source asset,
  private input or QuestionBank release/revoke behavior.
- P2-M5 CC04-A execution remains `CLOSED_PENDING_SEPARATE_DECISION_AUTHORITY`; P2-M6 remains closed. The M7 plan
  may not alter either state.
- The next required evidence is formatting/invariant validation followed by a normal candidate commit, non-force push,
  same-SHA CI and artifact review. Until then, no M7 task is accepted and no CLI is implemented.
- Scoped Prettier check passed for all five T01-owned documents, and `git diff --check` passed. The full workspace
  format check still reports the pre-existing user-modified `AGENTS.md` and `MODEL_ROUTING_POLICY.md`; neither file
  was formatted, staged or adopted by this task. No public route or dependency-manifest diff was found.

`P2_M7_T01: READY_FOR_TRACKED_EVIDENCE`

`P2_M7_GATE: NOT_EVALUATED`

`P2_M7_STATE: COMMITTED`
