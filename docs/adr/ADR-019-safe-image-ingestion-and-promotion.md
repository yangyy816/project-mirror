# ADR-019：安全图片摄入与 Original Asset 晋升

## Status

Accepted — 2026-08-16

## Context

P1-M3 已冻结 owner-bound `UploadIntent` 与私有 quarantine 上传控制面。`uploaded_unverified` 只证明 Provider object metadata 与客户端声明一致，不证明 bytes 是安全、可解码或适合成为 Original Asset。P1-M4 必须在不处理真人 fixture、不做人脸/landmark/AI 分析、不接真实 COS 的前提下，建立可重试、可审计、不可绕过的异步安全摄入链。

对象存储与 PostgreSQL 不能共享事务，Celery 也只提供 at-least-once delivery。设计必须允许消息重复、Worker 崩溃、对象写入后数据库提交失败、数据库完成后 quarantine 删除失败，并且任何失败都不能产生半晋升 Asset。

## Decision

### 1. 显式异步边界

- 新增 `POST /api/v1/assets/upload-intents/{intent_id}/ingestion-jobs` → `202`。只有 owner、active actor、仍有效的精确用途授权和 `uploaded_unverified` intent 可创建摄入 Job；所有创建请求使用 `Idempotency-Key`。
- M3 的 `complete` 语义保持不变，不隐式创建 Job。摄入 Job 是单独、可观察、可重放的领域动作。
- 新增 owner-bound `GET /api/v1/jobs/{job_id}`。响应只暴露稳定状态、稳定失败码和成功时的 `asset_id`，不暴露 object key、decoder 原始异常、路径、图片 bytes 或 Provider payload。
- PostgreSQL `Job` 是权威工作状态；Celery/Local runner 只是 dispatch Adapter。dispatch 采用 at-least-once，pending/stale Job 可由 reconciler 重投。消息不携带 object key 或图片内容，只携带不可猜测的 `job_id`、`request_id` 和 schema version。

### 2. 验证与 canonical sanitization

- quarantine bytes 始终视为恶意输入。Worker 只能通过 `ObjectStorageProvider` 的 bounded stream 能力读取精确 server-generated key，不接受客户端 URL、路径、bucket 或任意远端 fetch。
- 首版接受 JPEG、PNG、WebP 的单帧静态输入。实际 magic、decoder format 与声明 MIME 必须完全匹配；动画、多帧、截断、畸形、未知格式、零尺寸、超限边长、超限像素和解压炸弹均拒绝。
- Operational targets：raw bytes 最多 20 MiB、单边最多 8192 px、总像素最多 40,000,000、最小边至少 64 px。它们由单一版本化配置表达，可在安全评估后前向调整，不是永久产品 invariant。
- sanitizer 应用 EXIF orientation 后丢弃 EXIF、XMP、ICC、文本块、文件名及所有其他 metadata；不把 raw container 直接复制或 server-side copy 为业务资产。
- `image-sanitizer-v1` 不解析或信任输入 ICC profile；它将解码后的像素值按版本化 assumed-sRGB 规则转换为 RGB，透明像素以固定白底合成，并以固定、版本化编码参数重新编码为无 ICC 的静态 JPEG。编码可使用确定性质量阶梯满足 sanitized output 上限，但不得缩放、裁剪、美化、锐化或改变几何。输出仍超限则拒绝。该取舍可能改变非 sRGB 图片的色彩，必须在后续界面说明并以测试固定。
- 晋升前对新输出重新解码验证、重新计算 SHA-256/byte size/dimensions/MIME，并验证输出不含可携带的 EXIF/XMP/ICC。P1-M4 不执行人脸检测、质量评分、landmark、Vision Provider 或任何 AI 调用。

### 3. 持久化与幂等晋升

- `0004` 只做前向追加：强化 owner-bound Job/JobAttempt、UploadIntent 的 processing/final timestamps 与 quarantine retention deadline，并新增 append-only `AssetIngestionRecord` 作为 promoted/rejected 最终证据。不得修改 `0001`、`0002` 或 `0003`。
- 一个 UploadIntent 最多对应一个 authoritative ingestion Job 和一个 final ingestion record；一个 promoted record 精确引用一个新建 `Asset(asset_role=original)`。rejected record 不得引用 Asset。
- `AssetIngestionRecord` 只记录实际开始过 attempt 的 promoted/rejected 摄入结果。若 Job 创建后、首次 claim 前，UploadIntent 已因用户取消、授权撤回或其他 M3 tombstone 进入 `cancelled`，Job 必须在不读取 quarantine bytes、不伪造 JobAttempt 的情况下进入 terminal `cancelled`；此时 `attempt_count=0`、无 Asset、无 `AssetIngestionRecord`，并保存稳定的非敏感 `result_code` 与审计事件。terminal cancelled Job 不得恢复为 pending/leased 或改写结果。
- Original Asset 的 `storage_key`、MIME、摘要、大小和尺寸从 sanitized output 产生，不复用客户端声明。raw quarantine object 从不成为 Asset，也不得被 Profile、编辑、分析或下载接口引用。
- sanitized object 使用由 job ID 派生的固定 opaque key并以 create-if-absent 写入。若相同 key 已存在，只有摘要、大小和 MIME 全部一致才可继续；否则 fail closed。
- 语义晋升点是持有 intent/job 行锁的 PostgreSQL 事务：再次验证 user/consent/intent 权限，创建 immutable Original Asset、追加 ingestion evidence 与 `promoted` event，并完成 Job。唯一约束保证重复 delivery 不会创建第二个 Asset。
- 对象先写入但数据库未提交时，重试复用相同安全输出；最终失败由 orphan cleanup 删除。数据库已提交但 quarantine 删除失败时，Asset 仍有效，清理作为幂等后置任务重试。不得为了清理失败回滚或复制第二个 Asset。

