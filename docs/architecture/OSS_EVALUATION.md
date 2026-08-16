# OSS Evaluation Registry

## Purpose and decision rule

Project Mirror 的复用原则是：复用成熟的通用基础设施，保留个性化审美智能。`SelfState`、`DesiredDeltaProfile`、`StyleProfile`、`IdentityConstraints`、证据优先级、self-transfer、anti-homogenization、Profile 版本与 PreferenceEvent 语义始终由 Project Mirror 持有，第三方库不得重新定义这些领域语义。

重大候选采用 `RESEARCH_ONLY → CANDIDATE → isolated PoC → MirrorBench/ablation → license/privacy/security/cost review → ADR → APPROVED` 的 Principal 决策链；风险项还可标为 `PRODUCTION_BLOCKED`、`REJECTED` 或 `REQUIRES_LEGAL_REVIEW`。PoC 成功不等于生产批准，高影响依赖进入生产前需要 ADR。

每次评估必须记录组件、权威 upstream、组织、候选版本、用途、目标 Phase、代码/模型/数据许可证、传递依赖、商业与再分发权利、SaaS 影响、隐私、网络/遥测、安全、维护、替换成本、平台支持、benchmark、决定、ADR 和复核日期。

外部研究结论还必须记录 `SOURCE`、`SOURCE_TYPE`、`ACCESSED_AT`、`CLAIM`、
`CLAIM_STATUS`、`REPRODUCED`、`PROJECT_MIRROR_EVIDENCE`、`LICENSE_EVIDENCE` 和
`CONFIDENCE`。`CLAIM_STATUS` 只允许 `UPSTREAM_CLAIM`、`INDEPENDENTLY_VERIFIED`、
`PROJECT_MIRROR_REPRODUCED`、`INFERENCE` 或 `UNVERIFIED`；没有 Project Mirror
reproduction artifact 的候选不得写成已证明适用。

## Provisional registry

| Component                                                       | Intended Phase / purpose                  | Current classification                | Required evidence before adoption                                                   |
| --------------------------------------------------------------- | ----------------------------------------- | ------------------------------------- | ----------------------------------------------------------------------------------- |
| MediaPipe / Face Landmarker                                     | P2-M3/P3 landmark、姿态与几何输入         | LICENSE_REVIEW_REQUIRED / POC_BLOCKED | package/runtime、bundle checksum、传递依赖、数据权利与隔离运行证据仍须闭合          |
| OpenCV                                                          | P2-M4/P3/P5/P6 确定性变换、warp、mask、QA | POC_REQUIRED                          | Python 3.13、Windows/Linux/Docker、wheel/SBOM、性能、确定性、替换边界               |
| imagededup                                                      | P2-M5 duplicate candidate                 | REJECT                                | 不采用依赖链；后续仅第一方实现 exact SHA-256、pHash、Hamming 与候选证据             |
| Konva / React-Konva                                             | P6 Web canvas                             | CANDIDATE                             | bundle、性能、可访问性、维护与 ImageVersion DAG 集成；不得成为状态权威              |
| miniPaint                                                       | P6 editor patterns                        | RESEARCH_ONLY / REFERENCE             | 只研究交互和工具组织；深度复用需单独 ADR                                            |
| Filerobot Image Editor                                          | P6 UX prototype                           | PROTOTYPE CANDIDATE                   | 与 React-Konva 对照评估；不得同时无决策引入两套框架                                 |
| Uppy                                                            | P1-M3 upload UX                           | HIGH-PRIORITY CANDIDATE               | M3 时评估；不得绕过 UploadIntent、quarantine、归属、校验与审计                      |
| tus / tusd                                                      | P1-M3/M4 或 iOS resumable upload          | DEFERRED CANDIDATE                    | 只有网络/产品测量证明普通签名上传不足时评估                                         |
| OpenAI Agents SDK                                               | P6 Agent orchestration                    | CANDIDATE                             | 与直接 orchestration 对比；必须位于 `AgentRuntimeProvider` 类边界后                 |
| PerTouch / RetouchIQ / IEA / InstantRetouch / Agentic Retoucher | P6 retouch baselines                      | RESEARCH_ONLY / REFERENCE             | 逐项核验 upstream、code/model/data；进入 MirrorRetouchBench 前不得安装              |
| MagicMakeup                                                     | P6 makeup-transfer baseline               | RESEARCH_ONLY / REFERENCE             | 完整代码、foundation model、weights、data、auxiliary stack 许可与 benchmark         |
| PMMC / MemEye / MemLens                                         | P7 prospective compilation / visual bench | RESEARCH_ONLY / REFERENCE             | 只借鉴 evidence-path compilation 与 visual-necessity evaluation；不得直接依赖       |
| Graphiti / Mem0 / GBrain                                        | P7 temporal/hybrid memory patterns        | RESEARCH_ONLY / REFERENCE             | 只登记上游主张；借鉴 provenance、add-only、hybrid/explain/session-demotion pattern  |
| LangGraph / LangMem / Letta                                     | P7 memory taxonomy / context hierarchy    | RESEARCH_ONLY / REFERENCE             | 只借鉴 hot/background、semantic/episodic/procedural 与 hot/cold hierarchy           |
| MemGate                                                         | P7 retrieval admission                    | RESEARCH_ONLY / REFERENCE             | deterministic first-party Gate 先行；learned Gate 只有独立 PoC 后可候选             |
| MemMachine / V-Mem / SAGE                                       | P7 evidence/retrieval/write patterns      | RESEARCH_ONLY / REFERENCE             | 只借鉴 ground-truth preservation、facet routing、novelty/no-op pattern              |
| pgvector                                                        | P7 first vector-index candidate           | DEFERRED POC CANDIDATE                | 仅 P7 rolling-wave 比较 PostgreSQL baseline、许可、运维、性能和删除传播             |
| ASAP                                                            | P4 active pair selection                  | HIGH-VALUE RESEARCH CANDIDATE         | 仅作 acquisition baseline，不得替代 self-conditioned questionnaire domain           |
| PyMC                                                            | P4/P7 offline Bayesian research           | RESEARCH / MODELING CANDIDATE         | 离线与同步生产可行性、性能及部署分别评估                                            |
| 3DDFA_V2                                                        | P3/P5 3D alignment benchmark              | RESEARCH / BENCHMARK CANDIDATE        | 代码、权重、数据许可、维护、准确性与性能                                            |
| FastAPI Users                                                   | P1 auth patterns                          | REFERENCE ONLY                        | 不替换已接受的邀请码、OTP、年龄、政策与 refresh-family 领域设计                     |
| Pillow 12.3.0                                                   | P1-M4 ingestion；future P2 normalization  | APPROVED FOR P1-M4 AND P2 SCOPE       | 不升级版本；精确 wheel/hash/license/native feature/vulnerability 见 adoption record |

