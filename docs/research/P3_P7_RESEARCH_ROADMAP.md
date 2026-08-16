# P3–P7 Research Governance Roadmap

## Authority and current state

This document is the forward research-governance map for P3–P7. It is not an execution
protocol and does not authorize implementation, dependency installation, model download,
real-user facial-data processing, schema work, public API work, or bounded Terra tasks.

| Scope | Current state     | Meaning                                                                |
| ----- | ----------------- | ---------------------------------------------------------------------- |
| P0    | `FROZEN`          | Historical foundation remains unchanged.                               |
| P1    | `FROZEN`          | Production implementation and migrations remain unchanged.             |
| P2-M1 | `FROZEN`          | Synthetic authority foundation remains frozen.                         |
| P2-M2 | `FROZEN`          | Generation pipeline and offline-source admission remain frozen.        |
| P2-M3 | `EXECUTION_READY` | Active normalization/base-QA milestone; this roadmap cannot change it. |
| P3–P7 | `PROVISIONAL`     | Directional research only.                                             |

Research maturity is explicit:

- `DIRECTIONAL`: worth researching, but the PoC is not completely preregistered.
- `RESEARCH_APPROVED`: question, baseline, data, budget, stop condition, Gate, and owner
  have been preregistered and approved by the Principal.
- `EXECUTION_READY`: the Phase is active and the Principal has created bounded tasks.

Every P3–P7 item in this revision is `DIRECTIONAL`. None is `RESEARCH_APPROVED` or
`EXECUTION_READY`.

## Cross-phase promotion rule

Every high-impact candidate follows one chain:

```text
DIRECTIONAL
→ complete reproducible PoC contract
→ Principal preregistration review
→ RESEARCH_APPROVED
→ isolated PoC
→ MirrorBench holdout + negative control + ablation
→ license / privacy / security / cost review
→ ADR when production architecture changes
→ active-Phase rolling-wave refinement
→ EXECUTION_READY
```

A successful PoC is evidence, not production approval. A candidate remains blocked if any
required code, model, weight, dataset, foundation-model, biometric, privacy, commercial, or
redistribution evidence is unresolved. If a simpler baseline performs materially the same,
the simpler baseline wins.

## Reproducible PoC contract

Every PoC must use the following versioned fields:

```text
QUESTION
HYPOTHESIS

BASELINE
BASELINE_COMMIT_SHA

INPUT_DATA
DATASET_VERSION
DATA_SPLIT
SOURCE_PROVENANCE
PRIVACY_CLASS

LICENSE_STATUS

METRICS
SUCCESS_GATE
NEGATIVE_CONTROL
ABLATION_PLAN

TIME_BUDGET
COST_BUDGET
STOP_CONDITION

REPRODUCTION_COMMAND
RANDOM_SEED

FAILURE_DECISION
ROLLBACK_PLAN

ARTIFACTS
OWNER_ROLE
DECISION_OWNER
RESULT_STATUS
```

An unfilled field is written as `NOT_PRE_REGISTERED_BLOCKING`; it is never guessed by an
implementing Agent. Before execution, `RESULT_STATUS` must be `NOT_RUN`, and
`DECISION_OWNER` must be the Principal. A result may only become `PASS`, `CONDITIONAL`, or
`FAIL` against the preregistered version; changing a threshold, split, or hypothesis creates
a new version.

## P3 — Provider-neutral SelfState measurement

**Maturity:** `DIRECTIONAL`

**Entry dependency:** P2 synthetic fixtures and provenance are frozen; the P3 legal,
Consent, PIPIA, privacy, security, and Provider Gates are independently satisfied before any
real-user data is admitted.

**First-party authority:** domain code consumes only `FaceObservation`,
`FaceLandmarkSet`, `PoseEstimate`, `GeometryMeasurement`, `MeasurementConfidence`, source
asset reference, measurement version, quality, and provenance. MediaPipe-, 3DDFA-, or
Provider-specific types cannot become `SelfState` authority.

