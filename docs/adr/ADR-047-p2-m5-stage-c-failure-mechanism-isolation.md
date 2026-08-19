# ADR-047：P2-M5 Stage C 失败机制隔离

## Status

Accepted — 2026-08-19

Change control: `CC-P2-M5-02`

## Context

`CC-P2-M5-01-C` 在 candidate `042f77e4b6708be827f2033a9740e348ae778f69`、GitHub Actions run
`32237678569` attempt 2 上被接受为 `FURTHER_RESEARCH`。六个候选均有 failed 或 missing case，冻结的
12/12 complete-case rule 因而使 Stage D eligible candidate count 为 0/4。该结论、manifest、aggregate、
private reports 和全部失败证据不可改写。

现有 aggregate 记录 218 个 `PLAN_BUILD_FAILED` 和 14 个 `TARGET_DIRECTION_MISMATCH`。进一步只读审查发现，
Stage C runner 的同一个 `try` 同时包围 plan construction、warp-plan authority、transform、Vision 和
measurement；其 generic `ValueError` handler 将这些不同阶段统一压成 `PLAN_BUILD_FAILED`。Project Mirror
的 geometry domain 已提供 `INVALID_WARP_PLAN`、`FOLDOVER_REJECTED`、`OUT_OF_BOUNDS_DISPLACEMENT` 等安全
reason code，但现有 Stage C evidence 没有无损保留它们。

因此，当前证据足以拒绝 Stage D，却不足以判断应当修改 plan builder、transform、measurement formula，还是
将某一 dimension 标记为 `UNSUPPORTED_IN_P2`。直接修改算法、扩大 cohort 或生成新资产会在根因未知时浪费资源，
也可能对已读取的 calibration evidence 做非预注册调参。

## Decision

- 接受 `CC-P2-M5-02 — Stage C Failure-Mechanism Isolation`，作为新的前向 research change control。它不是
  Repair Task，不创建 `T09/T10`，也不重新执行 `CC-P2-M5-01-C` 的 Gate。
- 旧 manifest digest、cohort digest、case-set digest、aggregate、qualified platform report digests、runtime、
  model、topology、algorithm、candidate family、formula、magnitude grid 和 12-identity calibration split 均为
  immutable inputs。
- 新 diagnostic harness 必须使用独立版本和 private output roots。它不得修改旧 runner、transform algorithm、
  domain authority、database schema、OpenAPI、dependency 或 model artifact。
- 每个 terminal case 必须分别记录 allowlisted `terminal_stage`、safe diagnostic reason 和（若存在）原始
  `DomainValidationError.reason_code`。不得记录 raw exception、landmark、Prompt、图片、路径、object key 或
  Provider payload。
- 现有 `PLAN_BUILD_FAILED` 不得直接支持 `UNSUPPORTED_DIMENSION`。只有 lossless diagnostic evidence 完成后，
  Principal 才能在另一个 forward change control 中决定 candidate-v2、formula-v2、plan-v2 或 unsupported
  disposition。
- target error、control drift、cross-platform tolerance、pHash threshold 和 near-duplicate threshold 在本 change
  control 中全部保持 `NULL` / `NOT_SELECTED`。Diagnostic output 不进入 Stage D eligibility，也不把旧 0/4
  改写为 PASS。
- 14 个 legacy direction-mismatch platform cases 只按 CC02-B 中提交的 opaque case digest 选择。旧 runner 在
  direction check 后才写 result artifact，因此这些 case 不存在 accepted legacy result bytes。CC02-C 必须从冻结
  input 重新执行一次 transform，把新产生的 bytes 作为独立 diagnostic evidence，并把完全相同的 bytes 送入三次
  Vision measurement；不得声称这些 case 具备 legacy-success drift comparison。三次都是同一错误符号时记录
  `TARGET_DIRECTION_STABLE_MISMATCH`；任意跨号或零值记录 `MEASUREMENT_SIGN_UNSTABLE`。两者都保持 candidate
  ineligible。
