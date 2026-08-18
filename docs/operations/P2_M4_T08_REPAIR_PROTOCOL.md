# P2-M4 T08 Forward Repair Protocol

## Status and authority

- Status: `EXECUTING`.
- Trigger: independent T08 final review of candidate `852a9777d8acec30170cc76554a97b51b3296228`.
- Authority: ADR-036–040, `P2_M4_EXECUTION_PROTOCOL.md` and the immutable T07 preregistration.
- Boundary: forward repair only. This document does not rewrite ADR-040, the original preregistration, private
  attempt evidence or the T07 measured result.
- P2-M5, production geometry, real-user facial processing and QuestionBank release remain closed.

## Recovered split authority

The Principal recovered the four source authorities from the preserved `p2m3_v01_authority` PostgreSQL database.
The new split envelope binds all three independent identifiers instead of inferring identity ownership from labels.

| Cohort      | M3 item             | SyntheticIdentity ID               | Asset ID                           | normalized SHA-256                                                 |
| ----------- | ------------------- | ---------------------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| calibration | `v01-category-a-02` | `1dd1786221d34bae9863df77c9d531e6` | `7c14195846924ad19d762080a626ab54` | `71fc0fadc69841664664cd912132edb2d64adc227a78755be38dedf5113add1e` |
| calibration | `v01-category-b-02` | `a959c8c392bb44f6a9120385ef16949c` | `d714a022dc2249edadef524ebb25f623` | `3532d0f7e30d64916a81059c24e6e0ea33f3c9fa5fff66600f7131a6728c9a05` |
| holdout     | `v01-category-c-02` | `4d4586cd398b496ba67c0f1601626706` | `27105c9647ad483c946f781570da06fe` | `a84f6a0316a665f311b42bf4c88d51caab1e0327109529d72f1a05d45940c3c5` |
| holdout     | `v01-category-d-02` | `58d63ba8b1854713a27fff66624994a7` | `6a034f419c3f4b3c895fc062c54d3833` | `c225320284eceec77dbdf24d9a806ce77f030f40f17237487719411bcc8255c5` |

This table contains opaque internal authority references and checksums only. It contains no image, object key,
private path, Prompt, landmark payload or User relation.

## P2-M4-R13 — Split-envelope authority repair

- `BOOTSTRAP_STATUS`: `OK`.
- `OBJECTIVE`: version the private input and split schemas so calibration and holdout are independently bound by
  SyntheticIdentity ID, Asset ID and normalized SHA-256.
- `WHY_DELEGATED`: not delegated; the Principal owns the integrated evidence repair.
- `SCOPE`: T07 private harness, focused tests, forward redacted evidence and reports.
- `ALLOWED_FILES_OR_MODULES`: `scripts/research/run_p2_m4_t07_evaluation.py`, its tests and P2-M4 T07/T08 evidence.
- `FORBIDDEN_SCOPE`: changing cohort, threshold, magnitude, algorithm, output policy or original attempt evidence.
- `DEPENDENCIES`: preserved M3 authority rows and unchanged four source bytes.
- `INPUTS_AND_ASSUMPTIONS`: the four rows above are authoritative and remain disjoint on all three axes.
- `ACCEPTANCE_CRITERIA`: three separate overlap negatives fail closed; within-split duplicates also fail closed;
  v2 digests are deterministic; labels are never substituted for authority IDs.
- `VALIDATION_COMMANDS`: focused pytest, Ruff, strict mypy, fixed private holdout replay and redaction scan.
- `RECOMMENDED_AGENT`: Principal/test worker.
- `RECOMMENDED_MODEL_TIER`: Terra Medium implementation with Principal integration.
- `OUTPUT_FORMAT`: standard bounded-task report.
- `ESCALATION_CONDITION`: missing source authority, changed source bytes or need to change the frozen cohort.

## P2-M4-R14 — Exact Vision and topology binding repair

- `BOOTSTRAP_STATUS`: `OK`.
- `OBJECTIVE`: fail closed before parsing or native execution unless the platform Vision executable and topology
  file match the frozen M3/T07 SHA-256 values.
- `WHY_DELEGATED`: not delegated; it collides with R13 in the same harness.
- `SCOPE`: T07 harness and focused negative tests.
- `ALLOWED_FILES_OR_MODULES`: T07 harness, tests and forward evidence.
- `FORBIDDEN_SCOPE`: replacing the source-built Vision runtime, model, topology, OpenCV runtime or model disposition.
- `DEPENDENCIES`: the exact Windows wrapper plus R25 main/core/imgproc closure
  (`d7d65625...` / `1c67ae02...` / `e0415de8...` / `1aa54040...`), the exact Linux wrapper plus
  R25 main/core/imgproc closure (`1cfbd3b2...` / `6a5fb351...` / `116c2db3...` / `765ebf6c...`), model SHA
  `64184e22...` and topology SHA `85eea84e...`.
