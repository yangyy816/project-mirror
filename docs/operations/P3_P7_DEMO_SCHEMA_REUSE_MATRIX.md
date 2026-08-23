# P3–P7 Demo Schema Reuse Matrix

## Checkpoint status

```text
MATRIX_VERSION: p3-p7-demo-schema-reuse-v1
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
BASE_SHA: d134517fa97132b180a82c69c617b8f65d3b282e
D01_A: TASK_ACCEPTED
D01_B: READY_FOR_INDEPENDENT_IMPLEMENTATION_REVIEW
INDEPENDENT_SOL_SCHEMA_REVIEW: PASS
INDEPENDENT_SOL_REVIEWED_MATRIX_SHA256: 382fb6ba3ef5059d4089fcb4f3b149ba0d65fedd43d5e4b11c3e4e55054544bc
PRINCIPAL_MATRIX_DISPOSITION: ACCEPTED_FOR_D01_B_IMPLEMENTATION
MIGRATION_ORM_WRITES_AT_MATRIX_ACCEPTANCE: NOT_STARTED
MIGRATION_ORM_IMPLEMENTATION: COMPLETE
INDEPENDENT_SOL_IMPLEMENTATION_REVIEW: PENDING
FORMAL_SCHEMA_CHANGE: FORBIDDEN
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This matrix freezes physical authority before any Demo migration or ORM implementation. It preserves all 26 planned
logical entities and adds `demo_job_binding`. Similar formal names are not semantic equivalence. The Demo track may
reference stable formal byte, lineage and execution authorities, but it may not turn formal P3–P7 profile,
questionnaire, editing or preference tables into prototype authority.

## Global physical disposition

```text
DEMO_LOGICAL_ENTITY_COUNT: 26
CROSS_CUTTING_ENTITY_COUNT: 1
NEW_PROTOTYPE_TABLE_COUNT: 27

