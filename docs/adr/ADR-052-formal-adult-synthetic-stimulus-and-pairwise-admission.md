# ADR-052：正式成年合成刺激、Pairwise 可比性与 Demo 准入

## Status

Accepted — 2026-08-29

## Context

P2 已有 China-first synthetic coverage、年龄呈现 v1/v2 与多峰 style policy，但它们没有形成一份同时
约束正式 QuestionBank、pairwise comparison 和本地 Demo 选图的长期准入合同。现有 ADR-030 还允许一般
非性感研究 cohort 在没有儿童/学生语境时保留 youthful、round-face 或 babyface presentation；该边界不能
自动等同于正式偏好题库的 18+ admission。

Project Owner 现要求正式刺激统一为 18–25 岁声明成年合成人物，以 20–25 为主体，同时固定拍摄语法、
分离 geometry/style pair、要求 pair 两侧均具产品可接受的完成度，并保留 morphology、identity 与 style
多样性。Owner 文本中的 `18 -16: 10%` 与 `ADULT_ONLY_18_TO_25`、禁止未成年人进入偏好学习以及正式
admission 仅允许两个成年 band 直接冲突，必须 fail closed 处理。

## Decision

### Forward-only authority

- 新权威为 `P2_QUESTIONBANK_GENERATION_POLICY_V3`。它前向适用于所有新正式 QuestionBank 候选、
  pairwise comparison、AestheticProfile synthetic input、Project Mirror 本地 synthetic Demo 选图，以及
  为这些用途生成的新 synthetic face。
- ADR-024、ADR-028、ADR-029、ADR-030、age/style v1/v2、V01、既有 Prompt、attempt、图片、manifest 和
  provenance 均保持不可变。V3 缩小未来正式用途的准入范围，不追溯重标历史研究 evidence。
- 在新正式 QuestionBank、pairwise stimulus、AestheticProfile synthetic input 与 Web Demo 选图范围内，
  V3 是比 ADR-029/030 更窄的 forward overlay：ADR-029 的 style descriptors 只有满足 V3 成年与非性化
  限制时才可使用；ADR-030 的一般非性感 research-cohort 边界不得替代 V3 的 18+ formal admission。
- 正式用途只允许 `ADULT_18_19` 与 `ADULT_20_25`。`ADULT_20_25` 默认目标约 70%，`ADULT_18_19`
  默认目标约 20%，剩余约 10% 是只能分配给这两个成年 band 的 cohort flex，不是第三个年龄 band，绝不
  能由 16–17 或其他未满 18 岁样本填充。
- `adult_status=VERIFIED_SYNTHETIC_ADULT` 表示 synthetic provenance、声明成年和版本化人工 presentation
  review 全部通过，不是生物年龄证明或自动年龄估计。正式准入要求 `suspected_minor=false`；任何疑似
  未成年、儿童/学生未成年语境或声明年龄 band 不匹配均 hard reject。
- 18–19 岁 band 只允许自然、清爽、温柔、甜美、冷感等非性化表达。轻熟、妩媚或类似成年风格只允许
  `ADULT_20_25`，但全题库仍禁止性感挑逗、色情暗示、身体展示、fetishized framing 或其他性化手段。

### Synthetic presentation and capture grammar

- 首包继续使用 ADR-024 的 China-market-first、East-Asian-presenting synthetic presentation scope。
  该 scope 不是 race、ethnicity、ancestry、nationality、真实用户标签或路由分类；不得从真实用户照片
  推断这些属性。可扩展的亚洲视觉变化仍通过 synthetic presentation、连续 morphology 与 style coverage
  表达，不能收敛为单一韩国网红脸模板。
- 除非被测 dimension 明确需要变化，所有正式刺激固定正面朝向、直视镜头、中性或轻微自然表情、稳定
  肩颈、等价头部占比和焦段感、柔和稳定光线、简洁中性背景、统一近景构图、轻度自然妆面、低干扰服饰，
  并拒绝 pose、背景、发型、妆容、配饰或滤镜主导选择的样本。

### Pair types and fair comparison

- `GEOMETRY_PAIR` 优先使用同一 canonical synthetic base identity，并保持 age band、pose、expression、
  background、lighting、camera/framing、hair、makeup 与 clothing 等价。每个 pair 只改变一个主要 geometry
  dimension；最多允许一个声明且确有必要的 correlated variable。所有非目标 geometry 必须通过版本化
  isolation evidence。
- `STYLE_PAIR` 保持主要 facial geometry 与 identity 不变，只改变一个版本化 style direction。不得用大幅
  妆容、发型、服饰、姿态、表情、曝光或背景差异替代 style control；生成式 style 结果仍须重测 geometry
  drift。
