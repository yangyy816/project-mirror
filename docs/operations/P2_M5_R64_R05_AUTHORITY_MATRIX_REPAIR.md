# P2-M5-R64-R05 — authority matrix repair

`STATUS: EXECUTING`

## Trigger

The R64-R04 same-SHA evidence did not discharge two independent-review findings:
the request-reference digest alone was not sufficient proof that every canonical
field matched durable bridge/state authority, and the focused suite no longer
covered the complete v2 security regression matrix.

## Repair

The immutable bridge now carries the verifier-derived action digest, registered
output and receipt anchors, policy anchors, and a snapshot of the already
approved runtime/model authority. The v2 transition compares every request
reference field against those bridge/state anchors before it may write the only
successor state.

The focused regression matrix covers wrong verifier pins; every request-field
mismatch; stale handles, root identity changes and branch files; cross-process
one-writer behavior; repeatability authority and failed-record rejection; and
the 20-operation bounded recovery profile. Tests use only procedural,
non-human bytes in temporary ignored roots.

## Scope boundary

This is a forward independent verifier/bridge repair only. It does not change
the legacy overlay, old receipt, schema, migration, OpenAPI, Provider, policy,
image generation, decode, M3, QuestionBank, or runtime/model artifacts.
R64 remains pending local regression, candidate commit, same-SHA CI, artifact
inspection, independent reviews, and Principal acceptance.

## Local verification

- focused bridge and verifier matrix: `30 passed`;
- focused bridge plus private post-registration regression: `52 passed`;
- CI-range Ruff and strict mypy: PASS;
- canonical-LF full API/Worker regression with task-owned PostgreSQL, Redis,
  Celery and shared private test volume: `964 passed`, `1 skipped`; and
- empty-database `base → head → base → head` migration lifecycle and Alembic
  drift check: PASS.

All exercised inputs were procedural non-human test bytes. No Provider,
image-generation, decode, M3, schema, migration, or legacy-overlay operation
was performed by this repair.
