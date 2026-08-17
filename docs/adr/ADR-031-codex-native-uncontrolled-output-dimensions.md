# ADR-031：Codex Native 未暴露输出尺寸的前向准入契约

## Status

Accepted — 2026-08-17

## Context

ADR-026 的 `CodexNativeGenerationSpecification/v1` 要求在生成前记录 requested width/height，并在
准入时拒绝不同纵横比。P2-M2-V01 的工具输出虽然由 requested `1024×1024` 变为 observed
`1254×1254`，但纵横比保持一致，因此 v1 能如实记录
`dimensions_match_requested=false`。

当前 Codex built-in `image_gen` 不提供可审计的尺寸或纵横比参数。P2-M3 style-v2 的受控生成按
预注册 Prompt 和 attempt ceiling 完成后，实际返回方形、纵向和横向 PNG。将 observed dimensions
回填成 requested dimensions 会伪造 provenance；裁切或重采样 raw source 会破坏原始输出证据；
修改已冻结的 v1 evidence 也违反前向治理。

## Decision

- `CodexNativeAdmissionManifest/v1`、`CodexNativeGenerationSpecification/v1` 和既有 P2-M2/V-next
  evidence 保持不可变并继续受支持。
- 新增前向 `CodexNativeAdmissionManifest/v2`、`CodexNativeGenerationSpecification/v2` 与
  `CodexNativeAdmissionEvidence/v2`，只用于生成工具没有暴露 requested dimensions 的未来 cohort。
- v2 manifest 把 requested quantity、global attempt ceiling、per-item retry ceiling 与 serial
  concurrency 作为 cohort-level constraints。不同 PromptTemplate 的 item 不得通过事后分摊 per-spec
  budget 来伪造全局 attempt budget。
- v2 用 `output_constraints` 表达生成前可知的 admission boundary：MIME、最大 bytes、最大 width、
  最大 height、最大 pixels，以及成对出现或同时为 `NULL` 的 requested width/height。
- requested dimensions 为 `NULL` 时，准入 evidence 必须保存 observed width/height，并将
  `requested_width`、`requested_height` 与 `dimensions_match_requested` 保持 `NULL`；不得猜测、
  回填或声称匹配，也不得执行 raw crop/resample。
- requested dimensions 已知时，两者必须同时提供；v2 继续执行 v1 的纵横比校验，并保存精确
  match/mismatch fact。
- 无论 requested dimensions 是否已知，checksum、MIME/magic、bounded bytes、single-frame、
  edge、pixel、decode、private source-root、symlink/reparse 与 attempt/concurrency gates 均保持
  fail closed。
- M3 normalizer 只消费 admitted raw bytes，按 ADR-027 生成新的 canonical Asset；它不反向改写 raw
  evidence。OpenAPI、runtime `ImageGenerationProvider`、生产配置与 M2 frozen Gate 不变。

## Alternatives Considered

- 把 observed dimensions 冒充 requested dimensions。
- 在 source admission 前裁切或缩放图片。
- 删除纵横比校验但仍保留非空 requested dimensions。
- 重写 v1 schema 或既有 P2-M2 evidence。
- 重新生成整个 cohort，假设 built-in tool 会遵守未暴露的尺寸控制。

## Consequences

P2-M3 可以如实准入尺寸控制不可见的 operator-assisted synthetic source，同时保持 raw bytes 与
provenance 不可变。v2 evidence 对未知 requested dimensions 明确使用 `NULL`，因此不能被解释为
Provider 尺寸遵从性证据。下游仍必须通过 M3 normalization、Vision QA 与人工 review；本 ADR 不
批准生产 Provider、真实用户生成或 QuestionBank release。

## Security / Privacy Considerations

放宽的仅是“未知 requested aspect ratio”这一表示问题，不放宽资源限制、图片解析、来源路径、
synthetic-only、真人 reference、Prompt/path/object-key 泄漏或生产 fail-closed。任何超出明确
edge/pixel/byte 上限的输出仍 hard reject。

## Testing Implications

- v1 行为和既有 evidence 必须回归通过。
- v2 未知 requested dimensions 的非方形 PNG 必须可准入，并保存三个 `NULL` requested facts。
- v2 cohort requested/attempt/retry/concurrency constraints 必须与 item 数和实际 attempt 总数一致。
- v2 只提供一个 requested dimension、超 edge/pixel/byte、格式不符、多帧或已知比例不符必须拒绝。
- redacted committed evidence 不得包含 Prompt、private path、object key、storage reference 或图片。
