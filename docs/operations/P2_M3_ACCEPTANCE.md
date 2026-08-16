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
| QA                        | versioned run, typed measurements, reason codes and hard-gate evaluator    | PENDING     |
| Adult policy              | explicit human review; ambiguous/minor-looking reject; no age estimation   | PENDING     |
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

## Deferred production boundary

`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER` remains `OPEN`. M3 synthetic research does not approve a
runtime image-generation Provider, real-user Vision processing, production QuestionBank or public
release. Codex native provenance remains `PROVENANCE_ONLY` and unknown facts remain `NULL`.

`P2_M3_LOCAL_GATE: PENDING`

`P2_M3_REMOTE_CI: PENDING`

`P2_M3_STATE: EXECUTING`

`P2_M4_ENTRY: CLOSED`
