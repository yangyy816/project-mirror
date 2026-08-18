# P2-M5 Evidence Expansion Protocol

## Status and authority

- Status: `CC_P2_M5_01_STAGE_A_EXECUTION_READY`
- Authority: ADR-041, ADR-042 and `P2_M5_EXECUTION_PROTOCOL.md`
- Prior T05 result: `FURTHER_RESEARCH`
- P2-MVR-v1 result: `NOT_EVALUATED`
- Scope: private synthetic-only research

This protocol does not mutate or replace the accepted T05 evidence. It defines the only forward path for acquiring
the missing calibration, candidate-dimension and later holdout evidence.

## Stage ordering

```text
A governance checkpoint
→ B calibration-only cohort
→ C measurement/transform/threshold calibration
→ D ontology/policy/split preregistration checkpoint
→ E sealed identity-disjoint holdout
→ existing T06/T07 only if every prerequisite passes
```

Stages are serial. Failure or `FURTHER_RESEARCH` at one stage keeps every later stage closed.

## Stage B calibration acquisition envelope

- Target: 12 new independent QA-passed canonical identities.
- Maximum attempts: 18 total; one retry per failed requested item.
- Concurrency: 1.
- Source: `CODEX_NATIVE_IMAGEGEN`, operator-assisted, `PROVENANCE_ONLY`.
- Presentation: synthetic adult 18+, East-Asian-presenting, female-oriented, nonsexual first-pack context.
- Hard reject: real-person/named identity reference, clearly pre-16 presentation, child/student-minor context,
  unsafe/unknown provenance, malformed or multi-face output, failed M3 hard QA, exact duplicate or unresolved source
  integrity.
- Soft selection evidence: ADR-028 first-pack age bands, morphology/style coverage and anti-homogenization. It cannot
  override a hard failure or become a beauty score.
- Private binary, Prompt, object key, raw provider response and storage reference stay outside Git.

If 12 accepted identities are not reached within 18 attempts, Stage B stops as `FURTHER_RESEARCH`; no silent extra
attempts are allowed. Expansion to 24 or 48 calibration identities requires a new committed resource envelope after
the 12-identity distribution is reviewed.

## Stage C candidate screening

Before reading Stage B measurements, commit an exact candidate manifest that fixes for every candidate:

- dimension key and non-sensitive region group;
- landmark topology/model/runtime digests and measurement formula;
- repeat count and Windows/Linux comparison rule;
- bidirectional plan-builder algorithm and magnitude grid;
- control dimensions and artifact/foldover gates;
- missingness/reliability rule and failure interpretation.

The initial research family is:

| Candidate         | Proposed region group | Current authority                                     |
| ----------------- | --------------------- | ----------------------------------------------------- |
| `jaw_width`       | `lower_face`          | M4 experimental measurement/transform evidence exists |
| `eye_spacing`     | `periocular`          | control measurement only; no transform approval       |
| `nose_width`      | `central_face`        | control measurement only; no transform approval       |
| `mouth_width`     | `perioral`            | formula and transform not yet frozen                  |
| `chin_height`     | `lower_face`          | formula and transform not yet frozen                  |
| `cheekbone_width` | `central_face`        | formula and transform not yet frozen                  |

All six outcomes must be reported. A candidate may advance only when measurement repeatability, both transform
directions, target direction, controls, artifacts and platform variance meet a threshold frozen from calibration.
No candidate is READY merely because a transform completes.

## Calibration outputs

Stage C may create only calibration-version evidence for:

- same-image/re-encode/repeat/platform measurement variance;
- requested-versus-measured target distributions;
- normalized control-drift distributions;
- transform/QA/artifact yield;
- exact SHA and first-party pHash/Hamming pair distributions with review labels;
- continuous morphology coverage, nearest-neighbor and duplicate-cluster evidence;
- generation/QA/transform cost and attempt aggregates when known.

No final threshold is valid until Stage D commits a new immutable evaluation-policy version. Unknown provider model,
seed, request ID, usage and cost remain `NULL`.

## Stage D preregistration Gate

Stage D may PASS only if:

- at least four bidirectional candidates cover at least three region groups;
- a calibration cohort is disjoint from all M4-seen identities and is duplicate-cluster adjusted;
- exact ontology, policy, formula, algorithm/runtime/model, threshold and reason-code versions exist;
- the future holdout selection/generation envelope is committed before any holdout measurement or transform;
- all MirrorBench mandatory fields, negative controls and stop interpretations are complete.

Otherwise Stage D records `FURTHER_RESEARCH`, retains all candidate failures and keeps Stage E/T06 closed.

## Stage E holdout envelope

- Entry: Stage D exact-SHA acceptance only.
- Target: 24 new effective holdout identities per candidate dimension; identities may be shared across dimensions.
- Maximum generation attempts: 36 total; one retry per requested item; concurrency 1.
- Split: disjoint from M4-seen and calibration by identity ID, canonical Asset ID, normalized SHA-256 and confirmed
  duplicate cluster.
- Blindness: no Vision measurement, transform, pHash review or manual morphology selection before the exact policy,
  candidate set and split envelope are committed.
- Expansion: N=24 → 48 → 96 only through a new policy/cohort version and the frozen ADR-041 stop rule.

## Mandatory negative controls

1. resource ceiling or retry overflow;
2. real-person/reference/Prompt/private-field leakage;
3. child/student-minor context or unsafe adult-only style ambiguity;
4. M4-seen/calibration/holdout overlap on any split axis;
5. duplicate-cluster double counting;
6. candidate omitted from the report after failure;
7. measurement/plan/runtime/model digest mismatch;
8. threshold created after holdout access;
9. automatic age estimation, beauty scoring or sensitive classification;
10. production Provider, public API, real-user facial processing or QuestionBank release enablement.

`CC_P2_M5_01_A: EXECUTION_READY`

`CC_P2_M5_01_B: CLOSED_PENDING_STAGE_A_TRACKED_ACCEPTANCE`

`CC_P2_M5_01_C_TO_E: CLOSED`

`P2_M5_T06_ENTRY: CLOSED`

`P2_MVR_V1_RESULT: NOT_EVALUATED`
