# P3–P7 Research Governance Alignment Report

## Executive summary

This report records the alignment of the user-provided 2026-08-16 research reports with the
repository's current authority. It separates directional research from implemented behavior,
adds reproducible PoC governance, incorporates the P7 Memory OS deep-research supplement, and
records call-safety and zero-impact evidence for the Principal.

```text
ADDENDUM_STATUS: READY_FOR_GOVERNANCE_CHECKPOINT
INITIAL_CAPTURE_STATUS: COLLISION_DETECTED
P7_DEEP_RESEARCH_ADDENDUM_STATUS: PASS
PRINCIPAL_REVIEW_REQUIRED: YES
INTEGRATION_STATUS: READY_WITH_EXTERNAL_P2_CHANGES_REPORTED
FINAL_PRINCIPAL_RECAPTURE_STATUS: PASS_LOCAL_REMOTE_CI_NOT_CLAIMED

P0_STATUS: FROZEN
P1_STATUS: COMPLETE/FROZEN
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

This P7 deep-research supplement is narrower than the original governance addendum and changes
only:

- `docs/architecture/VISUAL_MEMORY_OS.md` — Evidence Ledger/compiler/Gate/context authority chain,
  MEM-13–MEM-16, bi-temporal, independence, delete/rebuild, and research order.
- `docs/research/P3_P7_RESEARCH_ROADMAP.md` — P7 priorities, refined ablation, metrics, and failure
  decisions; all remain `DIRECTIONAL`.
- `docs/ai/MIRROR_BENCH.md` — SQL-first ladder, lifecycle scenarios, visual-necessity checks,
  explain trace, costs, and zero-tolerance hard Gates.
- `docs/architecture/OSS_EVALUATION.md` — additional P7 research candidates and evidence status.
- `docs/operations/P3_P7_RESEARCH_ALIGNMENT_REPORT.md` — this Principal handoff supplement and
  actual evidence.

`MILESTONES.md`, `MEMORY.md`, security policy, model registry, production code, migrations,
contracts, dependencies, and lockfiles are not owned by this P7 supplement.

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

P7 is refined from a broad evidence-grounded Visual Memory OS into an explicit authority and
runtime chain:

```text
User Truth
→ Evidence Ledger
→ Versioned Incremental Memory Compiler
→ Rebuildable Retrieval Views
→ Retrieval Router
→ Task-Conditioned Memory Gate
→ Bounded Context Compiler
→ Agent
```

Accepted visual, behavioral, and explicit evidence is authoritative. Profile, vector/visual
index, temporal graph, Active Exemplars, Memory Cards, procedural aggregates, OCR, external
content, model interpretation, and unsaved AI output are not authority. PostgreSQL Profile/SQL
baselines precede pgvector or any new memory/vector/graph service.

### P7 Memory OS deep-research supplement

The P7 plan now adds four directional invariants without authorizing implementation:

```text
MEM-13 EVIDENCE_LEDGER_AUTHORITY
MEM-14 COMPILER_IDEMPOTENCY
MEM-15 RETRIEVAL_EXPLAINABILITY
MEM-16 EVIDENCE_INDEPENDENCE
```

The research order is Evidence Ledger → Profile-only → SQL Structured Retrieval → deterministic
Memory Gate and bounded context → Active Exemplars → Temporal SQL → Visual/Vector PoC → Memory
Cards → Procedural Analytics → Graph PoC only if simpler relational baselines fail. Correlated
evidence remains preserved but cannot automatically count as independent confirmation.

Memory Gate v1 is deterministic and admits only `ALLOW | DOWNWEIGHT | ASK | DENY` decisions after
same-user, authorization, retention, validity, supersession, context, explicit-lock, provenance,
confidence, and current-instruction checks. Learned/neural gating remains an unselected future PoC.

Bi-temporal research distinguishes preference `VALID_TIME` from `SYSTEM_TIME / LEARNED_TIME`.
Memory Cards remain versioned intent-to-evidence hints, never future answers or user truth.
Procedural Memory begins as analytics-only recommendations and cannot self-modify prompts,
policies, tools, or code.

Delete/reset research must invalidate or rebuild object references, Profile, visual/vector index,
temporal facts, Active Exemplars, Memory Cards, procedural aggregates, analytic observations, and
caches. Completed deletion has the hard Gate `DERIVED_ORPHANS_AFTER_COMPLETED_DELETE = 0`;
backup retention remains deferred to legal/retention policy.

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

The pasted reports and their links are secondary research inputs accessed on 2026-08-16. No live
upstream refresh or Project Mirror reproduction was performed in this P7 supplement. Every row
below has `REPRODUCED: NO`, `PROJECT_MIRROR_EVIDENCE: NONE`, and
`CONFIDENCE: PROVISIONAL` unless explicitly stated otherwise.

| Candidate                   | Source / type / accessed                                      | Claim / status                                                                 | License evidence / Project Mirror decision                               |
| --------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| MediaPipe Face Landmarker   | Google AI Edge; upstream docs; 2026-08-16                     | landmark/pose candidate; `UPSTREAM_CLAIM`; release snapshot separately checked | artifact/model/data review required                                      |
| 3DDFA_V2                    | report-linked repo; secondary report; 2026-08-16              | 3D alignment baseline; `UPSTREAM_CLAIM`                                        | code/weight/data unresolved; production blocked                          |
| OpenAI Agents SDK           | official docs cited by report; secondary report; 2026-08-16   | runtime Adapter candidate; `UPSTREAM_CLAIM`                                    | no domain authority; adoption review required                            |
| Stable-Makeup / MagicMakeup | report-linked papers/repos; secondary report; 2026-08-16      | makeup baselines; `UPSTREAM_CLAIM`                                             | full dependency/foundation/weight/data chain unresolved                  |
| FLUX-Makeup / Kontext-dev   | user-provided license report; secondary report; 2026-08-16    | restricted dependency-chain concern; `UNVERIFIED`                              | `PRODUCTION_BLOCKED` pending authoritative review                        |
| Mem0                        | report-linked paper/repo; secondary report; 2026-08-16        | add-only/multi-signal pattern; `UPSTREAM_CLAIM`                                | managed benchmark has reported proprietary layer; candidate only         |
| GBrain                      | report-linked repo/evals; secondary report; 2026-08-16        | explainable hybrid/session-demotion pattern; `UPSTREAM_CLAIM`                  | author benchmark and license chain require review                        |
| Graphiti / Zep              | report-linked paper/repo/issues; secondary report; 2026-08-16 | provenance/bi-temporal pattern; `UPSTREAM_CLAIM`                               | issue generalization is `UNVERIFIED`; no graph runtime selected          |
| PMMC                        | report-linked 2026 paper; secondary report; 2026-08-16        | prospective evidence compilation; `UPSTREAM_CLAIM`                             | very new; artifact/data/runtime rights unreviewed                        |
| MemEye / MemLens            | report-linked 2026 papers/repos; secondary report; 2026-08-16 | visual-necessity/image-ablation methods; `UPSTREAM_CLAIM`                      | benchmark image/data licenses require separate review                    |
| LangGraph / LangMem / Letta | official docs cited by report; secondary report; 2026-08-16   | memory taxonomy/context hierarchy; `UPSTREAM_CLAIM`                            | performance benefit `UNVERIFIED`; cloud/data terms unreviewed            |
| MemGate                     | report-linked 2026 paper; secondary report; 2026-08-16        | retrieval admission may reduce memory threats; `UPSTREAM_CLAIM`                | learned Gate model/data/runtime unreviewed; deterministic baseline first |
| MemMachine / V-Mem / SAGE   | report-linked 2026 papers; secondary report; 2026-08-16       | evidence preservation/facet routing/novelty policies; `UPSTREAM_CLAIM`         | very new; artifacts and dependency chains unreviewed                     |

```text
RESEARCH_CLAIMS_PROPERLY_CLASSIFIED: PASS
```

## MirrorMemoryBench P7 changes

The P7 ablation now makes SQL structured evidence retrieval the first retrieval baseline:

```text
No Memory
→ Profile Only
→ SQL Structured Evidence Retrieval
→ Vector Only
→ Profile + Vector
→ Profile + Active Visual Exemplars
→ Hybrid Structured + Visual
→ Hybrid + Temporal
→ + Evidence Independence
→ + Counterevidence
→ + Memory Cards
→ + Procedural Memory
→ Full Candidate Visual Memory OS
```

Synthetic lifecycle coverage now includes explicit unlock, correlated photoshoot bursts,
counterevidence, unsaved candidates, cross-user visual similarity, deletion, and prompt injection
inside image/OCR. Visual cases require image-ablation so caption/Profile-only shortcuts cannot be
misreported as visual-memory evidence.

Run artifacts must preserve candidate set, score breakdown, Gate decision, selected/rejected
evidence, and compiled context. Metrics now explicitly cover p99 retrieval/compiler latency,
DB/object-store/embedding/LLM calls, unsupported Profile facts, evidence independence,
current/historical facts, visual granularity, rebuild, and delete propagation. Only wrong-user,
unauthorized, unsaved-output promotion, and completed-delete orphan counts are frozen zero-tolerance
hard Gates. All other numbers in the deep-research report are
`SUGGESTED_NOT_PRE_REGISTERED` until approved in a versioned PoC contract.

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

## P7 deep-research supplement evidence

The source supplement is the 2,423-line user-provided report accessed on 2026-08-16 with
SHA-256 `b3398267a0094a8f48d945d0e0715ed8b46ee0e21b6118af91ce52daef4d945e`.
It is a secondary source and was not treated as live upstream verification.

The first task capture occurred before any P7 edits:

```text
FIRST_CAPTURE_BRANCH: codex/phase2-m2-generation-pipeline
FIRST_CAPTURE_HEAD: be4a75fdc3b142fc8cd0fed8cef14b3fed9cff9b
FIRST_CAPTURE_STAGED_FILES: NONE
FIRST_CAPTURE_TRACKED_MODIFIED:
  MEMORY.md
  docs/ai/MIRROR_BENCH.md
  docs/architecture/OSS_EVALUATION.md
  docs/architecture/VISUAL_MEMORY_OS.md
  docs/data/MODEL_LICENSE_REGISTRY.md
  docs/operations/MILESTONES.md
  docs/security/THIRD_PARTY_SOFTWARE_POLICY.md
