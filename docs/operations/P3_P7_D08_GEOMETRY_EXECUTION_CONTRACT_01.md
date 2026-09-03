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

The accepted D02 backend set is not a general geometry editor. Its warp plans
bind the four admitted source images, their original landmark frames and a
fixed case matrix. The final admitted successor universe is intentionally
heterogeneous under ADR-053: forty-seven cases retain the accepted OpenCV
identity and exact Case 25 uses the accepted source-byte-only targeted repair
identity. D08 v1 must preserve both that boundary and the per-case identity.

## Frozen v1 scope

`D08_ORIGINAL_SOURCE_FIXED_CASE_GEOMETRY_V1` permits Geometry only when all of
the following are true:

- the input is the editing Session's current sequence-0 ImageVersion;
- sequence-0 bytes and digest equal the Session's admitted D02 SOURCE root;
- the sequence-0 input Asset is the immutable D07 original-snapshot Asset: its
  ID is distinct from the root SOURCE ID, while byte size, media type,
  dimensions, SHA-256 and bytes are equal, and its AssetVariant is exactly
  `root SOURCE -> input snapshot` with type
  `demo_p3_p7_original_snapshot`;
- the root is one of the four SOURCE Assets in the completed D02 admission;
- the case is one of the thirty-two result sides in the admitted sixteen-pair
  QuestionBank and its pair/report/manifest authority replays;
- a D02 RESULT, deleted Asset, non-synthetic Asset or later ImageVersion is
  rejected;
- `dimension_key` is exactly `jaw_width`, `chin_height` or `eye_spacing`;
- `abs(delta_ppm)` is exactly `15_000` or `30_000`;
- the sign maps exactly to `INCREASE` or `DECREASE`; and
- the accepted D02 report contains one unique source/dimension/direction/
  magnitude case.

Backend selection is an exact closed mapping. The frozen OpenCV algorithm is
eligible for ordinary admitted cases. `d02-targeted-jaw-repair-v1` is eligible
only for Case 25 (`source 3 / jaw_width / DECREASE / 15000`) and uses its own
configuration/recipe digest. No third algorithm, alternate selector, fallback
or matrix-wide configuration coercion is permitted.

The complete historical forty-eight-case manifest is eligibility and
plan-binding authority only. Only the thirty-two sides selected by the final
QuestionBank are runnable. Unselected cases, including the known failing
`chin_height` Case 05, remain honest screening evidence and fail closed as
editing capabilities. Historical bytes, ResultM3 rows and PASS state cannot
be replayed as the current execution or verification result.

The existing `demo-tool-registry-v1`, `demo-edit-planner-v1`, OperationSpec,
public request/response and reference-only task message remain unchanged.
Makeup and Generative remain unavailable. Geometry remains
`CAPABILITY_GATED` when no qualified runtime is installed.

## Internal execution authority

The repository reconstructs, from locked PostgreSQL rows, an immutable
`GeometryExecutionAuthority` containing:

- editing Session and plan IDs and authority digests;
- operation ID plus two non-interchangeable digests:
  `operation_authority_digest` is the persisted
  `DemoEditOperation.content_digest`, while `operation_spec_digest` is the
  deterministic digest of that row's frozen `OperationSpec` projection;
- current input ImageVersion ID and digest;
- input Asset and root SOURCE Asset IDs and SHA-256 values;
- D02 admission and screening report IDs and digests;
- exact case ID, digest and ordinal;
- dimension, direction and magnitude;
- warp-plan, geometry-ontology and source-landmark digests;
- output policy and determinism versions;
- accepted backend identity; and
- a canonical authority digest over every preceding field.

The case supplies the accepted algorithm, runtime-manifest and configuration
digests. The backend candidate ID is not present in the generic D02 report, so
it comes only from the tracked two-entry mapping: the already accepted
`providers.opencv_geometry.CANDIDATE_ID`, or the ADR-053 targeted candidate for
the exact Case-25 selector. It cannot come from HTTP, the task message or an
untrusted database scalar, and the installed per-case backend must match the
resulting complete identity.

`ExecutionCommand` receives the repository-derived Session, plan, both
operation digests, input
ImageVersion and root bindings plus the typed authority. HTTP and Celery
payloads cannot provide or override them. Geometry requires the authority;
Raster and transition operations forbid it. Every plan/operation/image/root/
case/backend field must agree bidirectionally.

Geometry `engine_digest` binds the registry engine version, accepted algorithm
and runtime identity. Geometry `config_digest` binds the plan, operation,
case, warp plan, output policy, verifier policy, both operation digests and
authority digest. The two operation digests use different schemas and must
never be compared as if they were the same value.

## Fresh execution evidence

The approved adapter creates a new backend execution for the current Attempt.
Its evidence has two explicit layers.

`GeometryStableMaterializationCore` excludes Job and Attempt identity and
contains:

- operation ID, operation authority/spec digests, authority, case, backend and
  warp-plan bindings;
- input ImageVersion, input Asset and root SOURCE bindings;
- result SHA-256, byte size, media type, dimensions and changed-pixel count;
- engine and config digests; and
- a canonical stable-core digest.

`GeometryAttemptExecutionEvidence` contains:

- Job binding, Attempt, operation ID, both operation digests and authority
  bindings;
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

An aggregate PASS cannot hide a failing repeat. The integrated selected-side
Gate produces canonical `GeometryMatrixQualification/v2` evidence ordered by
source, selected dimension, direction, magnitude and repeat index. For the
current admitted bank this is 32 cases (4 sources × 2 selected dimensions × 2
directions × 2 magnitudes). For every selected
source/dimension/direction and each repeat index it requires:

```text
abs(target delta at magnitude 30_000) >=
abs(target delta at magnitude 15_000)
```

The matrix evidence contains the selected dimension keys, selected-pair
manifest digest, ordered terminal Verification digests, ordered repeat deltas,
every comparison boolean, policy version and a cross-case Gate digest. That
digest is bound into the D08 integrated acceptance result and its policy
digest. It is a qualification Gate over the fresh selected matrix, not a
database prerequisite for an isolated post-qualification user operation.
Negative tests must fail the Gate when any repeat violates monotonicity or when
the terminal set differs from the admitted selected sides.
The matrix requires one shared source/M3/model/topology/network authority while
allowing the two exact case algorithms to retain distinct M4 recipe and
configuration identities. It never normalizes Case 25 back to the predecessor
OpenCV identity.

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
the controlled process. The bundle contains the shared accepted M3/source
authority plus exactly the standard OpenCV executor and, when present in the
admitted matrix, the Case-25 targeted executor. If the registered allowed-task
scope does not include D08, it returns `PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED`;
no process may scan for or infer a locator.

The task message remains reference-only. Missing capability fails before
source-byte loading and before Job claim. The accepted Windows Demo process
uses serial execution and denied public-network egress.

## Acceptance

D08 can be `TASK_ACCEPTED` only after:

- all 32 admitted QuestionBank result sides execute fresh; unselected cases
  remain capability-unavailable;
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
