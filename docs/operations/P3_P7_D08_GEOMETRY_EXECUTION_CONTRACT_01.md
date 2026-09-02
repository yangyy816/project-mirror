# P3–P7 Demo D08 Fixed-Case Geometry Execution Contract 01

## Decision status

```text
CONTRACT_ID: P3_P7_D08_GEOMETRY_EXECUTION_CONTRACT_01
STATUS: PRINCIPAL_ACCEPTED_FOR_IMPLEMENTATION
TRACK: DEMO_PROTOTYPE
BASE_SHA: a669275890565e98075ed09d0adee63669b89ff3
SCOPE: PRIVATE_SYNTHETIC_ONLY
PRODUCTION_AUTHORIZATION: NONE
PUBLIC_API_CHANGE: NONE
OPENAPI_CHANGE: NONE
MIGRATION_CHANGE: NONE
NEW_DEPENDENCY_OR_PROVIDER: NONE
```

## Problem

D08 already has a typed registry and deterministic planner, but the actual D07
Worker composition installs no Geometry dispatcher. Geometry therefore remains
correctly fail-closed. Historical D02 M4 rows prove that the accepted private
OpenCV capability executed its frozen synthetic cases; they are not evidence
that a new D07 editing Job executed or passed an independent verifier.

The accepted D02 backend is not a general geometry editor. Its warp plans bind
the four admitted source images, their original landmark frames and a fixed
case matrix. D08 v1 must preserve that boundary.

## Frozen v1 scope

`D08_ORIGINAL_SOURCE_FIXED_CASE_GEOMETRY_V1` permits Geometry only when all of
the following are true:

- the input is the editing Session's current sequence-0 ImageVersion;
- sequence-0 bytes and digest equal the Session's admitted D02 SOURCE root;
- the root is one of the four SOURCE Assets in the completed D02 admission;
- a D02 RESULT, deleted Asset, non-synthetic Asset or later ImageVersion is
  rejected;
- `dimension_key` is exactly `jaw_width`, `chin_height` or `eye_spacing`;
- `abs(delta_ppm)` is exactly `15_000` or `30_000`;
- the sign maps exactly to `INCREASE` or `DECREASE`; and
- the accepted D02 report contains one unique source/dimension/direction/
  magnitude case.

The historical case and result rows are eligibility and plan-binding
authority only. Their bytes, ResultM3 rows and PASS state cannot be replayed as
the current execution or verification result.

The existing `demo-tool-registry-v1`, `demo-edit-planner-v1`, OperationSpec,
public request/response and reference-only task message remain unchanged.
Makeup and Generative remain unavailable. Geometry remains
`CAPABILITY_GATED` when no qualified runtime is installed.

## Internal execution authority

The repository reconstructs, from locked PostgreSQL rows, an immutable
`GeometryExecutionAuthority` containing:

- editing Session, plan and operation IDs and digests;
- current input ImageVersion ID and digest;
- input Asset and root SOURCE Asset IDs and SHA-256 values;
- D02 admission and screening report IDs and digests;
- exact case ID, digest and ordinal;
- dimension, direction and magnitude;
- warp-plan, geometry-ontology and source-landmark digests;
- output policy and determinism versions;
- accepted backend identity; and
- a canonical authority digest over every preceding field.

`ExecutionCommand` receives the repository-derived Session, plan, input
ImageVersion and root bindings plus the typed authority. HTTP and Celery
payloads cannot provide or override them. Geometry requires the authority;
Raster and transition operations forbid it. Every plan/operation/image/root/
case/backend field must agree bidirectionally.

Geometry `engine_digest` binds the registry engine version, accepted algorithm
and runtime identity. Geometry `config_digest` binds the plan, operation,
case, warp plan, output policy, verifier policy and authority digest.

## Fresh execution evidence

The approved adapter creates a new backend execution for the current Attempt.
Its evidence has two explicit layers.

`GeometryStableMaterializationCore` excludes Job and Attempt identity and
contains:

- operation, authority, case, backend and warp-plan bindings;
- input ImageVersion, input Asset and root SOURCE bindings;
- result SHA-256, byte size, media type, dimensions and changed-pixel count;
- engine and config digests; and
- a canonical stable-core digest.

`GeometryAttemptExecutionEvidence` contains:

- Job binding, Attempt, operation and authority bindings;
- the stable-core digest;
- the fresh backend execution receipt; and
- a canonical Attempt-specific receipt digest.

`MaterializedObject` carries this evidence for Geometry and forbids it for
Raster or transitions. The adapter writes new bytes to quarantine; it cannot
accept a historical D02 result as an output input.

The MATERIALIZED event already persists the stable replay surface: result
digest, byte size, media type, dimensions, engine digest and config digest.
If the process crashes after MATERIALIZED but before terminal publication, a
later Attempt re-executes the deterministic provider and compares only its new
stable core and bytes with that persisted surface. It then creates a new
Attempt-specific execution receipt and fresh M3 verification bound to the new
Attempt. The later Attempt never claims equality with the lost old
Attempt-specific evidence and never invents an unpersisted receipt.

## Independent verifier

