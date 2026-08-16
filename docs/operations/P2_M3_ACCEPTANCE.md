# P2-M3 Acceptance Evidence

## Status

- Milestone: `P2-M3 — Synthetic Normalization and Base Identity QA`
- State: `EXECUTING`
- Frozen entry: `0b579ebdb1c2a63936225bc59a4b0ca780544df2`
- Planned migration: `0010_synthetic_asset_qa`
- Public API change: none
- Vision candidate Gate: `EXTERNAL_VALIDATION_REQUIRED`
- Real-user facial processing: prohibited

## Mandatory evidence matrix

| Gate                      | Required evidence                                                          | Status      |
| ------------------------- | -------------------------------------------------------------------------- | ----------- |
| M2 authority preservation | no GenerationItem/raw/generation evidence rewrite                          | T02 PASS    |
| Migration                 | fresh and `0009→0010→0009→0010`, drift zero                                | T02 PASS    |
| Normalization             | bounded decode, sanitation, canonical encode, second decode, checksum      | T03 PASS    |
| Namespace                 | normalized private namespace separate from raw/user assets                 | T03 PASS    |
| Immutability              | Asset/record/measurement/review/identity lineage cannot mutate/delete      | T02 PASS    |
| QA                        | versioned run, typed measurements, reason codes and hard-gate evaluator    | T04 PASS    |
| Adult policy              | explicit review contract; ambiguous/minor-looking reject; no age estimate  | T04 PARTIAL |
| Vision                    | approved exact package/model/data/license + controlled benchmark           | PENDING     |
| Identity                  | one QA-passed canonical Asset creates at most one identity transactionally | T05 PASS    |
| Synthetic-only            | no User relation, real-person fixture, scraping or sensitive classifier    | T02 PASS    |
| Recovery                  | duplicate delivery, lease expiry, blob-before-commit and cleanup race      | T05 PASS    |
| Contracts                 | OpenAPI/generated TypeScript unchanged                                     | T02 PASS    |
| Supply chain              | Pillow unchanged; every new package/model separately approved              | T02 PASS    |
| Full Gate                 | Python/TS/PG/Redis/Celery/Docker/Gitleaks/SBOM/same-SHA Actions            | PENDING     |
| Final review              | independent security and final reviewer acceptance                         | PENDING     |

## Bounded native validation

The existing eight P2-M2-V01 source files may be reused from private storage after checksum and
source-evidence reconciliation. They are not regenerated merely to exercise M3. Requested
`1024×1024 PNG` and observed `1254×1254 PNG` remain distinct facts.

The M3 validation sequence is:

1. `P2-M3-V01`: normalize all eight admitted raw objects without resampling to the requested shape;
   verify sanitation, canonical output, second decode, namespace, checksum and no tracked binary.
2. `P2-M3-V02`: after Vision candidate approval, run face/pose/visibility/landmark measurement,
   repeatability and negative controls under a preregistered QAPolicy.
3. Explicit operator review records clearly-adult presentation, obvious text/watermark/background,
   likeness risk and rights scope without overriding any automatic hard failure.
4. Register identities only for assets that satisfy every required gate. A rejected asset remains
   immutable evidence and is never silently replaced.

These eight assets validate the pipeline; they are not final coverage, diversity, transform,
QuestionBank or questionnaire evidence.

## T03 deterministic normalization evidence

- `SyntheticNormalizationService` preserves M2 raw authority, verifies inspect metadata plus the
  streamed byte count/checksum, reuses the pinned `image-sanitizer-v1`, and creates an immutable
  internal synthetic `Asset` only after canonicalization and normalized storage admission.
- normalized storage uses `internal-synthetic/v1/normalized`; its opaque reference is derived from
  the immutable record ID and normalizer config digest. Raw, normalized and user namespaces remain
  disjoint.
- all database paths use source-object then synthetic-record lock order. A concurrent duplicate is
  idempotent; a blob stored before database commit is reused; deterministic content/tamper/conflict
  failures are terminal; a transient store failure leaves `NORMALIZING` recoverable.
- Linux targeted evidence: 25 sanitizer/raw/normalized/0010/concurrency/recovery tests passed with
  zero skip. Full API/Worker regression: 366 tests, zero failures, zero errors and three pre-existing
  Celery round-trip skips because the isolated run did not start an external worker; these skips are
  not T03 mandatory evidence and remain covered by the later full CI Gate.
