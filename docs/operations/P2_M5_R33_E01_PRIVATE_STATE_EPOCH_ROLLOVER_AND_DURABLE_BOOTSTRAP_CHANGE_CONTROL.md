# P2-M5-R33 — E01 Private-State Epoch Rollover and Durable Bootstrap Change Control

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R33`
- `TASK_NAME: E01 Private-State Epoch Rollover and Durable Bootstrap Change Control`
- `OWNER_DECISION_ID: OD-P2-M5-CC04-B-E01-R33-001`
- `PREDECESSOR_ACCEPTED_AUTHORITY: 886f5d6e41bdf72dcf15c307cbc4837cc5cd6ab4`
- `PREDECESSOR_STATUS: R32_ACCEPTED_CAL_REQ_002_READY_BUT_PRIVATE_STATE_EPOCH_1_UNRECOVERABLE`
- `R33_AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Purpose and bounded forward disposition

R33 records the Owner-authorized retirement of the unrecoverable non-user synthetic private-state epoch and defines
the prospective durable-bootstrap authority for a new epoch. It is not a recovery, scan, reconstruction, reuse, or
validation of the historical private root, registry, specification instance, assignment ledger, or receipt. It does
not alter any formal resource count, revive `CAL-REQ-001`, create private state, or permit image generation.

The retired epoch is historical evidence only:

```text
E01_PRIVATE_STATE_EPOCH_1: RETIRED_EVIDENCE_LOCATION_LOST
E01_EPOCH_1_RECOVERY: ABANDONED_NO_SCAN_NO_GUESS
E01_EPOCH_1_PRIVATE_REGISTRY: UNRECOVERABLE
E01_EPOCH_1_GENERATION_SPECIFICATION_PRIVATE_INSTANCE: UNRECOVERABLE
E01_EPOCH_1_ASSIGNMENT_LEDGER: UNRECOVERABLE
E01_EPOCH_1_REUSE: PROHIBITED
E01_EPOCH_1_PATH_SEARCH: PROHIBITED
E01_EPOCH_1_ORPHANED_METADATA_POSSIBILITY: ACCEPTED_AS_NON_USER_SYNTHETIC_LOCAL_METADATA_RISK
```

No claim is made that any epoch-1 file is absent. `CAL-REQ-001` remains permanently consumed, failed,
non-admissible, and non-retryable; its Owner-attested cleanup facts remain unchanged.

## Prospective epoch-2 authority

After R33 acceptance, a separate `CC04-B-E01-BOOTSTRAP-Q01` may create exactly one Owner-designated,
Git-external epoch-2 control root and its fixed, Owner-visible bootstrap entrypoint. The bootstrap and its detached
SHA-256 file are the sole future recovery entrypoint. The actual local paths are Owner-visible operational metadata
and are deliberately absent from this tracked change control, CI, artifacts, MEMORY, commit messages, and ordinary
reports.

Before any epoch-2 state is created, Q01 must prove all authorized targets absent, reject symlink/junction/reparse
targets, use atomic create-new writes only, restrict ordinary-user write access, and stop without overwrite or
alternate epoch creation if any target is pre-existing or invalid. Q01 may create only the bootstrap, detached digest,
control/staging/custody/reports roots, private registry v2, request ledger v2, output ledger v2, assignment ledger v2,
generation specification v3, and a path-free local recovery receipt. Q01 must not call `image_gen`, consume an
ordinal, create output bytes, decode, run QA, screen, or admit an identity.

The new private versions are prospective and must not impersonate epoch 1:

```text
E01_PRIVATE_STATE_EPOCH: E01-EPOCH-2
PRIVATE_REGISTRY_VERSION: p2-m5-cc04-b-e01-private-registry-v2
GENERATION_SPECIFICATION_VERSION: p2-m5-cc04-b-calibration-generation-v3-east-asian-first-wave-epoch2
ASSIGNMENT_LEDGER_VERSION: p2-m5-cc04-b-calibration-assignment-v2-cal-req-002-forward
REQUEST_LEDGER_VERSION: p2-m5-cc04-b-e01-request-ledger-v2
OUTPUT_LEDGER_VERSION: p2-m5-cc04-b-e01-output-ledger-v2
EFFECTIVE_ORDINAL_RANGE: CAL-REQ-002_TO_CAL-REQ-032
```

The bootstrap must use canonical UTF-8-without-BOM, LF-terminated serialization and an atomic create-new write.
Its detached SHA-256 must be computed over the serialized bootstrap bytes; it must not self-contain that digest. It
must bind the epoch, owner decision, accepted authority SHA, exact local control-file references, private versions,
next ordinal, and the inherited `1/1/0`, `31/31`, and `62` accounting facts. Every control-state change must atomically
write, flush, close, reread, verify the relevant digest, refresh the bootstrap and detached digest, and create a
path-free local receipt. A fresh-process recovery test must use only the fixed bootstrap entrypoint.

## Preserved E01 and safety boundaries

Epoch 2 inherits the accepted raw maximum `32`, admitted target `24`, serial concurrency `1`, retry `0`, tranche
maximum `4`, register-before-decode, receipt-before-decode, and all `CAL-REQ-001` no-reuse prohibitions. It retains
the `EAST_ASIAN_PRESENTING_ADULT_SYNTHETIC_FACES` first-wave presentation context without sensitive classification,
continuous morphology and style diversity, anti-homogenization, no real person/User Asset/legacy identity reuse,
no beauty ranking, preliminary-only model screening, deferred human second round, and all 04-C/04-D/04-E/MVR/M6/
QuestionBank closures. Prompt plaintext and private operational fields remain prohibited from tracked evidence.

Only after Q01 and a separate `CC04-B-E01-A03` each complete their exact-SHA CI, artifact, Security, Privacy,
License, Research Integrity, Sol High, and Principal acceptance Gates may `CAL-REQ-002` be dispatched. A03 must
reconcile the epoch-2 bootstrap and all private control-file digests with the inherited resource ledger before making
the bounded tranche state effective.

## R33 acceptance criteria

1. The only changed paths are this document and the canonical/mirror true-EOF authority files.
2. The tracked content contains no local absolute path, locator, object key, URL, credential, Prompt, image bytes, or
   private control-state content.
3. The retirement is explicitly non-reconstructive; epoch-1 search/reuse remains prohibited.
4. `CAL-REQ-001` incident facts and every resource counter are preserved exactly.
5. Q01 is separated from R33 and no private root, bootstrap, control file, generation, decode, QA, screening, or
   admission happens in this task.
6. Canonical and mirror latest tails have the same governed key set, order, and values, with their sentinel as the last
   non-empty line.
7. Scoped formatting, diff/allowlist/accounting/no-retry/no-private-leak checks, normal forward commit and non-force
   push, exact-SHA CI, eight-artifact inspection, independent Security/Privacy/License/Research/Sol review, and
   Principal acceptance all pass.

## Failure disposition

Until R33 is accepted, epoch-2 creation and E01 execution are closed. After R33 acceptance, a pre-existing or invalid
authorized target is `E01_EPOCH_2_PREEXISTING_UNAUTHORIZED_TARGET`; a missing or digest-invalid fixed bootstrap is
`E01_DURABLE_BOOTSTRAP_MISSING_OR_INVALID`. Neither condition authorizes scanning, overwrite, cleanup, renaming,
epoch-3 creation, retry, or image generation.
