# ADR-023：合成 QA、发布与供应链治理

## Status

Accepted — 2026-08-16

## Context

合成题库必须是可测量、可验证、可版本化的刺激资产系统，而不是随机图片集合。Vision model、几何变换、near-duplicate threshold 和真实生成 Provider 尚未验证；这些研究结果不得被预先写成 invariant 或生产结论。

## Decision

- QA 绑定 QAPolicy、algorithm 和 threshold version，并保存 measurement、reason code 与 append-only review evidence；禁止只存 `qa_pass`。synthetic origin、license、adult policy、decode/safety、provenance、checksum、release consistency 与 unresolved hard variable-isolation failure 是自动 hard gates，人工 review 不得擦除 hard failure 或使其成为 eligible evidence。
- adult synthetic policy 是版本化 generation policy、Provider safety evidence 和必要的人类复核所支持的“clearly adult-appearing synthetic subject”。ambiguous/minor-looking output 必须拒绝；P2 不做年龄估计、不保存精确年龄，也不按敏感特征分类。
- future geometry variant 只以 QA-passed canonical base Asset 为输入，按相对 source measurement 的 `VariantSpecification` 表达。变换生成新 immutable Asset，并重新测量 target delta、non-target drift、pose/reliability 与 artifact；不得映射到全局理想脸或绝对几何。
- exact duplicate 由 normalized SHA-256 拒绝。near-duplicate、tolerance、measurement repeatability、supported dimension、corpus coverage 和 P2-MVR-v1 的四 dimensions / 三 region groups / 24 identities 是研究/运营目标，不是 invariant。它们必须先测量分布、预注册 policy、在 holdout 验证，并按 `24 → 48 → 96` cohort escalation；失败必须输出 `FURTHER_RESEARCH`、`EXPERIMENTAL`、`UNSUPPORTED_IN_P2` 或 `REQUIRES_3D_RESEARCH`。
- future QuestionBank release 只引用证据完整的 immutable manifest entry；revoke 追加事实并阻止新下游选择。P2-M1 只冻结 authority，不实现 release workflow。
- Pillow 12.3.0 已获 `APPROVE_FOR_P2` purpose extension，但不改变版本、也不授权 M1 图像处理。MediaPipe 为 `LICENSE_REVIEW_REQUIRED`，OpenCV 为 `POC_REQUIRED`，imagededup 为 `REJECT` / `REIMPLEMENT_SMALL_CORE`；M1 不安装它们或下载模型/权重。
- MediaPipe 上游事实按 planning amendment 保留：2026-08-16 GitHub API 核验 `v0.10.35` 存在且发布于 2026-04-28，这是本次 P2 candidate snapshot；同一上游 `releases/latest` 返回 `v1.0.0`，其 notes 写有“Bump MediaPipe version to 0.10.36”。因此 `v0.10.35` 不是无条件 current-latest 断言，后续 PoC 必须分别锁定并审查 exact source tag、package/runtime、Face Landmarker artifact 和 model/data terms。

## Alternatives Considered

- 依 Prompt 假定几何变化确实发生。
- 允许人工 review 任意 override hard gate。
- 未测量分布就固定 threshold、identity count 或 production model。
- 从代码许可证推导模型、权重、数据或商业条款批准。

## Consequences

M1 只产生 QA/release/supply-chain governance 与研究协议。M3–M6 才能根据该 authority 增加 measurement、isolation、duplicate/diversity、manifest 与 revoke；非确定性 benchmark 与 license/terms 结论需要独立 evidence。

## Security / Privacy Considerations

fixture、golden set、model、weight、dataset 与 Provider terms 分别登记 source/version/checksum/license/purpose/approval。production 继续拒绝未批准依赖、权重、公开存储与真实 facial processing；所有 P2 测试保持 synthetic-only。

## Testing Implications

M1 验证 policy digest、state/reason taxonomy、hard-gate non-bypass、无 dependency/model、fixture admission 和 OpenAPI unchanged。M4/M5 的 tolerance、2D transform、similarity 与 diversity 只能通过独立研究/holdout Gate 证明。