FIRST_CAPTURE_UNTRACKED:
  docs/operations/P3_P7_RESEARCH_ALIGNMENT_REPORT.md
  docs/research/P3_P7_RESEARCH_ROADMAP.md
```

While the report was being read, the external Principal process committed that exact pre-existing
governance content as `07e981e85c7f3380b9eaa2642b53008dddf19450`, then committed a P2-M2
Worker redaction repair as `11ffdd986c5fb8e85e4d236ae6444ddb2500b14d`. All five P7 supplement
paths were rehashed before editing; their bytes still matched the first capture, so the Principal
accepted an exact-content rebaseline. No external process changed their bytes after that rebaseline.

At the evidence capture on `2026-08-16T17:15:43.7337027+08:00`, the only non-owned working-tree
path was the externally created untracked
`services/api/tests/test_p2_m2_security_boundaries.py`. This supplement did not read, overwrite,
format, stage, revert, or attribute that file.

Manifest hashes below use sorted repository-relative path plus file SHA-256 rows, followed by
SHA-256 over the UTF-8 manifest. The before values come from the first capture; the after values
come from the evidence capture above.

| Item                      | Before                                                             | After                                                    | Result                  |
| ------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------- | ----------------------- |
| Branch / HEAD             | branch / `be4a75fdc3b142fc8cd0fed8cef14b3fed9cff9b`                | same branch / `11ffdd986c5fb8e85e4d236ae6444ddb2500b14d` | `EXTERNAL_HEAD_ADVANCE` |
| Active milestone          | P2-M2 `EXECUTING`                                                  | P2-M2 `EXECUTING`                                        | `PASS`                  |
| OpenAPI                   | `7e5cc642ecd486708e6766de3caa169a937f02c8a3c9de8e27e6562b14cf43e5` | same                                                     | `PASS`                  |
| Generated schema          | `e030e1f303beba64be2e8669cc7a10af03fca826ce2b4d6fef7bc33b4b70a1e9` | same                                                     | `PASS`                  |
| Migration manifest        | `55ae26cb9c0bc412d42dec1ffd30f08f78f28279b4a5fee0a04bb00ad6228186` | same                                                     | `PASS`                  |
| ORM schema authority file | `ade93960a6f6f849ff6bfb9092be02ae67eda0591bb3dcf6f401460d8e286238` | same                                                     | `PASS`                  |
| Dependency manifests      | `ee3e8dab7450cbad6dc9b9f4ddf3760408b82878bb27b35da663923a25d86899` | same                                                     | `PASS`                  |
| Lockfiles                 | `0666d1ca318417db3ca8e1fa925e5705ec9fbf86937e7a99ea3b0655f7c82acf` | same                                                     | `PASS`                  |
| P2-M2 active work         | no active implementation diff                                      | external commits plus one untracked security test        | `EXTERNALLY_CHANGED`    |
| Model artifacts           | tracked/untracked empty manifest                                   | tracked/untracked empty manifest                         | `PASS`                  |
| Image assets              | tracked/untracked empty manifest                                   | tracked/untracked empty manifest                         | `PASS`                  |

```text
NON_OWNED_PATH_CHANGES_DURING_TASK: DETECTED
ACTIVE_TASK_COLLISION: NONE
ALLOWED_PATH_CONTENT_COLLISION: NONE_AFTER_EXACT_HASH_REBASELINE
PREEXISTING_DIFF_PRESERVED: EXTERNALLY_CHANGED
ACTIVE_TASK_DIFF_PRESERVED: PASS

