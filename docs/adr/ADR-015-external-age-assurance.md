# ADR-015：外部年龄凭证与最小化 18+ 结论

## Status

Accepted — 2026-08-15

## Context

Project Mirror 的 Beta 仅面向成年人，但自行收集身份证件、姓名、出生日期或精确年龄会显著扩大高敏感数据处理和合规风险。Phase 1 必须建立可替换的年龄证明边界，而不在未验证供应商、法律条款和数据驻留前启用生产注册。

## Decision

- 年龄判断通过供应商中立的 `AgeAssuranceProvider` 完成。Application 只依赖其最小结果：`verified`、`not_verified` 或 `indeterminate`，以及供应商引用、Provider version、policy version 和可选到期信息；业务层不得依赖具体 SDK。
- 外部一次性凭证仅可在请求处理和 Provider 调用的瞬时边界出现。系统不得持久化或记录凭证原文、身份证件、姓名、生日、精确年龄、原始 Provider payload 或可复原的等价字段。
- 权威持久化证据是 append-only `AgeAssuranceRecord`：保存最小 18+ 结论、用途隔离的 Provider reference HMAC、Provider/policy 版本、验证时间、到期信息与审计关联。`User.age_confirmed_at` 如保留，仅为非权威投影，不能取代版本化证据。
- 只有 `verified` 结论可满足 18+ 激活前置；`not_verified` 和 `indeterminate` 均不得激活账户。年龄凭证与政策接受是不同事实：PolicyAcceptance 记录对指定文件版本的接受，facial-data Consent 在后续上传目的发生前单独取得。
- 开发、测试和 CI 可使用 deterministic Mock，以验证状态流和最小化持久化；Mock 不保留或记录原文且不得调用外部网络。未验证的 candidate adapter 必须明确失败。
- 真实供应商选择、接入、数据条款、地域、删除机制、法律审核和生产密钥均推迟到 Tencent Cloud 私测准备阶段。在此之前，production 必须保持注册关闭或因缺少已验证 Provider/Gate 而 fail closed。
- 年龄凭证相关表与不可变保护通过 `0002` 及后续前向 Alembic migration 追加；不得修改冻结的 `0001_phase0_foundation`。

## Alternatives Considered

- 用户勾选“我已满 18 岁”作为唯一证据。
- 保存证件照片、姓名、生日或完整第三方响应。
- 先绑定单一年龄验证 SDK，再在以后抽象。
- 在供应商与法律 Gate 前开放 production 注册。

## Consequences

Phase 1 可完成 pending-to-active 状态机与可测试 Provider contract，但不能宣称 production 年龄验证已就绪。真实 Beta 需要独立验证供应商是否满足数据最小化、数据驻留、删除、审计、PIPIA 与法律审查要求。

## Security / Privacy Considerations

年龄凭证关联信息与手机号关联均按高敏感个人数据保护。Provider 调用、错误、日志和审计采用字段白名单；记录仅允许最小结论及不可逆引用。production 在任何依赖为 Mock、Local、未验证或法律 Gate 未通过时拒绝启用。

## Testing Implications

必须验证 Provider protocol 的中立性与 deterministic 行为、敏感字段在返回/日志/持久化中不存在、verified/not_verified/indeterminate 状态、到期行为、append-only 保护、政策与年龄的双重 activation Gate，以及 production 配置的负向 fail-closed 测试。
