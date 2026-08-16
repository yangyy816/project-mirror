# P2-M1 Acceptance Evidence

## Candidate status

- Milestone: `P2-M1 — Domain, Provenance, Governance and Research Baseline`
- State: `EXECUTING`
- Local validation target: current working tree based on `fb0d6a4b67494d32b865d0eb170f43232c68efb9`
- Candidate commit SHA: `PENDING_PRINCIPAL_COMMIT`
- Same-SHA GitHub Actions evidence: `PENDING_PRINCIPAL_PUSH`

## Machine-readable evidence contract

The `mirror.p2-m1.ci-evidence/v1` artifact contains only:

- the full candidate commit SHA;
- the single Alembic head `0008_synth_dataset_foundation`;
- the SHA-256 digest of the authoritative OpenAPI document;
- aggregate P2-M1 JUnit counts, duration and zero-failure/error/skip status;
- aggregate PASS status for synthetic-only, dependency/model-artifact, Provider/network/SDK,
  production fail-closed and public-contract boundary checks.

The artifact excludes raw JUnit XML, repository paths, database rows, prompts, object keys,
URLs, images, Provider payloads, environment values and credentials.

## Local gate record

T07 local validation ran against the current worktree based on the recorded Phase 1 freeze
commit. The machine-readable sample intentionally binds that base commit because the Principal
has not yet created the candidate commit; it is generator evidence, not same-SHA acceptance
evidence. Remote candidate and acceptance closure results must be recorded by the Principal only
after the committed candidate SHA completes all three `project-gates` jobs.

| Gate                       | Result  | Evidence                                                                                                 |
| -------------------------- | ------- | -------------------------------------------------------------------------------------------------------- |
| Python format/lint/type    | PASS    | Ruff 142 files; strict mypy 90 source files                                                              |
| Python API/Worker tests    | PASS    | API 275; Worker 19; P2-M1 evidence 87; zero mandatory skip                                               |
| Migration lifecycle        | PASS    | isolated PostgreSQL fresh→`0007→0008→0007→0008`; `alembic check`                                         |
| TypeScript/contracts/build | PASS    | complete `pnpm check`; OpenAPI digest `8809c9c63c609cc270c211d3f8cca03f47d76243fa5aeb6304bb385653adfdb2` |
| Docker                     | PASS    | Compose config/build; five healthy services; three HTTP 200 responses; Celery ping                       |
| Supply chain               | PASS    | Python/Node audits; Python/Node licenses; Python SBOM; no dependency/model additions                     |
| Secret scan                | PASS    | Gitleaks 8.28.0 candidate snapshot and 63-commit full history; no leaks                                  |
| GitHub Actions             | PENDING | same-SHA three-job run                                                                                   |

The isolated migration and evidence databases were checked for zero active sessions and removed
after validation. Existing ACL-protected `.tmp` paths were not accessed or changed.

## Repair evidence

`P2-M1-R04` corrected one Worker test fixture that created production `Settings` without the new
synthetic storage field. With CI correctly setting `SYNTHETIC_STORAGE_PROVIDER=mock`, the fixture
inherited mock and failed at the production configuration gate before exercising its intended
LocalTaskRunner production rejection. The repair explicitly sets
`synthetic_storage_provider="disabled"` only in that production fixture. The targeted test and the
complete 19-test Worker suite pass with the CI mock environment; production code and fail-closed
semantics are unchanged.

`P2_M1_T07_LOCAL_GATE: PASS`
`P2_M1_T07_STATUS: EXECUTING`
