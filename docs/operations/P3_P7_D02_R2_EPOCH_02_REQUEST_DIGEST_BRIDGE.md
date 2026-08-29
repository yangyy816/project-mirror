# P3–P7 D02-R2 Epoch 02 — Request Digest Bridge Repair

## Status

```text
TASK_ID: P3_P7_D02_R2_R09_EPOCH_02_REQUEST_DIGEST_BRIDGE
CHANGE_CLASS: FROZEN_ARCHITECTURE_CONTRACT_REPAIR
PARENT_AUTHORITY: P3_P7_D02_R2_EXECUTION_EPOCH_02
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED_PLAN_IMPLEMENTATION_PENDING
BASE_IMPLEMENTATION_SHA: 911f0fc97df76c66f5e456dbda43cc4865fb7a2c
E2_REGISTRY_EVENT_COUNT_AT_REPAIR_ENTRY: 0
CC11_OR_CC12: FALSE
EVIDENCE_CUSTODY_HOST_BINDING_CHANGE: NONE
MIGRATION_OR_ORM_CHANGE: NONE
PUBLIC_API_CHANGE: NONE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

The independent pre-execution review found one product-authority continuity
defect before any singleton authority bytes or ImageGen call were created.
The CC08 allocation schema retains the field
`generation_request_policy_digest`, while the accepted E2 invocation authority
uses `mirror.demo/D02R2Epoch2GenerationRequestPolicy/v1` and calls its digest
field `generation_request_digest`. The E1 request-policy validator is
intentionally bound to the failed-closed E1 root, producer and dispatch epoch;
it cannot be re-signed for E2 under the same semantics.

This repair freezes the missing bridge. It does not reopen CC09 or CC10, add
an evidence layer, mutate E1, alter the E2 root receipt, or weaken any call,
network, retry, concurrency, source, provenance or registry boundary.

## Canonical digest decision

For E2 only:

```text
CANONICAL_DISPATCHED_REQUEST_AUTHORITY:
  mirror.demo/D02R2Epoch2GenerationRequestPolicy/v1

CANONICAL_DISPATCHED_REQUEST_DIGEST:
  generation_request_digest

CC08_ALLOCATION_COMPATIBILITY_FIELD:
  generation_request_policy_digest

REQUIRED_EQUALITY:
  allocation.generation_request_policy_digest
  == generation_request.generation_request_digest
  == generation_receipt.generation_request_policy_digest

BRIDGE_SEMANTIC_VERSION:
  demo-d02-r2-e2-request-digest-bridge-v1
