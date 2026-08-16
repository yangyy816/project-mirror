# ADR-027：合成规范化、QA 与 identity registration 权威

## Status

Accepted — 2026-08-17

## Context

P2-M2 已将 `GenerationItem`、raw source、generation evidence 与成本冻结为生成阶段权威。
`RAW_STORED` 是带 `finalized_at` 的 M2 终态；把 M3 normalization/QA 状态追加回该实体会重写已冻结的
生成事实并混淆 execution failure 与内容 rejection。现有 `SyntheticVisionRequest` 仍以
`GeneratedImagePayload` 接收 bytes，也会错误暗示 Vision 可以直接消费 Provider raw output。

P2-M3 需要把不可信 raw source 转换为 canonical immutable synthetic Asset，保存版本化 QA evidence，
并仅在所有 hard gates 通过后原子登记 bank-independent `SyntheticIdentity`。Codex native outputs 只具备
`PROVENANCE_ONLY`，生产 image-generation Provider 仍未配置；这些限制不能阻止 synthetic-only M3
研究，也不能被改写为更强 provenance 或生产批准。

## Decision

- `GenerationItem` 与 `SyntheticSourceObject` 保持 M2 immutable authority；M3 不增加或回退其状态。
  新建 `SyntheticAssetRecord`，生命周期为
  `NORMALIZATION_PENDING → NORMALIZING → NORMALIZED → QA_PENDING → QA_RUNNING → QA_PASSED |
REJECTED → IDENTITY_REGISTERED`，另以 `NORMALIZATION_FAILED` / `QA_FAILED` 表示耗尽重试后的执行失败。
  QA 内容 rejection 不能伪装成 infra failure，反之亦然。
- `SyntheticAssetRecord` 一对一绑定一个未被删除的 raw source object。normalization 使用已批准并锁定的
  Pillow 12.3.0、版本化 normalizer config 与现有 dependency-local sanitizer primitives；输入仍受 bounded
  bytes、magic/MIME、single-frame、edge/pixel/decompression-bomb Gate。输出是 metadata-free canonical
  JPEG，必须 second-decode、重新计算 SHA-256，并写入独立
  `internal-synthetic/v1/normalized` private namespace。raw 与 normalized blob 永不覆盖同一对象。
- normalized storage 使用 create-if-absent、opaque reference 与 deterministic recovery。blob 已写而 DB
  transaction 失败时通过 deterministic reference reconciler 恢复；Asset 及 record commit 后不得修改
  storage reference、checksum、MIME、bytes、dimensions、normalizer version 或 source linkage。
- `Asset` 继续保存 canonical blob metadata，且必须满足 `owner_user_id=NULL`、`asset_role=synthetic`、
  `synthetic=true`、`internal_purpose=synthetic_dataset`。只有 normalized output 可以在 M3 创建该 Asset；
  Provider raw source 永不直接成为 Asset。
- `SyntheticQARun` 按 normalized Asset + approved `SyntheticQAPolicy` 唯一，状态为
  `PENDING → RUNNING → PASSED | REJECTED | FAILED`。`FAILED` 表示执行失败；`REJECTED` 表示已完成测量但
  一个或多个 gate 不通过。retry 使用 `Job`/`JobAttempt` envelope，不创建第二份冲突的 QA authority。
- `SyntheticQAMeasurement` 是 append-only、schema-versioned evidence，记录 measurement kind/code、typed
  payload、payload digest、algorithm/version、confidence、threshold outcome 与 reason code。landmark、pose
  与 geometry observation 通过第一方 canonical schema 保存；Provider SDK type/raw response 不得持久化。
- `SyntheticQAReviewDecision` 是 append-only operator evidence。clearly-adult presentation 必须有显式
  human review；ambiguous/minor-looking、真人 likeness risk、许可缺失或其他 hard failure必须 reject。
  人工 review 不能擦除自动 hard failure，也不能把未测量能力标记为通过。P2 不做年龄估计、颜值评分、
  race/ethnicity/ancestry/nationality 分类或真实用户推断。
