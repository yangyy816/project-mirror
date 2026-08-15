# P1-M1 Acceptance Record

## Gate

- Milestone: `P1-M1 — Invite-only Identity and Authentication Backend`
- Candidate SHA: `99c4fcc7e1fea5e240da09b45e532b9d9c793088`
- Candidate run: [31886292870](https://github.com/yangyy816/project-mirror/actions/runs/31886292870)
- Principal decision: `PASS`
- Freeze state: pending the closure commit's complete remote CI

`PASS` records that T01–T08 and all mandatory M1 evidence were accepted. `FROZEN` is not
issued until this acceptance record itself has passed the complete workflow.

## Accepted scope

- T01: authentication/session and external age-assurance decisions are frozen in Accepted ADRs.
- T02: additive `0002_identity_auth` persistence and PostgreSQL invariants are implemented.
- T03: phone/OTP/HMAC/JWT/refresh/CSRF/rate-limit primitives fail closed in production.
- T04: transient SMS destination and minimal age-assurance Provider boundaries are implemented.
- T05: challenge, session, refresh, logout, age, policy, activation and idempotency application
  transactions are implemented independently from FastAPI.
- T06: the seven approved `/api/v1` HTTP interfaces and generated TypeScript contract are
  implemented.
- T07: invite creation/disable CLI keeps plaintext issuance one-time and persistence hashed.
- T08: the assembled vertical chain passed local and remote integration, security and contract
  verification.

No Web onboarding, upload, facial processing, real SMS/age Provider, payment or public
registration was added.

## Local authoritative evidence

| Area            | Evidence                                                           | Result                   |
| --------------- | ------------------------------------------------------------------ | ------------------------ |
| API integration | Compose PostgreSQL 17 + Redis 8, complete API suite                | `98 passed`, zero skip   |
| Vertical HTTP   | challenge → OTP → pending → age → policy → active refresh → logout | PASS                     |
| Python quality  | Ruff format/check and strict mypy over API + Worker                | PASS                     |
| TypeScript      | canonical `pnpm check`, including lint/type/test/build             | PASS                     |
| Contract        | OpenAPI export → generated TypeScript → zero diff                  | PASS                     |
| Migration       | `0001 → 0002 → 0001 → 0002`; `alembic check`                       | PASS, no drift           |
| Supply chain    | `pip-audit --local`; `pnpm audit --audit-level high`               | no known vulnerabilities |
| Secret scan     | Gitleaks 8.28.0 over exact Git-index snapshot                      | no leaks found           |
| Containers      | full image build, five-service readiness, API/Web/Worker smoke     | PASS                     |

The isolated migration database `mirror_m1_t08` was deleted after verification. Tests contain
only synthetic markers and deterministic Fakes; they make no external Provider calls.

## Remote evidence

Run `31886292870` is bound to candidate SHA
`99c4fcc7e1fea5e240da09b45e532b9d9c793088` and completed successfully.

| Job                       | Job ID        | Mandatory evidence                                                                                                                |
| ------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `quality-and-integration` | `95015961340` | Python quality/tests, PostgreSQL migration lifecycle, Redis/Celery, TypeScript, contract drift, dependency/license audit and SBOM |
| `secret-scan`             | `95015961336` | Gitleaks action                                                                                                                   |
| `docker-validation`       | `95015961359` | Compose validation/build/start, health behavior, Worker ping and Alembic check                                                    |

Artifacts are present and unexpired:

- `phase-0-audit-evidence` (`9247365938`)
- `phase-0-docker-evidence` (`9247355536`)
- `gitleaks-results.sarif` (`9247336849`)

The artifact labels above are historical workflow naming debt; the closure commit renames future
evidence labels without changing Gate behavior.

## Material repairs closed

- R13: idempotency replay cannot reissue access for consumed, revoked or expired sessions.
- R14: revoked access is rejected after logout and browser DELETE preflight is supported.
- R15: challenge acceptance uses deterministic decoy `202` semantics to prevent direct account
  enumeration without sending SMS or creating a real challenge.
- R16: a post-SMS finalize failure changes the idempotency claim from `in_progress` to `failed`,
  allowing a safe same-key retry instead of permanently wedging the request.

## Deferred production gates

- Production registration remains disabled until real SMS and age-assurance Providers are
  independently verified.
- Real SMS response-time enumeration must be re-gated before P9 production enablement.
- No real phone number, credential, face image, payment or public registration is accepted by this
  milestone.

`P1-M1_GATE: PASS`
