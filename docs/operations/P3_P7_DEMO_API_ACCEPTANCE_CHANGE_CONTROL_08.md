# P3–P7 Demo API Acceptance Change Control 08

## Decision status

```text
CHANGE_CONTROL_ID: CC-P3-P7-DEMO-API-08
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
CHANGE_TYPE: FORWARD_ACCEPTANCE_AND_OWNERSHIP_CLARIFICATION
STATUS: PRINCIPAL_ACCEPTED_FOR_TRACKED_EVIDENCE
BASE_SHA: 055b6dabfb79c1b0fc0b93906125b6418ffe9cd5
INDEPENDENT_SOL_ARCHITECTURE_REVIEW: PASS
NEW_D_TASK: NO
HISTORICAL_ACCEPTANCE_REWRITE: FORBIDDEN
FORMAL_AUTHORITY_CHANGE: NONE
D02_CURRENT_STATUS: NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE
D02_TASK_ACCEPTED: NO
DEMO_API_APPLICATION_INTEGRATION: CLOSED_DEPENDENCY_GATED
DEMO_API_CONTRACT_FREEZE: NOT_READY
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This forward change closes an acceptance-definition gap without changing any accepted implementation, public schema,
migration, ORM model or formal authority. D09 is historically accepted for its ledger and Final Save domain, while
its two public route adapters remain unimplemented. D01-C is historically accepted for the complete contract skeleton,
typed Job binding and synchronous idempotency authority, while generic Job query and cancellation application routes
remain unimplemented. Neither historical result is rewritten or withdrawn.

The missing boundary is made explicit as a non-D-task checkpoint:

```text
DEMO_API_APPLICATION_INTEGRATION
```

It is inserted after all required D03–D10 domain/application checkpoints and before
`DEMO_API_CONTRACT_FREEZE`. It preserves D01–D12 exactly and cannot open while D02 is not `TASK_ACCEPTED`.

## Historical acceptance treatment

```text
D01_C: TASK_ACCEPTED
D01_C_ACCEPTED_SCOPE: CONTRACT_SKELETON_AND_IDEMPOTENCY_AUTHORITY
GENERIC_JOB_ROUTE_INTEGRATION: NOT_VERIFIED