**Research sequence:**

1. Freeze a provider-neutral observation and confidence contract without selecting a winner.
2. Establish a deterministic numeric/synthetic baseline and invalid-input negative controls.
3. Preregister same-subject, multi-photo, multi-pose, multi-lighting, and multi-device
   repeatability fixtures whose rights and privacy class are explicit.
4. Compare selected candidates behind replaceable adapters.
5. Measure repeatability, missing/low-quality rejection, confidence calibration, platform
   variance, latency, cost, and failure behavior in `MirrorSelfStateBench`.
6. Reject or downgrade measurements whose reliability is insufficient; never emit false
   precision.

**Candidate set, not decisions:** MediaPipe Face Landmarker and 3DDFA_V2. Exact source,
runtime, artifacts, weights, and datasets require separate evidence.

**Exit evidence:** provider-neutral contract, fixture manifest, holdout results, negative
controls, confidence-calibration evidence, license/privacy/security review, and a Principal
decision. Without them, P4 cannot treat SelfState measurements as reliable evidence.

## P4 — Self-conditioned preference acquisition

**Maturity:** `DIRECTIONAL`

**Entry dependency:** P3 supplies versioned SelfState observations with calibrated
reliability; P2 supplies traceable adult synthetic question stimuli.

**First-party authority:** routing uses continuous morphology, reliability, coverage,
uncertainty, Local Morphological Neighborhood, context, and deterministic version/seed
facts. It never routes by race, ethnicity, ancestry, nationality, or another sensitive class.

**Mandatory baselines and negative controls:**

- random question selection;
- fixed canonical route;
- uncertainty-only selection;
- information-gain/active acquisition;
- shuffled or deliberately uninformative questions as a negative control.

Each method is compared under equal evidence and fatigue budgets for full, quick, and
progressive calibration. The 72-slot taxonomy expresses coverage capability, not a mandatory
question count.

**Failure decision:** if active acquisition cannot reach the same held-out transfer accuracy
or stability with fewer questions, it does not enter production; fixed/progressive routing
remains the baseline. Complexity and novelty cannot override this decision.

**Exit evidence:** `MirrorQuestionnaireBench` artifact covering information gain,
test-retest stability, coverage, uncertainty calibration, fatigue, latency, and downstream
transfer performance.

## P5 — DesiredDelta and self-transfer calibration

**Maturity:** `DIRECTIONAL`

**Entry dependency:** P3 measurement reliability and P4 questionnaire evidence have passed
their versioned research Gates.

**First-party authority:** `DesiredDeltaProfile` remains a derived, versioned,
self-conditioned model with dimension value, uncertainty/confidence, context, supporting
evidence, constraints, and profile version. It is not a global desired face.

**Evidence precedence:**

```text
current explicit instruction / manual correction / explicit lock
> valid self-transfer evidence
> synthetic questionnaire evidence
> population prior used only for uncertainty and scheduling
```

**Research sequence:** preregister synthetic-to-self signed transfer error, absolute error,
correction direction, uncertainty calibration, context stability, counterevidence, and
anti-homogenization. Compare questionnaire-only, questionnaire plus self-transfer, and
explicit-correction baselines.

**Failure decision:** evidence that does not transfer reliably must reduce delta magnitude
and confidence or remain provisional; it cannot be rescued by a global aesthetic prior.

**Exit evidence:** `MirrorTransferBench`, versioned evidence links, correction provenance,
uncertainty calibration, and a rebuildable Profile materialization contract.

## P6 — Verified non-destructive editing and Agent runtime

**Maturity:** `DIRECTIONAL`

**Entry dependency:** P5 supplies versioned intent/evidence semantics; P1 supplies immutable
originals, private assets, consent, deletion, and non-destructive lifecycle foundations.

**Capability boundaries:** Deterministic Editor, Geometry Editor, Generative Editor,
Identity-Preserving Makeup Transfer, and Agent Tool Layer are peer subsystems. No SDK,
Provider, or model becomes the domain authority.

