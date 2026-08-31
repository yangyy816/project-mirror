# P2-M5-R64 — legacy overlay verification bridge

- `BOOTSTRAP_STATUS: OK`
- `OWNER_DECISION_ID: OD-P2-M5-R64-LEGACY-OVERLAY-BRIDGE-001`
- `BASELINE_SHA: 307147f5395a3746c5976ffce8d9fcfac12c1f4d`
- `STATUS: EXECUTING`

## Invariants

- legacy overlay source and legacy receipt are byte-exact immutable;
- only `CAL-REQ-004` may obtain a legacy attestation/bridge;
- no redispatch, retry, imagegen, decode or M3;
- new records are create-new, digest-bound and redacted; and
- the new verifier pins both its own SHA and the legacy controller SHA.

## Independent verifier boundary

The verifier owns an append-only v2 chain only. Genesis is the exact
`OUTPUT_REGISTERED_PRE_DECODE` bridge receipt; the sole R64 transition binds a
canonical request reference and reaches `POST_REGISTRATION_ATTEMPT_BOUND`.
Neither transition performs decode, M3, Provider work, model loading, or any
terminal disposition.

Every v2 operation takes the same bounded cross-process lease. The durable
tip is bound to the bridge, legacy controller/receipt, verifier source SHA,
root identity and request-reference digest. Recovery re-reads the complete
deterministically named chain, rejects stale handles, extra branch files,
non-canonical content and root/controller/bridge changes, then can separately
re-read the bridge receipt. Its small verified-tip index is a bounded cache,
never an authority.

Windows process-resource observation binds its ctypes signatures once through a
module-level locked singleton. Signature assignment is absent from the
verification hot path; private receipt bytes, locators, images, Prompts and
credentials are never emitted into tracked evidence.

The only public bridge-creation entry receives the exact legacy receipt path
and every receipt/state/registration/action/output anchor, then invokes
`verify_cal_req_004_once` before it can create or re-verify a bridge receipt.
Caller-built attestation payloads are not an authority input.

## Required local evidence

- legacy overlay fixed-SHA regression;
- exact bridge creation/re-verify and tamper rejection;
- v2 entry, fresh-process recovery, stale/root/branch/request-reference
  rejection and one-writer concurrency;
- 20-operation bounded-profile exercise, focused Ruff and strict mypy; and
- canonical-LF API/Worker regression before candidate creation.

The first local attempt is recorded in
`docs/operations/P2_M5_R64_LOCAL_EVIDENCE.md`; it is explicitly non-candidate
evidence until the complete regression has a zero exit status.

## Allowed scope

- independent legacy verifier and post-registration verifier/bridge modules;
- bounded terminal-tip verification in
  `private_imagegen_post_registration.py`, without changing the legacy overlay;
- focused tests and R64 governance evidence; and
- minimal private post-registration routing only after a bridge validates.

## Forbidden scope

- `private_execution_overlay.py`, old receipts, legacy controller pin,
  Provider/runtime/model execution, schema/migration/OpenAPI/policy and
  QuestionBank changes.

## Conditional true EOF

```text
R63_STATUS: NOT_ACCEPTED_ARCHITECTURE_SPLIT_REQUIRED
R64_STATUS: PASS_AFTER_THIS_COMMIT_ALL_GATES_AND_PRINCIPAL_ACCEPTANCE
LEGACY_OVERLAY_CONTROLLER: PRESERVED_BYTE_EXACT
CAL_REQ_004_LEGACY_BRIDGE: AUTHORIZED_ONLY_AFTER_R64_ACCEPTANCE
CAL_REQ_004_STATUS: OUTPUT_REGISTERED_PRE_DECODE
CAL_REQ_004_REDISPATCH: PROHIBITED
NEXT_READY_TASK: RESUME_CAL_REQ_004_POST_REGISTRATION_USING_ACCEPTED_LEGACY_BRIDGE
POST_ACCEPTANCE_COMMIT_REQUIRED: NO
```
