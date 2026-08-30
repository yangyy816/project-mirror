# P2-M5-R56 — CC06 terminal evidence closure repair

## Bounded-task authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R56`
- `BASELINE_SHA: 7119f6dd05c26ab6aa533b9567c22e22f9515a41`
- `BASELINE_CI_RUN: 33326809003_ATTEMPT_1_ALL_MANDATORY_JOBS_PASS`
- `CHANGE_CLASS: BOUNDED_CC06_INTEGRITY_AND_FAILURE_TAXONOMY_REPAIR`
- `CURRENT_MILESTONE: P2-M5_EXECUTING`
- `CURRENT_CANARY: CAL-REQ-004_OUTPUT_REGISTERED_PRE_DECODE`
- `STATUS: EXECUTION_READY_PENDING_IMPLEMENTATION_AND_TRACKED_GATES`

R56 is the minimum forward repair for mandatory findings returned after the
CC06 candidate completed same-SHA CI and artifact inspection. The candidate is
not accepted. CAL-REQ-004 remains registered but undecoded, may not be invoked
again, and may not enter post-registration execution until R56 and CC06 pass
all required Gates and Principal acceptance.

## Objective

Make terminal and successor authority depend on a complete, byte-exact replay
of every evidence object required by the actual terminal path; classify known
pre-invocation failures truthfully without converting them into an unknown M3
outcome; and freeze one coherent post-acceptance successor.

The repair also regression-locks the controller properties already present in
the CC06 candidate: a real shared R55 lease for the initial canary, canonical
provider-port references, element-wise repeatability, strict result recovery,
externally anchored capability authority, typed evidence validation and stale
successor rejection. R56 must not replace those properties with weaker
equivalents.

## Allowed files

- `services/api/src/mirror_api/synthetic_dataset/private_imagegen_post_registration.py`
- `services/api/tests/test_private_imagegen_post_registration.py`
- `services/api/tests/test_questionbank_generation_policy_v3.py`
- `docs/operations/P2_M5_R56_CC06_TERMINAL_EVIDENCE_CLOSURE_REPAIR.md`
- append-only current-authority tails in:
  - `docs/operations/P2_M5_ACCEPTANCE.md`
  - `docs/operations/P2_M5_EXECUTION_PROTOCOL.md`

## Forbidden scope

No change to `private_execution_overlay.py`, the no-echo capture runner, any
private receipt/root/image/Prompt, schema, migration, ORM, OpenAPI, public API,
dependency, workflow, threshold, runtime/model identity, generation policy,
assignment, epoch, resource ledger, QuestionBank admission, M6, production or
real-user processing. No imagegen, private-image decode or real M3 execution is
part of R56 validation.

The existing `.task-ci-*` directories are protected user/task artifacts and
must not be read, modified, enumerated internally or cleaned.

## Mandatory repair requirements

### Complete terminal evidence closure

`verify_post_registration_terminal()` and every successor rollover must
rebuild the terminal evidence closure from the current durable state instead
of trusting summary fields alone.

The verifier must, according to the exact terminal path:

1. verify the bound overlay receipt, state, event and post-registration module
   pins and prove that the supplied receipt is the current tip;
2. verify the attempt record and its exact state binding;
3. when normalization completed, verify the normalization record, normalized
   immutable bytes, canonical digest, size, MIME and dimensions;
4. for every planned operation, verify canonical plan bytes, plan digest,
   operation/platform/repeat, capability authority and normalized/request
   bindings;
5. for every completed or failed operation, verify canonical result bytes,
   result digest, plan binding, typed payload and terminal classification;
6. require the exact state-derived set of planned/completed/failed records and
   reject missing, extra, duplicated, stale or tampered evidence; and
7. recompute the terminal reason from verified evidence where the terminal
   path has enough completed results to do so.

