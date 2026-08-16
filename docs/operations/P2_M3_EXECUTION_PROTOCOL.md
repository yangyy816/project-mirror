# P2-M3 Execution Protocol

## Authority and state

- Milestone: `P2-M3 — Synthetic Normalization and Base Identity QA`
- Entry baseline: P2-M2 freeze-state `0b579ebdb1c2a63936225bc59a4b0ca780544df2`
- Entry run: `31958786882`; all three jobs passed with exact-SHA artifacts
- Branch: `codex/phase2-m3-normalization-base-qa`
- State: `EXECUTING`
- Architecture authority: ADR-021–027
- Scope: synthetic-only normalization, base QA evidence and canonical identity registration
- Public API impact: none
- Production image-generation Provider: `NOT_CONFIGURED`; generation remains `FAIL_CLOSED`
- Vision candidate: `EXTERNAL_VALIDATION_REQUIRED`

Project Owner change control explicitly opens M3 for synthetic research and permits the bounded
P2-M2-V01 Codex-native raw assets to be used for Pillow normalization, metadata sanitation, image
safety, synthetic Vision QA and QA policy calibration. It does not authorize real user photographs,
runtime Codex invocation, ChatGPT Web automation, unofficial endpoints or production Provider
approval.

## Frozen boundary

M3 implements this chain only:

```text
immutable M2 raw source
→ deterministic normalization
→ private normalized namespace
→ immutable synthetic Asset + SyntheticAssetRecord
→ versioned QARun / Measurement / Review evidence
→ atomic bank-independent SyntheticIdentity registration
```

M2 `GenerationItem` remains terminal and immutable. M3 state belongs to `SyntheticAssetRecord`.
Raw source, normalized Asset, QA evidence and identity are separate layers. No failure or review may
rewrite prior evidence.

M3 explicitly excludes:

- real user photos, User references, SelfState and BaselineFaceModel;
- variant generation, isolation, duplicate/diversity and QuestionBank release;
- public/internal HTTP endpoints, admin Web and the M7 CLI;
- age estimation, beauty scoring, sensitive inference, celebrity similarity or race-based routing;
- unapproved dependency, SDK, model, weight, dataset or live Provider call;
- dedicated coverage-pack/style-pack persistence before later rolling-wave authority.

## Data and migration contract

The sole planned migration is `0010_synthetic_asset_qa` and must not modify `0001`–`0009`.

It establishes:

- `SyntheticAssetRecord`: one raw source, one normalized Asset, immutable lineage/config/digest and
  a monotonic normalization/QA/registration lifecycle;
- `SyntheticQARun`: one normalized Asset + approved QAPolicy authority, execution state, provider/
  algorithm references and terminal outcome;
- `SyntheticQAMeasurement`: append-only typed/canonical evidence with digest, algorithm version,
  confidence, threshold result and reason code;
- `SyntheticQAReviewDecision`: append-only operator decision with review kind, decision, reason,
  actor and timestamp; no hard-gate override field;
- `SyntheticIdentity` forward strengthening: canonical Asset and accepted QA run become the unique
  authority while Phase 0 generator/model/prompt/provenance fields become nullable legacy projection.

The migration must preserve legacy skeleton rows, but PostgreSQL must reject new canonical
identities without a matching `QA_PASSED` record and normalized synthetic Asset. Asset blob fields,
record lineage, measurement/review evidence and identity canonical links are immutable. Delete is
forbidden; later revocation is a separate Milestone.

## Normalization and storage contract

- Reuse pinned Pillow 12.3.0 and the dependency-local sanitizer core; no version change.
- Read only an undeleted M2 raw source through the synthetic storage port and verify authoritative
  byte count, MIME, dimensions and SHA-256 before decode.
- Enforce magic/MIME, bounded bytes, single frame, edge/pixel limits, decompression-bomb handling,
  orientation, fixed colorspace handling, metadata stripping, canonical JPEG encode, second decode
  and output SHA-256.
