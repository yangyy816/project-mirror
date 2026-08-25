# P2-M5-R36 — E01 First-Wave Synthetic Local Custody Resilience Change Control

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R36`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-R36-001`
- `PREDECESSOR_ACCEPTED_AUTHORITY: 27e62de8c948fc40159542a742d7cf00f95abadc`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Purpose and bounded disposition

R36 records the Owner-authorized, narrowly scoped resilience policy after the first Bootstrap-Q02 attempt failed
before any private control file, bootstrap, digest, raw output, or generation ordinal was created. The Owner has
attested exact cleanup of that empty, task-owned root. This change control preserves both Q01 and the first Q02
failure as historical evidence; it does not rewrite either failure as a pass and does not create private state.

The sole prospective successor is `CC04-B-E01-BOOTSTRAP-Q02-R1`. It may recreate the same epoch-2 control state
only after this R36 authority is accepted. It remains prohibited from calling `image_gen`, consuming `CAL-REQ-002`,
creating raw output, decoding, QA, screening, admission, holdout work, 04-C through 04-E, MVR, M6, production, or
real-user processing.

## First-wave synthetic-local custody policy

`LOCAL_CUSTODY_POLICY_VERSION: p2-m5-e01-first-wave-synthetic-local-custody-v1`

The policy applies only to non-user, synthetic-only first-wave P2-M5 E01 control state. It does not apply to any
real person, User Asset, upload, SelfState, DesiredDelta, credential, production data, production service, or real
user questionnaire. The Owner-controlled Git-external path, exact create-new operations, non-reparse verification,
digest binding, fixed-entrypoint recovery, and no-disclosure rules remain mandatory.

Custom NTFS ACL hardening is reduced to optional, best-effort operational hardening. Parent-directory inherited ACL
is accepted for this narrow scope. A runtime inability to write or read custom ACLs is an operational warning, not a
hard gate; it must never be generalized beyond this first-wave synthetic-only policy.

## Preserved failure history

```text
BOOTSTRAP_Q01_RESULT: FAILED_E01_EPOCH_2_CONTROL_STATE_COMMIT_FAILED
BOOTSTRAP_Q01_FAILURE: DIRECTORY_INHERITANCE_FLAGS_APPLIED_TO_FILE_ACL
BOOTSTRAP_Q02_FIRST_ATTEMPT_RESULT: FAILED_ACL_VALIDATION
BOOTSTRAP_Q02_FIRST_ATTEMPT_IMAGEGEN_CALLS: 0
BOOTSTRAP_Q02_FIRST_ATTEMPT_CAL_REQ_ORDINALS: 0
BOOTSTRAP_Q02_FIRST_ATTEMPT_PRIVATE_BYTES: 0
BOOTSTRAP_Q02_FIRST_ATTEMPT_VALID_BOOTSTRAP: NOT_CREATED
BOOTSTRAP_Q02_FIRST_ATTEMPT_ROOT: OWNER_CLEANED_EMPTY_NON_AUTHORITATIVE_TARGET
```

The new Q02-R1 is a forward implementation under R36, not a retry that retroactively accepts the earlier attempt.

## Local preflight and recovery requirements

Before any authoritative epoch-2 directory is created, Q02-R1 must use a non-private temporary preflight object to
prove create-new, atomic rename, canonical UTF-8-without-BOM LF serialization, detached digest, flush/close/reread,
fresh-process reopen, locking, and cleanup. This preflight must not use a formal ordinal, a real bootstrap target,
private payload, or `image_gen`.

After preflight, Q02-R1 must create only the approved bootstrap, detached digest, epoch-2 root, and its
`control`, `staging`, `custody`, and `reports` children. It must use inherited ACLs without `SetAccessControl`,
`DirectorySecurity`, or `FileSecurity`. The bootstrap must bind the five required control files, their digests, the
epoch, this Owner decision, accepted authority SHA, inherited `1/1/0`, `31/31`, and `62` resource facts, and next
ordinal `CAL-REQ-002`. Fresh-process recovery may use only the fixed bootstrap entrypoint.

## Low-level autonomy classification

L0 mechanical failures and L1 task-owned recoverable control-state failures may be repaired autonomously within the
same bounded task, using at most three distinct local preflight implementations and exact task-owned cleanup only.
L2 substantive boundary changes—including a reparse point, image or unknown binary, user data, credential, ordinal
uncertainty, resource change, new dependency/provider/model, path escape, remote concurrency, or invariant change—
remain Owner-escalation conditions.

No local debugging attempt creates tracked evidence, authority state, a commit, a push, or CI. Exactly one successful
or final-failed Q02-R1 evidence candidate may be created after local preflight resolves.

## R36 acceptance criteria

1. Only this change control and the canonical/mirror true-EOF authority files change.
2. Tracked content has no local path, locator, Prompt, private byte, image, URL, object key, credential, or local user identity.
3. The reduced-assurance policy is explicitly limited to first-wave non-user synthetic local custody and leaves all future sensitive and production custody gates strict.
4. Q01 and the first Q02 attempt remain failed historical evidence; no resource count, ordinal, output, or execution authority changes.
5. Canonical and mirror tails are generated from one complete ordered key map, have equal key set/order/values, and end with their true-EOF sentinels.
6. Scoped formatting, diff and allowlist checks, no-private-leak and counter checks, normal forward push, exact-SHA CI, eight-artifact inspection, independent Security/Privacy/License/Research review, Sol High review, and Principal acceptance pass.
