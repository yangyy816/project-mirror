# P2-M5-R64-R06 — request-reference digest repair

`STATUS: EXECUTING`

## Trigger

The independent R05 security review found that a caller could construct a
`PostRegistrationRequestReference` with legitimate authority fields but a
forged digest and matching display prefix. The v2 transition compared fields
but did not recompute the canonical digest before persisting it.

## Repair

The independent verifier now recomputes SHA-256 over the canonical request
authority mapping and requires it to equal the supplied digest before any
bridge/state comparison or successor write. A focused regression constructs a
forged dataclass directly and verifies fail-closed rejection.

## Scope boundary

No legacy overlay byte, old receipt, schema, migration, OpenAPI, Provider,
policy, image generation, image decode, M3, runtime/model artifact, or
QuestionBank behavior changes. R64 remains pending new local validation,
candidate commit, same-SHA CI, artifact inspection, independent reviews, and
Principal acceptance.
