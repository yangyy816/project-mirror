# ADR-040：P2-M4-T07 测量与 Warp Plan 预注册权威

## Status

Accepted — 2026-08-18

## Context

ADR-036–039 已冻结 source-relative variant、不可变 `LandmarkWarpPlan`、OpenCV 5 私有运行时和
reference-only execution authority，但没有定义 T07 应使用的 landmark index、归一化公式、control
measurement 或 source-relative plan builder。若直接执行 holdout，执行者可在看到结果后选择公式、幅度或
权重，无法形成独立证据。

另一个事实是，当前 private source-built Face Landmarker 返回固定 index 的 478 个坐标，但不返回逐点
confidence。`WarpControlPoint.confidence_ppm` 因此不能伪装成 Provider 概率或模型事实。

## Decision

- T07 只研究 `jaw_width`；不把该维度晋升为 `READY`，也不冻结 M5 isolation tolerance。
- 只使用前 468 个 MediaPipe face-mesh landmarks。target measurement 为
  `distance(234, 454) / distance(10, 152)`。
- control measurements 为 `distance(98, 327) / distance(10, 152)`（`nose_width`）和
  `distance(133, 362) / distance(10, 152)`（`eye_spacing`）。左右眼宽只作为诊断量：
  `distance(33, 133)` 与 `distance(362, 263)`，使用相同 face-height normalization。
- 距离只使用 normalized image-space X/Y；Z、transformation matrix、人口先验和绝对理想脸不参与。
- mesh 必须从已审计的 exact MediaPipe `FACEMESH_TESSELATION` list 按原始顺序每三个 directed edges
  重建一个 triangle，得到 468 points / 852 triangles。不得从无序 edge set 推断额外 clique。
- plan 以 landmarks 234/454 为左右 jaw anchors。requested magnitude 固定为 `30_000 ppm`。
  destination X 使用左右 anchor 的 Gaussian local field：horizontal sigma=`0.12 * jaw_width`，vertical
  sigma=`0.18 * face_height`；每个 anchor 的最大位移是
  `direction_sign * jaw_width * 30_000 / 2_000_000`。destination Y 不变。
- T07 的 `confidence_ppm=500_000` 是已通过完整 landmark、repeatability 和 source-QA Gate 后的保守
  **plan-admission floor**，不是 Provider/model confidence。Provider 未报告的逐点 confidence 仍为未知，
  不得记录为 `1.0` 或宣称模型给出该值。
- calibration 与 holdout identity-disjoint。固定 split、runtime digest、重复次数、stop rule 和 negative
  controls 由 `P2_M4_T07_PREREGISTRATION.md` 绑定；holdout 只能在本 ADR 与 preregistration 提交后执行。
- T07 可证明 same-platform bit-exact replay，并在 Windows/Linux 间检查 measurement equivalence；除非
  bytes 实际一致，否则不得声称 cross-platform bit exact。

## Alternatives

- 使用未定义的 QA JSON 或人工选择 landmark：拒绝，缺少可重建 authority。
- 把 `confidence_ppm=1_000_000` 当作模型输出：拒绝，当前 runtime 未报告该事实。
- 在看到 holdout 后选择 magnitude、公式或权重：拒绝，构成 holdout leakage。
- 在 M4 冻结 target/control tolerance：拒绝，属于 P2-M5 calibration/holdout authority。

## Consequences

- T07 结果可以是 `PASS_EVALUATION_COMPLETE` 或 `FURTHER_RESEARCH`；target effect 弱或 control drift 大
  不得通过放宽同一协议来修饰。
- 该决定不新增 dependency、model、migration、公开 API、生产 geometry、QuestionBank release 或真实用户
  facial processing 权限。
- 若未来 Provider 真正报告逐点 confidence，必须新增版本化 builder/protocol，不能改写本 ADR。
