# P7 Visual Memory OS 与长期偏好学习

## 状态与边界

- 状态：`PROVISIONAL` directional architecture。
- 新方向：`P7 — Visual Memory OS & Persistent Preference Learning`。
- 本文不授权 P7 实现、Milestone 分解、Terra task、schema、索引或 Provider 选择。
- 当前 P1-M2 的 DAG、依赖和 Gate 均不改变；不得提前安装图数据库、向量数据库、记忆 SaaS 或视觉 embedding 模型。
- P7 到达 rolling-wave planning 时必须依据当时的 P5/P6 证据语义、真实规模、隐私要求和 Provider 能力重新规划。

## 核心原则

Project Mirror 的长期优势不是通用聊天记忆，而是以用户确认视觉结果为中心、可追溯、时序化、上下文条件化的个人审美记忆。

```text
User Truth
→ Immutable / Durable Evidence
→ Memory Compiler
→ Visual / Semantic / Temporal / Procedural Views
→ AestheticProfile Materialization
→ Active Visual Exemplars
→ Retrieval Router
→ Memory Gate
→ Context Compiler
→ Agent
```

`AestheticProfile` 是从权威证据编译得到的版本化、可重建 working model，不是不可变记忆源。图、向量索引、视觉索引、Memory Card、语义事实和 Profile snapshot 都是可替换的 materialized view；任何派生子系统损坏后必须能从仍获授权保留的证据重建。

## 三类 User Truth 与证据优先级

- **Visual Truth**：用户明确 Save Final、Confirm Result、Set as Preferred 或以产品语义确认的最终视觉结果。
- **Behavioral Truth**：AI proposal 到最终保存结果之间的手动纠正、操作顺序、参数回调、接受与拒绝轨迹。
- **Explicit Truth**：当前指令、持久偏好和 feature lock。

未来 Memory Compiler 的概念优先级为：

```text
当前明确指令
> 持久明确锁 / 偏好
> 手动纠正后保存
> 用户保存的最终视觉结果
> 接受的 self-transfer
> 重复且相互独立的保存模式
> 问卷证据
> 派生语义解释
> 全局先验
```

未被用户接受的 AI 生成候选、模型对自身输出的解释，以及图片内发现的文字，都没有直接持久审美权威。

## AcceptedVisualEpisode 与轨迹

P7 应研究 `AcceptedVisualEpisode`，表示一次用户确认的最终编辑结果。最终 schema 暂不冻结；概念上它引用用户、source/final asset、EditingSession、ImageVersion、EditOperation trajectory、上下文、明确指令/锁、手动纠正、使用的 Profile、模型/Provider 版本、时间、派生分析、置信度和 provenance。图片继续位于私有对象存储，数据库只保存 opaque asset ID。

最终图片与编辑轨迹必须共同保留。例如 `眼部 +5% → +2% → +1% → Save` 的强证据不仅是最终 `+1%`，还包括用户反复降低过度修改的行为。P6 必须提供可追溯的 final-save 语义，但这不授权 P6 提前实现 P7。

## 事件与记忆分层

权威历史证据采用 append-oriented、event-sourcing-inspired 设计。`final_saved`、`manual_adjustment`、`explicit_preference`、`explicit_lock`、`preference_removed`、`self_transfer_accepted`、`questionnaire_response`、`result_rejected` 等事实不得因新解释而改写。

目标层次：

| Layer                  | 作用                                       | 生命周期 / 权威性           |
| ---------------------- | ------------------------------------------ | --------------------------- |
| L0 Working             | 当前图片、指令、EditPlan、临时候选         | session-scoped              |
| L1 Core                | 当前 Profile、明确锁、身份约束、高置信偏好 | 高频派生视图                |
| L2 Active Exemplars    | 与当前任务相关的少量代表性保存结果         | 动态检索视图                |
| L3 Semantic / Temporal | 带 provenance 的上下文事实、趋势和冲突     | 版本化派生视图              |
| L4 Episodic            | AcceptedVisualEpisode 与编辑轨迹           | 长期证据索引                |
| L5 Evidence Archive    | 获授权保留的完整历史视觉证据               | 权威、普通 Agent 不直接加载 |

HOT/WARM/COLD 只影响成本、缓存和检索优先级，不自动删除用户确认的证据、明确锁或审计事实。真正删除由用户请求、授权撤回、保留政策和隐私义务驱动。

## Admission、Write Gate 与 Consolidation