模型、权重与数据相关候选的许可证状态以 `docs/data/MODEL_LICENSE_REGISTRY.md` 为权威登记。以上分类是规划候选，不是已完成的 upstream、法律或生产验收。

P2-M1 的逐项 upstream、license、dependency、decision 与 review-trigger evidence 见 `docs/security/P2_SUPPLY_CHAIN_DECISIONS.md`。

上述新增 future candidates 只登记研究方向，未完成实时 upstream/许可证核验，不表示可下载、可执行或可商用。其 PoC 必须先建立 `docs/ai/MIRROR_BENCH.md` 要求的输入数据、许可、预算、成功和失败合同。

## Research claim evidence snapshot

本节只分类 2026-08-16 用户提供研究报告中的候选线索，不执行实时网络刷新。报告及其链接属于
`SOURCE_TYPE: USER_PROVIDED_RESEARCH_REPORT`；除下面明确说明外，
`REPRODUCED: NO`、`PROJECT_MIRROR_EVIDENCE: NONE`、`CONFIDENCE: PROVISIONAL`。

| Component                   | Source                                                 | Claim                                                                        | Claim status                                                                | License evidence / decision                                          |
| --------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| MediaPipe Face Landmarker   | Google AI Edge Face Landmarker；accessed 2026-08-16    | 可提供 landmark/pose observation candidate                                   | `UPSTREAM_CLAIM`；release metadata 另见下方 independently verified snapshot | artifact/model/data 仍 `LICENSE_REVIEW_REQUIRED`；适用性未复现       |
| 3DDFA_V2                    | `cleardusk/3DDFA_V2`；accessed 2026-08-16              | 可作为 3D alignment reliability baseline                                     | `UPSTREAM_CLAIM`                                                            | code/weight/data 未完成权威复核；`PRODUCTION_BLOCKED`                |
| OpenAI Agents SDK           | OpenAI Agents SDK docs；accessed 2026-08-16            | 可作为 Agent runtime Adapter candidate                                       | `UPSTREAM_CLAIM`                                                            | 未与 first-party orchestration 复现比较；不得成为 domain authority   |
| Stable-Makeup               | `Xiaojiu-z/Stable-Makeup`；accessed 2026-08-16         | 可作为 makeup-transfer research baseline                                     | `UPSTREAM_CLAIM`                                                            | 完整 foundation/weight/data/runtime chain 未清除                     |
| MagicMakeup                 | user-reported arXiv reference；accessed 2026-08-16     | 可作为 makeup-transfer research baseline                                     | `UPSTREAM_CLAIM`                                                            | exact upstream 与完整 dependency rights 未清除；`PRODUCTION_BLOCKED` |
| Graphiti                    | `getzep/graphiti`；accessed 2026-08-16                 | temporal/provenance graph pattern may help time-aware retrieval              | `UPSTREAM_CLAIM`; community issue generalization is `UNVERIFIED`            | 只作 pattern reference；须经 MirrorMemoryBench 和供应链 Gate         |
| Mem0                        | report-linked paper/repository；accessed 2026-08-16    | add-only and multi-signal retrieval may improve memory quality               | `UPSTREAM_CLAIM`; managed benchmark is not first-party reproduction         | secondary license report only；managed proprietary layer 未清除      |
| GBrain                      | report-linked repository/evals；accessed 2026-08-16    | explainable hybrid scoring and session demotion may reduce burst bias        | `UPSTREAM_CLAIM`                                                            | author benchmark only；runtime/dependency rights 未复核              |
| PMMC                        | report-linked 2026-08 paper；accessed 2026-08-16       | prospective evidence-path compilation may reduce query cost                  | `UPSTREAM_CLAIM`; very new                                                  | paper input only；code/data/runtime rights 未复核                    |
| MemEye / MemLens            | report-linked 2026 papers/repos；accessed 2026-08-16   | image ablation exposes caption-only shortcuts and fidelity loss              | `UPSTREAM_CLAIM`                                                            | benchmark code/data/image rights must be reviewed separately         |
| LangGraph / LangMem / Letta | report-linked official docs/repos；accessed 2026-08-16 | memory taxonomy and hot/cold context patterns may inform design              | `UPSTREAM_CLAIM`; performance benefit `UNVERIFIED`                          | architecture reference only；cloud/data terms not reviewed           |
| MemGate                     | report-linked 2026 paper；accessed 2026-08-16          | query-conditioned admission may reduce memory-induced threats                | `UPSTREAM_CLAIM`                                                            | neural model/data/runtime license and privacy not reviewed           |
| MemMachine / V-Mem / SAGE   | report-linked 2026 papers；accessed 2026-08-16         | evidence preservation, modality routing, and novelty write policies may help | `UPSTREAM_CLAIM`; very new                                                  | paper inputs only；artifacts and dependency chains not reviewed      |

