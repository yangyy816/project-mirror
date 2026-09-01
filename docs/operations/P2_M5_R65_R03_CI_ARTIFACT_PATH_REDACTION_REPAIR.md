# P2-M5-R65-R03 — CI artifact path-redaction repair

`STATUS: EXECUTING`

## Trigger

R65-R02 closed absolute paths in the Playwright installation artifact, but its
same-SHA review found container-internal absolute paths in the Docker log
artifact. Those paths contained no credential or user data, yet ordinary CI
artifacts must not retain host or container locators.

## Repair

The shared redaction pattern now recognizes Unix paths after punctuation as
well as whitespace, and the Docker log is sanitized before artifact write.
Static tests require the sanitizer to precede both Playwright and Docker
artifact writes.

## Scope boundary

No Docker topology behavior, retry/timeout policy, Provider, runtime, model,
image generation, decode, M3, schema, migration, OpenAPI, ledger or QuestionBank
behavior changes. A new same-SHA CI run and artifact review remain mandatory.
