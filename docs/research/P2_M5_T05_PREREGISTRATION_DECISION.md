# P2-M5-T05 Cohort and Preregistration Decision

## Result

`P2_M5_T05_OUTCOME: FURTHER_RESEARCH`

`P2_MVR_V1_RESULT: NOT_EVALUATED`

`P2_M5_T06_ENTRY: CLOSED`

T05 cannot honestly create a final `SyntheticEvaluationPolicy`, threshold set or holdout manifest from current
evidence. The four canonical identities are exactly the four identities already used by M4 calibration/holdout, so
all four are `M4_SEEN` under ADR-041. The M5 identity-disjoint holdout count is therefore zero.

## Evidence-bound readiness

The machine-readable decision is `P2_M5_T05_READINESS_EVIDENCE.json`. It binds the accepted M3 authority, M4
preregistration/calibration/evaluation and corrected M4 split authority by SHA-256.

- canonical identities: 4;
- M5 split: 4 `M4_SEEN`, 0 calibration, 0 holdout;
- evaluated dimensions: one `EXPERIMENTAL` `jaw_width` dimension;
- ready dimensions: 0 of required 4;
- ready non-sensitive region groups: 0 of required 3;
- effective M5 holdout N: 0 of required 24 per dimension.

M4's N=2 holdout remains valid M4 reproducibility evidence, but it cannot be re-labelled or counted as an M5
holdout. Its observed target asymmetry and maximum control drift remain descriptive facts, not a tolerance.

## Fail-closed decision

No target/control tolerance, near-duplicate threshold, new ontology version or final cohort digest is selected. No
holdout is accessed or executed. T06 stays closed because its prerequisite exact policy/cohort digests do not exist.

Further work requires a forward research change control that uses the existing synthetic generation, normalization,
QA and M4 evidence boundaries to establish:

1. an identity-disjoint calibration cohort and at least 24 holdout identities per candidate dimension;
2. at least four bidirectional candidate dimensions across at least three non-sensitive region groups;
3. calibration distributions for measurement variance, target error, control drift and pHash distance;
4. a new immutable ontology/policy version and exact split/cohort digests committed before holdout.

This is not authorization to generate unbounded assets, reuse M4-seen identities, select thresholds post-holdout,
enable production geometry, process real-user facial data or release a QuestionBank.
