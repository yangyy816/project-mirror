# P3–P7 D02-R2 Forward Execution Plan Acceptance

## Decision

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_08
TRACK: DEMO_PROTOTYPE
STATUS: PRINCIPAL_ACCEPTED
ACCEPTED_PLAN_SHA: 218f4b5a5ee4e6e2223995d232da61496dd47de3
ACCEPTED_PLAN_TREE: 1cff56bd1f1127a310622d5b8a72045b39290549
PLAN_GOVERNANCE_COMMIT: c0cbcfe833f05952aac6c33c2f34583f366ea1ae
PLAN_BASE_SHA: 17f8f1edd84ab39925441b596152c1ff973ed03a
INDEPENDENT_SOL_EXACT_PLAN_REVIEW: PASS
INDEPENDENT_SOL_FINDINGS_P0_P1_P2_P3: 0/0/0/0
ACCEPTED_PLAN_SAME_SHA_CI: PASS
ACCEPTED_PLAN_SAME_SHA_CI_RUN: 32865068842
ACCEPTED_PLAN_SAME_SHA_CI_JOBS: 3_PASS
ACCEPTED_PLAN_SAME_SHA_CI_ARTIFACTS: 5_PRESENT_NOT_EXPIRED
OLD_D00_RECOVERY: CLOSED_NO_NEW_LEAD
CC07_HISTORICAL_RESULT: EVIDENCE_LOCATION_LOST
CC07_CURRENT_RESULT: NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE
REGISTRY_RECEIPT_IMPLEMENTATION: EXECUTION_READY
EVIDENCE_ROOT_CREATION: CLOSED_PENDING_REGISTRY_IMPLEMENTATION_ACCEPTANCE
SOURCE_GENERATION: BLOCKED_PENDING_SEPARATE_GENERATION_CAPABILITY_AUTHORITY
GENERATION_CALLS_AUTHORIZED_BY_CC08: 0
M3_M4_CORE_EXECUTION: BLOCKED_PENDING_ROOT_AND_RUNTIME_GATES
MIGRATION_IMPLEMENTATION: CLOSED_PENDING_SEPARATE_BOUNDED_TASK
POSTGRESQL_ADMISSION: CLOSED
D02_R2_TASK_ACCEPTED: NO
D02_TASK_ACCEPTED: NO
D03: BLOCKED
D04_B: BLOCKED
D07_B: BLOCKED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

## Accepted exact bytes

The Principal accepts revision 5 without rewriting its reviewed bytes:

| Authority file                             | SHA-256                                                            |
| ------------------------------------------ | ------------------------------------------------------------------ |
| `P3_P7_D02_AUTHORITY_CHANGE_CONTROL_08.md` | `d8702231045af9c705b9bccd2e26cce8d791823e9717574b317c91fbbef9da47` |
| `P3_P7_PROTOTYPE_AGENT_ROUTING.md`         | `a0a5e9678d1d28fa9146928b93bbf62d72a770717325d9fd8d36dde10f27ad31` |
| `P3_P7_DEMO_FAST_TRACK_CONTRACT.md`        | `34c5467a5d5030aa8d17c6983570217a47e472c8e6005535f2e7d210af1f0695` |
| `P3_P7_DEMO_RISK_REGISTER.md`              | `7295ef8dd2fc42d580a82432c6d606ef8b8e5fec5b77860223721e7a8ae54bcc` |

The accepted integration SHA is a descendant of the governance commit and contains those exact four blobs. Its only
intervening changes replace the externally failing licensed Gitleaks action with the exact OCI-digest-pinned Gitleaks
8.28.0 scanner, preserve complete-history scanning, bind the one historical public OpenAPI-digest false positive by
exact commit/path/match, and restore the existing SARIF artifact. These CI repairs do not change CC08 semantics.

The first attempted governance run, `32862520111`, is retained as negative operational evidence: its product quality
and Docker jobs passed, while the third-party action stopped before scanning because of its new license/API dependency.
Run `32863572563` proved the standalone scanner and all three jobs, but exposed the missing SARIF artifact. Final run
`32865068842` closed both defects: all three jobs passed and the five expected artifacts include
`gitleaks-results.sarif`.

## Acceptance boundary

This checkpoint accepts the forward-only plan and opens exactly one implementation boundary: the Principal-owned
root-receipt/two-copy-registry module and its fault tests. It does not create a private directory, receipt, SQLite
database, source image, runtime output, Report, QuestionBank row or PostgreSQL authority.

All future D02-R2 private execution evidence is confined to the single root identified publicly as
`P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT`, whose fixed basename is
`p3-p7-d02-r2-cc08-e1-evidence`. The absolute locator stays in Principal custody and never enters Git, CI artifacts,
ordinary logs, coordination mailboxes or `MEMORY.md`.

The root remains absent until an independently reviewed, exact tracked registry implementation supplies all three
authorities required by the root receipt:

```text
registry_schema_contract_digest
registry_normalized_ddl_sha256
registry_implementation_sha
```

Only after that implementation's targeted/fault tests, independent exact review, same-SHA CI and Principal acceptance
may the Principal create the root. The first immutable file must then be exactly
`D02_R2_EVIDENCE_ROOT_NAME_RECEIPT.json`; no subdirectory or second file may precede it.

## Unchanged stop states

CC07 remains immutable and is not reclassified as recovered. No legacy output ID, database row, inferred locator,
fixture, summary or new file may impersonate old D00 custody authority. CC08 authorizes no generation call, Provider
use, M3/M4 execution, migration, ORM change or PostgreSQL admission. Formal P3–P7 status and production authorization
remain unchanged.