FORMAL_ASSET_AUTHORITY_REUSE: Asset, AssetVariant
FORMAL_EXECUTION_AUTHORITY_REUSE: Job, JobAttempt
FORMAL_SYNTHETIC_IDENTITY_REUSE: REFERENCE_ONLY_ADMISSION
FORMAL_PROFILE_QUESTIONNAIRE_EDITING_PREFERENCE_REUSE: FORBIDDEN_AS_DEMO_AUTHORITY
FORMAL_TABLE_DDL_CHANGE: FORBIDDEN
```

`Asset` continues to own immutable bytes and storage facts. `AssetVariant` continues to own formal source/result byte
lineage. `Job` and `JobAttempt` continue to own execution, attempt, lease and terminal result facts. A Demo table owns
all Demo actor/session/entity, semantic idempotency and P3–P7 evidence facts. No formal table receives a Demo-only
column, trigger, constraint, index, current pointer or preference/profile payload.

## Five mandatory preservation proofs

| Proof                           | Design result | Implementation result            | Reason                                                                                      |
| ------------------------------- | ------------- | -------------------------------- | ------------------------------------------------------------------------------------------- |
| `NO_CAPABILITY_LOSS`            | `PASS`        | `PASS_FOR_REMEDIATION_CANDIDATE` | All 26 entities plus the Job bridge retain one tested authority.                            |
| `NO_EVIDENCE_LOSS`              | `PASS`        | `PASS_FOR_REMEDIATION_CANDIDATE` | Admission snapshots and the complete image execution chain are enforced.                    |
| `NO_API_LOSS`                   | `PASS`        | `PASS_FOR_REMEDIATION_CANDIDATE` | The physical graph represents every frozen API authority without implementing D01-C routes. |
| `NO_REBUILDABILITY_LOSS`        | `PASS`        | `PASS_FOR_REMEDIATION_CANDIDATE` | Append-only evidence, lineage, watermarks and exact digests remain reconstructable.         |
| `NO_FORMAL_AUTHORITY_POLLUTION` | `PASS`        | `PASS_FOR_REMEDIATION_CANDIDATE` | Non-Demo table DDL is byte-identical at 0014 and Demo head.                                 |

Design `PASS` authorizes implementation only. D01-B remains incomplete until real PostgreSQL migration, invariants,
concurrency, populated downgrade, ORM consistency and independent review pass.

## Frozen cross-cutting schema rules

### Canonical authority

`demo-canonical-json-v1` is the only Demo digest envelope:

- UTF-8 JSON, lexicographically sorted object keys and no insignificant whitespace;
- arrays preserve declared semantic order; set-like arrays are sorted by canonical element bytes before persistence;
- digest-authoritative numerics use integers with declared units such as ppm, pixels or milliseconds;
- raw binary float, NaN, infinity, database wall clock and unordered collection are forbidden digest inputs; JSONB
  normalization collapses negative zero to integer zero, so it can never remain a distinct authority representation;
- authority timestamps are normalized UTC RFC 3339 with six fractional digits and `Z`; audit-only `created_at` and
  execution duration do not enter a digest unless the contract explicitly names the timestamp as request authority;
- IDs are 32 lowercase hexadecimal characters and SHA-256 digests are 64 lowercase hexadecimal characters;
- each content digest includes schema version, algorithm/compiler/config versions and the complete semantic payload.

All new payload columns are PostgreSQL `JSONB`. Database checks use `jsonb_typeof`, required-key/type checks, finite
allowlists and mutually exclusive shape checks. Pydantic validation is additional defense, not the database authority.

PostgreSQL must verify every authoritative digest on `INSERT`; shape-only validation is insufficient. The migration
installs an immutable, recursive `mirror_demo_canonical_json(jsonb) -> text` function with these exact rules:

- objects are serialized as `{` plus comma-separated key/value pairs plus `}`; keys use PostgreSQL JSON string escaping
  and are ordered by `key COLLATE "C"`;
- arrays preserve ordinal position and are serialized without whitespace;
- strings use PostgreSQL JSON string escaping; booleans and `null` use their lowercase JSON spellings;
- numeric leaves after JSONB normalization are accepted only when their JSON text matches `0|-?[1-9][0-9]*`;
  fractional values fail, while lexically different inputs that normalize to an integer have only that integer as
  authority;
- the digest bytes are UTF-8 bytes of
  `schema_version || E'\\n' || mirror_demo_canonical_json(canonical_payload)`;
- `content_digest` must equal lowercase `encode(sha256(digest_bytes), 'hex')`.

A shared `BEFORE INSERT OR UPDATE OR DELETE` trigger recomputes and compares that digest on all 27 tables, rejects
`UPDATE`/`DELETE` according to the table classification below, and rejects a non-object payload. Table-specific insert
guards additionally require the canonical payload to contain every digest-authoritative scalar/FK and to equal the
corresponding structured columns. Direct-SQL tests must prove that a valid-shaped payload with a wrong digest, a
structured-column/payload mismatch and a non-integer numeric leaf fail closed, and that `-0` produces exactly the same
persisted canonical payload and digest as integer `0` rather than a second authority.

### Ownership and immutability

- `demo_sessions` exposes `UNIQUE (id, actor_id)`; owner-scoped descendants use composite foreign keys when a direct
  chain is available.
- Opaque IDs never substitute for owner/session authorization.
- Immutable evidence, version, configuration, plan, operation, tool result, verifier result and ledger rows have
  PostgreSQL triggers rejecting `UPDATE` and `DELETE`, including direct SQL.
- Runtime progress is represented by formal Job/JobAttempt or append-only step/event rows. No mutable Demo
  `active_*`/`current_*` pointer becomes a second authority.
- Reset, rollback, rejection, cancellation and deletion are forward evidence. Rollback creates a new version; it never
  overwrites an older version.

Every table has one frozen mutation class:

| Mutation class                            | Logical entities                                                                                                                                                                                                                                                                                                                                                                                              | PostgreSQL behavior                                                                                                                                                       |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TERMINAL_TRANSITION_HEADER`              | `demo_actor`, `demo_session`, `demo_editing_session`                                                                                                                                                                                                                                                                                                                                                          | Reject `DELETE`; permit only one-way `NULL -> timestamp` terminal fields while every other authority column remains byte-equivalent.                                      |
| `IMMUTABLE_EVIDENCE_OR_CONFIG`            | `demo_synthetic_identity`, `demo_face_observation`, `demo_face_observation_repeat`, `demo_question_bank`, `demo_question_pair`, `demo_questionnaire_run`, `demo_questionnaire_step`, `demo_identity_constraints`, `demo_self_transfer_run`, `demo_edit_plan`, `demo_edit_operation`, `demo_tool_run`, `demo_verification_result`, `demo_preference_event`, `demo_accepted_visual_episode`, `demo_job_binding` | Reject every `UPDATE` and `DELETE`; correction, revocation, retry, rollback and deletion intent are new immutable rows/events.                                            |
| `IMMUTABLE_DERIVED_TOMBSTONED`            | `demo_baseline_face_model`, `demo_self_state`, `demo_desired_delta_profile`, `demo_style_profile`, `demo_reference_profile`, `demo_image_version`, `demo_aesthetic_profile`, `demo_context_compilation`                                                                                                                                                                                                       | Reject every `UPDATE` and `DELETE`; an append-only `demo_preference_event` invalidates the target and a rebuild creates a new version/generation.                         |
| `REPLACEABLE_DERIVED_WITH_GUARDED_DELETE` | none in prototype schema v1                                                                                                                                                                                                                                                                                                                                                                                   | No v1 table may use an implicit wall clock or unrecorded cleanup as delete authority. Any future physical cleanup requires explicit change control and conversion policy. |

For `demo_session` and `demo_editing_session`, `closed_at` may transition once and `tombstoned_at` may transition once
at or after closure; `demo_actor` permits only `tombstoned_at`. These timestamps are audit/terminal evidence and must be
included in the transition event digest, not retroactively inserted into the original creation digest. TTL and
`expires_at` affect eligibility only; they never authorize silent row deletion. A `DELETE` API appends a typed
`TOMBSTONE`/`DELETE` event, removes the target from compiler inputs, and creates replacement derived generations while
retaining prototype evidence rows.

For derived invalidation, `demo_preference_events.target_type` is limited to `BASELINE_FACE_MODEL`, `SELF_STATE`,
`DESIRED_DELTA_PROFILE`, `STYLE_PROFILE`, `REFERENCE_PROFILE`, `IMAGE_VERSION`, `AESTHETIC_PROFILE` and
`CONTEXT_COMPILATION`; a fixed `CASE` trigger resolves the target table and proves the same actor ownership. `RESET`
targets `DEMO_ACTOR` plus an explicit event-sequence watermark. An accepted event never authorizes SQL `DELETE`; it
only removes the target from future compiler inputs and requires a new immutable generation.

### Formal row namespaces

```text
DEMO_JOB_TYPE_PREFIX: demo_p3_p7.
DEMO_ASSET_VARIANT_TYPE_PREFIX: demo_p3_p7_
FORMAL_JOB_PAYLOAD: EMPTY_OR_REFERENCE_ONLY
```

`demo_job_bindings` uniquely owns `(demo_actor_id, endpoint_operation, idempotency_key_hash)`, request semantic digest
and typed target binding. The corresponding formal Job idempotency hash is derived with the actor and operation
namespace so the existing global uniqueness constraint cannot collide across Demo actors/operations. Same key and
same digest reloads the winner; same key and different digest is a 409 conflict.