该表不能升级候选 maturity。P3–P7 当前均为 `DIRECTIONAL`；完整 PoC 合同与 Phase 依赖见
`docs/research/P3_P7_RESEARCH_ROADMAP.md`。

## P2 upstream verification snapshot

- 2026-08-16 通过 `google-ai-edge/mediapipe` GitHub Releases API 核验：`v0.10.35` 是有效 release，发布于 2026-04-28；它是本次 P2 评估指定的候选快照。
- 同日 `releases/latest` 返回 `v1.0.0`，而该 release notes 又写明内部版本升至 `0.10.36`。因此仓库不把 `v0.10.35`、GitHub tag 或 package/runtime version 混写为同一个“当前版本”，后续 PoC 必须锁定并分别核验 exact source tag、package 和 artifact。
- MediaPipe 的批准链固定为 `LICENSE_REVIEW_REQUIRED → POC_APPROVED → RUNTIME_CANDIDATE → APPROVED`；任何一步都不得从 permissive source-code license 推导模型 artifact 已获商业批准。
- 2026-08-17 独立读取并完整渲染 Google 官方 BlazeFace Short Range、Face Mesh V2 与 Blendshape
  V2 model cards。三份卡均明确把相应模型标为 Apache-2.0；BlazeFace 卡称训练/评估使用经同意的
  mobile-AR 真人图像，Face Mesh V2 卡称使用真实环境 smartphone 图像，Blendshape V2 卡称使用
  实验室 multi-view subjects 与 GHUM-derived samples。上述是 `INDEPENDENTLY_VERIFIED` 的官方
  模型许可与高层数据来源描述，不是训练数据逐项权利、地域、删除或再分发证明。
- Face Landmarker public object 的 GCS metadata 给出 immutable generation
  `1683136941468629`、size `3758596`、MD5 `b0e7274907a1644404fef66b28dd6d85` 与 CRC32C，
  但 upstream 不发布 SHA-256。未经显式 artifact-download authorization，Project Mirror 未下载
  bundle 或 wheel，因此 package contents、bundle SHA-256、SBOM、native notices、Python 3.13、
  zero-network 和平台重复性仍为 `NOT_VERIFIED`，T06 保持 `POC_BLOCKED`。

## Current execution boundary

P0/P1 与 P2-M1/P2-M2 保持 `FROZEN`，P2-M3 为 `EXECUTING`。当前 active milestone 只能按其已冻结
protocol 和 Gate 前进；本文不授权其引入未来候选。Pillow 12.3.0 保持既有锁定版本；不引入其余
未经批准候选、不下载权重、不调用未批准外部模型服务，也不预实现 P3–P7 能力。Terra 发现新
候选时只能提交 `THIRD_PARTY_CANDIDATE_FOUND` 报告，包含名称、用途、upstream、Phase、来源与
claim status、许可证证据、模型/数据依赖、收益、替换成本和风险，由 Principal 决定是否建立未来
评估任务。
