"""Static privacy checks for CI artifact logging."""

import re
import subprocess
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


def test_docker_log_artifact_is_sanitized_before_write() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    start = workflow.index("      - name: Capture container evidence\n")
    end = workflow.index("      - uses: actions/upload-artifact@v4\n", start)
    step = workflow[start:end]

    raw_command = "docker compose -f compose.yaml logs --no-color"
    assert raw_command in step
    assert "| sed -E" in step
    assert "<redacted-file-uri>" in step
    assert "<redacted-path>" in step
    assert "[^[:alnum:]_:/.-]" in step
    assert step.index(raw_command) < step.index("| sed -E") < step.index("> docker-compose.log")


def test_artifact_sanitizer_redacts_file_unix_windows_and_unc_paths() -> None:
    source = "\n".join(
        (
            "file:/etc/apt/apt-mirrors.txt",
            "installed to /var/lib/mirror-private/output.raw",
            "loaded (/usr/local/bin/tool)",
            "written=C:\\runner\\workspace\\artifact.log",
            "unc=\\\\server\\share\\artifact.log",
        )
    )
    result = subprocess.run(
        [
            "/bin/sed",
            "-E",
            "-e",
            "s#file:/[^[:space:]]+#<redacted-file-uri>#g",
            "-e",
            "s#(^|[^[:alnum:]_:/.-])/[A-Za-z0-9_./-]+#\\1<redacted-path>#g",
            "-e",
            "s#([A-Za-z]:\\\\|\\\\\\\\)[^[:space:]]+#<redacted-path>#g",
        ],
        input=source,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "<redacted-file-uri>" in result.stdout
    assert result.stdout.count("<redacted-path>") == 4
    assert re.search(r"file:/\S+|(^|\s)/|[A-Za-z]:\\|\\\\", result.stdout, re.MULTILINE) is None
