# P2-M5-R64-R10 — authority-string matrix test repair

`STATUS: EXECUTING`

## Trigger

The R09 final review found that exact-string implementation guards existed, but
the focused matrix did not explicitly cover authority key and value subclasses.

## Repair

The regression matrix now rejects a subclassed authority key at construction
and a subclassed authority value injected before an idempotent replay. This is
test-only coverage for the already-implemented exact-type boundary.

## Scope boundary

No production source, legacy overlay, receipt, schema, migration, OpenAPI,
Provider, policy, image generation, image decode, M3, runtime/model artifact,
or QuestionBank behavior changes.
