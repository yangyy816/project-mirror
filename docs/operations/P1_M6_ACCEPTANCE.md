# P1-M6 Acceptance Record

## Gate

- Milestone: `P1-M6 — Application Foundation Integration Gate`
- Candidate SHA: `ed24b3d856e22bc1d0779a9eace254200041fb81`
- Candidate run: [31924258547](https://github.com/yangyy816/project-mirror/actions/runs/31924258547)
- Principal decision: `PASS`
- Acceptance SHA: `cc926ceb49c7978cb7b57df778ec2f1c7f4cc878`
- Closure run: [31924651458](https://github.com/yangyy816/project-mirror/actions/runs/31924651458)
- Freeze state: `FROZEN`

T01–T05 and all mandatory candidate evidence are accepted. The acceptance record's
own commit repeated the complete remote Gate successfully, so P1-M6 and Phase 1 are
frozen without entering P2.

## Accepted scope

- T01 froze the Phase 1 integrated evidence matrix and kept P1-M6 limited to
  verification, observability, CI evidence and freeze work.
- T02 added one owner-bound synthetic/non-face vertical lifecycle and recovery drill
  across invited authentication, activation, Consent, quarantine, ingestion, private
  access, export, Asset deletion and account deletion.
- T03 added standard-library allowlisted operational events, route-template HTTP
  counts/latency, job dispatch correlation and a redaction/incident runbook without
  claiming a production telemetry backend.
- T04 added fail-closed `mirror.phase1.ci-evidence/v1`, binding the commit SHA, single
  Alembic head, OpenAPI digest and zero-skip vertical JUnit result.
- T05 assembled local and remote PostgreSQL/Redis/Celery, Python/TypeScript/browser,
  contract, supply-chain, Docker and Gitleaks evidence on one candidate SHA.

No migration, public product endpoint, third-party dependency, real phone, age
credential, face image, Provider traffic, deployment, payment, P2 implementation or
production enablement was added.

## Local authoritative evidence

| Area           | Evidence                                                                                 | Result                    |
| -------------- | ---------------------------------------------------------------------------------------- | ------------------------- |
| Python         | Ruff over `134` files; strict mypy over `87` source files; complete API/Worker suite     | PASS, zero mandatory skip |
| Vertical       | isolated PostgreSQL/Redis invite-to-deletion lifecycle with upload-grant expiry recovery | PASS                      |
| PostgreSQL     | isolated `base → 0007 → base → 0007`; `alembic check`                                    | PASS, no drift            |
| Redis/Celery   | dedicated broker DB and temporary Linux Celery Worker for complete suite                 | PASS                      |
| Observability  | fixed-field events, HTTP route-template and local grant-handle negative tests            | PASS                      |
| Evidence       | real JUnit + migration head + OpenAPI + full commit local generation and negative tests  | PASS, fail closed         |
| TypeScript/Web | full `pnpm check`, `54` Web tests and Next production build                              | PASS                      |
| Browser        | Playwright authentication/onboarding/data-rights flows                                   | `5 passed`                |
| Containers     | full image rebuild; five services healthy; API live/ready, Web 200, Celery ping          | PASS                      |
| Supply chain   | `pip-audit --local`, `pnpm audit --audit-level high`                                     | no known vulnerabilities  |
| Secret scan    | verified Gitleaks 8.28.0 over 59-commit history and exact Git index                      | no leaks                  |

All integration data was deterministic synthetic/non-face fixture data. Test databases,
Redis DBs and temporary Celery containers were isolated and removed after use.

## Remote candidate evidence

Run `31924258547` is bound to candidate SHA
`ed24b3d856e22bc1d0779a9eace254200041fb81` and completed successfully.

| Job                       | Job ID        | Mandatory evidence                                                                                                                                                                      |
| ------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `quality-and-integration` | `95109211376` | Python quality/tests, migration lifecycle, Redis/Celery, explicit Phase 1 vertical test, TypeScript/build, browser, contract drift, Phase 1 evidence, dependency/license audit and SBOM |
| `secret-scan`             | `95109211287` | complete-history Gitleaks with default rules preserved                                                                                                                                  |
| `docker-validation`       | `95109211330` | Compose validation/build/start, health behavior, Worker suite and Alembic check                                                                                                         |

Artifacts were downloaded, readable and unexpired on 2026-08-16:

- `project-audit-evidence` (`9257372469`)
- `phase1-ci-evidence` (`9257370449`): candidate SHA, head
  `0007_account_quarantine_evidence`, OpenAPI LF-byte SHA-256
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`, and one
  passing vertical test with zero failures, errors or skips
- `project-docker-evidence` (`9257358370`)
- `gitleaks-results.sarif` (`9257333907`): zero results

The conditional browser-failure artifact step was correctly skipped because browser
integration passed. GitHub's Node 20 action-runtime deprecation annotations are
nonblocking upstream maintenance debt; all mandatory steps completed successfully.

## Remote closure evidence

Run `31924651458` is bound to acceptance SHA
`cc926ceb49c7978cb7b57df778ec2f1c7f4cc878` and completed successfully.

| Job                       | Job ID        | Result  |
| ------------------------- | ------------- | ------- |
| `quality-and-integration` | `95110182752` | SUCCESS |
| `secret-scan`             | `95110182730` | SUCCESS |
| `docker-validation`       | `95110182753` | SUCCESS |

Artifacts were downloaded, readable and unexpired on 2026-08-16:

- `project-audit-evidence` (`9257494004`)
- `phase1-ci-evidence` (`9257491150`): acceptance SHA, head
  `0007_account_quarantine_evidence`, OpenAPI LF-byte SHA-256
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`, and one
  passing vertical test with zero failures, errors or skips
- `project-docker-evidence` (`9257470076`)
- `gitleaks-results.sarif` (`9257448027`): zero results

The closure repeated Python, migration, Redis/Celery, Phase 1 vertical recovery,
TypeScript/build, browser, contract, dependency/license, SBOM, Docker/Compose and
complete-history secret-scan Gates. The freeze-state commit receives its own full CI
verification; that run is reported at handoff and is not recursively written back.

## Defect classification

No product implementation defect required a `P1-M6-Rxx` task. During candidate
assembly, test-only assertions were aligned with the frozen phone-hash de-association
semantics, logger state was isolated across the full suite, the evidence configuration
was corrected to the repository's exact migration revision, and two synthetic
idempotency literals were changed to low-entropy fixtures after local Gitleaks findings.
No Gate or security rule was weakened.

## Deferred production gates

- Real SMS, age assurance, COS, real facial-data intake and AI Provider traffic remain
  fail closed pending legal, privacy, Provider and security review.
- Production telemetry, paging, Tencent Cloud deployment,备案/PIPIA and incident-response
  exercises remain P9 work.
- P2 synthetic dataset implementation must not begin until Phase 1 is frozen and a new
  rolling-wave plan is authorized.

`P1-M6_GATE: PASS`

`P1-M6_STATE: FROZEN`