**Research sequence:**

1. Compare Project Mirror-owned orchestration with an Agents SDK adapter for runtime
   correctness, recovery, observability, latency, cost, and replaceability.
2. Preregister versioned Tool Effect Contracts and `EffectVerifier` policies.
3. Compare deterministic, lightweight/local, and full-generative edit paths.
4. Evaluate target effect, forbidden/non-target effects, region leakage, feature locks,
   identity/geometry/skin preservation, artifacts, rollback, idempotency, and verifier false
   positives/negatives.
5. Evaluate Stable-Makeup, MagicMakeup, and commercial engines only as isolated baselines
   after their complete dependency and rights chains are cleared for the research scope.

**P6 evidence obligation for P7:** a final save must be traceable to source/result asset,
`ImageVersion` DAG, `EditPlan`, `EditOperation`, manual corrections, Profile version,
context, current instruction/locks, Agent runtime, Provider/model/prompt/tool versions, and
verification result. P6 produces these facts but does not implement P7 memory compilation.

**Failure decision:** transport or JSON success is never visual success. A result that fails
the versioned verifier cannot be published as an accepted `ImageVersion`; an unproven SDK or
engine remains an Adapter candidate.

## P7 — Visual Memory OS and persistent preference learning

**Maturity:** `DIRECTIONAL`

**Entry dependency:** P6 provides accepted final-save semantics and edit provenance; P5
provides rebuildable Profile/evidence semantics.

**First-party authority:** accepted visual, behavioral, and explicit user evidence first enter
an `Evidence Ledger` authority boundary. Directional evidence includes accepted final saves,
edit trajectories, explicit preference set/remove, feature lock/unlock, manual corrections,
self-transfer/questionnaire evidence, and deletion/reset events. Unsaved AI output,
model-generated interpretations, image OCR, external content, vector similarity, Graph nodes,
Memory Cards, and Profile materializations never gain persistent instruction authority.

**Refined architecture direction:**

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

Profile, Visual Index, temporal facts/graph, Active Exemplars, Memory Cards, and Procedural
Memory are optional derived views. Each must be versioned, evidence-linked, deletion-aware,
and rebuildable. A graph, vector index, LLM summary, or third-party memory runtime cannot become
Project Mirror's memory authority.

**Directional research priorities:**

1. Evidence Ledger contract and authority/provenance/deletion semantics.
2. Compiler idempotency, checkpoint, partial retry, generation invalidation, and rebuild.
3. Profile-only and PostgreSQL structured-evidence retrieval baselines.
4. Deterministic Memory Gate v1 with `ALLOW | DOWNWEIGHT | ASK | DENY` decisions.
5. Bounded Context Compiler with separate Profile, exemplar, counterevidence, and procedure
   budgets.
6. Bi-temporal preference facts using valid time and system/learned time without destructive
   overwrite.
7. Evidence Independence grouping/weighting for same-session, burst, photoshoot, near-duplicate,
   shared-reference, or batch-correlated evidence; raw evidence remains preserved.
8. Retrieval explain traces and supporting/counterevidence channels.
9. Diverse Active Visual Exemplars and faceted retrieval for global, geometry, makeup, skin,
   lighting, scene, pose, procedure, temporal history, and identity constraints.
10. Memory Cards as versioned intent-to-evidence acceleration, never user truth.
11. Procedural Memory as analytics-first recommendation; no autonomous prompt, tool-policy, or
    code self-modification.
12. Complete delete propagation, derived-orphan verification, and rebuild from remaining
    evidence.
13. A dedicated graph backend only if PostgreSQL relational temporal baselines fail their
    preregistered Gate.

Every item remains `DIRECTIONAL`. The list does not create tasks, freeze a schema, select a
Provider/model/backend, or imply `RESEARCH_APPROVED`.

**Mandatory ablation ladder:**

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

