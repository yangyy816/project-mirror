# P3–P7 D02 Change Control 03 — Prototype Revision Allocation Addendum

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_03
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
STATUS: PRINCIPAL_ACCEPTED
DISCOVERED_BY: D09 PostgreSQL provenance corrective change
BASE_SHA: 0c83682599da5794dc562cb710f2da8d36cf5cff
INDEPENDENT_SOL_EXACT_SHA_REVIEW: PASS_FOR_5c2dfff4f93626d1bda2131350756e9bf35a25d5
REVIEW_FINDINGS_P0: 0
REVIEW_FINDINGS_P1: 0
REVIEW_FINDINGS_P2: 0
D02_TASK_ACCEPTED: NO
D02_PRIVATE_SCREENING: CLOSED
D03: BLOCKED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This addendum changes only the unimplemented D02 forward-migration allocation frozen as a candidate in
`P3_P7_D02_CC_02`. It does not alter Candidate 3 algorithms, schemas, payloads, digest domains, manifests, test matrices,
private-runtime boundaries or review evidence.

## Superseded reservation

```text
OLD_MODULE: demo_0004_d02_measurement_quality_authority.py
OLD_REVISION: demo_0004_d02_quality_auth
OLD_DOWN_REVISION: demo_0003_d02_import_auth
OLD_IMPLEMENTATION_STATUS: NOT_CREATED
OLD_DISPOSITION: SUPERSEDED_UNIMPLEMENTED_DO_NOT_CREATE
```

The old candidate revision must not be created, cherry-picked or represented as historical schema authority. No
accepted migration byte is rewritten because the reservation has never been implemented.

## New D02 allocation

```text
NEW_MODULE: demo_0005_d02_measurement_quality_authority.py
NEW_REVISION: demo_0005_d02_quality_auth
REVISION_LENGTH: 26
NEW_DOWN_REVISION: demo_0004_d09_episode_prov
PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

`demo_0004_d09_episode_prov` is the immediate corrective migration allocated by
`CC-P3-P7-DEMO-D09-02`. This ordering preserves a single Demo head and lets the independently open D09 ledger domain
repair its proven database authority gap without waiting for D02 private screening.

Rejected alternatives:

- two revisions directly descending from `demo_0003`, which creates multiple heads;
- a merge revision for two not-yet-created siblings;
- modifying `demo_0001`–`demo_0003`;
- assigning D09 `demo_0005` behind a D02 migration that is not yet open;
- silently reusing the reserved `demo_0004` name without this addendum.

## Preserved D02 authority

All of the following remain byte- and semantics-preserved from `P3_P7_D02_CC_02` and its accepted peer manifest:

- measurement observability and fixed quantization;
- exact three-repeat source and result certification;
- v3 facts/source-manifest/import authority;
- v2 SourceM3 and ResultM3 records;
- v4 Measurement Gate;
- complete Report v2 group/cardinality/order/digest requirements;
- 48-case, 96-M4, 144-ResultM3, image/pHash, pair, eligibility and selection evidence;
- fail-closed PostgreSQL equality matrix;
- private runtime and D03 execution Gates.

Pure Packet B work remains open under its existing two-file boundary. Migration/ORM work remains closed until Packet B
pure-domain bytes receive Principal acceptance and independent exact-bytes review.

## Future migration lifecycle

When D02 migration implementation is eventually authorized, it must prove:

```text
fresh 0014 -> demo_0005 head
demo_0004 -> demo_0005
demo_0005 -> demo_0004 on a database with no new-version D02 authority
demo_0004 -> demo_0005
populated D02 v3/v2/v4 authority downgrade -> FAIL_CLOSED
alembic heads: single head demo_0005_d02_quality_auth
alembic check: zero drift
formal non-Demo DDL drift: zero
```

Historical reports that correctly bind execution at `demo_0003` remain historical evidence and are not mechanically
rewritten. Current-head assertions and prototype-only CI ancestry checks move forward only when the corresponding
migration is actually implemented.

## Exit disposition

```text
P3_P7_D02_CC_03_ACCEPTED: YES
D02_MIGRATION_REVISION: demo_0005_d02_quality_auth
D02_MIGRATION_IMPLEMENTATION: CLOSED_PENDING_PURE_DOMAIN_ACCEPTANCE
D02_PRIVATE_SCREENING: CLOSED
D02_TASK_ACCEPTED: NO
D03: BLOCKED
FORMAL_MAINLINE_IMPACT: NONE_EXPECTED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```
