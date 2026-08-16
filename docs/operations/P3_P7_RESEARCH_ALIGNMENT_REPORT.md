# P3–P7 Research Governance Alignment Report

## Executive summary

This report records the alignment of the user-provided 2026-08-16 research report with the
repository's current authority. It separates directional research from implemented behavior,
adds reproducible PoC governance, and records call-safety and zero-impact evidence for the
Principal.

```text
ADDENDUM_STATUS: READY_FOR_GOVERNANCE_CHECKPOINT
INITIAL_CAPTURE_STATUS: COLLISION_DETECTED

P0_STATUS: FROZEN
P1_STATUS: FROZEN
P2_M1_STATUS: FROZEN
P2_M2_STATUS: EXECUTING
P3_P7_STATUS: PROVISIONAL
```

No P0/P1 production repair is claimed. P3–P7 remain `DIRECTIONAL`; no research item was
promoted to `RESEARCH_APPROVED` or `EXECUTION_READY`.

The initial capture correctly stopped on concurrent P2-M2 changes. Principal resumed only after
T05 became the isolated commit `be4a75fdc3b142fc8cd0fed8cef14b3fed9cff9b`; the post-stability
manifest below supersedes the collision as the checkpoint decision evidence without rewriting the
historical preflight.

## Expected outcomes

These are preregistered expectations, not forced results:

```text
EXPECTED_CURRENT_MILESTONE_IMPACT: NONE
EXPECTED_CURRENT_MILESTONE_GATE_IMPACT: NONE
EXPECTED_DEPENDENCIES_ADDED: NONE
EXPECTED_MODEL_ARTIFACTS_ADDED: NONE
EXPECTED_NEW_ADRS: NONE
```

Actual values appear below and must reflect the working tree and validation evidence.

## Principal preflight manifest

```text
CAPTURED_AT: 2026-08-16T15:30:19.9886877+08:00
FINAL_EVIDENCE_CAPTURED_AT: 2026-08-16T15:46:26.9186335+08:00
BRANCH: codex/phase2-m2-generation-pipeline
HEAD_SHA_BEFORE: 86f41bd98874f393a86552d1e86edb483de70162
STAGED_FILES_BEFORE: NONE
```

Pre-existing P2-M2 collision domain:

| Path                                                                 | State before     | SHA-256 before                                                     |
| -------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------ |
| `.github/workflows/ci.yml`                                           | tracked modified | `9dffab187a1d98664953e9bc30d74bcddb3f08cd7a9003b9c88134544345e844` |
| `services/api/src/mirror_api/models.py`                              | tracked modified | `98039068d762d07b988639e4800404e18d69eb1bccc87cb243fc7fd4b8b285d1` |
| `services/api/tests/test_migrations.py`                              | tracked modified | `d3f38d7909e35f55f8a959c7f3adc4bc2fc5c698cbbd09ee3269891599ab7277` |
| `services/api/migrations/versions/0009_generation_batch_pipeline.py` | untracked        | `25719ebb6070287691eb6f0aff00d882947c7066c999629f1d6e28405012501a` |
| `services/api/tests/test_generation_batch_foundation_invariants.py`  | untracked        | `af7e22b8e8a6f6588504ca119ba668f9c1b17c9bacf303295daf1811e119dca7` |

No preflight path was staged. During this documentation task, the external P2-M2 process
changed the two untracked files below, advanced HEAD from `86f41bd` to `85a9450`, continued
editing the `0009` migration, and then started a new five-file application/domain change set
without touching an allowed governance path:

- `services/api/migrations/versions/0009_generation_batch_pipeline.py`
- `services/api/tests/test_generation_batch_foundation_invariants.py`
- `services/api/src/mirror_api/synthetic_dataset/domain.py`
- `services/api/src/mirror_api/synthetic_dataset/generation_repository.py`
- `services/api/src/mirror_api/synthetic_dataset/generation_service.py`
- `services/api/src/mirror_api/synthetic_dataset/generation_types.py`
- `services/api/src/mirror_api/synthetic_dataset/prompt_material.py`

