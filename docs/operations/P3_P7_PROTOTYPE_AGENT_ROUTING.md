# P3–P7 Prototype Platform Agent Routing

## Authority and current evidence

```text
ROUTING_VERSION: p3-p7-prototype-agent-routing-v1.1-api-acceptance-amended
TRACK: DEMO_PROTOTYPE
STATUS: ACCEPTED_WITH_CC_P3_P7_DEMO_API_08
LOGICAL_MAIN_PROCESS_ROLE: TERRA_HIGH_PRINCIPAL
REQUESTED_MODEL: gpt-5.6-terra
REQUESTED_REASONING_EFFORT: high
PROJECT_TOP_LEVEL_MODEL_OVERRIDE: ABSENT
CURRENT_THREAD_MODEL_RUNTIME_VERIFICATION: NOT_EXPOSED
```

The task-scoped Principal requirement does not authorize repository config to override the Owner's Codex UI model
choice. Evidence always separates requested role/model, static role config and runtime-verified metadata. If the
runtime does not expose the current thread model, the status remains `NOT_EXPOSED`; logical orchestration authority
does not manufacture model provenance.

The current session discovered the eleven base repository roles below through callable Agent types. D00 also contains
successful bounded invocations of Sol review and Luna inventory contexts. No new role is needed for D01-A. A future
configuration change requires a fresh-session discovery smoke before acceptance.

## Agent capability matrix

| Agent ID               | Static model/effort   | Primary role                           | Authorized Demo use                                           | Forbidden in packet                                              | Private input               | Reuse                    |
| ---------------------- | --------------------- | -------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------- | ------------------------ |
| `pm_planner`           | Sol/high              | architecture, math spec, task contract | ADR/schema/algorithm semantics and independent bounded review | product implementation, private discovery, self-acceptance       | redacted only               | `REUSE_WITH_TASK_PACKET` |
| `pm_final_reviewer`    | Sol/high              | final integrated review                | D00/D01/D04/D09/D10/D12 independent review                    | implementation, commits, Gate mutation                           | redacted only               | `REUSE_WITH_TASK_PACKET` |
| `pm_terra_high_worker` | Terra/high            | difficult frozen implementation        | runtime, math, transactions, concurrency, compilers           | architecture or scope invention                                  | exact handoff only          | `REUSE_WITH_TASK_PACKET` |
| `pm_backend_worker`    | Terra/medium          | ordinary backend/domain/API            | services, schemas, raster tools, API integration              | migration authority, private discovery, contract redesign        | denied unless packeted      | `REUSE_WITH_TASK_PACKET` |
| `pm_data_worker`       | Terra/medium          | PostgreSQL/Alembic                     | D01-B implementation under single-writer ownership            | independent schema decisions, formal migration promotion         | denied unless packeted      | `REUSE_WITH_TASK_PACKET` |
| `pm_test_worker`       | Terra/medium          | tests/evaluation                       | PostgreSQL lifecycle, numerical, concurrency and E2E evidence | changing authority to make tests pass                            | redacted/exact handoff only | `REUSE_WITH_TASK_PACKET` |
| `pm_frontend_worker`   | Terra/medium          | unique Web owner                       | D11 Next.js UI and frontend tests after API freeze            | API/schema invention, second Web writer                          | denied                      | `REUSE_WITH_TASK_PACKET` |
| `pm_infra_worker`      | Terra/medium          | Docker/Redis/Celery/tooling            | bounded local topology and CI scaffolding                     | production deployment, public ingress, dependency adoption       | no raw private bytes        | `REUSE_WITH_TASK_PACKET` |
| `pm_security_reviewer` | Terra/high, read-only | security/privacy boundary review       | D06/D11/D12 lightweight independent review                    | implementation and production approval                           | redacted only               | `REUSE_WITH_TASK_PACKET` |
| `pm_luna_worker`       | Luna/medium           | deterministic batch/evidence           | inventory, matrices, fixture aggregation, doc sync            | business decisions, control flow, private discovery              | frozen exact handoff only   | `REUSE_WITH_TASK_PACKET` |
| `pm_fast_worker`       | Spark/medium          | atomic micro task                      | isolated CSS/type/format repair with exact validation         | migration, database, security, facial domain, product invariants | denied                      | `REUSE_WITH_TASK_PACKET` |

System `explorer` or specialized Terra roles cover read-only inventory and ordinary implementation when required. The
Demo branch does not copy the formal worktree's untracked Agent definitions and does not create duplicate `*_v2` roles.

## Selection algorithm

For every delegation Principal identifies the task ID, dependency readiness, collision domain, private/network/data
boundary and validation before choosing the lowest-cost sufficient role:

```text
Spark or Luna sufficient -> do not use Terra
Terra Medium sufficient -> do not use Terra High
Terra High sufficient -> do not use Sol for implementation
Sol -> architecture, math specification, critical review and final Gate only
```

Escalation is based on evidence:

```text
Spark -> Terra Medium: ambiguity, business logic, multi-file or state machine
Luna -> Terra Medium: field/semantic/control-flow decision
Terra Medium -> Terra High: transaction, concurrency, recovery, math, private runtime or complex compiler
Terra High -> Sol review: architecture, ADR/schema authority, invariant, math definition, security boundary or Gate
```

Do not default to Ultra reasoning. Do not generate tasks merely to meet a model-token ratio.

## D00–D12 routing matrix

| Task     | Principal-owned integration                       | Bounded roles                                               | Independent review                                 |
| -------- | ------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| D00      | decision, registry, network/custody               | Terra High runtime; Luna evidence                           | Sol architecture                                   |
| D01-A    | ADR/contract/routing/manifest                     | Luna evidence if needed                                     | Sol architecture                                   |
| D01-B    | schema disposition, migration/models integration  | Data or Terra High single writer; Test                      | Sol schema authority                               |
| D01-C    | contract skeleton/OpenAPI/client authority        | Backend; Test; Luna codegen evidence                        | Sol contract                                       |
| D02      | private custody and bank acceptance               | Terra High; Luna matrix; Test                               | Principal boundary                                 |
| D03      | Worker registration and P3 integration            | Terra High runtime; Backend; Test                           | Sol authority                                      |
| D04-A/B  | frozen math and P4 integration                    | Terra High; Test; Luna numerical matrix                     | separate Sol math review                           |
| D05      | P5 semantics integration                          | Terra High; Backend; Test                                   | Sol semantics                                      |
| D06      | cross-domain self-transfer                        | Terra High; Test; Security                                  | Sol Reference Profile                              |
| D07-A/B  | Operation Graph/editor/Worker                     | Terra High; Backend raster; Test; Luna matrix               | Sol graph review                                   |
| D08      | planner/registry/verifier                         | Terra High; Backend; Test; Luna capability matrix           | Sol tool contract                                  |
| D09      | ledger and Final Save domain provider             | Terra High single ledger writer; Test; Luna matrix          | separate Sol authority review                      |
| D10      | compiler semantics/integration                    | Terra High; Backend; Test; Luna rebuild matrix              | separate Sol determinism review                    |
| API Gate | central router/Job lifecycle/contract integration | Principal wiring; Backend/Test evidence; Luna matrix        | independent Sol integrated-contract review         |
| D11      | Web integration after API freeze                  | one Frontend owner; Backend repair; Test; Luna; Spark micro | Security boundary                                  |
| D12      | final evidence and decision                       | Test; Luna evidence; Security                               | Sol final; second Sol only for unresolved conflict |

The same Sol context may not be both the sole specification author and sole independent reviewer. Worker PASS is
evidence; Principal inspects the actual diff, reruns critical validation and decides `TASK_ACCEPTED`, repair or reject.

## Concurrency and collision policy

```text
DEFAULT_ACTIVE_SUBAGENTS: 1
MAX_ACTIVE_SUBAGENTS: 2
CAN_DELEGATE: false
```

OpenAI's official Codex configuration reference defines
`agents.max_concurrent_threads_per_session` as spawned-agent threads excluding the primary thread. Project config is
therefore `2`, which maps exactly to Principal plus at most two sub-agents. Two may run only when dependencies are
ready, file/database/OpenAPI/private-custody collision domains are disjoint, outputs are independently verifiable and
Principal can review them promptly.

Reference: <https://developers.openai.com/codex/config-reference>

No two Agents may concurrently modify migration, central ORM, OpenAPI, generated TypeScript, Celery registration,
central Demo router, Agent registry, private registry, MEMORY, the same Web page, the same compiler or acceptance state.

`CAN_DELEGATE=false` is mandatory in every packet. It is an explicit authority/stop rule enforced by Principal review;
unless the runtime separately proves tool removal, the document does not claim a physical nested-delegation sandbox.

## Central ownership

Principal retains:

```text
CENTRAL_MIGRATION_OWNER
CENTRAL_ORM_INTEGRATOR
CENTRAL_DEMO_ROUTER_OWNER
CENTRAL_OPENAPI_OWNER
CENTRAL_GENERATED_CLIENT_OWNER
CENTRAL_CELERY_REGISTRATION_OWNER
CENTRAL_JOB_LIFECYCLE_INTEGRATION_OWNER
CENTRAL_AGENT_REGISTRY_OWNER
CENTRAL_PRIVATE_INPUT_REGISTRY_OWNER
CENTRAL_MEMORY_OWNER
CENTRAL_ACCEPTANCE_STATE_OWNER
CENTRAL_GIT_COMMIT_OWNER
```

