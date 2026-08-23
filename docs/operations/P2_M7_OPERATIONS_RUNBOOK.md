# P2-M7 internal operations runbook

## Status and boundary

`NOT_DEPLOYED`. This runbook covers the accepted internal P2 operation contract and the pending T04 read-only cost and
operational-event projection. It is not an admin API, dashboard, collector, Provider integration or production
approval. P2-M5 fresh study and P2-M6 release/revoke remain closed.

## Cost projection meaning

`ProviderCostEvent` is the sole monetary authority for generation cost. The projection must report these categories
separately and must never sum them into a single asserted spend:

| Category      | Source                                       | Permitted interpretation                                                        |
| ------------- | -------------------------------------------- | ------------------------------------------------------------------------------- |
| `actual`      | `ProviderCostEvent.event_kind=final`         | Provider-posted final monetary fact, grouped by currency.                       |
| `estimated`   | `ProviderCostEvent.event_kind=estimated`     | Versioned pricing estimate, grouped by currency.                                |
| `unavailable` | terminal `GenerationItem` with no cost event | Absence of a provider monetary fact; it is never converted from request counts. |
| `pending`     | `REQUESTED` or `GENERATING` item             | Cost evidence is not terminal; it is neither zero nor unavailable.              |

Currency values remain separate. `actual`, `estimated`, `unavailable`, and `pending` must never be compared or
converted without a new approved pricing/FX authority.

## Operator procedure

1. Confirm the environment is not `production`, then invoke only the approved `mirror-dataset` application-service
   adapter with explicit actor, reason, request correlation and expected immutable target state.
2. Request a batch cost summary through the T04 read port. It only reads accepted `GenerationBatch`,
   `GenerationItem`, and immutable `ProviderCostEvent` rows; it cannot create or modify evidence.
   The current `mirror-dataset` `cost_summary` command remains fail-closed unavailable until T05 integrates this
   projection behind the accepted operator-service recovery and concurrency boundary.
3. Emit the fixed `synthetic_dataset.cost_summary.projected` event only after the read succeeds. The event contains
   opaque batch/policy/request references, actor, reason and allowlisted category counts. It contains no Prompt,
   object key, image/landmark bytes, URL, raw Provider payload, credential, private path or user data.
4. If the batch is missing, malformed, production-bound, or its required application service is unavailable, stop
   fail-closed and preserve the stable reason code. Do not use SQL, a temporary script, or a Provider console fallback.
5. Retain PostgreSQL `ProviderCostEvent` and audit/evidence rows as authority. CLI output and payload-free logs are
   projections only; neither can override a hard gate, terminal evidence state or an unavailable cost fact.

## Incident handling

- Treat `unavailable` as a missing cost fact, not as zero cost or permission to retry/generate.
- Treat different currencies as incomparable aggregates.
- Do not attach arbitrary diagnostic metadata to operational events. Escalate any need for a new event field, cost
  category, role model, schema, collector, dashboard or public endpoint through change control.
- Production operation remains disabled until a separate production authorization is accepted.
