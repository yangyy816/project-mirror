# P3–P7 D01-A Acceptance Evidence

## Candidate status

```text
TASK: D01-A — Worktree and Demo authority
TRACK: DEMO_PROTOTYPE
BASE_SHA: d134517fa97132b180a82c69c617b8f65d3b282e
BRANCH: codex/p3-p7-core-demo
STATUS: READY_FOR_INDEPENDENT_REVIEW
PRINCIPAL_TASK_ACCEPTANCE: NOT_DECIDED
D01_B: CLOSED
```

This checkpoint implements governance and entry boundaries only. It contains no migration, ORM, public Demo API, Web,
P3–P7 domain implementation or formal authority change.

## D00 entry authority

```text
D00_RESULT: GO
D00_REVIEW_PACKET_SHA256: a987dcec3580e2baa02cc8c783dd15a94804651e81d76b8081de6777b28539be
D00_PRINCIPAL_DECISION_SHA256: 5f7734a51ae1f761b36b7375578e16fb6c26c5fd6d274ef3aff708d43b3797ac
D00_A_ACQUISITION_COUNT: 0
D00_B_PUBLIC_INTERNET_EGRESS: DENIED
```

D00 retained localhost and Docker internal data plane. It authorizes this checkpoint only and does not stand in for
D02 pair QA or D03–D12 evidence.

## Files in candidate scope

New authority/evidence:

```text
docs/adr/ADR-050-p3-p7-algorithmic-prototype-platform-demo-track.md
docs/operations/P3_P7_DEMO_FAST_TRACK_CONTRACT.md
docs/operations/P3_P7_DEMO_RISK_REGISTER.md
docs/operations/P3_P7_PREEXISTING_WORKTREE_MANIFEST.md
docs/operations/P3_P7_PROTOTYPE_AGENT_ROUTING.md
docs/operations/P3_P7_D01_A_ACCEPTANCE.md
```

Bounded updates:

```text
.codex/config.toml
AGENTS.md
MEMORY.md
docs/operations/MODEL_ROUTING_POLICY.md
requirements.lock
```

The lock change is exactly `pip==26.1.2 -> pip==26.2.1`, replayed from source commit
`b179c193b3a719142139b6d42e5be0c22ef4b225`. The source commit also changed a generated-date comment; D01-A did not
replay that line and did not cherry-pick the commit.

## Worktree isolation result

```text
DEMO_WORKTREE_CLEAN_AT_ENTRY: PASS
DEMO_BRANCH_POINT_SHA: d134517fa97132b180a82c69c617b8f65d3b282e
BASE_SHA_EXACT: PASS
FORMAL_DIRTY_BYTES_COPIED: FALSE
PROTECTED_TMP_CONTENT_READ: FALSE
DEMO_TASK_FORMAL_WRITE_COUNT: 0
FORMAL_WORKTREE_UNCHANGED_BY_DEMO_TASK: PASS
```

The formal checkout advanced externally during D01-A from P2-M5 HEAD `fd64a313...` to P2-M7 HEAD `8816047a...`.
Tracked/untracked dirty path sets stayed unchanged and no Git operation was active. This evidence does not claim
literal formal HEAD stability; the exact before/after attribution is preserved in the manifest.

## Network and private-runtime result

Network semantics are frozen as:

```text
PUBLIC_INTERNET_EGRESS_DISABLED
NOT ALL_NETWORK_DISABLED
```

The D01-A official-worktree M4 replay:

- resolved the runtime only from the original D00 task receipt and Principal registry;
- verified the registered runtime manifest digest without printing or persisting its locator;
- loaded code from the Demo worktree `services/api/src` and ran its tracked adapter smoke;
- temporarily blocked the selected Python process's outbound traffic and removed the firewall rule in `finally`;
- performed no runtime/model/asset acquisition and made no Provider call;
- produced `changed_pixel_count=1895` and deterministic result digest
  `5f7868d5538134c3a85fdb91a02c02a0bcfbb009e8fd717298447e2c5bf8e0bb`.

```text
PRIVATE_RUNTIME_LOAD_FROM_OFFICIAL_WORKTREE: PASS
PUBLIC_EGRESS_RULE_FOR_OFFICIAL_WORKTREE_PROCESS: PASS
D01_A_FIREWALL_RULE_CLEANUP: PASS
```

