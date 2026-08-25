# P2-M5-R35 — E01 Epoch-2 Controlled Cleanup and ACL Recreation Change Control

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R35`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-R35-001`
- `PREDECESSOR_ACCEPTED_AUTHORITY: 5b5d65a108411c8fa2c67ed10ae9f9bc0463f99f`
- `R35_AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ARTIFACT_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Purpose

The Owner selects controlled cleanup and recreation of the same epoch-2 target after Bootstrap-Q01 stopped while hardening Windows ACLs. R35 is documentation and current-authority change control only. It authorizes neither local cleanup nor epoch-2 creation; those actions remain exclusive to a later `CC04-B-E01-BOOTSTRAP-Q02` after R35 acceptance.

## Preserved Bootstrap-Q01 failure evidence

```text
BOOTSTRAP_Q01_RESULT: FAILED_E01_EPOCH_2_CONTROL_STATE_COMMIT_FAILED
BOOTSTRAP_Q01_FAILURE_STAGE: WINDOWS_ACL_HARDENING
BOOTSTRAP_Q01_FAILURE_REASON: DIRECTORY_INHERITANCE_FLAGS_APPLIED_TO_FILE_ACL_AND_REJECTED_BY_WINDOWS
BOOTSTRAP_Q01_IMAGEGEN_CALLS: 0
BOOTSTRAP_Q01_CAL_REQ_ORDINALS_CONSUMED: 0
BOOTSTRAP_Q01_RAW_OUTPUTS_CREATED: 0
BOOTSTRAP_Q01_VALID_DETACHED_DIGEST: NOT_CREATED
BOOTSTRAP_Q01_VALID_RECOVERY_RECEIPT: NOT_CREATED
BOOTSTRAP_Q01_DURABLE_BOOTSTRAP: NOT_VALID
BOOTSTRAP_Q01_PRIVATE_TARGET: INCOMPLETE_NON_AUTHORITATIVE
```

Q01 is not rewritten as PASS. Its local control fragments are prohibited from authority reuse; R35 does not claim that the target never existed or that any resource is refunded.

## Authorized successor: Bootstrap-Q02

Only after R35 acceptance, Q02 may inventory the exact Owner-designated epoch-2 root and only its descendants. The inventory may inspect entry name, type, byte size, extension, reparse state, and last-write metadata; text control files may be read only to confirm the recorded Q01 failure. Parent directories, epoch 1, cache locations, and any other location remain outside scope.

Q02 must stop without deleting anything if it observes a reparse point, image format, unknown binary, user data, credential, or other unexplained content. If all guards pass, it may delete only the exact failed bootstrap JSON, detached digest, and epoch-2 root. It must then prove their absence before recreating the same epoch, never epoch 3.

## Corrected ACL policy

Directory objects use a protected `DirectorySecurity` ACL with current Owner SID and Local System SID full control, `ContainerInherit | ObjectInherit`, no retained inherited ACEs, and no Everyone, Users, or Guest write access.

File objects use `FileSecurity` or hardened-parent inheritance only. Explicit file ACEs use `InheritanceFlags.None` and `PropagationFlags.None`. Applying directory inheritance flags to a file object is prohibited. Every ACL write must be reread and verified before proceeding.

## Q02 mandatory completion conditions

Q02 must prove exact-scope cleanup; no unexpected content; no reparse point; correct directory and file ACLs; canonical bootstrap plus matching detached SHA-256; matching control-file digests; inherited resource state `1/1/0`, `31/31`, and `62`; next ordinal `CAL-REQ-002`; and a fresh-process recovery through only the fixed bootstrap entrypoint. It must not call `image_gen`, consume `CAL-REQ-002`, create raw output, or enter A03.

Tracked Q02 evidence may contain only the Owner decision ID, epoch ID, Q01 failure type, cleanup outcome, ACL policy result, schema/version identifiers, digests, receipt ID, counters, and recovery result. Local paths, locators, private bytes, Prompt text, URLs, credentials, local user names, and control-file content remain prohibited.

## Boundaries retained by R35

`CAL-REQ-001` remains `CONSUMED_FAILED_NO_RETRY`; counters remain calls/raw/admitted `1/1/0`, remaining `31/31`, and global native capacity `62`. Concurrency is `1`, retry is `0`, tranche maximum is `4`, and the next unused ordinal remains `CAL-REQ-002`. M5 is executing; MVR, M6, QuestionBank, production, real-user handling, and release remain closed.

## R35 acceptance criteria

1. Only this document and the canonical/mirror true-EOF authority files change.
2. The tracked diff contains no private path, locator, Prompt, image byte, object key, URL, credential, or local user identity.
3. The current tails preserve Q01 as failed historical evidence and make Q02 conditional on R35 acceptance.
4. No private cleanup, ACL operation, bootstrap creation, generation, or ordinal consumption occurs in R35.
5. Scoped formatting, diff and allowlist checks, counter/no-retry and tail checks, normal push, exact-SHA CI, artifact inspection, independent reviews, Sol High review, and Principal acceptance pass.
