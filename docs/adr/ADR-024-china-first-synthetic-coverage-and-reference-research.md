# ADR-024：China-first 合成覆盖与参考研究边界

## Status

Accepted — 2026-08-16

## Context

Project Mirror 首发面向中国大陆，首个内部 synthetic corpus 与 QuestionBank candidate pool
需要服务中国市场语境，但现有 P2 合同尚未明确区分市场范围、合成视觉呈现范围与连续形态覆盖。
若把本地化范围压成粗糙人口类别、真实用户标签或单一“典型脸”，会违反 No Sensitive
Inference、No Sensitive-trait Routing 与 Anti-homogenization。公开真人图片也不能成为快速补齐
覆盖的捷径。

## Decision

- 首个内部 coverage package 采用 China-first 产品范围：`MarketScope=CN_MAINLAND`；其候选
  内部标识为 `CN_EAST_ASIAN_PRESENTATION_V1`，只描述 clearly-adult synthetic female
  stimuli 的 East-Asian-presenting 生成范围，不代表 ancestry、nationality、ethnicity、race、
  biological truth 或对中国女性的普遍代表。
- 三个轴必须分离：MarketScope 表达市场/语言/运营语境；SyntheticCoveragePack 表达仅适用于
  synthetic assets 的 presentation/generation/release 范围；MorphologyCoverageCell 表达由
  GeometryOntologyVersion 定义的连续、可测量形态区间。StyleContextPack 与 morphology 分离，
  同一 synthetic identity 可在多个 style context 下复用。
- 连续 morphology measurement 是 generation targeting、coverage、local-neighborhood matching、
  duplicate/mode-collapse、variant/isolation 与未来 SelfState compatibility 的主要技术依据。
  broad presentation scope 不能替代 measurement，也不得构造人口平均脸、审美标准或单一典型脸。
- Project Mirror 不创建 race/ethnicity/ancestry/nationality classifier，不从真实用户照片推断或
  持久化这些属性，也不将其用于 User、BaselineFaceModel、SelfState、AestheticProfile、routing、
  memory 或 analytics。未来用户只能显式选择非敏感的 reference scope；默认 China-market pool
  内仍按 continuous SelfState geometry、reliability、uncertainty 与 Local Morphological
  Neighborhood 选择 stimuli。
- `SyntheticCoveragePack` 是 versioned、pack-extensible、release 后不可变的第一方治理概念；
  material policy 或 membership 变化创建新版本。P2-M1 只冻结合同，不增加数据库表或公开 API。
  现有 SyntheticGenerationPolicy 与 GeometryOntologyVersion 保存可校验的 policy/ontology authority；
  dedicated persistence、typed value objects、manifest membership 与 StyleContextPack schema 由对应
  后续 Milestone rolling-wave refinement 决定，不能由实现 Worker 自行新增。
- 24→48→96 cohort 按多个 morphology coverage cells 分配并记录 occupancy、underrepresentation、
  nearest-neighbor、duplicate、generation/QA/transform/isolation yield 与 Provider-version effects。
  anti-stereotype/anti-homogenization 通过连续覆盖与 style separation 证明，不通过敏感标签实现。
- 网络/文献/获授权市场研究默认只产生经人工复核的抽象、非识别 descriptors，再进入版本化
  GenerationPolicy 或 StyleContextPack。禁止抓取、下载或摄入社交平台、搜索结果、名人、网红、
  未授权 stock 或未知许可真人肖像；公开可访问不等于获准。
- 真人 reference 默认 `PROHIBITED_FOR_DATASET_GENERATION`，不得作为 identity seed、face-swap
  source、QuestionBank asset、fixture、model artifact 或 production generation input。未来若证明
  必需，只能通过独立 restricted licensed-reference Gate，并分别证明 copyright/license、adult
  model release、portrait/privacy、AI processing/derivative/commercial/storage/retention/territory/
  revocation rights。任一缺失即 `REQUIRES_LEGAL_REVIEW` 或 `PRODUCTION_BLOCKED`。
- 获清权 reference 仍默认 `REFERENCE_RESEARCH_ONLY`，优先提取 aggregated non-identifying pose、
  lighting、makeup、palette、region-style 与 broad morphology descriptors；禁止精确人物复现、
  celebrity/influencer imitation、one-to-one template 或真实姓名 prompt。若受控研究产生 likeness
  risk，输出不得进入 SyntheticIdentity、QuestionBank、golden fixture 或 public product asset；
  automated metric 不能单独构成法律充分性。
- 后续 coverage packs 复用同一 GeometryOntology、provenance、synthetic-only、QA、isolation、
  release/revoke 与 no-sensitive-routing 规则。cross-pack evaluation 只检测工程性能差异和 coverage
  gaps，不进行审美排名。

## Alternatives Considered

- 用一个平均或“典型”中国面孔派生首个 corpus。
- 把 broad presentation label 作为 morphology measurement 或用户 routing variable。
- 把中国妆容/摄影 style 与 morphology 合并为一个不可分标签。
- 抓取公开真人肖像或直接使用单一真人作为 synthetic identity template。
- 在 P2-M1 尾声立即为所有候选概念新增表和 API。

## Consequences

首个 corpus 是 China-market-first、East-Asian-presenting、synthetic-only，同时底层保持连续形态、
pack-extensible、non-sensitive、non-identifying 与 globally expandable。P2-M1 只增加 governance 和
domain contract；M1 代码、`0008`、DAG、依赖、模型和 fixture 不变。后续 M2–M6 refinement 必须决定
pack persistence 与 release binding，并显式披露首包覆盖、空白、Provider bias、measurement/pose/3D
限制及未完成的 questionnaire validation。

## Security / Privacy Considerations

不得将真人 pixels、社交媒体 URL、真实姓名 prompt、敏感群体推断或 classifier artifact 写入 Git、
fixtures、Prompt authority、logs、model registry 或 corpus。未来 ReferenceResearchRecord 在没有存储
批准时只保存 source authority、rights/review status 与抽象 descriptors；source pixels 默认不保存。
发现来源不明 artifact 时只 quarantine、报告和复核 provenance，不自动删除或悄悄纳入。

## Testing Implications

后续 P2 negative scans 覆盖 scraped portraits、social-media face-source URLs、celebrity-name prompts、
unlicensed real-person references、race/ethnicity classifier artifacts 与 real-user images。Coverage QA
按 cell 输出 occupancy/yield/duplicate/isolation/Provider evidence，并验证 released pack immutability、
known-limitations disclosure 与 no-sensitive-user-routing。P2-M1 当前只验证文档一致性以及零依赖、
零模型、零真人图片和 P1/`0008` implementation unchanged。
