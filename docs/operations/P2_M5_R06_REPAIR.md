# P2-M5-R06 — Playwright system-dependency acquisition retry repair

## Status and authority

- Status: `LOCAL_GATE_PASS_CANDIDATE_PENDING`.
- Trigger: acceptance checkpoint `aa32c8b912aa0a5196f2615a1ed4b651ef17166d`, GitHub Actions run
  `32300981951`, attempts 1 and 2.
- Classification: `REPEATED_EXTERNAL_APT_REPOSITORY_ACQUISITION_STALL`.
- Boundary: CI acquisition resilience only. This repair does not change product code, dependencies, the lockfile,
  Browser Integration semantics, acceptance thresholds, research evidence or the P2-M5 Gate.

## Repository evidence and reclassification

Both attempts ran the same commit and passed Python, Phase 1/M1/M2/M3 evidence tests and TypeScript before the
system-dependency step. Attempt 1 quality job `96223196271` and attempt 2 quality job `96227326083` each spent exactly
600 seconds in `playwright install-deps chromium` and exited through the existing GNU timeout with status `124`.

The final progressing operations in both logs were Ubuntu `noble-updates` package-index acquisition through the
GitHub-hosted runner mirror list. Chromium binary acquisition and Browser Integration never started. There is no
checksum, browser revision, launch, disk-space, TLS, lockfile or test-assertion failure evidence. Because the same
stage failed twice consecutively, this incident is no longer described as a single transient download stall.

Successful run `32299835326` at candidate `298420fcc362851b96c1005e25608f37b2016373` remains the control: the same
Playwright `1.62.1` command completed system dependencies, official Chromium acquisition and Browser Integration
without a repository change. Its system-dependency log also proves that Ubuntu runners require nine packages, so
skipping `install-deps` or treating the runner image as sufficient would weaken the Browser Gate.

## Bounded-task contract

- `BOOTSTRAP_STATUS`: `OK`.
- `TASK_ID`: `P2-M5-R06`.
- `OBJECTIVE`: recover from a bounded apt repository acquisition stall inside the same ephemeral runner while
  retaining the existing fail-closed Browser Gate.
- `WHY_DELEGATED`: not delegated; this repair has one workflow/test collision domain and follows an active Principal
  acceptance checkpoint.
- `SCOPE`: the Playwright system-dependency workflow step, its static resilience test and this forward repair record.
- `ALLOWED_FILES_OR_MODULES`: `.github/workflows/ci.yml`,
  `services/api/tests/test_ci_playwright_resilience.py`, this document and later forward acceptance evidence.
- `EXPECTED_CHANGE`: retain the official Playwright `install-deps chromium` command, but run at most three
  600-second attempts in the same runner with 30/60-second backoff and per-attempt timestamps, elapsed time, exact
  Playwright version and exit status.
- `FORBIDDEN_SCOPE`: product source, lockfile, package versions, browser tests, test retries, acceptance thresholds,
  Ubuntu source rewriting, dependency caching, research results, Phase/Milestone state or protected worktree files.
- `DEPENDENCIES`: Playwright `1.62.1`, GNU `timeout`, Bash and the existing always-uploaded redacted install evidence.
- `INPUTS_AND_ASSUMPTIONS`: a timed-out `apt-get update` leaves only ephemeral runner state; rerunning the idempotent
  official Playwright command can reuse successfully acquired indexes and still validates/install the full package
  set.
- `ACCEPTANCE_CRITERIA`: success stops retries immediately; every attempt is hard-bounded; three failures fail the
  job; install evidence is uploaded on failure; Chromium acquisition remains a separate three-attempt step; Browser
  Integration still runs only after both acquisition stages pass.
- `VALIDATION_COMMANDS`: targeted Ruff and pytest; workflow formatting; Bash/GNU-timeout failure/success probe in an
  isolated Linux container; full local applicable gates; exact-SHA GitHub Actions and artifact inspection.
- `SECURITY_NOTES`: no new endpoint, credential, proxy, mirror override or untrusted script is introduced.
- `PRIVACY_NOTES`: no Prompt, image, user data, object key or provider payload is processed.
- `DATA_NOTES`: no database, migration, generated contract or research authority changes.
- `LICENSE_NOTES`: no dependency or model artifact changes.
- `ROLLBACK`: revert R06 before any dependent acceptance checkpoint; R04 remains the historical timeout-wrapper
  evidence.
- `RECOMMENDED_AGENT`: Principal.
- `RECOMMENDED_MODEL_TIER`: current Principal; no subagent is needed for the single workflow collision domain.
- `OUTPUT_FORMAT`: standard bounded-task report with local, exact-SHA CI and artifact evidence.
- `ESCALATION_CONDITION`: any need to skip dependencies, rewrite package sources, change the runner image, weaken
  Browser Integration or alter product/research behavior.

## Repair contract

- R04's inner timeout ownership is preserved for every attempt: the child Bash process owns both the Playwright
  command and its `tee` logging pipeline.
- The system-dependency step now has three attempts, 600 seconds each, with 30/60-second backoff and a 35-minute
  outer Actions watchdog. Worst-case inner timeout plus kill/backoff remains below the outer bound.
- Retrying occurs before Chromium acquisition, on the same runner, and may reuse only that runner's partial apt
  state. Browser download is not repeated until system dependencies succeed.
- The install evidence records attempt number, start/end UTC timestamp, elapsed seconds, exact Playwright version,
  exit status, retry delay and terminal failure outcome.
- Any successful attempt exits immediately. Three failures remain a hard job failure; Browser Integration is never
  skipped and reported as successful.

## Local validation

- The locked CLI reports Playwright `1.62.1`; its official `install-deps --help` confirms the supported
  `install-deps` command. The successful control log shows nine runner packages were actually missing, so R06 does
  not use the optional dry-run mode to skip installation.
- `test_ci_playwright_resilience.py` passed 3/3. Ruff format, lint and strict mypy passed for the changed Python test.
  The workflow parsed as YAML and `git diff --check` passed for the complete R06 scope.
- A Linux `--network none` probe using the repository API image exercised the same Bash/GNU-timeout control flow. A
  first-attempt stall returned `124`, attempt 2 succeeded and stopped the loop; a separate case returned non-zero on
  all three attempts and produced the terminal `outcome=failed attempts=3` evidence.
- `pnpm check` passed formatting, ESLint, strict TypeScript, 56 Vitest tests, generated-contract drift and the
  production build. No generated contract, dependency, lockfile, browser test or product file changed.

`P2_M5_R06_LOCAL_GATE: READY_FOR_CANDIDATE_CI`
