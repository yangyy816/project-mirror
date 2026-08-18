# ADR-042：P2-M5 研究证据扩充前向变更控制

## Status

Accepted — 2026-08-19

Change control: `CC-P2-M5-01`

## Context

P2-M5-T05 已以 candidate `e46d7a9d19eee536c2f57cac6de224cccf27f2be`、run `32187946640`
和七项 exact-SHA artifacts 被 Principal 接受为 `FURTHER_RESEARCH`。该结论不是实现缺陷：现有四项
canonical identities 全部属于 `M4_SEEN`，M5 calibration/holdout effective N 均为 0；仓库只有一个
`EXPERIMENTAL jaw_width`，没有四个 READY dimensions、三个冻结 region groups 或 calibration
distributions。

因此 T06–T08 与 M6 不能通过 Repair Task 打开。若要继续 M5，必须使用前向 research change control
扩充 synthetic-only calibration、dimension-candidate 和 identity-disjoint holdout evidence，同时保留 T05
原始 stop decision。

## Decision

- 接受 `CC-P2-M5-01`，只增加 M5 research evidence-expansion path；不修改 T05、M4 或更早 evidence，
  不创建 `T09/T10`，不把研究不足伪装成 Repair。
- 复用冻结的 M2 offline Codex-native admission、M3 normalization/QA/identity authority、M4 deterministic
  measurement/transform/runtime authority与 M5 `0014_m5_eval_authority`。不得建立平行权威或把图片、Prompt、
  object key、private path 写入 Git。
- calibration 与 final holdout 分成不同生成和执行 checkpoint。先建立 12 个独立、QA-passed calibration
  identities；仅当预注册 stability rule 未满足时，按新版本整体扩展到 24，再到 48。首个 12-identity
  calibration wave 最多 18 次 generation attempts，串行执行，单项至多一次 retry。
- calibration 只允许选择 measurement formula、candidate transform、natural magnitude、target/control
  tolerance、repeat/platform variance、pHash candidate threshold 和 coverage rule。它不能产生 MVR result。
- 初始非敏感 candidate family 为 `jaw_width`、`eye_spacing`、`nose_width`，以及在执行前另行冻结 exact
  landmark formula 的 `mouth_width`、`chin_height`、`cheekbone_width`。这些名称只是研究候选，不是 READY
  声明。全部候选结果必须报告，不得只保留成功项。
- 候选 region groups 为 `lower_face`、`periocular`、`central_face` 与 `perioral`。它们只描述几何测量区域，
  不表示人群、民族、审美等级或真实用户分类。最终 MVR 仍要求至少四个双向 dimensions 覆盖至少三个
  groups。
- 每个新 measurement formula、landmark topology、control set、plan builder、magnitude grid、runtime/model
  digest 和 stop rule 必须在读取 calibration image measurements 之前提交。未知或不可靠候选可诚实结束为
  `FURTHER_RESEARCH`、`UNSUPPORTED_IN_P2` 或 `REQUIRES_3D_RESEARCH`。
- 只有 calibration 完成且新的 immutable ontology/evaluation-policy version、thresholds、algorithm/runtime
  digests 和 exact split contract 已被 Principal 接受后，才可建立新的 final holdout。首个 holdout target
  为每个 candidate dimension 24 个 cluster-adjusted identities；同一 holdout identities 可跨 dimensions，
  但每维必须双向完整。首个 holdout wave 最多 36 次 generation attempts。
- holdout identities 必须与 M4-seen/calibration 在 identity、canonical Asset、normalized SHA-256 和 confirmed
  duplicate cluster 四层互斥。holdout 在 policy/split commit 前不得进行 Vision measurement、transform、
  pHash review 或人工筛选。
- generation 使用 `CODEX_NATIVE_IMAGEGEN` operator-assisted offline source，保留 `PROVENANCE_ONLY` 和所有
  unknown provider facts。它不是 production `ImageGenerationProvider`；真实问卷 runtime generation 调用为 0。
