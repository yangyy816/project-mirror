# P2-M3 Acceptance Evidence

## Status

- Milestone: `P2-M3 — Synthetic Normalization and Base Identity QA`
- State: `EXECUTION_READY`
- Frozen entry: `0b579ebdb1c2a63936225bc59a4b0ca780544df2`
- Planned migration: `0010_synthetic_asset_qa`
- Public API change: none
- Vision candidate Gate: `EXTERNAL_VALIDATION_REQUIRED`
- Real-user facial processing: prohibited

## Mandatory evidence matrix

| Gate                      | Required evidence                                                          | Status  |
| ------------------------- | -------------------------------------------------------------------------- | ------- |
| M2 authority preservation | no GenerationItem/raw/generation evidence rewrite                          | PENDING |
| Migration                 | fresh and `0009→0010→0009→0010`, drift zero                                | PENDING |
| Normalization             | bounded decode, sanitation, canonical encode, second decode, checksum      | PENDING |
| Namespace                 | normalized private namespace separate from raw/user assets                 | PENDING |
| Immutability              | Asset/record/measurement/review/identity lineage cannot mutate/delete      | PENDING |
| QA                        | versioned run, typed measurements, reason codes and hard-gate evaluator    | PENDING |
| Adult policy              | explicit human review; ambiguous/minor-looking reject; no age estimation   | PENDING |
| Vision                    | approved exact package/model/data/license + controlled benchmark           | PENDING |
| Identity                  | one QA-passed canonical Asset creates at most one identity transactionally | PENDING |
| Synthetic-only            | no User relation, real-person fixture, scraping or sensitive classifier    | PENDING |
| Recovery                  | duplicate delivery, lease expiry, blob-before-commit and cleanup race      | PENDING |
| Contracts                 | OpenAPI/generated TypeScript unchanged                                     | PENDING |
| Supply chain              | Pillow unchanged; every new package/model separately approved              | PENDING |
| Full Gate                 | Python/TS/PG/Redis/Celery/Docker/Gitleaks/SBOM/same-SHA Actions            | PENDING |
| Final review              | independent security and final reviewer acceptance                         | PENDING |

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

## Deferred production boundary

`PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER` remains `OPEN`. M3 synthetic research does not approve a
runtime image-generation Provider, real-user Vision processing, production QuestionBank or public
release. Codex native provenance remains `PROVENANCE_ONLY` and unknown facts remain `NULL`.

`P2_M3_LOCAL_GATE: PENDING`

`P2_M3_REMOTE_CI: PENDING`

`P2_M3_STATE: EXECUTION_READY`

`P2_M4_ENTRY: CLOSED`