Sub-agents may modify only explicitly owned files, run tests and propose evidence. They do not commit, push, deploy,
write MEMORY, mutate Gate state or expand architecture.

## Provider and central route ownership

`CC-P3-P7-DEMO-API-08` freezes two mandatory layers:

1. A D02–D10 topic provider owns only its domain/application behavior, transaction semantics, state transitions, typed
   errors and provider-level tests.
2. The Integration Principal alone owns `services/api/src/mirror_api/routers/demo.py`, cross-domain authorization/error
   mapping, central Celery registration, OpenAPI, generated TypeScript and capability-state promotion.

A topic `TASK_ACCEPTED` can advance its route cohort only from `CONTRACT_ONLY_501` to
`DOMAIN_READY_ROUTE_PENDING`. It cannot modify the central files, return public success, flip capability availability or
claim contract completion.

After all required D03–D10 checkpoints are accepted, the Principal executes the non-D-task
`DEMO_API_APPLICATION_INTEGRATION` checkpoint. It centrally implements generic Job query/cancel and the shared Job
state mapping, wires all provider cohorts, verifies all 23 operations and 14 creating-operation idempotency authorities,
and proves PostgreSQL/Redis/Celery execution under denied public egress. Only its `TASK_ACCEPTED` result opens
`DEMO_API_CONTRACT_FREEZE`; only the freeze opens D11.

## Required bounded-task packet

Every task uses the repository `bounded-task-contract` and includes all fields below; `NONE` is explicit where a field
does not apply:

```text
BOOTSTRAP_STATUS: OK
TASK_ID
OBJECTIVE
WHY_DELEGATED
WHY_THIS_AGENT
MODEL
REASONING_EFFORT
BASE_SHA
CURRENT_BRANCH
DEPENDENCIES
INPUTS_AND_ASSUMPTIONS
SCOPE
ALLOWED_FILES_OR_MODULES
EXPECTED_CHANGE
FORBIDDEN_SCOPE
COLLISION_DOMAIN
CAN_DELEGATE: false
PRIVATE_INPUT_HANDOFF
NETWORK_POLICY
DATABASE_POLICY
ACCEPTANCE_CRITERIA
VALIDATION_COMMANDS
SECURITY_NOTES
PRIVACY_NOTES
DATA_NOTES
LICENSE_NOTES
ROLLBACK
OUTPUT_FORMAT
ESCALATION_CONDITION
```

Missing bootstrap blocks the task. Missing private input returns `PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED`; the worker
does not search. A worker reports concise evidence and one of `PASS`, `BLOCKED`, or `FAILED`; it never announces task,
milestone, phase or production acceptance.

## Private input handoff

ADR-049 remains authority. Principal alone resolves the Git-external registry, validates digest/size/authority/scope,
and creates a task-scoped read-only handle. Packets never contain locator, host absolute private path, secret, Prompt,
object key, landmark bytes or image bytes. Sibling/later/nested contexts inherit nothing. If least privilege cannot be
proven, `PRINCIPAL_EXECUTES_SENSITIVE_STEP` and reviewer receives only tracked/redacted evidence.

Network policy is task-specific. D00-A permits only pre-registered approved-source acquisition. D00-B and P3–P7 core
runtime use `PUBLIC_INTERNET_EGRESS_DISABLED` while retaining localhost and Docker internal data plane. Any hidden core
egress is `EXTERNAL_RUNTIME_DEPENDENCY_FOUND`.

## Cost and context discipline

Operational allocation target, not a quota:

```text
SOL: 10-15%
TERRA: 65-75%
LUNA: 15-25%
SPARK: 0-5%
```

Agents receive the task contract, relevant accepted ADR/source/tests/invariants and exact handoff only—not the entire
conversation, private roots or unrelated Phase history. Agent definitions are reusable; task conversations close after
report and Principal review so old assumptions do not silently propagate.

## Configuration validation semantics

- `AGENT_CONFIG_STATIC_VALIDATION` covers TOML parse, unique role IDs, allowed model/reasoning values, no top-level
  Principal override, hard concurrency `2`, required forbidden/private/Spark/Sol boundaries and existing-role retention.
- `AGENT_RUNTIME_ROLE_DISCOVERY` covers roles exposed by the current Codex session; it does not prove each task's model
  selection.
- `RUNTIME_VERIFIED_MODEL` is reported only when the runtime exposes it. Requested or static model names do not count.
- A configuration edit is not accepted until a fresh session discovers the intended roles. Since D01-A changes only
  concurrency and governance, no role-definition discovery delta is asserted.