- Record requested/source dimensions separately from normalized dimensions; never pretend the
  P2-M2 native `1254×1254` outputs matched requested `1024×1024`.
- Write normalized bytes to `internal-synthetic/v1/normalized`, never raw or user namespaces.
- Use deterministic opaque references and create-if-absent. A conflicting existing blob fails
  closed. Crash recovery may attach only an exact checksum match.
- Raw TTL cleanup must not race an active normalization lease. Once immutable normalized evidence
  commits, normal raw retention policy resumes and deletion remains append-only evidence.

## QA and identity Gate

Every QAPolicy used for identity registration must explicitly enumerate required measurements,
hard/soft classification, algorithm/version, threshold/review rule and reason taxonomy. Unknown,
unsupported or unmeasured required capability fails closed.

Required hard evidence:

- synthetic origin and permitted internal research rights;
- raw and normalized checksum chain;
- decode/sanitize/second-decode success;
- exactly one face;
- policy-bounded pose, occupancy, eye/mouth visibility and landmark confidence;
- no unresolved automatic hard failure;
- explicit clearly-adult presentation review;
- explicit likeness/no-real-person-reference and license/rights review;
- approved Vision candidate/model artifact for any automated Vision claim.

Human review may supply explicitly human-only observations such as adult presentation, obvious
watermark/text, background suitability or likeness risk. It may not erase an automatic failure,
invent a model result or convert an unsupported check to PASS.

Identity registration locks the asset record, Asset and QARun in one PostgreSQL transaction,
rechecks every required gate, inserts exactly one canonical identity and moves the record to
`IDENTITY_REGISTERED`. Concurrent duplicate registration must yield one identity and one safe
idempotent result, never two identities.

## Vision and supply-chain Gate

The existing first-party `FaceObservation`, `FaceLandmarkSet`, `PoseEstimate` and
`GeometryMeasurement` contracts are inputs to refinement, not proof that a Provider is approved.
M3 must change Vision input from `GeneratedImagePayload` to a normalized-synthetic input type.

Candidate progression is:

```text
LICENSE_REVIEW_REQUIRED
→ POC_APPROVED
→ RUNTIME_CANDIDATE
→ APPROVED_FOR_SYNTHETIC_M3
```

Code license, Python package, native dependencies, Face Landmarker/model artifact, training/
evaluation data and redistribution/commercial terms are reviewed separately. The PoC must bind exact
versions/checksums, Python 3.13 Windows/Linux/Docker compatibility, SBOM, vulnerabilities, runtime
footprint, deterministic/repeatability evidence, failure cases and replacement boundary.

`P2-M3-VISION-GATE: EXTERNAL_VALIDATION_REQUIRED`

Without an approved candidate and controlled benchmark, M3 remains `EXECUTING` or at most
`CONDITIONAL`; it cannot become `PASS/FROZEN`, create release-eligible evidence or open M4.

## Bounded task contracts

Every task reports:

`TASK_ID; STATUS: PASS|BLOCKED|FAIL; SUMMARY; FILES_CHANGED; TESTS_RUN; TEST_RESULTS; ACCEPTANCE_CRITERIA; SECURITY_NOTES; DATA_NOTES; OSS_LICENSE_NOTES; ASSUMPTIONS; BLOCKERS; RISKS_FOUND; HANDOFF_NOTES`

### P2-M3-T01 — Governance and execution freeze

- BOOTSTRAP_STATUS: `OK`.
- TASK_ID: `P2-M3-T01`.
- OBJECTIVE: encode ADR-027, M3 execution/acceptance documents and forward project state.
- WHY_DELEGATED: `NOT_DELEGATED`; architecture freeze and milestone authorization remain Principal
  responsibilities.
- SCOPE: governance-only planning checkpoint.
- ALLOWED_FILES_OR_MODULES: ADR-027, M3 operations docs, architecture/provider/milestone/AGENTS/
  MEMORY and forward research-boundary synchronization.
