# ADR-053：项目内私有证据保管与 ImageGen 输出桥

## Status

Accepted — 2026-08-30

Change control: `CC-P2-M5-05-D0`

## Context

Project Mirror 已通过 ADR-049 冻结 Principal 管理的私有输入和输出登记，但其历史表述仍允许临时 copy 位于
repository 外。Project Owner 现进一步要求：所有由 Project Mirror 任务创建、且不能上传 GitHub 的收据、
私有证据和私有文件，都必须在所属项目工作树内的专用 Git-ignored 目录保留可恢复副本；Temp、Agent
memory、对话记录或工具隐式存储都不能成为唯一权威。

P2-M5 的 `CAL-REQ-002` 已调用一次 built-in imagegen。返回结果没有提供冻结 controller 要求的 exact
absolute local output-hint path，因此 overlay 在读取或解码图片前以
`GENERATED_ARTIFACT_RECEIPT_INVALID` 进入 `OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE`。该调用及其一个
returned/raw output 已永久计入账本；attempt/failure evidence 已进入项目内 Git-ignored custody，但 raw image
没有建立项目内 canonical copy，诚实状态为 `EVIDENCE_LOCATION_LOST`。禁止搜索丢失 raw output、退款、替换、
重试 `CAL-REQ-002` 或再次调用 imagegen 来伪造恢复。

当前 built-in imagegen 工具实际提供 required `image_url` 和 optional `output_hint`。`image_url` 可携带
Base64 data URL；`output_hint` 不是稳定的 exact local-path contract。应用侧必须显式持久化返回 bytes，不能把
工具的临时输出位置当成长期 custody。

## Decision

### Project-local private custody

- 所有未来由 Principal、sub-agent、脚本、PoC、下载或工具调用创建且不得上传 GitHub 的 Project Mirror
  receipt、private artifact、model/runtime copy、Prompt materialization、image bytes 和 private report，必须在
  对应项目工作树的专用 Git-ignored private namespace 中保留 recoverable canonical copy。
- 临时目录、外部 cache、工具返回值或内存可以作为 bounded transport，但在任务继续消费前必须完成项目内
  create-new copy、digest verification、opaque registry registration 和 retention/cleanup policy binding。
- Git 只允许保存 allowlisted redacted facts、opaque IDs、digests、状态和 aggregate；private path、Prompt、
  data URL、object key、signed URL、Provider payload、secret 和 image bytes 继续禁止进入 Git、MEMORY、普通 CI
  artifact、日志或 UI。
- 本决定前向适用，不授权扫描、复制或迁移历史未知 private locations；历史 locator 丢失仍按 ADR-049 报告
  `EVIDENCE_LOCATION_LOST`。
- `.gitignore` 只防止普通 Git 收集，不是访问控制。private namespace 仍需 task-scoped custody、least privilege、
  no-discovery 和 Principal registry。

### Built-in ImageGen transport bridge

- 保留现有 `register_output_before_decode(...)` exact-path API 和历史语义，不把 data URL 伪装成 path，也不降低
  absolute-path、root-containment、reparse/symlink 或 create-new Gate。
- 新增独立 `register_imagegen_data_url_before_decode(...)` transport bridge。调用顺序固定为：

  ```text
  dispatch consumed
  → returned/raw counters committed
  → exact data-URL digest bound to expected opaque output ID
  → registration-attempt receipt committed
  → bounded Base64 transport decode
  → project-local private staging create-new
  → capture sidecar receipt create-new and verified
  → existing output record and registration receipt
  → OUTPUT_REGISTERED_PRE_DECODE
  ```

- Base64 transport decode 不是 image/pixel decode。bridge 必须先验证 strict
  `data:image/{png|jpeg|webp};base64,<payload>` grammar、encoded-size ceiling、standard Base64、decoded byte ceiling，
  再要求 declared MIME 与 PNG/JPEG/WebP magic 一致。参数、空白、换行、URL encoding、空 payload、未知 magic
  和 MIME mismatch 全部 fail closed。
- data URL plaintext 永不落盘、进入 receipt、异常消息或日志；只保存其 SHA-256。staging bytes、capture receipt、
  output record 和 registration receipt 必须使用 create-new-or-verify-exact 语义，并能从精确 predecessor receipt
  在 fresh process 中幂等恢复。
