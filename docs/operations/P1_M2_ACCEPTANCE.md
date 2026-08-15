# P1-M2 Acceptance Record

## Gate

- Milestone: `P1-M2 — Web Authentication and Onboarding`
- Candidate SHA: `f4dd6f0a58635e0d8505a5fa0ce0c2ed366982aa`
- Candidate run: [31892402898](https://github.com/yangyy816/project-mirror/actions/runs/31892402898)
- Principal decision: `PASS`
- Freeze state: `PASS` pending acceptance-closure CI

`PASS` means T01–T06 and all mandatory M2 evidence have been accepted. The Milestone becomes
`FROZEN` only after this acceptance record's closure commit completes the same full remote Gate.

## Accepted scope

- T01: ADR-017 and the M2 execution protocol freeze browser session, CSRF, age popup, policy manifest and protected-route semantics.
- T02: generated-client browser adapter, in-memory access session, single-flight refresh and production fail-closed config are implemented.
- T03: accessible phone/invite/OTP UI uses non-enumerating language, prevents duplicate submit and clears sensitive form state.
- T04: strict external-age popup bridge and exact approved policy acceptance are implemented without a real Provider.
- T05: `/join` and `/account` provide bootstrap recovery, pending/active gating, protected-content suppression and confirmed logout semantics.
- T06: deterministic Fake API/age bridge and real production-build browser acceptance cover the complete M2 vertical flow.

No M1 API/domain change, upload, facial processing, real Provider, payment, analytics or public registration was added.

## Local authoritative evidence

| Area             | Evidence                                                                      | Result                                 |
| ---------------- | ----------------------------------------------------------------------------- | -------------------------------------- |
| Browser          | Microsoft Edge + Next standalone, three end-to-end scenarios                  | `3 passed`                             |
| Web unit         | auth, onboarding, session, config and API suites                              | `52 passed`                            |
| Browser privacy  | Web Storage, URLs, protected static HTML and transient credential assertions  | PASS                                   |
| TypeScript       | format, ESLint, strict typecheck, Vitest, contract check and production build | PASS                                   |
| Python           | Ruff, strict mypy and host tests                                              | `82 passed`; expected infra skips only |
| PostgreSQL/Redis | API container with explicit infrastructure                                    | `97 passed`, zero infra skip           |
| Worker           | Celery/Redis suite and inspect ping                                           | `5 passed`; pong                       |
| Migration        | isolated `base → 0001 → 0002 → 0001 → 0002`; `alembic check`                  | PASS, no drift                         |
| Contract         | FastAPI OpenAPI regeneration and generated TypeScript diff                    | zero drift                             |
| Supply chain     | Python/Node audit and Playwright adoption review                              | no known vulnerabilities               |
| Containers       | all images, five-service health, API ready and Web smoke                      | PASS                                   |
| Secret scan      | Gitleaks 8.28.0 over exact candidate index snapshots                          | no leaks found                         |

The isolated migration database `mirror_m2_gate_20260815` was deleted after verification. Browser fixtures contain only synthetic markers and deterministic Fakes; no external Provider call, real phone, credential or face image was used.

## Remote evidence

Candidate run `31892402898` is bound to SHA `f4dd6f0a58635e0d8505a5fa0ce0c2ed366982aa` and completed successfully.

| Job                       | Job ID        | Mandatory evidence                                                                                                                                                   |
| ------------------------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quality-and-integration` | `95030535884` | Python quality/tests, PostgreSQL lifecycle, Redis/Celery, TypeScript build, Chromium install, browser integration, contract drift, dependency/license audit and SBOM |
| `secret-scan`             | `95030535839` | Gitleaks action                                                                                                                                                      |
| `docker-validation`       | `95030535934` | Compose validation/build/start, health behavior, Worker ping and Alembic check                                                                                       |

Artifacts are present, downloadable and unexpired:

- `project-audit-evidence` (`9248929443`): Celery log, Python/Node licenses and Python SBOM.
- `project-docker-evidence` (`9248909537`): Compose log.
- `gitleaks-results.sarif` (`9248887386`): one SARIF run, zero results.

The historical GitHub display name `phase-0-gates` and Node 20 action-runtime deprecation annotations are nonblocking workflow identity/runtime debt; the actual workflow jobs and mandatory steps above executed.

## Material repairs closed

- R01: corrected T04 test typing and an ambiguous duplicate text query.
- R02: logout network failure no longer claims server-side revocation; protected data is hidden and retry is explicit.
- R03: bootstrap without CSRF safely becomes anonymous/re-authentication instead of attempting an unsafe refresh.
- R04: separated Vitest unit collection from Playwright suites locally.
- R05: moved the E2E exclusion into `vitest.config.ts`, preventing Bash glob expansion from turning helper files into positional filters. Failed run `31891358894` classified this as deterministic CI test-command configuration.
- R06: assembled the pnpm `@swc/helpers/esm` runtime for Next standalone browser tests with cross-platform realpath handling. Failed run `31891997721` classified this as deterministic Linux standalone assembly.

## Deferred production gates

- Real SMS and age-assurance Providers remain unselected and production registration remains disabled.
- Facial-data consent/upload, real images, analytics, payment and public registration remain outside M2.
- Node action runtime warnings and historical workflow display naming remain nonblocking maintenance debt.

`P1-M2_GATE: PASS`

`P1-M2_STATE: PASS_PENDING_CLOSURE_CI`
