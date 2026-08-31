# P2-M5-R64-R02 — legacy receipt authority repair

`STATUS: EXECUTING`

## Trigger

Independent security and final reviews rejected R64-R01 candidate
`79291210b8d23850fff77bcce3fd290fcfdf1a6d`: bridge creation accepted a
caller-built attestation payload and its self-computed digest without forcing
verification of the exact legacy receipt.

## Repair

`create_or_verify_cal_req_004_bridge_from_legacy_receipt` now accepts the
exact receipt path plus controller, receipt, state, registration, action and
output anchors. It calls `verify_cal_req_004_once` before delegating to the
internal bridge serializer. The serializer is not a public authority entry.

Focused tests create a procedural non-human temporary legacy receipt using the
unchanged overlay, then verify legitimate bridge creation and reject receipt
tampering, cross-controller reuse, bridge tampering and future ordinals.

## Scope boundary

No legacy overlay byte, legacy receipt, schema, migration, OpenAPI, Provider,
policy, image generation, decode or M3 behavior changes. R64 remains pending a
new candidate, same-SHA CI, artifact inspection and independent reviews.
