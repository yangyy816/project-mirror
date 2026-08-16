# P2-M1 T08 Security, Data and Phase-Boundary Review

## Candidate review

- Candidate: `a901337ca8e0ef1fc93e64638ef72abb56bc1d28`
- GitHub Actions: run `31930761620`; all three jobs passed
- Review mode: independent read-only
- Result: `FAIL`

The candidate passed synthetic-only, Provider isolation, production fail-closed, supply-chain,
OpenAPI, migration lifecycle and machine-readable CI evidence checks. The downloaded P2 evidence
bound the exact SHA and head `0008_synth_dataset_foundation`, reported 87 tests with zero
failures/errors/skips and five passing boundary scans; Gitleaks SARIF contained zero results.

## Mandatory findings

### P2-M1-R07 — database authority invariants

1. `0008` made `synthetic_identities.bank_version_id` nullable but did not reject new non-null
   values. Because the migration first requires zero existing identities, every post-`0008`
   identity is a P2 identity and must be bank-independent. A default `NULL` is not an invariant.
2. The authority trigger and ORM listener protected schema/version/content/digest but allowed an
   approval update to mutate authority identity evidence such as `id` or `created_at`.

R07 must add PostgreSQL and ORM enforcement plus negative real-PostgreSQL tests while preserving a
legal DRAFT→APPROVED transition and the existing revision identifier.

### P2-M1-R08 — canonical domain fail-closed

The exported frozen `CanonicalPolicy` dataclass could be constructed directly with an invalid
version, non-canonical content or arbitrary digest, bypassing `create()` and `validate_external()`.
R08 must ensure every normal construction path validates kind, version, canonical object JSON and
the schema/version/content digest envelope without echoing submitted content.

## Checks that passed

- no dependency manifest, OpenAPI, route or public Web contract change;
- no image, model, weight, MediaPipe, OpenCV or imagededup addition;
- Provider contracts expose no arbitrary URL, object key, SDK type, plaintext Prompt or User ID;
- Tencent candidates and production Mock generation/Vision/synthetic storage fail closed;
- internal synthetic storage namespace is separate from user storage;
- no P3 or real-user facial processing authority;
- `0008` downgrade blocks destructive rollback when P2 authority/data exists;
- machine-readable P2/Phase 1 evidence and zero-result SARIF are exact-SHA artifacts.

MediaPipe/OpenCV upstream facts, model artifacts, live Provider terms and external benchmarks are
`NOT VERIFIED` by T08 and remain correctly outside M1.

`P2_M1_T08_REVIEW: FAIL`

## Repair re-review

- `P2-M1-R07` adds a PostgreSQL check and matching ORM guard that reject every non-null
  `SyntheticIdentity.bank_version_id`; it also makes authority `id` and `created_at` immutable in
  both the PostgreSQL trigger and ORM listener without weakening the legal DRAFT→APPROVED path.
- `P2-M1-R08` makes `CanonicalPolicy.__post_init__` validate kind, version, exact canonical object
  JSON and the schema/version/content SHA-256 envelope, so normal direct construction fails closed.
- Principal independently reviewed the diffs and ran 32 domain tests plus 10 isolated real-
  PostgreSQL migration/invariant tests. The PostgreSQL run covered `0007→0008→0007→0008`,
  `alembic check`, DB/ORM negative cases and removal of the exact isolated test database. Scoped
  Ruff, strict mypy and `git diff --check` passed.
- No public API, dependency, model artifact, Provider network path, P1 migration or P1 production
  implementation changed.

The repair working tree passes the original T08 findings. Final M1 acceptance still requires a new
committed SHA and all three same-SHA GitHub Actions jobs; this local re-review does not reuse the
pre-repair candidate run as repair evidence.

`P2_M1_R07_TASK_ACCEPTED: PASS`

`P2_M1_R08_TASK_ACCEPTED: PASS`

`P2_M1_T08_REPAIR_REVIEW: PASS`

The repair candidate `9f3ca343223478f60a8eb0aed1b6d2342235f497` completed GitHub Actions run
`31932052115` with all three jobs passing. The downloaded P2 evidence reports migration head
`0008_synth_dataset_foundation`, the unchanged OpenAPI digest, 94 tests with zero
failures/errors/skips and all five boundary classes passing. Retained Phase 1 evidence binds the
same SHA; Docker evidence is readable and Gitleaks SARIF contains zero results.

`P2_M1_T08_FINAL_STATUS: PASS`
