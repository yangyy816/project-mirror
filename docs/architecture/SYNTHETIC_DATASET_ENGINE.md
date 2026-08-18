# 合成数据集引擎（P2）

## 状态与边界

Phase 2 是 `COMMITTED`，P2-M1、P2-M2 与 P2-M3 已 `FROZEN`，P2-M4 是 `EXECUTING`。该阶段仅处理可追溯的成年合成人物资产；真人、用户资料、SelfState、问卷运行、DesiredDelta、编辑、支付、部署和公开 API 都不在范围。P2-M5 及以后仍须 rolling-wave refinement。

## 权威链

```mermaid
flowchart LR
  G["Synthetic generation"] --> R["Raw Provider evidence"]
  R --> N["Deterministic normalization"]
  N --> A["Immutable synthetic Asset"]
  A --> Q["Versioned synthetic Vision QA"]
  Q --> I["Bank-independent SyntheticIdentity"]
  I --> V["Variant and isolation evidence"]
  V --> M["Immutable QuestionBank manifest"]
  M --> X["Append-only revocation"]
```

- raw Provider output is untrusted and never becomes an Asset, identity or QuestionBank entry.
- QuestionBank is later immutable manifest membership, not SyntheticIdentity ownership.
- `Job`/`JobAttempt` supply only execution/retry/recovery; P2 authority uses typed P2 records rather than arbitrary job payload.
- normalized base, variant and released entry are separate immutable evidence layers.

## 生命周期和控制面

Generation batches use `DRAFT → QUEUED → RUNNING → COMPLETED | PARTIAL | FAILED | CANCELLED`. M2 generation items use `REQUESTED → GENERATING → RAW_STORED | GENERATION_FAILED | CANCELLED` and remain immutable after M2. M3 uses a separate `SyntheticAssetRecord`: `NORMALIZATION_PENDING → NORMALIZING → NORMALIZED → QA_PENDING → QA_RUNNING → QA_PASSED | REJECTED → IDENTITY_REGISTERED`, with distinct exhausted-retry execution failures. Provider/normalization failure never masquerades as QA `REJECTED`. Future variants use `SPECIFIED → GENERATING → GENERATED → MEASURED → ISOLATION_PASSED | REJECTED`; future QuestionBank releases use `DRAFT → UNDER_REVIEW → RELEASED → REVOKED`.

The P2 control plane is application service plus a later restricted CLI, not public/internal HTTP. Provider/storage access remains private, typed and adapter-mediated. P2-M3 may create only canonical normalized synthetic Assets, versioned base QA evidence and bank-independent SyntheticIdentity registrations. It does not create variants, isolation/diversity evidence, QuestionBank releases, model approval or real-user processing authority. Complete M3 authority is in ADR-027.

## 研究边界

MVR-v1 counts, repeatability, supported 2D dimensions, tolerance, near-duplicate threshold, diversity saturation and Provider quality are provisional research/operational targets. They are not product invariants or M1 acceptance claims. P3 remains blocked on separate real-data Legal, Consent, PIPIA, Security and Provider Gates.

## China-first coverage contract

首个内部 synthetic coverage package 采用 `MarketScope=CN_MAINLAND` 与候选标识
`CN_EAST_ASIAN_PRESENTATION_V1`。它只描述 China-market-first、declared-adult、synthetic female
stimuli 的生成/评估范围；其人工视觉呈现边界由当前版本化 rubric（一般非性感 cohort 为 ADR-030）
约束。该 scope 不是 ancestry、nationality、ethnicity、race 或真实用户分类，也不宣称代表全部中国
女性。

架构必须分离：

- `MarketScope`：市场、语言与运营语境；
- `SyntheticCoveragePack`：仅适用于 synthetic assets 的 versioned presentation/release scope；
- `MorphologyCoverageCell`：由 GeometryOntologyVersion 约束的连续 measurement ranges；
- `StyleContextPack`：与 morphology 分离的可替换摄影、妆容和 styling context。

