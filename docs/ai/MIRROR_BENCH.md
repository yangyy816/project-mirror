# MirrorBench Family 与 P2–P7 研究 Gate

## 状态与权限边界

- 状态：`ACCEPTED DIRECTION / PROVISIONAL EXECUTION`。
- 适用范围：P2–P7 的候选算法、Provider、Agent runtime、Tool、编辑与视觉记忆架构。
- 本文只建立 benchmark authority、证据格式和未来 PoC backlog；不授权安装依赖、下载模型、处理真实用户图片或执行 P3–P7。
- P1 保持 `FROZEN`。当前 P2-M1 的 schema、typed ports、synthetic-only 和生产 fail-closed Gate 不因本文改变。

Project Mirror 采用统一晋级链：

```text
Candidate
→ isolated PoC
→ MirrorBench
→ ablation
→ license / privacy / security / cost review
→ ADR
→ APPROVED
```

PoC 成功不是生产批准。若简单 baseline 与复杂候选效果接近，选择简单方案；失败的 benchmark 可以删除复杂架构，而不是放宽阈值强迫通过。

## 每项 Bench 的强制合同

每个 versioned Bench 必须固定并输出：

- question、hypothesis、baseline 和候选；
- dataset/fixture manifest、source、synthetic/real classification、license、checksum 和 holdout split；
- metrics、预注册 threshold、failure interpretation 和 human-review 边界；
- ablation matrix；
- algorithm/model/provider/runtime version 与配置；
- reproducibility level、seed 支持事实和 platform；
- latency、cost、resource envelope 与 failure rate；
- machine-readable artifact、summary、provenance 和 commit SHA。

阈值必须先由 calibration evidence 冻结，再在未参与校准的 holdout 上评估。看到 holdout 后放宽阈值只能产生新算法/QAPolicy/Bench version，不能改写旧结果。

## Bench family

| Bench                      | 首要 Phase | 证明的问题                                                                                                    |
| -------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------- |
| `MirrorSyntheticBench`     | P2         | provenance、normalization、成年合成策略、变量隔离、duplicate/diversity、release consistency                   |
| `MirrorSelfStateBench`     | P3         | same-person multi-photo/pose/light/device measurement repeatability、confidence 与 Provider 可替换性          |
| `MirrorQuestionnaireBench` | P4         | random/fixed/active acquisition、信息增益、test-retest、quick/full/progressive calibration                    |
| `MirrorTransferBench`      | P5         | synthetic preference 到本人 self-transfer 的 transfer error、correction evidence 与 uncertainty               |
| `MirrorToolBench`          | P6         | tool/parameter/region correctness、forbidden effects、rollback、idempotency、Verifier 误差、cost/latency      |
| `MirrorRetouchBench`       | P6         | deterministic/local/generative retouch 的质量、保持、返工、成本与延迟                                         |
| `MirrorMakeupBench`        | P6         | identity/geometry/skin preservation、region/reference fidelity、pose/light robustness、intensity monotonicity |
| `MirrorMemoryBench`        | P7         | retrieval、temporal/counterevidence、independence、deletion、profile rebuild、context bound 与成本            |
| `MirrorSafetyBench`        | P2–P7      | 越权、prompt injection、wrong-user、泄漏、未批准 Provider/model、feature-lock 与 fail-closed                  |
| `MirrorEconomicsBench`     | P2–P7      | cost per accepted artifact/final save、retry、latency、yield、storage/compile growth                          |

## 关键 Gate

### P2 variable isolation

`P2-MVR-v1` 的 4 dimensions / 3 regions / N=24 只是技术可行性下限，不是科学充分性。每个 `READY` dimension 必须保存 requested/actual target delta、target error、non-target drift、repeatability/platform variance、artifact failures、holdout pass rate、sample/identity count 和 uncertainty。证据不稳定时按 24→48→96 升级；N=96 仍不稳定则分类为 `EXPERIMENTAL`、`UNSUPPORTED_IN_P2` 或 `REQUIRES_3D_RESEARCH`，不得无限扩样本强迫 PASS。

首个 China-first coverage pack 还必须按 continuous morphology cells 报告 occupancy、empty/
underrepresented cells、nearest-neighbor、duplicate、generation/QA/transform/isolation yield、
coverage gain 与 Provider/model effects。anti-stereotype Gate 检查 generator default、face proportion、
makeup、skin finish、hairstyle、face shape 与 eye geometry 的过度重复，但禁止 attractiveness、race/
ethnicity confidence 或 celebrity similarity。future cross-pack evaluation 只解释工程性能差异，不做
群体审美排名。

