# P3–P7 D01-B Change Control 01 — Admission and Image Execution Authority Repair

## Decision status

```text
CHANGE_CONTROL_ID: P3_P7_D01_B_CC_01
TRACK: DEMO_PROTOTYPE
PLAN_VERSION: P3_P7_ALGORITHMIC_PROTOTYPE_PLATFORM_PLAN_V1_1
REJECTED_CANDIDATE: 4c84f25502486781c6a6613f9e0658406c4602ff
DECISION: ACCEPTED_FOR_BOUNDED_FORWARD_REMEDIATION
D01_B: REJECTED_REMEDIATION_REQUIRED
D01_C: CLOSED
FORMAL_PHASE_AUTHORITY: FALSE
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

The rejected candidate remains immutable history. Remediation is a new forward commit on the same Demo branch; it does
not reset, amend, rebase or conceal the rejected candidate. The branch-local revision remains
`demo_0001_p3_p7_core` because the candidate was not pushed or promoted and no non-disposable Demo database is an
accepted authority. Every validation database must be recreated from an empty isolated PostgreSQL instance.

## Findings that require repair

1. `demo_synthetic_identities` did not freeze the canonical formal Asset/QA snapshot and allowed a stale historical
   `ADMIT` row to authorize new evidence after a later `REVOKE`.
2. `demo_image_versions` stored shape-valid but unresolved plan/tool/verifier digest strings, omitted source/result SHA
   snapshots and permitted incomplete ImageVersion/VerificationResult half-edges.

Until both findings are implemented, tested on real PostgreSQL and independently reviewed:

```text
NO_EVIDENCE_LOSS: FAIL
NO_CAPABILITY_LOSS: NOT_REVALIDATED
NO_API_LOSS_FROM_PHYSICAL_MAPPING: NOT_REVALIDATED
NO_REBUILDABILITY_LOSS: NOT_REVALIDATED
NO_FORMAL_AUTHORITY_POLLUTION: PASS_FOR_REJECTED_DIFF_ONLY
R-DEMO-06: OPEN_BLOCKING_D01_B
```

## Frozen synthetic admission contract

Every `demo_synthetic_identities` row freezes:

```text
formal_synthetic_identity_id
formal_canonical_asset_id
formal_canonical_asset_sha256
formal_accepted_qa_run_id
formal_accepted_qa_snapshot_digest
admission_sequence
admission_action
admission_config_digest
supersedes_id
```

`formal_accepted_qa_snapshot_digest` uses domain `mirror.demo/FormalSyntheticQASnapshot/v1`. Its canonical JSON object
contains the immutable QA run fields, the approved policy identity/version/content digest, every measurement ordered by
`measurement_code` with `confidence * 10_000_000` as an integer, and every review ordered by `review_kind`. Storage
timestamps are excluded; authority timestamps use fixed-microsecond UTC. A snapshot is eligible only for a terminal
`PASSED` `CANONICAL_BASE` run, an approved policy, at least one measurement, no failed hard gate and all three mandatory
`adult_presentation`, `likeness_risk` and `license_rights` reviews with `PASSED` decisions.

Admission append is serialized by a formal-identity-scoped PostgreSQL advisory transaction lock. The first row must be
sequence 1 `ADMIT`; every successor must name the actual latest row, increment sequence by one and alternate action.
`supersedes_id` is unique. `ADMIT` must match the live immutable formal identity/Asset/QA snapshot. `REVOKE` copies the
predecessor snapshot exactly and remains appendable after the formal Asset has been tombstoned.

New observations and question pairs must use the current latest admission row, whose action is `ADMIT`, and must recheck
the frozen snapshot against the live formal authority. Historical `ADMIT` rows remain reconstructable evidence but are
not current eligibility authority. Concurrent evidence/revocation uses the same advisory lock, giving one deterministic
order rather than a stale check-then-insert race.

## Frozen image execution contract

`demo_image_versions` additionally freezes `source_asset_sha256` and `result_asset_sha256`; its
`result_asset_variant_id` is mandatory and must resolve the exact formal AssetVariant source/result pair in the
`demo_p3_p7_*` namespace.

```text
ORIGINAL:
  sequence = 0
  parent_version_id = NULL
  plan_digest = tool_run_digest = verifier_digest = NULL

EDITED | RESTORED | ROLLED_BACK:
  sequence > 0
  plan_digest, tool_run_digest and verifier_digest resolve to exact immutable rows
  verifier outcome = PASS

QUARANTINED:
  sequence > 0
  complete resolved lineage is still mandatory
  verifier outcome = FAIL | HUMAN_REVIEW