The documentation task did not overwrite, format, stage, revert, or attribute those changes
to itself.

## Files changed by this addendum

- `docs/research/P3_P7_RESEARCH_ROADMAP.md` — new research-governance authority.
- `docs/operations/P3_P7_RESEARCH_ALIGNMENT_REPORT.md` — this Principal handoff.
- `docs/ai/MIRROR_BENCH.md` — maturity, reproducibility, negative-control, and claim status.
- `docs/operations/MILESTONES.md` — current P2-M2 state and phase-neutral future boundary.
- `docs/architecture/VISUAL_MEMORY_OS.md` — phase-neutral boundary and evidence-derived impact.
- `docs/architecture/OSS_EVALUATION.md` — external claim evidence and candidate classification.
- `docs/security/THIRD_PARTY_SOFTWARE_POLICY.md` — claim-status and artifact-manifest policy.
- `docs/data/MODEL_LICENSE_REGISTRY.md` — model claim status and expanded artifact controls.

`MEMORY.md` is Principal-owned and may only be updated after final validation and acceptance.

## Architecture and phase direction changes

### P3

Provider-neutral `FaceObservation`, landmark, pose, geometry, and confidence remain first-party
authority. MediaPipe and 3DDFA are candidates only. Measurement reliability must be proven
across versioned multi-condition fixtures before SelfState can rely on it.

### P4

Random, Fixed Canonical, Uncertainty-only, and Information-Gain acquisition are mandatory
comparators, with shuffled/uninformative negative controls and full/quick/progressive modes.
Failure to reduce questions at equivalent transfer accuracy keeps the fixed/progressive
baseline.

### P5

Synthetic-to-self transfer error, correction evidence, uncertainty, context, evidence
precedence, and anti-homogenization become mandatory research outputs. Profile remains a
rebuildable derived model.

### P6

Agent runtime remains replaceable; first-party orchestration and an Agents SDK adapter require
a benchmark. Deterministic, Geometry, Generative, Makeup Transfer, and Agent Tool subsystems
remain peers behind versioned Tool Effect Contracts and EffectVerifier Gates.

P6 must preserve final-save provenance from source asset through `ImageVersion`, `EditPlan`,
operations, manual corrections, Profile/context, runtime/Provider/model/prompt/tool versions,
and verification. P6 does not implement P7 memory compilation.

### P7

Profile-only through Full Visual Memory OS is a mandatory ablation ladder. PostgreSQL/SQL and
Profile baselines precede pgvector or any new memory/vector/graph service. Accepted user
evidence is authoritative; unsaved AI output and visual/OCR content are not instructions.

## Research maturity and PoC governance

```text
P3_MATURITY: DIRECTIONAL
P4_MATURITY: DIRECTIONAL
P5_MATURITY: DIRECTIONAL
P6_MATURITY: DIRECTIONAL
P7_MATURITY: DIRECTIONAL
P3_P7_TERRA_TASKS_CREATED: NONE
```

Every PoC now requires baseline commit SHA, versioned data and split, provenance/privacy,
negative control, ablation, budget, stop condition, reproduction command, seed, rollback,
decision owner, and result status. Missing fields are `NOT_PRE_REGISTERED_BLOCKING`.

## External research claim status

The pasted report and its links are secondary research inputs accessed on 2026-08-16. No live
upstream refresh or Project Mirror reproduction was performed in this task.

