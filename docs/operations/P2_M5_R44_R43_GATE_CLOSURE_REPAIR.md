# P2-M5-R44 — R43 Gate Closure Repair

## Task contract

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R44`
- `OBJECTIVE`: close the four deterministic blockers found by the independent R43 Security and Sol High reviews
  without mutating the accepted CC05-A genesis or consuming `CAL-REQ-002`.
- `WHY_THIS_TASK_EXISTS`: candidate `8becae2c9f81794b0e7ae0d46e4df155ce072b64` passed local and same-SHA CI,
  but independent review correctly rejected its incomplete receipt/source binding, non-terminal registration errors,
  partial-transition crash window, and missing `REQUEST_ORDINAL` Prompt substitution.
- `SCOPE`: the R43 controller and non-human synthetic tests, this forward repair record, and the current
  Acceptance/Execution conditional tail.
- `FORBIDDEN_SCOPE`: no image generation, private Prompt export, private locator, private byte read, ordinal
  consumption, decode, QA, screening, admission, QuestionBank release, MVR, M6, schema, migration, public API,
  dependency, model, workflow, MEMORY, shared-summary or P2-M7 change.
- `DEPENDENCIES`: accepted CC05-A/R42 at `40a239831985b76dd55788a4ede6d98d60438f3d`; rejected conditional R43
  candidate `8becae2c9f81794b0e7ae0d46e4df155ce072b64`; R30 register-before-decode ordering.
- `ESCALATION_CONDITION`: any need to overwrite a committed transition, discover a private directory, weaken
  retry-zero, trust a URL/data URL, decode before a commit receipt, or alter V3 product policy.

## Review findings accepted as defects

1. A non-empty non-URL string and any ordinary file inside a caller-supplied root could be asserted as native
   imagegen provenance. The exact output hint was not durably bound before file access.
2. Registration validation/copy exceptions returned control without automatically committing
   `OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE`, so a replacement receipt or file could be attempted.
3. Event and state files could be complete while the receipt was absent. Exact replay then failed on the existing
   files and no fresh-process roll-forward path existed.
4. `REQUEST_ORDINAL` was declared as an accepted private template placeholder but was absent from the substitution
   mapping.

R44 treats all four as deterministic implementation defects. The green R43 run remains honest evidence for that
exact rejected candidate and is not reused as R44 acceptance evidence.

## Exact transition recovery

Each transition file remains canonical UTF-8/LF, deterministic, create-new and immutable. The controller now handles
an exact predecessor replay as follows:

- an absent event/state/receipt is created, flushed, closed and reread;
- a pre-existing plain file is accepted only when its bytes are exactly the canonical bytes the same predecessor and
  same inputs would create;
- any existing-byte mismatch is `CREATE_NEW_EXISTING_CONTENT_CONFLICT` and fails closed;
- no directory listing, glob, search, mutable latest pointer, overwrite, alternate root or timestamp guessing is
  allowed.

This permits fresh-process roll-forward when interruption happens after a complete event, state or receipt write.
It does not turn an exact replay into a second generation attempt or second resource consumption. A different action,
timestamp, ordinal, output ID, receipt digest or allowed-root digest cannot reuse the deterministic sequence.

## Returned-output and registration binding

The output opaque ID is fixed in `DISPATCH_PREPARED`, before the native call. After the tool returns:

1. `OUTPUT_RETURNED_UNREGISTERED` first commits returned/raw counters and formal raw-capacity consumption without
   reading source bytes, size, magic, dimensions, path metadata or image metadata.
2. `OUTPUT_RETURNED_RECEIPT_BOUND` then stores only the SHA-256 of the exact Principal-received imagegen output-hint
   string, bound to action, ordinal and the predeclared output opaque ID. Prompt text and the private absolute path are
   not written into the overlay.
3. `OUTPUT_REGISTRATION_ATTEMPT_BOUND` consumes the single registration attempt before any file validation or byte
   read. It binds the returned receipt digest and the exact allowed-root string digest.
4. Registration derives the source path from that exact bound output hint; there is no independent caller-selected
   source-path parameter. It must be an absolute plain file under the exact absolute allowed root and outside the
   overlay. URL/data URL, newline/NUL, symlink/reparse, root escape and receipt substitution fail closed.
5. A successful path creates or exact-verifies the byte-preserving staging copy, output record and registration
   receipt. Only the final hash-bound overlay receipt opens `decode_authorized=true`.
6. Any validation, copy, record or receipt error automatically commits
   `OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE`, clears the active call and permanently leaves decode closed. An exact
   replay may recover the same failure receipt; a changed receipt, root or source cannot become success.

The private record stores the output-hint digest rather than the private path. This is Principal-local tool-bound
provenance, not Provider attestation and not production `ImageGenerationProvider` evidence.

## Frozen state machine after R44

```text
READY
  -> DISPATCH_PREPARED
  -> DISPATCH_STARTED_CONSUMED
  -> OUTPUT_RETURNED_UNREGISTERED
  -> OUTPUT_RETURNED_RECEIPT_BOUND
  -> OUTPUT_REGISTRATION_ATTEMPT_BOUND
  -> OUTPUT_REGISTERED_PRE_DECODE

DISPATCH_STARTED_CONSUMED
  -> DISPATCH_FAILED_FINAL

OUTPUT_REGISTRATION_ATTEMPT_BOUND
  -> OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE
```

`retry=0`, concurrency `1`, call/raw/global ceilings, the accepted CC05-A resource ledger and every downstream Gate
remain unchanged.

## Prompt closure

The substitution map now contains all four declared fields:

- `REQUEST_ORDINAL`
- `DECLARED_AGE_BAND`
- `MORPHOLOGY_DESCRIPTOR`
- `STYLE_DESCRIPTOR`

Unknown or malformed format fields produce the allowlisted
`PRIVATE_PROMPT_PLACEHOLDER_RENDER_FAILED` error. Prompt plaintext remains Principal-process-only and must not enter
Git, logs, artifacts, MEMORY or reviewer material.

## Required evidence before acceptance

1. Focused tests must prove fresh-process roll-forward after injected interruption at complete event, state and receipt
   boundaries.
2. Tests must prove returned counters precede receipt/path/file inspection, source hint/output ID/ordinal binding,
   automatic terminal failure, no replacement after failure, no URL/data URL, and registration-before-decode.
3. A template segment must exercise `{REQUEST_ORDINAL}` directly.
4. Ruff, strict mypy, focused/affected/full Python, TypeScript/contracts, no-private scans and canonical/mirror checks
   must pass.
5. A new normal non-force candidate must pass same-SHA three-job CI, all eight artifact-family inspections, independent
   Security/Privacy/License/Research review, independent Sol High review and Principal acceptance.

Until all five pass, accepted CC05-A remains current, `P2-M5-R43-Q01` is closed and `CAL-REQ-002` is not dispatched.

## Candidate status

- `P2_M5_R44_STATUS: READY_FOR_TRACKED_EVIDENCE`
- `P2_M5_R43_PRINCIPAL_ACCEPTANCE: DENIED_AT_8BECAE2_AFTER_SECURITY_AND_SOL_REVIEW`
- `P2_M5_R44_IMAGEGEN_CALLS: 0`
- `P2_M5_R44_ORDINALS_CONSUMED: 0`
- `P2_M5_R44_PRIVATE_ROOTS_CREATED: 0`
- `P2_M5_R44_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN: 0`
- `NEXT_READY_TASK_AFTER_ACCEPTANCE: P2-M5-R43-Q01_PRIVATE_EXECUTION_OVERLAY_MATERIALIZATION`
