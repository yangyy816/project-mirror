# ADR-056: Streamed private post-registration verification

## Status

Accepted for bounded R60 implementation planning. It does not authorize a
canary, Provider call, decode, Vision/M3, runtime use, source admission, or
successor dispatch.

## Context

ADR-054 requires digest-bound durable operation records and complete
history/replay verification. R60 reproduced unbounded memory growth while the
deterministic success-chain persists and verifies twenty synthetic operation
results. The current controller repeatedly materializes historical state and
result structures during a single invocation.

## Decision

1. The set of receipts, plans, results, registration artifacts, capability
   bindings and checkpoint fields verified by ADR-054 remains unchanged.
2. R60 may replace in-memory historical collection with streamed iteration and
   bounded summaries containing only the exact anchor fields needed by later
   checks. It must not cache unverifiable historical JSON or omit a required
   file/digest/canonical-byte verification.
3. Before each external operation boundary, the controller must still establish
   the exact durable chain and current tip. Terminal, recovery and successor
   verification retain complete evidence verification.
4. A streamed implementation must reject the same malformed, missing,
   substituted, stale, duplicate and tampered records as the prior controller.
   Existing create-once, lease, unknown-outcome and no-retry semantics remain
   immutable.
5. The repair is internal/private only: no persisted schema, public API,
   OpenAPI, migration, Provider, policy, model/runtime, ledger or CAL-REQ state
   may change.

## Alternatives considered

- **Skip historic verification after the initial call.** Rejected: tampering
  between external operation boundaries could go unnoticed.
- **Cache all parsed historical state.** Rejected: it preserves the resource
  failure and creates mutable authority.
- **Relax the test's operation count or landmark cardinality.** Rejected: that
  weakens the frozen CC06 qualification boundary.

## Consequences

R60 implementation must demonstrate semantic-equivalence negative controls,
bounded resource behavior and fresh-process recovery before it can unblock the
R59 full regression gate. A failure to do so remains fail closed.