```

The legacy field name is retained because the private allocation and source
authority schemas already use it. It does not invoke, inherit or impersonate
`mirror.demo/D02R2GenerationRequestPolicy/v1`. E2 must never validate an E2
request through the E1 builder or validator.

## Exact non-cyclic construction order

The E2 reserve activation does not consume the allocation-manifest digest.
Therefore the following order is authoritative and acyclic:

```text
root receipt + cohort/capability authority
→ generation preregistration digest
→ pure projections of all source/provenance name receipts
→ E2 reserve activation
→ four exact E2 generation requests
→ four allocation entries whose compatibility field equals each request digest
→ source allocation manifest digest
→ producer dispatch digest
→ actual receipt allocation in frozen sequence 1..12
→ singleton output creation/seal/register in events 1..3
→ ImageGen release boundary
```

The actual name-receipt order remains:

1. `SOURCE_GENERATION_PREREGISTRATION`
2. `SOURCE_ALLOCATION_MANIFEST`
3. `SOURCE_PRODUCER_DISPATCH_RECEIPT`
4. ordinal 1 source
5. ordinal 1 provenance
6. ordinal 2 source
7. ordinal 2 provenance
8. ordinal 3 source
9. ordinal 3 provenance
10. ordinal 4 source
11. ordinal 4 provenance
12. preallocated cohort-failure `NEGATIVE_RECEIPT`

The singleton and negative name receipts are produced by
`P3_P7_D02_R2_EXECUTION_02`. Source and provenance name receipts are produced
by `P3_P7_D02_R2_SOURCE_COHORT_02`. The singleton authority payloads continue
to name the source producer where required by the frozen CC08 schemas.

## Mandatory bridge validation

The bridge implementation must be pure and must not resolve a root, path,
Prompt, image, registry, network client, database or Provider. It must prove:

- exact CC08 key sets and domain-separated digest replay for preregistration,
  allocation manifest and producer dispatch;
- four ordered allocations and four distinct E2 requests;
- exact equality of ordinal, E2 root, capability, preregistration, producer,
  epoch, source/provenance output IDs, name-receipt digests, Prompt-material
  digest, media types and byte ceilings;
- exact compatibility-field equality to the accepted E2 request digest;
- generation-receipt equality to the same digest and allocation tuple;
- fully re-signed allocation/manifest/request mismatches fail closed;
- unknown keys, E1 request digests, changed state, fifth ordinals, retries and
  replacement allocations fail closed; and
- deterministic replay produces byte-identical canonical payloads and digests.

## Execution and downstream boundary

No singleton authority or ImageGen call may occur until the bridge code and
tests pass targeted format, lint, strict typing and unit validation, the
changed-code exact-SHA CI passes, and an independent exact-SHA review returns
no blocking finding.

The existing `demo_d02_r2_authority` and `demo_0008` admission boundary remain
hard-bound to E1. Successful E2 source generation does not bypass that fact.
Before M3/M4-derived E2 source authority can enter PostgreSQL, a separate
product-forward schema/authority task must version the E2 root/epoch binding
and prove single-transaction admission. That later work is not an evidence,
custody or host-binding change control and cannot reinterpret E1.

## Private preflight output-name closure

The product execution preflight uses one pure projector before any create-new
name-receipt write. The projector and the registry writer must produce equal
payloads and equal `name_receipt_digest`; any mismatch stops before ImageGen.
Actual allocation remains ordered `1..12`.

The projector does not accept a caller-supplied bare parent digest as
authority. Sequence 1 derives its parent from the accepted generation
capability; every other sequence receives and validates the corresponding
preregistration, allocation-manifest or producer-dispatch authority object and
its accepted upstream graph, then derives the parent digest internally.
Allocation sequence uses a strict integer boundary, so JSON booleans and other
integer-like values fail before any create-new write.

The exact binding matrix is:

| Sequence | Semantic role                       | Parent authority                      | Producer           | Media type         | Maximum bytes |
| -------: | ----------------------------------- | ------------------------------------- | ------------------ | ------------------ | ------------: |
|        1 | `SOURCE_GENERATION_PREREGISTRATION` | accepted generation-capability digest | E2 execution task  | `application/json` |        262144 |
|        2 | `SOURCE_ALLOCATION_MANIFEST`        | preregistration digest                | E2 execution task  | `application/json` |        262144 |
|        3 | `SOURCE_PRODUCER_DISPATCH_RECEIPT`  | allocation-manifest digest            | E2 execution task  | `application/json` |        262144 |
| 4/6/8/10 | `SOURCE_CANDIDATE`                  | preregistration digest                | E2 source producer | `image/png`        |      20971520 |
| 5/7/9/11 | `SOURCE_PROVENANCE`                 | preregistration digest                | E2 source producer | `application/json` |        262144 |
|       12 | `NEGATIVE_RECEIPT`                  | producer-dispatch digest              | E2 execution task  | `application/json` |        262144 |

The unused sequence-12 receipt is allocation evidence only. It is not sealed
or registered unless the cohort actually fails. This narrow repair does not
reopen CC09/CC10, add a custody layer, change public API, migration, ORM or
Provider invocation, or authorize an ImageGen call before the three singleton
events replay equally in both registry copies.

```text
D02_R2_TASK_ACCEPTED: NO
D03: BLOCKED_PENDING_D02_R2_TASK_ACCEPTED
D04_B: BLOCKED_PENDING_D02_R2_AND_D03_TASK_ACCEPTED
D07_B: BLOCKED_PENDING_D02_R2_AND_D03_TASK_ACCEPTED
REAL_USER_VALIDITY: NOT_EVALUATED
PRODUCTION_SECURITY: DEFERRED_FOR_FORMAL_PHASE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```
