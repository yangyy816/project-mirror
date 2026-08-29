# P3–P7 D03 Analysis Authority Change Control 01

## Decision status

```text
CHANGE_CONTROL_ID: CC-P3-P7-D03-ANALYSIS-01
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
CHANGE_TYPE: FORWARD_PROTOTYPE_AUTHORITY_REPAIR
STATUS: PRINCIPAL_ACCEPTED_FOR_IMPLEMENTATION
INDEPENDENT_REVIEW: PASS_FINDINGS_NONE
REVIEWED_DOCUMENT_SHA256: 94dadff1b84e4c232fa8518351f13da47e6c417600f7fdd1e3dc0aeab6e0b498
BASE_SHA: 2037de1c7956b21e1cb2fce934b70671fbc77d55
HISTORICAL_D01_C_ACCEPTANCE: UNCHANGED
HISTORICAL_M3_ACCEPTANCE: FROZEN_UNCHANGED
D02_RUNTIME_REPLAY_STATE: DEFERRED_UNTIL_ACTUALLY_REQUIRED
FORMAL_AUTHORITY_CHANGE: NONE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

## Problem

The accepted Demo API contract makes `POST /api/v1/demo/analyses` asynchronous and returns a `PENDING` Job plus a
typed immutable target. The current database maps `analysis.create` to `FACE_OBSERVATION`, and the Job-binding trigger
requires that observation to exist before the binding is inserted. A `DemoFaceObservation` can only be `SUPPORTED` or
`UNSUPPORTED`, requires final runtime/config authority, and is immutable after insertion.

The current contract therefore cannot represent the legal execution order:

```text
immutable request authority
→ PENDING Job and binding
→ Worker claim/runtime execution
→ atomic final observation + three repeats + baseline + SelfState
```

Creating a final observation before runtime would fabricate evidence. Mutating a placeholder observation would violate
append-only authority. Delaying the Job binding until after runtime would violate the accepted asynchronous and
idempotency contract.

## Decision

Add one Demo-only immutable staging authority, `demo_analysis_runs`, and make it the typed target for
`analysis.create`.

```text
PUBLIC_TARGET_TYPE: ANALYSIS_RUN
ANALYSIS_ID: demo_analysis_runs.id
JOB_LIFECYCLE_AUTHORITY: formal jobs/job_attempts
REQUEST_AUTHORITY: demo_analysis_runs
FINAL_RUNTIME_AUTHORITY:
  demo_face_observations
  demo_face_observation_repeats
  demo_baseline_face_models
  demo_self_states
