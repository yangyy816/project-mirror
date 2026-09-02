# D02 Autonomous Source Acquisition Operator Runbook

本 runbook 只适用于已批准的 D02 autonomy bootstrap。它不改变 public API、Provider policy
或 E1-E4 历史 authority。

## Fixed limits

- Provider budget：50 total candidates。
- Rolling tranche：10 candidates；按 ordinal 顺序开放。
- Concurrency：1；same-ordinal retry：0。
- 接受 4 个 formal source 后停止；失败/拒绝 ordinal 仍消耗预算。
- 顺序：Run → Candidate → Manifest → formal source。
- Candidate policy digests：M3 prescreen `e40d23b...`；composite QA `b79d03d...`；
  normalization `cae980e...`；manual review `23078b7...`。

## Before starting

1. 确认当前 run、migration lease、revision 和 tracked projection 与批准摘要一致。
2. 若需要网络 acquisition，代理必须是进程级 `http://127.0.0.1:7897`；启动前重新检查该
   端口确实由预期进程监听。不得使用 `8307`，该端口必须保持禁用。
3. 确认 DB authority 可写且 private registry 可读取；tracked JSON 只作为非权威摘要。
4. 确认当前 budget consumed、ordinal、tranche 和 stage 可由 DB/events 重建。
5. Candidate M3 或 final runtime 前，固定 ignored handoff
   `.private-handoff/D02_RUNTIME_LOCATORS.json` 必须存在并通过 exact schema、runtime/model/topology/M4
   manifest digest 校验；禁止扫描或猜测历史 binary/model/runtime。

## Execution

1. 通过内部非 HTTP operator 的 `bootstrap` 创建不可变 Run header，固定 50/10/1/0 和 target=4。
   PostgreSQL 只允许一个 bootstrap spec 和一个 run；相同 authority 只能 replay，不同 spec/run
   key 必须 fail closed。
2. 每次使用同一个长生命周期 `call-session`：先提交并输出 redacted `CALL_STARTED` facts，随后才从
   non-TTY stdin 读取一条 bounded、newline-delimited Provider result envelope。输入协议仅允许
   `RESULT`、明确 `NO_RESULT` 或 `UNCERTAIN`；缺失、截断或无法分类的输入必须将整个 run fail closed。
3. 仅开放当前 tranche，逐 ordinal 创建 Candidate；每个 ordinal 只能尝试一次。
4. 每次调用先发布 primary，立即把精确 locator/file identity与digest写入private index，再将
   `PRIMARY_DURABLE` Candidate提交到PostgreSQL；只有该提交成功后才从绑定的primary创建backup。
5. Candidate 通过后建立 Manifest，再建立 formal source authority；未完成前不得跳 stage。
6. Formal source 对同一 normalized JPEG 执行三次真实 source M3 与 manifest-bound Principal
   review。R2 runtime manifest digest 与 generic formal manifest digest 分域保存，不得互换。
7. Final runtime 第一阶段只执行一次 48 cases / 96 M4 / 144 result M3；每个 first-replay
   result 立即写 primary/backup、re-read、rehash，并登记 availability-only private index。
8. 48 张 result 完成后暂停给 Principal 做 artifact review；48 个 sealed decision 齐备后只重放
   prepared public evidence生成 Report，禁止再次执行 M3/M4。
9. Generic bundle 必须重放 4 source + 48 result Assets、48 AssetVariants、16 QuestionPairs，
   然后才允许调用单事务 coordinator。
10. 每个阶段写 append-only event，并更新可重建 projection；不得把 Prompt、path、private
    locator、raw bytes 或 credential 写入 tracked state。
11. 达到 4 个 accepted formal source 后立即 finalize；不得继续调用 Provider。

Bootstrap identity 固定来自 tracked code/authority，不接受 CLI 覆盖：provider identity、M3 prescreen
policy、runtime、model、QA policy 与唯一 run key 都必须逐字节 replay。Operator 命令行只接收非敏感的
run/candidate ID、digest、ordinal、stage code；数据库 URL 仅从进程环境读取。

Candidate durable 后使用 `python -m mirror_api.demo_d02_candidate_operator`。它只从 non-TTY stdin
读取一条 `D02CandidateReviewCommand/v1`，operator 自动绑定 Candidate、normalized JPEG、slot 与真实
one-shot M3；不得用裸 `m3-supported`/`qa-accepted` Boolean 更新 ledger。

Manifest finalized 后使用 `python -m mirror_api.demo_d02_final_runtime_operator` 的单一长生命周期
session：stdin 第一行是4项 `D02FormalSourceReviewCommand/v1`；执行并 two-copy 持久化48个 result 后，
stdout 仅返回 case ID/result digest/decision sequence；stdin 第二行必须是48项
`D02ArtifactReviewCommand/v1`。该进程随后只重放 prepared evidence、构造 generic bundle并调用既有
atomic coordinator。任何 review command 均不得包含路径、Prompt或bytes。

Final runtime official entrypoint 会先取得 run-scoped PostgreSQL session advisory lock；同一 run 的
第二个进程必须返回 `FINAL_RUNTIME_ALREADY_ACTIVE`。48 个结果完整后，operator 在固定 ignored
`D02_FINAL_RUNTIME_CHECKPOINT.json` 保存 PREPARED evidence；收到48项决策后前向更新为 REVIEWED。
PREPARED/REVIEWED 恢复不加载 M3/M4 backend。若 result index 非空但 checkpoint 不存在，返回
`FINAL_RUNTIME_PARTIAL_WITHOUT_CHECKPOINT`，不得通过重新执行或目录扫描补证据。

## Failure and recovery

- `CALL_STARTED` 之后不得重试该调用，也不得为同 ordinal 创建替代 attempt；按失败事件消耗
  ordinal 并进入下一合法状态。
- 若进程在primary发布后中断，只能用DB中仍开放的`CALL_STARTED`、private index中该调用的
  精确locator/file identity和recovery-only capability重新绑定同一文件，并登记同一Candidate；
  recovery capability不得进入Provider dispatch或materialize新result，不得搜索或使用同digest的
  其他文件。无法确定Provider outcome时立即把整个run置为`FAILED_CLOSED`。
- 若 backup 已按固定 allocation 创建、但 private index 或 DB 更新中断，恢复只能精确重绑该 allocation
  与已登记 primary identity；不得再次复制、生成新名称或调用 Provider。
- backup、M3、QA、screening或admission技术失败只能恢复同一Candidate/Manifest/bundle，不得
  触发新的Provider调用。
- result runtime 中断时只允许按已知 case ordinal 与固定 index 恢复 exact primary/backup；
  不得扫描、猜测或为本地失败重新生成 source。
- 等待 artifact review 或 admission 失败后的恢复必须读取 run/Manifest/runtime-bound checkpoint；
  checkpoint digest、binding、cardinality、result two-copy 或 sealed decision 任一不一致即 fail closed。
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