- Windows and Linux produced the same canonical JPEG checksum
  `f55764d4e734d3d465707df1327826395f3ca3972c40601c1477f3cb8c52a495`, byte size `694`,
  dimensions `64×64`, and config digest
  `5ebe5ea3e9b0e5c8ad86b93166e38f11da7bdcd76a7a2801aadd0f30e32f81de`. Input PNG bytes differed
  by platform compression, while canonical output remained exact.
- complete Linux Ruff format/lint and strict mypy passed; `pnpm.cmd contracts:check` passed; no
  dependency, model/weight, public API, OpenAPI/generated TypeScript or real-person fixture changed.

T03 does not execute private V01 source normalization. That bounded evidence remains `P2-M3-V01`
and must reconcile all eight private checksums before use.

## T03 same-SHA remote evidence

- Checkpoint `9856c235432fb580836480cfaee56c21e8c58c1b` was pushed to
  `codex/phase2-m3-normalization-base-qa` and run `31965014695` completed successfully.
- `quality-and-integration`, `secret-scan` and `docker-validation` all passed on that exact SHA.
  Python quality/tests, the PostgreSQL migration lifecycle, Redis/Celery integration, TypeScript
  quality/build, browser integration, contract drift, dependency/license audit and SBOM steps all
  succeeded.
- Phase 1, P2-M1 and P2-M2 regression evidence artifacts, Docker evidence, project audit evidence
  and Gitleaks SARIF were present and exact-SHA bound. This checkpoint proves T03 regression safety;
  it is not the final `mirror.p2-m3.ci-evidence/v1` required by T07.

## T04 QA contract and R01 evidence

- The Vision port accepts only bounded canonical-JPEG `NormalizedSyntheticImagePayload` with an
  opaque normalized Asset reference and content-matching SHA-256. Raw generation payloads, User
  Assets, URLs, object keys, SDK types and network locations are not representable on this path;
  the Mock remains deterministic and zero-network, while unverified candidates remain fail closed.
- `SyntheticQAService` persists typed measurements and explicit operator reviews into the existing
  append-only `0010` authority. Execution `FAILED` remains distinct from content `REJECTED`.
- `P2-M3-R01` removed caller-supplied finalization requirements. Finalization now loads the exact
  QARun-bound `APPROVED` QAPolicy, validates its canonical digest and closed
  `QAPolicyDefinition/v1` grammar, and matches hard-gate classification plus algorithm/version.
  Missing, unknown, unsupported, malformed, `NOT_APPLICABLE` or mismatched required evidence fails
  closed; human review cannot erase an automatic hard failure.
- Principal verification: Ruff format/lint passed; strict mypy passed for 96 sources; 12 focused
  unit/provider tests passed; contract drift remained zero. A fresh isolated PostgreSQL 17.6 was
  migrated through `0010`; the migration-backed async service test passed twice consecutively in
  Linux, proving deterministic replay. The temporary database was removed and the original five
  Compose services remained healthy.
- T04 does not approve a real Vision candidate, perform adult/likeness/license review on V01 assets,
  register an identity or satisfy T06/T07. Those gates remain pending.

## P2-M3-R02 frozen M2 boundary regression repair

- The failed `quality-and-integration` job in run `31966322329` was caused by the frozen M2
  regression test recursively scanning every later `synthetic_dataset` module. The new M3
  normalization and QA modules therefore supplied `SyntheticQARun` to an M2-only forbidden-symbol
  assertion even though no M2 implementation crossed into M3.
- `P2-M3-R02` keeps the existing broad zero-network and redacted-logging scan intact, but fixes the
  M2 phase-boundary scan to the concrete M2 generation, prompt, raw-storage and Worker module set.
  A regression assertion proves that present M3 normalization/QA modules are non-empty and disjoint
  from that frozen M2 source set.
- The four focused M2 security-boundary tests pass locally; Ruff format/lint and `git diff --check`
  also pass. The wider evidence tests require Linux CI because the known Windows pytest temporary
  directory ACL fault recurred.
- Repair commit `d37f61b253c2240478d72aacedd167ede6d96eaa` completed same-SHA run `31966877634`.
  `quality-and-integration`, `secret-scan` and `docker-validation` all passed, including the original
  P2-M2 deterministic integration and boundary evidence step. Phase 1, P2-M1, P2-M2, Docker,
  project-audit and zero-result Gitleaks artifacts were present. `P2-M3-R02` is accepted.

## T05 Worker orchestration and P2-M3-R03 evidence

- Normalization and QA task messages are closed, reference-only schemas containing only the
  record/run ID, deterministic Job ID, request ID and schema version. `Job`/`JobAttempt` remain an
  empty-payload execution envelope; no image bytes, Prompt, policy payload, storage location, URL or
  Provider SDK type enters Celery.
