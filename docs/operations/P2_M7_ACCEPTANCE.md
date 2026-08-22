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
- Candidate `6ecacf45792e7b93c666eec05b4d19ba7c05a3f8` completed exact-SHA run `32587937578`, attempt 1, with
  `quality-and-integration`, `secret-scan` and `docker-validation` all successful. The quality job completed
  PostgreSQL lifecycle, Python, retained Phase 1/P2-M1/M2/M3 evidence, TypeScript, Playwright dependency/download,
  Browser Integration, contract drift and dependency/license stages successfully.
- Eight unexpired service-side artifacts are present and metadata-bound to the exact candidate SHA:
  `gitleaks-results.sarif`, `project-docker-evidence`, `playwright-install-evidence`, `phase1-ci-evidence`,
  `p2-m1-ci-evidence`, `p2-m2-ci-evidence`, `p2-m3-ci-evidence` and `project-audit-evidence`. Current-session
  archive download returned HTTP 401, so artifact **content** is `NOT_VERIFIED_AUTH_REQUIRED`; metadata is not
  treated as a replacement for content inspection.
- T01 remains unaccepted and M7 remains `COMMITTED` until a read-only authenticated artifact inspection proves the
  archived contents are readable, exact-SHA bound and free of contradictory mandatory evidence.

`P2_M7_T01_REMOTE_CI: PASS_AT_6ECACF4_RUN_32587937578_ATTEMPT_1`

`P2_M7_T01_ARTIFACT_METADATA: PASS_8_EXACT_SHA_UNEXPIRED`

`P2_M7_T01_ARTIFACT_CONTENT: NOT_VERIFIED_AUTH_REQUIRED`

`P2_M7_T01: PENDING_ARTIFACT_CONTENT_INSPECTION`

`P2_M7_GATE: NOT_EVALUATED`

`P2_M7_STATE: COMMITTED`
