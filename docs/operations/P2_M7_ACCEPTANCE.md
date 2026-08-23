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
- Principal review found that the initial T01 protocol abbreviated the required per-task bounded contracts. `P2-M7-R01`
  is a docs-only completeness repair: it must retain the same architecture and closed boundaries, then receive its own
  same-SHA CI/artifact evidence before T01 is reconsidered.

`P2_M7_T01_REMOTE_CI: PASS_AT_6ECACF4_RUN_32587937578_ATTEMPT_1`

`P2_M7_T01_ARTIFACT_METADATA: PASS_8_EXACT_SHA_UNEXPIRED`

`P2_M7_T01_ARTIFACT_CONTENT: NOT_VERIFIED_AUTH_REQUIRED`

`P2_M7_T01: PENDING_P2_M7_R01_AND_ARTIFACT_CONTENT_INSPECTION`

`P2_M7_R01: READY_FOR_TRACKED_EVIDENCE`

`P2_M7_GATE: NOT_EVALUATED`

`P2_M7_STATE: COMMITTED`

## P2-M7-R02 / T01 evidence-state reconciliation

- `P2-M7-R02` is a documentation-only repair for the stale evidence-state labels above. It does not change
  ADR-051, a schema, public API, dependency, model, Provider, production capability, M5 research authority or M6
  release/revoke authority.
- Repair candidate `78c6370fa6b73491bf3ad0c705f6cf284982e3ee` completed GitHub Actions run `32588923032`, attempt 1,
  with `quality-and-integration`, `secret-scan` and `docker-validation` successful on that exact SHA.
- All eight expected artifacts were unexpired and service-side SHA-256 bound to that run. Principal performed an
  authenticated, temporary content inspection of all eight archives: 11 files, candidate-SHA bindings in the retained
  evidence JSON, zero credential-pattern or image files, and zero Gitleaks SARIF results. Temporary download material
  was deleted after inspection.
- The only skipped quality-job upload step is `playwright-failure-evidence`, guarded by `if: failure()`; Browser
  Integration passed, so this conditional failure-only artifact is not a mandatory skip. The mandatory Playwright
  install evidence was uploaded and content-inspected.
- Independent security/privacy/data/supply-chain review of `6ecacf4^..78c6370` passed. The reviewer found no scope
  bypass and did not reinterpret Principal's artifact-content inspection as independently performed evidence.
- Principal has completed the evidence review, but this R02 candidate must receive its own same-SHA CI before a
  separate T01 acceptance checkpoint can open T02. This is not M7 Gate evidence and does not open M5 fresh-study
  execution, M6 release/revoke, production CLI enablement or a public interface.

`P2_M7_R02: READY_FOR_TRACKED_EVIDENCE`

`P2_M7_T01: PENDING_P2_M7_R02_TRACKED_EVIDENCE`

`P2_M7_R01: PASS_AT_78C6370_RUN_32588923032_ATTEMPT_1`

`P2_M7_STATE: COMMITTED`

`P2_M7_NEXT_TASK: P2_M7_R02_TRACKED_EVIDENCE`

## P2-M7-R02 tracked acceptance / T01 closure

- Candidate `aead7961d9ab9a062a88e8177f785dc1730dfc5f` completed GitHub Actions run `32589829490`, attempt 1, with
  `quality-and-integration`, `secret-scan` and `docker-validation` successful on that exact SHA.
- All eight expected artifacts were unexpired, service-side SHA-256 bound and authenticated/content-inspected. The
  inspection found 11 files, candidate-SHA bindings in retained evidence JSON, zero credential-pattern or image files,
  and zero Gitleaks SARIF results; its temporary download root was deleted.
- Principal accepts T01, R01 and R02. M7 enters `EXECUTION_READY`; T02 is the sole authorized next implementation task.
  This remains governance-only evidence: M7 Gate is not evaluated, production CLI remains `NOT_DEPLOYED`, M5 fresh
  study remains closed and M6 release/revoke remains closed.

`P2_M7_R02: PASS_AT_AEAD796_RUN_32589829490_ATTEMPT_1`

`P2_M7_T01: PASS_AT_AEAD796_RUN_32589829490_ATTEMPT_1`

`P2_M7_STATE: EXECUTION_READY`

`P2_M7_NEXT_TASK: T02_AUTHORIZED`

## P2-M7-R03 to R07 / T02 Principal acceptance

- The linear T02 repair chain `17fdecb` -> `f127cb8` -> `4e13c86` -> `fa6f7b2` ->
  `5be883049d8eda2e4f32a6820e1380aa8a189397` is accepted only through its final R07
  candidate. R03-R06 remain historical repair evidence; their individual same-SHA success does not replace the R07
  evidence.
