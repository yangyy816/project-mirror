# ADR-017：浏览器认证会话与 Onboarding

## Status

Accepted — 2026-08-15

## Context

P1-M1 已冻结手机号 challenge、短时 access JWT、轮换 refresh Cookie、外部年龄凭证、精确政策接受和 pending/active scope。P1-M2 必须在 Next.js Web 中消费这些契约，同时防止 access/refresh token、手机号、OTP、邀请码和年龄凭证进入持久化浏览器存储、Server Component、URL、日志或 analytics。

真实 SMS 与年龄供应商仍未获生产批准，因此 Web 必须能完整测试 deterministic 流程，但不得伪装生产注册或内置供应商秘密。

## Decision

- 浏览器只通过由 FastAPI OpenAPI 生成的 `@mirror/contracts` 客户端访问认证 API。不得手写重复 DTO，业务状态不得依赖具体 FastAPI 或 Provider 类型。
- Access JWT 仅保存在 Client Component 的内存 session store 中。禁止写入 `localStorage`、`sessionStorage`、IndexedDB、Cache Storage、Cookie、URL、HTML、Server Component props 或日志。页面刷新后只能调用 refresh endpoint 恢复 access token。
- Refresh token 继续只由 API 通过 `HttpOnly` Cookie 管理，JavaScript 不得读取。浏览器请求使用 `credentials: include`。refresh/logout 从非 HttpOnly CSRF Cookie 读取 token，并同时发送精确 `Origin`；401 后只允许一个 single-flight refresh，成功后最多重放一次原请求。
- Session store 使用明确状态：`bootstrapping | anonymous | pending | active | error`。受限页面在 bootstrap 完成前不得渲染账户数据；pending 用户只能进入年龄、政策、刷新和退出流程。
- 创建型请求的 idempotency key 使用 Web Crypto 生成。同一逻辑提交在网络结果不确定时复用原 key；用户改变 payload 或明确重新开始时生成新 key。
- 年龄凭证通过 Provider-neutral popup/message bridge 接收。必须同时验证配置的 HTTPS Provider origin、popup `event.source`、CSPRNG state nonce、消息 schema、超时与 popup 关闭；一次性 credential 只在消息处理与 API 请求的瞬时生命周期存在。未配置或未批准的 Provider 明确不可用，生产不得回退到手输 credential 或 Mock。
- 政策显示与提交使用 server-validated manifest，至少包含 document code、version、SHA-256 digest、标题、内容 URL 和批准状态。Client 只能提交页面实际展示且用户逐项确认的精确版本。Manifest 缺失、digest 非法、内容非 HTTPS（测试/本机例外）或生产状态非 approved 时 fail closed；组件不得自行硬编码权威版本。
- 手机号、OTP、邀请码、access token、年龄 credential 和 CSRF token 不进入 analytics、错误 telemetry 或 console。P1-M2 不接入 analytics SDK。
- 账户 shell 是 client-side authorization boundary，不是服务端权限权威；所有数据请求仍由 API 校验 bearer session/scope。静态 HTML 不得包含受保护账户数据。
- 浏览器 E2E 必须覆盖 challenge、OTP、pending onboarding、刷新恢复、CSRF、过期/错误恢复、激活和退出。测试只使用合成 fixture 与受控 Fake API/Provider，不调用真实网络供应商。

## Alternatives Considered

- 将 access JWT 放入 localStorage 或可读 Cookie。
- 让 Next.js Server Component 代理并持久化用户 token。
- 在 Web 源码中硬编码政策版本或提供手工年龄凭证输入框。
- 每个 401 独立刷新并无限重试。
- 在真实供应商未确定前跳过年龄与政策 onboarding UI。

## Consequences

刷新恢复发生在客户端 hydration 后，受限页面必须先显示无数据的安全 loading 状态。Web 配置需要独立的政策 manifest 与年龄 Provider public metadata，但不包含 secret。真实生产注册仍由 P1-M1 后端 Gate 和 Web fail-closed 配置共同阻断。

## Security / Privacy Considerations

XSS 仍可读取内存 access token，因此 Web 必须保持无第三方脚本默认、严格 CSP 候选、依赖审计和输出编码。CSRF token 不是认证凭据，但仍不得记录。popup bridge 的 origin/source/state 任一不匹配均必须忽略并最终超时，不得回显 credential。

## Testing Implications

必须用静态 source scan 与浏览器测试证明没有 Storage/token URL 路径；验证 refresh single-flight、一次重放、Cookie credentials、CSRF、popup origin/source/state、manifest fail-closed、无未授权内容闪现、键盘/label/focus/error accessibility，以及生成契约零漂移。
