# ADR-050：P2-M5 遗失证据后的独立新研究线

## Status

Accepted — 2026-08-22

Change control: `CC-P2-M5-04`

## Context

ADR-047 的 CC02-C 只允许对冻结的 CC01-C 输入做 lossless diagnostic replay。ADR-049 的有界恢复审计已经证明
其中一项合格 Linux legacy-report capability 无法从允许的 task receipt/registry 恢复。该 change control 因而以
`EVIDENCE_LOCATION_LOST` / `FURTHER_RESEARCH_EVIDENCE_NOT_RECONSTRUCTABLE` 停止，且没有读取任何平台 private
bytes、执行 transform/Vision 或创建输出。

旧 Stage C 的 `FURTHER_RESEARCH`、0/4 eligibility、manifest、aggregate 与已存在 evidence 必须保持 immutable。
新生成、重新测量或重新构建的资料不能被声称为 legacy replay、诊断结果、历史成功漂移比较或旧 Gate 的修复。

## Decision

- 建立 `CC-P2-M5-04 — Fresh Evidence Line After Recovery Stop`。它是独立的 forward research line，不是 Repair
  Task、CC02 replay、旧 evidence replacement 或对遗失 locator 的恢复尝试。
- 只有 `04-G` 在本 ADR 下开始：它只冻结治理、数据隔离、stop rule 和后续 stage sequencing；不读取 private input，
  不生成资产，不安装 dependency/model，不运行 transform/Vision，也不选择 threshold、candidate 或 resource count。
- 若未来启动 `04-A`，它必须先独立冻结新的 resource/candidate/algorithm/runtime/policy/ontology proposal、预算与
  exact input/output custody。旧 CC01-C/CC02 private reports、case digests、output roots 和 aggregates 只能作为
  historical context，绝不作为新实验输入或 identity/Asset selection source。
- 任一新 source Asset、identity、measurement、transform、signature、policy、split、runtime/model manifest 和 private
  output 必须有新的 version/digest/opaque recoverable locator。它们不得复用旧 evidence ID，也不得改变旧状态。
- 新研究线仅在完整新 calibration、preregistration、identity-disjoint holdout、duplicate/diversity、isolation 和 M5
  technical/MVR Gates 各自通过后，才可影响未来 M5 conclusion。它不能自动打开 CC02-D/E、T06–T08、MVR、M6、
  production geometry、QuestionBank release 或真实用户处理。

## Bounded stages

```text
04-G governance and separation contract
→ 04-A new research/resource/candidate proposal
→ 04-B fresh synthetic-only calibration cohort
→ 04-C fresh calibration/diagnostic evidence
→ 04-D immutable policy/split preregistration
→ 04-E sealed holdout and independent review
→ separate M5 disposition
```

Every stage is a separate bounded task with its own candidate commit, exact-SHA CI, artifact review and explicit
stop result. A failed or unavailable stage does not permit stage skipping, evidence substitution or retry expansion.

## Consequences

- P2-M5 remains `EXECUTING`; its current MVR result remains `NOT_EVALUATED`.
- The accepted CC02 recovery stop remains final for legacy evidence. CC02-D/E is closed permanently for that lost
  input set; a future fresh line is not a reopening.
- `04-G` creates no database, API, dependency, model, runtime, production capability, test fixture or image asset.
- Stage `04-A` must return to Principal if it needs a new architecture, schema, public contract, license disposition,
  adult-policy exception, provider scope or resource-envelope decision.

## Security / Privacy / Data / License

The fresh line remains synthetic-only and does not authorize real-person references, User relations, sensitive
classification, beauty scoring, Prompt/plaintext logging, object keys, signed URLs, secrets or production providers.
Future private evidence follows ADR-049: Principal-owned registry custody, opaque recoverable locators, no Agent
discovery and no tracked private bytes. Existing qualified runtimes retain their approved scope only; no new dependency,
model or license approval is implied.

## Validation

`04-G` requires Markdown formatting, `git diff --check`, authority/conflict scans, no-private-field scans, unchanged
schema/OpenAPI/dependency/workflow checks, exact-SHA CI, artifact inspection and independent security/final review.
