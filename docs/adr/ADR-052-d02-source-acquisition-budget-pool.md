# ADR-052: D02 Source Acquisition Budget Pool

## Status

Accepted — 2026-08-31

## Context

D02 自治 source acquisition 需要在一次 run 内管理有限的 Provider 预算，同时保持
Candidate、Manifest 和 formal source authority 的边界清晰。已冻结的运行参数为：总预算
50、rolling tranche 10、串行并发 1、不重试同一 ordinal。只有 admission 成功时才要求并
接受 4 个 formal source；暂停或预算耗尽可以少于 4。
E3/E4 是历史兼容分支，永久 `FAILED_CLOSED`，不为本设计新增 E5/E6/E7 schema 或 trigger
分支。当前 base 是 rejected candidate，已知 materializer findings 仍需由主线程处理。

## Decision

1. D02 使用单一 generic acquisition run；五个 acquisition 核心模型恰为
   `D02CohortSpec`、`D02SourceAcquisitionRun`、`D02SourceAcquisitionEvent`、
   `D02SourceCandidate`、`D02SelectedSourceManifest`。Formal source 是下游阶段，不计入这五类。
   Bootstrap spec 与 run 都是 PostgreSQL singleton；相同 authority 只能幂等 replay，不同 spec
   或 run key 不得复制第二个 50-call pool。
2. Run header 不可变；Tranche 不单独建模，由 append-only event 与 reconciliation projection
   表达。Candidate 必须先于 SelectedSourceManifest，Manifest 必须先于下游 formal source。
3. Candidate ordinal 为 1..50，每个 ordinal 只允许一次尝试；失败或拒绝会消耗该 ordinal，
   不得同 ordinal retry。Tranche 只能按顺序滚动开放。
4. PostgreSQL 是预算、ordinal、event 和 candidate 的唯一业务权威。Private checkpoint 仅保存
   opaque locator 与 primary/backup digest index，用于可用性恢复，不决定状态或形成权威链。
   Tracked state 是允许滞后的纯派生 projection。
5. 恢复按 stage 感知：先重建 DB authority；private checkpoint 只用于定位/可用性核验；tracked
   projection 仅供展示。无法证明上一 stage 的完整性时不得跳到下一 stage。所有 tracked 文件不得
   包含 Prompt、path、private locator、raw bytes 或 credential。
6. PostgreSQL trigger 只保护不可变/append-only、同一 run 的 ordinal 唯一性、event sequence、
   终态后禁止追加，以及 admission 成功时 final source 的全局四源完整性。连续研究/质量 policy
   不在 DB 中推断；`D02_GENERATION_POLICY_V1` 的四个 selector slot 只由版本/digest 与应用层测试
   绑定。永久 DB 内容约束仅覆盖 synthetic adult、允许年龄段与 `suspected_minor=false`。
7. bootstrap 只建立一次 registry/run authority；需要的 migration 使用 D02 shared lease，
   不改写 E1-E4 历史数据。E3/E4 旧 schema 保持永久 `FAILED_CLOSED`，新 acquisition 路径不
   通过新增 epoch 分支兼容它们。
8. two-copy 仅是 availability 机制：保留 private checkpoint 与 digest-only DB/tracked
   projection；它不改变 DB 的唯一业务权威地位。
9. 收到 `CALL_STARTED` 后不得重试同一次调用。
10. review 预算必须显式预留并由 CI/review gate 检查；不得因 review、失败诊断或 materializer
    恢复而隐式增加 Provider 调用预算。
11. 两副本按 `primary publish → private locator/file-identity index → PRIMARY_DURABLE Candidate
commit → backup publish → Candidate reconciliation` 排序。进程中断后只能用 DB 中仍开放的
    `CALL_STARTED` 与 private checkpoint 的精确 locator/file identity 重放同一 primary；禁止扫描、
    替换文件或创建新 Provider call。恢复只签发不能进入 Provider dispatch 或新 result
    materialization 的 recovery-only capability，并必须同时提交 exact `BoundPngFile`；若 Provider
    outcome 无法判定，必须用该 open-call event 原子进入 `FAILED_CLOSED`。
12. 任一 Candidate 处于 `PRIMARY_DURABLE`、`DURABLE` 或 `M3_SUPPORTED` 时，不得创建下一条
    `CALL_STARTED`；必须先让同一 Candidate 达到 `QA_ACCEPTED` 或 `QA_REJECTED`。
