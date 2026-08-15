# P1-M4 Acceptance Record

## Gate

- Milestone: `P1-M4 — Safe Image Ingestion and Asset Lifecycle`
- Candidate SHA: `b28f0e6b547df94ded12ce6323efb06ae269a11e`
- Candidate run: [31903655766](https://github.com/yangyy816/project-mirror/actions/runs/31903655766)
- Principal decision: `PASS`
- Acceptance SHA: `PENDING_CLOSURE_COMMIT`
- Closure run: `PENDING_REMOTE_CI`
- Freeze state: `PASS_AWAITING_CLOSURE`

T01–T08 and all mandatory M4 evidence are accepted. The Milestone becomes `FROZEN` only after this acceptance record's own commit completes the same full remote Gate.

## Accepted scope

- T01: ADR-019 and the execution protocol freeze explicit ingestion Jobs, canonical re-encoding, promotion, recovery, cleanup and the M5 boundary.
- T02: `pillow==12.3.0` passed the independent decoder supply-chain Gate for strict JPEG/PNG/WebP decoding and canonical JPEG encoding only.
- T03: forward-only `0004_safe_image_ingestion` adds authoritative Job/attempt/final evidence, owner lineage, retention and immutable Original constraints.
- T04: provider-neutral bounded storage reads/writes and `image-sanitizer-v1` implement magic/MIME/decode/size/pixel/frame checks, EXIF orientation, metadata removal and deterministic re-encoding.
- T05: ingestion application services implement owner/Consent/TTL rechecks, one Job/Original, lease/reclaim, stable rejection, idempotent promotion and object/database fault recovery.
- T06: reference-only task messages, LocalTaskRunner, Celery queues, retry/recovery reconcilers and quarantine/orphan cleanup implement at-least-once-safe execution.
- T07: ingestion Job create/status endpoints and OpenAPI-generated TypeScript contracts expose only owner-bound stable state.
- T08: migration, PostgreSQL/Redis/Celery, sanitizer/security, browser, supply-chain, Gitleaks and Docker evidence is independently assembled on one candidate SHA.

No real face image, COS/AI call, face detection, landmark, quality score, public object, Asset download/delete UI, payment or public registration was added.

## Local authoritative evidence

| Area              | Evidence                                                                                                   | Result                               |
| ----------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| Python            | Ruff, strict mypy, complete API + Worker suites                                                            | `186 passed`, zero mandatory skip    |
| PostgreSQL        | Fresh `0001 → 0002 → 0003 → 0004`; `0004 → 0003 → 0004`; `alembic check`                                   | PASS, no drift                       |
| Redis/Celery      | Linux queue registration, dispatch/round trip, recovery and cleanup                                        | PASS; Worker suite `14 passed`       |
| Sanitizer/storage | JPEG/PNG/WebP, malformed/polyglot/bomb/animation, metadata, repeatability, containment and conflict matrix | PASS                                 |
| Ingestion domain  | ownership, Consent/TTL races, idempotency, lease/reclaim, one Original, retries and cleanup faults         | PASS                                 |
| Contract          | FastAPI OpenAPI export, generated TypeScript, equality/drift/typecheck/Vitest                              | PASS, zero drift                     |
| TypeScript/Web    | format, ESLint, strict typecheck, `52` unit tests and Next production build                                | PASS                                 |
| Browser           | real Microsoft Edge Playwright regression                                                                  | `3 passed`                           |
| Containers        | all images rebuilt; five services healthy; API live/ready and Web `200`; Worker queues/tasks healthy       | PASS                                 |
| Supply chain      | `pip-audit --local`, `pnpm audit --audit-level high`                                                       | no known vulnerabilities             |
| Secret scan       | Gitleaks 8.28.0 over 44 commits and exact Git-index snapshot; negative control                             | no leaks; unrelated control rejected |

Only generated synthetic/non-face fixtures and deterministic Providers were used. No real phone, age credential, image, cloud credential or external model call entered the tests.

## Remote evidence

Candidate run `31903655766` is bound to SHA `b28f0e6b547df94ded12ce6323efb06ae269a11e` and completed successfully.

| Job                       | Job ID        | Mandatory evidence                                                                                                                                          |
| ------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quality-and-integration` | `95058107592` | Python quality/tests, PostgreSQL lifecycle, Redis/Celery, TypeScript build, Chromium/browser integration, contract drift, dependency/license audit and SBOM |
| `secret-scan`             | `95058107550` | complete-history Gitleaks action with default rules preserved                                                                                               |
| `docker-validation`       | `95058107554` | Compose validation/build/start, health behavior, complete Worker suite and Alembic check                                                                    |

Artifacts are present, downloadable and unexpired:

- `project-audit-evidence` (`9251803909`): Celery log, Python/Node licenses and Python SBOM.
- `project-docker-evidence` (`9251783200`): Compose log.
- `gitleaks-results.sarif` (`9251759661`): Gitleaks SARIF evidence.

The historical workflow display name `phase-0-gates` and Node action-runtime deprecation annotations are nonblocking maintenance debt; the current jobs and mandatory steps above executed.

## Material repairs closed

- R01: enforced promoted Asset classification and immutable metadata.
- R02: enforced commit-time Job/current-attempt consistency.
- R03: classified sanitized-object create conflicts through the provider-neutral boundary.
- R04: made repeated claim of pre-claim terminal cancellation idempotent.
- R05: moved `ingestion-task-v1` to the shared domain contract and removed API-to-Worker coupling.
- R06: copied authoritative OpenAPI into API/Worker images, exercised all Celery queues and complete Worker tests in CI, and closed formatting drift.
- R07: replaced the current synthetic idempotency fixture that resembled a credential.
- R08: preserved default Gitleaks rules while allowing only the exact historical commit/path/match false positive; an unrelated negative control remains blocked.

## Deferred production gates

- Real COS and real facial-data intake remain fail closed pending legal, privacy, Provider and security review.
- M5 Asset download, deletion, export and lifecycle UI are not claimed by M4.
- Face detection, landmark, quality analysis, AI editing and real-user image processing remain out of scope.
- Node action runtime warnings and the historical workflow display name remain nonblocking maintenance debt.

`P1-M4_GATE: PASS`

`P1-M4_STATE: PASS_AWAITING_CLOSURE`
