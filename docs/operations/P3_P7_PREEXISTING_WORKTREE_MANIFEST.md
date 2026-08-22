# P3–P7 Demo Pre-existing Worktree Manifest

## Capture authority

```text
MANIFEST_VERSION: p3-p7-demo-preexisting-worktree-v1
CAPTURED_AT_UTC: 2026-08-22T17:29:10Z
CAPTURE_PHASE: D01-A ENTRY
CAPTURE_METHOD: git object/status/operation metadata only
PROTECTED_TMP_CONTENT_READ: FALSE
PRIVATE_LOCATOR_RECORDED: FALSE
```

This tracked manifest is intentionally redacted to repository-relative paths and Git facts. It records other work so
the Demo task can preserve it; it does not claim ownership and does not copy any listed byte into the Demo branch.

## Formal worktree at D01-A entry

```text
FORMAL_WORKTREE: D:\p
FORMAL_BRANCH: codex/phase2-m5-failure-mechanism-isolation
FORMAL_HEAD: fd64a313c3f2da534e3e019991f1cdb8352f5a74
PLAN_TIME_FORMAL_HEAD_REFERENCE: b179c193b3a719142139b6d42e5be0c22ef4b225
FORMAL_HEAD_ADVANCED_SINCE_PLAN: TRUE
FIXED_DEMO_BASE_IS_FORMAL_HEAD_ANCESTOR: PASS
MERGE_BASE_WITH_DEMO_BASE: d134517fa97132b180a82c69c617b8f65d3b282e
```

### Pre-existing tracked modifications

```text
.codex/agents/pm-fast-worker.toml
.codex/agents/pm-luna-worker.toml
.codex/agents/pm-planner.toml
.codex/agents/pm-terra-high-worker.toml
.codex/config.toml
AGENTS.md
MEMORY.md
docs/operations/MODEL_ROUTING_POLICY.md
packages/contracts/openapi.json
```

### Pre-existing untracked paths

```text
.agents/
.codex/agents/pm-luna-explorer.toml
.codex/agents/pm-terra-worker.toml
.tmp/
```

The manifest does not enumerate `.agents/` or `.tmp/` contents. These paths belong to formal/concurrent work and are
outside Demo authority.

### Protected temporary namespace

```text
PROTECTED_PATH: .tmp/p1m6-unit/
OBSERVED_ACCESS: ACL_DENIED
CONTENTS_READ: FALSE
CONTENTS_COPIED: FALSE
```

The ACL denial is preserved as negative evidence. No workaround, permission change, enumeration or cleanup is allowed.

### Formal Git operations

```text
MERGE: FALSE
CHERRY_PICK: FALSE
REVERT: FALSE
BISECT: FALSE
REBASE_APPLY: FALSE
REBASE_MERGE: FALSE
```

### Concurrent formal head advance observed during D01-A

At `2026-08-22T17:44:44Z`, a separate formal task changed the formal checkout branch/HEAD while D01-A was editing only
the Demo worktree:

```text
FORMAL_BRANCH_AT_ENTRY: codex/phase2-m5-failure-mechanism-isolation
FORMAL_HEAD_AT_ENTRY: fd64a313c3f2da534e3e019991f1cdb8352f5a74
FORMAL_BRANCH_LATER_OBSERVED: codex/phase2-m7-internal-operations
FORMAL_HEAD_LATER_OBSERVED: 8816047a104cf9e4ee277b315ac9f7b13ab20f75
FORMAL_HEAD_CHANGED_EXTERNALLY: TRUE
FORMAL_TRACKED_DIRTY_PATH_SET_CHANGED: FALSE
FORMAL_UNTRACKED_PATH_SET_CHANGED: FALSE
FORMAL_GIT_OPERATION: NONE
FIXED_DEMO_BASE_IS_LATER_FORMAL_HEAD_ANCESTOR: PASS
DEMO_TASK_FORMAL_WRITE_COUNT: 0
```

Therefore a literal machine-wide `FORMAL_HEAD_UNCHANGED` claim is false. The checkpoint uses the narrower, auditable
Gate `FORMAL_WORKTREE_UNCHANGED_BY_DEMO_TASK`; the external advance is preserved rather than reverted or copied.

## Demo worktree at D01-A entry

```text
DEMO_WORKTREE: D:\p-p3-p7-core-demo
DEMO_BRANCH: codex/p3-p7-core-demo
DEMO_HEAD: d134517fa97132b180a82c69c617b8f65d3b282e
DEMO_BRANCH_POINT_SHA: d134517fa97132b180a82c69c617b8f65d3b282e
DEMO_TRACKED_MODIFICATIONS: NONE
DEMO_UNTRACKED_FILES: NONE
DEMO_GIT_OPERATION: NONE

DEMO_WORKTREE_CLEAN_AT_ENTRY: PASS
BASE_SHA_EXACT: PASS
FORMAL_DIRTY_BYTES_COPIED: FALSE
```

The D01-A governance edits and the bounded `pip==26.2.1` replay occur only after this entry capture.

## Running execution contexts

At capture time the Principal context was active and active sub-agent count was zero. Three D00 bounded contexts were
already completed and were not running: one Luna inventory, one Sol routing review and one Sol final architecture
review. Completed context text is not reproduced here; only its redacted accepted evidence is used.

```text
ACTIVE_PRINCIPAL_CONTEXTS: 1
ACTIVE_SUBAGENTS: 0
MAX_ACTIVE_SUBAGENTS: 2
D00_DOCKER_PROJECT: mirror-d00-d134517-01
D00_DOCKER_SERVICES_LAST_OBSERVED_HEALTHY: 5/5
```

Running Docker services are local feasibility evidence, not another Agent and not a formal service mutation.

## D01-A exit checks

These fields are completed only after implementation and validation:

```text
DEMO_WORKTREE_CLEAN_AFTER_CHECKPOINT_COMMIT: NOT_VERIFIED
FORMAL_WORKTREE_UNCHANGED_BY_DEMO_TASK: PASS
FORMAL_HEAD_UNCHANGED_DURING_D01_A: FAIL_EXTERNAL_ADVANCE_RECORDED
BASE_SHA_EXACT_AFTER_CHANGES: NOT_VERIFIED
PRIVATE_RUNTIME_LOAD_FROM_OFFICIAL_WORKTREE: PASS
SCOPED_DIFF: NOT_VERIFIED
D01_A_INDEPENDENT_REVIEW: NOT_VERIFIED
```

The official-worktree replay resolved the M4 handle only from the original D00 task receipt/registry, verified the
registered manifest digest, blocked the selected Python process's outbound network, and ran the tracked
`run_p2_m4_t05_adapter_smoke.py` from this Demo worktree. The first isolated-interpreter attempt failed closed because
`PIL` was absent; its temporary firewall rule was removed. The accepted retry reused already-present read-only packages,
performed no acquisition, produced 1,895 changed pixels and the same deterministic result digest as D00, and removed
its temporary firewall rule. No private locator or byte is recorded here.
