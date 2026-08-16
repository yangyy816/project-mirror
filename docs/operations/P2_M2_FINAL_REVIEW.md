# P2-M2 Independent Final Review

## Review identity

- Milestone: `P2-M2 — Generation Batch and Provider Pipeline`
- Frozen entry: `4a69f93f0d092afa0b520bbfb6e7d192e0f3dff1`
- Reviewed implementation head: `8a1a2463c545be31b38303a68c8f99772074e202`
- Branch: `codex/phase2-m2-generation-pipeline`
- Review mode: read-only implementation, schema, contract, security, data and supply-chain review
- Review result: `CONDITIONAL_LOCAL`

This report does not declare M2 `PASS` or `FROZEN`. It records the strongest conclusion supported
by current evidence and leaves every missing external or remote check explicit.

## Scope and authority review

The implementation remains inside the accepted ADR-025 boundary:

- PostgreSQL owns batch, item, raw-source, generation-evidence, cost and deletion-evidence state.
- Job and JobAttempt remain execution envelopes; task messages are exact reference-only values.
- Prompt material is bounded, leased, ephemeral, redacted and absent from task messages and logs.
- Provider output enters a private synthetic raw namespace and cannot become a normalized Asset,
  SyntheticIdentity, QA result, variant or QuestionBank entry in M2.
- retries, cancellation, stale leases, duplicate delivery, budget ceilings, raw conflicts and
  cleanup preserve append-only evidence and fail closed.
- production generation and synthetic storage remain disabled; Mock/Local are not production
  capabilities.

Relative to the frozen M1 entry, 48 files changed. Schema change is exactly one forward migration,
`0009_generation_batch_pipeline.py`; migrations `0001` through `0008` are unchanged. The current
unique Alembic head is `0009_generation_batch_pipeline`.

## Security, privacy and phase-boundary evidence

| Review item            | Evidence                                                                       | Result |
| ---------------------- | ------------------------------------------------------------------------------ | ------ |
| Synthetic-only         | contracts, task shape, fixture/source scans                                    | PASS   |
| Public API             | no OpenAPI/generated TypeScript diff; no generation route                      | PASS   |
| Network/SDK            | no URL or `aiohttp`/`boto3`/`httpx`/`requests`/Tencent SDK import in M2 source | PASS   |
| Prompt/log redaction   | exact task rejection plus R05 no-cause Celery fallback regression              | PASS   |
| Private raw storage    | namespace, traversal/symlink/tamper/conflict and exact-delete tests            | PASS   |
| PostgreSQL authority   | migration lifecycle, constraints, triggers, locks and concurrency tests        | PASS   |
| Production fail-closed | disabled production Provider/storage configuration                             | PASS   |
| M3 boundary            | no QA, identity registration, normalization, variant or release implementation | PASS   |
| Real-person data       | tracked/untracked image and fixture scans empty                                | PASS   |
| Dependencies/models    | no manifest/lock diff and no model artifact                                    | PASS   |

No credential, Prompt, image bytes, Provider URL, raw Provider response or object key is included in
the M2 CI evidence artifact.

## Validation evidence reviewed

- Ruff format/lint passed across 158 files; strict mypy passed across 99 sources.
- `pnpm check` passed, including lint, strict typecheck, 54 Web tests, contract drift and Next build.
- Fresh Linux containers passed 307 API tests and 27 Worker tests with zero skip against isolated
  PostgreSQL, Redis and a real Celery worker.
- The dedicated M2 evidence set passed 37 tests with zero failure/error/skip and generated a valid
  `mirror.p2-m2.ci-evidence/v1` aggregate.
- The evidence binds migration head and OpenAPI digest and truthfully records
  `external_validation_required` plus `production_approved=false`.
- Both isolated databases, the dedicated Redis test DB and temporary Workers were removed; the
  normal five-service Compose topology returned healthy.
- Windows host pytest is not used as evidence because the runtime denied access to both the existing
  and newly isolated temp roots. No protected ACL directory was cleaned or adopted.

## Evidence not verified

### Same-SHA GitHub Actions

`NOT VERIFIED`. The current branch has not been pushed because the available explicit push
authorization covered a different historical branch and the security approval rejected expanding
it to this P2-M2 payload. Therefore none of the three remote jobs or uploaded artifacts is claimed.

### Controlled live image-generation Provider

`EXTERNAL_VALIDATION_REQUIRED: IMAGE_GENERATION_PROVIDER`. The Provider/model registry still lacks
approved evidence for model/data terms, retention, public training, region, subprocessors, deletion,
output rights, content safety and cost. Mock evidence cannot satisfy this Gate and no unapproved live
call was attempted.

## Gate conclusion

All deterministic local implementation, security and integration evidence reviewed here passes.
The missing remote same-SHA run and controlled real-Provider validation are mandatory M2 exit
evidence. Consequently:

```text
P2_M2_T08_LOCAL_REVIEW: PASS
P2_M2_REMOTE_CI: NOT_VERIFIED
P2_M2_PROVIDER_GATE: BLOCKED
P2_M2_LOCAL_GATE: CONDITIONAL
P2_M2_STATE: EXECUTING
P2_M2_PASS: NOT_AUTHORIZED
P2_M2_FROZEN: NOT_AUTHORIZED
P2_M3_ENTRY: CLOSED
PHASE_2_COMPLETE: NO
```

Only a same-SHA remote run plus an approved controlled Provider benchmark can upgrade this result.