```

`demo_tool_runs` freezes `edit_operation_digest`, which must equal the referenced operation row. An execution Job
binding and JobAttempt may be shared by the ordered operations of one plan; uniqueness is
`(formal_job_attempt_id, edit_operation_id)`, not a single-column uniqueness claim.

`demo_verification_results.image_version_id` is mandatory and unique. ImageVersion and VerificationResult form a
commit-time, bidirectional edge. Creation uses a preallocated ImageVersion ID:

```text
persist RESULT EditPlan and ordered DemoEditOperation rows
→ create one edit_plan.execute binding and formal JobAttempt
→ execute one operation and persist Asset + AssetVariant + immutable ToolRun
→ preallocate image_version_id
→ compute VerificationResult payload/content digest using that ID
→ insert ImageVersion carrying plan/tool/verifier digests
→ insert VerificationResult referencing image_version_id
→ commit; deferred constraints validate the complete edge
```

Each plan operation produces one ImageVersion. Operation 0 consumes the plan input version; later operations consume the
previous operation's output, use the same execution binding/attempt and advance the image sequence by one. A later plan
may consume only the final PASS step of the preceding plan. `operation_specs[index]` must exactly match the persisted
operation engine/type/parameters/preserve/expected-effect object.

AcceptedVisualEpisode must resolve its entire root-to-leaf trajectory. Every derived ImageVersion must pass the complete
plan → operation → ToolRun → AssetVariant → verifier binding, the accepted leaf must be a final plan operation with PASS,
and the acceptance event, source/final Asset IDs and SHA snapshots must all match.

## Deferred validation and acyclicity

The ImageVersion `verifier_digest` references the unique VerificationResult `content_digest`; the VerificationResult
payload references the preallocated ImageVersion ID but never the ImageVersion digest. There is therefore no digest
cycle. Deferrable foreign keys and constraint triggers run at commit from both sides and reject an orphan ImageVersion,
an orphan VerificationResult, arbitrary/missing/cross-owner digests, ID/digest mismatch and invalid outcome/kind.

All Demo authority rows remain append-only. A missing digest cannot be inserted and patched later with `UPDATE`.

## Mandatory remediation verification

Real PostgreSQL tests must cover matching and mismatched admission snapshots, deterministic QA digest, legal
`ADMIT → REVOKE → ADMIT`, stale admission rejection, post-tombstone revoke, concurrent successor selection, ORIGINAL and
derived image shapes, arbitrary/missing/cross-owner lineage, source/result SHA and AssetVariant mismatch, plan operation
ordering/spec mismatch, shared execution attempt, half-edge commit failures, verifier outcome mapping and complete
AcceptedVisualEpisode traversal.

The complete migration lifecycle, ORM parity, all 27 Demo tables, formal DDL diff, populated downgrade, Alembic drift,
full API regression, Ruff, strict mypy, Gitleaks, private-locator scan and public repository visibility must be rerun for
the new candidate. Historical `24 PASS / 718 PASS` evidence remains labelled as rejected-candidate evidence only.

## Network and formal boundaries

```text
NETWORK_SEMANTICS: PUBLIC_INTERNET_EGRESS_DISABLED
ALL_NETWORK_DISABLED: FALSE
LOCALHOST_AND_DOCKER_INTERNAL_NETWORK: REQUIRED
D00_A_BOUNDED_ACQUISITION_DURING_REMEDIATION: Gitleaks v8.28.0 only
D00_A_GITLEAKS_SHA256: da6458e8864af553807de1c46a7a8eac0880bd6b99ba56288e87e86a45af884f
D00_A_PROXY_SCOPE: ACQUISITION_ONLY
PRODUCTION_PROVIDER_CALLS: 0
FORMAL_TABLE_DDL_CHANGE: FORBIDDEN
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
```

PostgreSQL, Redis, Celery, FastAPI, Next.js and private object storage remain valid local/internal network consumers.
Any core runtime attempt to use public internet must fail closed as `EXTERNAL_RUNTIME_DEPENDENCY_FOUND`. The Gitleaks
binary was acquired from the exact official v8.28.0 release plus its checksum manifest into Git-external private tool
storage. No proxy variable or acquired network capability entered a core validation process.

## Remediation outcome

```text
REMEDIATION_CANDIDATE: dd39b37f5cf9286be0153dd034737865ebf3e0cd
REMEDIATION_CANDIDATE_TREE: 13b2b09aa507194fa4a5da15cb1c81213dfb0f60
INDEPENDENT_SOL_IMPLEMENTATION_REVIEW: PASS
BLOCKING_FINDINGS: 0
NON_BLOCKING_FINDINGS: 0
D01_B_PRINCIPAL_ACCEPTANCE: TASK_ACCEPTED
D01_C: EXECUTION_READY
FORMAL_P3_P7_STATUS: UNCHANGED
PRODUCTION_RELEASE: NOT_AUTHORIZED
```

The rejected parent remains immutable negative evidence. Acceptance applies only to D01-B Demo persistence authority;
it does not accept D01-C implementation, D02–D12, formal P3–P7 or production release.