- FORBIDDEN_SCOPE: production code, migration, dependencies, models, images, `.tmp` and M4 scope.
- DEPENDENCIES: frozen P2-M2 SHA/run/artifacts and Project Owner M3 synthetic-research authorization.
- INPUTS_AND_ASSUMPTIONS: repository state at `0b579eb`; production Provider remains unavailable;
  existing private V01 assets remain outside Git.
- ACCEPTANCE_CRITERIA: M2 terminal authority, M3 state, Vision Gate, hard reviews and identity authority
  need no implementation-worker decisions.
- VALIDATION_COMMANDS: `pnpm.cmd format:check`; `git diff --check`; invariant/conflict scan; same-SHA
  GitHub Actions after commit/push.
- RECOMMENDED_AGENT: Principal/Sol High.
- RECOMMENDED_MODEL_TIER: Sol High.
- OUTPUT_FORMAT: the milestone report format defined above plus checkpoint SHA/run evidence.
- ESCALATION_CONDITION: any unresolved schema, privacy, license, Provider or Phase-boundary decision.

### P2-M3-T02 — `0010_synthetic_asset_qa` authority

- BOOTSTRAP_STATUS: `OK`.
- TASK_ID: `P2-M3-T02`.
- OBJECTIVE: implement the four M3 entities and forward-strengthen SyntheticIdentity.
- WHY_DELEGATED: bounded PostgreSQL/SQLAlchemy migration implementation under frozen ADR-027
  semantics.
- SCOPE: database authority and database-only tests.
- ALLOWED_FILES_OR_MODULES: SQLAlchemy models, `0010_synthetic_asset_qa`, real-PostgreSQL migration/
  invariant/concurrency tests.
- FORBIDDEN_SCOPE: historical migrations, normalization code, Provider adapters, routes, M4 entities.
- DEPENDENCIES: T01 checkpoint CI PASS and unique current migration head `0009_generation_batch_pipeline`.
- INPUTS_AND_ASSUMPTIONS: ADR-027 entity names, states, uniqueness, immutability and legacy projections
  are frozen; no existing M3 rows exist.
- ACCEPTANCE_CRITERIA: lifecycle/immutability/unique/legacy compatibility and atomic identity
  prerequisites are enforced by PostgreSQL; downgrade with M3 data fails closed where lossless
  reversal is impossible.
- VALIDATION_COMMANDS: Ruff; strict mypy; fresh/`0009→0010→0009→0010`; `alembic check`; targeted
  real-PostgreSQL tests.
- RECOMMENDED_AGENT: `pm_data_worker`.
- RECOMMENDED_MODEL_TIER: Terra Medium.
- OUTPUT_FORMAT: milestone report format plus migration head and database lifecycle evidence.
- ESCALATION_CONDITION: any need to change schema semantics, ADR-027 authority, historical migration,
  public contract or Phase boundary.

### P2-M3-T03 — Deterministic normalizer and normalized storage

- BOOTSTRAP_STATUS: `OK`.
- TASK_ID: `P2-M3-T03`.
- OBJECTIVE: implement raw verification, canonical normalization, normalized namespace and crash
  recovery without changing M2 raw authority.
- WHY_DELEGATED: bounded backend/storage implementation reusing an approved pinned image primitive.
- SCOPE: synthetic normalizer, normalized storage adapter boundary and recovery tests.
- ALLOWED_FILES_OR_MODULES: synthetic dataset normalizer/storage application modules, storage keys/
  adapters and tests.
- FORBIDDEN_SCOPE: Vision/identity logic, new dependency, user sanitizer behavior changes without
  explicit compatibility proof, public API.
- DEPENDENCIES: T01 PASS and T02 schema names integrated; pinned Pillow 12.3.0 remains unchanged.
- INPUTS_AND_ASSUMPTIONS: only M2 raw-source opaque references are accepted; V01 binaries stay in
  ignored private storage and may be reused only after checksum reconciliation.
