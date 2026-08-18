# P2-M5-R02 Data-Rights Vertical-Test Dispatch Isolation Repair

## Status and authority

- Status: `REPAIR_ACCEPTED`.
- Trigger: Stage A acceptance checkpoint `d3158c03e0843e5a504531dd407eafea534630de`, run `32190386366`.
- Boundary: test-composition repair only. No production code, schema, migration, API, authorization, deletion
  semantics, P2 research result or dependency changes are permitted.
- Stage B remains closed until the repaired checkpoint passes exact-SHA CI and artifact review.

## Observed failure

The run passed `secret-scan` and `docker-validation`, but `quality-and-integration` ended with 566 passed, one
existing optional skip and one failure. The failing Phase 1 HTTP vertical test reached its final
`TRUNCATE TABLE users CASCADE` while a Celery delivery still held a related transaction:

```text
Process 262 waits for AccessExclusiveLock on relation 32699
Process 264 waits for RowShareLock on relation 18589
```

The Stage A commit changed governance documents only, so this is not a direct functional regression. It also cannot
be dismissed as flaky because the test dispatched data-export, asset-deletion and account-deletion jobs to a live
worker while independently driving the same data-rights services synchronously.

## Repair contract

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M5-R02`.
- `OBJECTIVE`: make the synchronous HTTP vertical test own all work that can touch its TRUNCATE-based isolation
  domain.
- `WHY_DELEGATED`: not delegated; the repair is small and collides with the Principal-owned acceptance checkpoint.
- `SCOPE`: the single data-rights HTTP integration test and forward evidence documents.
- `ALLOWED_FILES_OR_MODULES`: `test_data_rights_http_integration.py`, this repair record, M5 acceptance/log/MEMORY
  after tracked validation.
- `EXPECTED_CHANGE`: compose the test with recoverable no-broker dispatchers for data-rights and asset-deletion jobs;
  continue driving the authoritative services explicitly inside the test.
- `FORBIDDEN_SCOPE`: production dispatcher/service changes, retry masking, deadlock exception swallowing, schema,
  trigger, API, authorization, deletion semantics, Stage B execution, image generation or `.tmp` access.
- `DEPENDENCIES`: existing recoverable dispatcher ports and separate Celery/Redis integration coverage.
- `INPUTS_AND_ASSUMPTIONS`: this test validates HTTP ownership/idempotency and synchronous service outcomes; dedicated
  tests continue to validate Celery dispatch and live worker execution.
- `ACCEPTANCE_CRITERIA`: the test emits no Celery delivery, passes 20 repeated runs against real PostgreSQL with an
  isolated live worker present, and the complete repository Gate remains unchanged and green.
- `VALIDATION_COMMANDS`: targeted Ruff; 20-run isolated PostgreSQL/Redis/Celery replay; full API/Worker pytest; strict
  mypy; migration lifecycle/check; pnpm/contracts/build; Docker health/smoke; Gitleaks; exact-SHA Actions/artifacts.
- `SECURITY_NOTES`: no authorization or fail-closed behavior changes; this removes unintended duplicate execution
  from one test only.
- `PRIVACY_NOTES`: no real user data, image, Prompt, object key or database row is committed.
- `DATA_NOTES`: no migration or authority-row rewrite.
- `LICENSE_NOTES`: no dependency or model artifact change.
- `ROLLBACK`: revert the test and forward evidence before any dependent checkpoint.
- `RECOMMENDED_AGENT`: Principal.
- `RECOMMENDED_MODEL_TIER`: current Principal; no subagent needed for this isolated test repair.
- `OUTPUT_FORMAT`: standard bounded-task report plus exact-SHA CI evidence.
- `ESCALATION_CONDITION`: any need to change production locking, schema, trigger, API, authorization or deletion
  policy.

## Local evidence

- With only data-rights dispatch suppressed, the isolated replay still deadlocked on iteration 2 because the asset
  deletion endpoint independently dispatched to the same maintenance worker.
- With both automatic dispatch paths replaced by their existing recoverable no-broker adapters, the same test passed
  20/20 runs against a dedicated PostgreSQL database while an isolated Redis DB and live Celery maintenance worker
  were present.
- The isolated worker received zero tasks during the repaired replay. This proves the vertical test no longer leaks
  background work into its cleanup transaction without weakening the separate broker/worker tests.
- Full Linux API/Worker validation passed `567 passed, 1 skipped`; the skip is the existing optional private-runtime
  gate. Ruff covered 212 files, strict mypy covered 124 sources, and the complete Alembic
  `base -> head -> base -> head` lifecycle plus zero-drift check passed on fresh PostgreSQL.
- `pnpm check`, full Compose rebuild, five-service health, API/Web smoke, Celery ping, the exact staged-index Gitleaks
  scan and the 178-commit full-history scan all passed. No dependency, model, image or OpenAPI artifact changed.

`P2_M5_R02_LOCAL_GATE: READY_FOR_TRACKED_EVIDENCE`

## Tracked acceptance evidence

- Repair candidate `9946a43d771c2cb27d764243bda047e943ad5c99` completed GitHub Actions run
  `32192316257`; `quality-and-integration`, `secret-scan` and `docker-validation` all passed on that exact SHA.
- Seven expected artifacts are present, readable and unexpired. Phase 1/M1/M2/M3 evidence binds the exact candidate,
  migration head `0014_m5_eval_authority` and the unchanged OpenAPI digest; the suites report 1/98/52/46 tests with
  zero failures, errors or skips. Gitleaks SARIF contains zero results.
- The complete Python run reports `567 passed, 1 skipped`; the skip is the existing optional private-runtime Gate.
  Celery evidence contains no `ERROR`, traceback or deadlock. The only case-insensitive Docker-log `error` match is
  Redis configuration field `bf-error-rate`, not an execution failure.
- Principal accepts R02 as a test-composition repair. No production code, schema, API, authorization, deletion
  semantics, research result, dependency, model or image changed. Stage B may resume under its already accepted
  12-identity/18-attempt/concurrency-1 envelope.

`P2_M5_R02: REPAIR_ACCEPTED`

`CC_P2_M5_01_B: EXECUTION_READY`
