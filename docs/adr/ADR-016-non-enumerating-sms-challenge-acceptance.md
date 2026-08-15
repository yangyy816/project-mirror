# ADR-016：不可枚举的短信挑战受理

## Status

Accepted — 2026-08-15

## Context

ADR-014 同时要求：现有用户重新登录不需要邀请码；新用户必须先提供有效邀请码；无资格的新用户不得触发短信成本；公开错误不得暴露账号或邀请码状态。若 API 对现有号码返回 `202`、对无有效邀请码的新号码返回 `401`，攻击者便可通过状态码枚举手机号是否已注册。

## Decision

- `POST /api/v1/auth/sms-challenges` 是“请求已受理”边界，不承诺短信已经发送。格式合法且通过限流的请求统一返回 `202` 与相同的 `challenge_id`、`expires_at` 结构。
- 现有用户或具备有效邀请码且允许新注册的用户进入真实挑战路径：调用 SMS Provider，并持久化只含 HMAC 的 `PhoneVerificationChallenge`。
- 无有效邀请码或当前禁止新注册的未知号码进入 decoy 路径：不得调用 SMS Provider，不得创建真实 `PhoneVerificationChallenge`，也不得产生可用于认证的 OTP。服务只在既有 `IdempotencyRecord` 中保存不可猜测的受理引用与完成时间，以保证相同 key/fingerprint 的重放返回同一安全引用。
- decoy `challenge_id` 在 `POST /api/v1/auth/sessions` 中按普通未知挑战处理，始终返回通用认证失败；它不能创建用户、消费邀请码或建立 session。
- 同一 idempotency key 但不同 fingerprint 仍返回 `409 idempotency_conflict`。限流在真实与 decoy 判定之前执行，两条路径的公开错误、响应 schema 与状态码保持一致。
- 内部审计只记录通用 challenge 受理事件与不可猜测引用，不记录手机号、邀请码或用于公开枚举的分类标签。Provider 失败仍返回通用认证失败，不伪装为已成功发送。

## Alternatives Considered

- 对所有号码发送短信，再在 OTP 后校验邀请码：降低枚举差异，但允许无资格请求制造短信成本与骚扰。
- 要求现有用户每次登录也输入邀请码：违背已批准的登录语义。
- 对未知号码直接返回 `401`：实现简单，但公开泄露账号存在性。
- 在当前 Milestone 引入异步短信队列和固定延迟响应：可进一步降低时间侧信道，但超出 M1 已冻结边界；真实 Provider 接入前仍须以基准测试复核时间侧信道。

## Consequences

客户端不能把 `202` 解释为短信必达，只能进入统一验证码等待状态。未知或无资格请求不会获得真实认证能力。内部监控需要分别统计 Provider 调用成功、通用受理和后续验证失败，但这些分类不得出现在公开响应中。

## Security / Privacy Considerations

该决策关闭直接 HTTP 状态码枚举并避免无资格新号码触发短信。真实 Provider 延迟仍可能形成统计时间侧信道；在 P9 启用真实短信前，必须通过异步化、响应时间整形或经基准验证的等效控制关闭该风险。手机号、邀请码、OTP 与 decoy 分类均不得进入日志或公开错误。

## Testing Implications

必须在真实 PostgreSQL 上验证现有/未知号码与有效/无效/缺失邀请码的公开响应均为相同 `202` schema；decoy 重放返回相同引用且不发送短信、不创建 challenge；decoy session 创建失败；相同 key 不同 fingerprint 冲突；有效邀请的真实挑战与最终邀请码消费语义不变。
