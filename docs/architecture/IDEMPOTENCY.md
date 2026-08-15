# Idempotency 基线

## Key 与 Scope

- 客户端为每个创建意图生成 8–128 字符的 `Idempotency-Key`；服务端只保存带服务端 pepper 的散列。
- 唯一范围是 `(actor_key, operation_scope, key_hash)`。已登录用户的 actor 为 user id；公开认证挑战使用手机号散列 + 风控域，不使用明文手机号。
- 同一 key 不能跨用户、跨 endpoint 或跨语义操作复用。

## Fingerprint

对规范化 method、route、业务 schema version 和请求体计算 SHA-256。Header 顺序、空白和非语义字段不影响 fingerprint；敏感原文不进入日志或记录。

## Replay 与 Conflict

- key + scope + actor + fingerprint 相同：返回首次持久化的状态/资源引用；运行中的异步操作返回同一 `job_id`。
- key 相同但 fingerprint 不同：返回稳定 `409 idempotency_conflict`，不得执行第二次。
- 首次事务失败且未提交任何领域状态：记录可安全重试状态；外部副作用必须使用下游幂等键。

## Expiry

具体期限是 `OPERATIONAL TARGET`，由风险和操作类型配置。支付/账务事件依靠 Provider event id 与 Ledger 唯一约束长期去重，不能仅依赖短期 IdempotencyRecord。

## Job ID

`job_id` 使用不可枚举 UUIDv4 的 32 位 lowercase hex 表示，与 `request_id` 分离。TaskEnvelope 同时携带 request_id、job_id、idempotency hash 和 schema version，使 API → Application → Worker → Provider → Log 可追踪。
