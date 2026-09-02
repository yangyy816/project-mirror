# ADR-053: D02 Targeted M4 Repair Successor Evidence

## Context

D02 autonomous runtime completed four source admissions, twelve source-M3 repeats, forty-eight
cases, ninety-six M4 executions, one hundred forty-four result-M3 repeats, and forty-eight sealed
artifact reviews without further Provider calls. The immutable V1 screening report then failed
closed because Case 25 (`source 3 / jaw_width / DECREASE / 15000`) measured a repeat-consistent
reverse micro-increase. Case 05 remains a separate truthful failure, but `eye_spacing` already has
eight of eight eligible pairs, so repairing Case 25 is sufficient to make `jaw_width` the second
complete dimension.

The Owner approved `APPROVE_M4_TARGETED_ALGORITHM_REPAIR` and rejected source/Manifest
reselection, alternative pair semantics, side reuse, mixed-magnitude pairs, and a fourteen-pair
degradation. Provider calls remain seven. V1 evidence, results, decisions, checkpoint, and report
must remain immutable.

The existing live executor uses one global recipe/backend version, but the persisted R2 authority
binds geometry algorithm, warp plan, runtime config, execution config, case ID, and case
specification per case. The formal report does not require all forty-eight cases to share one
geometry algorithm version. Therefore a composite successor can replay forty-seven predecessor
cases and replace exactly Case 25 without rerunning the complete backend.

The predecessor checkpoint does not retain the 478 source landmarks. A repair that silently reruns
source M3 would violate the Owner boundary. The targeted algorithm therefore must consume only the
already-bound canonical source JPEG and fixed Case 25 selector; it cannot depend on recovered or
new source landmarks.

## Decision

### 1. Exact scope

The only backend reexecution selector is:

```text
case_ordinal = 25
source_ordinal = 3
dimension_key = jaw_width
direction = DECREASE
magnitude_ppm = 15000
```

The successor executes exactly two M4 replays, three result-M3 repeats, and one new Principal
artifact review for this selector. It performs zero source-M3 calls, zero Provider calls, and zero
M4/result-M3 calls for the other forty-seven cases. Any out-of-scope invocation fails closed.

### 2. Versioned repair algorithm

`D02_TARGETED_JAW_REPAIR_V1` is a deterministic, source-byte-bound image-space mesh warp. It uses
the canonical source JPEG, fixed image dimensions, fixed centered lower-face mask, and a
versioned strength/configuration payload. It does not load landmarks, discover files, call a
network service, or use the predecessor result as an untracked input.

The algorithm produces a canonical JPEG twice and requires byte equality, positive changed-pixel
count, exact dimensions, and stable result digest. Its policy fixes:

```text
minimum_effect_margin_ppm = 10
target direction = strictly negative
target absolute delta <= predecessor Case 26 absolute delta for every repeat
existing target maximum and control-drift limits remain unchanged
```

Changing strength, mesh, mask, encoding, or algorithm code creates a new repair implementation
digest and successor case identity. Attempts are private development evidence; only the accepted
configuration may enter the successor universe.

### 3. Immutable predecessor and successor overlay

The V1 FAILED report, REVIEWED checkpoint, result store, and all predecessor records remain
byte-identical. A separate successor result store and checkpoint hold the Case 25 replacement.

The successor authority binds:

- predecessor V1 report ID, report/content digest, and `FAILED` status;
- predecessor checkpoint payload digest;
- repair policy and implementation digests;
- exact backend scope `[25]` and `provider_reexecution = false`;
- predecessor and successor Case 25 identities;
- two successor M4 record digests;
- three successor result-M3 record digests;
- successor result output/digest and one new review observation;
- forty-seven ordered predecessor slot digests and one replacement slot digest;
- twelve predecessor source-M3 record digests;
- counts `M4=2`, `result-M3=3`, `manual review=1`, `source-M3=0`.

The successor formal R2 report is rebuilt from the composite forty-eight-case universe. Case 26 is
not reexecuted, but its magnitude-monotonicity projection is deterministically recomputed against
the successor Case 25. Manual decision sequence changes caused by a new Case ID are derived
projections bound to the old observation digest, not new human reviews.

The exact-key R2 report cannot carry predecessor metadata. A separate private successor provenance
envelope binds the V1 report to the PASSED successor report. PostgreSQL admission continues to
store the existing formal report schema; no migration or public API change is authorized.

### 4. Recovery

Stages are monotonic:

```text
PREDECESSOR_REVIEWED_FAILED
→ REPAIR_POLICY_VALIDATED
→ TARGET_M4_DURABLE
→ TARGET_RESULT_M3_COMPLETE
→ TARGET_REVIEW_REQUIRED
→ SUCCESSOR_REVIEWED
→ SUCCESSOR_SCREENING_REPLAYED
→ ADMISSION_READY
→ ADMITTED
```

Once replacement bytes are durable, later failures replay those bytes and cannot execute M4
again. A non-empty successor store without a valid successor checkpoint fails closed. The
predecessor store is never overwritten or reused as a write target.

### 5. QuestionPair projection

QuestionPair semantics remain same-source, same-dimension, same-magnitude, opposed-direction
result pairs. Database columns `left_delta_ppm/right_delta_ppm` are nominal requested deltas and
must equal `-magnitude_ppm/+magnitude_ppm`. Real measured deltas remain immutable in pair-side
screening evidence and the QA payload. Substituting measured values into nominal columns fails
closed.

### 6. Admission boundary

Only a PASSED successor report with complete provenance may enter the existing single-transaction
generic coordinator. Admission must verify four sources, sixteen QuestionPairs, thirty-two
distinct result sides, fifty-two Assets, forty-eight AssetVariants, replay, payload collision,
concurrent unique winner, rollback, and zero partial rows.

## Alternatives

### Rerun all forty-eight cases

Rejected. Full-report cardinality is a replay requirement, not a backend reexecution requirement.
It would violate the Owner's targeted scope.

### Rerun all four `jaw_width / DECREASE / 15000` cases

Rejected. No persisted family-wide algorithm-version invariant requires it. Only Case 25 failed.

### Recover landmarks by rerunning source M3

Rejected. Source-M3 reexecution is explicitly forbidden and unnecessary for the chosen
source-byte-only repair.

### Change QuestionPair semantics, reduce cardinality, or reselect sources

Rejected by Owner decision.

### Persist predecessor lineage in PostgreSQL

Deferred. The current exact schema has no predecessor columns and the Owner did not authorize a
migration. The private successor envelope and public integration package carry this lineage.

## Consequences

- V1 stays permanently `FAILED_CLOSED` and remains auditable.
- Only Case 25 receives new result bytes and execution/measurement/review authority.
- The repair can proceed without Provider calls, source-M3 replay, new landmarks, migration, or
  public contract drift.
- Success remains fail-closed if the repaired case does not satisfy direction, minimum effect,
  control drift, artifact, repeatability, and Case 26 monotonicity Gates.
- The final integration package must disclose the exact backend reexecution scope and that
  PostgreSQL does not persist predecessor lineage directly.

## Status

Accepted — Owner-approved targeted repair authority, 2026-09-02.
