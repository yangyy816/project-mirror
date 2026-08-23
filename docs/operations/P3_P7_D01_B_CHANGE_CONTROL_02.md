# P3–P7 D01-B Change Control 02 — Synchronous Semantic Idempotency Authority

## Disposition

```text
CHANGE_CONTROL: CC-P3-P7-DEMO-D01B-02
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
DISCOVERED_BY: D01-C independent contract review
STATUS: ACCEPTED_FOR_IMPLEMENTATION
D01_B: REOPENED_FOR_CC02
D01_C: BLOCKED_BY_SYNCHRONOUS_IDEMPOTENCY_AUTHORITY
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

The accepted `demo_job_bindings` table is the correct immutable authority for asynchronous commands because each row
must bind a real formal `Job`. It cannot honestly represent the six synchronous persistence commands below without a
nullable fake Job or another loss of authority. The formal `idempotency_records` table is a transient coordinator: it
may expire, has no Demo response target foreign-key semantics and has no actor/session target-integrity proof. It is
therefore not the durable Demo semantic idempotency authority.

This change control keeps `demo_0001_p3_p7_core` immutable and adds one branch-local forward migration:

```text
MIGRATION_MODULE: demo_0002_p3_p7_command_authority.py
REVISION: demo_0002_p3_p7_command_auth
DOWN_REVISION: demo_0001_p3_p7_core
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

The descriptive module name is retained. The Alembic revision identifier is shortened to 28 characters because the
existing Alembic version authority uses the standard 32-character revision envelope; the 33-character descriptive
name must not be forced into that authority.

## Frozen physical authority

Add immutable `demo_command_bindings` with:

```text
id
schema_version
canonical_payload
content_digest
created_at
demo_actor_id
demo_session_id nullable
endpoint_operation
idempotency_key_hash
request_digest
response_type
response_id
response_status
```

Required constraints and guards:

- actor foreign key and optional composite `(demo_session_id, demo_actor_id)` foreign key use `RESTRICT`;
- `UNIQUE (demo_actor_id, endpoint_operation, idempotency_key_hash)` selects the canonical concurrent winner;
- `UNIQUE (response_type, response_id)` prevents one durable response authority from being claimed by two commands;
- key and request digests are lowercase SHA-256; IDs are 32 lowercase hexadecimal characters;
- response status is fixed by operation, not supplied as an arbitrary success code;
- the existing canonical-payload/digest function verifies every structured field;
- every `UPDATE` and `DELETE` fails closed;
- the response row must already be visible in the same PostgreSQL transaction and match actor/session ownership;
- populated `demo_0002 -> demo_0001` downgrade fails closed.

## Frozen operation and response mapping

| `endpoint_operation`            | `response_type`        | Status | Required response authority                                                                                         |
| ------------------------------- | ---------------------- | -----: | ------------------------------------------------------------------------------------------------------------------- |
| `session.create`                | `DEMO_SESSION`         |    201 | `demo_sessions`; response ID and binding session ID are the same owned session                                      |
| `questionnaire.response.create` | `QUESTIONNAIRE_STEP`   |    201 | owned/session-bound `demo_questionnaire_steps` row with `event_type=RESPONDED`                                      |
| `style_feedback.create`         | `PREFERENCE_EVENT`     |    201 | owned event whose session is identical, including both-null, and whose source is explicit user action               |
| `constraint.create`             | `IDENTITY_CONSTRAINTS` |    201 | owned constraints version with the identical optional session scope                                                 |
| `image_version.feedback`        | `PREFERENCE_EVENT`     |    201 | owned/session-bound accepted, rejected or adjusted image feedback event targeting an `IMAGE_VERSION`                |
| `job.cancel`                    | `JOB`                  |    200 | real formal Job already bound through `demo_job_bindings`, owned by the same actor/session and terminal `CANCELLED` |

For `style_feedback.create`, allowed event types are `EXPLICIT_STYLE_SELECTION` and
`MAXIMUM_INTENSITY_CHANGED`. Lock/unlock, temporary override and prohibited-operation commands are persisted through
`constraint.create` plus their explicit evidence event in the same application transaction; this change control does
not merge the constraints and ledger authorities.

For `job.cancel`, the Job must remain inside the `demo_p3_p7.*` namespace, have no formal user owner or ingestion
intent, have an empty payload and no result asset, and contain non-null terminal time and result code. A Job ID or
unguessable identifier never replaces the existing Demo actor/session binding.

## Replay and concurrency semantics

Application code must resolve the immutable binding under the unique key:

```text
(demo_actor_id, endpoint_operation, idempotency_key_hash)
```

- same key and same request digest reloads the typed response authority and returns its recorded status;
- same key and different request digest returns `409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`;
- a concurrent insert conflict is reloaded from PostgreSQL; no check-then-insert or in-memory authority is allowed;
- target creation/change and command binding become visible atomically;
- no synchronous fake Job, nullable `DemoJobBinding.job_id`, JSONB-only key stash or expiring formal idempotency row is
  permitted.

## Required validation

```text
EMPTY demo_0001 -> demo_0002 -> demo_0001 -> demo_0002
POPULATED demo_0002 -> demo_0001: FAIL_CLOSED
FRESH -> demo_0002
0014 -> demo_0002
ALEMBIC_CHECK: ZERO_DRIFT
FORMAL_NON_DEMO_DDL_DIFF: ZERO
DEMO_TABLE_COUNT: 28
AUTHORITY_TRIGGER_COUNT: 28
ORM_DATABASE_FK_PARITY: PASS
SIX_OPERATION_POSITIVE_MATRIX: PASS
WRONG_OWNER_SESSION_TYPE_STATUS_TARGET: REJECTED
CONCURRENT_CANONICAL_WINNER: EXACTLY_ONE
UPDATE_DELETE: REJECTED
```

## Boundary

This repair changes no formal table, formal migration, public API, Worker registration, OpenAPI or generated client.
It does not implement D01-C. D01-C remains blocked until the migration, ORM, real PostgreSQL invariants, lifecycle,
regression suite and independent review are accepted by Principal.

Network semantics remain:

```text
PUBLIC_INTERNET_EGRESS_DISABLED
NOT ALL_NETWORK_DISABLED
LOCALHOST_AND_DOCKER_INTERNAL_NETWORK: REQUIRED
```

PostgreSQL may use the isolated Docker internal network. No public acquisition, proxy or Provider call is authorized
by this schema change.