- ACCEPTANCE_CRITERIA: deterministic exact input produces exact normalized evidence; malformed/
  polyglot/bomb/metadata/animation/tamper/storage-conflict paths fail closed; raw cleanup race is safe.
- VALIDATION_COMMANDS: Ruff; strict mypy; Pillow golden tests; storage/recovery tests; Linux/Windows
  parity evidence.
- RECOMMENDED_AGENT: `pm_backend_worker`; upgrade to `pm_terra_high_worker` only on evidenced frozen
  crash-state complexity.
- RECOMMENDED_MODEL_TIER: Terra Medium by default, Terra High only after escalation evidence.
- OUTPUT_FORMAT: milestone report format with deterministic checksums and zero-skip platform evidence.
- ESCALATION_CONDITION: sanitizer semantics, dependency, output contract, namespace or crash-recovery
  authority must change.

### P2-M3-T04 — QA domain, repository and normalized Vision port

- BOOTSTRAP_STATUS: `OK`.
- TASK_ID: `P2-M3-T04`.
- OBJECTIVE: implement typed QA state, measurement/review evidence, hard-gate evaluator and
  normalized-only Vision contract with deterministic Mock.
- WHY_DELEGATED: bounded domain/provider-port implementation with frozen evidence and failure rules.
- SCOPE: first-party QA types, repository/service, normalized Vision port and deterministic Mock.
- ALLOWED_FILES_OR_MODULES: P2 domain/provider contracts, QA repository/service and unit/PostgreSQL
  tests.
- FORBIDDEN_SCOPE: selecting/installing a real Vision dependency, age/sensitive classifiers,
  identity registration, routes or M4 transforms.
- DEPENDENCIES: T01 PASS and T02 entity names integrated; T03 normalized payload/reference type frozen.
- INPUTS_AND_ASSUMPTIONS: automatic claims require an approved algorithm; human-only observations
  stay explicit reviews and cannot erase hard failures.
- ACCEPTANCE_CRITERIA: required unknown/unsupported evidence fails closed; hard failures cannot be
  overridden; SDK/raw/URL/User inputs cannot cross the port.
- VALIDATION_COMMANDS: Ruff; strict mypy; targeted unit/PostgreSQL/provider zero-network tests; source
  scans.
- RECOMMENDED_AGENT: `pm_backend_worker`.
- RECOMMENDED_MODEL_TIER: Terra Medium.
- OUTPUT_FORMAT: milestone report format with reason-taxonomy and zero-network evidence.
- ESCALATION_CONDITION: new QA authority, threshold decision, sensitive classifier, dependency/model
  selection or public contract is required.

### P2-M3-T05 — Worker orchestration and identity registration

- BOOTSTRAP_STATUS: `OK`.
- TASK_ID: `P2-M3-T05`.
- OBJECTIVE: implement reference-only normalization/QA tasks, retries/reconcile and atomic canonical
  identity registration.
- WHY_DELEGATED: contracts are frozen, while transactions, leases, at-least-once delivery and crash
  recovery require difficult multi-file control-flow implementation.
- SCOPE: M3 application orchestration, reference-only task adapters and atomic registration.
- ALLOWED_FILES_OR_MODULES: M3 application service, Worker tasks/dispatcher, repositories and
  integration tests.
- FORBIDDEN_SCOPE: CLI/public API, real Provider call, M4, QuestionBank and production enablement.
- DEPENDENCIES: T02–T04 integrated and Principal-accepted.
- INPUTS_AND_ASSUMPTIONS: PostgreSQL is authoritative; Celery is only an at-least-once adapter; all
  task payloads contain opaque IDs/request ID/schema version only.
- ACCEPTANCE_CRITERIA: at-least-once delivery is idempotent; execution failure differs from rejection;
  concurrent registration yields one identity; logs remain allowlisted.
- VALIDATION_COMMANDS: Ruff; strict mypy; real PostgreSQL/Redis/Celery crash/retry/concurrency tests
  with zero mandatory skip.
