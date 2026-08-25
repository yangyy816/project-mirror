# CC04-B-E01-A03 — Durable E01-EPOCH-2 Reconciliation and CAL-REQ-002 Resume Authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-E01-A03`
- `TASK_NAME: Resume CAL-REQ-002 under Durable E01-EPOCH-2`
- `OWNER_CLARIFICATION_ID: OC-P2-M5-CC04-B-E01-A03-RECOVERY-RECEIPT-001`
- `PREDECESSOR_ACCEPTED_AUTHORITY: a48809061ff8ea053e1c512b448bbdfe17661178`
- `PREDECESSOR_CI_RUN: 32816806144`
- `A03_AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Scope and non-negotiable boundary

A03 is the separate, bounded reconciliation checkpoint required after accepted Q02-R1 and R37. It may make only
the already-created durable E01-EPOCH-2 control state effective for the next never-used ordinal, `CAL-REQ-002`,
after every A03 Gate passes. It neither creates an output nor dispatches an ordinal.

This task performs no image generation, image-byte read, image decode, QA, model screening, admission, holdout,
04-C through 04-E, MVR, M6, production, or real-user activity. It changes no private control file, bootstrap,
detached digest, registry, ledger, GenerationSpecification, prompt, resource envelope, provider, model,
dependency, schema, migration, API, or production boundary.

```text
IMAGEGEN_CALLS_EXECUTED_IN_A03: 0
CAL_REQ_002_CONSUMED: NO
IMAGE_BYTES_CREATED_OR_READ: 0
IMAGE_DECODE: 0
QA: 0
MODEL_SCREENING: 0
```

## Principal-only private-state reconciliation

The Principal used the Owner-authorized exact read-only bootstrap and detached-digest references only. Neither
reference is recorded here. The procedure did not enumerate a parent directory, glob, search, discover, guess a
path, or access a bootstrap-undeclared file.

- `OPAQUE_INPUT_ID: PM-A03-E01-EPOCH2-BOOTSTRAP-001`
- `DIRECT_BOOTSTRAP_HANDLE_ACCESS: PASS`
- `A03_BOOTSTRAP_SHA256_CHECK: PASS`
- `A03_BOOTSTRAP_DETACHED_DIGEST_CHECK: PASS`
- `A03_BOOTSTRAP_JSON_PARSE: PASS`
- `A03_CONTROL_FILE_DIGEST_CHECK: 5_MATCHING`
- `A03_FRESH_PROCESS_RECOVERY: PASS`
- `A03_RESOURCE_LEDGER_CHECK: PASS`
- `A03_NEXT_ORDINAL_CHECK: CAL-REQ-002`

The five executable private control files were present only through the exact bootstrap declarations. Each was a
regular non-reparse file whose exact bytes matched its bootstrap-declared SHA-256 and byte size. The reconciled
state remains `1 call / 1 raw / 0 accepted`, with `31` formal calls, `31` raw outputs, and `62` global native
outputs remaining. `CAL-REQ-002` remains unconsumed.

## Recovery receipt authority

The Q02-R1 recovery receipt is an accepted logical evidence receipt, not a sixth private control file:

```text
A03_RECOVERY_RECEIPT_MODEL: ACCEPTED_LOGICAL_TRACKED_EVIDENCE_RECEIPT
A03_RECOVERY_RECEIPT_ID: E01-EPOCH-2-BOOTSTRAP-Q02-R1-RECOVERY-RECEIPT-V1
A03_RECOVERY_RECEIPT_FILE_REFERENCE: NOT_REQUIRED
RECOVERY_RECEIPT_AUTHORITY_FILE: docs/operations/P2_M5_CC04_B_E01_BOOTSTRAP_Q02_R1_DURABLE_BOOTSTRAP_EVIDENCE.md
RECOVERY_RECEIPT_EVIDENCE_SUFFICIENCY: PASS
```

The accepted tracked Q02-R1 evidence at the R37 accepted SHA records the matching bootstrap digest, five matching
control digests, fixed-entrypoint fresh-process recovery PASS, receipt ID, next ordinal, `1/1/0` resource state,
`31/31/62` remaining capacity, zero Q02-R1 image generation, and zero `CAL-REQ-002` consumption. A03 independently
reconfirmed the private durable-state facts and fresh-process recovery. No receipt locator, path, content, prompt,
image byte, URL, credential, or other private operational value is tracked.

## Effective authority after A03 acceptance

Only after all A03 same-SHA CI, artifact, Security, Privacy, License, Research Integrity, Sol High, and Principal
acceptance Gates pass may the following become effective:

```text
CC04_B_EXECUTION: READY_FOR_BOUNDED_TRANCHE_RESUME_MAX_4_CALLS
FORMAL_E01_STATUS: READY_TO_RESUME_AT_CAL_REQ_002
NEXT_UNUSED_FORMAL_ORDINAL: CAL-REQ-002
NEXT_READY_TASK: EXECUTE_CAL_REQ_002
```

The first subsequent operation is still serial, zero-retry, at most four calls per tranche, and starts only with
`CAL-REQ-002`. `REGISTER_BEFORE_DECODE` and `RECEIPT_BEFORE_DECODE` continue to require the future per-output
registry-commit receipt before any decode. That per-output receipt is distinct from the logical bootstrap recovery
receipt reconciled here.

## Acceptance criteria

1. The tracked evidence contains no private absolute path, locator, control-file content, prompt, image byte, URL,
   credential, or secret.
2. The bootstrap, detached digest, five exact control-file digests, fixed-entrypoint fresh-process recovery, resource
   ledger, next ordinal, and accepted logical recovery receipt all reconcile.
3. Canonical and mirror true-EOF maps are complete, ordered, value-identical, and end at their sentinels.
4. The candidate passes scoped local validation, changed-path allowlist and no-private-leak scans, normal forward
   commit and non-force push, exact-SHA CI, eight-artifact inspection, independent Security/Privacy/License/Research
   review, Sol High review, and Principal acceptance.
