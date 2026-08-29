# P3–P7 D05/D07 Application Authority Change Control 01

## Disposition

```text
CHANGE_CONTROL: CC-P3-P7-DEMO-APPLICATION-01
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_FOR_IMPLEMENTATION
DISCOVERED_BY: D05_AND_D07_APPLICATION_INTEGRATION_MAPPING
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

The accepted D01-B schema remains the prototype baseline, but application mapping found two
correctness gaps that cannot be repaired by guessing JSON shapes or by publishing an unverified
derived Asset. This change control adds only the minimum forward Demo authority required for D05
profile materialization and D07 non-publication. It changes no formal mainline authority and grants
no fresh M3/M4 runtime evidence.

## D05 profile materialization authority

The compile request continues to use the frozen public contract. Its SelfState anchor is resolved
without wall-clock ordering:

1. collect the distinct SelfState IDs referenced by consumable, non-invalidated questionnaire runs
   owned by the actor and session;
2. if exactly one exists, use it;
3. if none exists, use a SelfState only when the actor/session owns exactly one row;
4. multiple candidates, cross-anchor evidence, or an ownership mismatch fails closed.

`created_at`, maximum version, or an implicit “latest” query must never select the anchor.

Every compiler `AuthorityEvent` binds both its deterministic projection digest and the immutable
source `DemoPreferenceEvent.content_digest`. The projection digest cannot replace the ledger digest.

Add branch-local forward migration `demo_0012_d05_profile_authority.py`:

```text
REVISION: demo_0012_d05_profile_auth
DOWN_REVISION: demo_0011_d03_job_recovery
PROTOTYPE_MIGRATION: TRUE
```

The migration must:

- add partial uniqueness for `demo_job_binding_id` on desired-delta and style profiles;
- add nullable `demo_job_binding_id`, `desired_delta_profile_id`,
  `compilation_watermark`, and `compiler_version` to identity constraints;
- require those four fields together for compiler materializations and all four to be null for
  explicit command snapshots;
- enforce one compiled constraint row per `(job binding, constraint scope)`;
- add append-only `demo_self_transfer_dimension_evidence` rows containing an owned RESULT run,
  dimension key, desired delta ppm, confidence ppm, verifier outcome, and canonical digest;
- enforce one dimension row per self-transfer RESULT and validate that its parent/result/verifier
  authority is consistent.

One successful compile atomically creates exactly:

```text
1 DemoDesiredDeltaProfile
1 DemoStyleProfile
1 PERSISTENT DemoIdentityConstraints
1 current-session SESSION_OVERRIDE DemoIdentityConstraints
```

The same Job replay returns that exact group and creates no new version. A rollback leaves none of
the four rows. Explicit constraint commands remain separate append-only snapshots and do not
pretend to be compiler output.

## D07 materialize, verify, then promote

Unverified bytes must not become a normal `Asset`. Generic Asset ownership is not a quarantine
boundary, and `DemoImageVersion(version_kind=QUARANTINED)` alone cannot prevent normal Asset access.

Add branch-local forward migration `demo_0013_d07_publish_authority.py`:

```text
REVISION: demo_0013_d07_publish_auth
DOWN_REVISION: demo_0012_d05_profile_auth
PROTOTYPE_MIGRATION: TRUE
```

The migration adds immutable `demo_edit_artifacts` reservations and append-only
`demo_edit_artifact_events`:

- a reservation binds actor, session, operation, execution JobBinding, exact JobAttempt, and a
  deterministic private result object key before storage write;
- events are ordered per reservation and limited to `MATERIALIZED`, `PROMOTED`, `REJECTED`,
  `CANCELLED`, and `CLEANED`;
- the materialized event locks SHA-256, byte size, dimensions, MIME and engine/config digests;
- promotion binds the new Asset, AssetVariant, VerificationResult, and ImageVersion;
- rejected/cancelled/cleaned events never bind an Asset or ImageVersion;
- every update/delete of either authority fails closed.

`DemoToolRun` binds the materialized artifact rather than treating it as an Asset. A completed tool
run therefore proves deterministic execution, not publication. `DemoVerificationResult` gains the
exact verifier JobAttempt and artifact binding. Its result shape is:

```text
PASS         -> output Asset and ImageVersion required
FAIL         -> output Asset and ImageVersion forbidden
HUMAN_REVIEW -> output Asset and ImageVersion forbidden
```

Only PASS promotes the already-private object into an immutable derived Asset and creates a normal
ImageVersion. FAIL/HUMAN_REVIEW maps the Job to REJECTED and leaves only quarantine authority;
cleanup is an explicit later event. Storage success followed by a DB failure remains recoverable
from the pre-existing reservation and deterministic key. A retry inspects the exact object and may
append the missing MATERIALIZED event only after checksum/metadata validation.

## Required gates

- real PostgreSQL migration upgrade/downgrade/re-upgrade, `alembic check`, single head, zero drift;
- populated downgrade fails closed;
- canonical payload/digest and append-only trigger coverage for every added authority;
- profile same-Job replay, concurrent actor compilation, four-row rollback and anchor ambiguity;
- exact SelfTransfer dimension/verifier projection and source-ledger digest binding;
- storage-before-DB crash recovery, duplicate Worker delivery and conflicting result object;
- PASS-only Asset/ImageVersion promotion and FAIL/HUMAN_REVIEW non-publication;
- verifier JobAttempt/JobBinding consistency and owner/session isolation;
- restore/rollback creates a new verified version and never overwrites history.

## Boundary

This change control is product persistence authority, not a new custody/preflight layer. It does not
search for an M3 handle, create private evidence, call a Provider, alter D02 final status, authorize
real-user validity, or claim biometric identity preservation. Runtime-dependent gates remain
deferred until they are genuinely exercised.
