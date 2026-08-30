# ADR-055: Recoverable private Vision runtime versioning and post-registration rebinding

## Status

Accepted for implementation under `CC-P2-M5-08`, conditional on the CC08-G
candidate completing same-SHA CI, artifact inspection, independent review and
Principal acceptance.

## Context

ADR-054 pins the CAL-REQ-004 post-registration canary to the accepted V01/V03
Linux and Windows runtime artifacts, model, manifest and QA policy. R57 then
correctly requires exact caller-retained capability authority and refuses
payload self-signing.

CC07-A reacquired the official source commit, exact model, model cards, frozen
patches, Bazel binaries and OpenCV source. It could not recover the historical
effective build-input manifest bytes/algorithm, the exact builder inventory
bytes or task-scoped builder/repository-cache handles. A digest-only historical
claim cannot recreate an executable capability. CC07-A therefore stopped at
`BLOCKED_EXACT_BUILD_INPUT_AUTHORITY_UNAVAILABLE` before any build, model load,
Vision call or canary access.

Using the same source and model under a new toolchain may produce a valid
candidate, but it cannot inherit the old runtime identity or QA approval.

## Decision

1. Establish `CC-P2-M5-08 — Recoverable Private Vision Runtime V2
Qualification and CAL-REQ-004 Rebinding` as a new forward execution line.
   CC07-A and all old V01/V03/R25/R26 evidence remain immutable history.
2. Preserve the accepted MediaPipe commit, exact Face Landmarker model and 12
   frozen source patches as input authorities. New output bytes receive new,
   observed runtime/OpenCV digests and a new manifest version; no near match may
   be relabeled as an old V01 artifact.
3. Require a tracked deterministic builder algorithm and exact public input
   lock. Private repository caches, builder objects and outputs must have
   complete digest/byte manifests, reacquisition rules and recoverable
   task-scoped registry handles. An undocumented private algorithm is not
   authority.
4. Freeze these new versions:
   - `p2-m5-cc08-source-built-vision-recipe-v1`;
   - `p2-m5-cc08-private-vision-runtime-v1`;
   - `p2-m5-cc08-private-vision-qa-v1`; and
   - `p2-m5-cc08-post-registration-capability-v1`.
5. Build serially on Linux and Windows with two clean roots per platform. Only
   byte-identical pairs may enter the new runtime manifest. A single-platform
   or nondeterministic build stops.
6. Re-run supply-chain, native-surface and process-level zero-egress
   qualification for the new artifacts. Distribution, production and real-user
   use remain blocked.
7. Do not automatically inherit the old V03 QA approval. Old numeric limits
   may be preregistered unchanged as candidate hypotheses, but a new policy
   version must bind the new runtime manifest and pass fresh synthetic-only
   calibration plus a sealed identity-disjoint holdout. Holdout failure cannot
   be repaired by relaxing that policy version.
8. Update the tracked post-registration controller constants and policy
   reference only after the new runtime and QA authorities are accepted. The
   registered CAL-REQ-004 overlay tip remains immutable; no post-registration
   attempt currently exists, so forward controller rebinding does not rewrite
   private history.
9. Preserve ADR-054's state machine, plan-before-invoke, unknown-outcome,
   terminal/successor and no-retry rules, plus all R57 external registered-tip,
   terminal-tip and capability-map requirements.
10. Before canary decode, an independent Principal verifier must create the
    exact per-platform capability map, bind recoverable executor handles and
    prepare an empty write-once terminal-tip checkpoint slot.

## Version and authority boundary

ADR-055 supersedes ADR-054 only for future post-registration runtime/manifest/
policy pins. It does not supersede ADR-032/033/034 source and security
decisions, ADR-049 custody, R55 concurrency, R57 evidence replay, the generation
ledger, or any product/data invariant.

No migration, ORM, OpenAPI, public API, dependency lock, workflow, Provider,
generation policy, resource ceiling, QuestionBank release, production or
real-user authority changes.

## Alternatives considered

- **Use the reacquired source to claim the old runtime digest.** Rejected: source
  equality is not binary or builder authority.
- **Use a near-matching rebuild with the old manifest.** Rejected: it breaks
  provenance and QA binding.
- **Search Docker, sibling tasks or D02 for legacy handles.** Rejected by
  ADR-049, CC07-A and the accepted D02 negative handoff.
- **Run CAL-REQ-004 as the calibration input.** Rejected: readiness and QA must
  precede the canary.
- **Adopt the official MediaPipe wheel.** Rejected: it remains the telemetry
  negative control.

## Consequences

CC08 adds a serial qualification line and may honestly stop if the new builder,
two-platform outputs, zero-egress, synthetic fixture authority or QA holdout
cannot pass. Successful source-equivalent reconstruction still produces a new
runtime identity and requires controller rebinding.

Private source/model/runtime bytes and locators stay outside Git. Tracked
evidence contains only versions, hashes, byte counts, allowlisted results and
reproducibility instructions.

## Security, privacy, data and license

The scope remains private, synthetic-only and internal. No real-person or user
image, sensitive inference, beauty/age scoring, production Vision,
distribution, public API or credential is authorized. The exact model remains
`PRIVATE_RESEARCH_ONLY`; incomplete training-data/redistribution evidence is not
upgraded by a successful build.
