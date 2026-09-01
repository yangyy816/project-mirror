# P3–P7 D10 Memory and Context Application Contract 01

```text
TASK: D10 — Profile/Context Compiler, rebuild and next-session recall
TRACK: DEMO_PROTOTYPE
CONTRACT_ID: P3_P7_D10_MEMORY_CONTEXT_CONTRACT_01
STATUS: OWNER_SUPERSEDED_FOR_QUEUED_CONTEXT_EXTENSION
SCHEMA_CHANGE: QUEUED_CONTEXT_REQUEST_RESULT_ONLY
ORM_CHANGE: QUEUED_CONTEXT_REQUEST_RESULT_ONLY
PUBLIC_API_CHANGE: CONTEXT_COMPILE_ADMISSION_ONLY
D02_PRIVATE_INPUT: NONE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

## 2026-09-01 Owner supersession

After D02 common-base ACK and D06 acceptance released the migration lease, the Owner explicitly authorized the next
serial node `D10_CONTEXT_QUEUED_COMPILER_AND_REBUILD`. This forward extension preserves every deterministic and
privacy boundary below while allowing exactly one successor migration after `demo_0016_d06_ref_profile_queue`, an
immutable Context compile request/result link, reference-only Job/Worker orchestration, and a typed Demo-only Context
compile admission route. It does not change D09 evidence semantics, D02 private state, production authorization or
the existing caller-provided `recall_at` reads.

The queued extension is frozen as follows:

- migration: `demo_0017_d10_context_queue`;
- admission: `POST /api/v1/demo/sessions/{session_id}/context/compile` with operation
  `demoCompileSessionContext`;
- Job authority: operation `context.compile`, type `demo_p3_p7.context.compile`, target `DEMO_SESSION`, capability
  `P7_CONTEXT_COMPILER`;
- immutable authority: `DemoContextCompileRequest/v1` and `DemoContextCompileResult/v1` joined to the existing
  `DemoContextCompilation`;
- execution: at most three attempts with a 300-second lease, opaque task references only, PENDING/expired-RUNNING
  reconciliation, and generic owner-bound cancellation;
- determinism: the request freezes the complete selected/rejected evidence, budgets, trace, profile digest,
  compilation watermark, explicit timezone-aware as-of, instruction digest and expiry. Execution must re-freeze and
  compare that complete snapshot before materialization; the queue clock is audit/lease metadata only. Admission and
  execution must also lock and revalidate the current actor/session lifecycle at the later of explicit as-of and audit
  time; tombstoned actors and closed, tombstoned or expired sessions reject without Context/result authority;
- idempotency: an exact key replays, a key/payload collision is rejected, and a second key for the same actor/frozen
  input is rejected with one PostgreSQL winner;
- atomicity: ContextCompilation, result authority, JobAttempt and Job terminalization commit together or not at all;
  cancellation, stale inputs, collisions and failures cannot leave a partial Context/result;
- privacy: Job/task payloads contain no raw user payload, Prompt, image bytes, private locator or credential.

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

Stable ordering is priority, ascending event sequence, authority kind and digest; non-event Profile authority uses the
fixed event-sequence sentinel `0`. Overflow remains present in
`rejected_evidence` with a non-sensitive reason. Previous-session temporary overrides are rejected and never recalled
into a new session. The current instruction is always first in the trace priority but is represented only by its
caller-supplied digest.

Recall requires the same actor/session ownership, an active non-invalidated AestheticProfile, an unexpired Context and
an explicit timezone-aware recall time. Recall revalidates every selected event and accepted-episode dependency against
the current effective ledger before returning. It never returns a tombstoned/deleted or lifecycle-stale Context or
Profile. A Reference Profile is active only while its linked Style/Constraints evidence and every accepted source
ImageVersion dependency remain active.

## Implementation boundary

The original internal slice changed only D10 application code and tests while D02 held the migration lease. The Owner
supersession above now permits the minimal queued-Context migration/ORM/router/schema/OpenAPI/client and Worker
registration needed for this serial node. D02 private state, D09 source-evidence semantics and non-D10 product
authority remain forbidden.
