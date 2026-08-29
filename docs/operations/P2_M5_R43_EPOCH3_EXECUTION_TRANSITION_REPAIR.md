# P2-M5-R43 — Epoch-3 Append-only Execution Transition Repair

## Task contract

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R43`
- `OBJECTIVE`: close the accepted epoch-3 recovery gap before `CAL-REQ-002` by adding a controller whose execution
  overlay is append-only, receipt-addressed and recoverable without modifying the accepted CC05-A genesis bytes.
- `WHY_THIS_TASK_EXISTS`: the accepted CC05-A fixed entrypoint correctly verifies the zero-execution materialization,
  but its frozen semantic checks cannot verify a consumed ordinal, changed counters or a registered output. Directly
  changing that entrypoint or its control files would invalidate the accepted bootstrap, registry and receipt digests.
- `SCOPE`: controller, non-image synthetic tests, this repair record, and the canonical/mirror current-state tails.
- `ALLOWED_FILES_OR_MODULES`: `private_execution_overlay.py`, its focused tests, this record,
  `P2_M5_ACCEPTANCE.md`, and `P2_M5_EXECUTION_PROTOCOL.md`.
- `FORBIDDEN_SCOPE`: no image generation; no private Prompt export; no private locator or byte in Git; no mutation of
  CC05-A genesis; no ordinal consumption; no decode, QA, screening, admission, QuestionBank release, MVR, M6, schema,
  migration, public API, dependency, model, workflow, MEMORY, shared-summary or P2-M7 change.
- `DEPENDENCIES`: accepted CC05-A/R42 at `40a239831985b76dd55788a4ede6d98d60438f3d`, accepted R30
  register-before-decode ordering, and the existing `1/1/0`, `31/31`, `62`, `CAL-REQ-002` accounting authority.
- `INPUTS_AND_ASSUMPTIONS`: the current task-scoped epoch-3 receipt remains recoverable and verifies exactly; the
  overlay is materialized only after this repair is accepted.
- `RECOMMENDED_AGENT: Principal`
- `RECOMMENDED_MODEL_TIER: Sol High architecture / Terra High implementation semantics`
- `ESCALATION_CONDITION`: any requirement to mutate genesis, discover a private directory, relax retry-zero, decode
  before a valid registration receipt, or change the V3 product policy.

## Root cause and forward-only decision

CC05-A is an immutable materialization checkpoint, not a mutable execution ledger. Its fixed entrypoint deliberately
proves the initial `CAL-REQ-002: NOT_CONSUMED`, `31/31/62` state and exact eleven-file root. The E01 contract separately
requires every request attempt, dispatch, output count and registration to be append-only and fresh-process
recoverable. No accepted transition mechanism currently connects those two authorities.

R43 preserves every CC05-A byte and digest. After R43 acceptance, one new task-owned sibling overlay may be created
under the already authorized Git-ignored private namespace. Recovery starts from one exact receipt handle; it never
lists, globs, searches, guesses or chooses a latest file by modification time. Every transition creates three new
canonical UTF-8/LF files:

1. an event bound to the previous event digest;
2. a complete state snapshot bound to the previous state and current event digests; and
3. a receipt bound to the event, state, controller digest and previous receipt digest.

Files are create-new/no-overwrite, flushed, closed, reread and SHA-256 verified. Sequence numbers and filenames are
deterministic from the exact predecessor receipt. There is no mutable `latest` pointer and no directory discovery.

## Frozen state machine

```text
READY
  -> DISPATCH_PREPARED
  -> DISPATCH_STARTED_CONSUMED
  -> OUTPUT_RETURNED_UNREGISTERED
  -> OUTPUT_REGISTERED_PRE_DECODE

DISPATCH_STARTED_CONSUMED
  -> DISPATCH_FAILED_FINAL

OUTPUT_RETURNED_UNREGISTERED
  -> OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE
