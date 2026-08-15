# ADR-018：用途授权与隔离上传控制面

## Status

Accepted — 2026-08-15

## Context

P1-M1/M2 已冻结 active actor、年龄与政策接受语义，但后续 facial-data 上传还需要独立的用途授权、资源归属、短时私有上传和撤回传播。现有 `ConsentRecord` 只是 Phase 0 append-only 骨架，`Asset` 表只适合已验证并晋升的业务资产；把浏览器刚上传的 blob 直接写成 Original Asset 会绕过 M4 的 MIME/magic/大小/像素/解码/重编码/EXIF Gate。

M3 必须建立可运行的控制面，同时仍禁止真人数据、图像分析和生产真实上传。

## Decision

- 政策 acknowledgement 与 facial-data purpose consent 继续分离。用途授权由服务端配置的精确 `purpose_code`、`purpose_version`、policy code/version/SHA-256 digest 和结构化 scope 定义；配置不是法律批准，生产真实数据入口仍受独立 Legal/Security Gate 阻断。
- Consent 是 append-only event。grant 与 withdrawal 都创建新记录；withdrawal 精确引用被撤回的有效 grant。当前状态由事件计算，不覆盖历史。所有创建事件接收 `Idempotency-Key`，审计只记录白名单标识和版本，不记录图片或签名 URL。
- 只有 `active` actor 且存在当前有效、完全匹配配置的用途 grant 才能创建上传意图。pending、未授权、授权版本过期或已撤回用户统一拒绝。
- 新增 `UploadIntent` 作为 quarantine 控制实体，并用 append-only `UploadIntentEvent` 记录创建、签名、上传声明、取消、过期和未来 M4 处理状态。它不是 Asset，不能被 Profile、编辑或分析引用。
- 对象 key 由服务端使用 CSPRNG 生成固定语法的 opaque quarantine key；客户端不得提供 key、路径、bucket、URL 或 Provider 参数。桶保持私有，Provider 只为精确 key、方法、TTL、声明 MIME/大小和完整性 header 生成短时 upload grant。
- M3 状态为 `awaiting_upload → uploaded_unverified`，并允许进入 `cancelled | expired`。M4 才可进入 `processing → promoted | rejected`。`complete` 只根据 Provider-owned metadata 确认对象存在和声明大小/MIME 边界，绝不声称内容安全或创建 Original Asset。
- grant URL 只在创建响应中返回，不持久化、不写日志/审计或普通 GET response。同一 idempotent replay 在 grant 仍有效时可返回同一安全结果；过期后不得以同一 key 静默签发新 URL，客户端须创建新 intent。
- 授权撤回立即阻止新 intent/签名，并把仍未晋升的相关 intent 标记取消；已发 URL 在 Provider 无撤销能力时最多存活至短 TTL，但任何迟到对象都不可进入 M4，并由清理流程删除。该残余窗口必须在响应/运行文档中明确，不伪造即时 URL 撤销。
- `ObjectStorageProvider` 扩展为 Provider-neutral upload grant、metadata inspection 与 quarantine delete 能力。业务层不得解析供应商 URL、接受任意 URL 或直接依赖 COS SDK。
- 非生产 Local adapter 提供 tokenized `PUT /_local/private-upload/{token}` ingress，用于合成/非真人 fixture 的真实控制面测试；不提供 GET，不接受路径，token 过期/重复/元数据不匹配时 fail closed。生产禁止 Local/Mock，Tencent COS adapter 在验证前继续明确失败。
- 所有 intent 查询、complete、cancel 和后续 M4 消费都必须在 SQL 条件中绑定 `owner_user_id`；仅凭不可猜测 ID 不是授权。

## Public Interfaces

- `GET /api/v1/users/me/consents`：返回当前配置用途的 grant/withdrawn/missing 状态和精确版本，不返回内部历史 payload。
- `POST /api/v1/users/me/consents` → `201`：创建精确用途 grant。
- `POST /api/v1/users/me/consents/{grant_id}/withdrawals` → `201`：追加 withdrawal 并取消未晋升 quarantine intents。
- `POST /api/v1/assets/upload-intents` → `201`：创建 intent，并一次性返回 Provider-neutral `method/url/required_headers/expires_at`。
- `GET /api/v1/assets/upload-intents/{intent_id}` → `200`：只返回 owner-safe 状态与声明元数据，不返回 object key 或 URL。
- `POST /api/v1/assets/upload-intents/{intent_id}/complete` → `200`：确认 Provider object 存在并标记 `uploaded_unverified`；不得创建 Asset/Job 或伪造 M4。
- `DELETE /api/v1/assets/upload-intents/{intent_id}` → `204`：幂等取消并请求清理 quarantine object。

所有 POST 使用 `Idempotency-Key`；稳定错误继续使用 `code/message/request_id/details`。M3 允许声明的格式暂定为 JPEG、PNG、WebP，声明上限为可配置 20 MiB operational target；M4 必须重新以实际 bytes、magic 和解码结果验证，不能信任声明。

## Alternatives Considered

- 直接把上传 blob 创建为 `Asset(asset_role=original)`。
- 让客户端提供 COS key、任意 URL 或 bucket。
- 用可覆盖 Boolean 表示 consent。
- 将政策接受等同于 facial-data purpose consent。
- 在 M3 直接执行图像解码、人脸检测或 Original promotion。
- 为未来状态过早引入公开桶、永久 URL、图像 Provider 或真实 COS SDK。

## Consequences

M3 增加 `0003` migration、application service、ownership policy、存储 Adapter 和生成契约。上传需要一次 intent 创建和一次 complete 调用；M4 可以从 `uploaded_unverified` 安全接管。撤回后已签 URL 存在严格 TTL 残余窗口，因此必须通过 intent tombstone 和清理保证迟到对象无处理权威。

## Security / Privacy Considerations

数据库和日志不得出现签名 URL、upload token、图片 bytes、客户端路径或 Provider credential。对象 key 不含手机号、用户 ID 或文件名。Local adapter 强制解析后路径仍位于配置 root，生产配置拒绝 Local。上传频率、并发 intent 数和累计声明 bytes 必须可配置并 fail closed；完整滥用限流在 M3 Gate 验证。

## Testing Implications

使用真实 PostgreSQL 验证 append-only consent/event、唯一约束、并发与 migration lifecycle；使用合成非真人 bytes 验证 Local ingress、过期/重复 token、路径穿越、大小/MIME/完整性声明和删除。API 测试覆盖 active/pending、缺失/撤回/过期授权、横向访问、idempotency、complete/cancel 竞态、URL/日志脱敏、OpenAPI 生成与生产 fail-closed。M4 的 magic/decode/pixel/EXIF 测试不在本 ADR 的 M3 Gate 中冒充完成。