- RECOMMENDED_AGENT: `pm_terra_high_worker`.
- RECOMMENDED_MODEL_TIER: Terra High.
- OUTPUT_FORMAT: milestone report format with lock ordering, retries, concurrency and failure evidence.
- ESCALATION_CONDITION: any architecture, schema, task-message, privacy/security or milestone-scope
  change is needed.

### P2-M3-T06 — Vision candidate license review, PoC and calibration

The exact artifact acquisition, isolated runtime audit, calibration/holdout split, negative controls
and threshold-freeze sequence are preregistered in
`docs/research/P2_M3_V02_VISION_CALIBRATION_PROTOCOL.md`. That protocol is non-executable until the
Project Owner explicitly authorizes the exact wheel and model-bundle downloads.

- BOOTSTRAP_STATUS: `OK`.
- TASK_ID: `P2-M3-T06`.
- OBJECTIVE: select and prove one synthetic-only Vision candidate or return an evidence-backed blocker
  without weakening the Gate.
- WHY_DELEGATED: `PARTIALLY_DELEGATED`; bounded PoC mechanics may be isolated, but license/model/data
  approval and threshold freeze remain Principal decisions.
- SCOPE: exact candidate supply-chain review, isolated PoC, preregistered calibration and review.
- ALLOWED_FILES_OR_MODULES: live upstream/license research, isolated PoC environment, model registry,
  SBOM, benchmark fixtures/results and approval ADR/addendum.
- FORBIDDEN_SCOPE: real/user images, unreviewed weights, production config, benchmark threshold
  changes after holdout, or representing code license as model approval.
- DEPENDENCIES: T03 normalized assets, T04 normalized Vision port, approved PoC authorization and
  checksum-valid private V01 source set.
- INPUTS_AND_ASSUMPTIONS: MediaPipe is only `LICENSE_REVIEW_REQUIRED`; no package, model or weight is
  approved by this protocol itself.
- ACCEPTANCE_CRITERIA: exact package/model/data/license/checksum and platform evidence; bounded
  eight-asset benchmark plus negative controls and repeatability; explicit PASS/FAIL/FURTHER_RESEARCH.
- VALIDATION_COMMANDS: reproducible PoC command; checksum verification; Windows/Linux/Docker;
  source/license/vulnerability/SBOM scan; holdout report.
- RECOMMENDED_AGENT: Principal for approval; `pm_terra_high_worker` only for bounded frozen PoC
  implementation; `pm_security_reviewer` for independent review.
- RECOMMENDED_MODEL_TIER: Sol High decision, Terra High bounded implementation/review.
- OUTPUT_FORMAT: milestone report format plus candidate manifest, preregistration and benchmark result.
- ESCALATION_CONDITION: unclear artifact rights, new dependency chain, data/privacy uncertainty,
  platform mismatch, threshold change or benchmark anomaly.

### P2-M3-T07 — Integrated evaluation and same-SHA CI evidence

- BOOTSTRAP_STATUS: `OK`.
- TASK_ID: `P2-M3-T07`.
- OBJECTIVE: independently verify schema, normalization, QA, review, identity and boundary behavior.
- WHY_DELEGATED: independent tests and CI evidence improve defect detection; test and CI ownership must
  remain disjoint if both agents are used.
- SCOPE: M3 test fixtures, regression/security suites, CI evidence and acceptance evidence only.
- ALLOWED_FILES_OR_MODULES: synthetic/non-human fixtures, tests, CI evidence generator/workflow and
  acceptance docs.
- FORBIDDEN_SCOPE: production fixes hidden inside tests, real images, live AI in default CI or Gate
  skips.
- DEPENDENCIES: T02–T06 integrated, Vision Gate resolved, and Principal candidate review complete.
- INPUTS_AND_ASSUMPTIONS: default CI is deterministic/zero-network and private V01 binaries remain
  outside Git; only allowlisted aggregate artifacts may be uploaded.
- ACCEPTANCE_CRITERIA: full Python/TS/PostgreSQL/Redis/Celery/Docker/contracts/Gitleaks/license/SBOM
  Gate and `mirror.p2-m3.ci-evidence/v1` bind one SHA with zero mandatory skip.
