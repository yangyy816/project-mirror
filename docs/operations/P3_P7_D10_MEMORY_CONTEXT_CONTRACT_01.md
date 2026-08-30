# P3–P7 D10 Memory and Context Application Contract 01

```text
TASK: D10 — Profile/Context Compiler, rebuild and next-session recall
TRACK: DEMO_PROTOTYPE
CONTRACT_ID: P3_P7_D10_MEMORY_CONTEXT_CONTRACT_01
STATUS: PRINCIPAL_FROZEN_FOR_IMPLEMENTATION
SCHEMA_CHANGE: NONE
ORM_CHANGE: NONE
PUBLIC_API_CHANGE: NONE
D02_PRIVATE_INPUT: NONE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

## Authority boundary

D09 remains the append-only PreferenceEvent and AcceptedVisualEpisode authority. D05 and D06 remain the structured
profile and accepted self-transfer/reference authorities. D10 may only create derived `DemoAestheticProfile` and
`DemoContextCompilation` rows through the existing PostgreSQL authority and Job/JobBinding state machine. It never
updates or deletes source evidence.

An event-only `IMAGE_ACCEPTED` is feedback, not a Final Save, and is never promoted into visual episode memory.
Only a valid `DemoAcceptedVisualEpisode` supplies durable accepted-visual evidence. Explicit current instructions and
locks outrank accepted self-transfer/reference evidence, which outranks Final Save and questionnaire-derived evidence.

## Deterministic lifecycle projection

The compiler replays the complete digest chain and derives an effective event view:

- `RESET` replaces the effective prefix with the already-verified state at its strict-earlier `reset_watermark`, then
  appends the RESET event itself. Later events remain eligible normally.
- `ROLLBACK` targeting an owned `AESTHETIC_PROFILE` replaces the effective prefix with the state at that profile's
  `as_of_event_sequence`, then appends the ROLLBACK event. Other rollback targets remain provenance-only for D10.
- `TOMBSTONE` and `DELETE` invalidate their exact target and D10 derivatives that directly depend on it. They do not
  remove ledger rows or source authority.
- A source with an event watermark is eligible only when that watermark remains in the effective event view. A source
  event digest must likewise remain effective.
- `reset_epoch` is the count of verified RESET events in full append-only history, so it never decreases.

The Profile compilation watermark is a digest of the compiler version, actor, complete ledger tail, effective event
sequences, reset epoch, invalidated targets and ordered source manifest. No wall clock, raw float or database audit
timestamp participates in Profile authority. Rebuilding the same watermark replays the same immutable row; another
idempotency key for the same immutable input fails closed instead of creating a competing generation.

## Context and recall

Context compilation requires an explicit timezone-aware `context_as_of_time` and current-instruction digest. The
compiler never reads wall clock as context authority. Expiry is deterministically `context_as_of_time + 30 minutes`.

The fixed `demo-context-compiler-v1` budget is:

```text
PROFILE_CORE: 1
PERSISTENT_CONTROL_EVENTS: 8
CURRENT_SESSION_EVENTS: 8
ACCEPTED_VISUAL_EPISODES: 4
TOTAL_SELECTED_EVIDENCE: 21
```

Stable ordering is priority, event sequence, authority kind and digest. Overflow remains present in
`rejected_evidence` with a non-sensitive reason. Previous-session temporary overrides are rejected and never recalled
into a new session. The current instruction is always first in the trace priority but is represented only by its
caller-supplied digest.

Recall requires the same actor/session ownership, an active non-invalidated AestheticProfile, an unexpired Context and
an explicit timezone-aware recall time. It never returns a tombstoned/deleted Context or Profile.

## Implementation boundary

Allowed implementation files are a D10-only application module and D10-only tests. The migration lease owned by the
D02 subsystem remains untouched: no migration, `demo_models.py`, public router/schema, OpenAPI/generated client,
Celery registration or D02 private state is modified by this slice.