```

`demo_analysis_runs` binds exactly one actor, session, current admitted synthetic identity, immutable source Asset and
checksum, accepted analyzer/runtime/model/config digests, all Baseline/SelfState compiler versions, exactly three
required repeats, and exactly one `demo_job_binding`. The session's immutable config must name the same synthetic
identity, and that identity's current admitted canonical Asset/checksum must equal the requested source.

The creation transaction preallocates the Job, run and binding IDs and uses this exact order:

```text
INSERT formal Job(PENDING, payload={})
→ INSERT DemoAnalysisRun(binding_id preallocated; FK deferred)
→ INSERT DemoJobBinding(target=ANALYSIS_RUN/run_id)
→ deferred reverse-binding validation
→ COMMIT
```

The forward Job-binding trigger validates run ownership. A deferred reverse trigger validates that the run's binding
points back to that exact run, actor, session, operation and Job. The run-binding relationship is one-to-one; neither a
second binding for one run nor one binding reused by a second run is legal.

The table is append-only. Execution state is never stored by mutating it; the formal Job state machine remains the only
execution lifecycle authority. The Worker may publish final D03 authority only in one transaction after a valid claim.

### AnalysisRun physical authority

The minimum structured fields are frozen as:

```text
demo_actor_id
demo_session_id
demo_synthetic_identity_id
source_asset_id
source_asset_sha256
demo_job_binding_id NOT NULL UNIQUE
analyzer_version
runtime_manifest_digest
model_manifest_digest
observation_config_digest
baseline_aggregation_version
measurement_version
self_state_ontology_version
self_state_derivation_version
repeat_count = 3
```

The binding foreign key is `DEFERRABLE INITIALLY DEFERRED`. A partial unique index on
`demo_job_bindings(target_type, target_id)` for `target_type = 'ANALYSIS_RUN'` prevents a second binding from targeting
the same run. Commit-time validation requires exact equality in both directions, including the same Job ID.

### Session-selected identity authority

No new mutable Session column is introduced. A Session usable by D03 must carry this exact immutable config projection:

```json
{
  "schema_version": "mirror.demo/DemoSessionConfig/v1",
  "synthetic_identity_id": "<opaque DemoSyntheticIdentity ID>"
}
```

That config is already inside the immutable Session canonical payload/digest. AnalysisRun insertion must reject unknown
config keys, a different/missing identity, a closed/tombstoned/expired Session, a non-current identity admission, or a
source Asset/checksum different from the identity's admitted canonical source. Completion rechecks the locked Session
and current admission. A close, tombstone or revocation committed before completion makes the Job `REJECTED` with zero
final D03 rows; it never permits stale result publication.

### Schema-versioned canonical projection

The migration replaces `mirror_demo_authority_projection` with a schema-aware version. For an existing
`mirror.demo/DemoFaceObservation/v1` row, projection omits the newly added `analysis_run_id`, so its historical payload
and digest replay byte-for-byte without re-signing. For v2, projection includes the non-null field. A dedicated insert
guard rejects every post-upgrade v1 observation; only rows already present before the migration remain legal legacy
authority. Downgrade restores the prior projection function only after proving there is no AnalysisRun or v2
observation authority.

`demo_face_observations` gains an optional, unique `analysis_run_id` and a versioned payload rule:

- legacy `mirror.demo/DemoFaceObservation/v1` rows have no analysis-run binding and remain readable;
- new `mirror.demo/DemoFaceObservation/v2` rows require one;
- after this migration, every new observation insert must be v2; the database rejects new v1 injection;
- a final observation must match the run actor, session, identity, source Asset/checksum and pinned digests;
- each repeat must match the run's pinned runtime/model manifests, while Baseline and SelfState must match the pinned
  aggregation, measurement, ontology and derivation versions;
- one run can publish at most one observation;
- every D03 Job has zero attempts only for pre-claim cancellation, otherwise exactly one immutable attempt 1; and
- every Attempt or result insertion revalidates the complete Job/Attempt/result graph at deferred commit time, so a
  completed Job cannot later acquire another Attempt, Baseline version, SelfState version or partial replacement graph;
- cancellation or failure publishes no observation, repeat, baseline or SelfState.

The public Job target union adds `ANALYSIS_RUN`. The existing analysis request and response paths and fields remain
unchanged. `GET /analyses/{analysis_id}` uses the run ID: PENDING/RUNNING map to the existing `PENDING` analysis state;
completed jobs return the bound final observation; rejected, failed or cancelled jobs return a structured terminal
error and never fabricate an observation.

## Migration contract

```text
REVISION: demo_0010_d03_analysis_run
DOWN_REVISION: demo_0009_d02_r2_e2_adm
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

The migration must:

1. create `demo_analysis_runs` with canonical payload/digest, owner/session/source/identity constraints and append-only
   enforcement;
2. add the deferrable Job-binding relationship and a deferred reverse-binding validation trigger;
3. add `analysis_run_id` to `demo_face_observations`, version its schema constraint, preserve existing v1 rows, reject
   all new v1 inserts, and validate complete v2 observation/repeat/baseline/SelfState lineage;
4. update the Demo Job target allowlist and validation function so only `analysis.create → ANALYSIS_RUN` is legal;
5. add D03-specific PostgreSQL Job and JobAttempt transition guards plus deferred bidirectional graph validation for
   the frozen uppercase state machine, exact Attempt cardinality and final result graph;