- VALIDATION_COMMANDS: complete repository Gate plus exact-SHA GitHub Actions and artifact inspection.
- RECOMMENDED_AGENT: `pm_test_worker`, then `pm_infra_worker` only for disjoint CI/evidence files.
- RECOMMENDED_MODEL_TIER: Terra Medium.
- OUTPUT_FORMAT: milestone report format plus exact SHA, job, artifact and zero-skip summary.
- ESCALATION_CONDITION: any mandatory skip, Gate weakening, CI live-model dependency, sensitive fixture
  need or production defect discovered by tests.

### P2-M3-T08 — Independent final review and freeze

- BOOTSTRAP_STATUS: `OK`.
- TASK_ID: `P2-M3-T08`.
- OBJECTIVE: read-only security/privacy/data/supply-chain/phase review and Principal Gate decision.
- WHY_DELEGATED: final Gate requires independent security and integrated acceptance review.
- SCOPE: read-only candidate, evidence and artifact review; Principal alone records the Gate.
- ALLOWED_FILES_OR_MODULES: diff, schema, tests, logs and artifacts read-only; review reports.
- FORBIDDEN_SCOPE: implementation changes, Gate weakening, M4 execution or production approval.
- DEPENDENCIES: T07 same-SHA candidate CI and artifacts complete.
- INPUTS_AND_ASSUMPTIONS: candidate SHA is immutable during review; any repair creates a new candidate
  and repeats required validation.
- ACCEPTANCE_CRITERIA: PASS/CONDITIONAL/FAIL with evidence; defects become minimal `P2-M3-Rxx`; only
  all mandatory PASS may become `FROZEN` and open M4 refinement.
- VALIDATION_COMMANDS: exact candidate SHA; all three CI jobs; artifacts; migration head; OpenAPI
  digest; dependency/model/fixture manifests; zero-skip evidence.
- RECOMMENDED_AGENT: `pm_security_reviewer` plus `pm_final_reviewer`; Principal decides final Gate.
- RECOMMENDED_MODEL_TIER: Terra High security review and Sol High final review.
- OUTPUT_FORMAT: milestone report format with independent verdicts, evidence pointers and repair list.
- ESCALATION_CONDITION: any architecture, security, privacy, license, migration, Phase-boundary or
  unverified mandatory evidence defect.

## Execution waves

1. Wave 0: T01 planning checkpoint and same-SHA CI.
2. Wave 1: T02 schema; after frozen names, T03 and T04 may proceed only in non-overlapping modules.
3. Wave 2: Principal integration, then T05.
4. Wave 3: T06 license/PoC/calibration; normalization-only validation may begin earlier, but no
   automated Vision PASS claim precedes approval.
5. Wave 4: T07 full integrated evidence.
6. Wave 5: T08 independent review, bounded repairs and closure/freeze CI.

Repair tasks use `P2-M3-R01...`. Architecture, schema semantics, public contract, privacy, license,
model selection or Phase changes require Principal change control and cannot be disguised as Repair.

## Entry and exit

Entry is satisfied when the planning checkpoint CI passes at the M2 freeze-state descendant, the
worktree contains only the protected untracked `.tmp`, migration head remains `0009`, and no new
dependency/model/real image is present.

M3 PASS requires all T01–T08 evidence, real PostgreSQL lifecycle, deterministic normalization,
versioned QA/review, atomic identity registration, an approved synthetic-only Vision candidate,
bounded V01/Vision benchmark, complete local/remote same-SHA Gate and independent final review.

`P2_M3_REFINEMENT: COMPLETE`

`P2_M3_STATE: EXECUTING`

`P2_M3_IMPLEMENTATION_AUTHORIZATION: T02_THROUGH_T08_UNDER_FROZEN_CONTRACT`

`P2_M4_ENTRY: CLOSED_UNTIL_P2_M3_FROZEN`