- Pair 两侧都必须通过相同 source、rights、decode、QA、adult、visual-finish、likeness、duplicate、
  anti-homogenization 与 comparability Gate。任何一侧明显失败、低完成度、结构异常或成为“一眼错误答案”
  时整个 pair 拒绝，不得以降低阈值或保留较好一侧修复。

### Product acceptance without beauty scoring

- 产品接受度只使用 categorical rubric：结构自然、完成度合格、具有可解释辨识度、适合公平比较。禁止
  beauty/attractiveness score、ranking、percentile、真实用户外貌评价或统一理想脸。
- cohort 运营目标约为 70–80% 清爽协调且完成度较高、15–25% 辨识度明显且仍具良好接受度、最多约
  10% 中性普通边界样本。该分布只用于 pack-level curation，不产生 per-face 数值或排序。
- 年轻化不得通过 infantilization、homogenization、模板脸或损失 morphology/identity/style coverage 实现。

### Metadata, Prompt and release boundaries

- 每个候选记录 V3 定义的 synthetic identity、声明年龄 band、adult status、presentation context、style、
  geometry、controlled/preserved variables、source/provider facts、policy/version/digest、QA/rejection、pair、
  base-family reference，以及 formal admission 实际消费的 source-rights、decode/QA、likeness、duplicate、
  visual-quality、comparability、isolation 与 anti-homogenization 结果。Provider/model/seed 等实际不可获得的
  事实必须为 `NULL`，不得把
  `CODEX_NATIVE_IMAGEGEN` 伪装为 runtime `ImageGenerationProvider`。
- Git 可保存 first-party policy、required/forbidden Prompt semantics、opaque references、digests、checksums
  和 allowlisted aggregate evidence；完整 Prompt、seed value、图片、private locator、object key、signed URL、
  Provider raw payload 与凭据不得进入 Git、MEMORY、普通日志、公开 artifact 或 UI。
- M6 refinement 必须把 V3 policy/rubric、pair type、source/result checksum、isolation、QA 与 admission facts
  绑定到 immutable manifest entry。该 ADR 不提前创建 M6 schema、migration、公开 API 或 release。
- 本地 Web Demo 只能使用预生成、已通过同等 hard gates 的 synthetic assets，必须标记为 internal/research
  demonstration；真实用户运行时 generation 调用为 0，不得宣称 production validity 或正式训练数据。

### Active M5 boundary

- R39 基线保持 accepted，`CAL-REQ-002` 保持未消费。旧 private generation specification 不得用于新的
  dispatch；必须先通过 `CC-P2-M5-05-A` materialize 新 private policy/Prompt/rubric version 并验证 digest、
  assignment、custody、zero-leakage 与 register-before-decode Gate。
- 本决定本身生成 0 张图片，不打开 M5 technical Gate、MVR、M6、QuestionBank release、production geometry、
  production Provider 或 real-user facial processing。

## Alternatives Considered

- 将冲突行解释为 16–17 岁的 10% 正式样本。
- 直接覆盖 ADR-030 或重写既有 v1/v2 evidence。
- 只在 Prompt 中追加“young”而不版本化 pair、admission 和 Demo 规则。
- 用 beauty score 或一侧明显更差的 pair 提升选择率。
- 立即新增 M6 表、public API 或生产 Provider。

## Consequences

正式刺激获得一个可审计、成人-only、China-first、可公平比较且防同质化的前向合同。M5 必须先完成
private V3 materialization 才能继续 generation；M6 将在 entry Gate 通过后的 rolling-wave refinement 中决定
typed persistence 与 immutable manifest。当前依赖、模型、migration head、OpenAPI、生产 fail-closed、
QuestionBank release 和真实用户边界均不改变。

## Security / Privacy Considerations

禁止真人 reference、真实未成年人、名人/公众人物 imitation、社交/搜索肖像、敏感身份推断、自动年龄
估计、私有 Prompt/seed/locator 泄漏和任何未获权利的 source。发现年龄、provenance、likeness、pair isolation
或 metadata 不一致时 fail closed 并保留不可变 attempt/rejection evidence，不得删除失败事实或人工覆盖 hard gate。

## Testing Implications

- machine-readable V3 policy 必须通过 canonical digest、age-band、distribution、pair isolation、Prompt semantic、
  metadata、Demo zero-runtime-generation 与 privacy negative tests。
- 证明历史 v1/v2 文件、OpenAPI、migration 与依赖不变。
- M5 private materialization 前验证 `CAL-REQ-002` 未消费且 image generation calls 为 0。
- 后续 admission tests 必须分别覆盖 suspected minor、student/minor context、18–19 style restriction、pair
  contamination、one-sided quality failure、template collapse、Prompt/seed/locator leakage 与 provider-fact NULL 保真。
