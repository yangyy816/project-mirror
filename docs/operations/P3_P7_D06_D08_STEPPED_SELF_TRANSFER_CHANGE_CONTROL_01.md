# P3–P7 D06/D08 Stepped Self-Transfer Change Control 01

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D06_D08_STEPPED_SELF_TRANSFER_CHANGE_CONTROL_01
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_APPROVED_FOR_ISOLATED_IMPLEMENTATION
ENTRY_BASE_SHA: 929550d5e5d331697f3f426dc102cee7296db22d
R09_CANDIDATE_SHA: 746f210418182672126718bc3043124e8e931f5e
INTEGRATION_PREREQUISITE: R05_R08_SUCCESSOR_CI_PASS_AND_R09_TASK_ACCEPTED
PUBLIC_API_CHANGE: ADDITIVE_DEMO_ONLY
MIGRATION_CHANGE: ONE_FORWARD_DEMO_SCHEMA_VERSION_CONSTRAINT_ONLY
MIGRATION_REVISION: demo_0019_d06_stepped_transfer
MIGRATION_PARENT: demo_0018_d03_pose_evidence
ORM_CHANGE: DEMO_SELF_TRANSFER_RUN_SCHEMA_VERSION_CONSTRAINT_ONLY
D02_AUTHORITY_CHANGE: NONE
PRODUCTION_AUTHORIZATION: NONE
REAL_USER_AUTHORIZATION: NONE
```

## Product correction

The deterministic raster result in Contract 09 is a valid published
`ImageVersion`, but it is not a valid general D06 learning input. Its raster
verifier deliberately reports a zero `jaw_width` projection, while D06 binds a
real DesiredDelta dimension and requested delta. Raster publication must not be
relabelled as self-transfer evidence.

This change adds one explicit profile-guided Geometry preview. It preserves the
existing raster flow, ordinary Geometry request semantics, D08 selected-case
authority, D06 v1 replay and all existing public requests byte-for-byte.

## EditPlan instruction provenance repair

D09's frozen Final Save authority requires:

```text
AcceptedVisualEpisode.instruction_digest
= DemoEditingSession.instruction_digest
= terminal RESULT DemoEditPlan.instruction_digest
```

The repository path already follows this rule, but the command-service path
incorrectly stores the per-plan semantic request digest as the EditPlan
instruction digest. That request digest already belongs to the exact
`DemoJobBinding.request_digest`; it is not the user/session instruction
authority.

The command-service repair must make `_persist_plan` inherit
`DemoEditingSession.instruction_digest` for ordinary and transition plans and
must retain the plan command digest only in its JobBinding. No historical row
is rewritten. Any plan whose instruction differs from its EditingSession
continues to fail closed at Final Save.

## Fixed selection policy

```text
POLICY_VERSION: demo-profile-guided-d08-step-v1
POLICY_DIGEST: d66875008d6145c5c5ca381f9024bdba40aa7df4b752766a9e15d04dd994468d
ALLOWED_DIMENSIONS: chin_height, eye_spacing, jaw_width
ALLOWED_MAGNITUDES_PPM: 15000, 30000
```

The policy digest is SHA-256 over this canonical JSON:

```json
{
  "allowed_dimensions": ["chin_height", "eye_spacing", "jaw_width"],
  "allowed_magnitudes_ppm": [15000, 30000],
  "candidate_requirements": [
    "CONFIDENCE_POSITIVE",
    "GEOMETRY_NOT_PROHIBITED",
    "PROFILE_DELTA_NONZERO",
    "RESTRAINT_NONE",
    "SELECTED_D02_DIMENSION",
    "SELECTED_D08_CASE",
    "SESSION_OVERRIDE_FOR_PRESERVE"
  ],
  "dimension_order": ["ABS_PROFILE_DELTA_DESC", "DIMENSION_KEY_ASC"],
  "magnitude_order": ["ABS_DISTANCE_ASC", "MAGNITUDE_ASC", "CASE_DIGEST_ASC"],
  "policy_version": "demo-profile-guided-d08-step-v1",
  "sign_rule": "INHERIT_NONZERO_PROFILE_DELTA",
  "source_scope": "CURRENT_D02_SELECTED_SIDE_CASE_ONLY"
}
```

A candidate is eligible only when all of these are true:

- the dimension is present in the exact D05 DesiredDeltaProfile;
- its delta is non-zero, confidence is positive and restraint is `NONE`;
- the dimension belongs to the current D02 screened selected dimensions;
- Geometry is not prohibited;
- a persistent `PRESERVE` lock has an explicit current-session
  `ALLOW_CHANGE` override;
- the current source, dimension, direction and magnitude resolve to exactly one
  selected D08 case.

Filter before ranking. Rank eligible dimensions by absolute profile delta
descending and dimension key ascending. For that dimension, select the step
whose magnitude minimizes `(abs(magnitude - abs(profile_delta)), magnitude)`;
the sign always inherits the non-zero profile delta. Case digest is the final
stable tie-break.

This nearest qualified step is not a silent snap. The browser must display the
selected dimension, direction and exact step before execution. A step below or
above the continuous posterior is only authorized after the user explicitly
starts this fixed-step preview. No eligible case returns
`DEMO_PROFILE_GEOMETRY_STEP_UNAVAILABLE`; it never falls back to raster.

## D06 v2 authority

Historical `mirror.demo/DemoSelfTransferRun/v1` rows and behavior remain
unchanged. New stepped acceptance uses
`mirror.demo/DemoSelfTransferRun/v2` in the existing JSONB columns.

Real PostgreSQL proved that the inherited v1-only `schema_version` constraint
rejects v2 before application validation can run. A single forward migration
from `demo_0018_d03_pose_evidence` must therefore replace only
`ck_demo_self_transfer_runs_schema_version_shape` with an exact closed set that
admits v1 and v2. The ORM expression must match it. No column, index, foreign
key, trigger, table or other Demo authority changes.

Fresh upgrade, `demo_0018` → `demo_0019`, Alembic check/single-head, preserved
v1 rows, accepted v2 rows, unknown-version rejection, rollback and re-upgrade
are blocking migration tests. A populated downgrade must fail closed while any
v2 row exists; after v2 rows are absent it may restore the exact v1-only
constraint.

The v2 REQUEST and RESULT carry the same immutable request envelope:

```text
dimension_key
profile_desired_delta_ppm
execution_delta_ppm
selection_policy_version
selection_policy_digest
selected_case_digest
execution_job_id
result_image_version_id
```

The profile value, execution step and fresh measured delta are distinct values
and must never overwrite or alias one another. D08 verifier
`requested_delta_ppm` must equal `execution_delta_ppm`; measured delta remains
the accepted D06 evidence value. The D05 profile ID/digest, D08 Job/plan/case,
published `ImageVersion`, PASS verifier and source/result Assets are revalidated
on every create, replay and finalize.

## Demo API contract

Add these Demo-only endpoints:

```text
POST /api/v1/demo/editing-sessions/{editing_session_id}/profile-geometry-plans
GET  /api/v1/demo/edit-plans/execution-jobs/{job_id}/media/{side}
POST /api/v1/demo/edit-plans/execution-jobs/{job_id}/accept-as-reference
GET  /api/v1/demo/reference-profiles/compilation-jobs/{job_id}/result
```

The profile-geometry request accepts only the fixed policy version and an
`Idempotency-Key`. The server selects the dimension and step; callers cannot
override them. It returns the existing trusted Job projection plus safe preview
metadata. Existing execution admission is reused with `execution_mode=GEOMETRY`,
followed by the exact execution-result read.

Media `side` is exactly `INPUT` or `RESULT`. The resolver follows the exact
Job → Binding → Plan → published ImageVersion → Asset lineage, revalidates
owner/session/digests/MIME/decode and streams private no-store bytes. It never
returns a locator, object key or arbitrary Asset lookup.

The acceptance body is exactly:

```json
{ "outcome": "FINAL_SAVE_AND_USE_AS_REFERENCE" }
```

It requires a separate `Idempotency-Key`. Its trusted response may contain the
D09 event/episode, D06 request/result/evidence and Reference Profile Job
authority for the server-side BFF only. None of those identifiers or digests
may reach browser JSON, DOM, URL, storage or logs.

The exact Reference Profile result endpoint must replay JobBinding → immutable
compile request → compile result → ReferenceProfile. Active/latest fallback is
forbidden.

## Atomic user outcome

Publishing or displaying an image never means acceptance. The user must first
see the exact before/after media, then explicitly choose “最终保存并用作参考”.

D09 Final Save and the D06 v2 ACCEPTED RESULT/evidence commit in one PostgreSQL
transaction. The fixed lock order is actor preference advisory lock, current
actor/session/edit lineage, then D06 Job/request. The transaction creates and
revalidates the exact Final Save episode before creating D06 RESULT/evidence;
D06 must bind that exact episode. Any error rolls back the D09 event/episode,
D06 request/result/evidence and Job terminal transition together.

After commit, ensure the existing queued Reference Profile request with a
deterministic server key derived from the D06 result. Dispatch failure leaves a
durable PENDING Job for reconciliation. A later compilation failure does not
undo the user's Final Save or D06 evidence; the UI reports “已保存，参考档案待恢复”.

## D11 BFF and UI

Add same-origin routes for self-transfer start/read, tokenized input/result
media and explicit outcome. Start accepts no operation, ppm, ID or digest; it
expresses only `PROFILE_GUIDED_GEOMETRY_PREVIEW`.

Browser-visible states are bounded to:

```text
STARTING
PENDING
PREVIEW_READY
SAVING
REFERENCE_PROFILE_PENDING
REFERENCE_PROFILE_READY
NO_COMPATIBLE_CASE
UNAVAILABLE
FAILED
```

Media tokens are random, short-lived, same-handle/session/generation bound and
not derived from upstream authority. All Session, Job, Binding, Plan, ToolRun,
Verifier, ImageVersion, Asset, Profile IDs/digests and Bearer remain in the
server registry. Logout, expiry, configuration rotation and a newer action
invalidate outstanding responses and media tokens.

## Runtime prerequisite

D08 history proves the implementation, not current Worker capability. Before a
real Geometry Job is claimable, the controlled Worker process must receive an
already-authorized `AcceptedD02GeometryCapabilityFactory` through the existing
process-local installation seam. Factory, locator, bytes and landmarks never
enter a task message, Git, logs or BFF state.

Without that exact factory, the Worker fails before Job claim and before byte
read. It does not discover private state, advertise `P6_GEOMETRY=AVAILABLE` or
fall back to raster. Runtime materialization is required only for the real
Geometry integration Gate and does not reopen D02, D03, D08 or historical M3/M4.

## Implementation order

1. The one schema-version constraint migration and matching ORM expression.
2. Correct command-created EditPlan instruction inheritance while preserving
   its distinct JobBinding request digest.
3. Pure selector and D06 v2 parsing/replay, preserving v1.
4. In-session D09 + D06 atomic coordinator and post-commit Reference queue
   ensure.
5. Additive schemas/routes, exact media and Reference result reads, OpenAPI and
   generated client.
6. Controlled Worker factory-present fresh synthetic Geometry Gate.
7. D11 BFF/UI and browser privacy flow.
8. Principal integrated review and one wave-level CI.

Migration, domain and API contract ownership are serial. Web work starts only
after the generated contract and runtime Gate are stable. No task may modify
D02 private state, use ImageGen, re-run D02 admission, or add any schema change
beyond the exact self-transfer schema-version constraint authorized above.

## Acceptance matrix

- selector boundaries: zero/confidence-zero/restraint/lock/prohibited/
  unselected/missing-case all fail closed;
- deterministic values: `±1`, `±14999`, `±15000`, `±22500`, `±29999`,
  `±30000`, `±100000`, sign and tie behavior;
- PostgreSQL: v1 replay, v2 replay, payload collision, cross-owner/session,
  case/job/image substitution, concurrency and zero partial rows;
- migration: fresh/forward upgrade, single head, v1 preservation, v2 admission,
  unknown-version rejection, populated downgrade fail-closed and clean
  downgrade/re-upgrade;
- provenance: command-created raster/Geometry/transition RESULT plans inherit
  the exact EditingSession instruction while their JobBindings retain the
  distinct request digest; a drifted plan remains Final Save-ineligible;
- atomic outcome: D09/D06 rollback, exact Final Save binding, lost-response
  replay and one unique winner;
- Reference queue: deterministic ensure, dispatch loss, reconciliation,
  redelivery, lease expiry and exact result read;
- media: input/result checksum, MIME/decode, foreign owner, no-store and zero
  locator disclosure;
- Worker: missing factory preclaim failure, factory-present fresh execution,
  exact Case-25 routing and no raster fallback;
- Web: preview before accept, explicit wording, retry/logout/expiry/rotation,
  responsive accessibility and zero authority/credential storage;
- Ruff, strict mypy, targeted PostgreSQL, migration-head check, contract drift,
  TypeScript, production build, Playwright, Gitleaks and one integrated CI.
