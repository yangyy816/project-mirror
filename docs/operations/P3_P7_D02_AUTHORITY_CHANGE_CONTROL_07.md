# P3–P7 D02 Change Control 07 — Lost D00 Custody Evidence Disposition

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D02_CC_07
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
STATUS: PRINCIPAL_REVIEWED_CANDIDATE
BASE_SHA: be22b8cabd34a6b29d49955b884774d3e52fbc59
DISCOVERY: D00_PER_ITEM_CUSTODY_BINDING_UNRECOVERABLE
EVIDENCE_LOCATION_LOST: TRUE
D00_HISTORICAL_ACCEPTANCE: UNCHANGED
D00_CURRENT_DEPENDENCY_RECHECK: NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE
D02_PRIVATE_SNAPSHOT_AND_REGISTRY: NOT_CREATED
D02_PRIVATE_SCREENING: BLOCKED
D02_TASK_ACCEPTED: NO
D03: BLOCKED
INDEPENDENT_SOL_AUTHORITY_REVIEW: PASS
INDEPENDENT_SOL_FINDINGS_P0_P1_P2_P3: 0/0/0/0
REVIEWED_CANDIDATE_BLOB_SHA256: b676b5352a8f4f75904b19b5985a9ac752af2a84adfbfe0d910933423e8e4f6f
CANDIDATE_SAME_SHA_CI: PENDING
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

This forward record does not rewrite the historical D00 acceptance or any accepted D01, D04-A, D07-A or D09
checkpoint. It records that the exact private custody evidence required by CC05 and CC06 is no longer consumable at the
D02 execution boundary. The disposition is fail closed; it does not create substitute evidence.

## Repository and accepted-authority baseline

The disposition was evaluated against clean integration commit
`be22b8cabd34a6b29d49955b884774d3e52fbc59`, which is identical to the remote Demo branch and contains the accepted
CC06 implementation and acceptance checkpoint. The branch-local migration and all previously accepted pure-domain and
persistence checkpoints remain unchanged.

The read-only legacy PostgreSQL authority still exposes exactly four canonical synthetic identities and their accepted
QA chains. Those rows establish formal legacy facts, not private custody. A database naming convention, a tracked item
reference, a normalized Asset SHA or a historical summary cannot authenticate a missing D00 registry row.

## Bounded custody recovery evidence

The Principal exhausted the one bounded, task-scoped recovery allowed by the D00 and ADR-049 contracts:

1. The known 2026-08-23 and 2026-08-24 task receipts were streamed read-only. Across 239 receipt files and 9,922 actual
   tool-output records, five outputs mentioned all four target item references. None contained a complete per-item
   `output_id` plus digest or byte-size, authority and custody binding, and none contained a currently resolvable registry
   reference.
2. Exact-ID probes against the three known standard private custody namespaces found zero matching D00 registries.
3. A receipt-level candidate found during the audit was proven to be self-referential evidence from the current audit
   and was excluded. It cannot promote a search command, prompt, later summary or fixture into historical authority.
4. Historical statements that a 27-row registry existed and that one M3 smoke recovered registry authority do not
   publish the four original registry rows or a task-scoped handle that a later Principal can consume.
5. The shared D00 batch receipt content digest has prior same-task replay evidence, but the accepted batch document bytes
   and their four per-item custody bindings are not currently replayable.

No ordinary-disk search, parent-directory enumeration, locator propagation, private-byte read, network acquisition or
Owner re-upload was performed.

## Missing mandatory authority

For each of the four target identities, CC05 and CC06 require one original binding:

```text
item_reference
→ exact D00 source_output_id
→ original registry row
→ expected_digest == actual_digest == registered-byte SHA-256
→ registered byte_size, authority, allowed_tasks, retention, custody and recovery_status
→ normalized source SHA-256
```

They additionally require the original accepted batch receipt document to replay to the frozen shared content digest and
to bind the same four sources. None of those requirements may be inferred from a naming convention or reconstructed from
the legacy database.

## Rejected recovery draft

The Git-external recovery draft is disabled and must not be executed. Independent review of its original exact blob
`ca75217b80cb20953ac5136cb7aad7e61531ab6a08f962c08cf5a73fdf25e4a0` found that it fabricated
`source_output_id` values from item references and substituted constants for live receipt replay. The later unreviewed
draft blob `20bf3c14a81a3d344f835a71c793286d325510febb9acf0d3ce03f97fb71eca5` still does not consume a verified
per-item D00 handoff and remains `DO_NOT_EXECUTE`.

No new child registry, hard-coded identifier, database row, test fixture, static Profile, landmark or after image may be
used to replace the missing authority.

## Disposition

```text
EVIDENCE_LOCATION_LOST
D02_RECOVERY_RESULT: NO_GO_CRITICAL_DEPENDENCY_UNAVAILABLE
D02_PRIVATE_SNAPSHOT_AND_REGISTRY: NOT_CREATED
D02_PRIVATE_SCREENING: NOT_EXECUTED
D02_POSTGRESQL_IMPORT: NOT_EXECUTED
D02_TASK_ACCEPTED: NO
D03: BLOCKED
D04_B: BLOCKED
D07_B: BLOCKED
ALGORITHMIC_PROTOTYPE_PLATFORM_FINAL_GATE: NOT_VERIFIED
```

No identity, screening Report, QuestionBank, QuestionPair or derived source authority may be inserted. Existing accepted
pure functions, schema checkpoints, domain tasks and negative evidence remain valid; they do not convert this result into
a partial D02 acceptance.

## Reopen condition

This stop may be reopened only if an already-existing, accepted and task-scoped original D00 receipt, registry or proven
task-owned root becomes available without broad discovery. A compliant handoff must supply all four original registry
rows, privately resolve and rehash their registered bytes, replay the accepted batch receipt document, and prove the
D00/tracked-authority/tracked-holdout/PostgreSQL four-way mapping.

If that exact evidence becomes available, the Principal must first repair the recovery implementation, close all
atomic-publication, durability, ACL, append-only-trigger and registered-byte replay findings, obtain a new independent
exact-blob Sol review, and only then perform the first private execution. Merely finding the four identifier strings does
not reopen the Gate.

## Formal and production boundary

This record changes no formal migration, formal authority, formal P3–P7 status, real-user processing permission,
production security conclusion or release authorization. The Demo branch remains isolated, and production release
remains unauthorized.