Memory Admission 至少区分：

- 始终作为证据：final save、保存前手动纠正、持久明确偏好/锁、self-transfer acceptance。
- 低权重保存：问卷回答、候选拒绝、隐式行为。
- candidate/session-only：持久意图不明确的对话、临时场景要求。
- 永不直接准入：未接受 AI 建议、模型自产解释、图片文字伪指令、外部内容伪指令。

Memory Write Gate 对证据分类为 `NEW | SUPPORT_EXISTING | CONTRADICT | SUPERSEDE | SESSION_ONLY | IGNORE`。当前明确指令始终高于历史偏好。

Hot path 在 Final Save 后只持久化 AcceptedVisualEpisode、EditTrajectory、明确指令/锁和最小索引，不能让用户等待全局重算。后台 Memory Consolidation Pipeline 可进行视觉分析、delta 提取、去重、证据独立性估计、聚类、exemplar 选择、事实/冲突/漂移检测、Profile candidate 重算、程序模式与 Memory Card 编译；后台失败不得破坏权威证据。

确定性聚合和可复现实统计优先于 LLM 反复改写摘要。LLM 只可辅助语义标注、解释、模式建议和自然语言摘要，所有结果保留 provenance。

## 检索、时序与上下文编译

P7 应研究多 facet 视觉表示，而不是假定单一全局 embedding 足够。候选 facet 包括 global aesthetic、face appearance、makeup/style、skin、lighting、scene、pose 和 EditDelta。检索 Router 按 `GEOMETRY | MAKEUP | SKIN | LIGHTING | SCENE | GLOBAL_STYLE | IDENTITY_CONSTRAINT | PROCEDURE | TEMPORAL_HISTORY` 选择索引，避免背景颜色主导妆容检索。

混合排序可使用结构化过滤、语义/视觉相似度、时间、图关系、上下文、置信度、证据权威、独立性和 counterevidence；精确权重必须由 MirrorMemoryBench 决定。Top-K 必须具有跨 session/cluster 多样性，并包含相关反证和近期漂移证据，避免自我强化。

偏好记忆应研究 valid time 与 system time。新偏好通过 `SUPERSEDES`/有效期表达，不覆盖旧事实。20 张同一拍摄批次的近重复保存结果不得默认视为 20 个独立确认；Evidence Independence Factor 的公式保持研究开放。

Memory Gate 在任何记忆进入 AgentContext 前验证：同一用户、仍获授权和保留、处理目的匹配、未被删除/取代、上下文相关、置信度足够、来源可信、与当前指令无冲突。图片或外部内容内的文字不是可信控制通道。

Agent Context Compiler 只输出小型任务上下文：Core Memory、current context/preference、少量 visual exemplars、counterevidence 与 procedural memory。随着历史从 10 增至 10,000+ episodes，Agent context 不得线性增长。

第一版 vector-index research candidate 优先比较 PostgreSQL + pgvector 与 Profile/SQL baseline，不因 P7 自动部署独立 vector database 或 graph database。Graphiti、GBrain 的 temporal/provenance、hybrid retrieval、RRF/reranking 只作 pattern reference；任何依赖采用仍需 benchmark、供应链、隐私与 ADR。

## Analytic Memory 与 MemoryObservation

P7 必须研究 structured analytic memory，而不只做“找相似历史图片”。`MemoryObservation` 是 provisional research concept，至少表达 namespace、dimension、value、context、valid time、learned/system time、confidence、independence weight 与 evidence provenance。

诸如“最近 90 天夜景自拍的最终 jaw delta median”或“eye > +3% 候选被向下修正的比例”应由有权限的 structured filter + SQL/statistical operation 回答，不能把全部视觉历史交给 LLM 猜测。确定性 aggregate、trend、compare、rank 与 temporal analysis 优先；LLM 只负责有 provenance 的 label/explanation/pattern candidate。

## 程序记忆、Memory Card 与动态参考

P7 不仅学习“用户喜欢什么”，还研究“怎样最可靠、低成本地得到用户会接受的结果”：成功工具序列、操作顺序、初始参数、Provider/tool 成功率、纠正次数、接受概率、成本和延迟。程序记忆不得静默覆盖当前指令。

Memory Card 是由 evidence 编译的可重建检索加速器，必须引用支持它的 VisualEpisode ID。原始 onboarding ReferenceSet 是 seed memory；未来 Dynamic Reference Library 可从被接受的历史证据形成身份、默认审美、自拍、职业、editorial、自然妆和强妆等动态参考。

