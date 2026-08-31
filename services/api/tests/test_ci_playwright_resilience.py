"""Static fail-closed checks for the Playwright acquisition workflow boundary."""

import re
from pathlib import Path

WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


def _step_body(workflow: str, step_name: str, next_step_name: str) -> str:
    start = workflow.index(f"      - name: {step_name}\n")
    end = workflow.index(f"      - name: {next_step_name}\n", start)
    return workflow[start:end]


def test_playwright_system_dependencies_timeout_owns_each_logging_pipeline_and_retries() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    step = _step_body(
        workflow,
        "Install Playwright Chromium system dependencies",
        "Download Playwright Chromium",
    )

    timeout = 'timeout --signal=TERM --kill-after=30s "${timeout_seconds}s"'
    child_shell = "bash -o pipefail -c '"
    pnpm_command = "pnpm --filter @mirror/web exec playwright install-deps chromium 2>&1"
    loop = 'for attempt in $(seq 1 "$max_attempts"); do'
    success_branch = """            if [[ "$install_status" -eq 0 ]]; then
              exit 0
            fi"""
    backoff_branch = """            if [[ "$attempt" -lt "$max_attempts" ]]; then
              backoff="${backoff_seconds[$((attempt - 1))]}"
              printf 'event=playwright_system_dependencies retry_after_seconds=%s\\n' "$backoff" \\
                | tee -a "$PLAYWRIGHT_INSTALL_LOG"
              sleep "$backoff"
            fi"""
    terminal_failure = (
        "printf 'event=playwright_system_dependencies outcome=failed attempts=%s\\n' "
        '"$max_attempts"'
    )

    assert "timeout-minutes: 35" in step
    assert "readonly max_attempts=3" in step
    assert "readonly timeout_seconds=600" in step
    assert "readonly -a backoff_seconds=(30 60)" in step
    assert ': > "$PLAYWRIGHT_INSTALL_LOG"' in step
    assert loop in step
    assert timeout in step
    assert child_shell in step
    assert pnpm_command in step
    assert '| tee -a "$PLAYWRIGHT_INSTALL_LOG"' in step
    assert 'exit "${PIPESTATUS[0]}"' in step
    assert 'install_status="$?"' in step
    assert success_branch in step
    assert backoff_branch in step
    assert terminal_failure in step

    loop_start = step.index(loop)
    timeout_start = step.index(timeout, loop_start)
    child_start = step.index(child_shell, timeout_start)
    command_start = step.index(pnpm_command, child_start)
    success_start = step.index(success_branch, command_start)
    backoff_start = step.index(backoff_branch, success_start)
    sleep_start = step.index('sleep "$backoff"', backoff_start)
    loop_end = step.index("          done\n", sleep_start)
    terminal_start = step.index(terminal_failure, loop_end)
    terminal_exit = step.index("          exit 1\n", terminal_start)
    assert (
        loop_start
        < timeout_start
        < child_start
        < command_start
        < success_start
        < backoff_start
        < sleep_start
        < loop_end
        < terminal_start
        < terminal_exit
    )

    outer_match = re.search(r"timeout-minutes: (\d+)", step)
    attempts_match = re.search(r"readonly max_attempts=(\d+)", step)
    timeout_match = re.search(r"readonly timeout_seconds=(\d+)", step)
    kill_after_match = re.search(r"--kill-after=(\d+)s", step)
    backoff_match = re.search(r"readonly -a backoff_seconds=\((\d+) (\d+)\)", step)
    assert outer_match is not None
    assert attempts_match is not None
    assert timeout_match is not None
    assert kill_after_match is not None
    assert backoff_match is not None

    outer_minutes = int(outer_match.group(1))
    max_attempts = int(attempts_match.group(1))
    timeout_seconds = int(timeout_match.group(1))
    kill_after_seconds = int(kill_after_match.group(1))
    backoff_seconds = [int(value) for value in backoff_match.groups()]
    assert len(backoff_seconds) == max_attempts - 1
    worst_case_seconds = max_attempts * (timeout_seconds + kill_after_seconds) + sum(
        backoff_seconds
    )
    assert worst_case_seconds == 1980
    assert worst_case_seconds < outer_minutes * 60


def test_playwright_install_evidence_is_always_uploaded_before_browser_tests() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    step = _step_body(
        workflow,
        "Upload Playwright install evidence",
        "Browser integration",
    )

    assert "if: always()" in step
    assert "uses: actions/upload-artifact@v4" in step
    assert "name: playwright-install-evidence" in step
    assert "path: ${{ runner.temp }}/playwright-chromium-install.log" in step
    assert "if-no-files-found: error" in step


def test_playwright_install_evidence_is_initialized_before_python_tests() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    start = workflow.index("      - name: Initialize Playwright install evidence\n")
    end = workflow.index("      - name: Python tests\n", start)
    step = workflow[start:end]

    assert "PLAYWRIGHT_INSTALL_LOG" in step
    assert ': > "$PLAYWRIGHT_INSTALL_LOG"' in step
    assert "event=playwright_install_evidence outcome=not_started" in step


def test_playwright_download_timeout_owns_each_logging_pipeline_and_keeps_retry_contract() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    step = _step_body(
        workflow,
        "Download Playwright Chromium",
        "Upload Playwright install evidence",
    )

    timeout = 'timeout --signal=TERM --kill-after=30s "${timeout_seconds}s"'
    child_shell = "bash -o pipefail -c '"
    pnpm_command = "pnpm --filter @mirror/web exec playwright install chromium 2>&1"

    assert "timeout-minutes: 35" in step
    assert "readonly max_attempts=3" in step
    assert "readonly -a backoff_seconds=(30 60)" in step
    assert "unset PLAYWRIGHT_DOWNLOAD_HOST PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST" in step
    assert timeout in step
    assert child_shell in step
    assert pnpm_command in step
    assert '| tee -a "$PLAYWRIGHT_INSTALL_LOG"' in step
    assert 'exit "${PIPESTATUS[0]}"' in step
    assert 'install_status="$?"' in step
    assert 'if [[ "$install_status" -eq 0 ]]; then' in step
    assert "exit 1" in step
    assert step.index(timeout) < step.index(child_shell) < step.index(pnpm_command)
