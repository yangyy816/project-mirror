# P2-M5-R64-R08 — idempotent request-reference revalidation repair

`STATUS: EXECUTING`

## Trigger

The R06 final review found two residual request-reference authority gaps: a
stateful `Mapping` could change between reads, and the idempotent-successor
path compared only the stored digest before returning success.

## Repair

The v2 append operation materializes authority exactly once before every
security decision. The idempotent-successor branch now reruns canonical digest,
display-reference, and bridge/state authority validation before returning the
existing successor. Focused regressions cover a stateful mapping and malformed
authority on an idempotent replay.

## Scope boundary

No legacy overlay byte, old receipt, schema, migration, OpenAPI, Provider,
policy, image generation, image decode, M3, runtime/model artifact, or
QuestionBank behavior changes. R64 remains pending validation, same-SHA CI,
artifact inspection, independent reviews, and Principal acceptance.
