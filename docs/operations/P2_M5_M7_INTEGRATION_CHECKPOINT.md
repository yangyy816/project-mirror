# P2-M5/M7 Controlled Integration Checkpoint

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-M7-INTEGRATION-01`
- `STATUS: PASS_PENDING_ACCEPTANCE_CLOSURE_CI`
- `BRANCH: codex/phase2-m5-m7-integration`
- `MERGE_COMMIT: 6a596a848f39c1a5e0248cf23ee35fbc38d6da36`
- `CANDIDATE_COMMIT: fc336345e96a7f1627c681770b58659f8c2ebb05`
- `CANDIDATE_RUN: 32642007499_ATTEMPT_1`
- `ACCEPTANCE_CLOSURE_COMMIT: THIS_COMMIT`
- `INTEGRATION_CHECKPOINT: PASS_PENDING_ACCEPTANCE_CLOSURE_CI`
- `MIGRATION_HEAD: 0014_m5_eval_authority`
- `PUBLIC_API_CHANGE: NONE`
- `PRODUCTION_STATUS: NOT_DEPLOYED`

This checkpoint combines accepted M5 current authority with the frozen M7 implementation and history. It is not an M5,
M6, M8 or Phase 2 Gate and does not change any research result, execution authority or entry condition.

## Exact parents and predecessor evidence

| Line                     | Exact head                                 | Exact run                | Mandatory evidence                         |
| ------------------------ | ------------------------------------------ | ------------------------ | ------------------------------------------ |
| P2-M5 current authority  | `496d8061f4493b280d41ae33e4c8df78493e860c` | `32631572282`, attempt 1 | three jobs PASS; eight unexpired artifacts |
| P2-M7 frozen final state | `376d26d7ee5a4394ec167f26b087d0bb0ed7ceea` | `32640294672`, attempt 1 | three jobs PASS; eight unexpired artifacts |

The merge base is `fd64a313c3f2da534e3e019991f1cdb8352f5a74`. M5 has 19 branch-exclusive commits and M7 has 38. Their branch-exclusive changed-path sets have zero overlap. The merge is an ordinary two-parent merge: no rebase,
force push, amend, history rewrite, tag change or cherry-pick is used.

## Combined repository truth

- Phase 0 and Phase 1 remain `FROZEN`.
- P2-M1 through P2-M4 remain `FROZEN`.
- P2-M5 remains `EXECUTING`; `P2_MVR_V1_RESULT` remains `NOT_EVALUATED`.
- P2-M7 remains `FROZEN`; its final freeze evidence is not reused as an M5 Gate.
- P2-M6 remains `COMMITTED` and closed pending M5 technical Gate plus MVR PASS.
- P2-M8 remains `COMMITTED` and closed pending P2-M5 and P2-M6 frozen dependencies.
- P2-M9 remains `COMMITTED` and closed pending M1-M8 Gates.

The canonical M5 true-EOF authority remains unchanged:

```text
CC04_B_E01_RUNTIME_CAPABILITY_GATE: BLOCKED_SECURITY_PRIVACY_LICENSE
PRIVATE_OUTPUT_SINK_CAPABILITY: NOT_PROVEN
ACTUAL_HUMAN_DUPLICATE_REVIEW_CAPABILITY: NOT_PROVEN
OWNER_DECISION_STATUS: OWNER_DECISION_REQUIRED
CC04_B_EXECUTION: CLOSED_PENDING_OWNER_OR_EXTERNAL_RUNTIME_CAPABILITY_RESOLUTION
GENERATION_CALLS_EXECUTED: 0
RAW_OUTPUTS_CREATED: 0
REQUEST_ORDINAL_CONSUMED: NONE
```

The built-in image-generation Skill documents a default save under Codex-managed storage, but the exposed tool does not
provide the destination-bound private-sink handle, transcript-suppression contract, custody receipt or authenticated
actual-human pair-review evidence required by the accepted E01 contract. Skill availability therefore does not resolve
the blocker and no generation call is made.

## Scope and non-goals

This checkpoint may:

- merge the exact two accepted heads;
- synchronize current Milestone status and the autonomous execution log;
- run combined local and remote regression evidence; and
- record exact-SHA artifact and independent-review results in a later closure.

It must not:

- alter M5 evaluation, policy, threshold, cohort, runtime, custody or reviewer authority;
- generate, copy, discover or attach images or private evidence;
- select Owner Decision option A, B or C on the Owner's behalf;
- open M6, M8, production, real-user facial processing or QuestionBank release;
- merge or modify the independent P3-P7 demo line; or
- modify `MEMORY.md`, project/user Codex configuration, OpenAPI or protected temporary directories.

## Local validation

Completed on the combined merge tree:

- both exact parent ancestry checks: PASS;
- `git diff --check`: PASS;
- `python -m ruff format --check services`: PASS, 233 files;
- `python -m ruff check services`: PASS;
- strict mypy: PASS, 130 source files;
- fixed P2-M7 test slice: 68 PASS and 7 PostgreSQL-environment skips;
- Node lint and strict typecheck: PASS;
- Node tests: 54 PASS;
- Next.js production build: PASS.

The seven local skips are not accepted as zero-skip evidence. Docker/PostgreSQL lifecycle and browser execution were not
available in this local worktree. System Git `core.autocrlf=true` caused new-checkout CRLF byte differences, so local
repo-wide Prettier and byte-exact generated-contract checks are not authoritative. No bulk rewrite or tracked contract
change is permitted. Linux same-SHA CI must prove all mandatory Gates.

## Candidate Gate

Before this checkpoint may be accepted, its exact candidate SHA must prove:

1. `quality-and-integration`, `secret-scan` and `docker-validation` all PASS;
2. full Python, PostgreSQL migration lifecycle, Redis/Celery, TypeScript, Browser, contract drift, dependency/license,
   SBOM and Gitleaks Gates remain intact;
3. eight required artifacts are present, readable, unexpired and bound to the exact candidate SHA;
4. artifact members contain migration head `0014_m5_eval_authority`, zero mandatory skip for fixed evidence suites and
   no private path, image, Prompt, credential, signed URL, object key or Provider-payload leak;
5. independent Security/Privacy/Data/License review passes; and
6. independent Sol High final integration review passes before Principal acceptance.

A failed Gate produces a bounded integration repair. It cannot weaken M5/M7 evidence, reinterpret E01, skip Browser or
PostgreSQL, or use either parent run as combined-state acceptance.

## Candidate evidence and independent reviews

Candidate `fc336345e96a7f1627c681770b58659f8c2ebb05` completed GitHub Actions run `32642007499`, attempt 1.
`quality-and-integration`, `secret-scan` and `docker-validation` all succeeded on that exact SHA. The refreshed remote
integration ref points to the same candidate.

- Full Python reported 814 passes and one existing optional M4 private-runtime skip. The fixed P2-M7 evidence slice
  reported 75 passes and zero failure, error or skip; Phase 1 and P2-M1/M2/M3 reported 1/98/52/46 tests with zero skip.
- Ruff covered 233 files and strict mypy covered 130 source files. PostgreSQL completed full downgrade, upgrade,
  re-upgrade and Alembic check at `0014_m5_eval_authority`. TypeScript quality, 54 tests, production build, five
  Browser Integration tests and generated-contract drift all passed.
- Redis/Celery evidence contains only the expected successful task results. Docker evidence reports all five services
  running and healthy. Both dependency audits report no known vulnerabilities; license evidence contains 101 Python
  entries and 14 Node license groups / 480 package entries, and the CycloneDX 1.6 SBOM contains 105 components.
- Eight unexpired artifacts contain 12 fixed-relative members and bind the candidate SHA. Their IDs and GitHub archive
  digests are `9493901524` / `00e61f89...`, `9493898903` / `442d5516...`, `9493898656` / `65b75341...`,
  `9493898439` / `1ec07fac...`, `9493898214` / `fcbe69bb...`, `9493894730` / `3d1bcb2c...`, `9493869841` /
  `b8402f41...` and `9493848304` / `855d5005...`.
- Artifact scans found zero image extensions or image magic, private/runner absolute paths, credential assignments,
  signed URLs, Prompt fields, object-key fields or raw Provider payload fields. The exact task-owned inspection root
  was deleted after both reviewers completed, and its absence was verified.

The secret-scan evidence is recorded exactly: this run used Gitleaks `8.24.3` through the existing
`gitleaks/gitleaks-action@v2` workflow and scanned the one post-merge candidate commit, producing one SARIF run with zero
results. It is not represented as Gitleaks 8.28.0 or as a new full-history scan. Combined-tree coverage remains valid
because the separately accepted parent runs cover their histories, all 24 M5 and 41 M7 changed paths are byte-identical
between each accepted parent and merge `6a596a8`, their path sets have zero overlap, and the only post-merge changes are
the three governance documents scanned in this candidate run.

Independent Security/Privacy/Data/License review returned `PASS` with no bounded repair. Independent Sol High final
review returned `PASS_FOR_PRINCIPAL_ACCEPTANCE_CLOSURE`. Principal separately reviewed the merge graph, all 65 parent
path bindings, candidate diff, exact-SHA logs, artifacts, M5 true-EOF authority and both review reports. The candidate
satisfies the controlled integration Gate, subject only to this documentation-only acceptance closure receiving its
own same-SHA three-job CI and eight-artifact inspection.

This decision does not alter any Milestone state. P2-M5 remains `EXECUTING`; E01 remains
`BLOCKED_SECURITY_PRIVACY_LICENSE` with zero generation calls, raw outputs or consumed request ordinal; P2-M7 remains
`FROZEN`; and P2-M6/M8, production, real-user processing and QuestionBank release remain closed.

```text
INTEGRATION_CANDIDATE: PASS_AT_FC336345_RUN_32642007499_ATTEMPT_1
INTEGRATION_SECURITY_REVIEW: PASS
INTEGRATION_FINAL_REVIEW: PASS_FOR_PRINCIPAL_ACCEPTANCE_CLOSURE
INTEGRATION_CHECKPOINT: PASS_PENDING_ACCEPTANCE_CLOSURE_CI
MILESTONE_STATE_CHANGE: NONE
NEXT_ACTION: ACCEPTANCE_CLOSURE_SAME_SHA_CI
```

## Protected-worktree evidence

The primary, protected M5 and independent P3-P7 worktrees remain untouched. Their branches, uncommitted changes,
`.tmp`/ACL directories, Codex configuration, `AGENTS.md`, `MEMORY.md` and OpenAPI working copies are not staged, copied,
cleaned, reset or adopted by this checkpoint.

## Next action

```text
commit documentation-only acceptance closure
-> push with the exact integration-branch refspec
-> exact-SHA three-job Actions
-> inspect all eight artifacts
-> record final controlled-integration acceptance or bounded repair
```
