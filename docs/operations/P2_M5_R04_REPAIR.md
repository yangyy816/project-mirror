# P2-M5-R04 — Playwright timeout-wrapper repair

## Status

`REPAIR_ACCEPTED_AT_EE19AD6_RUN_32282614608_ATTEMPT_1`

This document records an accepted CI-only repair. It does not declare a P2-M5
Gate pass, alter the Browser Integration gate, or change P2-M5 research
evidence.

## Incident and bounded diagnosis

Run `32278984711` at commit `5159c3f28ab8dcbb7db07c5bead3780a409ace25` was
cancelled while `Install Playwright Chromium system dependencies` was running.
The quality job was `96152991638`. The redacted install-evidence artifact
`9376056329` records a start event at `2026-08-19T17:01:49Z`, Ubuntu
`noble-updates` acquisition as the final observed operation, and no terminal
end event. Chromium download and Browser Integration never started.

The prior wrapper applied GNU `timeout` only to `pnpm`, while `tee` was the
right-hand command in the parent shell pipeline. A descendant retaining the
pipeline output descriptor can keep `tee` open after the timed command has
been signalled. The terminal log does not prove which child retained the
descriptor; the repair therefore addresses the wrapper boundary rather than
claiming a Playwright, apt, lockfile, browser, or product defect.

## Repair contract

- System dependencies remain a single execution with a 600-second inner GNU
  timeout and a 12-minute GitHub Actions step watchdog.
- Each of the existing three Chromium download attempts retains its 600-second
  inner GNU timeout, 30/60-second backoff, official-source boundary and
  fail-closed terminal outcome; the complete step has a 35-minute watchdog.
- Each inner timeout now starts `bash -o pipefail -c`; that child owns both the
  Playwright command and `tee -a "$PLAYWRIGHT_INSTALL_LOG"`, then exits with
  the original Playwright command status from `PIPESTATUS[0]`.
- The existing redacted version, start/end timestamp, elapsed-time and exit
  status logging remains the required evidence. `if: always()` continues to
  upload the install log after a normal step failure.

## Tracked acceptance evidence

- Candidate `ee19ad6efe49decfa3a0c8f0dbf3f130b5c59460` passed GitHub Actions run
  `32282614608` attempt 1. Quality job `96164640367`, Docker job `96164640344`
  and secret-scan job `96164640053` all succeeded.
- Playwright `1.62.1` system dependencies completed in 12 seconds with exit
  status 0. Chromium downloaded from the official Playwright source on attempt
  1/3 in 12 seconds with exit status 0. Browser Integration passed 5/5 in
  13.1 seconds.
- All eight artifacts were readable and unexpired. Install artifact
  `9376516571` has API digest
  `sha256:83fcede6c3c7ae45bf3aa7825fefaf1e14a5a99edd4df4f634e9e56afdfefd31`;
  its extracted log has SHA-256
  `dc50b9aea95858178d994e13d76cb1b4e636c19dfee5652feb555432c5c2125d`.
- The full Python suite passed 642 tests with one existing optional private
  runtime skip. Frozen Phase 1/M1/M2/M3 evidence remained exact-SHA bound at
  migration head `0014_m5_eval_authority` and unchanged OpenAPI digest
  `a9ee1e0ad3b942e5be5790b4fc7ff8c0deab744a84d3383a7a8856a8f97b4841`.
- Independent security and final reviews found no mandatory issue. The
  Principal accepts R04 as CI-only resilience evidence.

This acceptance does not claim that the timeout branch was injected on the
successful run. Static regression tests and the Linux GNU `timeout` probe bind
that branch; any future timeout incident must still fail the job and retain its
own evidence. R04 does not change a dependency, lockfile, browser test, product
behavior, research result or P2-M5 Gate.
