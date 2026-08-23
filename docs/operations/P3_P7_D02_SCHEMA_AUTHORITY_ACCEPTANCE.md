# P3–P7 D02 Schema Authority Checkpoint Acceptance

## Decision

```text
TASK: D02 — synthetic identities / mini bank / pair QA
CHECKPOINT: D02_SCHEMA_AUTHORITY_CHECKPOINT
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
REVIEWED_CANDIDATE_SHA: ba7dd1b9db406f39b9eb523f93bf2eb2f15a3f7d
INTEGRATED_SHA: 2b903084c2b28c422f4362496fe832a107b341d5
INDEPENDENT_SOL_EXACT_SHA_REVIEW: PASS
INDEPENDENT_SOL_FINDINGS: NONE
SAME_SHA_CI_RUN: 32672168021
D02_SCHEMA_AUTHORITY_CHECKPOINT: TASK_ACCEPTED
D02_PRIVATE_SCREENING: NOT_VERIFIED
D02_TASK_ACCEPTED: NO
D03: BLOCKED
R_DEMO_03: OPEN
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This is a forward acceptance record for the Revision 9 schema and PostgreSQL admission authority. The
`PENDING_INDEPENDENT_SOL_REVIEW` markers embedded in the reviewed change-control and preregistration blobs describe
their pre-review state; this record supplies the later Principal disposition without rewriting those reviewed bytes.

## Accepted boundary

The checkpoint accepts only:

- the Revision 9 source-import, measurement, screening-report, selection and bank-admission contract;
- branch-local prototype migration head `demo_0003_d02_import_auth`;
- the corresponding Demo ORM projection and real PostgreSQL validation/immutability triggers;
- schema-shaped tests, adversarial PostgreSQL tests and prototype CI boundary checks.

The reviewed D02 authority blobs are byte-identical between the reviewed candidate and the integrated merge. The merge
does not grant formal migration authority, P2 dimension promotion, production geometry, real-face processing or a
QuestionBank release.

## Exact-SHA validation evidence

GitHub Actions run `32672168021` completed successfully for exact integrated SHA
`2b903084c2b28c422f4362496fe832a107b341d5`:

```text
secret-scan: PASS
docker-validation: PASS
quality-and-integration: PASS
python: 941 passed, 1 explicit skip
strict mypy: 132 sources PASS
playwright: 5/5 PASS
migration head: demo_0003_d02_import_auth
OpenAPI drift: PASS
license/SBOM: PASS
```

The same-SHA artifacts were present and unexpired when reviewed:

```text
project audit: 9501762153
Demo boundary: 9501758961
Playwright: 9501754424
Docker: 9501686669
Gitleaks: 9501669743
```

## Mandatory negative evidence

The existing positive schema fixture uses `mirror.demo/D02FixtureEvidence/v1`; it fabricates result checksums,
64×64/4096-byte image metadata, changed-pixel counts and several true Gate values. It proves only that the frozen
PostgreSQL graph accepts a structurally valid payload and rejects the registered adversarial mutations.

Therefore none of the following is accepted by this checkpoint:

```text
REAL_SOURCE_M3_12: NOT_VERIFIED
REAL_M4_EXECUTIONS_96: NOT_VERIFIED
REAL_RESULT_M3_144: NOT_VERIFIED
REAL_48_CASE_MEASUREMENT_GATES: NOT_VERIFIED
REAL_48_CASE_MANUAL_REVIEW: NOT_VERIFIED
REAL_52_IMAGE_EXACT_SHA_GATE: NOT_VERIFIED
REAL_1326_PHASH_OBSERVATIONS: NOT_VERIFIED
REAL_24_PAIR_SCREENING: NOT_VERIFIED
REAL_SELECTED_16_PAIR_BANK: NOT_VERIFIED
P4_MULTI_DIMENSION_ACTIVE_ROUTING: NOT_VERIFIED
ALGORITHMIC_PROTOTYPE_PLATFORM: NOT_VERIFIED
```

D00 dimension artifacts remain `D00_FEASIBILITY_ONLY` and `NOT_D02_PAIR_QA`. They may establish runtime entry
conditions, but they cannot be promoted into D02 result evidence.

## Principal decision

Revision 9 is open for a bounded real executor/report-builder implementation and Principal-custodied offline
screening. Full D02 acceptance requires the fixed 4-source/48-case execution, explicit manual decisions, real
PostgreSQL report and selected-bank admission, independent exact-SHA review and same-SHA CI. Until all those steps
finish, D03 implementation remains dependency-gated and R-DEMO-03 remains open.