- M3 hard gates 至少包括：synthetic provenance、source checksum/retention、decode/sanitize/second-decode、
  normalized checksum、exactly-one-face、pose/visibility policy、approved Vision/algorithm evidence、adult
  presentation review、license/rights 与 unresolved hard-failure absence。水印/文字、背景与基础质量若尚无
  获批自动算法，必须由版本化 human review 明确覆盖，不能记录虚构自动 measurement。
- Vision 只能消费 normalized synthetic input。第一方 port 改为 bounded normalized payload 或 opaque
  normalized-asset reference；不得接受 raw source、User Asset、URL、object key、SDK type 或任意网络
  location。deterministic Mock 仅用于 CI。任何真实 synthetic Vision candidate 必须分别通过 code、package、
  model artifact、data/license、privacy/security、platform 与 benchmark Gate。
- MediaPipe 保持 `LICENSE_REVIEW_REQUIRED`，OpenCV 保持 `POC_REQUIRED`；M3 planning 不安装依赖或下载
  权重。M3 final Gate 必须有至少一个获批 synthetic-only Vision candidate 和受控 benchmark；缺失时 M3
  不能 `PASS/FROZEN`，M4 measurement-dependent entry 保持关闭。
- `SyntheticIdentity` 增加 canonical Asset 与 accepted QA run 的唯一引用。Phase 0 generator/model/prompt/
  provenance 字段降为 nullable legacy projection，不再是 M3 authority；Codex native model/request/seed/usage/
  cost 继续为 `NULL`。新 canonical identity 只能由一个 `QA_PASSED` record 在同一 PostgreSQL transaction
  中创建，一项 canonical Asset 只能登记一个 identity。
- M3 不新增 public/internal HTTP API 或 CLI，不创建 QuestionBank、variant、isolation、duplicate/diversity
  或 real-user facial-processing authority。控制面仍是 typed application service 与 reference-only Worker
  task；M7 才提供 operator CLI。
- `SyntheticCoveragePack`、`MorphologyCoverageCell` 与 `StyleContextPack` 的 dedicated persistence 继续
  延后到 coverage/release 需要明确 membership 的 rolling-wave Milestone。M3 只保留已批准 policy/
  ontology reference 与 source provenance，不创建敏感标签或人口平均目标。

## Alternatives Considered

- 扩展 M2 `GenerationItem` 状态到 normalization/QA。
- 让 Vision 直接读取 Provider raw bytes 或任意 URL。
- 只在 `Asset` 或 JSON flag 上保存 `qa_pass=true`。
- 允许人工 review 覆盖自动 hard failure。
- 在没有 model/license evidence 时直接安装 MediaPipe 或下载 Face Landmarker。
- 继续以 legacy generator/model 字段作为 SyntheticIdentity 权威。

## Consequences

M2 的生成与成本事实保持冻结，M3 可独立重试和审计 normalization/QA，并以不可变链连接 raw source、
normalized Asset、QA evidence 与 identity。缺少 Vision candidate 不阻塞 schema、normalizer、state machine、
Mock 与安全测试实现，但会阻塞 M3 final Gate 和 M4 entry。

## Security / Privacy Considerations

全流程 synthetic-only；V01 private assets 可用于 normalization/QA，不得提交图片、Prompt、路径、object
key 或 Provider payload。normalized namespace 与 raw/user namespaces 分离。日志仅允许 opaque IDs、版本、
outcome、reason 与 aggregate；不允许 bytes、landmarks payload、Prompt、signed URL 或真实个人数据。

## Testing Implications

`0009 → 0010 → 0009 → 0010`、fresh upgrade、`alembic check`、legacy identity compatibility、immutable
lineage、state transitions、raw-retention race、normalized create-if-absent、crash recovery、hard-gate
non-bypass 与 concurrent identity registration 必须在真实 PostgreSQL/Linux 验证。OpenAPI/generated
TypeScript 保持无差异；default CI 只使用 deterministic Mock 和 checksum-bound synthetic/non-human
fixtures，零网络、零 mandatory skip。
