# P2-M2 Independent Final Review

## Review identity

- Milestone: `P2-M2 — Generation Batch and Provider Pipeline`
- Frozen entry: `4a69f93f0d092afa0b520bbfb6e7d192e0f3dff1`
- Branch: `codex/phase2-m2-generation-pipeline`
- Last same-SHA baseline: `c24b03b636722614f1c23eef1e1b4a83c28fcd28`, run `31954658786`
- Current review target: ADR-026 / V01 candidate working tree; final commit SHA pending
- Review mode: independent read-only security, privacy, schema, contract, phase and supply-chain
  review after Principal implementation and repair
- Review result: `CONDITIONAL_REMOTE_ONLY`

The only remaining condition is the final candidate same-SHA GitHub Actions run. The review found no
unresolved implementation, security, privacy, phase-boundary or supply-chain defect and does not
require a production runtime Provider for P2 synthetic-only research.

## Change-control and scope conclusion

ADR-026 validly supersedes only the earlier M2 exit-Gate interpretation:

- `CODEX_NATIVE_IMAGEGEN` is an operator-assisted offline source, never a runtime
  `ImageGenerationProvider` or production config option.
- The existing programmatic Provider port, deterministic Mock pipeline and future domestic Adapter
  boundary remain unchanged.
- Missing production Provider terms, Adapter and controlled live benchmark are recorded as
  `DEFERRED_EXTERNAL_PRODUCTION_DEPENDENCY` and
  `PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER: OPEN`.
- M2 still stops at immutable private raw admission. It does not normalize, run Vision/QA, register
  identity, create variants or release QuestionBank content.
- Public OpenAPI/generated TypeScript, dependencies, model artifacts and migrations are unchanged.

## V01 and repair evidence

V01 generated four categories × two outputs in serial: 8 requested, 8 admitted, 8 attempts used,
12-attempt maximum and no retry. All expected SHA-256 values matched. Requested `1024×1024 PNG`
and observed `1254×1254 PNG` facts are both retained with
`dimensions_match_requested=false`; no M2 resampling or normalization occurred.

Independent review initially found two mandatory defects and one associated leakage risk:

- `P2-M2-R06` now requires an approved private source root, rejects UNC, traversal,
  symlink/reparse escape, requires per-item expected SHA-256 before storage, enforces item retry and
  specification attempt ceilings, and converts OS errors to a stable path-free reason.
- `P2-M2-R07` adds runtime guards proving that model, model version, Provider request, seed, usage
  and Provider cost remain `NULL`; Python type annotations alone are no longer trusted.
- Negative tests cover external root, UNC, symlink, checksum mismatch, attempt overspend, null-fact
  fabrication and path-redaction behavior.

After repair, the independent security reviewer found no remaining ADR-026 defect. The native
origin and generation event are necessarily Principal/operator attestations at
`PROVENANCE_ONLY`; this accepted research limitation cannot be upgraded to model/request/cost
provenance or production approval.

## Local validation reviewed

| Evidence                                | Result                                                             |
| --------------------------------------- | ------------------------------------------------------------------ |
| Ruff format/lint                        | 161 files PASS                                                     |
| strict mypy                             | 101 sources PASS                                                   |
| Full API/Worker/PostgreSQL/Redis/Celery | 353 passed, zero skip                                              |
| R06/R07 targeted tests                  | 11 passed                                                          |
| Alembic isolated lifecycle              | base→head→base→head and `check` PASS                               |
| TypeScript/Web/contracts/build          | `pnpm check` PASS; 54 Web tests                                    |
| OpenAPI regeneration                    | no OpenAPI/generated TypeScript diff                               |
| Docker build and health                 | images built; API/Web/Worker/PostgreSQL/Redis healthy              |
| Docker smoke                            | API live/ready, Web 200 and Celery ping PASS                       |
| V01 rerun                               | 8/8 admitted; expected SHA matches; 8/12 attempts                  |
| Supply chain                            | no dependency, model artifact, Provider SDK or tracked image added |

The persistent normal development PostgreSQL volume reports one historical schema drift: it is
already stamped at `0009` but predates the frozen `0008` bank-independent identity check. The
isolated fresh database completed both migration lifecycles and `alembic check`; the existing
volume was not manually altered or deleted. Fresh-volume Docker CI is the authoritative final
evidence for this environment-only condition.

## Gate conclusion

```text
P2_M2_CORE_PIPELINE_GATE: PASS_LOCAL
P2_M2_CODEX_NATIVE_SOURCE_GATE: PASS
P2_M2_PROGRAMMATIC_PROVIDER_GATE: DEFERRED_EXTERNAL_PRODUCTION_DEPENDENCY
P2_M2_PRODUCTION_PROVIDER_APPROVAL: NOT_GRANTED
P2_M2_PRODUCTION_GENERATION: FAIL_CLOSED
P2_M2_T08_SECURITY_REVIEW: PASS
P2_M2_LOCAL_GATE: PASS
P2_M2_REMOTE_CI: PENDING_FINAL_CANDIDATE
P2_M2_STATE: EXECUTING
P2_M2_PASS: PENDING_FINAL_SAME_SHA_CI
P2_M2_FROZEN: NOT_YET_AUTHORIZED
P2_M3_ENTRY: CLOSED_UNTIL_FINAL_CI
```

If all three final candidate jobs and the v2 evidence artifact pass on one SHA, the Principal may
declare M2 `PASS`, create the acceptance closure, and then freeze M2 after the closure same-SHA CI.
