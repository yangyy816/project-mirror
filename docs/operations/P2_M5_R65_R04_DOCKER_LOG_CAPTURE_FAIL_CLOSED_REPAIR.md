# P2-M5-R65-R04 — Docker log capture fail-closed repair

`STATUS: EXECUTING`

## Trigger

The independent R65-R03 final review confirmed all three mandatory CI jobs and
all redacted artifacts, but found that the Docker evidence pipeline did not
explicitly preserve the upstream `docker compose logs` exit status. A successful
sanitizer could otherwise mask a failed log capture.

## Repair

The capture step now sets `pipefail` before the pipeline, so an upstream Docker
log failure fails the job instead of producing incomplete evidence. The static
regression test requires that guard to precede the capture command and retains
the existing sanitizer-before-write checks.

## Scope boundary

No Docker topology behavior, retry/timeout policy, Provider, runtime, model,
image generation, decode, M3, schema, migration, OpenAPI, ledger or
QuestionBank behavior changes. A fresh same-SHA CI run, artifact audit,
independent Security review and final review remain mandatory.