| Candidate                            | Claim status                                                        | Reproduced | Project Mirror decision                                |
| ------------------------------------ | ------------------------------------------------------------------- | ---------- | ------------------------------------------------------ |
| MediaPipe Face Landmarker            | `UPSTREAM_CLAIM`; release metadata has a separate verified snapshot | No         | Candidate; artifact/model/data license review required |
| 3DDFA_V2                             | `UPSTREAM_CLAIM`                                                    | No         | Research baseline; production blocked                  |
| OpenAI Agents SDK                    | `UPSTREAM_CLAIM`                                                    | No         | Adapter candidate; no domain authority                 |
| Stable-Makeup                        | `UPSTREAM_CLAIM`                                                    | No         | Research reference; full dependency review required    |
| MagicMakeup                          | `UPSTREAM_CLAIM`                                                    | No         | Research reference; production blocked                 |
| Graphiti, Mem0, GBrain, MemEye, PMMC | `UPSTREAM_CLAIM`                                                    | No         | Pattern references pending MirrorMemoryBench           |
| FLUX-Makeup / FLUX.1 Kontext-dev     | `UNVERIFIED` license-chain report                                   | No         | `PRODUCTION_BLOCKED` pending authoritative review      |

```text
RESEARCH_CLAIMS_PROPERLY_CLASSIFIED: PASS
```

## API and runtime call-safety matrix

| Capability                | Current authority                                      | Safe instruction to future Codex                                               |
| ------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------ |
| Public HTTP prefix        | Generated OpenAPI                                      | Call only `/api/v1`; never infer `/v1` aliases.                                |
| `/v1/edit-plans/simulate` | Research-report example only                           | Do not call or generate a client method.                                       |
| Editing sessions          | `/api/v1/editing-sessions` currently includes `501`    | Treat as unimplemented until OpenAPI and runtime prove otherwise.              |
| Profiles                  | `/api/v1/profiles` currently includes `501`            | Do not report profile creation as available.                                   |
| Questionnaires            | `/api/v1/questionnaires/runs` currently includes `501` | Do not run P4 through this stub.                                               |
| Billing                   | `/api/v1/billing/checkout` currently includes `501`    | Do not treat real payment as enabled.                                          |
| P2 generation API         | No public OpenAPI operation                            | Use only the current internal P2-M2 protocol; do not invent an endpoint.       |
| P2 Provider execution     | Typed internal ports and current milestone Gate        | Default Mock/zero-network; live Provider requires the dedicated Gate.          |
| Agent runtime             | No approved P6 runtime                                 | Do not install or call Agents SDK as production infrastructure.                |
| Vision runtime            | No approved P3 runtime                                 | Do not install MediaPipe/3DDFA or process real users.                          |
| Visual memory runtime     | No approved P7 runtime                                 | Do not install pgvector, graph DB, vector DB, memory SaaS, or embedding model. |

## OSS, model registry, and AI-BOM changes

- OSS entries now distinguish upstream claims from Project Mirror reproduction.
- Graphiti and Mem0 are explicitly research references, not memory authority.
- Model registry production blocks remain unchanged.
- AI-BOM policy now covers model identity/version, hashes, provenance, all license layers,
  dataset lineage, approved environment, biometric restrictions, and security review.
- Artifact scanning covers tracked and new untracked `.pt`, `.pth`, `.ckpt`, `.onnx`,
  `.safetensors`, `.bin`, `.gguf`, `.mlmodel`, and `.tflite` files.

## Zero-impact evidence

Hashes are SHA-256 over file bytes. Directory manifests use sorted repository-relative path
plus file SHA-256 rows, then hash the UTF-8 manifest.

