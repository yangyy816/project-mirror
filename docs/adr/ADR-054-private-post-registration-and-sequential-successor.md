# ADR-054: Private post-registration qualification and sequential successor

## Status

Accepted for implementation under `OD-P2-M5-IMAGEGEN-BATCH-EXECUTION-001`; operational authority remains
conditional on the resulting candidate completing same-SHA CI, artifact inspection, independent review and Principal
acceptance.

## Context

R55 established a digest-bound, project-local, Git-ignored custody root and a cooperative cross-process lease for the
native imagegen transport. `CAL-REQ-004` then reached `OUTPUT_REGISTERED_PRE_DECODE` with one exact registered PNG,
but the tracked controller intentionally stops at `verify_registration_before_decode()`. It has no transition for
bounded decode, deterministic normalization, the accepted private-synthetic M3 reliability checks, a terminal content
disposition, or a sequential successor.

Changing `private_execution_overlay.py` now would change the controller digest already bound into the live
`CAL-REQ-004` receipt. Replacing that controller in place would make the accepted custody evidence unverifiable.
Creating one repair and one same-SHA Gate per successful image would instead turn an operational batch into an
unbounded governance loop. The Owner standing decision authorizes one batch-level forward change while preserving the
existing 32-call ledger, concurrency one, one output per call and zero same-ordinal retries.

## Decision

1. Add a separate, digest-bound private post-registration controller. It starts only from the exact current
   `OUTPUT_REGISTERED_PRE_DECODE` tip, reacquires the R55 quiescence lease and reruns the complete registration verifier.
2. Keep the live overlay controller byte-for-byte unchanged. The auxiliary controller binds its own SHA-256 into every
   attempt, operation, checkpoint and terminal transition while the original overlay receipt continues to retain its
   original controller pin.
3. Use `image-sanitizer-v1` for bounded decode, metadata-free canonical JPEG creation and second decode. Raw, normalized
   and evidence files remain distinct create-new-or-verify-exact private objects.
4. Consume M3 through provider-neutral canonical vision values plus a private technical wrapper for platform, runtime,
   model, transformation-matrix, occupancy and zero-egress evidence. Runtime/model locators remain injected opaque
   handles and never enter tracked evidence. Capability authority digests must come from the independently verified
   task-scoped registry authority; deriving the expected authority from the supplied capability at execution time is
   prohibited.
5. Bind the accepted V01/V03 technical authority exactly: two supported platforms, ten executions per platform,
   478 landmarks, the frozen runtime/model/policy digests and the preregistered repeatability, parity, occupancy and pose
   limits. No download, runtime substitution, hidden network, threshold relaxation or one-platform downgrade is allowed.
6. Persist an operation plan before every M3 invocation and its result after return. A fresh process may resume only
   from a complete durable result. A planned invocation without a result is
   `POST_REGISTRATION_UNKNOWN_M3_OUTCOME` and is never rerun. If a terminal checkpoint or successor intent was durable
   before a process interruption, recovery reuses its persisted timestamp and exact canonical payload rather than
   synthesizing a new record.
7. Use four terminal outcomes:
   - `POST_REGISTRATION_TECHNICAL_QA_PASSED`;
   - `POST_REGISTRATION_CONTENT_REJECTED`;
   - `POST_REGISTRATION_INFRA_FAILURE`; and
   - `POST_REGISTRATION_UNKNOWN_M3_OUTCOME`.

   Every terminal state has `active_calls=0`, disables decode, preserves Provider counters and records the truthful
   `decode_performed` fact. Technical QA does not create an Asset, QA database authority, identity, admission or
   QuestionBank member.

8. A generic successor rollover derives the next ordinal and all counters from the exact terminal predecessor. It
   durably commits the parent-scoped intent before creating the successor root, so a crash cannot leave an
   unauthoritative unrecoverable root. It then creates or recovers the exact zero-work root, binds predecessor
   receipt/state/event/checkpoint digests, commits `READY` atomically under the same lease model, and rejects stale,
   forked or replayed transitions.
9. `CAL-REQ-004` is the one-call canary tranche. Only technical QA PASS may open tranche 2. Within an already accepted
   later tranche, technical PASS or a completed content rejection may advance to the next sequential ordinal; an
   infrastructure, unknown-outcome or global-integrity failure stops the tranche immediately.
10. Private evidence is retained per output. Tracked governance is emitted once per completed tranche or hard incident,
    never per normal output.

## Alternatives considered

- **Modify the live overlay controller.** Rejected because it invalidates the exact controller digest already bound to
  the registered canary.
- **Run M3 through the normal PostgreSQL orchestration and admission services.** Rejected for this change because the
  canary first needs private technical qualification; creating Asset, Job, QA or identity authority would expand scope.
- **Treat registration as sufficient and start the next ordinal.** Rejected because the standing canary Gate explicitly
  requires decode, deterministic QA and fresh recovery.
- **Create one Rxx and remote Gate per output.** Rejected by the standing batch authorization and because it adds no
  safety once the common controller is accepted.
- **Retry an incomplete M3 operation.** Rejected because an invocation-start receipt without a durable result has an
  unknown external outcome.

## Consequences

- The post-registration module deliberately has a narrow internal coupling to exact overlay helpers; focused tests must
  detect drift in that coupling.
- The Owner standing cap of 50 remains only an outer interaction ceiling. The effective call cap is always the smaller
  accepted execution ledger; after `CAL-REQ-004` registration the verified remaining ledger is 28 formal calls, 28 raw
  outputs and 59 global native outputs.
- Exact task-scoped Windows/Linux runtime and model handles are execution preconditions, not tracked locators or new
  adoption decisions.
- A technically qualified canary may still require categorical adult, likeness, license, watermark, background, style,
  duplicate and morphology review before any later source admission.
- This ADR changes no migration, ORM, OpenAPI, public API, dependency, CI workflow, M6 state, production capability or
  real-user processing boundary.