The target-kind allowlist and physical ownership resolution are frozen as follows. A target must exist before the
binding becomes visible; a newly created request target, formal Job and binding are inserted atomically in one
transaction.

| `target_type`       | Target table              | Required ownership proof                                                                                |
| ------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------- |
| `DEMO_ACTOR`        | `demo_actors`             | `target_id = demo_actor_id`; an optional session must belong to that actor.                             |
| `DEMO_SESSION`      | `demo_sessions`           | `target_id = demo_session_id` and composite `(demo_session_id, demo_actor_id)` matches.                 |
| `FACE_OBSERVATION`  | `demo_face_observations`  | target row has the same actor and session.                                                              |
| `QUESTIONNAIRE_RUN` | `demo_questionnaire_runs` | target row has the same actor and session.                                                              |
| `SELF_TRANSFER_RUN` | `demo_self_transfer_runs` | target row has the same actor and session.                                                              |
| `EDITING_SESSION`   | `demo_editing_sessions`   | target row has the same actor and Demo session.                                                         |
| `IMAGE_VERSION`     | `demo_image_versions`     | ownership resolves through its editing session to the same actor/session.                               |
| `EDIT_PLAN`         | `demo_edit_plans`         | ownership resolves through its editing session to the same actor/session.                               |
| `EDIT_OPERATION`    | `demo_edit_operations`    | ownership resolves through plan -> editing session to the same actor/session.                           |
| `TOOL_RUN`          | `demo_tool_runs`          | ownership resolves through operation -> plan -> editing session and its binding Job matches this actor. |

The endpoint-operation mapping is also fixed:

| `endpoint_operation`       | Required `target_type` | Target lifecycle point                                                                                     |
| -------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------- |
| `analysis.create`          | `FACE_OBSERVATION`     | immutable request header exists before the Job is visible; repeats/model/SelfState are completion results. |
| `questionnaire.run.create` | `QUESTIONNAIRE_RUN`    | immutable run header exists before the Job is visible; steps are append-only.                              |
| `profile.compile`          | `DEMO_ACTOR`           | actor exists; result Profile rows reference this binding and compiler watermark.                           |
| `editing_session.create`   | `EDITING_SESSION`      | immutable editing-session request exists before the Job is visible.                                        |
| `edit_plan.create`         | `EDIT_PLAN`            | immutable plan request/authority exists before the Job is visible.                                         |
| `edit_plan.execute`        | `EDIT_PLAN`            | accepted input plan exists; ToolRun/ImageVersion results reference this binding.                           |
| `image_version.restore`    | `IMAGE_VERSION`        | source version exists; restore creates a new ImageVersion.                                                 |
| `profile.rebuild`          | `DEMO_ACTOR`           | actor exists; rebuilt generations reference the binding and frozen watermark.                              |
| `self_transfer.execute`    | `SELF_TRANSFER_RUN`    | immutable self-transfer request exists; result evidence references the binding.                            |
| `tool.verify`              | `TOOL_RUN`             | immutable ToolRun exists; VerificationResult references the binding/Job.                                   |
| `context.compile`          | `DEMO_SESSION`         | actor-owned session exists; ContextCompilation result references the binding.                              |

At binding insert, the formal Job must have `job_type = 'demo_p3_p7.' || endpoint_operation`, owner and ingestion
fields null, `status = 'PENDING'`, no result, and an empty or frozen reference-only payload. The binding trigger rejects
all other shapes and validates the exact target table by a fixed `CASE` statement. Terminal processing locks the Job,
binding and target. `COMPLETED` is committed only in the same transaction as the required result authority;
`REJECTED`, `FAILED` and `CANCELLED` require a non-empty result code and may not publish a success result. A retry adds
a `JobAttempt`; it never changes a terminal Job back to pending. Because `demo_0001` may not add a trigger to the formal
`jobs` table, the terminal transaction protocol is enforced by the single Demo job application service and verified by
D01-C/D03-D10 state-machine tests plus D12 reconciliation queries; D01-B must not falsely claim a formal-table trigger.

### Migration and downgrade

