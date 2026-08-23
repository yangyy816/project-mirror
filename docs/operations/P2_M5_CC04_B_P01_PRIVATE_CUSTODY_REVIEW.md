# CC04-B-P01 Private Custody, Locator, and Cleanup Review

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: CC04-B-P01`
- `TASK_NAME: Private Custody, Locator, and Cleanup Review`
- `PARENT_AUTHORITY: P2-M5-R15_AND_REPAIRED_CC04-B-S01`
- `BASELINE_SHA: 126f96e2da286f7c5e74f0648023d76efec32b29`
- `REVIEW_CANDIDATE: THIS_COMMIT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_SOL_AND_PRINCIPAL_ACCEPTANCE`
- `PRE_CONDITION_CURRENT_STATE: CC04_B_P01=REVIEW_CANDIDATE_PENDING_ACCEPTANCE; CC04_B_EXECUTION=CLOSED`

This is a policy review only. It does not create or resolve a private path, registry, root, locator, handle, receipt, output, Asset, identity, or cohort; access private input; invoke image generation; consume quota; or authorize execution.

## Frozen custody authority

- `PRIVATE_INPUT_CUSTODIAN: PRINCIPAL`
- `PRIVATE_OUTPUT_CUSTODIAN: PRINCIPAL`
- `PRIVATE_REGISTRY_AUTHORITY: PRINCIPAL_PRIVATE_OUTPUT_REGISTRY`
- `PRIVATE_REGISTRY_LOCATION: GIT_EXTERNAL_AND_NOT_DISCLOSED_IN_TRACKED_EVIDENCE`
- `SUBAGENT_PRIVATE_DISCOVERY: PROHIBITED`
- `PRIVATE_INPUT_NON_PROPAGATION: REQUIRED`
- `PRINCIPAL_RETAINS_GATE_AND_SCOPE_AUTHORITY: REQUIRED`

The future execution task remains under ADR-049 and the Principal-Managed Private Input Delegation Protocol. An accepted execution contract must authorize the exact task, role, operation, output type, byte ceiling, network policy, retention, and cleanup before any private capability is created or used. Starting another Agent does not transfer custody or grant sibling, later-task, or recursive access.

If the available runtime cannot prove least privilege for a private step, `PRINCIPAL_EXECUTES_SENSITIVE_STEP`. Reviewers receive only tracked redacted evidence and never a locator, path, private byte, Prompt, Provider payload, or credential.

## Principal private-output registry record

The future Git-external registry is the sole custody authority for each newly created private output. It must create an immutable record containing at least:

```text
INPUT_OR_OUTPUT_ID
CREATING_TASK
CREATING_AGENT
SOURCE_KIND
GENERATION_SPECIFICATION_ID
GENERATION_SPECIFICATION_DIGEST
OPAQUE_LOCATOR
EXPECTED_DIGEST
ACTUAL_DIGEST
MEDIA_TYPE
MAGIC_BYTES_CLASS
BYTE_SIZE
AUTHORITY
RETENTION_PURPOSE
RETENTION_START
RETENTION_END
ALLOWED_FUTURE_TASKS
CUSTODY_STATUS
CLEANUP_TRIGGER
CLEANUP_STATUS
```

The registry may additionally record request-count and output-count bindings, policy/rubric versions, coverage assignment, creation timestamp, and allowlisted disposition. Unknown Provider model, snapshot, seed, request ID, usage, and monetary cost remain `UNKNOWN_OR_NULL` and must not be fabricated.

For a generated output, SHA-256 is computed from the exact returned bytes before any admission use. At initial immutable registration, `EXPECTED_DIGEST` and `ACTUAL_DIGEST` are set to that verified digest; later recovery must match it exactly. Type, byte size, task, authority, retention, or scope mismatch is a hard stop. Q01 remains responsible for image decode, canonical normalization, QA, identity, and duplicate admission; P01 does not perform or approve those operations.

## Create-once private output root

Only a separately accepted `CC04-B-EXECUTION` task may create the calibration root, and it must do so once before the first generation call. The Principal must resolve the exact task-scoped parent capability from the accepted execution receipt without enumerating its parent or searching the disk, then verify that the new root:

1. is outside Git, ordinary CI artifact paths, shared caches, P2-M7, and unrelated project roots;
2. is newly created for the exact execution task, not a pre-existing legacy, User, CC01-C, CC02, or M4 location;
3. is a normal directory, not a symlink, junction, reparse point, mount alias, or path traversal result;
4. is empty at creation and owned by the Principal custody flow;
5. is registered once through an opaque locator before use;
6. is never replaced, renamed as a retry, mirrored to a fallback root, or broadened to a parent directory;
7. remains within the global 8 GiB new-private-output ceiling and the later O01 storage ledger.

Any pre-existing target, unresolved capability, unsafe filesystem type, second-root request, path escape, or storage uncertainty stops before generation. This review creates no root and does not disclose a future root location.

## Opaque locator and recoverability

`OPAQUE_LOCATOR` is a private registry capability, not the tracked `INPUT_OR_OUTPUT_ID`. It remains only in the Git-external registry or exact task receipt and must never enter Git, ordinary logs, CI artifacts, MEMORY, reviewer context, commit messages, or user-facing status text.

Tracked evidence may record only an opaque output ID, content digest, byte count, authority, retention class, allowlisted status, and cleanup status. It must not contain the locator, absolute or relative private path, directory name, object key, bucket, URL, signed URL, credential, secret, raw Provider payload, Prompt plaintext, image bytes, or encoded image data.

Recovery starts only from the exact task receipt, Principal registry entry, or already-proved task-owned handle. It may not use drive-wide search, home-directory enumeration, globbing, parent listing, sibling-task lookup, protected temporary-root discovery, or legacy-registry reuse. Failure of bounded recovery returns `EVIDENCE_LOCATION_LOST`; it never triggers silent regeneration, quota erasure, Owner re-upload demand, or a broad search.

## Prompt and logging boundary

Future execution may retain a versioned GenerationSpecification ID and digest, Prompt-template ID and digest, policy versions, coverage assignment, request/output counts, and known timestamps. Prompt plaintext and Provider request/response payloads remain private and are prohibited from Git, normal logs, CI, artifacts, MEMORY, exception text, and reviewer packets.

Logs use allowlisted event names and opaque IDs. Errors are mapped to allowlisted reason codes before persistence; raw exceptions, paths, URLs, keys, secrets, image content, directory listings, and payload fragments are prohibited. Credential values are process-bound only, but 04-B currently authorizes no paid or programmatic Provider credential.

## Retention and cleanup

P01 inherits L01 without expansion:

- `RETENTION_PURPOSE: AUTHORIZED_P2_M5_CALIBRATION_RESEARCH_AND_AUDIT_ONLY`
- `RETENTION_START: ONLY_AFTER_ACCEPTED_CC04_B_EXECUTION_AUTHORITY_CREATES_THE_OUTPUT`
- `RETENTION_END: M5_RESEARCH_STOP_OR_M5_CLOSURE_AFTER_REQUIRED_AUDIT_AND_CLEANUP_EVIDENCE`
- `EARLY_CLEANUP_TRIGGER: SECURITY_PRIVACY_LICENSE_SCOPE_OR_INTEGRITY_FAILURE`
- `RETENTION_EXTENSION: REQUIRES_EXPLICIT_ACTIVE_SECURITY_OR_RESEARCH_EVIDENCE_HOLD_AUTHORITY`
- `PRODUCTION_OR_PUBLIC_RETENTION: NOT_AUTHORIZED`

Cleanup is Principal-owned, bounded to exact registered output IDs and their task-owned locator capabilities, and prohibited from broad or recursively computed targets. Before deletion, the registry freezes output ID, digest, byte size, request/output count binding, reason, retention disposition, and cleanup authority. After deletion, the Principal verifies absence through the same exact capability and records timestamp plus `CLEANUP_COMPLETE` or `CLEANUP_FAILED`.

Cleanup uncertainty keeps the task unaccepted. Deleting private bytes never erases request counts, output counts, rejected-output counts, digests, allowlisted rejection facts, security failures, or historical audit evidence. A failure cleanup may remove only outputs newly created by that failed task and only when no explicit evidence hold applies.

## Negative controls and stop outcomes

The later execution contract must hard-stop on:

- missing or multiple registry records;
- unregistered, unresolved, duplicate, substituted, or printed locator;
- pre-existing, second, reparse, escaped, legacy, shared, or P2-M7 root;
- digest, type, byte-size, authority, task, agent, purpose, retention, or scope mismatch;
- private discovery, parent enumeration, sibling/cross-task propagation, or reviewer capability exposure;
- Prompt, payload, path, key, URL, credential, secret, directory-listing, or image-byte leakage;
- private bytes entering Git, staging, commit objects, ordinary CI, artifact, cache, or MEMORY;
- storage overflow, untracked bytes, unsupported PASS, missing cleanup evidence, or cleanup uncertainty;
- silent regeneration after locator loss or deletion;
- any attempt to treat P01 as generation, QA, cohort, execution, MVR, M6, production, or public-release authority.

Legal dispositions include `PRIVATE_CUSTODY_REVIEW: PASS | BLOCKED`, `EVIDENCE_LOCATION_LOST`, `PRIVATE_INPUT_SCOPE_EXPANSION_REQUIRED`, `CLEANUP_FAILED`, and the existing fail-closed task outcomes. No negative-control failure authorizes a retry, replacement output, quota transfer, or second root.

## Review result

- `PRIVATE_CUSTODY_REVIEW: PASS`
- `PASS_SCOPE: FUTURE_CC04_B_PRIVATE_SYNTHETIC_CALIBRATION_ONLY`
- `PRIVATE_ROOT_CREATED: NO`
- `PRIVATE_LOCATOR_CREATED: NO`
- `PRIVATE_OUTPUT_REGISTRY_MUTATED: NO`
- `NEXT_REQUIRED_REVIEW: CC04-B-Q01`

This result becomes effective only after this exact commit passes same-SHA CI, artifact inspection, independent Security/Privacy review, independent Sol High review, and Principal acceptance. Until then P01 remains a candidate, Q01 remains closed, and generation and execution remain prohibited.

## Acceptance criteria and validation

1. ADR-049 authority, create-once root, private registry schema, opaque recoverability, no discovery/non-propagation, retention, and cleanup evidence are frozen without creating a capability.
2. No private byte, locator, Prompt, path, key, URL, credential, Provider payload, image, binary, root, Asset, identity, cohort, quota, or execution authority is created or disclosed.
3. S01 hard controls, L01 retention, Owner resource envelope, serial review DAG, Q01/O01 boundary, and downstream closures remain unchanged.
4. Exactly three tracked Markdown paths change; scoped Prettier, `git diff --check`, required-marker, forbidden-field, binary, scope, true-EOF, last-occurrence, sentinel, and canonical/mirror checks pass.
5. The exact commit passes all CI, artifact, independent review, and Principal Gates.

After acceptance, stop P01 and open only `CC04-B-Q01`. Do not create private custody, start O01, write an execution contract, invoke image generation, or access any private input in this task.
