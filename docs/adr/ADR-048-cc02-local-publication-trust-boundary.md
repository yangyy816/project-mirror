# ADR-048：CC02 本地发布可信独占边界

## Status

Accepted — 2026-08-20

Change control: `CC-P2-M5-03`

## Context

已接受的 CC02-B builder contract 明确要求 `maximum_concurrency = 1`、builder 自身不使用 concurrency，并把
builder 定位为把两个已接受 private legacy reports 投影到两个固定 tracked candidate paths 的本地工具。它要求
create-once、no-partial、异常节点拒绝和 crash/error recovery，但没有批准独立发布服务、不同 OS principal 或
transactional object store。

R05 为提高普通 filesystem failure 的可恢复性，引入 same-parent staging、incomplete marker、held directory
anchor、exact child identity/content checks 和 directory durability。独立 final review 随后构造出一个有效反例：
在最后一次 exact final/marker/anchor validation 与 marker unlink 之间，拥有相同 write/delete authority 的主动
writer 可以替换 final；原 writer 随后会成功删除 marker。继续在 marker 前后增加 validation 只会移动竞态窗口，
post-commit failure 还可能产生 unmarked residue。

POSIX held `dir_fd`、普通 file descriptor、`fsync`、hard link、`rename`、advisory lock 和 owner-controlled mode
无法阻止同 UID owner 修改 child namespace/content。Windows deny-delete sharing 可以收窄 Windows 窗口，但没有
portable POSIX 等价物。两个普通文件的内容/identity validation 与第三个 marker unlink 也没有跨平台单一条件事务
primitive。因此主动同凭据写者不能被诚实描述为当前 builder 可防御的威胁。

## Decision

- 接受 `CC-P2-M5-03 — Local Publication Trust Boundary`。这是前向 security/threat-model change control，
  不是 R05 implementation trick，也不修改既有 CC02 manifest schema、固定 output paths 或 accepted evidence。
- `LOCAL_PUBLICATION_TRUST_BOUNDARY`：从 output preflight 开始，直到 builder 返回且 Principal 取得立即的
  path/type/byte/hash/diff snapshot，`docs/research` 必须由一个可信、协作的执行者独占 write/delete custody。
  其他 Agent、进程、编辑器自动写入、同步器或第二个未协调 writer 不得在该窗口写入该目录。不能建立该
  前置条件时不得运行 builder，private-input Gate 保持关闭。
- Builder 是 create-once correctness and recovery mechanism，不是 hostile-local-writer authorization boundary。
  它保证：完整内存 validation、预存 final/staging/marker collision、symlink/junction/reparse 拒绝、协作型重复
  invocation、普通 syscall failure 和规定 crash states。它不保证抵抗 active same-credential namespace/content
  mutation、compromised process/kernel/filesystem/hardware 或未批准的 network/cloud filesystem semantics。
- Same-credential active-writer counterexample 保留为 change-control evidence。它不再作为 R05 必须用更多
  revalidation 伪修复的测试，但也不得被描述为“已被 builder 防住”。
- Incomplete marker 是 crash/recovery signal，不是 authorization、signature 或针对目录 owner 的 tamper-proof
  artifact。Successful marker unlink 只在可信独占 custody 前提下表示 logical commit。
- Git tracked diff/hash、same-SHA CI 和独立 review 是后续 acceptance snapshot authority。它们不得反向宣称
  builder 本身抵抗同权限主动写者。
- 若未来必须把 active same-credential writer 纳入威胁模型，必须另行批准不同 OS principal/privileged broker、
  protected transactional store 或 protected signing/authority service；不得继续扩张当前普通文件 writer。

## Operational protocol

1. Builder implementation先以 synthetic-only tests取得 tracked acceptance；此前 private report path/bytes 禁止。
2. 真实 manifest invocation 前，Principal 停止所有可能写 `docs/research` 的并发 Agent/工具并确认两个 fixed
   outputs、staging 和 marker 均不存在，目录链为本地非 reparse directories。
3. 单一 builder process 以 concurrency one 执行。任何 custody uncertainty、pre-existing node、unexpected
   filesystem error 或 marker recovery state都 hard stop，不读取后续 private evidence或手工修补输出。
4. Builder 返回后，在释放 custody 前立即核验两个 fixed paths 的 regular/non-reparse type、exact bytes/digests、
   marker/staging absence和 scoped Git diff。之后才可形成 candidate commit。
5. Candidate 仍须 same-SHA three-job Actions、八项 artifacts、独立 security/final review和 Principal disposition；
   这些步骤不自动打开 CC02-C或任何后续 Gate。

## Alternatives Considered

- 在 marker unlink 前再增加一次 validation：拒绝，只把主动 writer 的调度窗口后移。
- marker unlink 后 validation/rollback/recreation：拒绝，检测失败后可能制造 `FAIL + marker absent residue`，仍无
  原子条件事务。
- POSIX advisory lock、chmod或 held fd：拒绝，不能约束相同 owner/credential 的主动写者或既有 writable fd。
- 只在 Windows 持有 no-delete-share final handles：拒绝，没有跨平台一致的 POSIX guarantee。
- 现在引入 privileged publisher/service/store：拒绝，超出 CC02-B、依赖和当前 Milestone boundary；若产品未来
  需要 hostile-local-writer resistance，应独立规划。

## Consequences

- R05 已完成的 reparse、identity、exact-type、durability和 recovery hardening继续保留，但其验收必须按本 ADR
  的 trusted-exclusive-custody model执行。
- 此前 final-review 的 same-credential swap反例是有效的 portability proof，不是当前实现可继续追逐的普通 bug。
- P2-M5保持 `EXECUTING`。CC02-B builder、pre-read Gate、private input、CC02-C–E、T06–T08、MVR、M6、
  production geometry、real-user processing和QuestionBank release全部继续关闭，直到各自既定 Gate。
- 本 ADR不新增 dependency、schema/migration、OpenAPI、workflow、model、runtime artifact或 production capability。

## Security / Privacy / Data / License

本 change control只定义本地 repository publication custody，不授权读取 private reports、图片、landmark、Prompt、
object key、Provider payload或credential。Builder/tests继续synthetic-only、zero-network、zero-subprocess、
zero-replay/transform/Vision。没有新增 OSS、模型或数据资产。

## Testing Implications

- 保留pre-existing final/staging/marker、parent/child reparse、matching-byte child/marker swap、malformed input、
  write/link/unlink/fsync/close和persistent rollback failure tests。
- 增加两个遵守协议的并发invocation test：最多一个成功；成功时两个exact outputs存在且marker/staging不存在；
  失败调用不得清理winner的文件。
- 保留active same-credential final-swap probe为threat-boundary evidence，并明确其expected结果是
  `OUTSIDE_GUARANTEE_REQUIRES_EXCLUSIVE_CUSTODY`，不得把它误写成实现PASS。
- Windows、Linux `--network none`、Ruff、strict mypy、full regression、same-SHA CI和独立审查仍为mandatory。
