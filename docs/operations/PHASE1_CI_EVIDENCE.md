# Phase 1 CI Evidence

`phase1-ci-evidence.json` is the machine-readable acceptance artifact for the P1-M6
integration Gate. The `quality-and-integration` job creates it only after the explicit
Phase 1 vertical lifecycle test and contract regeneration drift check pass.

The artifact uses schema `mirror.phase1.ci-evidence/v1` and contains only allowlisted
fields:

- the full commit SHA supplied by GitHub Actions;
- the single verified Alembic head, expected to be
  `0007_account_quarantine_evidence` for the Phase 1 candidate;
- the path and SHA-256 digest of the authoritative OpenAPI document;
- aggregate pass, failure, error, skip and duration values for the named Phase 1
  vertical lifecycle test.

Generation fails when an input is absent or empty, the SHA is not a full hexadecimal
commit, the migration output has zero or multiple heads, the OpenAPI document is
invalid, the required vertical test is absent, or any test is failed, errored or skipped.
The artifact deliberately excludes raw JUnit output, environment values, database
content, logs, URLs, object keys, image bytes and Provider payloads.

Local generation uses only synthetic test output and a real repository commit SHA:

```powershell
python -m pytest services/worker/tests/test_phase1_vertical.py `
  --junitxml=phase1-integration-results.xml
python -m alembic -c services/api/alembic.ini heads | `
  Set-Content -Encoding utf8 phase1-migration-head.txt
$commitSha = git rev-parse HEAD
python -m mirror_api.scripts.phase1_ci_evidence `
  --commit-sha $commitSha `
  --migration-head-file phase1-migration-head.txt `
  --expected-migration-head 0007_account_quarantine_evidence `
  --openapi packages/contracts/openapi.json `
  --test-results phase1-integration-results.xml `
  --output phase1-ci-evidence.json
```

The generated files are transient CI evidence and must not be committed.