13. `calls_without_accept` 是当前 `content_review_epoch` 内自最近一次 accepted/review resume
    起的连续计数；授权的 D02 Principal review 可开启下一 epoch并清零该计数，但
    `budget_consumed` 永不清零、扩容或回退。
14. Bootstrap 不接受调用者临时编造的 identity。四个 D02-only identity 使用
    domain-separated canonical JSON 固定为：
    - `mirror.demo/D02AcquisitionProviderIdentity/v1`：只绑定已接受的 ImageGen control-plane、
      endpoint、credential boundary、retention 与 Prompt policy，不绑定已被本 ADR 取代的旧四调用预算；
      digest 为 `e3d94667886b21f80ae30fce1f49bb5a072dd3678506d21091d48ab88029bc05`；
    - `mirror.demo/D02CandidateM3PrescreenPolicy/v1`：绑定当前 M3 runtime/model/topology/config，
      Candidate 只执行一次 provisional source inspection，Manifest 后仍强制正式三次重跑；digest 为
      `e40d23b47551720fd1cd2630ac3e8bfdf65e8d3184e9c4b2e5127a4d09c30b09`；
    - `mirror.demo/D02CandidateQAPolicy/v1`：复合绑定 Candidate M3 prescreen、规范化、
      Principal manual review、成年合成、no-real-person/no-celebrity、anti-homogenization 以及
      Candidate evidence 仅为 provisional；digest 为
      `b79d03d6a738044cca032029ba2f84618c613e0539bd93ce8f19ac5dcc1cf178`；
    - `mirror.demo/D02AutonomousAcquisitionRunKey/v1`：绑定唯一自治授权、最终运行时 Gate、E3/E4
      `FAILED_CLOSED` 与 forward-only policy；digest 为
      `04c4dacd3199bed812aeef542cea12b521689aa58796dd2f0ea20f8a9683e1a2`。
    runtime 与 model digest 继续直接复用已有 tracked authority。Operator 只能使用这些 replayable
    defaults；测试占位 digest、branch SHA、随机值或 private preimage 均不得进入 run bootstrap。
15. 正式 application entrypoint 是 D02-owned、非 HTTP 的 operator。`call-session` 必须先在短事务中
    commit `CALL_STARTED`，再通过 non-TTY stdin 消费恰好一条 bounded、newline-delimited result
    envelope。Provider 调用、result materialization、文件 I/O、M3、QA 与 screening 均不得持有数据库锁。
    Provider 调用、result materialization、文件 I/O、M3、QA 与 screening 不得持有数据库 transaction
    或 row lock；第21项的 session advisory mutex 只作同run外部执行互斥，不承载业务状态。
    Operator stdout/stderr 只允许 ordinal、slot、ID、digest、计数和安全错误码，不得输出 Prompt、tool
    payload、data URL、bytes 或 private locator。
16. Candidate 入选后的正式 source 构造采用 sealed staged builder：finalized Candidate Manifest →
    provisional descriptor/Asset ID → 三次真实 source M3 → manifest-bound Principal review →
    facts-independent generic source row → runtime-handle-bound M3 evidence → R2 facts → byte-equal
    source-row replay → formal identity/runtime packet。Candidate M3/QA evidence 不得替代正式三次 M3。
17. Formal source manifest 存在两个不可混淆的 digest domain：R2 runtime packet 使用
    `D02SourceAuthorityManifest/v2` digest；generic Report/admission 使用
    `D02GenericFormalSourceManifest/v1` digest。两者绑定相同四个有序 entry，但不得互相替代。
18. Final runtime 分两阶段：第一阶段完成 48 cases、96 M4、144 result M3，每个 first-replay
    JPEG 立即 two-copy durable；完整 PREPARED checkpoint 成功后，人工 review、screening replay 或
    admission failure 的恢复只重放 checkpoint，不再次调用 M3/M4。第一阶段技术失败仍按本 ADR 的
    same-Manifest recovery 语义处理，且永不新增 Provider 调用；若已存在 result bytes 却缺少可验证
    checkpoint，必须 fail closed，不得猜测或重复执行。
19. 48 个 result JPEG 使用固定 ignored availability index；primary/backup 分别 create-new、re-read、
    SHA-256/尺寸/file identity 相等后才可进入 generic bundle。该 index 不是业务 authority，locator
    不进入 Report、PostgreSQL 或 tracked projection。