```text
MIGRATION_FILE: services/api/migrations/versions/demo_0001_p3_p7_core.py
REVISION: demo_0001_p3_p7_core
DOWN_REVISION: 0014_m5_eval_authority
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

Populated downgrade fails before dropping any object when any `demo_*` table is non-empty, any Job uses the
`demo_p3_p7.` namespace, a JobAttempt belongs to such a Job, or any AssetVariant uses `demo_p3_p7_`. A failed downgrade
must leave the revision, rows, digests, functions and triggers unchanged. Empty downgrade removes objects in reverse
dependency order. Formal promotion always uses a new forward migration from the then-current formal head and an
explicit ID/digest conversion strategy.

## Entity matrix

The following repeated records contain every mandatory matrix field. `FWD_CONVERSION` means a future formal change
control creates new forward schema and explicit ID/digest mapping; it never cherry-picks this prototype revision.

### Session and asset authority

#### `demo_actor`

```text
LOGICAL_ENTITY: demo_actor
EXISTING_FORMAL_ENTITY: User
SEMANTIC_EQUIVALENCE: NONE
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: demo credential proof, actor kind, lifecycle tombstone
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_actors
AUTHORITY_OWNER: Demo actor registry
OWNER_BINDING: root owner authority
APPEND_ONLY_MECHANISM: immutable identity plus terminal tombstone transition
DIGEST_INPUTS: schema, actor kind, credential key id, authority creation instant
DELETE_OR_TOMBSTONE_SEMANTICS: terminal actor tombstone; evidence remains auditable
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_actors
PROMOTION_STRATEGY: FWD_CONVERSION; never convert into an existing formal User implicitly
DECISION_EVIDENCE: ADR-050, Fast Track Contract, formal User semantics
```

#### `demo_session`

```text
LOGICAL_ENTITY: demo_session
EXISTING_FORMAL_ENTITY: UserSession, EditingSession
SEMANTIC_EQUIVALENCE: NONE
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: cross-P3-P7 context, actor ownership, expiry, close/tombstone
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_sessions
AUTHORITY_OWNER: Demo session registry
OWNER_BINDING: composite (id, demo_actor_id)
APPEND_ONLY_MECHANISM: immutable configuration plus terminal close/tombstone
DIGEST_INPUTS: actor, session configuration, expiry, context seed
DELETE_OR_TOMBSTONE_SEMANTICS: close/tombstone without cascading evidence deletion
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_sessions
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: ADR-050, Fast Track Contract
```

#### `demo_synthetic_identity`

```text
LOGICAL_ENTITY: demo_synthetic_identity
EXISTING_FORMAL_ENTITY: SyntheticIdentity
SEMANTIC_EQUIVALENCE: PARTIAL; formal owns canonical Asset, QA, adult attestation and provenance
REUSE_POSSIBLE: REFERENCE_ONLY
EXTENSION_REQUIRED: Demo admission, frozen canonical Asset/QA snapshot, latest-row eligibility and admission config digest
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_synthetic_identities for admission only
AUTHORITY_OWNER: split by field; formal identity facts remain formal
OWNER_BINDING: global Demo corpus; no actor binding
APPEND_ONLY_MECHANISM: immutable actor-independent admission rows; advisory-serialized revocation/re-admission is a new row
DIGEST_INPUTS: formal identity id, canonical Asset id/SHA, accepted QA run/deterministic snapshot digest, sequence/action/config/supersedes
DELETE_OR_TOMBSTONE_SEMANTICS: append admission revocation; never rewrite formal identity
FORMAL_AUTHORITY_POLLUTION_RISK: MEDIUM
MIGRATION_OBJECT: demo_synthetic_identities with RESTRICT FK to synthetic_identities
PROMOTION_STRATEGY: FWD_CONVERSION of admission metadata only
DECISION_EVIDENCE: ADR-050, Fast Track Contract, formal SyntheticIdentity authority, P3_P7_D01_B_CC_01
```

### P3 authority

#### `demo_face_observation`

```text
LOGICAL_ENTITY: demo_face_observation
EXISTING_FORMAL_ENTITY: BaselineFaceModel, SyntheticQARun
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: formal Asset reference only
EXTENSION_REQUIRED: three-repeat contract, runtime/config, eligibility and unsupported result
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_face_observations
AUTHORITY_OWNER: Demo P3 observation evidence
OWNER_BINDING: actor, session, optional Demo identity and source Asset
APPEND_ONLY_MECHANISM: immutable observation header
DIGEST_INPUTS: owner/session/identity, source Asset SHA, analyzer/runtime/config, repeat count
DELETE_OR_TOMBSTONE_SEMANTICS: forward tombstone; Asset deletion remains formal
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_face_observations
PROMOTION_STRATEGY: FWD_CONVERSION by observation digest
DECISION_EVIDENCE: Fast Track Contract P3, formal baseline/QA models
```

#### `demo_face_observation_repeat`

```text
LOGICAL_ENTITY: demo_face_observation_repeat
EXISTING_FORMAL_ENTITY: SyntheticQARun, SyntheticQAMeasurement
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: NO ROW REUSE
EXTENSION_REQUIRED: repeat index, 478 normalized landmarks, pose, quality and fixed measurements
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_face_observation_repeats
AUTHORITY_OWNER: Demo P3 repeat evidence
OWNER_BINDING: parent observation owner chain
APPEND_ONLY_MECHANISM: immutable; unique (observation_id, repeat_index)
DIGEST_INPUTS: observation, repeat, runtime/model manifest, landmarks, pose and measurements
DELETE_OR_TOMBSTONE_SEMANTICS: invalidation via parent/source tombstone
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_face_observation_repeats
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P3, D00 M3 contract
```

#### `demo_baseline_face_model`

```text
LOGICAL_ENTITY: demo_baseline_face_model
EXISTING_FORMAL_ENTITY: BaselineFaceModel, BaselineMeasurement
SEMANTIC_EQUIVALENCE: PARTIAL; formal lacks Demo repeat/reliability authority
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: repeat aggregation, reliability, uncertainty and unsupported reason
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_baseline_face_models
AUTHORITY_OWNER: Demo derived P3 authority
OWNER_BINDING: actor, session and observation
APPEND_ONLY_MECHANISM: versioned rebuildable generation; immutable rows
DIGEST_INPUTS: ordered repeat digests, aggregation/measurement versions and fixed metrics
DELETE_OR_TOMBSTONE_SEMANTICS: append typed tombstone event, exclude this generation and rebuild from remaining valid repeats; physical DELETE forbidden
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH IF FORMAL REUSED
MIGRATION_OBJECT: demo_baseline_face_models
PROMOTION_STRATEGY: FWD_CONVERSION; do not write formal baseline
DECISION_EVIDENCE: ADR-050, formal BaselineFaceModel semantics
```

#### `demo_self_state`

```text
LOGICAL_ENTITY: demo_self_state
EXISTING_FORMAL_ENTITY: SelfState, BaselineMorphologyDescriptor
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: canonical fixed geometry, reliability, uncertainty and routing eligibility
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_self_states
AUTHORITY_OWNER: Demo derived P3 authority
OWNER_BINDING: actor and baseline version
APPEND_ONLY_MECHANISM: versioned rebuildable generation; immutable rows
DIGEST_INPUTS: baseline digest, ontology/derivation versions, measurements/reliability/uncertainty
DELETE_OR_TOMBSTONE_SEMANTICS: append typed tombstone event, exclude this generation and rebuild after evidence tombstone; physical DELETE forbidden
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH IF FORMAL REUSED
MIGRATION_OBJECT: demo_self_states
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: ADR-050, Fast Track Contract P3, formal SelfState semantics
```

### P4 authority

#### `demo_question_bank`

```text
LOGICAL_ENTITY: demo_question_bank
EXISTING_FORMAL_ENTITY: QuestionBankVersion, QuestionTemplate
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: formal Asset references only
EXTENSION_REQUIRED: Bayesian, scheduler, stopping and pair-manifest configuration
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_question_banks
AUTHORITY_OWNER: Demo P4 immutable configuration
OWNER_BINDING: global versioned bank
APPEND_ONLY_MECHANISM: immutable; configuration changes create a new bank version
DIGEST_INPUTS: schema/config/algorithm/routing/stop versions and ordered pair digests
DELETE_OR_TOMBSTONE_SEMANTICS: append revocation/supersession; no mutation
FORMAL_AUTHORITY_POLLUTION_RISK: MEDIUM
MIGRATION_OBJECT: demo_question_banks
PROMOTION_STRATEGY: FWD_CONVERSION with separate formal qualification
DECISION_EVIDENCE: Fast Track Contract P4, formal questionnaire models
```

#### `demo_question_pair`

```text
LOGICAL_ENTITY: demo_question_pair
EXISTING_FORMAL_ENTITY: QuestionInstance, QuestionAsset, AssetVariant
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: formal Asset and AssetVariant references only
EXTENSION_REQUIRED: same-source opposite direction, magnitude, QA and pair lineage
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_question_pairs
AUTHORITY_OWNER: Demo P4 stimulus authority
OWNER_BINDING: bank and Demo synthetic identity
APPEND_ONLY_MECHANISM: immutable pair rows
DIGEST_INPUTS: bank/identity/source/left/right checksums, variant lineage, dimension/magnitude/QA
DELETE_OR_TOMBSTONE_SEMANTICS: bank/pair tombstone; formal Assets remain formal
FORMAL_AUTHORITY_POLLUTION_RISK: MEDIUM
MIGRATION_OBJECT: demo_question_pairs with formal Asset/AssetVariant FKs
PROMOTION_STRATEGY: retain formal Assets; FWD_CONVERSION of pair metadata
DECISION_EVIDENCE: Fast Track Contract P4, formal Asset lineage
```

#### `demo_questionnaire_run`

```text
LOGICAL_ENTITY: demo_questionnaire_run
EXISTING_FORMAL_ENTITY: QuestionnaireRun
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: Demo actor/session, integer posterior config and evidence watermark
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_questionnaire_runs
AUTHORITY_OWNER: Demo P4 run authority
OWNER_BINDING: actor, session, bank and SelfState
APPEND_ONLY_MECHANISM: immutable header; progress derives from append-only steps
DIGEST_INPUTS: owner, bank/SelfState digests, algorithm/config and seed
DELETE_OR_TOMBSTONE_SEMANTICS: forward tombstone; steps remain auditable
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH IF FORMAL REUSED
MIGRATION_OBJECT: demo_questionnaire_runs
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P4, formal QuestionnaireRun semantics
```

#### `demo_questionnaire_step`

```text
LOGICAL_ENTITY: demo_questionnaire_step
EXISTING_FORMAL_ENTITY: QuestionInstance, QuestionResponse, QuestionnaireRoute
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: PRESENTED/RESPONDED/STOP event, route/posterior snapshots and stop evidence
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_questionnaire_steps
AUTHORITY_OWNER: Demo P4 answer/routing evidence
OWNER_BINDING: questionnaire run owner chain
APPEND_ONLY_MECHANISM: unique run event sequence and immutable event rows
DIGEST_INPUTS: run/event/pair, routing components, response, posterior input/output and scheduler version
DELETE_OR_TOMBSTONE_SEMANTICS: corrections and invalidation are new events
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_questionnaire_steps
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P4 numerical/routing rules
```

### P5 authority

#### `demo_desired_delta_profile`

```text
LOGICAL_ENTITY: demo_desired_delta_profile
EXISTING_FORMAL_ENTITY: DesiredDeltaProfileVersion, DesiredDeltaDimension
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: fixed posterior units, evidence precedence, locks and compiler watermark
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_desired_delta_profiles
AUTHORITY_OWNER: Demo P5 derived authority
OWNER_BINDING: actor and SelfState version
APPEND_ONLY_MECHANISM: versioned rebuildable immutable generations
DIGEST_INPUTS: SelfState and ordered questionnaire/self-transfer/explicit evidence, compiler and dimensions
DELETE_OR_TOMBSTONE_SEMANTICS: append typed tombstone event, exclude this generation and rebuild; physical DELETE forbidden
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH IF FORMAL REUSED
MIGRATION_OBJECT: demo_desired_delta_profiles
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: ADR-050, Fast Track Contract P5, formal desired-delta semantics
```

#### `demo_style_profile`

```text
LOGICAL_ENTITY: demo_style_profile
EXISTING_FORMAL_ENTITY: StyleProfileVersion
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: explicit context, negative evidence, compiler watermark and digest
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_style_profiles
AUTHORITY_OWNER: Demo P5 derived authority
OWNER_BINDING: actor and profile version
APPEND_ONLY_MECHANISM: versioned rebuildable immutable generations
DIGEST_INPUTS: ordered evidence, compiler, preferences, negatives and confidence integers
DELETE_OR_TOMBSTONE_SEMANTICS: append typed tombstone event, exclude this generation and rebuild; physical DELETE forbidden
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH IF FORMAL REUSED
MIGRATION_OBJECT: demo_style_profiles
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P5, formal StyleProfileVersion
```

#### `demo_identity_constraints`

```text
LOGICAL_ENTITY: demo_identity_constraints
EXISTING_FORMAL_ENTITY: IdentityConstraintVersion
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: explicit locks, unlocks, prohibited operations and session override precedence
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_identity_constraints
AUTHORITY_OWNER: Demo P5 explicit/version authority
OWNER_BINDING: actor, optional session and SelfState
APPEND_ONLY_MECHANISM: immutable versions; explicit unlock/override creates new evidence/version
DIGEST_INPUTS: owner/SelfState, source events, locks/bounds/prohibitions and schema version
DELETE_OR_TOMBSTONE_SEMANTICS: superseding version or explicit tombstone; history retained
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH IF FORMAL REUSED
MIGRATION_OBJECT: demo_identity_constraints
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P5 lock/override contract
```

#### `demo_self_transfer_run`

```text
LOGICAL_ENTITY: demo_self_transfer_run
EXISTING_FORMAL_ENTITY: SelfTransferValidationRun, SelfTransferValidationResponse
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: formal Job operational reference only
EXTENSION_REQUIRED: candidate, correction, measured delta, drift, verifier and result evidence
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_self_transfer_runs
AUTHORITY_OWNER: Demo P5 self-transfer evidence
OWNER_BINDING: actor, session, desired delta and job binding
APPEND_ONLY_MECHANISM: immutable final evidence; runtime status remains formal Job authority
DIGEST_INPUTS: owner/profile, assets, corrections, runtime/algorithm, measured result and outcome
DELETE_OR_TOMBSTONE_SEMANTICS: forward tombstone; Asset lifecycle remains formal
FORMAL_AUTHORITY_POLLUTION_RISK: MEDIUM
MIGRATION_OBJECT: demo_self_transfer_runs
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P5 self-transfer
```

#### `demo_reference_profile`

```text
LOGICAL_ENTITY: demo_reference_profile
EXISTING_FORMAL_ENTITY: ReferenceSet
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: formal Asset references only
EXTENSION_REQUIRED: structured reference/style evidence, confidence, source roles and compiler version
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_reference_profiles
AUTHORITY_OWNER: Demo P5 derived authority
OWNER_BINDING: actor, source Assets and profile version
APPEND_ONLY_MECHANISM: versioned rebuildable immutable generations
DIGEST_INPUTS: Asset checksums/roles, analysis/compiler versions, structured profile and evidence links
DELETE_OR_TOMBSTONE_SEMANTICS: source Asset tombstone appends invalidation evidence and rebuilds a new generation; physical DELETE forbidden
FORMAL_AUTHORITY_POLLUTION_RISK: MEDIUM
MIGRATION_OBJECT: demo_reference_profiles
PROMOTION_STRATEGY: Assets remain formal; metadata uses FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P5, formal ReferenceSet semantics
```

### P6 authority

#### `demo_editing_session`

```text
LOGICAL_ENTITY: demo_editing_session
EXISTING_FORMAL_ENTITY: EditingSession
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: source Asset reference only
EXTENSION_REQUIRED: Demo owner/session, instruction, locks, context and registry digests
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_editing_sessions
AUTHORITY_OWNER: Demo P6 session authority
OWNER_BINDING: actor, Demo session and source Asset
APPEND_ONLY_MECHANISM: immutable header; progress derives from versions/plans/jobs
DIGEST_INPUTS: owner/session/source Asset checksum, profile/context/instruction/registry versions
DELETE_OR_TOMBSTONE_SEMANTICS: close/tombstone; original Asset stays immutable
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH IF FORMAL REUSED
MIGRATION_OBJECT: demo_editing_sessions
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: ADR-050, Fast Track Contract P6, formal EditingSession
```

#### `demo_image_version`

```text
LOGICAL_ENTITY: demo_image_version
EXISTING_FORMAL_ENTITY: ImageVersion, AssetVariant
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: formal Asset/AssetVariant references only
EXTENSION_REQUIRED: Demo DAG, plan/tool/verifier lineage, quarantine and acceptance evidence
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_image_versions
AUTHORITY_OWNER: Demo P6 version authority; formal owns bytes/variant lineage
OWNER_BINDING: actor through editing session
APPEND_ONLY_MECHANISM: immutable; unique session sequence; guarded same-session parent; deferred bidirectional verifier edge
DIGEST_INPUTS: session/parent/source/result Asset ids and SHA snapshots, AssetVariant id, kind and resolved plan/tool/verifier digests
DELETE_OR_TOMBSTONE_SEMANTICS: rejection/quarantine never mutates prior version; Asset deletion is formal
FORMAL_AUTHORITY_POLLUTION_RISK: MEDIUM
MIGRATION_OBJECT: demo_image_versions
PROMOTION_STRATEGY: retain/remap formal Assets; metadata uses FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P6, formal ImageVersion/AssetVariant, P3_P7_D01_B_CC_01
```

#### `demo_edit_plan`

```text
LOGICAL_ENTITY: demo_edit_plan
EXISTING_FORMAL_ENTITY: Plan (entitlement plan; not equivalent)
SEMANTIC_EQUIVALENCE: NONE
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: typed ordered planner output, tools, constraints and expected effects
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_edit_plans
AUTHORITY_OWNER: Demo P6 planner authority
OWNER_BINDING: actor, editing session and input image version
APPEND_ONLY_MECHANISM: immutable versions; replanning creates a new plan
DIGEST_INPUTS: input version, profile/constraints/instruction, planner/registry and operation specs
DELETE_OR_TOMBSTONE_SEMANTICS: supersede/tombstone by forward evidence
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_edit_plans
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P6 planner
```

#### `demo_edit_operation`

```text
LOGICAL_ENTITY: demo_edit_operation
EXISTING_FORMAL_ENTITY: EditOperation
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: plan binding, typed fixed units, expected effect and correction lineage
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_edit_operations
AUTHORITY_OWNER: Demo P6 Operation Graph
OWNER_BINDING: actor through plan/editing session
APPEND_ONLY_MECHANISM: immutable; unique plan operation index
DIGEST_INPUTS: plan/index/type/engine, canonical parameters, preservation and expected effect
DELETE_OR_TOMBSTONE_SEMANTICS: rollback creates new operation/ImageVersion; history remains
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH IF FORMAL REUSED
MIGRATION_OBJECT: demo_edit_operations
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P6, formal EditOperation
```

#### `demo_tool_run`

```text
LOGICAL_ENTITY: demo_tool_run
EXISTING_FORMAL_ENTITY: ModelRun, JobAttempt
SEMANTIC_EQUIVALENCE: PARTIAL
REUSE_POSSIBLE: formal Job/JobAttempt operational references only
EXTENSION_REQUIRED: registry/effect contract, deterministic input/result, trace and quarantine evidence
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_tool_runs
AUTHORITY_OWNER: Demo P6 tool evidence; formal owns attempt lifecycle
OWNER_BINDING: actor/session, job binding and edit operation
APPEND_ONLY_MECHANISM: immutable result; retry creates new JobAttempt/tool run
DIGEST_INPUTS: operation id/digest, plan/job/attempt, tool/version, input/output checksums and effect contract
DELETE_OR_TOMBSTONE_SEMANTICS: failed/rejected rows remain; output Asset deletion stays formal
FORMAL_AUTHORITY_POLLUTION_RISK: MEDIUM
MIGRATION_OBJECT: demo_tool_runs
PROMOTION_STRATEGY: FWD_CONVERSION; prototype jobs are not automatically promoted
DECISION_EVIDENCE: Fast Track Contract P6, formal JobAttempt/ModelRun, P3_P7_D01_B_CC_01
```

#### `demo_verification_result`

```text
LOGICAL_ENTITY: demo_verification_result
EXISTING_FORMAL_ENTITY: SyntheticQARun
SEMANTIC_EQUIVALENCE: NONE FOR P6 EFFECT VERIFICATION
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: structural, lock, target, drift, artifact, immutability and decode checks
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_verification_results
AUTHORITY_OWNER: Demo P6 verifier evidence
OWNER_BINDING: actor through tool run and image version
APPEND_ONLY_MECHANISM: immutable result rows; mandatory unique ImageVersion id and deferred bidirectional binding
DIGEST_INPUTS: tool/image/output checksum, verifier/config, integer metrics/thresholds and outcome
DELETE_OR_TOMBSTONE_SEMANTICS: failed evidence remains; quarantined bytes may be formally deleted
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_verification_results
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P6 verifier, P3_P7_D01_B_CC_01
```

### P7 authority

#### `demo_preference_event`

```text
LOGICAL_ENTITY: demo_preference_event
EXISTING_FORMAL_ENTITY: PreferenceEvent
SEMANTIC_EQUIVALENCE: PARTIAL; formal lacks actor digest chain/reset/delete authority
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: actor sequence, previous digest, authority source, target and temporal semantics
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_preference_events
AUTHORITY_OWNER: Demo P7 Evidence Ledger
OWNER_BINDING: actor and optional session/episode/version targets
APPEND_ONLY_MECHANISM: actor-serialized sequence plus previous/event digest chain
DIGEST_INPUTS: actor/sequence/type/source/target/signal/occurred_at/previous digest
DELETE_OR_TOMBSTONE_SEMANTICS: append RESET, ROLLBACK, TOMBSTONE or DELETE event
FORMAL_AUTHORITY_POLLUTION_RISK: CRITICAL IF FORMAL REUSED
MIGRATION_OBJECT: demo_preference_events
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: ADR-050, Fast Track Contract P7, Visual Memory OS
```

#### `demo_accepted_visual_episode`

```text
LOGICAL_ENTITY: demo_accepted_visual_episode
EXISTING_FORMAL_ENTITY: NONE
SEMANTIC_EQUIVALENCE: NONE
REUSE_POSSIBLE: formal Asset/Image references only
EXTENSION_REQUIRED: final-save provenance, trajectory, instruction/profile/context and verifier links
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_accepted_visual_episodes
AUTHORITY_OWNER: Demo P7 visual evidence
OWNER_BINDING: actor, editing session and accepted image version
APPEND_ONLY_MECHANISM: immutable; only verified user-accepted image is eligible
DIGEST_INPUTS: source/final checksums and image/plan/operation/tool/verifier/profile/context/instruction digests
DELETE_OR_TOMBSTONE_SEMANTICS: append ledger tombstone/delete; Asset bytes use formal deletion
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_accepted_visual_episodes
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P7, Visual Memory OS, P3_P7_D01_B_CC_01 complete trajectory binding
```

#### `demo_aesthetic_profile`

```text
LOGICAL_ENTITY: demo_aesthetic_profile
EXISTING_FORMAL_ENTITY: AestheticProfile, AestheticProfileVersion
SEMANTIC_EQUIVALENCE: PARTIAL; formal pointer/evidence semantics do not meet deterministic rebuild contract
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: compiler generation, watermark, reset epoch, counterevidence and temporal validity
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_aesthetic_profiles
AUTHORITY_OWNER: Demo P7 derived materialization
OWNER_BINDING: actor and evidence watermark
APPEND_ONLY_MECHANISM: versioned rebuildable immutable generations; no mutable current pointer
DIGEST_INPUTS: accepted episodes/events/delta/style/constraint digests, compiler, watermark and reset epoch
DELETE_OR_TOMBSTONE_SEMANTICS: append RESET/TOMBSTONE/DELETE event, exclude this generation and rebuild from remaining evidence; physical DELETE forbidden
FORMAL_AUTHORITY_POLLUTION_RISK: CRITICAL IF FORMAL REUSED
MIGRATION_OBJECT: demo_aesthetic_profiles
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: ADR-050, Fast Track Contract P7, Visual Memory OS
```

#### `demo_context_compilation`

```text
LOGICAL_ENTITY: demo_context_compilation
EXISTING_FORMAL_ENTITY: NONE
SEMANTIC_EQUIVALENCE: NONE
REUSE_POSSIBLE: NO
EXTENSION_REQUIRED: explicit as-of time, bounded budget, selection/rejection and Gate trace
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_context_compilations
AUTHORITY_OWNER: Demo P7 derived context authority
OWNER_BINDING: actor, new Demo session and Profile generation
APPEND_ONLY_MECHANISM: immutable rebuildable compilation rows
DIGEST_INPUTS: actor/session/as-of/profile/watermark/instruction/candidates/budgets/compiler
DELETE_OR_TOMBSTONE_SEMANTICS: expires_at changes eligibility only; append invalidation/delete event and recompile; physical DELETE forbidden
FORMAL_AUTHORITY_POLLUTION_RISK: LOW
MIGRATION_OBJECT: demo_context_compilations
PROMOTION_STRATEGY: FWD_CONVERSION
DECISION_EVIDENCE: Fast Track Contract P7, Visual Memory OS
```

### Cross-cutting execution authority

#### `demo_job_binding`

```text
LOGICAL_ENTITY: demo_job_binding
EXISTING_FORMAL_ENTITY: Job, JobAttempt
SEMANTIC_EQUIVALENCE: PARTIAL; formal owns execution only
REUSE_POSSIBLE: YES FOR FORMAL EXECUTION ONLY
EXTENSION_REQUIRED: actor/session/operation/idempotency/request digest and typed target integrity
NEW_PROTOTYPE_TABLE_REQUIRED: YES
DEMO_AUTHORITATIVE_SOURCE: demo_job_bindings
AUTHORITY_OWNER: split by field; binding owns Demo authorization and semantic request
OWNER_BINDING: composite session/actor plus typed target
APPEND_ONLY_MECHANISM: immutable; retry creates a new formal JobAttempt
DIGEST_INPUTS: actor/session/operation/key hash/request digest/job/target
DELETE_OR_TOMBSTONE_SEMANTICS: terminal evidence retained; explicit test teardown only after namespace checks
FORMAL_AUTHORITY_POLLUTION_RISK: HIGH WITHOUT NAMESPACE AND TARGET TRIGGER
MIGRATION_OBJECT: demo_job_bindings with formal Job FK and typed target-integrity trigger
PROMOTION_STRATEGY: FWD_CONVERSION; operational rows are reused only under explicit future approval
DECISION_EVIDENCE: ADR-050, Fast Track Contract idempotency/job contract, formal Job/JobAttempt
```

## D01-B implementation entry gates

The migration/ORM writer may begin only with all of the following frozen:

```text
D01_A_TASK_ACCEPTED: PASS
SCHEMA_MATRIX_TRACKED: SATISFIED_BY_THIS_CHECKPOINT_COMMIT
INDEPENDENT_SOL_SCHEMA_DESIGN_REVIEW: PASS
INDEPENDENT_SOL_SCHEMA_FILE_REVIEW: PASS
ALL_27_AUTHORITATIVE_SOURCES_UNIQUE: PASS
CANONICAL_JSON_VERSION: demo-canonical-json-v1
NEW_DEMO_PAYLOAD_TYPE: POSTGRESQL_JSONB
FORMAL_TABLE_DDL_CHANGE: FORBIDDEN
POPULATED_DOWNGRADE_NAMESPACE_CHECK: REQUIRED
DB_LEVEL_IMMUTABILITY: REQUIRED
DEMO_JOB_TYPED_TARGET_INTEGRITY: REQUIRED
```

The independent Sol file review bound candidate hash
`382fb6ba3ef5059d4089fcb4f3b149ba0d65fedd43d5e4b11c3e4e55054544bc`, verified all 27 entity records and closed all
five mandatory repair findings with no new finding. Principal reviewed the repaired content and accepts this Matrix as
the sole D01-B physical-authority design checkpoint. Acceptance authorizes only the bounded migration/ORM implementation
that follows this document; it does not assert implementation or PostgreSQL success.

After implementation, an independent Sol review must verify the actual diff and real PostgreSQL evidence. Until then:

```text
D01_B_IMPLEMENTATION: REMEDIATION_VALIDATED_PENDING_INDEPENDENT_REVIEW
D01_C: CLOSED
DEMO_MIGRATION_LIFECYCLE: PASS_FOR_REMEDIATION_CANDIDATE
POSTGRESQL_AUTHORITY: PASS_FOR_REMEDIATION_CANDIDATE
INDEPENDENT_SOL_IMPLEMENTATION_REVIEW: PENDING
PRINCIPAL_TASK_ACCEPTANCE: BLOCKED_PENDING_INDEPENDENT_REVIEW
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```