### P3 measurement reliability

domain 只消费 `FaceObservation`、`FaceLandmarkSet`、`PoseEstimate`、`GeometryMeasurement` 与 `MeasurementConfidence`。MediaPipe/3DDFA-specific 类型不得成为 SelfState authority。低可靠 measurement 必须降低 confidence 或拒绝，不能伪装为精确事实。

### P4 acquisition

比较 random、fixed、active sampling，并分别评估 full、quick、progressive calibration。72-slot taxonomy 表示覆盖能力，不等于用户必须回答 72 次；实际问题数由信息增益、覆盖和置信度决定。

### P6 visual effects

HTTP/JSON success 不等于视觉成功。每个修改型 Tool 受 `TOOL_EFFECT_CONTRACT.md` 约束；结果进入 accepted `ImageVersion` 前必须由 versioned `EffectVerifier` 输出 `PASS`，或在策略允许时进入 `HUMAN_REVIEW`。`FAIL` 不得发布。

### P7 memory

至少比较：No Memory、Profile Only、Vector Only、Profile + Vector、Profile + Visual Exemplars、Hybrid Retrieval、Hybrid + Temporal、Visual Exemplars + Temporal、+ Analytic Memory、+ Memory Cards、+ Procedural Memory、Full Visual Memory OS。规模覆盖 20/100/500/2,000/10,000+ VisualEpisodes 和一周/三月/一年/多年。

必须测量 Recall@K、Precision@K、MRR、Visual Evidence/Explicit Lock Recall、Wrong Context/Stale Memory/Hallucinated/Unauthorized Memory、Contradiction Resolution、Drift Detection、Deletion Completeness、profile rebuild、p50/p95、context/token、storage/compile cost、first-pass acceptance、manual corrections、generation count 与 cost per final save。

## Future PoC candidate backlog

以下均为 `PROVISIONAL RESEARCH BACKLOG`，不是 execution-ready task：

| Phase | Candidate PoC                                        | Baseline / Gate                                                    |
| ----- | ---------------------------------------------------- | ------------------------------------------------------------------ |
| P2    | Synthetic variable isolation                         | unchanged control pairs；预注册 target/non-target holdout          |
| P3    | MediaPipe vs 3DDFA measurement reliability           | same-person multi-condition repeatability；license/model Gate 先行 |
| P4    | Random vs fixed vs active pairwise acquisition       | equal evidence budget 下的信息增益、稳定性与疲劳                   |
| P5    | Synthetic preference vs self-transfer calibration    | signed transfer error、correction 与 uncertainty                   |
| P6    | Direct Responses orchestration vs Agents SDK adapter | runtime correctness、recovery、cost；Mirror domain 始终自有        |
| P6    | Deterministic vs generative retouch                  | target effect、preservation、latency、cost、manual correction      |
| P6    | Tool Effect Verifier                                 | false-positive/negative、region leakage、feature-lock failure      |
| P6    | Stable-Makeup / MagicMakeup algorithm review         | identity/geometry/skin/reference；完整 dependency license Gate     |
| P6    | Commercial makeup engine baseline                    | commercial rights、data terms、quality、cost 与替换性              |
| P7    | Profile-only memory baseline                         | 明确可解释的最小 baseline                                          |
| P7    | Visual exemplar retrieval                            | facet selection、diversity、context relevance                      |
| P7    | PostgreSQL/pgvector retrieval                        | 与纯 SQL/profile baseline 比较；不预设新 vector DB                 |
| P7    | Temporal relational memory                           | valid/system time、supersession、counterevidence                   |
| P7    | Analytic Memory                                      | structured observation + SQL/statistical aggregate 准确性          |
| P7    | Memory Card compilation                              | evidence provenance、rebuild、deletion 与 query-time savings       |
| P7    | MirrorMemoryBench scale                              | 20→10,000+ episodes 的质量、延迟、成本与 context bound             |

每个 PoC refinement 必须补齐：`QUESTION`、`HYPOTHESIS`、`BASELINE`、`INPUT_DATA`、`LICENSE_STATUS`、`METRICS`、`TIME_BUDGET`、`COST_BUDGET`、`SUCCESS_GATE`、`FAILURE_DECISION`、`ARTIFACTS`、`OWNER_ROLE`。缺一不得执行。

`DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`