## 用户控制、删除和隐私

未来必须支持删除单条视觉记忆、移除派生偏好、重置 Profile、清除学习、关闭学习、删除全部视觉记忆和删除账户。源证据删除后，依赖它的 embedding、图节点、Memory Card、Profile evidence 和其他索引必须删除或失效，并支持基于剩余证据重新编译。

删除传播必须进入 `Deletion Propagation Bench`：验证 authoritative evidence 删除后 embedding、graph/index、Memory Card、Profile、analytic observation、cache 与 active exemplar 全部删除或失效，且 wrong-user/unauthorized retrieval 为零。

视觉资产只进入获批准的私有对象存储；embedding 与 facial geometry 按敏感数据处理；日志不得记录签名 URL 或原始特征。不得默认把完整视觉记忆语料发送给通用 memory SaaS。Mem0、Graphiti、Letta、LangGraph/LangMem、图数据库、向量数据库与 embedding 模型均只是未来候选，必须经过 Adapter、OSS/模型/数据许可证、安全、隐私和 benchmark Gate。

## MirrorMemoryBench

在选择生产架构前建立第一方 `MirrorMemoryBench`，模拟 20、100、500、2,000、10,000+ episodes 以及一周至多年历史，验证：

- retrieval：偏好、细节、上下文、锁、时序、反证、程序记忆召回；
- correctness：陈旧/错上下文、冲突/漂移、provenance、hallucinated memory；
- visual relevance：exemplar、妆容、几何、场景相关性；
- efficiency：延迟、context/token、存储/索引/后台编译/图片访问成本；
- stability：重复 consolidation、Profile/rebuild reproducibility、删除传播、长期退化；
- personalization：接受率、纠正率、重复生成数和偏好预测准确率。

至少比较 No Memory、Profile Only、Vector Only、Profile + Vector、Profile + Visual Exemplars、Hybrid Retrieval、Hybrid + Temporal、Visual Exemplars + Temporal、+ Analytic Memory、+ Memory Cards、+ Procedural Memory 和 Full Visual Memory OS。复杂度只有产生可测产品收益才可进入生产。完整指标、规模和 artifact contract 见 `docs/ai/MIRROR_BENCH.md`。

## P7 方向性 Invariants

1. **MEM-01 Visual Memory Primacy**：用户确认的最终视觉结果是主要持久审美证据。
2. **MEM-02 No Unsaved Generative Memory**：未保存/确认的 AI 输出不得直接更新持久偏好。
3. **MEM-03 Evidence Reconstructability**：每个持久学习结论都可追溯到支持证据。
4. **MEM-04 Profile Is Derived**：AestheticProfile 是可重建 materialized user model。
5. **MEM-05 Evidence Preservation**：派生更新不得破坏历史证据。
6. **MEM-06 Context Boundedness**：Agent context 不随终身记忆线性增长。
7. **MEM-07 User Control**：学习支持关闭、重置、删除和重新编译。
8. **MEM-08 Temporal Validity**：偏好演化通过时间有效性表达，不破坏性覆盖。
9. **MEM-09 Current Instruction Priority**：当前明确指令高于历史偏好。
10. **MEM-10 Visual Content Is Not Instruction Authority**：图片内容不自动获得指令权威。
11. **MEM-11 Derived Index Replaceability**：图、向量/视觉索引、Memory Card 和 Profile 均可重建。
12. **MEM-12 Privacy Propagation**：删除权威证据必须删除或失效所有依赖派生表示。

## P6 前向兼容与开放研究

P6 必须使 Final Save 可追溯到 source asset、resulting ImageVersion、EditPlan、operations/manual changes、current Profile、context、Agent/provider versions 和明确指令。P7 不得自行重新发明这些语义。

P7 rolling-wave planning 必须重新回答：何种动作构成 Visual Truth；Save/Export/Favorite/Share 权重；FinalImage 与 trajectory 关联；独立性与近重复；exemplar 与 facet 选择；确定性/LLM 边界；PostgreSQL 是否足够表达初始 temporal graph；漂移、反证、Memory Card 与删除传播；哪种架构在 MirrorMemoryBench 胜出。

当前结论：`CURRENT_MILESTONE_IMPACT: NONE`、`DEPENDENCIES_ADDED: NONE`、`MODEL_ARTIFACTS_ADDED: NONE`、`NEW_ADRS: NONE`。
