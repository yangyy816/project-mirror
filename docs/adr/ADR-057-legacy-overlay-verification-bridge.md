# ADR-057: Legacy overlay verification bridge

## Status

Accepted by `OD-P2-M5-R64-LEGACY-OVERLAY-BRIDGE-001`.

## Context

The immutable `CAL-REQ-004` receipt binds the exact historical
`private_execution_overlay.py` SHA. R62/R63 resource improvements changed
that file and therefore cannot be accepted for the registered canary.

## Decision

The legacy overlay remains byte-exact and is verified once in a fresh process
against the receipt's pinned SHA. The verifier emits only a redacted,
digest-bound attestation for the exact `CAL-REQ-004` receipt. An independent
append-only bridge receipt then binds that attestation to a new resource-bounded
post-registration verifier. No legacy receipt is rewritten or re-pinned.

The bridge is allowlisted to one exact controller SHA, receipt SHA and ordinal;
it is never a general historic-receipt compatibility mechanism. Future
ordinals use only the new verifier authority.

The independent verifier creates a create-new v2 genesis and only an
append-only request-reference binding transition. Both durable-chain
verification and mutation use one cross-process lease. It re-reads a bounded,
deterministically named chain during recovery and treats any fork, stale tip,
root identity change, bridge mismatch or non-canonical record as invalid. A
small terminal verification index is an evicting performance cache only.

The existing post-registration verifier may receive the equivalent
invocation-local terminal-tip index only as a read-only resource bound. It does
not modify the legacy overlay, receipt format, state machine or controller pin
and cannot create a general legacy compatibility path.

## Consequences

R64 may add independent verifier/bridge modules and focused tests but may not
modify the legacy overlay, receipt, schema, public API, Provider or policy.
The bridge alone does not authorize image decoding, Vision/M3 or redispatch.