首包不能由一个平均/典型脸派生；24→48→96 cohort 必须分布于多个 morphology cells，并记录
occupancy、coverage gap、nearest-neighbor、duplicate、generation/QA/transform/isolation yield 与
Provider-version effects。QuestionBank candidate 先受 pack scope 约束，再按 target dimension、
non-target morphology similarity、Local Morphological Neighborhood、isolation 和 QA evidence 选择，
不能只因共享 broad presentation scope 而配对。

P2-M1 只冻结这些 first-party contracts，不新增表或 API。后续 Milestone refinement 决定 pack/cell/
style 的 typed/persistence 形态和 immutable manifest binding；所有未来 packs 复用同一 ontology、
provenance、QA、isolation、release/revoke 与 no-sensitive-routing 规则。完整决定见 ADR-024。

ADR-028 为首包增加版本化年龄呈现控制：18–25 是 clearly-adult primary presentation target，
26–30 仅在 coverage 需要时作为 secondary，31–34 de-emphasized，明显 35+ 从首包 selection 排除。
其 v1 universal `minor ambiguity` hard reject 已由 ADR-030 对未来一般非性感 cohort 前向取代；
childlike 与 schoolgirl framing 仍拒绝。该轴由 Prompt 与人工 review 约束，不是年龄估计；不得通过
幼态化、单一模板脸或损失 morphology/identity diversity 实现年轻化。

ADR-029 为独立的 style-aware cohort 增加多峰、非打分式视觉方向。Style context 只描述可替换的
presentation、styling、lighting 与女性向问卷 product fit；它不拥有 identity、morphology、QA 或
路由 authority。首版允许 `PURE_CLEAN_NATURAL`、`GENTLE_SWEET_APPROACHABLE`、
`REFINED_ELEGANT`、`SOPHISTICATED_URBAN`、`GLAMOROUS_STRIKING`、`CHARMING_ALLURING`、
`ADULT_SAFE_SEXY` 与 `INTELLECTUAL_ELEGANT_LIGHT_MATURE` 八个非排他 context。任何 beauty/
attractiveness score、percentile、ranking 或统一理想脸均禁止；adult/minor safety 是 hard gate，
style/product mismatch 只作为首包 soft curation exclusion。现有 V01 与 age-only V-next evidence 不
重写、不覆盖、不追溯重标。

ADR-030 通过 v2 policy 前向修订一般非性感 cohort 的人工年龄呈现边界：round face、babyface、
soft features 或其他 youthful adult traits 本身不再触发拒绝；只有整体明确呈现为未满 16 岁，或
出现儿童/学生未成年语境时 hard reject。该分类不是自动年龄估计，identity 仍声明为 synthetic
adult。`ADULT_SAFE_SEXY`、`CHARMING_ALLURING` 与任何 intimate/sexualized context 保留严格的
unambiguous 18+ overlay，不能使用可能呈现为 16–17 岁的主体。所有 v1 evidence 保持不可变。

ADR-031 为 Codex native tool 未暴露 requested dimensions 的未来 cohort 增加前向 admission v2。
未知 requested width/height 与 match fact 必须保持 `NULL`，observed dimensions 单独记录；不得把
实际输出冒充请求参数或在 raw admission 前裁切。MIME、checksum、byte、edge、pixel、single-frame、
private source-root 与 decode gates 不变，v1 manifest/evidence 继续冻结。

## Reference research boundary

网络、文献和获授权市场研究默认只提取人工复核的 abstract non-identifying descriptors，再进入
GenerationPolicy 或未来 StyleContextPack。真人 reference 默认
`PROHIBITED_FOR_DATASET_GENERATION`；禁止抓取社交媒体/搜索结果/名人/网红/未知许可肖像，禁止
identity seed、face swap、one-to-one template 与 identifiable-person prompt。

未来若 reference 必需，必须先经独立 restricted licensed-reference Gate，分别证明版权、成年 model
release、portrait/privacy、AI/derivative/commercial/storage/retention/territory/revocation rights；即使
获清权也默认 `REFERENCE_RESEARCH_ONLY`。source pixels 默认不保存、不进 Git，likeness-risk output
不得进入 SyntheticIdentity、QuestionBank、golden fixtures 或 public product assets。