Negative evidence is retained: the first replay used the D00 isolated interpreter and failed with missing `PIL`; it
did not acquire a package or produce a PASS, and its firewall rule was removed. The accepted retry reused existing
read-only host packages and the same checksum-bound private runtime.

## Agent routing and configuration

```text
LOGICAL_MAIN_PROCESS_ROLE: TERRA_HIGH_PRINCIPAL
REQUESTED_MODEL: gpt-5.6-terra
REQUESTED_REASONING_EFFORT: high
CURRENT_THREAD_MODEL_RUNTIME_VERIFICATION: NOT_EXPOSED
PROJECT_TOP_LEVEL_PRINCIPAL_OVERRIDE: ABSENT
DEFAULT_ACTIVE_SUBAGENTS: 1
MAX_ACTIVE_SUBAGENTS: 2
CAN_DELEGATE: false
```

Python 3.13 `tomllib` parsed the project config and all eleven base Agent definitions; IDs are unique and configured
models/efforts are within the accepted set. Current-session callable discovery exposed the eleven roles, and D00
successfully invoked bounded Sol and Luna contexts. No role definition changed in D01-A.

OpenAI's official configuration reference was fetched read-only outside the core offline window and confirms
`agents.max_concurrent_threads_per_session` counts spawned Agent threads while excluding the primary thread. Config is
therefore `2`. The WindowsApps Codex CLI remained ACL-denied even in the approved execution context, so an additional
CLI fresh-process smoke is `NOT_VERIFIED`; this is not converted into a runtime-model claim.

```text
TOML_PARSE: PASS
AGENT_COUNT: 11
UNIQUE_AGENT_IDS: PASS
CONCURRENCY_KEY_SEMANTICS: VERIFIED_FROM_OFFICIAL_OPENAI_DOCS
CURRENT_SESSION_ROLE_DISCOVERY: PASS
POST_EDIT_CODEX_CLI_FRESH_PROCESS_SMOKE: NOT_VERIFIED_ACL_DENIED
AGENT_CONFIG_VALIDATION: CONDITIONAL_WITH_EXPLICIT_NEGATIVE_EVIDENCE
```

## Validation evidence

```text
PRETTIER_TARGETED_MARKDOWN: PASS
TOML_PARSE_AND_INVARIANTS: PASS
GIT_DIFF_CHECK: PASS
PRODUCT_SCHEMA_API_WEB_DIFF: NONE
TRACKED_PRIVATE_LOCATOR_SCAN: PASS
GITLEAKS_8_28_0_DIRECTORY_SCAN: PASS
GITLEAKS_FINDINGS: 0
GITLEAKS_ARCHIVE_SHA256: da6458e8864af553807de1c46a7a8eac0880bd6b99ba56288e87e86a45af884f
GITLEAKS_TEMP_CLEANUP: PASS
```

Gitleaks was acquired only as ephemeral D01-A tooling from the official `gitleaks/gitleaks` v8.28.0 GitHub release,
outside D00-B. Its checksum was pre-read from the fixed official checksum manifest, the archive was verified before
execution, and no binary/artifact entered Git. The first archive attempt passed checksum/version but used an obsolete
`--source` flag; it produced no scan conclusion and cleaned its temporary directory. The corrected positional command
scanned approximately 5.70 MB and found no leaks.

Not run because this checkpoint changes no product/schema/API code: Python product suites, PostgreSQL migration
lifecycle, OpenAPI generation/drift, TypeScript build and Playwright. They remain mandatory in their owning checkpoints.

## Claims and remaining Gate

```text
D01_A_INDEPENDENT_REVIEW: NOT_VERIFIED
DEMO_CANDIDATE_COMMIT_SHA: NOT_CREATED
DEMO_WORKTREE_CLEAN_AFTER_CANDIDATE_COMMIT: NOT_VERIFIED
FIRST_PUSH_REPOSITORY_VISIBILITY: NOT_VERIFIED
FORMAL_MAINLINE_IMPACT: NONE_ATTRIBUTABLE_TO_DEMO_D01_A

D01_A: NOT_ACCEPTED
D01_B: CLOSED
D01_D12_IMPLEMENTATION: NOT_VERIFIED
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

An independent Sol High review must bind the candidate SHA and this evidence. Principal accepts or repairs D01-A only
after reviewing that report and rerunning affected checks.
