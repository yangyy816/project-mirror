# P2-M5/M7 Controlled Integration Checkpoint

## Status and authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-M7-INTEGRATION-01`
- `STATUS: READY_FOR_TRACKED_EVIDENCE`
- `BRANCH: codex/phase2-m5-m7-integration`
- `MERGE_COMMIT: 6a596a848f39c1a5e0248cf23ee35fbc38d6da36`
- `CANDIDATE_COMMIT: THIS_COMMIT`
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

## Protected-worktree evidence

The primary, protected M5 and independent P3-P7 worktrees remain untouched. Their branches, uncommitted changes,
`.tmp`/ACL directories, Codex configuration, `AGENTS.md`, `MEMORY.md` and OpenAPI working copies are not staged, copied,
cleaned, reset or adopted by this checkpoint.

## Next action

```text
commit candidate
-> normal non-force push
-> exact-SHA three-job Actions
-> inspect all eight artifacts
-> independent security and final reviews
-> Principal integration acceptance or bounded repair
```