CURRENT_MILESTONE_IMPACT_BY_P7_SUPPLEMENT: NONE
CURRENT_MILESTONE_GATE_IMPACT_BY_P7_SUPPLEMENT: NONE

PUBLIC_API_CHANGED_BY_P7_SUPPLEMENT: NO
OPENAPI_CHANGED_BY_P7_SUPPLEMENT: NO
GENERATED_CLIENT_CHANGED_BY_P7_SUPPLEMENT: NO
DATABASE_SCHEMA_CHANGED_BY_P7_SUPPLEMENT: NO
MIGRATIONS_CHANGED_BY_P7_SUPPLEMENT: NO
DEPENDENCIES_ADDED_BY_P7_SUPPLEMENT: NONE
DEPENDENCY_MANIFESTS_CHANGED_BY_P7_SUPPLEMENT: NO
LOCKFILES_CHANGED_BY_P7_SUPPLEMENT: NO

TRACKED_MODEL_ARTIFACTS_ADDED_BY_P7_SUPPLEMENT: NONE
UNTRACKED_MODEL_ARTIFACTS_ADDED_BY_P7_SUPPLEMENT: NONE
MODEL_DOWNLOAD_COMMANDS_EXECUTED_BY_P7_SUPPLEMENT: NONE
REAL_FACE_ASSETS_ADDED_BY_P7_SUPPLEMENT: NONE

