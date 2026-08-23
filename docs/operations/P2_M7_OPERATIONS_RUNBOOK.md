# P2-M7 internal operations runbook

## Status and boundary

`NOT_DEPLOYED`. This runbook covers the accepted internal P2 operation contract and the R14 candidate composition of
accepted batch operations plus the read-only cost projection. R14 is not accepted until exact-SHA CI, artifact
inspection and independent review complete. This is not an admin API, dashboard, collector, Provider integration or
production approval. P2-M5 fresh study and P2-M6 release/revoke remain closed.

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

1. Confirm the environment is not `production`. Set `MIRROR_DATASET_DATABASE_ENVIRONMENT` to the exact CLI environment
   and provide `MIRROR_DATASET_DATABASE_URL` through the approved operator process boundary. Never print either value.
   Then invoke only `mirror-dataset` with explicit actor, reason, request correlation and expected immutable target
   state. Missing or mismatched configuration fails closed before composition; production fails before engine/session
   construction.
2. Request a batch cost summary through the T04 read port. It only reads accepted `GenerationBatch`,
   `GenerationItem`, and immutable `ProviderCostEvent` rows; it cannot create or modify evidence.
   The R14 candidate exposes this projection only in configured non-production environments. Actual and estimated
   amounts stay grouped by their own currency; pending and unavailable are counts rather than inferred money.
3. Emit the fixed `synthetic_dataset.cost_summary.projected` event only after the read succeeds. The event contains
   opaque batch/policy/request references, actor, reason and allowlisted category counts. It contains no Prompt,
   object key, image/landmark bytes, URL, raw Provider payload, credential, private path or user data.
4. If the batch is missing, malformed, production-bound, or its required application service is unavailable, stop
   fail-closed and preserve the stable reason code. Do not use SQL, a temporary script, or a Provider console fallback.
5. Retain PostgreSQL `ProviderCostEvent` and audit/evidence rows as authority. CLI output and payload-free logs are
   projections only; neither can override a hard gate, terminal evidence state or an unavailable cost fact.
6. `provenance_status` and `qa_status` remain stably unavailable. Do not replace them with SQL, storage inspection or
   invented authority while their accepted application-service capability is absent.

## Incident handling

- Treat `unavailable` as a missing cost fact, not as zero cost or permission to retry/generate.
- Treat different currencies as incomparable aggregates.
- Do not attach arbitrary diagnostic metadata to operational events. Escalate any need for a new event field, cost
  category, role model, schema, collector, dashboard or public endpoint through change control.
- Production operation remains disabled until a separate production authorization is accepted.