| Item                      | Before                                                                             | After                                                               | Result                           |
| ------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------- | -------------------------------- |
| Branch / HEAD             | `codex/phase2-m2-generation-pipeline` / `86f41bd98874f393a86552d1e86edb483de70162` | same branch / `85a94506f629fd39b578fc07d040bf74e9c590b7`            | `EXTERNAL_HEAD_ADVANCE`          |
| Active milestone          | P2-M2 `EXECUTING`                                                                  | P2-M2 `EXECUTING`                                                   | `PASS`                           |
| OpenAPI                   | `8809c9c63c609cc270c211d3f8cca03f47d76243fa5aeb6304bb385653adfdb2`                 | same                                                                | `PASS`                           |
| Generated client manifest | `b92933ab4d1775ca3ccea953000637cc15014e5c3a8dea7b5b6408e69892dbf9`                 | same                                                                | `PASS`                           |
| Migration manifest        | `6a4afe02c1cc60e1543aa400ae2a8b5fca27c55276742b9bc2b12720afe4474a`                 | `c0f2a05c23a0167d1b3bb166fcee00e06382e5b50d959415736e492914eb48f3`  | `EXTERNAL_CHANGE_DETECTED`       |
| Dependency manifests      | `94aecb0765aff2f40e1980fca7349a4ee2eca0cd8aeb709d29da045d98172b94`                 | same                                                                | `PASS`                           |
| Lockfiles                 | `7e9f4d583ba590caed6afbafb16b1bb2f1a7f8b7f841d2f5d293a6ab1c49e9b6`                 | same                                                                | `PASS`                           |
| P2-M2 active diff         | Five-file before manifest recorded                                                 | external commit plus migration and five-file application/domain set | `EXTERNALLY_CHANGED / PRESERVED` |
| Model artifacts           | tracked none; untracked none                                                       | tracked none; untracked none                                        | `PASS`                           |
| Image assets              | tracked none; untracked none                                                       | tracked none; untracked none                                        | `PASS`                           |

## Initial concurrent-capture results

```text
INITIAL_CURRENT_MILESTONE_IMPACT: EXTERNAL_P2_M2_CHANGE_DETECTED
INITIAL_CURRENT_MILESTONE_GATE_IMPACT: NOT_EVALUATED_DUE_CONCURRENT_CHANGE

NON_OWNED_PATH_CHANGES_DURING_TASK: DETECTED
ACTIVE_TASK_COLLISION: NONE
PREEXISTING_DIFF_PRESERVED: EXTERNALLY_CHANGED
ACTIVE_TASK_DIFF_PRESERVED: PASS

PUBLIC_API_CHANGED: NO
OPENAPI_CHANGED: NO
GENERATED_CLIENT_CHANGED: NO
DATABASE_SCHEMA_CHANGED: EXTERNAL_CHANGE_DETECTED
MIGRATIONS_CHANGED: EXTERNAL_CHANGE_DETECTED
MIGRATIONS_CHANGED_BY_THIS_TASK: NO
DEPENDENCIES_ADDED: NONE
DEPENDENCY_MANIFESTS_CHANGED: NO
LOCKFILES_CHANGED: NO

TRACKED_MODEL_ARTIFACTS_ADDED: NONE
UNTRACKED_MODEL_ARTIFACTS_ADDED: NONE
MODEL_ARTIFACTS_ADDED: NONE
MODEL_DOWNLOAD_COMMANDS_EXECUTED: NONE
REAL_FACE_ASSETS_ADDED: NONE

NEW_ADRS: NONE
INITIAL_MEMORY_UPDATE: SKIPPED_DUE_COLLISION
```

## Post-stability Principal recapture

The Principal recaptured the repository after P2-M2 T05 was committed and the working tree became
stable. Directory manifests use sorted repository-relative path, a tab, and lowercase file SHA-256,
joined with LF and no terminal newline, then SHA-256 over the UTF-8 rows.

```text
INITIAL_POST_T05_RECAPTURED_AT: 2026-08-16T17:00:01.5476147+08:00
BRANCH: codex/phase2-m2-generation-pipeline
BASELINE_HEAD: be4a75fdc3b142fc8cd0fed8cef14b3fed9cff9b
STAGED_FILES: NONE
ACTIVE_NON_GOVERNANCE_DIFF: NONE
RESEARCH_GOVERNANCE_FILES: 8
PRINCIPAL_MEMORY_FILES: 1
```