NEW_ADRS_BY_P7_SUPPLEMENT: NONE
P7_TERRA_TASKS_CREATED: NONE
MEMORY_MD_CHANGED_BY_P7_SUPPLEMENT: NO
MILESTONES_MD_CHANGED_BY_P7_SUPPLEMENT: NO
```

The external HEAD advances and non-owned P2-M2 file are reported, not normalized into `NONE`.
They do not change the conclusion that this P7 supplement itself has zero production/runtime
impact.

## Final Principal recapture after the P2-M2 T08 candidate

The Principal performed one final read-only recapture after the P2-M2 deterministic candidate was
committed. This section supersedes only the current checkpoint view; it does not rewrite the two
historical collision/recapture records above.

```text
CAPTURED_AT: 2026-08-16T17:29:43.8993030+08:00
BRANCH: codex/phase2-m2-generation-pipeline
HEAD: 7658d11a06efe99e5302d3900000e10937fa637e
STAGED_FILES: NONE
UNTRACKED_FILES: NONE
ACTIVE_NON_GOVERNANCE_DIFF: NONE
RESEARCH_GOVERNANCE_DIFF:
  docs/ai/MIRROR_BENCH.md
  docs/architecture/OSS_EVALUATION.md
  docs/architecture/VISUAL_MEMORY_OS.md
  docs/operations/P3_P7_RESEARCH_ALIGNMENT_REPORT.md
  docs/research/P3_P7_RESEARCH_ROADMAP.md
