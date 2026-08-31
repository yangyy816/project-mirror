# P2-M5-R58 — CC08-A builder network and root-chain security repair

## Bounded authority

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R58`
- `OWNER_DIRECTIVE_ID: OD-P2-M5-CC08-A-SECURITY-REPAIR-AND-AUTO-ADVANCE-001`
- `BASELINE_SHA: 95bd90253ac96489ab321a4d7cae900ec495529a`
- `CHANGE_CLASS: BOUNDED_CC08_A_SECURITY_REPAIR`
- `STATUS: LOCAL_PASS_PENDING_TRACKED_GATES`

## Objective and scope

R58 closes only the two mandatory findings that denied Principal acceptance of
the CC08-A predecessor candidate: executable per-`RUN` network isolation plus a
digest-bound structured Docker build invocation, and no-follow validation of
the authorized parent/ancestor/root chain throughout create, read, traversal,
seal and fresh-process recovery.

The old candidate, its successful CI/artifacts and its failed Security review
remain immutable history. R58 is a normal forward descendant and creates a new
builder identity. It does not relabel either old Linux image.

## Executable invariants

- Dockerfile version:
  `p2-m5-cc08-builder-dockerfile-v2-run-network-none`.
- Locked invocation version:
  `p2-m5-cc08-builder-invocation-v2-run-network-none`.
- Every executable Dockerfile `RUN` uses `--network=none`; remote `ADD`, network
  acquisition commands, non-LF bytes and an unbound external frontend are
  rejected.
- The structured argv binds the exact Docker executable, `build`, Dockerfile,
  context, task root, output tag, `--network=none`, `--pull=false`,
  `--no-cache`, `--provenance=false`, base authority and input-authority digest.
- Base-image acquisition remains separately classified as bounded public
  acquisition or a preloaded exact digest. R58 does not claim the complete
  Docker build is offline.
- Root-chain verification uses lexical containment before content access and
  `lstat`/no-follow on every component. Windows reparse points and POSIX mount
  or special traversal fail closed. A create-once root marker plus device/inode
  identity detects post-create, pre-seal and fresh-process replacement without
  recording a locator in tracked evidence.
- Errors and tracked evidence do not contain private roots, entry names,
  Prompt, image bytes, model bytes or credentials.

## Frozen non-goals

No runtime feature, model, source commit, patch, Bazel/OpenCV authority,
generation assignment, Prompt, QA threshold, resource limit, schema,
migration, OpenAPI, dependency, workflow, M6 state, imagegen, canary decode or
M3 change is authorized.

## Acceptance

Acceptance requires focused positive/negative tests, full governance and local
regression, canonical LF, exact changed-path allowlist, staged Gitleaks and
private-pattern scans, canonical/mirror true-EOF equality, same-SHA three-job
CI, eight artifact-family content checks, independent Security/Privacy/License/
Research review, Sol High final review and Principal acceptance.

After acceptance the sole successor is read from the accepted CC08 contract:

`P2-M5-CC08-B_BUILD_AND_FREEZE_NEW_TWO_PLATFORM_RUNTIME_MANIFEST`.

No post-acceptance synchronization commit is required. `CAL-REQ-004` remains
`OUTPUT_REGISTERED_PRE_DECODE`; generation, decode and M3 calls remain zero.
