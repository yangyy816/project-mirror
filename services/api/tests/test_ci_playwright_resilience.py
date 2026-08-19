"""Static fail-closed checks for the Playwright acquisition workflow boundary."""

from pathlib import Path

WORKFLOW_PATH = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


def _step_body(workflow: str, step_name: str, next_step_name: str) -> str:
    start = workflow.index(f"      - name: {step_name}\n")
    end = workflow.index(f"      - name: {next_step_name}\n", start)
    return workflow[start:end]


def test_playwright_system_dependencies_timeout_owns_logging_pipeline() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    step = _step_body(
        workflow,
        "Install Playwright Chromium system dependencies",
        "Download Playwright Chromium",
    )

    timeout = 'timeout --signal=TERM --kill-after=30s "${timeout_seconds}s"'
    child_shell = "bash -o pipefail -c '"
    pnpm_command = "pnpm --filter @mirror/web exec playwright install-deps chromium 2>&1"

    assert "timeout-minutes: 12" in step
    assert timeout in step
    assert child_shell in step
    assert pnpm_command in step
    assert '| tee -a "$PLAYWRIGHT_INSTALL_LOG"' in step
    assert 'exit "${PIPESTATUS[0]}"' in step
    assert 'install_status="$?"' in step
    assert step.index(timeout) < step.index(child_shell) < step.index(pnpm_command)


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
