# P2-M5-R37 — Q02-R1 Post-Acceptance Next-Ready-Task Authority Repair

- `BOOTSTRAP_STATUS: OK`
- `TASK_ID: P2-M5-R37`
- `PREDECESSOR_CANDIDATE: 8d58413059705099b0749fdebf5896ce6dd105bf`
- `PREDECESSOR_FAILURE_GATE: POST_ACCEPTANCE_CURRENT_AUTHORITY_NEXT_TASK_CONFLICT`
- `AUTHORITY_CONDITION: EFFECTIVE_ONLY_AFTER_THIS_COMMIT_SAME_SHA_CI_ALL_EIGHT_ARTIFACT_CONTENT_CHECKS_SECURITY_PRIVACY_LICENSE_RESEARCH_SOL_AND_PRINCIPAL_ACCEPTANCE`

## Purpose and bounded disposition

Independent Sol High review found that the Q02-R1 true-EOF authority tail would still name its completed same-SHA gate as `NEXT_READY_TASK` after all Q02-R1 gates and Principal acceptance. That conflicts with the recorded rule that acceptance must enter `CC04-B-E01-A03` automatically without a post-acceptance state commit.

R37 is an L0, documentation-only current-authority repair. It neither changes the durable epoch-2 state nor rewrites the Q01 or first-Q02 failures. The Q02-R1 durable-bootstrap evidence, CI result, artifact inspection, and independent Security/Privacy/License/Research result remain preserved evidence; Q02-R1 has not received Principal acceptance.

## Exact scope

1. Add this repair record.
2. Append one complete canonical/mirror true-EOF authority map.
3. Mark Q02-R1 Principal acceptance as not granted because of the recorded Sol High authority defect.
4. Make the post-R37-acceptance `NEXT_READY_TASK` unambiguously `CC04-B-E01-A03`.

No private state, control file, ACL, ordinal, resource fact, generation specification content, image, decode, QA, screening, admission, holdout, dependency, provider, schema, migration, CI workflow, production, or real-user boundary changes.

## Preserved boundaries

- `image_gen`: prohibited.
- `CAL-REQ-002`: not consumed.
- Formal resource facts remain `1/1/0`, `31/31`, and global remaining `62`.
- A03 must still complete its own full same-SHA acceptance before any formal generation becomes dispatchable.
- Q01 and the first Q02 attempt remain failed historical evidence.

## Acceptance criteria

1. Changed paths are limited to this repair record and the canonical/mirror authority files.
2. The canonical/mirror tails have equal key set, order, and values, with no duplicate keys and true-EOF sentinels.
3. The predecessor Sol High failure is preserved, and the repaired post-acceptance next ready task is explicit without relying on reader inference.
4. No tracked local path, locator, Prompt, private byte, URL, credential, object key, or local user identity is introduced.
5. Scoped formatting, diff/allowlist/no-leak and authority checks, normal forward push, exact-SHA CI, eight-artifact inspection, independent Security/Privacy/License/Research review, independent Sol High review, and Principal acceptance pass.