```

- `DISPATCH_PREPARED` changes no resource counter and binds the exact ordinal and opaque action ID durably.
- `DISPATCH_STARTED_CONSUMED` increments request and requested-output counts once, decrements formal call capacity and
  the global native-output reservation once, sets one active call and advances the never-reusable ordinal.
- `OUTPUT_RETURNED_UNREGISTERED` is written before any source byte, size, magic or metadata inspection. It increments
  returned/raw counts once and decrements formal raw capacity once.
- `OUTPUT_REGISTERED_PRE_DECODE` requires an exact tool-returned artifact handle, create-new byte-preserving staging
  copy, equal source/staging SHA-256, byte count, non-decoding magic/media classification, immutable output record and
  valid registration-commit receipt. Only this state sets `decode_authorized=true`.
- Any tool/zero-output failure is final for the consumed ordinal. Any registration failure after a returned output is
  the R30 hard stop `OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE`. Neither state permits retry, replacement, decode or a
  later ordinal.

Counter corrections are new events; existing events and receipts are never rewritten. `retry=0`, concurrency `1`,
formal request maximum `32`, formal raw maximum `32`, global native-output ceiling `64`, returned byte maximum `16 MiB`
and every existing storage/Vision/transform/holdout/downstream closure remain unchanged.

## Private Prompt boundary

The controller renders the already materialized private template only in the Principal process. It validates the exact
ordinal assignment and `plaintext_export=PROHIBITED`, substitutes the four accepted render fields deterministically,
and returns no seed or Provider fact. Prompt plaintext must not be printed, written to the overlay, committed, placed
in ordinary command logs, CI, artifacts, MEMORY or reviewer material. The built-in image generation call remains the
only permitted consumer after the overlay pre-dispatch receipt is valid.

## Pre-decode output record

The immutable private record binds every R30 field: opaque output ID, ordinal, source kind, delivery class, exact
generated-artifact receipt, source/staging SHA-256, byte size, media/magic class, generation specification and
assignment versions/digests, request/output statuses, custody, retention, cleanup policy, timestamp and predetermined
registration-receipt ID. The separate commit receipt binds the record digest and confirms `COMMITTED/VALID` while both
`decode_performed` and `dimensions_read` remain false.

The controller accepts only an exact plain-file artifact handle, rejects symlink/reparse inputs and overlay-internal
source substitution, never accepts a URL, and performs no decode or dimension read. Unknown magic is retained as
untrusted `application/octet-stream/UNKNOWN` for later hard QA rather than guessed or silently replaced.

## Sequencing after acceptance

R43 itself remains zero-generation and zero-private-mutation. Principal may perform exact receipt/control preflight
reads, but no private Prompt plaintext is exported and no private image byte is read. After all R43 Gates and Principal
acceptance:

1. `P2-M5-R43-Q01` creates exactly one overlay at an absent task-owned target and validates sequence zero;
2. a separate redacted forward evidence candidate binds only opaque IDs, controller/receipt/state digests, counters,
   zero-generation facts and the exact next task;
3. that evidence must pass same-SHA CI, artifact inspection, independent Security/Privacy/License/Research and Sol
   review plus Principal acceptance; and
4. only then may the Principal prepare and execute exact `CAL-REQ-002` with one built-in imagegen call and zero retry.

No step may mutate or retire the CC05-A genesis evidence. Overlay materialization failure creates no alternative root
and does not authorize image generation.

## Acceptance criteria and validation

1. The controller uses only the Python standard library, contains no network or Provider SDK, and performs no directory
   discovery.
2. Focused tests prove create-new recovery, predecessor hash chaining, exact ordinal ordering, prepare-before-consume,
   permanent counters, output-return accounting before byte access, register-before-decode, failure hard stops,
   tamper detection and private-template rendering policy using non-human synthetic bytes only.
3. Ruff format/check, strict mypy, focused and affected P2-M5 tests, `git diff --check`, no-private/no-binary/no-Prompt
   scans and canonical/mirror true-EOF checks pass locally.
4. The candidate changes no OpenAPI, migration, dependency, model artifact or workflow.
5. Normal non-force push, same-SHA three-job CI, all eight artifact-family inspections, independent
   Security/Privacy/License/Research review, independent final review and Principal acceptance pass before Q01.

## Candidate status

- `P2_M5_R43_STATUS: READY_FOR_LOCAL_VALIDATION`
- `P2_M5_R43_IMAGEGEN_CALLS: 0`
- `P2_M5_R43_ORDINALS_CONSUMED: 0`
- `P2_M5_R43_PRIVATE_ROOTS_CREATED: 0`
- `P2_M5_R43_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN: 0`
- `P2_M5_R43_DECODE_QA_SCREENING_ADMISSION: 0`
- `NEXT_READY_TASK_AFTER_ACCEPTANCE: P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION`
