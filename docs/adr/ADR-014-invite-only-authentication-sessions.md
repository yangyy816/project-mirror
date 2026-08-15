# ADR-014：邀请制手机号认证与会话

## Status

Accepted — 2026-08-15

## Context

Phase 0 仅提供认证领域骨架和 `501` 占位端点。Phase 1 需要为邀请制 Beta 提供可审计的手机号认证、会话和 onboarding 前置状态，同时不得持久化或记录手机号、验证码、邀请码或令牌原文。

## Decision

- 新用户注册必须完成有效邀请码验证；已存在且未删除的用户重新登录不要求邀请码。邀请码在短信 challenge 创建时绑定候选注册，不得在此时消费；只在验证码验证、新用户创建和邀请码兑换的同一数据库事务中消费。
- 手机号仅接受规范化的中国大陆 `+86` E.164 号码。原始号码只允许存在于请求处理与 SMS Provider 的瞬时调用边界；持久化、索引、幂等 actor key 和审计关联使用用途隔离的 HMAC 派生值，不保存原文。
- 验证码由 CSPRNG 生成，短时有效、限制尝试次数且只能成功消费一次。验证码原文只在瞬时短信发送和验证请求边界存在；持久化记录只保存用途隔离的验证值。挑战、短信重发、验证码验证与会话创建均受手机号、IP 和设备维度的限流保护；错误响应不得枚举账户或邀请码状态。
- Access token 使用短时 HS256 JWT，默认五分钟。签发与验证使用支持轮换的 keyring，并以 `kid` 标识签名密钥；只接受固定算法、issuer 与 audience。JWT 必须包含 `iss`、`aud`、`sub`、`sid`、`scope`、`jti`、`iat`、`nbf`、`exp`，不得包含手机号、年龄凭证或其他敏感原文。
- Web refresh token 使用可轮换的不透明 token，默认绝对期限三十天。它只可通过 `HttpOnly`、`Secure`、`SameSite=Lax` Cookie 传输，持久化只保存用途隔离的 HMAC 派生值。刷新与基于 Cookie 的会话撤销必须通过 CSRF 与 Origin 校验；实现不得让 JavaScript 读取 refresh token。
- 每个登录会话属于 session family。刷新在事务与锁保护下轮换；发现已使用的 refresh token 被重用时，撤销该 family 的全部会话并拒绝此次请求。显式退出撤销当前 family 并清理浏览器 Cookie。
- 新创建用户初始为 pending，只能使用当前用户查询、年龄凭证、政策接受、刷新和退出能力。只有有效的 18+ 年龄凭证和精确版本的必需政策接受均完成后，用户才可成为 active。政策接受是 append-only 的 `PolicyAcceptance` 记录；它不替代用途级 `Consent`，后者在需要处理 facial data 的上传阶段单独建立。
- `POST` 创建型认证接口遵守 ADR-008 与 `Idempotency-Key` 规则。认证/会话持久化将在 `0002` 及后续 Alembic migration 中以前向追加方式实现，绝不重写冻结的 `0001_phase0_foundation`。
- 生产注册在可验证的 SMS Provider、年龄凭证 Provider、密钥、Redis 限流和相关安全 Gate 未满足时必须关闭或启动失败；development/test 的 deterministic Mock 不得进入 production。

## API Boundary

所有接口位于 `/api/v1`，错误维持 `code`、`message`、`request_id`、`details` 信封；下列 `POST` 均要求 `Idempotency-Key`。

| Endpoint                            | Success | Contract boundary                                                                            |
| ----------------------------------- | ------- | -------------------------------------------------------------------------------------------- |
| `POST /auth/sms-challenges`         | `202`   | 接收 `+86` E.164 手机号与可选邀请码；新用户必须有有效邀请码，challenge 仅绑定而不消费。      |
| `POST /auth/sessions`               | `201`   | 接收 challenge 与 OTP；原子消费 OTP、创建新用户（如需要）、兑换邀请码并创建 session family。 |
| `POST /auth/token/refresh`          | `200`   | 通过 refresh Cookie 及 CSRF/Origin 校验轮换 token；重用撤销 family。                         |
| `DELETE /auth/sessions/current`     | `204`   | 撤销当前 family 并清理浏览器 Cookie；适用相同 Cookie 安全校验。                              |
| `GET /users/me`                     | `200`   | 仅返回 user id、状态、scope 与 onboarding requirements，不返回手机号散列。                   |
| `POST /users/me/age-assurances`     | `201`   | 交换一次性外部年龄凭证；持久化遵循 ADR-015 的最小化记录。                                    |
| `POST /users/me/policy-acceptances` | `201`   | 接收精确 document code、version 与 digest，并追加政策接受记录。                              |

## Alternatives Considered

- 密码或第三方 OAuth 认证。
- 要求每次登录都输入邀请码。
- 长期 access JWT 或由 JavaScript 持有 refresh token。
- 在 `User` 上用 Boolean 或时间戳覆盖年龄与政策状态。

## Consequences

认证需要 session lineage、邀请码兑换审计、版本化政策接受和真实 PostgreSQL 并发验证。Web 与未来 iOS 均可使用短时 Bearer access token；Web 还需要遵守 refresh Cookie、CSRF 和 Origin 边界。邀请管理只提供受限 CLI，不在本里程碑建立公开管理 API。

## Security / Privacy Considerations

日志、错误、数据库字段和审计 payload 不得记录手机号原文、验证码、邀请码原文、access/refresh token、CSRF token 或签名 URL。密钥须按手机号索引、OTP、邀请码、refresh token 等用途隔离。生产配置必须拒绝弱密钥、Mock 限流器、开发 CORS、Debug 或未验证注册能力。

## Testing Implications

必须在真实 PostgreSQL 与 Redis 上验证邀请码并发兑换、challenge 幂等与一次消费、OTP 过期/次数限制、刷新轮换与 reuse family revoke、退出、pending scope、政策激活 Gate、限流、CSRF/Origin、日志脱敏、生产 fail-closed，以及 OpenAPI 与生成 TypeScript 契约无漂移。