| Item                      | Recaptured evidence                                                         | Result             |
| ------------------------- | --------------------------------------------------------------------------- | ------------------ |
| Active milestone          | P2-M2 `EXECUTING`; T05 accepted, T06 next                                   | `PASS`             |
| OpenAPI                   | `8809c9c63c609cc270c211d3f8cca03f47d76243fa5aeb6304bb385653adfdb2`          | `UNCHANGED`        |
| Generated client manifest | 3 files; `b92933ab4d1775ca3ccea953000637cc15014e5c3a8dea7b5b6408e69892dbf9` | `UNCHANGED`        |
| Migration manifest        | 9 files; `f779c331a0d44014de82f5e9d19c11ce219d8576d62d70edb9cd8329e3aad0ef` | `CURRENT_BASELINE` |
| Dependency manifests      | no tracked diff                                                             | `UNCHANGED`        |
| Lockfiles                 | no tracked diff                                                             | `UNCHANGED`        |
| Model artifacts           | tracked none; untracked none                                                | `PASS`             |
| Image assets              | tracked none; untracked none                                                | `PASS`             |
| Governance collision      | only eight declared research paths plus Principal-owned `MEMORY.md` differ  | `NONE`             |

```text
CURRENT_MILESTONE_IMPACT: NONE
CURRENT_MILESTONE_GATE_IMPACT: NONE
PUBLIC_API_CHANGED_BY_ADDENDUM: NO
DATABASE_SCHEMA_CHANGED_BY_ADDENDUM: NO
MIGRATIONS_CHANGED_BY_ADDENDUM: NO
DEPENDENCIES_ADDED: NONE
LOCKFILES_CHANGED: NO
MODEL_ARTIFACTS_ADDED: NONE
REAL_FACE_ASSETS_ADDED: NONE
NEW_ADRS: NONE
MEMORY_UPDATE: PRINCIPAL_ACCEPTED
BEFORE_AFTER_MANIFEST_CHECK: PASS_AFTER_STABLE_RECAPTURE
```

## Risks and mitigations

- **Concurrency:** P2-M2 implementation changed during documentation work. Mitigation: preserve
  its files, record before/after hashes, and distinguish external changes from this addendum.
- **Research overclaim:** upstream claims may be stale or promotional. Mitigation: claim status,
  reproduction, license evidence, and Project Mirror evidence are separate fields.
- **Premature execution:** future frameworks may look attractive. Mitigation: every P3–P7 item
  remains `DIRECTIONAL`, with complete preregistration required before research.
- **Sensitive data:** measurement and memory work may involve facial data. Mitigation: real-user
  work remains blocked by Consent, legal, PIPIA, privacy, security, and Provider Gates.
- **Supply chain:** permissive source code may hide restricted weights/data. Mitigation: complete
  code/model/weight/dataset/foundation/runtime chain review and AI-BOM.

## Deferred decisions and change control

- P3 landmark/3D winner, P4 acquisition algorithm, P6 Agent runtime/editor/provider, and P7
  vector/graph/memory architecture remain deferred.
- Numeric thresholds, budgets, datasets, commands, and seeds require versioned preregistration.
- Any schema, API, dependency, model, sensitive-data, active-milestone, or production architecture
  change requires its own Principal change control and, where applicable, an ADR.
- External changes touching an allowed governance path require `COLLISION_DETECTED` and stop
  integration; no such collision had been observed when this draft was created.

## Tests and validation

```text
FORMAT_CHECK: PASS
FULL_DIFF_CHECK: PASS
SCOPED_DIFF_CHECK: PASS
CONTRACTS_CHECK: PASS
LOCAL_LINK_CHECK: PASS
STALE_STATE_SCAN: PASS
MODEL_ARTIFACT_SCAN: PASS
INITIAL_BEFORE_AFTER_MANIFEST_CHECK: COLLISION_DETECTED
POST_STABILITY_MANIFEST_CHECK: PASS
```

No formatter, code generator, auto-fix, dependency installation, model download, external
Provider call, or real-image processing is authorized or performed by this addendum.