- `INPUTS_AND_ASSUMPTIONS`: platform is an explicit closed enum; unknown platforms are rejected.
- `ACCEPTANCE_CRITERIA`: wrong executable, model or topology bytes stop before output-root creation, topology
  parsing, Vision execution and transform execution.
- `VALIDATION_COMMANDS`: focused pytest plus unchanged Windows/Linux private replay.
- `RECOMMENDED_AGENT`: Principal/test worker.
- `RECOMMENDED_MODEL_TIER`: Terra Medium implementation with Principal integration.
- `OUTPUT_FORMAT`: standard bounded-task report.
- `ESCALATION_CONDITION`: any required runtime/model/topology replacement.

## P2-M4-R15 — Active-state governance repair

- `BOOTSTRAP_STATUS`: `OK`.
- `OBJECTIVE`: remove the two stale P2-M3 `EXECUTING` declarations without changing historical evidence.
- `WHY_DELEGATED`: not delegated; two atomic governance lines are integrated with this closure.
- `SCOPE`: root project identity and current OSS execution boundary.
- `ALLOWED_FILES_OR_MODULES`: `AGENTS.md`, `docs/architecture/OSS_EVALUATION.md`.
- `FORBIDDEN_SCOPE`: historical audit text, Phase/Milestone Gate decisions or dependency dispositions.
- `DEPENDENCIES`: P2-M3 frozen closure `abbf6c9`; P2-M4 remains `EXECUTING`.
- `INPUTS_AND_ASSUMPTIONS`: current authority is `MEMORY.md` plus `MILESTONES.md` and the M4 protocol.
- `ACCEPTANCE_CRITERIA`: stale active-state scan reports zero contradictory current declarations.
- `VALIDATION_COMMANDS`: bounded source scan, Markdown format and `git diff --check`.
- `RECOMMENDED_AGENT`: Principal.
- `RECOMMENDED_MODEL_TIER`: Spark-eligible atomic edit, retained by Principal to avoid task overhead.
- `OUTPUT_FORMAT`: standard bounded-task report.
- `ESCALATION_CONDITION`: any contradictory Gate evidence.

## P2-M4-R16 — Persisted ontology execution Gate repair

- `BOOTSTRAP_STATUS`: `OK`.
- `OBJECTIVE`: rehydrate every executable specification from the approved, digest-valid persisted ontology and
  re-enforce `READY | EXPERIMENTAL` membership for its target and every control dimension before any I/O.
- `WHY_DELEGATED`: not delegated; the Principal owns the application/security integration repair.
- `SCOPE`: transform application service and PostgreSQL-backed adversarial tests.
- `ALLOWED_FILES_OR_MODULES`: `transform_service.py` and M4 orchestration tests.
- `FORBIDDEN_SCOPE`: historical migration edits, new schema, dimension promotion, threshold changes or production
  enablement.
- `DEPENDENCIES`: ADR-036 domain taxonomy and immutable approved ontology rows.
- `INPUTS_AND_ASSUMPTIONS`: a direct SQL/ORM row can be syntactically valid while semantically non-researchable;
  execution must not trust construction-time validation alone.
- `ACCEPTANCE_CRITERIA`: unknown, `UNSUPPORTED`, `REQUIRES_3D`, `STYLE_ONLY` target/control rows are rejected while
  the run remains `SPECIFIED`; source reads, native calls, result storage and result Asset creation remain zero.
- `VALIDATION_COMMANDS`: real PostgreSQL adversarial tests, focused/full pytest, Ruff and strict mypy.
- `RECOMMENDED_AGENT`: Principal/backend worker.
- `RECOMMENDED_MODEL_TIER`: Terra High because persisted authority and failure-path ordering are involved.
- `OUTPUT_FORMAT`: standard bounded-task report.
- `ESCALATION_CONDITION`: a database-level classification trigger or new migration becomes necessary.

## Closure sequence

```text
R13–R16 implementation
→ focused negative tests
→ fresh private Windows/Linux holdout output roots
→ v2 redacted evidence and unchanged-result reconciliation
→ full local Gate
→ exact-SHA candidate CI and artifact inspection
→ independent security and final review
→ Principal Gate decision
```

`P2_M4_T08_REPAIR_GATE: EXECUTING`
