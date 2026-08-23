# P3–P7 Algorithmic Prototype Platform Demo Fast Track Contract

## Contract status

```text
CONTRACT_VERSION: p3-p7-demo-fast-track-v1.1
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
TRACK: DEMO_PROTOTYPE
STATUS: ACCEPTED
D00_STATUS: GO
D01_A_STATUS: TASK_ACCEPTED
D01_B_STATUS: TASK_ACCEPTED_CC02
D01_C_STATUS: EXECUTION_READY
D02_D12_STATUS: NOT_STARTED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

Authority: Project Owner revision, ADR-050 and the accepted D00 decision. This contract governs only branch
`codex/p3-p7-core-demo` from exact base `d134517fa97132b180a82c69c617b8f65d3b282e`.

## Scope preservation

### Persistence authority

The Demo Track preserves every logical entity below. D01-B may prove physical reuse, but it may not remove logical
capability, evidence, API, rebuildability or create competing formal/Demo authorities.

| Domain        | Logical entities                                                                                                                                                           |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Session/asset | `demo_actor`, `demo_session`, `demo_synthetic_identity`                                                                                                                    |
| P3            | `demo_face_observation`, `demo_face_observation_repeat`, `demo_baseline_face_model`, `demo_self_state`                                                                     |
| P4            | `demo_question_bank`, `demo_question_pair`, `demo_questionnaire_run`, `demo_questionnaire_step`                                                                            |
| P5            | `demo_desired_delta_profile`, `demo_style_profile`, `demo_identity_constraints`, `demo_self_transfer_run`, `demo_reference_profile`                                        |
| P6            | `demo_editing_session`, `demo_image_version`, `demo_edit_plan`, `demo_edit_operation`, `demo_tool_run`, `demo_verification_result`                                         |
| P7            | `demo_preference_event`, `demo_accepted_visual_episode`, `demo_aesthetic_profile`, `demo_context_compilation`                                                              |
| Cross-cutting | `demo_job_binding`, `demo_command_binding`; stable formal `Asset`, `AssetVariant`, `Job` and `JobAttempt` may be reused without becoming Demo preference/profile authority |

All authorities preserve append-only evidence, immutable originals, versioning, canonical digest, source/result lineage,
strict JSONB payload validation, actor/session ownership, PostgreSQL authority and derived-state rebuildability.

### API authority

The complete `/api/v1/demo/*` surface is retained:

```text
GET  /capabilities
POST /sessions
GET  /sessions/{id}/context
GET  /identities
POST /analyses
GET  /analyses/{id}
POST /questionnaires/runs
GET  /questionnaires/runs/{id}/next
POST /questionnaires/runs/{id}/responses
POST /profiles/compile
GET  /profiles/active
POST /style-feedback
POST /constraints
POST /editing-sessions
POST /editing-sessions/{id}/plans
POST /edit-plans/{id}/executions
GET  /tool-runs/{id}
POST /image-versions/{id}/feedback
POST /image-versions/{id}/restore
POST /profiles/rebuild
GET  /traces/{session_id}
GET  /jobs/{job_id}
POST /jobs/{job_id}/cancel
```

All creating APIs require `Idempotency-Key`. Async work returns owner-bound, unguessable `job_id`; errors retain
`code`, `message`, `request_id`, and `details`. FastAPI/Pydantic → OpenAPI → generated TypeScript remains the only
contract direction. Every route is marked `x-demo-only`; an unimplemented route returns structured
`501 CAPABILITY_NOT_IMPLEMENTED`, never fake success.

### Algorithm authority

- P3: real three-repeat FaceObservation, BaselineFaceModel, SelfState, reliability, uncertainty, routing eligibility and
  unsupported state.
- P4: per-dimension Bayesian pairwise logistic MAP/Laplace, bounded Newton/KKT, integer canonical posterior,
  multi-dimension scheduler, Local Morphological Neighborhood, active routing, snapshots and stop rules; runtime
  generation calls are exactly zero.
- P5: DesiredDelta, StyleProfile, IdentityConstraints, explicit locks/session overrides, self-transfer and Reference
  Profile with evidence precedence and no-response restraint.
- P6: typed planner, crop/rotate/exposure/contrast/saturation/temperature, restore/rollback, at least two screened
  GeometryTransform dimensions, registry, Operation Graph, ToolRun, Verifier, quarantine, ImageVersion and trace.
- P7: digest-chained PreferenceEvent, AcceptedVisualEpisode, Profile/Context Compiler, deterministic rebuild,
  reset/rollback/tombstone/delete propagation and next-session recall.

Makeup is `DEFERRED_WITH_EXPLICIT_REASON`. Generative Editor is `CAPABILITY_UNAVAILABLE`; planner/API/registry/UI and
error semantics still expose those states.

## D00 two-stage contract

### D00-A — CONTROLLED RECOVERY

Bounded acquisition is allowed only when an already accepted runtime/model/dependency artifact is absent and the
exact source/version, approved source, expected checksum, maximum bytes, attempt count, time and output scope are
pre-registered. No arbitrary URL, production Provider call, real-user input or private-byte propagation is allowed.
The artifact is verified after download, stored privately and frozen before D00-B. The local proxy may be used only
inside such a registered acquisition process; it is forbidden from the core runtime environment.

Current result:

```text
D00_A_RESULT: NOT_REQUIRED
ACQUISITION_COUNT: 0
RUNTIME_AND_ASSET_SET: FROZEN
```

### D00-B — OFFLINE CORE EXECUTION

```text
NETWORK_POLICY: PUBLIC_INTERNET_EGRESS_DISABLED
ALL_NETWORK_DISABLED: FALSE
PUBLIC_INTERNET_EGRESS: DENIED
```

Required local paths remain enabled: localhost, Docker internal network, PostgreSQL, Redis, Celery, Web↔API and private
object storage. M3 Vision, M4 GeometryTransform and the fixed-base API/Web/Worker/data topology have all been executed
in controlled public-egress-denied windows. A runtime public-network attempt is
`EXTERNAL_RUNTIME_DEPENDENCY_FOUND` and fails closed.

```text
D00_B_RESULT: PASS
D00_RESULT: GO
```

This result authorizes D01-A only. It does not replace D02 pair QA or D03–D12 integration evidence.

## Worktree and formal isolation

```text
DEMO_BRANCH: codex/p3-p7-core-demo
DEMO_WORKTREE: D:\p-p3-p7-core-demo
DEMO_BRANCH_POINT_SHA: d134517fa97132b180a82c69c617b8f65d3b282e
PROTOTYPE_MIGRATION: demo_0001_p3_p7_core
FORMAL_DOWN_REVISION: 0014_m5_eval_authority
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

- Formal worktree dirty bytes and protected `.tmp/` are excluded.
- D01-A and D12 record formal before/after evidence. An external formal advance is recorded, never relabeled as Demo
  work. `FORMAL_WORKTREE_UNCHANGED_BY_DEMO_TASK` is the attribution Gate; a literal HEAD-stability claim is made only
  when observed.
- `requirements.lock` replays only the accepted `pip==26.2.1` line from source SHA `b179c193...`; no commit cherry-pick.
- Before the first push, Principal must verify repository visibility read-only. Unknown or changed visibility stops the
  push under R-DEMO-15.

## D01 internal checkpoints

### D01-A — Worktree and Demo authority

Owned outputs: ADR-050, this contract, risk register, agent routing contract, redacted pre-existing-worktree manifest,
environment/network/private boundaries and the bounded pip lock repair.

Exit requires:

```text
DEMO_WORKTREE_CLEAN_AT_ENTRY: PASS
FORMAL_WORKTREE_UNCHANGED_BY_DEMO_TASK: PASS
BASE_SHA_EXACT: PASS
PRIVATE_RUNTIME_LOAD_FROM_OFFICIAL_WORKTREE: PASS
AGENT_CONFIG_VALIDATION: PASS | CONDITIONAL_WITH_EXPLICIT_NEGATIVE_EVIDENCE
D01_A_INDEPENDENT_REVIEW: PASS
```

No migration, ORM, public Demo API or Web implementation may begin before Principal accepts D01-A.

### D01-B — Schema authority

Freeze `DEMO_SCHEMA_REUSE_MATRIX`, then implement `demo_0001_p3_p7_core`, ORM, `demo_job_binding`, ownership,
append-only and migration lifecycle. The post-acceptance D01-C review reopened D01-B through
`CC-P3-P7-DEMO-D01B-02`: the forward prototype migration `demo_0002_p3_p7_command_authority.py` adds immutable
`demo_command_binding` authority for synchronous creating commands. Migration and central models have one writer.
Populated evidence downgrade fails closed at every prototype revision.

### D01-C — API contract skeleton

Implement all schemas/routes as real contracts, `x-demo-only`, idempotency/job/status contracts, OpenAPI and generated
TypeScript. Principal is the only OpenAPI/client integrator. Routes may remain 501 until their owning D03–D10 task is
implemented; D11 waits for `DEMO_API_CONTRACT_FREEZE`.

### Demo CI evidence isolation

Formal Phase 1 and P2 evidence generators keep `0014_m5_eval_authority` as their single expected migration head. They
must not be weakened to accept a branch-local prototype revision and must not emit formal evidence from the Demo head.
On the fixed `codex/p3-p7-core-demo` branch, and on pull requests whose head is that branch, CI instead verifies the
single Demo head and its two explicit ancestry edges, then uploads a separate boundary artifact containing:

```text
TRACK: DEMO_PROTOTYPE
DEMO_MIGRATION_HEAD: demo_0002_p3_p7_command_auth
FORMAL_EVIDENCE_GENERATORS: NOT_RUN_ON_PROTOTYPE_HEAD
FORMAL_HEAD_AUTHORITY: 0014_m5_eval_authority
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

All Python, PostgreSQL lifecycle, Celery, TypeScript, browser, contract-drift, dependency, SBOM, Docker and Gitleaks
Gates continue to run. This conditional evidence routing is branch-local CI compatibility, not a formal Gate waiver.
The first same-SHA run exposing the mismatch was `32631450833`: all executable quality/integration jobs before the
formal evidence generator passed, while the generator correctly rejected the Demo head.

## Task DAG and collision rules

```text
D00 -> D01-A -> D01-B -> D01-C

D01-B -> D04-A posterior domain
D01-B -> D07-A Operation Graph domain
D01-B -> D09 ledger domain

D00 + D01-C -> D02
D02 + D00 Vision Gate -> D03
D02 + D03 + D04-A -> D04-B
D03 + D04-B -> D05
D02 + D03 + D07-A + D00 M4 Gate -> D07-B
D05 + D07-B + D09 -> D06
D05 + D07-B -> D08
D05 + D06 + D09 -> D10
D03-D10 accepted -> DEMO_API_CONTRACT_FREEZE -> D11 -> D12
```

Principal plus at most two active sub-agents; normal limit is one. Two are allowed only for ready, independently
verifiable, non-colliding scopes. No concurrent writers for migration, models, OpenAPI, generated client, Celery
registration, Agent registry, private registry, MEMORY, a Web page, compiler or acceptance state.

Every packet includes `CAN_DELEGATE=false`. Worker output is evidence only; Principal inspects actual diff and reruns
critical validation. D00, D01-A, D01-B, D04, D09, D10 and D12 require independent review.

## Private custody

Authority remains ADR-049 and the Principal-managed registry. Each private record contains opaque output ID, creating
task, opaque locator, expected/actual digest, byte size, authority, allowed tasks, retention, custody and recovery
status. Locator and bytes never enter Git. Recovery begins only from registry/receipt/task-owned root and never from
disk scanning. A sub-agent receives only a task-scoped read-only handle; no sibling, later task or nested agent inherits
access. If least privilege cannot be proven, Principal executes the sensitive step.

## Actor ownership, idempotency and async state

`demo_job_binding` is the immutable bridge from formal Job to Demo actor/session/entity authority for asynchronous
commands. `demo_command_binding` is the distinct immutable response/idempotency bridge for synchronous persistence
commands and never creates a fake Job. GET and mutation routes verify actor/session ownership; unguessable IDs are not
authorization.

Idempotency uniqueness is:

```text
(demo_actor_id, endpoint_operation, idempotency_key_hash)
```

Same key/same semantic digest returns the same authority; same key/different digest returns
`409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`. PostgreSQL unique constraints in the matching asynchronous or
synchronous binding authority decide concurrent winners; Worker redelivery cannot duplicate Event, ToolRun,
Verification, ImageVersion or Profile.

```text
PENDING -> RUNNING | CANCELLED
RUNNING -> COMPLETED | REJECTED | FAILED | CANCELLED
terminal -> no transition
```

Execution/storage/algorithm errors are `FAILED`; eligibility/constraint/verifier outcomes are `REJECTED`. Completion
occurs only after authority and successful result persist atomically. Retry creates a new JobAttempt.

## Evidence and final claims

Every mandatory D12 Gate is one of `PASS`, `FAIL`, `BLOCKED`, or `NOT_VERIFIED`; missing evidence is never PASS. Evidence
binds final Demo SHA, migration head, algorithm/config digest, runtime/asset manifest and environment.

Allowed final conclusion shape:

```text
ALGORITHMIC_PROTOTYPE_PLATFORM: PASS | FAIL
LOCAL_WEB_AGENT: PASS | FAIL

REAL_USER_VALIDITY: NOT_EVALUATED
PREFERENCE_MODEL_GENERALIZATION: NOT_EVALUATED
REAL_FACE_MEASUREMENT_VALIDITY: NOT_EVALUATED
REAL_USER_IDENTITY_PRESERVATION: NOT_EVALUATED
PRODUCT_MARKET_VALIDATION: NOT_EVALUATED

PRODUCTION_SECURITY: DEFERRED_FOR_FORMAL_PHASE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

Demo may prove real local execution, persistence, evidence, editing, rebuild, recall and Web operability only. It may
not prove real-user validity, real-face generalization, product aesthetics, biometric identity preservation or
production readiness.
