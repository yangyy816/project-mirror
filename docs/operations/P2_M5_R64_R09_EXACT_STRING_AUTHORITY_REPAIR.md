# P2-M5-R64-R09 — exact-string authority repair

`STATUS: EXECUTING`

## Trigger

The independent R08 reviews found that `str` subclasses could override equality
or encoding behavior used by request-reference authority checks.

## Repair

All request-reference boundary fields and authority keys/values now require the
exact builtin `str` type. The verifier repeats this exact-type guard before
canonical digest comparison. Focused regressions reject string subclasses both
at construction and after an idempotent successor exists.

## Scope boundary

No legacy overlay byte, old receipt, schema, migration, OpenAPI, Provider,
policy, image generation, image decode, M3, runtime/model artifact, or
QuestionBank behavior changes. R64 remains pending validation, same-SHA CI,
artifact inspection, independent reviews, and Principal acceptance.
