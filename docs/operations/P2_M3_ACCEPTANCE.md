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
| Identity                  | one QA-passed canonical Asset creates at most one identity transactionally | T02 PASS    |
| Synthetic-only            | no User relation, real-person fixture, scraping or sensitive classifier    | T02 PASS    |
| Recovery                  | duplicate delivery, lease expiry, blob-before-commit and cleanup race      | T03 PARTIAL |
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
  directory ACL fault recurred; same-SHA Actions evidence remains required before accepting R02.

## Deferred production boundary

`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER` remains `OPEN`. M3 synthetic research does not approve a
runtime image-generation Provider, real-user Vision processing, production QuestionBank or public
release. Codex native provenance remains `PROVENANCE_ONLY` and unknown facts remain `NULL`.

`P2_M3_LOCAL_GATE: PENDING`

`P2_M3_T03_REMOTE_CI: PASS`

`P2_M3_REMOTE_CI: PENDING_FINAL_T07`

`P2_M3_STATE: EXECUTING`

`P2_M4_ENTRY: CLOSED`
