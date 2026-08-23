# P3–P7 D01-C Acceptance Evidence

## Candidate status

```text
TASK: D01-C — API contract skeleton
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
BASE_SHA: d134517fa97132b180a82c69c617b8f65d3b282e
BRANCH: codex/p3-p7-core-demo
MIGRATION_HEAD: demo_0002_p3_p7_command_auth
INITIAL_CANDIDATE: 74e4212fe0b0730e844108d27b680e4ec4d83fed
REPAIR_CANDIDATE: 3523d61f92030e4d30876ee1aa5b4265d4d57200
REPAIR_PARENT: 74e4212fe0b0730e844108d27b680e4ec4d83fed
CURRENT_STATUS: TASK_ACCEPTED
PRINCIPAL_TASK_ACCEPTANCE: TASK_ACCEPTED
INDEPENDENT_SOL_EXACT_SHA_REVIEW: PASS
D02: EXECUTION_READY
D04_A: EXECUTION_READY
D07_A: EXECUTION_READY
D09: EXECUTION_READY
D03_D12_OTHERWISE: DEPENDENCY_GATED_OR_NOT_VERIFIED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This checkpoint accepts only the complete Demo API contract skeleton and its synchronous semantic-idempotency
application authority. It does not claim that P3–P7 algorithms, Worker registrations, the complete Web platform or any
D02–D12 acceptance Gate is implemented. `/api/v1/demo/capabilities` is the only success path at this checkpoint; every
unimplemented operation continues to fail closed as structured `501 CAPABILITY_NOT_IMPLEMENTED`.

## Accepted contract surface

The exact frozen surface contains 23 operations, including all 21 original operations and the two Job lifecycle
operations:

```text
GET  /api/v1/demo/capabilities
POST /api/v1/demo/sessions
GET  /api/v1/demo/sessions/{id}/context
GET  /api/v1/demo/identities
POST /api/v1/demo/analyses
GET  /api/v1/demo/analyses/{id}
POST /api/v1/demo/questionnaires/runs
GET  /api/v1/demo/questionnaires/runs/{id}/next
POST /api/v1/demo/questionnaires/runs/{id}/responses
POST /api/v1/demo/profiles/compile
GET  /api/v1/demo/profiles/active
POST /api/v1/demo/style-feedback
POST /api/v1/demo/constraints
POST /api/v1/demo/editing-sessions
POST /api/v1/demo/editing-sessions/{id}/plans
POST /api/v1/demo/edit-plans/{id}/executions
GET  /api/v1/demo/tool-runs/{id}
POST /api/v1/demo/image-versions/{id}/feedback
POST /api/v1/demo/image-versions/{id}/restore
POST /api/v1/demo/profiles/rebuild
GET  /api/v1/demo/traces/{session_id}
GET  /api/v1/demo/jobs/{job_id}
POST /api/v1/demo/jobs/{job_id}/cancel
```

All 23 operations require `DemoBearerAuth`, carry `x-demo-only: true` and use strict request/response models. The 14
creating POST operations require a visible-ASCII `Idempotency-Key` with the exact authority:

```text
type: string
minLength: 8
maxLength: 128
pattern: ^[!-~]{8,128}$
```

The Job accepted/lifecycle envelopes require `job_binding_digest` and a typed target containing `target_type`,
`target_id` and `authority_digest`. The ten target types match the immutable `DemoJobBinding` database allowlist.
`EDIT_PLAN.authority_digest` can be carried forward as `expected_plan_digest`; clients do not invent this value.

Capabilities retain the truthful unavailable states:

```text
P6_MAKEUP: DEFERRED_WITH_EXPLICIT_REASON
P6_GENERATIVE_EDITOR: CAPABILITY_UNAVAILABLE
```

No sensitive-trait routing, beauty score, raw-float digest authority, production Provider or production authorization
was added.

## Synchronous semantic idempotency

`DemoSemanticIdempotencyCoordinator` binds the frozen six synchronous operations to the accepted
`demo_command_bindings` PostgreSQL authority. Existing binding lookup occurs before the mutation creator, so same-key
replay and different-digest conflict cannot re-advance questionnaire or Job state. A miss still uses a savepoint and
PostgreSQL unique winner with `ON CONFLICT`; a losing concurrent creator rolls back and reloads the canonical winner.

Verified semantics:

```text
SAME_KEY_SAME_PAYLOAD: SAME_TARGET_AND_BINDING
SAME_KEY_DIFFERENT_PAYLOAD: 409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD
QUESTIONNAIRE_REPLAY_CREATOR_CALLS: 0
CANCELLED_JOB_REPLAY_CREATOR_CALLS: 0
CONCURRENT_CANONICAL_WINNERS: 1
LOSING_TARGET_AND_BINDING: ROLLED_BACK
OWNER_SESSION_TYPE_STATUS_TARGET_MISMATCH: FAIL_CLOSED
```

## Local validation

Validation used a complete LF-faithful snapshot of the candidate, a fresh task-scoped PostgreSQL database, isolated
Redis DB, real Celery worker, private local storage volume and a Docker internal network. No host port was published for
the task PostgreSQL or Redis containers.

```text
DOCKER_NETWORK_INTERNAL: TRUE
PUBLIC_INTERNET_EGRESS: DENIED
ALL_NETWORK_DISABLED: FALSE
LOCALHOST_AND_DOCKER_DATA_PLANE: RETAINED
PROXY_IN_CORE_TEST_CONTAINERS: ABSENT
PRODUCTION_PROVIDER_CALLS: 0

