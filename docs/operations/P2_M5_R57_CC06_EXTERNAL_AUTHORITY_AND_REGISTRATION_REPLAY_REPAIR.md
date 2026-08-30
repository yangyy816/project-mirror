# P2-M5-R57 — CC06 external authority and registration replay repair

## Bounded-task authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R57`
- `BASELINE_SHA: 5c89e580dfd999fecf3b4023b7b90a73373e12ed`
- `BASELINE_CI_RUN: 33332226587_ATTEMPT_1_ALL_MANDATORY_JOBS_PASS`
- `CHANGE_CLASS: BOUNDED_R56_EXTERNAL_AUTHORITY_AND_REGISTRATION_REPLAY_INTEGRITY_REPAIR`
- `CURRENT_MILESTONE: P2-M5_EXECUTING`
- `CURRENT_CANARY: CAL-REQ-004_OUTPUT_REGISTERED_PRE_DECODE`
- `STATUS: EXECUTION_READY_PENDING_IMPLEMENTATION_AND_TRACKED_GATES`

R57 is the minimum forward repair for mandatory findings returned after the
R56 candidate completed same-SHA CI and eight artifact-family content checks.
R56 is not accepted. CAL-REQ-004 remains registered but undecoded, cannot be
invoked again, and cannot enter post-registration execution until R57, R56 and
CC06 pass every required Gate and Principal acceptance.

## Objective

Make every terminal verification and successor decision depend on caller-
retained, task-scoped authority that cannot be reconstructed from the private
receipt chain being verified. Reopen and byte-exactly replay the original
registration evidence before accepting an attempt, terminal or successor.

R57 preserves the accepted CC06/R56 architecture. It adds no schema, public
API, registry carrier, dependency or ADR. The existing Principal-managed
private-output registry remains responsible for retaining the registered tip,
capability-authority map and any completed terminal tip needed by a fresh
process. Their values remain private and are never written into Git, ordinary
CI artifacts, logs or `MEMORY.md`.

`PRINCIPAL_AUTHORITY_DISPOSITION:
REUSE_EXISTING_PRINCIPAL_PRIVATE_OUTPUT_REGISTRY_FOR_EXACT_TERMINAL_TIP`.
This is the already accepted ADR-049/Principal-private-output custody
mechanism, not a new domain authority or persistence schema. The registry
entry stores the opaque output/task binding and exact digest trio; it does not
store image bytes, Prompt plaintext or a Git-visible host locator. If that
registry update is not durably confirmed, the terminal may remain immutable
evidence, but fresh-process recovery and successor rollover stay fail closed.
The ordinal is not retried and no new imagegen call is authorized.

## Allowed files

- `services/api/src/mirror_api/synthetic_dataset/private_imagegen_post_registration.py`
- `services/api/tests/test_private_imagegen_post_registration.py`
- `services/api/tests/test_questionbank_generation_policy_v3.py`
- `docs/operations/P2_M5_R57_CC06_EXTERNAL_AUTHORITY_AND_REGISTRATION_REPLAY_REPAIR.md`
- append-only current-authority tails in:
  - `docs/operations/P2_M5_ACCEPTANCE.md`
  - `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`

## Forbidden scope

No change to `private_execution_overlay.py`, the no-echo capture runner, any
private receipt/root/image/Prompt, schema, migration, ORM, OpenAPI, public API,
dependency, workflow, threshold, runtime/model identity, generation policy,
assignment, epoch, resource ledger, QuestionBank admission, M6, production or
real-user processing. No imagegen, private-image decode, real M3 execution or
database mutation is part of R57 validation.

The existing `.task-ci-*` directories are protected user/task artifacts and
must not be read, modified, internally enumerated or cleaned.

## Mandatory repair requirements

### External registered-tip authority

Every terminal and successor verifier must require the exact registered
receipt, state and event SHA-256 values retained outside the private chain.
The attempt's `overlay_tip` must equal those three values plus the exact
overlay-controller digest. Finding a self-consistent receipt in the current
root is not sufficient.

The verifier must locate that exact registered receipt within the bounded
receipt sequence, prove its receipt/state/event binding and reject any
substitution, canonical re-encode or coherent rehash that does not match the
externally supplied registered tip.

### Complete registration replay

Terminal verification and successor rollover must call the existing
`verify_registration_before_decode()` boundary using the externally anchored
registered receipt. That replay must reopen and verify:

1. the registered overlay receipt, state and event;
2. the immutable output-registration record and its actual SHA-256;
3. the immutable registration receipt and its actual SHA-256;
4. the capture sidecar;
5. the exact raw staging bytes;
6. MIME, magic-byte class, byte size, source checksum and staging checksum;
   and
7. output, action, ordinal and attempt bindings.

