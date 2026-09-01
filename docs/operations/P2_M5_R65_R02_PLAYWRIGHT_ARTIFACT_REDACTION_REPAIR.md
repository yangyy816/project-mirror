# P2-M5-R65-R02 — Playwright artifact redaction repair

`STATUS: EXECUTING`

## Trigger

R65-R01 exact same-SHA run `33483736921` passed all mandatory CI jobs, but the
uploaded Playwright installation log contained absolute CI runner paths. The
paths contained no credential, image or user data, but ordinary CI artifacts
must not retain host locators.

## Repair

Before either Playwright command appends output to its uploaded artifact, the
workflow redacts file URIs plus Unix, Windows and UNC absolute paths. The
bounded retries, timeouts, official download boundary, command exit status and
Browser Integration Gate are unchanged. Static workflow tests require the
redaction pipeline for both installation steps.

## Scope boundary

No R65 retirement state, ledger, Provider, runtime, model, image generation,
decode, M3, schema, migration, OpenAPI or QuestionBank behavior changes. A
fresh same-SHA CI run and artifact inspection remain mandatory.
