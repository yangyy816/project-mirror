# P1-M5 Acceptance Record

## Gate

- Milestone: `P1-M5 — Asset Access, User Data Rights and Lifecycle UI`
- Candidate SHA: `6d46b4be2368870252905b472915e5a5b1f7cd1a`
- Candidate run: [31921199397](https://github.com/yangyy816/project-mirror/actions/runs/31921199397)
- Principal decision: `PASS`
- Acceptance SHA: `ccbd136a42e7d3a702acd2050265ba0e8a211d3e`
- Closure run: [31921591091](https://github.com/yangyy816/project-mirror/actions/runs/31921591091)
- Freeze state: `FROZEN`

T01–T08 and all mandatory M5 evidence are accepted. The acceptance record's own commit completed the same full remote Gate, so the Milestone is frozen.

## Accepted scope

- T01: ADR-020 and the execution protocol freeze owner-bound private access, lifecycle authority, export contents, account deletion propagation, recovery and the P1-M6 boundary.
- T02: forward-only `0005_data_rights_lifecycle` adds authoritative Asset deletion, data export, account deletion and physical object deletion evidence.
- T03: exact-key private download grants, one-time Local redemption and owner-bound application services prevent public, stable or cross-user Asset access.
- T04: dependency-aware tombstones, reference-only tasks, Celery/Local execution, retry/reconciliation and per-target evidence implement truthful asynchronous Asset deletion.
- T05: deterministic private ZIP export and account deletion coordination implement session revocation, Consent/upload/ingestion/Asset/export propagation, retention cleanup and phone-hash de-association.
- T06: nine owner-bound `/api/v1` operations expose only stable lifecycle state through FastAPI OpenAPI and generated TypeScript contracts.
- T07: `/account` provides accessible Asset access/delete, data export and guarded account deletion controls without persisting tokens or download grants in browser storage.
- T08: migration, PostgreSQL/Redis/Celery, private-access/security, browser, contract, supply-chain, Gitleaks and Docker evidence is independently assembled on one candidate SHA.

No real face image, COS/AI/payment call, face analysis, Profile/Questionnaire/Edit data, public object, public registration or P1-M6 implementation was added.

## Local authoritative evidence

| Area            | Evidence                                                                                                          | Result                       |
| --------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| Python          | Ruff over `131` files, strict mypy over `86` source files, complete API suite                                     | PASS, zero mandatory skip    |
| PostgreSQL      | Isolated `base → 0007 → base → 0007`; `alembic check`; lifecycle/invariant and concurrency tests                  | PASS, no drift               |
| Redis/Celery    | Worker suite, real Redis/Celery ping, dispatch/retry/reconcile and deletion/export tasks                          | `18 passed`; round trip PASS |
| Asset access    | owner SQL predicates, expiry/replay, deleted/frozen actor, path/symlink and post-tombstone grant invalidation     | PASS                         |
| Deletion/export | dependency DAG, quarantine grant barrier, deterministic archive isolation, expiry, propagation and recovery races | PASS                         |
| Contract        | FastAPI OpenAPI export, generated TypeScript, equality/drift/typecheck/Vitest                                     | PASS, zero drift             |
| TypeScript/Web  | `pnpm check`, `54` Web unit tests and Next production build                                                       | PASS                         |
| Browser         | real Microsoft Edge Playwright data-rights flows                                                                  | `5 passed`                   |
| Containers      | rebuilt Web image; API/Web/Worker/PostgreSQL/Redis healthy; `/account` HTTP `200`; Celery ping                    | PASS                         |
| Supply chain    | `pip-audit --local`, `pnpm audit --audit-level high`                                                              | no known vulnerabilities     |
| Secret scan     | Gitleaks 8.28.0 over exact Git index and complete 56-commit history                                               | no leaks                     |

Only generated synthetic/non-face fixtures and deterministic Providers were used. No real phone, age credential, image, cloud credential or external model call entered the tests.

## Remote evidence

Candidate run `31921199397` is bound to SHA `6d46b4be2368870252905b472915e5a5b1f7cd1a` and completed successfully.

| Job                       | Job ID        | Mandatory evidence                                                                                                                                          |
| ------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quality-and-integration` | `95101227822` | Python quality/tests, PostgreSQL lifecycle, Redis/Celery, TypeScript build, Chromium/browser integration, contract drift, dependency/license audit and SBOM |
| `secret-scan`             | `95101227804` | complete-history Gitleaks action with default rules preserved                                                                                               |
| `docker-validation`       | `95101227825` | Compose validation/build/start, health behavior, complete Worker suite and Alembic check                                                                    |

Artifacts were downloaded, readable and unexpired on 2026-08-16:

- `project-audit-evidence` (`9256440139`): Celery log, Python/Node licenses and Python SBOM.
- `project-docker-evidence` (`9256419054`): Compose log.
- `gitleaks-results.sarif` (`9256396276`): readable SARIF with zero results.

Acceptance closure run `31921591091` is bound to SHA `ccbd136a42e7d3a702acd2050265ba0e8a211d3e` and repeated the complete Gate successfully:

- `quality-and-integration` (`95102180035`)
- `secret-scan` (`95102179949`)
- `docker-validation` (`95102179935`)

Closure artifacts were downloaded, readable and unexpired:

- `project-audit-evidence` (`9256539346`)
- `project-docker-evidence` (`9256524297`)
- `gitleaks-results.sarif` (`9256505465`), with zero SARIF results.

The conditional browser-failure artifact step was correctly skipped because browser integration passed. The historical workflow display name `phase-0-gates` and Node action-runtime deprecation annotations are nonblocking maintenance debt; the current jobs and mandatory steps above executed.

## Material repairs and change controls closed

- R01: added authority- and owner-bound deletion evidence for root and derived Assets, with PostgreSQL dependency constraints.
- R02 / CC-P1-M5-01: added quarantine-object deletion evidence and required the pre-existing upload-grant expiry barrier before account-deletion completion.
- R03: serialized export publication and account deletion on the User lock with a consistent lock order, closing orphan-publication and deadlock races.
- CC-P1-M5-02: allowed only the narrow current-deletion-status read with an unexpired JWT from a family revoked specifically for account deletion; refresh and all ordinary endpoints remain denied.

## Deferred production gates

- Real COS, real facial-data intake and real Provider traffic remain fail closed pending legal, privacy, Provider and security review.
- P1-M6 integration/freeze work is not claimed by M5 and must not begin until M5 is frozen.
- Profile, questionnaire, editing, AI analysis, payment and public registration remain out of scope.
- Node action-runtime warnings and the historical workflow display name remain nonblocking maintenance debt.

`P1-M5_GATE: PASS`

`P1-M5_STATE: FROZEN`