```

The manifest algorithm remains sorted repository-relative path, a tab, lowercase file SHA-256,
LF joining with no terminal newline, and SHA-256 over the UTF-8 rows. Dependency scope is the ten
tracked root/workspace/package Python and Node manifests; lock scope is `pnpm-lock.yaml` plus
`requirements.lock`.

| Item                   | Final evidence                                                                      | Result      |
| ---------------------- | ----------------------------------------------------------------------------------- | ----------- |
| Active milestone       | P2-M2 `EXECUTING`; T07 external Gate blocked; T08 remote pending                    | `PRESERVED` |
| OpenAPI worktree bytes | `8809c9c63c609cc270c211d3f8cca03f47d76243fa5aeb6304bb385653adfdb2`                  | `UNCHANGED` |
| Generated schema bytes | `997fde0854cc3d16afc44296052d17f0117cb6372775a150f00b01b53f64fb86`                  | `UNCHANGED` |
| Migration manifest     | 9 files; `f779c331a0d44014de82f5e9d19c11ce219d8576d62d70edb9cd8329e3aad0ef`         | `UNCHANGED` |
| ORM schema authority   | `ade93960a6f6f849ff6bfb9092be02ae67eda0591bb3dcf6f401460d8e286238`                  | `UNCHANGED` |
| Dependency manifest    | 10 files; `d62b3a690bfd73fa4210e3311f750a6a8da2a736c150340ac5e97c4b3dee6ed4`        | `UNCHANGED` |
| Lock manifest          | 2 files; `2ee0928a907ffdacf6aee8ad9df15f093fc7734f8245398c34c8a6e40dbaf6da`         | `UNCHANGED` |
| Model artifacts        | tracked none; untracked none                                                        | `PASS`      |
| Image assets           | tracked none; untracked none                                                        | `PASS`      |
| Local links            | no missing repository-local target across the five files                            | `PASS`      |
| Maturity scan          | `RESEARCH_APPROVED`/`EXECUTION_READY` occur only in definitions or explicit denials | `PASS`      |

```text
CURRENT_MILESTONE_IMPACT_BY_FINAL_SUPPLEMENT: NONE
CURRENT_MILESTONE_GATE_IMPACT_BY_FINAL_SUPPLEMENT: NONE
PUBLIC_API_CHANGED_BY_FINAL_SUPPLEMENT: NO
DATABASE_SCHEMA_CHANGED_BY_FINAL_SUPPLEMENT: NO
MIGRATIONS_CHANGED_BY_FINAL_SUPPLEMENT: NO
DEPENDENCIES_ADDED_BY_FINAL_SUPPLEMENT: NONE
LOCKFILES_CHANGED_BY_FINAL_SUPPLEMENT: NO
MODEL_ARTIFACTS_ADDED_BY_FINAL_SUPPLEMENT: NONE
REAL_FACE_ASSETS_ADDED_BY_FINAL_SUPPLEMENT: NONE
NEW_ADRS_BY_FINAL_SUPPLEMENT: NONE
P3_P7_MATURITY: DIRECTIONAL
MEMORY_UPDATE_DECISION: PRINCIPAL_ACCEPTED_DURABLE_DIRECTION_ONLY
GOVERNANCE_CHECKPOINT_DECISION: ACCEPT
```

The same local candidate passed Prettier, contracts, Ruff, strict mypy, the complete TypeScript
Gate, 37 isolated Linux M2 evidence tests with zero skip, and healthy five-service Compose. GitHub
Actions is deliberately `NOT CLAIMED`: pushing this P2-M2 branch requires explicit repository
authorization that was not available during this recapture. This limitation affects the active
M2 T08 remote Gate, not the zero-runtime-impact conclusion for this documentation checkpoint.

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

P7_SUPPLEMENT_FORMAT_CHECK: PASS
P7_SUPPLEMENT_FULL_DIFF_CHECK: PASS
P7_SUPPLEMENT_SCOPED_DIFF_CHECK: PASS
P7_SUPPLEMENT_CONTRACTS_CHECK: PASS
P7_SUPPLEMENT_LOCAL_LINK_CHECK: PASS
P7_SUPPLEMENT_STALE_STATE_SCAN: PASS
P7_SUPPLEMENT_PLACEHOLDER_SCAN: PASS
P7_SUPPLEMENT_MATURITY_SCAN: PASS_DEFINITIONS_ONLY
P7_SUPPLEMENT_MODEL_IMAGE_SCAN: PASS
P7_SUPPLEMENT_MANIFEST_CHECK: PASS_WITH_EXTERNAL_P2_CHANGES_REPORTED
```

No formatter, code generator, auto-fix, dependency installation, model download, external
Provider call, or real-image processing is authorized or performed by this addendum.
