# ADR-041：变量隔离、重复与多样性评估权威

## Status

Accepted — 2026-08-19

## Context

P2-M4 已冻结 source-relative `VariantSpecification`、`TransformRun`、不可变 result Asset 与实际
target/control measurement evidence。M4 的技术结果是
`FURTHER_RESEARCH_FOR_M5_ISOLATION`：只有 `jaw_width` 的 N=2 证据，该维度仍为
`EXPERIMENTAL`，尚无 target/non-target tolerance、near-duplicate threshold、coverage cohort authority
或 P2-MVR-v1 结论。

M5 必须能够诚实地区分“评估引擎正确、可重放”与“研究目标已经达到”。若把二者压成一个 PASS，便会
诱导执行者在看到 holdout 后放宽 threshold、把 calibration identity 计入 holdout，或为进入 M6 强迫扩容。

## Decision

- 分离 `P2_M5_TECHNICAL_GATE` 与 `P2_MVR_V1_RESULT`。技术 Gate 证明 authority、计算、恢复、证据和
  安全边界；MVR 结果只能是 `PASS | FURTHER_RESEARCH | FAIL`。技术 Gate 可以 PASS，而 MVR 仍为
  `FURTHER_RESEARCH`。
- 新建不可变、内容寻址的 `SyntheticEvaluationPolicy`，独立绑定 isolation formula、每维 target/error
  tolerance、control-drift tolerance、repeat/platform variance、duplicate candidate rule、coverage rule、
  cohort/split rule、算法版本和 stop rule。不得重解释 M4 `tolerance_policy_id` 或覆盖旧 policy。
- `GeometryOntologyVersion` 通过新版本前向加入非敏感 `region_group`。旧 ontology 不修改；每个 MVR
  dimension 必须绑定一个明示 region group。region group 只表示面部几何测量区域，不是人群、民族、审美
  或真实用户分类。
- `IsolationReport` 按 `TransformRun + SyntheticEvaluationPolicy` 唯一并只追加，保存 requested delta、
  measured target delta、target error、每个 control delta、normalized non-target drift、repeat/platform
  evidence、实际阈值、reason code 与结论。人工 review 不得覆盖自动 hard failure。
- `SimilaritySignature` 只使用 normalized SHA-256 与第一方固定 pHash bitstring；距离为确定性 Hamming。
  exact SHA 相同 hard reject。near-duplicate 在 threshold 预注册前只产生候选 pair，不自动拒绝。
  `imagededup` 保持拒绝，不引入其依赖。
- `DuplicateCluster` 保存版本化算法、member、retain/reject decision、actor/reason/timestamp 和 evidence。
  cluster/decision 只追加；不得删除或改写成员历史。
- `DiversityReport` 使用允许的连续 morphology measurement、nearest-neighbor distribution、cluster
  occupancy、duplicate rate、yield、style-context coverage 和已批准的年龄呈现分布控制。禁止 beauty
  score/rank/percentile、明星相似度、race/ethnicity/ancestry/nationality 或其他敏感分类。
- MVR 的 N 是**每个 dimension** 的 identity-disjoint holdout identity 数，并按 duplicate cluster 调整。
  calibration identity、M4-seen identity、同 identity variant 或同 duplicate cluster 不得重复计数。
  operational sequence 固定为 `24 → 48 → 96`；N=96 仍不稳定时重新分类，不继续扩容强迫 PASS。
- P2-MVR-v1 仍以至少 4 个双向 2D geometry dimensions、至少 3 个 region groups、每维至少 24 个有效
  holdout identities 为目标。每维分别判定，不允许用总样本数替代 per-dimension N。
- 年龄/风格 change control 只作为 selection/coverage distribution evidence：保持 synthetic-only、
  China-market-first、East-Asian-presenting、女性向、18+ 和当前 ADR-028–030 边界；不得变成年龄估计器、
  未成年分类器、颜值评分或单一模板脸优化。
- M6 refinement/release 只有在 `P2_M5_TECHNICAL_GATE=PASS` 且 `P2_MVR_V1_RESULT=PASS` 后开放。
  若 MVR 为 `FURTHER_RESEARCH`，M5 可完成技术冻结，但 QuestionBank release 继续关闭。
- M5 不新增 public/internal HTTP API、operator CLI、生产 geometry、真实用户 facial processing 或新的
  generation/model Provider。

## Alternatives Considered

- 复用 M4 tolerance reference 并在 M5 赋予新含义：拒绝，会改写旧 intent。
- 把 calibration、M4-seen 和 holdout identities 混合计数：拒绝，产生 leakage。
- 使用固定“经验 pHash 阈值”直接拒绝：拒绝，必须先测距离分布并预注册。
- 采用 `imagededup`：拒绝，依赖闭包远超所需的 exact/pHash/Hamming core。
- 将 M5 技术完成自动等同于 MVR PASS：拒绝，会把工程正确性伪装成研究充分性。

## Consequences

- 计划中的前向 migration 是 `0014_variable_isolation_coverage.py`，revision
  `0014_m5_eval_authority`，down revision `0013_warp_plan_authority`；实际 schema 必须由 T03 的真实
  PostgreSQL lifecycle 与 Principal review 接受。
- calibration、threshold freeze 和 holdout 必须是不同 checkpoint；看过 holdout 后的变化只能创建新
  policy/version/cohort，不能修改原 evidence。
- 当前只有 4 个 canonical identities、1 个 experimental dimension 和 N=2 M4 evidence，因此 T01 不
  宣告 MVR 可执行或可通过。补充 cohort 必须走后续既有 synthetic-only generation/QA authority。
- 下载任务所需依赖/model artifacts 已获 Owner 授权，但下载仍不等于 adoption、license approval、
  distribution、production enablement 或 real-user processing approval。

## Security / Privacy Considerations

所有输入继续限定为 private synthetic Asset 和已批准 evidence。committed report 仅包含 opaque IDs、
digests、版本、bounded measurements、aggregate counts 和 reason codes；不包含图片、landmark array、
Prompt、private path、object key、Provider payload 或真实用户关系。

## Testing Implications

必须验证 policy canonicalization/immutability、split/cluster leakage、target/control formula、exact duplicate、
pHash/Hamming golden vectors、threshold preregistration、append-only cluster/report、24→48→96 stop rule、
PostgreSQL concurrency、reference-only Worker、zero-network、zero OpenAPI drift 和完整 same-SHA CI。