FRESH_TO_DEMO_HEAD: PASS
DEMO_HEAD_TO_BASE_TO_DEMO_HEAD: PASS
ALEMBIC_CHECK: ZERO_DRIFT
FULL_API_WORKER_SUITE: 816 PASS, 1 EXISTING OPTIONAL PRIVATE-RUNTIME SKIP
RUFF_FORMAT_CHECK: 230 files formatted
RUFF_CHECK: PASS
STRICT_MYPY: PASS, 129 source files
OPENAPI_REEXPORT_DRIFT: 0
GENERATED_TYPES_FRESHNESS: PASS
GENERATED_TYPES_TYPECHECK: PASS
GITLEAKS_8_28_0_DIRECTORY_SCAN: PASS, 6.16 MB, 0 findings
```

Negative evidence is retained. The first migration harness omitted the CI-required `TASK_RUNNER=celery` and failed
closed during settings validation before database access. The first full Linux container run mounted the Windows
working tree directly and produced five frozen-byte digest failures from CRLF conversion while still producing
`811 passed, 1 skipped`; the same five tests passed `5/5` on the LF-faithful snapshot, and the complete snapshot suite
then passed `816/816` executable tests. Ruff and mypy initially attempted to write caches into the read-only snapshot;
the corrected run used `--no-cache` and a container-temporary mypy cache without changing source or Gate thresholds.

## Exact-SHA CI evidence

GitHub Actions run `32636591101` completed successfully for exact implementation SHA
`3523d61f92030e4d30876ee1aa5b4265d4d57200`.

```text
secret-scan: PASS
quality-and-integration: PASS
docker-validation: PASS
```

The quality job passed Python quality, PostgreSQL migration lifecycle, real Linux Celery, the complete Python suite,
Phase 1 and P2-M1–M3 regression groups, TypeScript quality/build, Playwright browser integration, contract regeneration
drift, Demo prototype boundary validation, dependency/license audits and SBOM generation. Formal Phase 1/P2 evidence
generators were deliberately skipped only on the Demo branch; executable Gates were not skipped.

The retained artifacts are unexpired:

```text
project-audit-evidence: 9492534393
demo-prototype-ci-boundary: 9492531462
playwright-install-evidence: 9492527387
project-docker-evidence: 9492488739
gitleaks-results.sarif: 9492471102
```

The downloaded prototype-boundary witness reports:

```text
TRACK: DEMO_PROTOTYPE
COMMIT_SHA: 3523d61f92030e4d30876ee1aa5b4265d4d57200
DEMO_MIGRATION_HEAD: demo_0002_p3_p7_command_auth
FORMAL_EVIDENCE_GENERATORS: NOT_RUN_ON_PROTOTYPE_HEAD
FORMAL_HEAD_AUTHORITY: 0014_m5_eval_authority
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

## Independent review and isolation

Sol High reviewed both the repair diff before commit and the exact committed SHA. The original three mandatory
findings—visible-ASCII idempotency keys, replay/conflict creator short-circuiting and owner-bound typed Job target
digests—are closed. The exact-SHA review found no new mandatory security, privacy, contract or concurrency finding.

Remote identity remained `yangyy816/project-mirror`; its current `PUBLIC` visibility matches the D01-A accepted
`PUBLIC_VERIFIED` authority. Before push, visibility was rechecked and the candidate contained no private bytes or
Gitleaks findings. The local proxy `127.0.0.1:7897` was used only for the authorized GitHub/Git control-plane calls and
never entered the offline core test environment.

The formal worktree remained on `codex/phase2-m7-internal-operations` at
`c15fd29340552f7c4d4b3348f862da6deb242986` throughout this repair closure. Its tracked modifications were pre-existing
concurrent formal work and were not read, copied, staged or changed by D01-C. Protected `.tmp/` content was not read.

## Principal decision

```text
D01_C: TASK_ACCEPTED
D02: EXECUTION_READY
D04_A: EXECUTION_READY
D07_A: EXECUTION_READY
D09: EXECUTION_READY
D03_D12_OTHERWISE: DEPENDENCY_GATED_OR_NOT_VERIFIED
ALGORITHMIC_PROTOTYPE_PLATFORM: NOT_VERIFIED
LOCAL_WEB_AGENT: NOT_VERIFIED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This acceptance opens only the DAG nodes whose frozen dependencies are satisfied. It does not freeze the final Demo API
contract, claim any P3–P7 algorithm PASS or authorize production use.