SQL Structured Evidence Retrieval is deliberately earlier than vector-only because Project
Mirror already owns rich domain evidence. The first vector candidate is PostgreSQL/pgvector
compared with Profile/SQL baselines; no graph database, vector database, memory SaaS, neural
Memory Gate, or embedding model is selected in advance.

`MirrorMemoryBench` must cover stable/context-conditioned preference, drift, contradiction,
explicit lock/unlock, correlated photoshoot burst, manual correction, unsaved candidates,
counterevidence, deletion, image/OCR prompt injection, and cross-user visual similarity. It
must measure retrieval precision/recall/MRR/nDCG, current/historical/visual/facet evidence,
explicit locks, wrong-context/user, stale/hallucinated/unsupported Profile facts, temporal
ordering, evidence independence, image-ablation visual necessity, profile rebuild, deletion
propagation, retrieval/compiler p50/p95/p99, context size, DB/object/embedding/LLM calls,
storage/compile cost, first-pass acceptance, manual correction count, generation count, time,
and cost per final save across 20 to 10,000+ episodes and multi-tenant fixtures.

Every run preserves candidate IDs, score breakdown, Gate/rejection decision, selected evidence,
and final context output. Wrong-user admission, unauthorized admission, unsaved AI-output
promotion, and derived orphan after completed deletion are zero-tolerance hard Gates. All other
numeric suggestions from research remain `SUGGESTED_NOT_PRE_REGISTERED` until the Principal
approves a complete versioned PoC contract.

**Failure decision:** if a simpler Profile or exemplar design performs materially the same,
the complex memory layer is rejected. Deletion, wrong-user isolation, authorization, current
instruction priority, evidence provenance, rebuild, and bounded context are hard Gates. A
learned Memory Gate, graph backend, Memory Card, or procedural-learning layer is rejected when
it does not provide a reproducible utility/security/cost improvement over its simpler baseline.

**Research references, not decisions:** Mem0, GBrain, Graphiti/Zep, PMMC, MemEye, MemLens,
LangGraph/LangMem, Letta, MemGate, MemMachine, V-Mem, and SAGE. Their reported benefits remain
`UPSTREAM_CLAIM` or `UNVERIFIED` until a Project Mirror artifact reproduces them; community issue
reports are not generalized production defects.

## External research claim evidence

External claims use these fields: `SOURCE`, `SOURCE_TYPE`, `ACCESSED_AT`, `CLAIM`,
`CLAIM_STATUS`, `REPRODUCED`, `PROJECT_MIRROR_EVIDENCE`, `LICENSE_EVIDENCE`, and
`CONFIDENCE`.

Allowed `CLAIM_STATUS` values are `UPSTREAM_CLAIM`, `INDEPENDENTLY_VERIFIED`,
`PROJECT_MIRROR_REPRODUCED`, `INFERENCE`, and `UNVERIFIED`.

The user-provided research reports were accessed on 2026-08-16 and are secondary research
sources. Their links identify candidates but do not establish Project Mirror reproduction or
commercial approval. Unless an existing repository record says otherwise, candidate benefit
claims are `UPSTREAM_CLAIM` or `UNVERIFIED`, `REPRODUCED: NO`,
`PROJECT_MIRROR_EVIDENCE: NONE`, and `CONFIDENCE: PROVISIONAL`.

Component-level evidence and license status remain in
`docs/architecture/OSS_EVALUATION.md` and `docs/data/MODEL_LICENSE_REGISTRY.md`.

## Current non-effects

These are expected outcomes, not facts to be forced after execution:

```text
EXPECTED_CURRENT_MILESTONE_IMPACT: NONE
EXPECTED_CURRENT_MILESTONE_GATE_IMPACT: NONE
EXPECTED_DEPENDENCIES_ADDED: NONE
EXPECTED_MODEL_ARTIFACTS_ADDED: NONE
EXPECTED_NEW_ADRS: NONE
```

Actual results must come from the alignment report's before/after evidence. A mismatch blocks
integration rather than being rewritten as `NONE`.