- Candidate `5be883049d8eda2e4f32a6820e1380aa8a189397` completed GitHub Actions run `32595984817`, attempt 1, with
  `quality-and-integration`, `secret-scan` and `docker-validation` successful on that exact SHA. The quality job
  completed Ruff, strict mypy, PostgreSQL migration lifecycle, Linux Celery, 759 Python passes with one existing
  non-mandatory skip, retained Phase 1/P2-M1/P2-M2/P2-M3 evidence, TypeScript, Playwright, contract drift,
  dependency/license audit and SBOM generation.
- Principal content-inspected all eight unexpired artifacts in a unique system temporary directory and removed it
  afterward. All artifact metadata and retained JSON evidence bind the exact candidate SHA and migration head
  `0014_m5_eval_authority`; SARIF has zero results, and the artifact content scan found zero image files and zero
  credential-pattern matches.
- Independent security/privacy/data/supply-chain review and independent final review both passed for the exact R07
  object and same-SHA evidence. They confirmed that backend result reconstruction does not dispatch forged subclasses,
  projection status and currency are closed, numeric values are exact non-negative integers, outcome is typed, malformed
  objects fail closed, and unsafe values are never echoed.
- Principal reviewed the actual R07 diff, local targeted/static evidence, same-SHA CI/artifacts and both independent
  reviews. Principal accepts `P2-M7-R03` through `P2-M7-R07` and `P2-M7-T02`. This does not accept T03 or any M7
  milestone Gate, enable production, alter M5, or open M6.

`P2_M7_R03: PASS_AT_5BE8830_RUN_32595984817_ATTEMPT_1`

`P2_M7_R04: PASS_AT_5BE8830_RUN_32595984817_ATTEMPT_1`

`P2_M7_R05: PASS_AT_5BE8830_RUN_32595984817_ATTEMPT_1`

`P2_M7_R06: PASS_AT_5BE8830_RUN_32595984817_ATTEMPT_1`

`P2_M7_R07: PASS_AT_5BE8830_RUN_32595984817_ATTEMPT_1`

`P2_M7_T02: PASS_AT_5BE8830_RUN_32595984817_ATTEMPT_1`

`P2_M7_T03: EXECUTION_READY`

`P2_M7_STATE: EXECUTING`

`P2_M7_GATE: NOT_EVALUATED`

`P2_M7_NEXT_TASK: T03_AUTHORIZED`

## P2-M7-T03 internal CLI adapter acceptance

- Candidate `5bca39236e2a77c03ea3c8dbeb81e0a9eb6a26a0` completed GitHub Actions run `32617351123`, attempt 1, with
  `quality-and-integration`, `secret-scan` and `docker-validation` successful on that exact SHA. The quality job
  completed Ruff, strict mypy, PostgreSQL migration lifecycle, Linux Celery, Python, retained Phase 1/P2-M1/P2-M2/P2-M3
  evidence, TypeScript, Playwright install/download, Browser Integration, contract drift, dependency/license audit and
  SBOM generation.
- The candidate adds only the `mirror-dataset` package entrypoint, a thin first-party CLI adapter and deterministic
  CLI tests. It has no SQL, HTTP, storage, Provider, task-runner, migration, public API/OpenAPI, dependency, model,
  M5 research or M6 release/revoke behavior. Missing backends return a typed unavailable result; production is rejected
  before dispatch; malformed or unknown arguments never echo their supplied value; rendered output is canonicalized to
  the T02 allowlist.
- Principal locally verified scoped T03 tests plus the full Python regression using a task-owned temporary root,
  then deleted that root. The local result was `602 passed`, `162 skipped` and one existing dependency deprecation
  warning; Ruff, strict mypy, contract drift and source scans were also successful. The normal Windows pytest temp root
  remains ACL-blocked and was not modified.
- Principal content-inspected all eight unexpired artifacts in a temporary directory and deleted it afterward. Every
  artifact binds the exact candidate SHA and migration head `0014_m5_eval_authority`; SARIF has zero results, and the
  content scan found zero image files, signed/private-path matches or credential-assignment matches.
- Principal reviewed the actual candidate diff and evidence. `P2-M7-T03` is accepted. This accepts neither the M7
  milestone Gate nor any T04–T08 behavior, enables no production operation and does not alter M5 or open M6.

`P2_M7_T03: PASS_AT_5BCA392_RUN_32617351123_ATTEMPT_1`

`P2_M7_T04: EXECUTION_READY`

`P2_M7_STATE: EXECUTING`

`P2_M7_GATE: NOT_EVALUATED`