- 新 cohort 继续使用 ADR-024、ADR-028–030：synthetic adult 18+ identity、China-market-first、
  East-Asian-presenting、female-oriented、无真人 reference。一般非性感 context 适用 v2 的
  `CLEAR_PRE16_PRESENTATION` / `CHILD_OR_STUDENT_MINOR_CONTEXT` hard reject；成人性感 context 继续要求
  unambiguous 18+。禁止年龄估计、颜值评分、幼态化目标和单一模板脸收敛。
- 官方 MediaPipe 0.10.35 wheels 维持 `REJECT_FOR_P2_M3_RUNTIME`，不得因新的下载授权重新采用。现有
  source-built private Vision runtime、Face Landmarker bundle 与 private OpenCV runtime 只有在 exact manifest
  复核通过时可用于 synthetic research；下载授权不等于 adoption、distribution、production 或真人处理批准。
- `P2_M5_TECHNICAL_GATE`、`P2_MVR_V1_RESULT` 与 M6 entry 继续分离。任何 stage 的失败都保留证据并停止
  后续 stage，不放宽 threshold 或静默替换 identity。

## Bounded change-control stages

1. `CC-P2-M5-01-A`：治理、resource ceiling、candidate family 与 stop contract。
2. `CC-P2-M5-01-B`：12-identity calibration-only generation/admission/normalization/QA/registration。
3. `CC-P2-M5-01-C`：measurement repeatability、candidate transform 与 isolation/pHash calibration。
4. `CC-P2-M5-01-D`：Principal 接受新 ontology/policy/algorithm/split preregistration，或再次
   `FURTHER_RESEARCH`。
5. `CC-P2-M5-01-E`：仅在 D PASS 后建立 24-identity sealed holdout；然后才可重新进入 T06/T07 路径。

每个 stage 都需要独立 bounded-task contract、targeted validation、candidate commit、same-SHA Actions 与
artifact inspection。A 的通过只开放 B；不得越级并行执行 B–E。

## Alternatives Considered

- 把 M4 N=2 或四个 M4-seen identities 重新标为 M5 holdout：拒绝，构成 leakage。
- 直接在 T05 内增加图片、维度和阈值：拒绝，会覆盖已接受的 stop decision。
- 先生成 holdout，再根据 calibration 选择是否查看：拒绝，无法证明 selection blindness。
- 固定一个经验 pHash 或 isolation threshold：拒绝，必须来自 calibration distributions 并前向冻结。
- 只实现四个最容易成功的候选并隐藏失败候选：拒绝，构成 cherry-picking。
- 使用真人 reference、人口标签或年龄估计提高 coverage：拒绝，违反产品与隐私边界。

## Consequences

- P2-M5 保持 `EXECUTING`，T05 仍为 `ACCEPTED_FURTHER_RESEARCH`，T06–T08 与 M6 继续关闭。
- Stage A 是治理 checkpoint，不生成图片、不安装依赖、不修改 schema/OpenAPI。
- Stage B 之后若无法得到 12 个来源、许可、adult-safety、single-face、QA 和 duplicate gates 全部通过的
  independent identities，change control 以 `FURTHER_RESEARCH` 停止。
- Stage C 若不足四个双向候选覆盖三个 region groups，不能建立 final holdout 或宣告 MVR 可执行。
- Stage D 的任何 threshold、ontology、algorithm 或 split 变化都创建新版本；不得改写本 ADR 或旧 evidence。

## Security / Privacy / Supply Chain

所有图片与模型仍位于 Git 忽略的 private namespace。committed evidence 仅允许 opaque IDs、digests、版本、
aggregate counts、bounded measurements 和 categorical reason codes。禁止真实人物、User relation、Prompt
plaintext、图片 bytes、landmark arrays、object keys、signed URLs、Provider payload、凭据和 private paths。

## Testing Implications

必须验证 generation/attempt ceilings、identity/Asset/SHA/cluster split、fixture provenance、age/style v2、
single-face/QA、exact/pHash candidates、candidate-family completeness、repeat/platform variance、threshold timing、
zero-network deterministic paths、OpenAPI zero drift、real PostgreSQL authority与 same-SHA CI artifacts。
