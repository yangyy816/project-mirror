# ADR-036：确定性几何变体研究权威

## Status

Accepted — 2026-08-18

## Context

P2-M3 已冻结 canonical synthetic Asset、版本化 QA evidence、bank-independent
`SyntheticIdentity` 与第一方 `FaceObservation` / `GeometryMeasurement`。P2-M4 需要研究可测量的
二维几何变体，但不能把 Prompt 近似、全局标准脸、未验证 OpenCV、M3 私有 Vision build closure 或
绝对目标坐标升级为变换权威。

M4 只证明 source-relative deterministic transform 的候选可行性。完整 target/non-target isolation、
duplicate/diversity 与 QuestionBank release 分别属于 M5 和 M6。

## Decision

- `VariantSpecification` 是不可变的 requested intent：绑定 canonical source Asset、source identity、
  approved source QA run、GeometryOntology version、target dimension、方向、相对 magnitude、显式 control
  dimensions、algorithm candidate/version 与 tolerance-policy reference。它不保存绝对理想几何或人口目标。
- M4 研究可接受 `EXPERIMENTAL` 或 `READY` ontology dimension；`UNSUPPORTED`、`REQUIRES_3D`、
  `STYLE_ONLY` 与未知 dimension 必须在写 result blob 前 fail closed。M4 PoC 不得仅凭视觉效果把 dimension
  提升为 `READY`；M5 的预注册 isolation holdout 才能支持该升级。
- `TransformRun` 是 execution/evidence authority。每次 attempt 追加事实，失败不得回退状态或覆盖旧证据。
  成功 run 绑定 source/result Asset、source/result QA measurement authority、exact algorithm/runtime manifest、
  deterministic level、requested delta 与实际测量 reference。
- 变换只相对 source landmark/measurement 计算 displacement。禁止映射到 global average、population prior、
  hidden beauty template 或跨 identity 的绝对目标坐标。
- result 必须是新的 private immutable synthetic Asset；source bytes、source Asset、M3 QA 与 identity 均不修改。
  输出保持 source dimensions、orientation 和 canonical colorspace，经过 bounded encode、second decode 与
  checksum 后才可提交。零变化、越界、折叠、自交、无效像素或 checksum conflict 必须拒绝。
- 变换引擎通过第一方 `GeometryTransform` port 接收 bounded canonical pixels、landmarks 与第一方 spec，
  返回 bounded bytes 和 allowlisted facts。SDK type、任意 URL、object key、Provider raw response 或隐式网络
  位置不得进入 domain。
- determinism 分级为 `BIT_EXACT_CROSS_PLATFORM`、`BIT_EXACT_SAME_PLATFORM` 和
  `MEASUREMENT_EQUIVALENT`。candidate 必须预注册所声称等级、runtime/toolchain manifest、pixel variance 与
  measurement variance Gate；未达到声明等级即 FAIL，不能事后降级同一 candidate 以强迫通过。
- M4 保存 target measurement 与 control measurement 的实际结果，但不生成最终 `IsolationReport`，也不
  宣告 P2-MVR-v1 通过。M5 才计算并冻结 target error、non-target drift、holdout threshold 与 dimension READY
  判定。
- M3 的 OpenCV 3.4.11 `core,imgproc` closure 继续仅服务私有 source-built Vision candidate，不构成 M4
  采用。M4 的 OpenCV 或其他候选必须经过独立 exact-version acquisition、license/SBOM/vulnerability、
  Windows/Linux/Docker、determinism、performance、footprint、zero-network 与 replacement-cost PoC。
- M4 不修改 public API，不新增 operator CLI，不处理真人或 User Asset，不生成 QuestionBank release。

## Alternatives Considered

- 通过 Prompt 生成“看起来更宽/更窄”的脸并把它当作确定性几何变体。
- 直接复用 M3 的 OpenCV 3.4.11 私有 build closure作为通用 runtime。
- 把 result measurements、isolation conclusion 和 release eligibility 压成一个 Boolean。
- 以全局平均脸或统一理想脸作为 target coordinate frame。
- 在看到 holdout 后修改同一 algorithm/tolerance version 的阈值。

## Consequences

M4 可以先实现稳定的领域、数据库、storage 和 evaluation boundary，再由隔离 PoC 决定是否采用具体
transform candidate。candidate 失败只产生 `FURTHER_RESEARCH` 或新版本研究，不削弱 fail-closed Gate。
M5 能从不可变 source/spec/run/result/measurement chain 重建 isolation evidence。

## Security / Privacy Considerations

输入仅限 M3 QA-passed private synthetic Asset。无真实人脸、User relation、敏感分类、颜值评分、任意网络
读取或生产 Provider。下载授权只允许可信上游、精确版本、checksum 与 ignored private research storage；
不等于 dependency adoption、分发、生产或真人处理批准。

## Testing Implications

需要覆盖 spec canonicalization、非法 dimension、source-relative invariant、state monotonicity、immutable
lineage、bounds/foldover、deterministic replay、second decode、same-platform repeatability、Windows/Linux
parity、candidate zero-network、failure recovery、PostgreSQL concurrency 与 OpenAPI zero drift。