D09: TASK_ACCEPTED
D09_ACCEPTED_SCOPE: LEDGER_AND_FINAL_SAVE_DOMAIN
D09_PUBLIC_API_INTEGRATION: NOT_VERIFIED
D09_ROUTE_STATE: DOMAIN_READY_ROUTE_PENDING
```

`P3_P7_D01_C_ACCEPTANCE.md` remains the immutable evidence for the 23-operation contract skeleton and PostgreSQL
idempotency authorities. `P3_P7_D09_ACCEPTANCE.md` remains the immutable evidence for PreferenceEvent, atomic Final
Save, AcceptedVisualEpisode and the branch-local provenance hardening. Their accepted commits intentionally contain no
successful implementation of the affected public routes.

The `owner_task` string in the D01-C 501 skeleton identifies the planned domain/application provider. It does not
assert that the provider task accepted the route, and it does not transfer ownership of the central router, OpenAPI or
generated client to a topic task.

## Two-layer ownership

For every Demo operation, ownership is split and both layers are mandatory:

1. The D02–D10 provider owner supplies accepted domain/application behavior, transaction semantics, state transitions,
   typed errors and provider-level tests.
2. The Integration Principal alone performs central router wiring, cross-domain authorization and error mapping,
   Celery registration, OpenAPI regeneration, generated-client regeneration and final contract acceptance.

Provider acceptance advances a route only to `DOMAIN_READY_ROUTE_PENDING`. It cannot by itself return success from the
HTTP route or advertise the capability as available.

```text
CONTRACT_ONLY_501
→ DOMAIN_READY_ROUTE_PENDING
→ ROUTE_INTEGRATED_NOT_FROZEN
→ CONTRACT_FROZEN
```

## Route ownership matrix

The provider owner never owns `services/api/src/mirror_api/routers/demo.py`, central Celery registration,
`packages/contracts/openapi.json` or `packages/contracts/src/schema.ts`.

|   # | Operation                                  | Provider owner and required dependencies                     | State at this change         |
| --: | ------------------------------------------ | ------------------------------------------------------------ | ---------------------------- |
|   1 | `GET /capabilities`                        | Principal aggregate over accepted route cohorts              | `SKELETON_AVAILABLE`         |
|   2 | `POST /sessions`                           | D02                                                          | `CONTRACT_ONLY_501`          |
|   3 | `GET /sessions/{id}/context`               | D10                                                          | `CONTRACT_ONLY_501`          |
|   4 | `GET /identities`                          | D02                                                          | `CONTRACT_ONLY_501`          |
|   5 | `POST /analyses`                           | D03 plus Worker registration                                 | `CONTRACT_ONLY_501`          |
|   6 | `GET /analyses/{id}`                       | D03                                                          | `CONTRACT_ONLY_501`          |
|   7 | `POST /questionnaires/runs`                | D04-B                                                        | `CONTRACT_ONLY_501`          |
|   8 | `GET /questionnaires/runs/{id}/next`       | D04-B                                                        | `CONTRACT_ONLY_501`          |
|   9 | `POST /questionnaires/runs/{id}/responses` | D04-B                                                        | `CONTRACT_ONLY_501`          |
|  10 | `POST /profiles/compile`                   | D05 plus Worker registration                                 | `CONTRACT_ONLY_501`          |
|  11 | `GET /profiles/active`                     | D05                                                          | `CONTRACT_ONLY_501`          |
|  12 | `POST /style-feedback`                     | D09 ledger provider                                          | `DOMAIN_READY_ROUTE_PENDING` |
|  13 | `POST /constraints`                        | D05                                                          | `CONTRACT_ONLY_501`          |
|  14 | `POST /editing-sessions`                   | D07-B                                                        | `CONTRACT_ONLY_501`          |
|  15 | `POST /editing-sessions/{id}/plans`        | D07-B execution authority plus D08 planner                   | `CONTRACT_ONLY_501`          |
|  16 | `POST /edit-plans/{id}/executions`         | D07-B runtime plus D08 registry/verifier                     | `CONTRACT_ONLY_501`          |
|  17 | `GET /tool-runs/{id}`                      | D07-B plus D08                                               | `CONTRACT_ONLY_501`          |
|  18 | `POST /image-versions/{id}/feedback`       | D09 ledger/Final Save plus D07-B and D08 trajectory/verifier | `DOMAIN_READY_ROUTE_PENDING` |
|  19 | `POST /image-versions/{id}/restore`        | D07-B                                                        | `CONTRACT_ONLY_501`          |
|  20 | `POST /profiles/rebuild`                   | D10 plus Worker registration                                 | `CONTRACT_ONLY_501`          |
|  21 | `GET /traces/{session_id}`                 | D10 reading the integrated D03–D10 trace                     | `CONTRACT_ONLY_501`          |
|  22 | `GET /jobs/{job_id}`                       | `DEMO_API_APPLICATION_INTEGRATION/JOB_LIFECYCLE`             | `CONTRACT_ONLY_501`          |
|  23 | `POST /jobs/{job_id}/cancel`               | `DEMO_API_APPLICATION_INTEGRATION/JOB_LIFECYCLE`             | `CONTRACT_ONLY_501`          |

The D09 image-feedback adapter must distinguish event-only acceptance from Final Save. A request that claims Final Save
must call the accepted atomic event-plus-episode service and may not append only `IMAGE_ACCEPTED`.

## Generic Job lifecycle ownership

Generic Job query/cancel no longer has semantic implementation ownership in D01-C. D01-C retains the accepted schemas,
`DemoJobBinding`, `DemoCommandBinding`, operation allowlists and idempotency coordinator. The central Job lifecycle
provider added during `DEMO_API_APPLICATION_INTEGRATION` must prove:

- actor/session/typed-target authorization through immutable `DemoJobBinding`;
- deterministic mapping from formal Job state to the Demo uppercase state contract;
- only the frozen legal state transitions and terminal-state immutability;
- one PostgreSQL canonical cancellation winner and same-key replay;
- cancellation versus Worker claim/result-publication races;
- no result publication after accepted cancellation;
- Worker redelivery does not duplicate Event, ToolRun, Verification, ImageVersion or Profile authority; and
- execution/storage/algorithm failure maps to `FAILED`, while eligibility/constraint/verifier rejection maps to
  `REJECTED`.

No individual D03–D10 topic may implement a private generic Job route or create a second state mapping.

## Revised DAG fragment

```text
D02 TASK_ACCEPTED
→ D03

D03 TASK_ACCEPTED
→ D04-B + D07-B

D04-B → D05
D05 + D07-B + D09 → D06
D05 + D07-B → D08
D05 + D06 + D09 → D10

D03, D04-B, D05, D06, D07-B, D08, D09, D10 TASK_ACCEPTED
→ DEMO_API_APPLICATION_INTEGRATION

DEMO_API_APPLICATION_INTEGRATION TASK_ACCEPTED
→ DEMO_API_CONTRACT_FREEZE

