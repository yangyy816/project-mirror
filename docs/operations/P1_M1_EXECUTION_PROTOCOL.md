# P1-M1 Execution Protocol

本文件是已通过的 rolling-wave plan 的治理增量，不重做或取代 Master Planning，也不扩大 P1-M1 功能范围。

## 统一状态机

唯一状态序列为：

`PROVISIONAL → COMMITTED → EXECUTION_READY → EXECUTING → PASS → FROZEN`

- Phase 0：`FROZEN`。
- Phase 1：`COMMITTED`。
- P1-M1：已由 `EXECUTION_READY` 进入 `EXECUTING`。
- `PASS` 只表示 mandatory evidence 已由 Principal 验收；形成审计 checkpoint 后才能标记 `FROZEN`。
- 未完成、未执行或仍有 mandatory Gate 的工作不得描述为 `PASS` 或 `FROZEN`。

## Terra 架构权限边界

- Terra 可以实现 Principal planning artifact 已明确批准的架构，也可以把这些既有决策编码为 Accepted ADR。
- Terra 不得创造新的系统架构、领域边界、安全模型、隐私模型、数据库策略、Provider 策略或 Phase/Milestone 结构。
- 若实现暴露新的架构决策，Terra 必须停止在决策边界并返回 `BLOCKED`，由 Principal 分类为 implementation clarification、Milestone-local decision、ADR-required change 或 Phase 0 change control。
- Terra 报告的 PASS 只是证据。Principal 必须检查实际 diff、测试、安全影响、migration、生成物和跨任务集成后给出 `TASK_ACCEPTED`、`TASK_REPAIR_REQUIRED` 或 `TASK_BLOCKED`。

## Repair Task 协议

- 计划外实现缺陷使用 `P1-M1-R01`、`P1-M1-R02`、`P1-M1-R03` 依次编号；不得追加 `T09/T10`。
- Repair Task 必须使用与 Terra bounded task 相同的完整任务合同，并保持最小允许范围。
- 修复后先重跑直接失败的验证，再重跑必要范围的 T08；mandatory validation 不得 skip 或弱化。
- 若问题改变已接受架构，不创建普通 Repair Task，必须进入 architecture change control。
- 只有 Principal 能接受 Repair Task、决定 M1 Gate，并在 PASS 后把 P1-M1 标记为 FROZEN。

## 执行边界

当前授权仅覆盖 P1-M1。完成 M1 Gate 后停止，不实现 P1-M2；下一步应重新读取仓库现实并单独规划下一可执行 Milestone。
