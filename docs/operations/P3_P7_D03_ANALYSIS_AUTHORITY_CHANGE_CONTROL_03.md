# P3–P7 Demo D03 Live M3 Runtime Change Control 03

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D03_CC_03
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_IMPLEMENTATION
BASE_SHA: 4bd7bf57dc52e7ccf4f2c5edd673365122c51230
HISTORICAL_M3_ACCEPTANCE: FROZEN_UNCHANGED
D02_R2_AND_D02_ACCEPTANCE: TASK_ACCEPTED
PRODUCTION_AUTHORIZATION: NONE
PUBLIC_API_CHANGE: NONE
OPENAPI_CHANGE: NONE
PRIVATE_LOCATOR_IN_MESSAGE_OR_SETTINGS: FORBIDDEN
```

## Problem

D03 already persists an immutable AnalysisRun, a formal Job/Attempt, exactly
three observation repeats, a BaselineFaceModel and a SelfState. Its Worker is
deliberately wired to `DeferredDemoAnalysisRuntime`, because no task-scoped M3
capability was available when D03 application orchestration was accepted.

The accepted D02 runtime can now execute three fresh M3 observations with 478
landmarks and the frozen six-dimension measurement contract. It does not emit
head pose. The existing D03 repeat type requires numeric yaw, pitch and roll;
writing zeros would incorrectly turn absence of evidence into measured pose.

D02 public Asset rows also contain logical storage keys, not a public copy of
the accepted source bytes. API, queue messages and ordinary workers must never
discover D02 private roots or receive locators.

## Decision

### Truthful pose authority

Add a forward Demo migration after `demo_0017_d10_context_queue`. No table or
column is added. `demo_face_observation_repeats.pose` remains JSONB and gains a
schema-versioned exact union.

Legacy repeat rows remain byte-identical:

```text
schema_version = mirror.demo/DemoFaceObservationRepeat/v1
pose = legacy object
```

New D03 runtime publication uses:

```json
{
  "schema_version": "mirror.demo/DemoFaceObservationRepeat/v2",
  "pose": {
    "state": "UNAVAILABLE",
    "reason": "M3_RUNTIME_DOES_NOT_EMIT_POSE"
  }
}
```

The v2 union also reserves a strictly typed future `SUPPORTED` shape containing
integer `yaw_ppm`, `pitch_ppm` and `roll_ppm`. The current accepted backend may
only emit `UNAVAILABLE`. A v2 repeat may not use an empty object, numeric zeros
without `state`, additional keys or a free-form reason.

A repeat attached to a v2 D03 observation must itself be v2. Historical v1
observations retain v1 repeats. Downgrade fails closed while any v2 repeat
exists. Baseline, SelfState, routing and public request/response shapes do not
change; pose-unavailable is not a dimension failure.

### Fresh runtime boundary

The live adapter must:

1. resolve only a current admitted D02 generic SOURCE Asset using public IDs,
   canonical digests and the exact source namespace;
2. load bytes through an injected Worker-only byte-loader capability;
3. verify JPEG bytes, size, dimensions and digest against the Asset row;
4. create a new M3 backend for every JobAttempt;
5. invoke the native runner exactly three times via
   `prepare_source_group()`;
6. validate runtime, model, topology and measurement configuration digests;
7. project 478 landmarks and all six typed measurements into three D03 v2
   repeats; and
8. hand the typed evidence to the existing atomic `complete()` transaction.

Old D02 M3 rows, result-store rows or receipts cannot substitute for fresh
execution. Equal deterministic output digests are allowed; freshness is proven
by a new backend instance, current Attempt and three runner invocations.

### Private source and runtime composition

D02 Subsystem Principal remains custodian of the accepted source bytes and
runtime locators. It may perform one idempotent, put-if-absent materialization
of the four accepted JPEGs into the existing logical D02 source storage keys,
or inject an equivalent opaque byte-loader capability into a controlled Worker
process. It must not change PostgreSQL authority or expose a path, Prompt,
image byte, credential or locator.

The backend factory is installed once in the controlled Worker process and
cannot be rebound. Worker restart requires the D02 custodian to reinstall the
same capability from existing authority; the Worker never scans a directory.

### Dedicated execution queue

D03 live tasks use `mirror.demo.analysis.m3`. The message remains the existing
reference-only `analysis_run_id/job_id/request_id` envelope. Only a Worker with
the installed M3 capability consumes this queue. Capability absence must be
detected before claim so a Job remains PENDING for reconciliation; an ordinary
`mirror.demo` Worker must not claim and terminalize it as a runtime failure.

Local execution likewise requires explicit capability injection. Celery is an
adapter and remains outside domain/application logic. The accepted Windows
prototype backend runs with solo concurrency and no public-network egress;
Linux CI validates serialization, registration and fail-closed composition but
does not claim native Windows execution.

## File and ownership boundary

Implementation may modify only the following bounded areas:

- one forward D03 migration and migration/schema tests;
- `demo_models.py` repeat pose constraint;
- `demo_analysis_service.py` typed v2 pose projection;
- a D03 source-authority/byte-loader adapter;
- `mirror_worker/demo_analysis_runtime.py` and its tests;
- Principal-owned Worker runtime, local and Celery registration files.

It must not modify D02 historical operators, D02 private registries, public API
schemas, OpenAPI, generated clients, production/formal tables or M3 historical
acceptance.

## Acceptance

- legacy v1 repeat replay remains unchanged;
- v2 `UNAVAILABLE` and future typed `SUPPORTED` shapes are exact and canonical;
- invalid/cross-version pose rows fail closed in real PostgreSQL;
- fresh upgrade, forward upgrade, downgrade guard, re-upgrade, single head and
  `alembic check` pass;
- each successful Attempt performs three native M3 calls and writes exactly one
  Observation, three Repeats, one Baseline and one SelfState;
- cancel, lost lease, retry, redelivery and publication failure leave no partial
  result graph;
- incapable workers cannot claim D03 work;
- no message, log, exception, Git file or CI artifact contains private bytes or
  locators; and
- a controlled Windows run on at least one admitted source plus same-SHA CI and
  final Principal review pass before D03 `TASK_ACCEPTED`.

## Rejected alternatives

- zero-valued pose: fabricates evidence;
- D02 frontal-presentation attestation as pose: not a runtime measurement;
- stored D02 M3 output as D03 fresh output: violates freshness;
- locators or source bytes in Celery messages/settings: violates private input
  non-propagation;
- one backend shared across jobs: leaks state and violates repeat semantics;
- ordinary queue fallback: can consume and terminalize work without capability;
- cross-host RPC or a new custody/host-binding layer: outside this Demo scope.