DEMO_API_CONTRACT_FREEZE
→ D11
→ D12
```

This inserts one explicit Gate into the previously direct transition. It adds no D-task, removes no dependency and
does not permit pure-domain work to bypass D02 or D03.

## Application-integration entry and exit

Entry requires:

```text
D03_D10_REQUIRED_CHECKPOINTS: TASK_ACCEPTED
DOMAIN_APPLICATION_PROVIDER_MATRIX: COMPLETE
CENTRAL_ROUTER_WRITER: PRINCIPAL_ONLY
CENTRAL_OPENAPI_CLIENT_WRITER: PRINCIPAL_ONLY
MIGRATION_HEAD: EXACT_AND_SINGLE
INTEGRATION_WORKTREE: CLEAN
D02_PRIVATE_GATE: ACCEPTED_AND_REPLAYABLE
```

Exit requires actual execution evidence:

```text
23_OPERATIONS_PRESENT: PASS
MANDATORY_CORE_ROUTES_RETURN_501: 0
14_CREATING_ROUTES_IDEMPOTENCY: PASS
ACTOR_SESSION_OWNERSHIP: PASS
JOB_GET_CANCEL: PASS
JOB_STATE_MACHINE: PASS
FAILED_REJECTED_SEPARATION: PASS
WORKER_REDELIVERY: PASS
D09_STYLE_FEEDBACK_ROUTE: PASS
D09_IMAGE_FEEDBACK_AND_FINAL_SAVE_ROUTE: PASS
FIXED_UNAVAILABLE_CAPABILITIES: PASS
REAL_POSTGRESQL_REDIS_CELERY: PASS
PUBLIC_INTERNET_EGRESS: DENIED
```

`MANDATORY_CORE_ROUTES_RETURN_501: 0` means every required deterministic P3–P7 operation has a real application path.
It does not turn Makeup or Generative Editor into available algorithms. Their planner/API/UI paths must truthfully return
the accepted unavailable semantics rather than a missing-route 501.

## Capability transition Gate

A capability may leave `NOT_IMPLEMENTED` only after its complete route cohort satisfies:

```text
DOMAIN_PROVIDER_ACCEPTED
ROUTE_WIRING_IMPLEMENTED
OWNER_BOUND_ACCESS_PASS
IDEMPOTENCY_OR_READ_REPLAY_PASS
STATE_MACHINE_PASS
REAL_POSTGRESQL_PASS
WORKER_PATH_PASS_IF_ASYNC
OPENAPI_AND_GENERATED_CLIENT_REGENERATED
CENTRAL_INTEGRATION_ACCEPTED
```

The D01-C hard-coded capability response is only a truthful skeleton. Domain `TASK_ACCEPTED` alone never changes it.
The fixed exceptions remain:

```text
P6_MAKEUP: DEFERRED_WITH_EXPLICIT_REASON
P6_GENERATIVE_EDITOR: CAPABILITY_UNAVAILABLE
```

## API contract freeze Gate

Entry requires:

```text
DEMO_API_APPLICATION_INTEGRATION: TASK_ACCEPTED
```

Exit requires:

```text
OPENAPI_23_OPERATION_MATRIX: PASS
X_DEMO_ONLY_23_OF_23: PASS
GENERATED_TYPES_FRESH: PASS
OPENAPI_DRIFT: 0
ERROR_ENVELOPE_CONTRACT: PASS
CAPABILITY_MATRIX_TRUTHFUL: PASS
SCHEMA_ROUTE_APPLICATION_PARITY: PASS
EXACT_SHA_CI: PASS
INDEPENDENT_SOL_REVIEW: PASS
```

The freeze only authorizes D11 to consume the stable Demo API. It is not D12, formal P3–P7 acceptance, real-user
validity, production security or release authorization.

## Current acceptance and blocker index

```text
D00: PROVEN_HISTORICAL_GO
D01_A: TASK_ACCEPTED
D01_B: TASK_ACCEPTED_CC02
D01_C: TASK_ACCEPTED
D02: BLOCKED_NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE
D03: BLOCKED_BY_D02
D04_A: TASK_ACCEPTED
D04_B: BLOCKED_BY_D02_AND_D03
D05: BLOCKED_BY_D03_AND_D04_B
D06: BLOCKED_BY_D05_D07_B_D09
D07_A: TASK_ACCEPTED
D07_B: BLOCKED_BY_D02_AND_D03
D08: BLOCKED_BY_D05_AND_D07_B
D09: TASK_ACCEPTED_LEDGER_AND_FINAL_SAVE_DOMAIN
D10: BLOCKED_BY_D05_AND_D06
DEMO_API_APPLICATION_INTEGRATION: CLOSED_DEPENDENCY_GATED
DEMO_API_CONTRACT_FREEZE: NOT_READY
D11: NOT_READY
D12: NOT_VERIFIED
```

Historical D00 `GO` remains unchanged. The current D02 custody dependency recheck remains
`NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE` under `P3_P7_D02_AUTHORITY_CHANGE_CONTROL_07.md`. This change control does not
create a new receipt, registry row, identity, pair, Report, QuestionBank, route implementation or private handle.

## Scope and formal-boundary proof

```text
ORIGINAL_23_ROUTE_SCOPE_PRESERVED: YES
D01_D12_TASKS_REMOVED: 0
HISTORICAL_ACCEPTANCE_REWRITTEN: NO
FAKE_PASS_ALLOWED: NO
D02_UNLOCKED: NO
PRIVATE_BYTES_READ_OR_CREATED: NO
FORMAL_MIGRATION_CHANGE: NONE
FORMAL_P3_P7_STATUS_CHANGE: NONE
PRODUCTION_AUTHORIZATION_CHANGE: NONE
```
