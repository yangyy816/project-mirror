# P2-M5-R04 — Playwright timeout-wrapper repair

## Status

`LOCAL_CANDIDATE_PENDING_TRACKED_EVIDENCE`

This document records a CI-only repair candidate. It does not declare a remote
pass, alter the Browser Integration gate, or change P2-M5 research evidence.

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

## Required tracked evidence

Acceptance requires a same-SHA GitHub Actions run with all existing jobs and
Browser Integration passing, readable redacted Playwright-install evidence,
and confirmation that no dependency, lockfile, browser-test, product or
research-gate semantics changed.
