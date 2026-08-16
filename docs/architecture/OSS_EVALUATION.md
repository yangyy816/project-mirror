# OSS Evaluation Registry

## Purpose and decision rule

Project Mirror 的复用原则是：复用成熟的通用基础设施，保留个性化审美智能。`SelfState`、`DesiredDeltaProfile`、`StyleProfile`、`IdentityConstraints`、证据优先级、self-transfer、anti-homogenization、Profile 版本与 PreferenceEvent 语义始终由 Project Mirror 持有，第三方库不得重新定义这些领域语义。

重大候选采用 `RESEARCH_ONLY → CANDIDATE → APPROVED` 的 Principal 决策链；风险项还可标为 `PRODUCTION_BLOCKED`、`REJECTED` 或 `REQUIRES_LEGAL_REVIEW`。PoC 成功不等于生产批准，高影响依赖进入生产前需要 ADR。

每次评估必须记录组件、权威 upstream、组织、候选版本、用途、目标 Phase、代码/模型/数据许可证、传递依赖、商业与再分发权利、SaaS 影响、隐私、网络/遥测、安全、维护、替换成本、平台支持、benchmark、决定、ADR 和复核日期。

## Provisional registry

| Component                   | Intended Phase / purpose                  | Current classification          | Required evidence before adoption                                                   |
| --------------------------- | ----------------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------- |
| MediaPipe / Face Landmarker | P2-M3/P3 landmark、姿态与几何输入         | LICENSE_REVIEW_REQUIRED         | 代码、package/runtime、Face Landmarker artifact、model/data 条款分别核验            |
| OpenCV                      | P2-M4/P3/P5/P6 确定性变换、warp、mask、QA | POC_REQUIRED                    | Python 3.13、Windows/Linux/Docker、wheel/SBOM、性能、确定性、替换边界               |
| imagededup                  | P2-M5 duplicate candidate                 | REJECT                          | 不采用依赖链；后续仅第一方实现 exact SHA-256、pHash、Hamming 与候选证据             |
| Konva / React-Konva         | P6 Web canvas                             | CANDIDATE                       | bundle、性能、可访问性、维护与 ImageVersion DAG 集成；不得成为状态权威              |
| miniPaint                   | P6 editor patterns                        | RESEARCH_ONLY / REFERENCE       | 只研究交互和工具组织；深度复用需单独 ADR                                            |
| Filerobot Image Editor      | P6 UX prototype                           | PROTOTYPE CANDIDATE             | 与 React-Konva 对照评估；不得同时无决策引入两套框架                                 |
| Uppy                        | P1-M3 upload UX                           | HIGH-PRIORITY CANDIDATE         | M3 时评估；不得绕过 UploadIntent、quarantine、归属、校验与审计                      |
| tus / tusd                  | P1-M3/M4 或 iOS resumable upload          | DEFERRED CANDIDATE              | 只有网络/产品测量证明普通签名上传不足时评估                                         |
| OpenAI Agents SDK           | P6 Agent orchestration                    | CANDIDATE                       | 与直接 orchestration 对比；必须位于 `AgentRuntimeProvider` 类边界后                 |
| ASAP                        | P4 active pair selection                  | HIGH-VALUE RESEARCH CANDIDATE   | 仅作 acquisition baseline，不得替代 self-conditioned questionnaire domain           |
| PyMC                        | P4/P7 offline Bayesian research           | RESEARCH / MODELING CANDIDATE   | 离线与同步生产可行性、性能及部署分别评估                                            |
| 3DDFA_V2                    | P3/P5 3D alignment benchmark              | RESEARCH / BENCHMARK CANDIDATE  | 代码、权重、数据许可、维护、准确性与性能                                            |
| FastAPI Users               | P1 auth patterns                          | REFERENCE ONLY                  | 不替换已接受的邀请码、OTP、年龄、政策与 refresh-family 领域设计                     |
| Pillow 12.3.0               | P1-M4 ingestion；future P2 normalization  | APPROVED FOR P1-M4 AND P2 SCOPE | 不升级版本；精确 wheel/hash/license/native feature/vulnerability 见 adoption record |

模型、权重与数据相关候选的许可证状态以 `docs/data/MODEL_LICENSE_REGISTRY.md` 为权威登记。以上分类是规划候选，不是已完成的 upstream、法律或生产验收。

P2-M1 的逐项 upstream、license、dependency、decision 与 review-trigger evidence 见 `docs/security/P2_SUPPLY_CHAIN_DECISIONS.md`。

## P2 upstream verification snapshot

- 2026-08-16 通过 `google-ai-edge/mediapipe` GitHub Releases API 核验：`v0.10.35` 是有效 release，发布于 2026-04-28；它是本次 P2 评估指定的候选快照。
- 同日 `releases/latest` 返回 `v1.0.0`，而该 release notes 又写明内部版本升至 `0.10.36`。因此仓库不把 `v0.10.35`、GitHub tag 或 package/runtime version 混写为同一个“当前版本”，后续 PoC 必须锁定并分别核验 exact source tag、package 和 artifact。
- MediaPipe 的批准链固定为 `LICENSE_REVIEW_REQUIRED → POC_APPROVED → RUNTIME_CANDIDATE → APPROVED`；任何一步都不得从 permissive source-code license 推导模型 artifact 已获商业批准。

## Current execution boundary

P2-M1 的单独授权仅覆盖 T01 文档治理编码；在 `P2-M1-PR1` Principal Architecture Review PASS 前，不得开始 T02–T05。Pillow 12.3.0 保持既有锁定版本；不引入其余未经批准候选、不下载权重、不调用外部模型服务，也不预实现后续能力。Terra 发现新候选时只能提交 `THIRD_PARTY_CANDIDATE_FOUND` 报告，包含名称、用途、upstream、Phase、许可证证据、模型/数据依赖、收益、替换成本和风险，由 Principal 决定是否建立未来评估任务。
