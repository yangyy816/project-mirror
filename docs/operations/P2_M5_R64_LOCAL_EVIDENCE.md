# P2-M5-R64 — local evidence

`STATUS: LOCAL_GATES_PASS_CANDIDATE_NOT_COMMITTED`

## Scope and negative-operation counters

- `IMAGEGEN_CALLS: 0`
- `DECODE_CALLS: 0`
- `M3_CALLS: 0`
- `PROVIDER_CALLS: 0`
- `SCHEMA_OR_OPENAPI_CHANGES: 0`
- `LEGACY_OVERLAY_CHANGES: 0`

## Completed checks

- legacy overlay SHA-256 exactly matches
  `1487d8d30f7354f7353b4784231ce5ca5b2a83ecdfd4356a152dcde3f5a09a4a`;
- `test_legacy_overlay_bridge.py`: `14 passed`;
- Ruff format/check: PASS; and
- strict mypy for all five R64 source modules: PASS.

## Linux validation

In an isolated Compose project, the API container passed the 36-test R64 plus
private post-registration focused suite. The CI-shaped Worker suite passed, and
`alembic check` found no new upgrade operations. The container image does not
include the whole repository, so a direct full API invocation has expected
missing-file failures for repository-level tests.

A read-only full-worktree Linux invocation completed with only one failure: the
API image lacks `git`, needed solely by a CC08 test that creates a temporary Git
repository. Re-running with a temporary Git installation reached the Windows
worktree-pointer limitation; the final three bounded attempts to install Git
for an isolated copied repository failed at the Debian mirror with HTTP 502
before test execution. No source, Dockerfile, lockfile or CI workflow was
changed to work around that external package-source failure.

A final isolated Linux invocation used an already available Project Mirror API
test image containing Git. It copied the non-private R64 worktree into the
ephemeral container, initialized a local Git repository there, and ran the
complete API suite to a zero exit status. The same isolated Compose project had
already passed its CI-shaped Worker suite and `alembic check`.

## Full-regression disposition

The canonical-LF API collection completed with 934 collected tests. The full
run progressed beyond 70% without a test failure, then remained in the legacy
private post-registration pressure path with no further output and increasing
working set. It was interrupted to protect the host after reproducing the
R60-known old-controller resource-growth symptom.

This is not an R64 acceptance or a reason to weaken any remote Gate. Local
candidate creation is now permitted; same-SHA CI, artifact inspection,
independent reviews and Principal acceptance remain mandatory.