A technical-pass or content-rejection terminal produced after the complete
V01/V03 matrix must therefore retain and verify all 20 plan/result pairs. An
infrastructure or unknown-outcome terminal verifies the exact smaller evidence
set authorized by its failure point; it must not fabricate absent results.
Any required evidence loss or mutation blocks terminal verification and
successor creation fail closed.
A canonical-but-rehashed rewrite is still a mutation and must be rejected
against the immutable historical transition anchor.

### Truthful pre-invocation failure

The durable plan remains the invocation boundary, but request construction is
still pre-invocation. If normalized bytes are missing, tampered or otherwise
invalid while constructing the canonical request:

- the executor call count is exactly zero;
- an immutable redacted failure result is written and bound to the plan;
- the terminal phase is `POST_REGISTRATION_INFRA_FAILURE` with a stable reason;
- recovery verifies and preserves that classification; and
- a later process must not relabel it
  `POST_REGISTRATION_UNKNOWN_M3_OUTCOME`.

Only a durable plan for which invocation may have occurred but no verifiable
result exists may use the unknown-outcome terminal. Same-operation retry
remains prohibited.

### Preserved controller security properties

Focused regression must prove, without private input, that:

- `process_registered_output()` holds the direct R55 quiescence lease for the
  initial registered canary and revalidates the current tip under that lease;
- request and normalized-asset references are deterministic lowercase opaque
  references derived from accepted digests;
- same-platform repeatability is calculated per landmark component and matrix
  element across repeats, never by mixing unrelated coordinates;
- recovery accepts a completed result only after canonical schema, bytes,
  digest, plan, request, capability, platform and repeat bindings pass;
- runtime executor values are canonical typed values, finite where required,
  unique where required, and cannot persist a path, URL or arbitrary locator;
- the independently supplied capability-authority digest binds the complete
  capability payload, including approved scope and zero-egress evidence;
- deterministic executor-return binding failures become infrastructure
  failures, while genuinely uncertain post-invocation outcomes alone become
  unknown;
- a successor verifier rejects stale sequence-zero receipts after any later
  receipt exists; and
- booleans are never accepted as numeric QA evidence.

If any of these properties cannot be satisfied without changing ADR-054 or
creating a new authority carrier, R56 stops at the decision boundary and
returns the exact unresolved question to the Principal.

## Conditional true EOF

The R56 candidate must append the same ordered key set to the canonical
acceptance document and its execution-protocol mirror. The overlay becomes
authoritative only after this commit's same-SHA CI, eight artifact-family
content checks, independent Security/Privacy/License/Research review, Sol High
final review and Principal acceptance.

Once that condition is satisfied, the activated values must be internally
coherent:

- CC06 and R56 are accepted rather than pending;
- `CAL-REQ-004` remains `OUTPUT_REGISTERED_PRE_DECODE` until the operational
  canary is actually executed;
- `CAL-REQ-004` post-registration execution is authorized exactly once;
- `CAL-REQ-005` remains unauthorized pending CAL-REQ-004 technical QA PASS;
- the only next task is
  `EXECUTE_CAL_REQ_004_POST_REGISTRATION_CANARY`;
- `STOP_OUTCOME: NONE`; and
- `POST_ACCEPTANCE_COMMIT_REQUIRED: NO`.

The precondition fallback remains the accepted R55 state plus the immutable
registered CAL-REQ-004 evidence. A candidate or failed Gate cannot activate
the R56 overlay.

## Acceptance

Acceptance requires:

- focused deletion and tamper tests for normalization record, normalized
  bytes, plan and result evidence before terminal verification and rollover;
- pre-invocation request-build failure and fresh-process recovery tests proving
  executor call count zero and infrastructure classification;
- non-degenerate repeatability, typed boundary, capability-authority, stale
  successor and direct-lease regression tests;
- all CC06/R50-R55 overlay and capture regressions;
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

Until those Gates pass, CC06/R56 are not accepted, CAL-REQ-004 remains
undecoded, CAL-REQ-005 is unauthorized, and no M5 technical/MVR or M6 Gate is
opened.
