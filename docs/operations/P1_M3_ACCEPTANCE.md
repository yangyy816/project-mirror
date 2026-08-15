# P1-M3 Acceptance Record

## Gate

- Milestone: `P1-M3 — Purpose Consent, Authorization and Private Upload Control Plane`
- Candidate SHA: `26fe43213519cebd4eda157b46035cc0beb43cc5`
- Candidate run: [31897237022](https://github.com/yangyy816/project-mirror/actions/runs/31897237022)
- Principal decision: `PASS`
- Freeze state: `PASS — closure CI pending`

T01–T07 and all mandatory M3 evidence are accepted. The Milestone remains unfrozen until this acceptance record's own commit completes the same full remote Gate.

## Accepted scope

- T01: ADR-018 and the execution protocol freeze purpose Consent, owner-bound quarantine, short-lived one-time upload grants and the M4 promotion boundary.
- T02: forward-only `0003_upload_control` adds exact append-only Consent evidence, UploadIntent, append-only events, ownership constraints and bounded declarations.
- T03: the storage Adapter exposes private PUT grants, metadata inspection and idempotent quarantine delete; Local ingress is write-only, loopback-only and nonproduction.
- T04: purpose Consent application services implement exact current-state derivation, active-user grant, owner-bound withdrawal, HMAC idempotency and withdrawal tombstones.
- T05: UploadIntent application services implement owner-bound create/get/complete/cancel, one grant per intent, rate/quota admission, metadata matching, late-upload tombstones and cleanup recovery.
- T06: seven `/api/v1` Consent/UploadIntent endpoints are wired to application services and generated TypeScript contracts; URL/headers appear only in the create response.
- T07: migration, PostgreSQL, Redis/Celery, browser, supply-chain, Gitleaks and Docker evidence is independently assembled on one candidate SHA.

No Original Asset, image decode, EXIF read, face/landmark/AI operation, real COS, real user image, payment or public registration was added.

## Local authoritative evidence

| Area           | Evidence                                                                                                   | Result                            |
| -------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------- |
| Python         | Ruff, strict mypy, API + Worker suites                                                                     | `145 passed`, zero mandatory skip |
| PostgreSQL     | Fresh `base → 0001 → 0002 → 0003 → base → 0003`; `alembic check`                                           | PASS, no drift                    |
| Redis/Celery   | Linux worker round trip and inspect ping                                                                   | PASS, pong                        |
| Consent/Upload | concurrency, idempotency, ownership, withdrawal, late upload, metadata, expiry, quota and cleanup recovery | PASS                              |
| Contract       | FastAPI OpenAPI export, generated TypeScript, equality/drift/typecheck/Vitest                              | PASS, zero drift                  |
| TypeScript/Web | format, ESLint, strict typecheck, `52` unit tests and Next production build                                | PASS                              |
| Browser        | real Playwright browser regression                                                                         | `3 passed`                        |
| Containers     | all images rebuilt; five services healthy; API ready/Web `200`; Worker ping; Alembic check                 | PASS                              |
| Supply chain   | `pip-audit --local`, `pnpm audit --audit-level high`                                                       | no known vulnerabilities          |
| Secret scan    | Gitleaks 8.28.0 over exact Git-index snapshots                                                             | no leaks found                    |

Only synthetic non-face byte fixtures and deterministic Providers were used. No real phone, age credential, image, cloud credential or external model call entered the tests.

## Remote evidence

Candidate run `31897237022` is bound to SHA `26fe43213519cebd4eda157b46035cc0beb43cc5` and completed successfully.

| Job                       | Job ID        | Mandatory evidence                                                                                                                                          |
| ------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quality-and-integration` | `95042298470` | Python quality/tests, PostgreSQL lifecycle, Redis/Celery, TypeScript build, Chromium/browser integration, contract drift, dependency/license audit and SBOM |
| `secret-scan`             | `95042298472` | Gitleaks action                                                                                                                                             |
| `docker-validation`       | `95042298454` | Compose validation/build/start, health behavior, Worker ping and Alembic check                                                                              |

Artifacts are present, downloadable and unexpired:

- `project-audit-evidence` (`9250163269`): Celery log, Python/Node licenses and Python SBOM.
- `project-docker-evidence` (`9250141782`): Compose log.
- `gitleaks-results.sarif` (`9250119796`): Gitleaks SARIF evidence.

The historical workflow display name `phase-0-gates` and Node 20 action-runtime deprecation annotation are nonblocking maintenance debt; the actual current jobs and mandatory steps above executed.

## Material repairs closed

- R01: removed an immutable Consent history backfill from `0003`.
- R02: cleared cached settings so migration tests target only the explicit isolated database.
- R03: isolated Consent and QuestionBank test roots across repeated full-suite runs.
- R04: compared legacy PostgreSQL `JSON` scope through explicit `JSONB` equality without changing schema or weakening exact matching.
- R05: allowed browser private-upload `PUT` and required integrity/authorization CORS headers.
- R06: supplied the new nonzero purpose-policy digest to the Worker production fail-closed fixture.

## Deferred production gates

- Real COS remains a fail-closed candidate boundary; Local ingress remains nonproduction only.
- Real facial-data intake remains blocked by legal, privacy, Provider and security review.
- M4 image decoding, MIME/magic verification, pixel limits, re-encoding, EXIF removal and Original promotion are not claimed by M3.
- Node action runtime warnings and historical workflow display naming remain nonblocking maintenance debt.

`P1-M3_GATE: PASS`

`P1-M3_STATE: PASS_PENDING_CLOSURE`