20. Generic admission assembly 固定生成 4 source Assets、48 result Assets、48 AssetVariants、
    1 Report、1 QuestionBank 与 16 QuestionPairs，并仅交给既有单 PostgreSQL 事务 coordinator。
    duplicate policy digest 为
    `f3ab1e7255744a4653456dbc25e9514b54caf1ba9faac765b4f2913edd97b4c5`，pHash implementation
    digest 为 `a820c98dd25fe76106891a5d38affe04c8172af8bdec95b3261eb724805925df`；
    pHash 只形成观察证据，不在本版本引入自动 rejection threshold。
21. Official final runtime operator 必须在独立 PostgreSQL connection 上取得 run-scoped session
    advisory lock，并覆盖 source assembly、M3/M4、人工 review、screening 与 admission；竞争者立即
    fail closed。ignored `D02_FINAL_RUNTIME_CHECKPOINT.json` 只保存 run/Manifest/spec/runtime-bound 的
    replayable adapter evidence与sealed decisions，标记为 recovery-only/non-business-authority；DB run
    state仍是唯一业务权威。

## Alternatives

- 为 E5/E6/E7 继续复制 schema 与 trigger 分支：拒绝，会扩大不可变兼容面并破坏单一 generic
  run 设计。
- 将 tracked JSON 作为运行时 authority：拒绝，tracked state 只是可重建且可滞后的摘要。
- 允许同 ordinal retry 或 hidden reserve calls：拒绝，与 retry=0 和总预算 50 冲突。
- 在 DB trigger 中编码全部视觉/研究 policy：拒绝，DB 仅执行结构性和全局完整性约束。
- 在 CALL_STARTED 后自动重试：拒绝，无法证明调用是否已消耗 Provider 预算。

## Stage-aware failure handling

| 阶段                         | durable authority 已存在                         | durable authority 不存在                                                                                              |
| ---------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| dispatch 前                  | replay DB event/candidate；不得重复 ordinal      | 可创建下一合法 event；保留预算边界                                                                                    |
| `CALL_STARTED` 后            | 以 DB event 为准；禁止 retry                     | 若精确 primary 与 file identity 可由 private index重放，则补写同一 Candidate；否则 outcome 不确定即全 run fail closed |
| Candidate primary durable 后 | 只处理同一 Candidate 的 backup/M3/QA；不新增调用 | 不得凭 tracked 摘要或目录扫描补写 Candidate                                                                           |
| Manifest durable 后          | 可重建下游 formal source                         | 不得跳过 Candidate 或直接生成 formal source                                                                           |
| admission 成功               | 必须恰好 4 个 formal source 后 finalize          | 少于 4 不得宣称 admission 成功                                                                                        |
| 暂停或预算耗尽               | 保留已消费计数，可少于 4                         | 进入显式 paused/terminal state，不补预算                                                                              |

CI/review gate 必须验证状态可重建、预算不超界、失败不重试，并验证 tracked projection 可滞后。

## Consequences

预算、恢复和终止条件可审计，且不会通过新 epoch 分支扩张 schema。实现需要 append-only
events、stage-aware materializer 和 PostgreSQL 跨行完整性检查；旧 E1-E4 replay 仍需单独保持。
tracked projection 可能短暂落后 DB/private authority，但不得被当作权威。

## Validation

- 验证 50 ordinal、10-item tranche、serial=1、retry=0、最终恰好 4 source。
- 验证 Candidate→Manifest→formal source 顺序、非法状态转换、终态追加和同 ordinal retry
  均 fail closed。
- 验证 R2 runtime/generic formal 两个 manifest digest domain 均可重放且不可替换。
- 验证完整 PREPARED stage 在人工 review/admission recovery 中不重复 M3/M4，只重放公开 evidence。
- 验证 PREPARED/REVIEWED crash recovery、checkpoint tamper/substitution 与 run-scoped advisory
  lock concurrent loser。
- 验证 48 result 的两副本 tamper/collision/partial recovery 与 52 Asset/48 AssetVariant assembly。
- 验证 DB/private/tracked 优先级与 stage-aware 恢复；验证 tracked state 不含敏感字段。
- 在真实 PostgreSQL 上验证 bootstrap、append-only trigger、跨行四源完整性及 downgrade guard。