`P2_M7_NEXT_TASK: T04_AUTHORIZED`

## P2-M7-R08 to R11 / T04 Principal acceptance

- The linear T04/CI-evidence repair chain `67d005e` -> `2110f33` -> `b6bbf0f` -> `dcb831a` ->
  `8fdd24341a21899fd67393baa4b67e0df769181c` is accepted only through the final R11 candidate. R08–R10
  remain historical repair evidence; their individual CI outcomes do not replace the exact R11 evidence.
- Candidate `8fdd24341a21899fd67393baa4b67e0df769181c` completed GitHub Actions run `32622260268`, attempt 1, with
  `quality-and-integration`, `secret-scan` and `docker-validation` successful on that exact SHA. The quality job
  completed Ruff, strict mypy, PostgreSQL migration lifecycle, Linux Celery, 774 Python passes with one existing
  non-mandatory skip, retained Phase 1/P2-M1/P2-M2/P2-M3 evidence, TypeScript, Playwright install/download,
  Browser Integration, contract drift, dependency/license audit and SBOM generation.
- Principal content-inspected all eight unexpired artifacts in a task-created temporary directory and deleted it
  afterward. All eight are metadata-bound to the exact candidate SHA; the 11 archive members have no
  runner/workspace/private path, image, credential, signed URL, Prompt, object-key or Provider-payload finding.
  Four retained evidence JSON files bind the SHA and migration head `0014_m5_eval_authority`; the fixed-name
  `gitleaks-results.sarif` member has zero results.
- Independent security/privacy/data/supply-chain review and independent Sol final review both passed. They confirmed
  that R11 retains the Gitleaks scan while replacing its artifact with a fixed staged member, malformed JSON/JSONL
  sanitizer errors never echo raw input, and the T04 cost/operational-event read models remain payload-free,
  PostgreSQL-authoritative and within the frozen M7 boundary.
- Principal reviewed the complete T04/R08–R11 diff, local targeted/static evidence, same-SHA CI/artifacts and both
  independent reviews. Principal accepts `P2-M7-R08` through `P2-M7-R11` and `P2-M7-T04`. This accepts neither the
  M7 milestone Gate nor T06–T08 behavior, enables no production operation, does not alter M5 and does not open M6.

`P2_M7_R08: PASS_THROUGH_FINAL_R11_8FDD243_RUN_32622260268_ATTEMPT_1`

`P2_M7_R09: PASS_THROUGH_FINAL_R11_8FDD243_RUN_32622260268_ATTEMPT_1`

`P2_M7_R10: PASS_THROUGH_FINAL_R11_8FDD243_RUN_32622260268_ATTEMPT_1`

`P2_M7_R11: PASS_AT_8FDD243_RUN_32622260268_ATTEMPT_1`

`P2_M7_T04: PASS_AT_8FDD243_RUN_32622260268_ATTEMPT_1`

`P2_M7_T05: EXECUTION_READY_PENDING_T04_ACCEPTANCE_CLOSURE_CI`

`P2_M7_STATE: EXECUTING`

`P2_M7_GATE: NOT_EVALUATED`

`P2_M7_NEXT_TASK: T04_ACCEPTANCE_CLOSURE_CI`

## P2-M7-T04 acceptance closure CI confirmation

- The acceptance closure commit `2bf0f2e3795d7497f0e28b630a227a5d09ba735f` completed GitHub Actions run
  `32623166435`, attempt 1, with `quality-and-integration`, `secret-scan` and `docker-validation` successful on
  that exact SHA. The closure job again completed PostgreSQL lifecycle, Linux Celery, Python/TypeScript/Browser
  regressions, contract drift, dependency/license audits and SBOM generation.
- Principal authenticated and content-inspected the closure run's eight unexpired artifacts, then deleted the
  task-created temporary directory. The 11 archive members are path-free and payload-free; four retained evidence
  JSON files bind the closure SHA and migration head `0014_m5_eval_authority`, and Gitleaks SARIF has zero results.
- The T04 acceptance is now effective. `P2-M7-T05` is the only next implementation task; it remains subject to the
  frozen recovery/concurrency scope and its own bounded-task, CI and review evidence. M7 Gate remains unevaluated;
  no production operation is enabled and M5/M6 remain closed.

`P2_M7_T04_ACCEPTANCE_CLOSURE: PASS_AT_2BF0F2E_RUN_32623166435_ATTEMPT_1`

`P2_M7_T05: EXECUTION_READY`

`P2_M7_STATE: EXECUTING`

`P2_M7_GATE: NOT_EVALUATED`

`P2_M7_NEXT_TASK: T05_AUTHORIZED`