- The Celery-independent application service schedules, leases, retries and reconciles M3 work;
  Celery routes normalization/QA to `mirror.synthetic` and reconciliation to
  `mirror.maintenance`. Production still rejects local synthetic storage and no public API or CLI
  was added.
- Canonical identity registration revalidates the approved policy and all append-only hard-gate
  evidence under PostgreSQL locks. Concurrent registration creates one identity, and the existing
  `0010` trigger atomically advances the record to `IDENTITY_REGISTERED`.
- Principal review rejected the initial Worker PASS and opened `P2-M3-R03`: reserve used
  `Job → record/run` while completion used `record/run → Job`; a crash after QA finalization also
  left `QA_PASSED` permanently unreconciled, and retry exhaustion terminalized only the Job.
  R03 now uses domain-authority-before-envelope lock order, reconciles `QA_PASSED` records until
  identity registration, and atomically moves exhausted normalization/QA work to
  `NORMALIZATION_FAILED`/`QA_FAILED` with a failed final attempt. A fifth delivery is a no-op.
- Fresh Linux targeted evidence passed: five PostgreSQL normalization/QA/concurrency/recovery tests,
  one real Redis/Celery queue test and two Worker adapter tests. A fresh full API/Worker suite with
  PostgreSQL 17.6, Redis 8.2.1 and an external Celery Worker passed with zero failures.
  `alembic check` reported no operations; Ruff covered 178 files, strict mypy covered 110 sources,
  contract drift and `git diff --check` passed. All exact T05/R03 temporary containers and private
  test directories were removed.
- T05 and R03 do not approve a Vision candidate, provide V02 calibration or satisfy T06–T08. M3
  remains `EXECUTING` and M4 entry remains closed.
- Candidate `5a726fc6348ab253b98e945348cfeac4b835a832` completed same-SHA run `31968433284`.
  `quality-and-integration`, `secret-scan` and `docker-validation` all passed. Phase 1, P2-M1,
  P2-M2, Docker, project-audit and zero-result Gitleaks artifacts were present. Principal accepts
  T05 and R03; this is not the final T07 M3 evidence Gate.

## T06 Vision candidate supply-chain Gate

- Exact MediaPipe source candidate remains `v0.10.35` at commit
  `f8ef212d5c962c0e853db7e59d217056b187084b`; Windows and Linux wheel SHA-256 values are recorded,
  but wheel contents and the native/transitive dependency chain have not been acquired or audited.
- The Principal read and rendered all pages of the official BlazeFace Short Range, Face Mesh V2 and
  Blendshape V2 model cards. Each model card explicitly states Apache-2.0. Their training/evaluation
  data descriptions are high level and do not close per-dataset rights, territory, deletion or
  redistribution evidence.
- GCS metadata fixes the Face Landmarker bundle at generation `1683136941468629`, size `3758596`,
  MD5 `b0e7274907a1644404fef66b28dd6d85` and CRC32C `2FSEdQ==`; upstream publishes no SHA-256.
- No wheel, package or `.task` artifact was downloaded, installed or executed. Explicit artifact
  acquisition authority is required before checksum, package notice/SBOM, Python 3.13, zero-network,
  platform and eight-asset calibration evidence can be produced.
- T06 therefore returns the protocol-defined evidence-backed blocker without weakening the Gate.
  T07/T08 and M4 entry remain closed.
- `docs/research/P2_M3_V02_VISION_CALIBRATION_PROTOCOL.md` now freezes the exact `0.10.35` candidate,
  artifact manifest, four-stage audit, V01 calibration/holdout split, negative controls and
  policy-freeze-before-holdout rule. This removes planning ambiguity but does not authorize a
  download, install, model run or threshold.
- PyPI `1.0.1` was rejected for this PoC because it retains the same unpinned dependency families and
  missing Python/license metadata, substantially enlarges both target wheels and introduces a
  GitHub/PyPI version mapping mismatch without closing any T06 blocker.

`P2_M3_T06_STATUS: BLOCKED`

## Deferred production boundary

`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER` remains `OPEN`. M3 synthetic research does not approve a
runtime image-generation Provider, real-user Vision processing, production QuestionBank or public
release. Codex native provenance remains `PROVENANCE_ONLY` and unknown facts remain `NULL`.

`P2_M3_LOCAL_GATE: PENDING`

`P2_M3_T03_REMOTE_CI: PASS`

`P2_M3_REMOTE_CI: PENDING_FINAL_T07`

`P2_M3_STATE: EXECUTING`

`P2_M4_ENTRY: CLOSED`
