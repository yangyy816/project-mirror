# P2-M7-R02 — T01 evidence-state reconciliation

## Problem

After `P2-M7-R01` passed same-SHA CI, authenticated artifact-content inspection and independent review, the durable
protocol and acceptance labels still described the earlier unauthenticated inspection as the current blocker. That
state would incorrectly keep T02 closed despite the required evidence being available.

## Repair

- Record the exact `78c6370` / run `32588923032` three-job evidence.
- Record content-level inspection as Principal evidence without exposing archive paths, object keys, signed URLs,
  image bytes, Prompt content, raw Provider payloads or credentials.
- Distinguish the expected `if: failure()` Playwright failure-evidence upload skip from a mandatory test or evidence
  skip.
- Reconcile T01/R01 to accepted and advance only P2-M7 to `EXECUTION_READY` with T02 authorized.

## Preserved boundaries

- No code, schema, migration, dependency, model artifact, Provider, public API, real-person input or private input is
  added.
- M5 CC04-A fresh-study execution and P2-M6 release/revoke remain closed.
- P2-M7 Gate remains `NOT_EVALUATED`; production CLI enablement remains `NOT_DEPLOYED`.

## Required validation

- scoped Markdown formatting and `git diff --check`;
- status/authority, public-contract and dependency negative scans;
- recheck the exact GitHub run/jobs/artifact metadata and compare the recorded SHA;
- confirm the independent review report contains no unresolved finding.

`P2_M7_R02: READY_FOR_TRACKED_EVIDENCE`
