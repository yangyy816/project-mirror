# P2-M5-R64-R03 — serializer authority repair

`STATUS: EXECUTING`

## Trigger

R64-R02 security review correctly observed that Python module-private names are
not an enforceable capability boundary: an in-process caller could retrieve the
private token and invoke the serializer with a forged attestation.

## Repair

The bridge module no longer contains a function that accepts
`LegacyOverlayAttestation`. The sole bridge-creation function performs exact
legacy receipt verification and immediately serializes its local verifier
result. No callable serializer accepts a caller-provided attestation, digest or
factory token.

## Regression evidence

Focused tests use a procedural non-human legacy receipt created by the
unchanged overlay. They verify real receipt-based bridge creation and reject
tampered receipt/bridge, cross-controller reuse and future ordinal references.

## Scope boundary

No legacy overlay byte, old receipt, schema, migration, OpenAPI, Provider,
policy, image generation, decode or M3 behavior changes. A new same-SHA CI and
independent review remain required.
