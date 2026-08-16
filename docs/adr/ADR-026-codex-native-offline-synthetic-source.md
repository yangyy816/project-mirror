# ADR-026：Codex 原生离线合成来源与生产 Provider 延后

## Status

Accepted — 2026-08-16

## Context

P2-M2 已实现可恢复的 programmatic Provider pipeline，但尚无通过中国大陆生产条款、数据地域、
留存、训练、删除、输出权利、安全与成本审查的 runtime image-generation Provider。Project Owner
通过正式 change control 批准 Codex 内置 `image_gen` 作为 P2 研究、测试、数据集与内部
QuestionBank 的开发来源，同时明确它不是生产 Provider，也不授权 ChatGPT Web 自动化、非官方
接口或真实用户照片处理。

Codex 原生能力不暴露稳定 model ID、model snapshot、request ID、usage 或 per-request cost。
把未知值填成占位字符串会制造虚假 provenance；把 Codex 实现成 runtime Adapter 则会错误依赖
交互会话、OAuth 或桌面状态。

## Decision

- 第一方 source classification 包含 `CODEX_NATIVE_IMAGEGEN`、`PROGRAMMATIC_PROVIDER` 与
  `DETERMINISTIC_FIXTURE`。它只描述 synthetic pixels 的取得方式，不成为用户接口或下游领域
  authority。
- `CODEX_NATIVE_IMAGEGEN` 是 operator-assisted offline development source，不实现
  `CodexImageGenerationProvider`，不进入 application/Worker runtime config，在 `APP_ENV=production`
  下不可选择。
- 每次 native generation 必须先有版本化 `CodexNativeGenerationSpecification`，绑定 policy、prompt
  digest、coverage、pose、expression、style、output、quantity、attempt、retry、concurrency 与 stop
  condition。默认串行；单 cohort 超过 24 张需新的 Principal 授权。
- 生成文件只能从 Principal 明确指定的 private staging source root 读取；解析后越界或 symlink
  source 必须拒绝。随后按不可信 raw input 接受 bounded decode、MIME/magic、single-frame、pixel、
  dimension 与 byte checks，再以 opaque reference 写入现有 `internal-synthetic/v1/raw` 私有
  namespace。M2 不做 normalization、QA、SyntheticIdentity、variant 或 QuestionBank release。
- native evidence 只记录实际已知事实。`source_kind=CODEX_NATIVE_IMAGEGEN`、
  `provenance_level=PROVENANCE_ONLY`、`cost_accounting_mode=REQUEST_COUNT_ONLY`；model、snapshot、
  provider request、seed、usage 与 provider cost 保持 `NULL`。Prompt text、源文件路径、object key 与
  image bytes 不进入日志或 CI artifact。
- downstream normalization、QA、geometry、isolation、diversity 与 QuestionBank 必须 source-neutral。
  未来国内 Provider 复用现有 `ImageGenerationProvider` 与同一 admission/downstream pipeline。
- 原 `P2_M2_RUNTIME_PROVIDER_GATE` 改为
  `P2_M2_PROGRAMMATIC_PROVIDER_GATE=DEFERRED_EXTERNAL_PRODUCTION_DEPENDENCY`。它不再阻塞 P2
  synthetic research 或 Phase 2 research Gate，但始终阻塞需要 runtime generation 的生产发布。
- 新增 durable `PRODUCTION-BLOCKER-IMAGEGEN-PROVIDER`。生产 generation 保持 fail closed；未完成
  Provider Adapter、条款、安全、成本和 benchmark 前不得宣告 production approval。
- P2 Milestone DAG 不变。M2 只有在 deterministic core、same-SHA CI、native admission V01 与本
  change control 均通过后，Principal 才可宣告 `PASS/FROZEN` 并开放 M3 synthetic-only refinement。

## Alternatives Considered

- 继续让生产 Provider 缺失阻塞全部 P2 研究。
- 把 Codex 会话包装为 production `ImageGenerationProvider`。
- 以占位 model/request/cost 值满足现有 Provider provenance。
- 绕过 raw admission，直接把生成文件升级为 Asset 或 SyntheticIdentity。
- 自动循环生成直到 QA 通过。

## Consequences

P2 可以使用受控 Codex credits 推进 synthetic-only 研究，同时保留未来国内 Provider 的稳定 Adapter
边界。Native outputs 只能进入内部研究链，provenance 强度明确低于 production Provider。生产上线仍
需要独立外部依赖 closure，且生产 questionnaire runtime 保持 generation-free。

## Security / Privacy Considerations

禁止真人 reference、抓取素材、名人模仿、用户数据、Prompt/image/path 日志泄漏与无界重试。Native
outputs 仍按恶意图片处理，binary 不提交 Git；只有小型 allowlisted evidence manifest 可以进入仓库。

## Testing Implications

测试必须证明 specification/budget fail closed、known-null provenance、source path/Prompt/object-key
不泄漏、private raw storage admission、production runtime 不出现 Codex option，以及 programmatic
Provider Gate 仍为 deferred 且 `production_approved=false`。