The actual output-registration record and registration-receipt digests must
match both immutable state and the post-registration attempt. Missing,
tampered, symlinked or canonical-but-rehashed evidence must block terminal
verification and successor creation fail closed.

### External capability authority

The exact per-platform capability-authority digest map is a required
task-scoped input to execution, recovery, terminal verification and successor
verification. Persisted operation plans and results must be reconstructed
against that external map. A persisted capability payload cannot manufacture
its own authority by hashing itself.

The map binds runtime, model, manifest, QA policy, approved scope and
zero-egress evidence. Any substitution or missing platform stops before a
terminal or successor can be accepted.

### External terminal-tip authority

A newly committed terminal may verify and return its exact receipt/state/event
digests in the same locked transition. The caller must retain that handle in
the existing task-scoped private registry. A later or fresh-process terminal
recovery, explicit terminal verification or successor rollover must require
all three exact terminal-tip digests.

Absence of the external terminal tip is fail closed. This prevents a coherent
rehash of post-registration receipts, plans and results from becoming its own
verification authority. Partial terminal-tip inputs are invalid.

### Call-path completeness

The registered authority, capability map and terminal tip must be propagated
through every terminal-producing and successor-producing path, including:

- normal technical PASS and content rejection;
- deterministic normalization or pre-invocation infrastructure failure;
- persisted plan recovery and unknown post-invocation outcome;
- direct terminal verification;
- successor creation; and
- fresh-process successor verification.

No path may silently fall back to summaries or recompute external authority
from the records it is verifying.

## Required regression matrix

Procedural non-human fixtures must prove:

- deletion and tampering of the registration receipt, output record, capture
  sidecar or staging raw bytes rejects terminal verification and rollover;
- canonical rehash of an output-registration field not otherwise consumed by
  the attempt is still rejected;
- registered-tip substitution and capability-authority substitution are
  rejected by terminal verification and rollover;
- canonical terminal receipt/state/event rehash is rejected against the
  externally retained terminal tip;
- fresh-process terminal recovery without the exact external terminal tip is
  rejected without executor invocation;
- unmodified success, content rejection, infrastructure failure, unknown
  outcome, recovery and successor paths continue to pass; and
- all R56 direct-lease, typed boundary, repeatability, stale-successor and
  evidence-closure regressions remain passing.

## Standing Owner authorization and resource boundary

`OD-P2-M5-IMAGEGEN-BATCH-EXECUTION-001` remains unchanged. Its standing cap of
50 is only an Owner-interaction ceiling. The effective execution cap remains
the minimum of that cap and the accepted resource ledger. R57 consumes no
ordinal and creates no raw output. The current ledger remains 28 formal calls,
28 formal raw outputs and 59 global native outputs available, with
CAL-REQ-005 closed.

R57 acceptance only authorizes the already registered CAL-REQ-004
post-registration canary. It does not authorize a new native imagegen call.

## Conditional true EOF

The R57 candidate must append the same ordered key set to the canonical
acceptance document and its execution-protocol mirror. The overlay becomes
authoritative only after this commit's same-SHA CI, eight artifact-family
content checks, independent Security/Privacy/License/Research review, Sol High
final review and Principal acceptance.

Once that condition is satisfied, the activated values must be coherent:

- CC06, R56 and R57 are accepted rather than pending;
- `CAL-REQ-004` remains `OUTPUT_REGISTERED_PRE_DECODE` until the operational
  canary is actually executed;
- CAL-REQ-004 post-registration execution is authorized exactly once;
- `CAL-REQ-005` remains unauthorized pending CAL-REQ-004 technical QA PASS;
- the only next task is `EXECUTE_CAL_REQ_004_POST_REGISTRATION_CANARY`;
- `STOP_OUTCOME: NONE`; and
- `POST_ACCEPTANCE_COMMIT_REQUIRED: NO`.

The precondition fallback remains the accepted R55 state plus the immutable
registered CAL-REQ-004 evidence. A local candidate or failed Gate cannot
activate R57, R56 or CC06.

## Acceptance

Acceptance requires:

- the complete registration, registered-tip, terminal-tip and capability
  negative-test matrix above;
- all CC06/R50-R56 overlay and capture regressions;
- Ruff format/check and strict mypy;
- canonical-LF complete API/Worker pytest with truthful environment-gated
  skips and zero failure/error;
- canonical/mirror authority equivalence, exact changed-path allowlist and
  private-leak checks;
- same-SHA three-job GitHub Actions;
- all eight artifact-family content checks;
- independent Security/Privacy/License/Research review;
- Sol High final review; and
- Principal inspection of the actual diff and evidence.

Until those Gates pass, CC06/R56/R57 are not accepted, CAL-REQ-004 remains
undecoded, CAL-REQ-005 is unauthorized, and no M5 technical/MVR or M6 Gate is
opened.