- 在访问 private calibration input 前，必须先提交 diagnostic manifest，绑定旧 private reports、opaque case
  digests、cohort/case/runtime/model/topology/algorithm digests、资源上限、reason taxonomy 和 stop rules。
- 若 accepted private reports 或其 exact digests 不可重建，change control 以
  `FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE` 停止；不得根据 redacted aggregate 猜测 case identity 或
  根因。

## Bounded stages

1. `CC-P2-M5-02-G`：本 ADR、diagnostic protocol、acceptance skeleton 和 closed Gates。
2. `CC-P2-M5-02-A`：版本化 diagnostic harness 与 deterministic reason-code tests；不访问 private input。
3. `CC-P2-M5-02-B`：immutable diagnostic manifest checkpoint；只绑定既有 input/evidence。
4. `CC-P2-M5-02-C`：Windows 与 zero-network Linux 串行 private replay，零 retry。
5. `CC-P2-M5-02-D`：提交 redacted mechanism matrix 与 `DIAGNOSIS_COMPLETE` 或 `FURTHER_RESEARCH` decision。
6. `CC-P2-M5-02-E`：same-SHA artifacts、独立 security/research-integrity review 与 Principal disposition。

每个 stage 需要独立 bounded-task contract、targeted validation、candidate commit、same-SHA Actions 和 artifact
inspection。`02-G` 的接受只开放 `02-A`，不得越级访问 private input。

## Alternatives Considered

- 直接把 `PLAN_BUILD_FAILED` 解释为 unsupported dimension：拒绝，当前 code 丢失了 plan/transform 安全 reason。
- 立即实现 candidate-v2 并重跑六候选：拒绝，尚不知道应修改哪一个 authority。
- 立即增加 12/24 个 identities：拒绝，Stage B 现有 12 identities 已完整，新增样本不能修复 reason loss。
- 放宽 complete-case 或忽略少量 direction mismatch：拒绝，会追溯改变已接受的 premeasurement rule。
- 使用人工 review 把技术失败改为 PASS：拒绝，人工 evidence 不能覆盖 plan、direction 或 completeness failure。

## Consequences

- P2-M5 保持 `EXECUTING`；`CC-P2-M5-01-C` 保持 `ACCEPTED_FURTHER_RESEARCH`。
- Stage D/E、T06–T08、P2-MVR-v1、production geometry、real-user facial processing、M6 和 QuestionBank release
  继续关闭。
- 成功完成诊断也不批准算法修复或新 threshold；它只允许 Principal 创建一个证据更充分的后续 redesign
  change control。
- 没有新增 generation attempt、identity、dependency、model、schema、migration、API 或 production capability。

## Security / Privacy / Data / License

输入仍是已接受的 synthetic-only calibration evidence。Private report、图片、landmark 和 runtime artifact 不进入
Git；committed output 仅包含 opaque case digest、版本/digest、aggregate count、allowlisted stage/reason 和有界
numeric distribution。禁止真人、User relation、敏感分类、颜值评分、Prompt plaintext、credential、private path、
object/storage reference 和外部网络。

Windows private replay 在读取任何 private input 前必须建立并验证覆盖 runner 及全部 child Vision/runtime process 的
outbound deny。Network capture 只能作为证据，不能代替 containment；无法建立或验证 deny 时不得开始 replay，任何
attempted egress 都必须 hard stop。Network evidence 保持 private/redacted，不进入 Git。

本 change control 只复用 exact-manifest private Vision/OpenCV runtimes，不改变它们的批准、许可证、分发、
production 或 real-user scope。

## Testing Implications

Future evidence must prove exact input digests, 576/576 platform-case coverage, lossless failure-stage mapping, zero
unknown terminal stage, zero legacy-success drift, deterministic case/reason aggregation, three-repeat direction-sign
classification, resource/retry ceilings, Windows child-process-inclusive outbound-deny verification, Linux
zero-network, Windows/Linux serial execution, private-field redaction, OpenAPI/dependency/schema zero drift and complete
same-SHA CI.
