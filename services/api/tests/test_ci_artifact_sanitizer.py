"""Regression tests for path-free CI artifact projections."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SANITIZER = ROOT / "scripts" / "ci_artifact_sanitizer.mjs"


def test_ci_artifact_sanitizer_projects_allowlisted_license_and_compose_fields(
    tmp_path: Path,
) -> None:
    licenses_input = tmp_path / "node-licenses-raw.json"
    docker_input = tmp_path / "docker-compose-raw.json"
    licenses_output = tmp_path / "node-license-evidence.json"
    docker_output = tmp_path / "docker-compose-evidence.json"
    licenses_input.write_text(
        json.dumps(
            {
                "MIT": [
                    {
                        "name": "@mirror/example",
                        "versions": ["1.2.3"],
                        "paths": ["/home/runner/work/project/node_modules/example"],
                        "homepage": "https://example.invalid",
                        "description": "untrusted raw metadata",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    docker_input.write_text(
        json.dumps(
            [
                {
                    "Service": "api",
                    "State": "running",
                    "Health": "healthy",
                    "ExitCode": 0,
                    "Command": "/home/runner/private command",
                }
            ]
        ),
        encoding="utf-8",
    )

    node = shutil.which("node")
    assert node is not None
    subprocess.run(  # noqa: S603
        [
            node,
            str(SANITIZER),
            "--licenses-input",
            str(licenses_input),
            "--licenses-output",
            str(licenses_output),
            "--docker-input",
            str(docker_input),
            "--docker-output",
            str(docker_output),
        ],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    artifacts = licenses_output.read_text(encoding="utf-8") + docker_output.read_text(
        encoding="utf-8"
    )
    assert "/home/runner" not in artifacts
    assert "https://" not in artifacts
    assert "untrusted raw metadata" not in artifacts
    assert json.loads(licenses_output.read_text(encoding="utf-8")) == {
        "schema_version": "mirror.ci.node-license-summary/v1",
        "license_groups": [
            {"license": "MIT", "packages": [{"name": "@mirror/example", "versions": ["1.2.3"]}]}
        ],
    }
    assert json.loads(docker_output.read_text(encoding="utf-8")) == {
        "schema_version": "mirror.ci.compose-status/v1",
        "containers": [{"service": "api", "state": "running", "health": "healthy", "exit_code": 0}],
    }