6. preserve existing v1 observations without re-signing or rewriting them;
7. fail closed on downgrade when any analysis-run or v2 observation authority exists; and
8. preserve a single Alembic head and zero model/schema drift.

## Application and Worker boundary

The D03 provider may add an analysis service, task contract and Worker executor after this change is accepted. It must:

- create Job, AnalysisRun and JobBinding atomically with PostgreSQL idempotency authority;
- pass only opaque Job/analysis IDs to the Worker;
- keep the live M3 handle deferred until an actual runtime execution is attempted;
- claim exactly one new JobAttempt and treat redelivery of a running or terminal Job as replay/no-op;
- publish Observation, exactly three repeats, Baseline and SelfState atomically;
- distinguish execution failure (`FAILED`) from unsupported real result (`COMPLETED` with `UNSUPPORTED` observation);
- make cancellation win before result publication; and
- avoid public network egress and any Provider or ImageGen call.

The D03 Job transition order is fixed:

```text
PENDING → RUNNING | CANCELLED
RUNNING → COMPLETED | REJECTED | FAILED | CANCELLED
terminal → no transition
```

Claim inserts the matching RUNNING JobAttempt before changing the locked Job to RUNNING. Terminalization updates that
attempt and the locked Job in one transaction. `COMPLETED` is legal only when the full final D03 graph exists and the
Job result code equals the observation outcome; `FAILED`, `REJECTED` and `CANCELLED` require no final D03 graph.
Every claim, cancellation and terminalization locks the formal Job `FOR UPDATE` first, then resolves and locks its
binding/run, and only then touches attempts or result authority. Cancellation and completion therefore contend on the
same first lock. A committed cancellation prevents all later result publication; a committed completion makes a later
cancel a terminal conflict/replay and never rewrites the result. A rollback at any point removes the Attempt transition,
Job transition and all candidate result rows together.

Central router, generic Job query/cancel, Celery registration, OpenAPI and generated TypeScript remain Principal-owned and
stay outside the D03 provider slice until `DEMO_API_APPLICATION_INTEGRATION`.

## Rejected alternatives

- **Premature final observation:** rejected because it fabricates `SUPPORTED`/`UNSUPPORTED` before runtime.
- **Mutable PENDING observation:** rejected because Demo authority is append-only and the terminal payload would be an
  in-place rewrite.
- **Job payload as the only request authority:** rejected because the accepted Demo Job envelope requires an empty
  formal payload and Job rows are lifecycle records, not immutable D03 input authority.
- **Session as the typed target:** rejected because it loses per-analysis identity and cannot enforce one final result
  per request.
- **Live M3 handle as an entry prerequisite:** rejected because frozen M3 capability satisfies implementation and
  contract dependencies; the handle is required only at actual runtime execution.

## Acceptance evidence

- fresh/upgrade/downgrade/re-upgrade lifecycle and `alembic check` on PostgreSQL;
- immutable/canonical payload and digest replay for AnalysisRun;
- JobBinding forward/reverse ownership and endpoint/type mismatch rejection;
- legacy v1 observation preservation, rejection of new v1 inserts and complete v2 analysis/compiler lineage;
- same-key replay, different-payload conflict and concurrent canonical winner;
- second-binding rejection and exact Job/Run/Binding circular equality;
- Worker redelivery, both cancel-versus-complete winner orders, Attempt/Job/result rollback and zero-partial-publication
  tests;
- post-completion Attempt insert/update/delete, second RUNNING Attempt, Baseline v2, SelfState v2 and second derived
  graph rejection with unchanged authority after rollback;
- cross-session identity/source mismatch, inactive Session, revoked admission and compiler-version tampering tests;
- no private bytes, locator, Prompt, credential, M3 handle or ImageGen execution in tracked evidence.
