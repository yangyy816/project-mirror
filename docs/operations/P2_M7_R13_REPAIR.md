# P2-M7-R13 — operator cancellation replay repair

## Status

`READY_FOR_TRACKED_EVIDENCE`

## Finding

The T08 final review found that a `RUNNING` generation batch can retain that state after the first operator cancellation
request while an item attempt is still leased. Repeating the same command and `request_id` therefore passed the state
expectation again and appended a second `AuditLog` row. The existing concurrency test used two different request IDs and
did not prove at-least-once replay safety.

## Bounded task contract

- `TASK_ID`: `P2-M7-R13`
- `OBJECTIVE`: make exact operator-cancellation retries idempotent while rejecting request-ID reuse with changed input.
- `SCOPE`: the accepted generation cancellation application service, its P2-M7 adapter, PostgreSQL recovery tests and
  this repair evidence.
- `ALLOWED_FILES_OR_MODULES`: `generation_service.py`, `operations_integration.py`,
  `test_p2_m7_recovery_integration.py`, P2-M7 repair/acceptance records.
- `EXPECTED_CHANGE`: serialize the request reference in PostgreSQL, replay one matching audit effect, and fail closed
  when target, expectation, actor or reason differs.
- `FORBIDDEN_SCOPE`: schema/migration, new authority, CLI composition, public API, M5/M6 behavior, dependency, Provider,
  model, production enablement or weakened cancellation/recovery behavior.
- `DEPENDENCIES`: accepted T02–T07/R12 code and T08 final-review finding at `9584177`.
- `INPUTS_AND_ASSUMPTIONS`: PostgreSQL remains authoritative; `AuditLog` is the accepted append-only operator evidence;
  request IDs and all compared fields have already crossed the typed validation boundary.
- `ACCEPTANCE_CRITERIA`: serial and concurrent exact retries yield one authoritative cancel/audit effect; changed
  target/expectation/actor/reason fails closed; stale expectation and crash-recovery behavior remain intact.
- `VALIDATION_COMMANDS`: focused real-PostgreSQL tests, full P2-M7 tests, Ruff, strict mypy, migration lifecycle,
  OpenAPI drift, full same-SHA GitHub Actions and eight-artifact inspection.
- `SECURITY_NOTES`: no caller value is included in exceptions or logs; the advisory-lock reference is never rendered.
- `PRIVACY_NOTES`: synthetic authority IDs only; no image, Prompt, object key, Provider payload or user data.
- `DATA_NOTES`: no new row shape or migration; exact replay reuses the existing append-only audit evidence.
- `LICENSE_NOTES`: no dependency, model, weight or external service change.
- `ROLLBACK`: disable the unaccepted mutation composition and retain the original audit evidence; no schema rollback.
- `RECOMMENDED_AGENT`: Principal bounded repair.
- `RECOMMENDED_MODEL_TIER`: Terra High because the frozen repair covers transaction and concurrent replay behavior.
- `ESCALATION_CONDITION`: any need for a new table, unique constraint, role model or persistence authority stops this
  repair and requires forward change control.
- `OUTPUT_FORMAT`: standard Project Mirror bounded-task report.

R13 does not make the real CLI entrypoint available. T08 and the M7 Gate remain blocked until R13 and the separate R14
composition repair both pass same-SHA evidence and independent re-review.

## Local evidence

- Real PostgreSQL 17 isolated database, fresh upgrade through `0014_m5_eval_authority`: PASS.
- Focused replay/concurrency/recovery suite: `6 passed`, zero skip.
- Complete P2-M7 Python suite: `65 passed`, zero skip.
- `0014 -> 0013 -> 0014` lifecycle and `alembic check`: PASS, zero drift.
- Focused Ruff and strict mypy: PASS; OpenAPI/generated TypeScript drift check: PASS.
- A first broad `pytest tests -k p2_m7` collection attempt lacked repository-root research/governance scripts in the
  read-only container mount and failed during unrelated module collection. The corrected exact P2-M7 file collection
  passed without a product change; this harness attempt is not treated as an application defect.

No CLI composition, migration, dependency, public contract, production, M5 or M6 change is included. Remote exact-SHA
CI, eight-artifact inspection and Principal acceptance are still required before R14 may expose mutation composition.
