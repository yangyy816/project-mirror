# P2-M4 Principal Refinement Review

## Decision

- Review date: 2026-08-18
- Baseline: `6b86a665e845e113bbfa2820f906d3b78506b753`
- Decision: `PRINCIPAL_REFINEMENT_REVIEW: PASS`
- Milestone state after review: `EXECUTION_READY`

## Evidence reviewed

- P2-M3 is FROZEN and GitHub Actions run `32108427849` passed all three jobs on the exact baseline.
- ADR-036 separates immutable source/spec/run/result/measurement authority and retains M5 isolation
  and M6 release boundaries.
- The research protocol prohibits absolute/global target geometry, Prompt-only claims, real-person
  inputs, sensitive routing and post-holdout threshold relaxation.
- The execution protocol provides T01–T08 bounded tasks, dependencies, collision domains, validation,
  repair numbering and candidate/closure/freeze ordering.
- M3 OpenCV 3.4.11 remains an isolated Vision build input and is not inherited by M4. Any transform
  candidate requires a separate evidence-backed disposition.
- No production code, migration, dependency manifest, model artifact, image binary, public API or M5
  implementation was added by T01.

## Conflict review

- Product Invariants: no conflict.
- P2-M3 frozen authority: no rewrite.
- Public OpenAPI: unchanged.
- Migration history: unchanged; entry head remains `0011_offline_synth_source`.
- Synthetic-only and real-user processing boundary: preserved.
- P2-MVR-v1: remains a future M5 technical-feasibility Gate, not an M4 PASS claim.

## Unlocked work

T02, T03 and T04 may begin under their frozen contracts. T05 remains blocked until T04 produces an
explicit `APPROVED_FOR_PRIVATE_SYNTHETIC_M4` candidate disposition. M5 refinement remains closed until
P2-M4 reaches FROZEN.
