# P2-M5-R45 — R44 Gate Closure Repair

## Task contract

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R45`
- `OBJECTIVE`: close the two deterministic R44 review blockers without changing the accepted CC05-A genesis,
  state machine, resource counters, public contract, private state or `CAL-REQ-002`.
- `DEPENDENCIES`: accepted CC05-A/R42 at `40a239831985b76dd55788a4ede6d98d60438f3d`; rejected R43
  candidate `8becae2c9f81794b0e7ae0d46e4df155ce072b64`; rejected R44 candidate
  `50b1de2c9fedfd0dd6997560f3c3c3a1c404e575`.
- `FORBIDDEN_SCOPE`: image generation, private input discovery or access, Prompt export, ordinal consumption,
  decode, QA, screening, admission, schema, migration, API, dependency, model, workflow, MEMORY and Gate changes.

## Review findings accepted as defects

1. The R44 source/root checks could be separated from the later ordinary `Path.open()` call. A source or allowed
   root replacement between those operations could redirect byte access.
2. `format_map` accepted composite format fields despite the four-field Prompt declaration. Attribute, index,
   positional, conversion and format-spec syntax therefore exceeded the declared contract.

R44 remains rejected evidence. Its same-SHA run and artifacts are not R45 acceptance evidence.

## Frozen repair behavior

- POSIX opens the absolute allowed root component by component with retained directory descriptors,
  `O_NOFOLLOW`, `dir_fd`, `fstat` type checks and a root identity recheck. The source is opened from the retained
  parent descriptor and only that opened descriptor is read.
- Windows opens and retains volume/root/intermediate/source handles with `CreateFileW`, read-only sharing that
  excludes write/delete, `FILE_FLAG_OPEN_REPARSE_POINT`, handle type/reparse checks and final-path bindings.
  Any capability, handle or binding failure fails closed.
- Source and ancestor descriptor/handle ownership is explicit across safe-open, CRT `fdopen`, validation and
  context teardown. Every exceptional path closes the resources it acquired before returning the terminal failure.
- A source/reparse/root replacement failure still commits the existing automatic
  `OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE` terminal transition. It creates no staging copy, authorizes no decode
  and cannot be retried or replaced.
- Prompt rendering uses `string.Formatter().parse`. Only the four exact declared field names, with neither a
  conversion nor a format specification, are accepted. Escaped literal braces remain valid; every other format
  field error is `PRIVATE_PROMPT_PLACEHOLDER_RENDER_FAILED`.

The immutable R44 state machine, returned-counter ordering, `retry=0`, concurrency `1`, registration-attempt
semantics and accepted CC05-A fallback remain unchanged.

The R45 machine-readable true-EOF authority preserves all 375 R44 predecessor keys, applies only the exact
review-driven overrides and appends 30 R45 closure keys. Acceptance and Execution therefore each contain the same
405-key ordered block; no current state is inherited implicitly from a rejected partial overlay.

## Required evidence before acceptance

Focused synthetic tests prove source and allowed-root replacement at the validate/open boundary has zero-byte
copy, decode closed and an automatic terminal result; ordinary source copying remains byte preserving. They also
prove each composite Prompt form is rejected and escaped braces plus four exact names render. A new candidate still
requires same-SHA CI, all artifact checks, independent Security/Privacy/License/Research/Sol review and Principal
acceptance. Until then CC05-A is current, R43-Q01 is closed and `CAL-REQ-002` is not dispatched.

## Candidate status

- `P2_M5_R45_STATUS: READY_FOR_TRACKED_EVIDENCE`
- `P2_M5_R45_IMAGEGEN_CALLS: 0`
- `P2_M5_R45_ORDINALS_CONSUMED: 0`
- `P2_M5_R45_PRIVATE_ROOTS_CREATED: 0`
- `P2_M5_R45_PRIVATE_IMAGE_BYTES_READ_OR_WRITTEN: 0`
