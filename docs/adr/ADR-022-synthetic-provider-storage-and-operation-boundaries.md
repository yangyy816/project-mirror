# ADR-022：合成生成、视觉与存储边界

## Status

Accepted — 2026-08-16

## Context

当前 ImageGenerationProvider、VisionProvider 与对象存储边界只覆盖 fixture 或用户资产路径。P2 需要可审计的合成生成/视觉 QA contract，却不能让 SDK 类型、任意 URL、raw payload 或真实数据进入领域层。

## Decision

- P2 使用 provider-neutral typed ports 表达 `SyntheticGenerationRequest/Result`、bounded generated payload、synthetic vision observation、landmark、pose 与 geometry measurement。generation request 固定 request/policy/prompt references、output specification、allowlisted scalar parameters、optional bounded seed 与 budget context；result 只回显 Provider 实际支持的 seed/parameters，并记录 provider/model/model-version references 与 `BIT_EXACT | SEED_REPLAYABLE | PROVENANCE_ONLY`。application 只接收第一方类型、opaque request/run reference 和 allowlisted provenance/cost facts。
- Adapter 不得返回 SDK type、raw response、signed URL、object key、任意 remote URL 或未净化异常。若 Provider 仅提供 URL，Adapter 必须在自身边界执行 allowlist、redirect、DNS/IP、size 和 bounded stream 防护；application 不得 fetch 任意地址。
- deterministic Mock 仅在 development/test/CI 返回固定 bytes、metadata、safety/cost facts，且零网络。Tencent 和其他未验证 candidate 必须 fail closed；production 拒绝 Mock、Local storage、未批准 Provider、未知 model artifact 和真实 facial processing。
- P2 使用独立 internal synthetic object storage port；其命名空间不与 user quarantine/sanitized/export 混用，访问保持 private、short-lived、actor-bound 且 audited。P2-M1 只定义 contract，不实现真实生成、存储 pipeline 或 Worker task。
- future task message 只包含 opaque IDs、request ID 与 schema version，禁止 Prompt、图片 bytes、Provider URL 或完整 policy payload。所有 Provider raw output 按不可信输入处理。
- live Provider benchmark 是显式、受控、非默认外部验证；不能进入 CI 或替代 deterministic test。未经输出权利、留存/训练、地域、安全和成本验证的 Provider 不得产出 released asset。

## Alternatives Considered

- application 直接依赖腾讯或其他供应商 SDK。
- Worker 下载 Provider 给出的任意 URL。
- 用通用 JSON 或日志保存 Prompt/原始响应。
- 在默认 CI 调用 live AI。

## Consequences

M1 无需安装 SDK、下载模型或联网即可实现 typed contract/mock。M2 才会以专用记录持久化 batch/provider/provenance/cost，并在后续供应商 Gate 通过后进入受控 benchmark。

## Security / Privacy Considerations

Prompt、图片、object key、signed URL、raw Provider payload、credential 和真实个人信息不得进入日志、错误、公开 API、job message 或 CI artifact。合成 Vision contract 不授权真实用户 facial processing；P3 仍须独立通过法律、Consent、PIPIA、安全与 Provider Gate。

## Testing Implications

M1 验证 typed protocol、bounded payload、determinism、zero network、candidate fail-closed、production Mock rejection、URL/SDK source scan 与 namespace isolation；不使用图片 fixture、模型权重或外部 Provider。