An injected `IndependentGeometryMeasurementPort` performs fresh accepted M3
source and result observations. It does not trust an M4 boolean or historical
ResultM3 row. Its canonical evidence binds:

- analyzer/runtime/model/topology/config identities;
- source/result SHA-256 and landmark digests;
- three fresh source and three fresh result repeat digests;
- six ordered measurements for each of the three repeat indexes;
- three ordered signed target deltas and five ordered control drifts per
  repeat;
- the per-repeat direction, minimum, maximum and control-drift Gate booleans;
- max non-target drift and its dimension;
- operation, case and JobAttempt; and
- decode, artifact and original-immutability checks.

The per-execution Geometry policy reuses the accepted D02 thresholds for each
of the three repeat indexes independently:

```text
target direction = requested direction
10 <= abs(measured target delta ppm) <= 60_000
max control drift ppm <= 20_000
decode/artifact/original immutability = PASS
source digest != result digest
```

An aggregate PASS cannot hide a failing repeat. The integrated 48-case Gate
also produces canonical `GeometryMatrixQualification/v1` evidence ordered by
source, dimension, direction, magnitude and repeat index. For every
source/dimension/direction and each repeat index it requires:

```text
abs(target delta at magnitude 30_000) >=
abs(target delta at magnitude 15_000)
```

The matrix evidence contains the ordered terminal Verification digests,
ordered repeat deltas, every comparison boolean, policy version and a
cross-case Gate digest. That digest is bound into the D08 integrated acceptance
result and its policy digest. It is a qualification Gate over the fresh matrix,
not a database prerequisite for an isolated post-qualification user operation.
Negative tests must fail the Gate when any repeat violates monotonicity.

The requested 15k/30k value is warp magnitude, not an assertion that measured
delta equals that value. Geometry uses its dedicated evaluator and then emits
the existing complete `EffectVerificationResult` categories.

## Persistence and publication

No table or column is added. Existing `DemoVerificationResult.metrics` and
`thresholds` store the complete fresh execution and independent measurement
evidence, explicit integer thresholds, identities and policy digest. The
Verification content digest and ImageVersion verifier digest therefore bind
the complete evidence, not only a PASS boolean.

External runtime/storage work occurs without a PostgreSQL lock. The terminal
transaction re-locks Job/Attempt, Session, plan, operation, input ImageVersion,
root D02 authority and artifact. If the input is no longer current sequence-0,
the result is `REJECTED_STALE_INPUT_VERSION`.

Only a complete PASS may create the final Asset, AssetVariant and ImageVersion.
Reject, human-review, cancel, lost lease, stale input or verifier failure
creates none of those publication rows. Quarantine cleanup remains idempotent
and best-effort after durable terminal authority exists.

## Private capability boundary

D02 Subsystem Principal remains the private-input custodian. Integration
Principal never reads or receives runtime locators, Prompt, image paths or
bytes. For the real Gate, D02 Subsystem Principal must verify that its existing
registry permits the D08 purpose, then install opaque M3/M4 factories inside
the controlled process. If the registered allowed-task scope does not include
D08, it returns `PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED`; no process may scan
for or infer a locator.

The task message remains reference-only. Missing capability fails before
source-byte loading and before Job claim. The accepted Windows Demo process
uses serial execution and denied public-network egress.

## Acceptance

D08 can be `TASK_ACCEPTED` only after:

- all 48 source × dimension × direction × magnitude cases execute fresh;
- each case has fresh source/result M3 verification;
- each repeat independently passes direction, 10–60,000 target magnitude and
  20,000 maximum control-drift Gates;
- each source/dimension/direction/repeat-index pair passes the 30k ≥ 15k
  magnitude-monotonicity Gate and the cross-case digest replays;
- substitution of any source, ImageVersion, plan, case, backend, warp plan,
  result or verifier identity fails closed;
- target/control/decode/artifact/original checks each have negative coverage;
- crash, redelivery, lease expiry, cancel and concurrency publish zero partial
  rows;
- Raster/transition behavior and Makeup/Generative fail-closed behavior regress
  cleanly;
- Local and real Redis/Celery controlled paths pass;
- no private locator, byte, landmark or object key enters Git, messages or
  ordinary logs; and
- integrated same-SHA CI and an independent final review pass.

This acceptance is Demo-only and private-synthetic-only. It grants no real-user
or production Geometry capability.

## Rejected alternatives

- treating D02 historical M4/ResultM3 as a new D07 execution;
- applying an original-source warp plan to sequence greater than zero;
- silently snapping an arbitrary planner delta to 15k/30k;
- trusting provider-returned PASS, measured delta or drift without independent
  M3 verification;
- sending locators, bytes, landmarks or runtime handles in a task message;
- falling back to fixed PASS or zero drift when the verifier is unavailable;
- accepting aggregate measurements while any repeat or cross-magnitude
  monotonicity comparison fails;
- comparing a new Attempt receipt with unpersisted evidence from a crashed
  prior Attempt;
- adding persistence schema solely for intermediate in-process evidence; or
- expanding this contract to a new Provider, dependency, production or real
  user scope.
