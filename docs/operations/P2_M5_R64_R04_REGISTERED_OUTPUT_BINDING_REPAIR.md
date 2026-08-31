# P2-M5-R64-R04 — registered-output binding repair

`STATUS: EXECUTING`

## Trigger

Independent R03 security review found that the bridge factory still accepted a
caller-supplied output digest rather than deriving it from verified registration
evidence.

## Repair

The public factory now requires the task-scoped project root and invokes
`verify_registration_before_decode` after exact legacy receipt verification.
The bridge records the verifier-derived `source_sha256`; it no longer accepts a
caller-provided output digest.

## Scope

No legacy overlay byte, old receipt, schema, migration, OpenAPI, Provider,
policy, image generation, decode or M3 behavior changes. R64 remains pending a
new candidate, same-SHA CI, artifact review and independent reviews.
