# P2-M5 CC-P2-M5-01-C Calibration Report

## Authority and scope

- Immutable candidate manifest digest:
  `eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4`.
- Manifest candidate/checkpoint: `b0b60eb29336d74a0f4c7628c9d1d1458d11d3f9` / run `32199176469`, accepted
  by `7a0d112e2b21588630096ab63bb5dc7613662bc5` / run `32199833331`.
- Machine-readable redacted evidence: `P2_M5_CC01C_CALIBRATION_AGGREGATE.json`; SHA-256
  `272e473b16b8af346a3e8b516aef1de13f2359583694e6db0bff79b1b472e3bb`.
- Result: `FURTHER_RESEARCH`.

This is synthetic-only calibration evidence. It does not select a tolerance, promote a dimension to `READY`, open a
holdout, authorize production geometry, or authorize real-user facial processing.

## Execution evidence

- Windows qualified report digest:
  `0eac3ef8f7fa10fc4c1b13c685e5d7534716fe011dce702402266987fc947861`.
- The first Debian 12 attempt is retained as failed environment-composition evidence. Its Vision wrapper could not
  start because the exact binary required `GLIBC_2.38` and `GLIBCXX_3.4.31/32`; it produced zero successful rows and
  report digest `593bbceeea82f8511580e99a8b0299ea105ea0334f32c1ef1ecdb8cabcb0a0c1`.
- The qualified Linux run used the existing Debian 13 builder/runtime composition with `--network none`; report digest
  `916ff02cf47d9677b62b57f66aff68364e7aa15f53018941545621d15e453884`.
- Both qualified platforms covered the identical 288-case set. Each produced 172 successful three-repeat cases and
  116 failed cases, for 1,032 successful transform/Vision rows in the combined aggregate.
- Same-platform measurement repeat variance is zero for every successful case. The maximum observed cross-platform
  measurement difference is `4.9965088934289525e-05`.
- A startup preflight now proves that the exact Vision runtime can process a frozen source before any transform work;
  ABI-incompatible environments fail before the 288-case loop.

## Complete candidate outcomes

Counts include both qualified platforms and preserve every failure.

| Candidate         | Cases | Failed | Failure evidence                                      | Stage D consideration |
| ----------------- | ----: | -----: | ----------------------------------------------------- | --------------------- |
| `cheekbone_width` |    96 |     66 | 58 `PLAN_BUILD_FAILED`; 8 `TARGET_DIRECTION_MISMATCH` | Ineligible            |
| `chin_height`     |    96 |      2 | 2 `TARGET_DIRECTION_MISMATCH`                         | Ineligible            |
| `eye_spacing`     |    96 |      2 | 2 `TARGET_DIRECTION_MISMATCH`                         | Ineligible            |
| `jaw_width`       |    96 |      2 | 2 `TARGET_DIRECTION_MISMATCH`                         | Ineligible            |
| `mouth_width`     |    96 |     74 | 74 `PLAN_BUILD_FAILED`                                | Ineligible            |
| `nose_width`      |    96 |     86 | 86 `PLAN_BUILD_FAILED`                                | Ineligible            |

The preregistered complete-case rule requires all 12 calibration identities. A missing row, wrong target direction or
unresolved artifact keeps the candidate out of Stage D. No candidate satisfies that rule; the required minimum is four
bidirectional candidates spanning three non-sensitive region groups.

## Artifact, duplicate and diversity evidence

- Manual categorical review covered repeat-1 Windows/Linux results for every successful case: 172 cross-platform case
  pairs and 344 artifacts. No visible warp tear, duplicated feature, disconnected contour or background seam was found.
- Private manual-review evidence SHA-256:
  `d9ed67391b83669c54335fda388acfb7c22eebf1f97c6580f4b980c43fb2bde6`; content digest
  `4e687b2dfe7a01cc39495025e04d6a891b5250ed80be16f509af2aaf44c55551`.
- Source exact-duplicate evidence compares 132 distinct-identity pairs within platform and finds zero duplicate pairs.
- Variant duplicate evidence compares distinct identities only within the same platform, candidate, direction and
  magnitude. Cross-platform reproducibility pairs and repeats are excluded. It finds zero exact-duplicate pairs.
- Observed result pHash distances are retained by candidate; the minimum observed value is 12. No near-duplicate
  threshold is selected and no automatic near-duplicate rejection is performed.
- Manual artifact review can reject a result but does not override plan, direction, measurement or completeness
  failures.

## Stop decision

`CC_P2_M5_01_C_OUTCOME: FURTHER_RESEARCH`

`CC_P2_M5_01_D_ENTRY: CLOSED`

`CC_P2_M5_01_E_ENTRY: CLOSED`

`P2_M5_T06_TO_T08_ENTRY: CLOSED`

`P2_MVR_V1_EXECUTION: CLOSED`

`P2_M6_ENTRY: CLOSED`

The evidence is useful for a future, separately accepted research redesign. It cannot be converted into Stage D by
relaxing the frozen complete-case rule or hiding failed candidates.