- capture receipt 是 decode Gate 的 mandatory sidecar。缺失、partial、digest mismatch、staging conflict、
  symlink/reparse、short write 或 crash recovery conflict 均不得打开 decode Gate。
- `record_output_returned` 和 registration-attempt binding 必须支持同一 exact predecessor/input 的幂等
  roll-forward，不能因 event/state/receipt 三写中断而重复计数或要求新生成。

### Terminal rollover and ledger truth

- `CAL-REQ-002` 的 terminal root 永远保持 `hard_stop=true`、`decode_authorized=false`；不得原地恢复为 READY。
- 新增 cross-root forward rollover，仅接受 exact terminal receipt、完整 hash-chain、匹配 controller digest、
  `active_calls=0` 和精确 terminal phase。新 root 的 counters 和 next ordinal 只能从已验证 predecessor 派生，
  不能由调用方自由填写。
- 新 root 必须保存 predecessor overlay ID、terminal receipt/state digest、sequence、phase 和 reason code，不保存
  absolute path 或 private receipt bytes。普通 `verify_overlay` 继续验证单 root；独立 verifier 负责跨 root binding。
- 冻结当前账本事实：`CAL-REQ-002=CONSUMED_FAILED_NO_RETRY`，next ordinal `CAL-REQ-003`，formal calls/raw
  capacity `30/30`，global native output capacity remaining/consumed `61/3`。失败调用不退款、不替换、不重试。
- Rollover、bridge implementation、tests 和 same-SHA Gates 均为零 generation；只有新的后续执行授权才可准备
  `CAL-REQ-003`。

## Alternatives Considered

- 继续依赖 optional `output_hint`：拒绝；它不是当前工具的稳定 exact-path contract。
- 放宽现有 path API 接受任意 data URL：拒绝；会混合两种信任模型并破坏历史 replay 语义。
- 把 Base64/data URL 写入普通 receipt 后再处理：拒绝；扩大私有 bytes、日志和 Git 泄漏面。
- 从工具临时存储或磁盘搜索恢复 `CAL-REQ-002`：拒绝；违反 ADR-049 task-scoped recovery 和用户最新 custody
  要求。
- 在 terminal root 内回退 counters 或恢复 READY：拒绝；会改写已消费调用和 hard-stop 证据。
- 为 data URL 单独创建第二个 capture root：拒绝；现有项目内 overlay staging 已是 task-owned custody，额外 root
  增加 orphan 和绑定复杂度。

## Consequences

- `CC-P2-M5-05-D0` 先冻结治理；实现由独立 `P2-M5-R50` 完成。D0/R50 都不生成图片、不读取丢失 raw bytes、
  不执行 decode/QA/screening/admission。
- P2-M5 保持 `EXECUTING`；technical Gate、MVR、M6、QuestionBank release、production Provider、production
  geometry 和 real-user facial processing 继续关闭。
- 不新增 schema/migration、OpenAPI、dependency、model、workflow 或 public API。
- ADR-049 的 authority、non-propagation、least-privilege 和 registry 要求保持；本 ADR 只把未来创建型 private
  output 的 canonical location 收紧为 project-local Git-ignored custody，并增加 built-in imagegen transport
  boundary。

## Security / Privacy / Data / License

实现和测试只使用 synthetic non-face byte fixtures，zero network、zero Provider call、zero model/dependency。
不允许真人 reference、真实用户数据、Prompt plaintext、secret 或 private locator 进入 tracked evidence。data URL
parser、byte bound、magic/MIME、project-root containment、create-new、sidecar binding、crash recovery 和
cross-root immutability 均为 mandatory security Gate。

## Validation

- strict data-URL grammar、Base64、encoded/decoded size、MIME/magic、empty/whitespace/URL-encoded negative tests；
- PNG/JPEG/WebP synthetic bytes success，且证明 image decoder、dimensions read 和 generation call 均为零；
- staging/capture/record/registration/event/state/receipt 每个 crash window 的 fresh-process exact recovery；
- pre-existing file、different bytes、symlink/reparse、root escape、tampered predecessor 和 wrong controller rejection；
- terminal rollover 精确继承 `CAL-REQ-003`、`30/30/61/3` 并拒绝 `CAL-REQ-002`；
- existing direct-path tests、Ruff、strict mypy、full regression、same-SHA CI、八类 artifacts、独立 security 与 Sol
  final review。