### 4. 撤回、失败与恢复

- Worker 在读取 quarantine 前及最终晋升事务中都必须重新验证 active actor、当前精确 Consent、intent owner/status 和 retention deadline。撤回、账户冻结、取消、过期或删除请求在任一检查失败时都阻止晋升。
- 撤回发生在首次 claim 前且 M3 已 tombstone intent 时，claim/reconciler 只终结 pending Job 为 `cancelled`，不创建虚假 attempt 或 rejected ingestion evidence；撤回发生在 attempt 已开始后，现有 attempt 必须完成为 `rejected` 并追加 rejected evidence。该区分保证“从未处理”和“处理开始后被阻断”可审计且不混淆。
- deterministic invalid input 形成稳定的 `rejected` evidence 和安全错误码；基础设施/存储/数据库瞬态错误保持 Job 可重试，不得被伪装为内容拒绝。
- Job claim、attempt number、lease/stale recovery 与 retry policy 必须由 PostgreSQL 状态和唯一约束证明；Worker crash 后可安全重投。Redis/Celery 状态不是权威。
- 新上传完成时写入固定 quarantine retention deadline。默认 1 小时、最大 24 小时；到期未晋升对象由幂等 sweeper tombstone 并删除。迟到或撤回后的 bytes 永不恢复处理资格。

### 5. Decoder dependency Gate

- 首版 decoder/sanitizer 候选为 Pillow，但在加入依赖和锁文件前必须完成独立 OSS/供应链任务：核验权威来源、精确版本、许可证全文、传递依赖、Python 3.13 wheel、已知漏洞、解码器编译特性和维护状态。
- 只有 Principal 明确给出 `THIRD_PARTY_APPROVED` 后实现任务才可安装或围绕 Pillow 编码。失败时停止在 dependency Gate，不得由 Terra 改选 ImageMagick、OpenCV、libvips、云端 decoder 或下载二进制。

## Public Interfaces

- `POST /api/v1/assets/upload-intents/{intent_id}/ingestion-jobs` → `202 JobAccepted`
- `GET /api/v1/jobs/{job_id}` → `200 JobStatusResponse`

现有 M3 Consent/UploadIntent 接口保持兼容。成功 Job 只返回新 `asset_id`；Asset 下载、用户资产列表、删除/导出和 Web UI 属于 P1-M5。

## Alternatives Considered

- 在 M3 `complete` 内同步解码并创建 Asset。
- 把客户端上传的 raw blob 直接标记为 Original。
- 依赖扩展名、声明 MIME 或对象存储 metadata 作为内容安全证明。
- 把任意 URL 交给 Worker/Provider 下载。
- 使用 exactly-once 假设或以 Celery result backend 作为权威状态。
- 保留全部原始 metadata，或为通过上限静默缩放/裁剪用户图片。
- 在未完成许可证与漏洞审查前直接加入 decoder 依赖。

## Consequences

摄入增加一次显式 Job 创建与查询，且需要 `0004`、storage stream/write/delete 能力、sanitizer、Job reconciler、Worker task 和 cleanup。统一 JPEG 会移除透明度与原容器编码，但显著缩小攻击面并建立稳定、无 metadata 的后续处理输入；该变化必须在用户界面进入上传阶段前说明。

## Change Control

- `CC-P1-M4-01`（2026-08-16，Accepted）：补充 pre-claim tombstone 语义。原因是 M3 可在 ingestion Job 创建后、首次 claim 前原子取消 `uploaded_unverified` intent；原始 promoted/rejected-only Job 状态无法在不伪造 attempt 的情况下终结该 Job。新增 terminal `cancelled` 仅表达“摄入从未开始”，不改变 raw 永不成为 Asset、双重授权检查、promoted/rejected evidence 或生产 fail-closed 约束。

## Security / Privacy Considerations

日志、错误、Job payload/event metadata 不得包含 object key、图片内容、原始 decoder 异常、签名 URL、文件名或 metadata。临时文件必须位于固定私有 root，使用受限权限、不可预测名称、bounded write 和 finally cleanup；不得把图片传给 OS shell、外部命令或网络 Provider。生产 real-image ingestion 在 Legal/Security/Provider Gate 通过前保持 fail closed。

## Testing Implications

只使用运行时生成的合成非人脸 JPEG/PNG/WebP fixture。必须覆盖 magic/MIME mismatch、截断、动画/多帧、polyglot trailing payload 不传播、解压炸弹、像素/边长/byte 限制、EXIF orientation 与清除、alpha flatten、metadata absence、sanitized re-decode、重复 delivery、Worker crash、dispatch failure、对象/数据库双写故障、撤回竞态、横向访问、TTL cleanup、migration lifecycle、OpenAPI drift、Redis/Celery 和 production fail-closed。
