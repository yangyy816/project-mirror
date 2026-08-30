# D02 Autonomous Source Acquisition Operator Runbook

本 runbook 只适用于已批准的 D02 autonomy bootstrap。它不改变 public API、Provider policy
或 E1-E4 历史 authority。

## Fixed limits

- Provider budget：50 total candidates。
- Rolling tranche：10 candidates；按 ordinal 顺序开放。
- Concurrency：1；same-ordinal retry：0。
- 接受 4 个 formal source 后停止；失败/拒绝 ordinal 仍消耗预算。
- 顺序：Run → Candidate → Manifest → formal source。

## Before starting

1. 确认当前 run、migration lease、revision 和 tracked projection 与批准摘要一致。
2. 若需要网络 acquisition，代理必须是进程级 `http://127.0.0.1:7897`；启动前重新检查该
   端口确实由预期进程监听。不得使用 `8307`，该端口必须保持禁用。
3. 确认 DB authority 可写且 private registry 可读取；tracked JSON 只作为非权威摘要。
4. 确认当前 budget consumed、ordinal、tranche 和 stage 可由 DB/events 重建。

## Execution

1. 创建不可变 Run header，固定 50/10/1/0 和 target=4。
   PostgreSQL 只允许一个 bootstrap spec 和一个 run；相同 authority 只能 replay，不同 spec/run
   key 必须 fail closed。
2. 仅开放当前 tranche，逐 ordinal 创建 Candidate；每个 ordinal 只能尝试一次。
3. 每次调用先发布 primary，立即把精确 locator/file identity与digest写入private index，再将
   `PRIMARY_DURABLE` Candidate提交到PostgreSQL；只有该提交成功后才从绑定的primary创建backup。
4. Candidate 通过后建立 Manifest，再建立 formal source authority；未完成前不得跳 stage。
5. 每个阶段写 append-only event，并更新可重建 projection；不得把 Prompt、path、private
   locator、raw bytes 或 credential 写入 tracked state。
6. 达到 4 个 accepted formal source 后立即 finalize；不得继续调用 Provider。

## Failure and recovery

- `CALL_STARTED` 之后不得重试该调用，也不得为同 ordinal 创建替代 attempt；按失败事件消耗
  ordinal 并进入下一合法状态。
- 若进程在primary发布后中断，只能用DB中仍开放的`CALL_STARTED`、private index中该调用的
  精确locator/file identity和recovery-only capability重新绑定同一文件，并登记同一Candidate；
  recovery capability不得进入Provider dispatch或materialize新result，不得搜索或使用同digest的
  其他文件。无法确定Provider outcome时立即把整个run置为`FAILED_CLOSED`。
- backup、M3、QA、screening或admission技术失败只能恢复同一Candidate/Manifest/bundle，不得
  触发新的Provider调用。
- 存在`PRIMARY_DURABLE`、`DURABLE`或`M3_SUPPORTED` Candidate时，必须先完成同一Candidate，
  PostgreSQL与应用服务都会拒绝下一条`CALL_STARTED`。
- 恢复顺序为 DB authority → private registry → tracked projection。若 DB/private stage
  完整性无法证明，停止并上报，不得依据 tracked 摘要猜测进度。
- materializer 发现不一致时，只暂停 projection 更新；不得回写或覆盖 DB/private authority。
- E3/E4 legacy branch 不得重新开启；未知 schema、epoch、root、policy 或状态必须
  `FAILED_CLOSED`。

## Review budget

Review、失败诊断和恢复检查只能使用已批准的 review budget；不得隐式增加总 Provider budget，
不得通过重试补足四源目标。

## Closeout

记录最终 event sequence、consumed budget、accepted formal source count 和 terminal state。
确认 tracked projection 仍标记 `non_authoritative`，并仅包含 digest、计数和状态摘要。
