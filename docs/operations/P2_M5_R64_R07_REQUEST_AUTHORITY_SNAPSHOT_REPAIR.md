# P2-M5-R64-R07 — request-authority snapshot repair

`STATUS: EXECUTING`

## Trigger

The R06 independent security review found that the public `Mapping` input to
the request reference could provide different values to digest recomputation
and subsequent bridge checks.

## Repair

`PostRegistrationRequestReference` now copies and freezes the authority mapping
at construction. Digest and bridge validation therefore consume the same,
immutable authority snapshot. A focused regression mutates the caller's source
mapping after construction and proves the verifier uses the frozen snapshot.

## Scope boundary

No legacy overlay byte, old receipt, schema, migration, OpenAPI, Provider,
policy, image generation, image decode, M3, runtime/model artifact, or
QuestionBank behavior changes. R64 remains pending validation, same-SHA CI,
artifact inspection, independent reviews, and Principal acceptance.
