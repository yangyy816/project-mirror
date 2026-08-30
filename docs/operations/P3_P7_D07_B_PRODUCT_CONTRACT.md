# P3–P7 Demo D07-B Product Contract

## Decision status

```text
CONTRACT_ID: P3_P7_D07_B_PRODUCT_CONTRACT_V1
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_AFTER_BOUNDED_ARCHITECTURE_REVIEW
BASE_SHA: 90681bdc9077e1b27885419d294f0f655cdf4359
PUBLIC_ROUTE_COUNT_CHANGE: 0
FORMAL_AUTHORITY_CHANGE: NONE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This contract closes the D01-C request-shape gaps required to run the already
approved D07 routes against real PostgreSQL and a real Worker. It does not
change the formal P3–P7 track, authorize real faces, or make the runtime
production-ready.

## Editing-session bootstrap

`POST /api/v1/demo/editing-sessions` keeps `session_id` and the existing
`source_image_version_id`, and adds optional `source_asset_id`. Exactly one
source selector is required.

- `source_asset_id` must resolve to an immutable, non-deleted, synthetic Asset.
- `source_image_version_id` must resolve to an actor/session-owned Demo
  ImageVersion; its result Asset becomes the source.
- A real source Asset is never mutated or reused as the result authority.
- The API transaction creates `DemoEditingSession`, a PENDING formal Job and
  its `DemoJobBinding` atomically.
- The Worker writes an immutable private original snapshot and then locks the
  create Job and current JobAttempt before atomically creating the derived
  Asset, AssetVariant and sequence-0 `DemoImageVersion` and terminalizing the
  Job/attempt in the same PostgreSQL commit.
- Storage-before-database interruption is replayed by deterministic object and
  authority IDs; a partial database graph is forbidden.

Profile selection is deterministic and fail-closed:

1. highest canonical version DesiredDelta for the same actor/session;
2. highest canonical version session StyleProfile, otherwise highest canonical
   version actor-global StyleProfile;
3. highest canonical version persistent IdentityConstraints;
4. highest canonical version same-session override is included in the context digest and planner
   input without replacing the persistent lock authority;
5. no missing authority is filled with a default profile, lock or style.

`context_digest` binds the source Asset digest, Demo session context seed,
selected profile/constraint digests and contract version. `instruction_digest`
is the canonical semantic request digest. Wall clock and raw float values are
excluded.

## Typed plan creation

`POST /editing-sessions/{id}/plans` retains its existing request schema. The
highest canonical `version` published ImageVersion in the editing session is
locked as input. The
deterministic planner consumes the requested operation/value, DesiredDelta,
persistent locks, explicit session overrides and prohibited operations.

The same API transaction persists REQUEST and RESULT `DemoEditPlan` rows,
ordered `DemoEditOperation` rows, a PENDING Job and `DemoJobBinding`. The Job
target is the RESULT plan. Makeup and Generative remain typed plans with their
fixed unavailable semantics; no tool is executed for either capability.

## Plan execution

`POST /edit-plans/{id}/executions` retains its existing schema. The API checks
owner/session, RESULT-plan digest and exact execution-mode/engine compatibility
before atomically creating a PENDING Job and binding to the plan.

The Worker alone claims a JobAttempt. It loads source bytes through a strict
local private Asset loader, executes persisted operations in order, writes only
to quarantine before verification, and publishes Asset/AssetVariant/
ImageVersion authority only after a publishable PASS. Publication or rejection
locks the execution Job, its current JobAttempt and the materialized artifact,
revalidates that the Job and attempt are still `RUNNING`, writes ToolRun,
Verification, event, Asset and ImageVersion authority as applicable, and
terminalizes the execution Job/attempt in one PostgreSQL commit. Redelivery
reuses the same attempt/artifact authority and never duplicates ToolRun,
Verification or ImageVersion rows.

Geometry execution remains injectable and fail-closed when the accepted M4
runtime is not materialized. This is a runtime-evidence gate, not a blocker for
raster/application implementation.

## ToolRun read

`GET /tool-runs/{id}` adds no request fields. It joins the authenticated Demo
actor to the ToolRun actor/session authority and maps the associated execution
Job state. An opaque identifier is not authorization.

## Restore

For `POST /image-versions/{image_version_id}/restore`, the path value is the
historical target version. `expected_current_image_version_id` and its digest
identify the optimistic-concurrency source/current version.

The API validates same actor/session/editing-session ancestry and persists a
typed RESTORE REQUEST/RESULT plan. The restore Job remains bound to the path
target as required by the frozen D01-B trigger. The plan IDs are deterministic
from the restore Job ID, allowing the Worker to recover the exact plan without
a second authority table. The Worker creates an internal `edit_plan.execute`
child Job/binding and publishes a new `RESTORED` ImageVersion through the same
quarantine/verifier path. No historical row is copied or overwritten.

The restore child idempotency key and request digest are versioned,
domain-separated values derived from the parent restore Job/binding. Before
publication, the Worker reconstructs the D07-A `TransitionIntent` from that
binding, the RESULT plan input and operation target, loads the historical
target through the strict private Asset loader, and proves:

```text
materialized.sha256
= target.result_asset_sha256
= TransitionIntent.expected_result_asset_sha256
```

The newly published result Asset ID must differ from both the current source
Asset ID and the historical target Asset ID. Restore publication or rejection
locks the parent restore Job, child execution Job, their current attempts and
the artifact in ascending UUID order; it revalidates every Job/attempt is still
`RUNNING`, writes the authority rows, and terminalizes both parent and child in
one PostgreSQL commit.

## State machine and failure semantics

```text
PENDING -> RUNNING | CANCELLED
RUNNING -> COMPLETED | REJECTED | FAILED | CANCELLED
terminal -> no transition
```

- runtime/storage/algorithm failures end `FAILED`;
- typed capability, constraint or verifier refusal ends `REJECTED`;
- `COMPLETED` or `REJECTED` and all corresponding authority rows are written in
  one PostgreSQL transaction; a second terminalization transaction is forbidden;
- cancellation prevents new result publication;
- storage-before-database interruption remains replayable with the same
  deterministic keys and authority IDs; `FAILED` is written only for a
  non-recoverable error or after the bounded retry policy is exhausted;
- every create operation uses the frozen
  `(demo_actor_id, endpoint_operation, idempotency_key_hash)` PostgreSQL
  winner and canonical semantic request digest.

## Fixed versions

```text
EDITING_CONTRACT_VERSION: demo-editing-product-contract-v1
PLANNER_VERSION: demo-edit-planner-v1
TOOL_REGISTRY_VERSION: demo-tool-registry-v1
RASTER_ENGINE: demo-raster-editor-pillow12-fixedpoint-v1
VERIFIER_VERSION: demo-tool-verifier-v1
```

The three fixed unavailable outcomes remain:

```text
MAKEUP: DEFERRED_WITH_EXPLICIT_REASON
GENERATIVE: CAPABILITY_UNAVAILABLE
FRESH_GEOMETRY_RUNTIME_MISSING: RUNTIME_EVIDENCE_DEFERRED_OR_FAILED, NEVER MOCKED
```
