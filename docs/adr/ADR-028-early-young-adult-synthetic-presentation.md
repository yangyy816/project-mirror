# ADR-028：首包合成年轻成年女性年龄呈现控制

## Status

Accepted — 2026-08-17

## Context

P2-M2-V01 的八个 synthetic-only、clearly-adult 女性候选均保持成年人呈现，但只用宽泛的
`early-adult` Prompt，没有首包年龄呈现重心、双向人工筛查或 selection exclusion。只读视觉审查
确认样本整体偏成熟，尤其部分 coverage cells 的视觉重心接近 30+，不符合首发面向 35 岁以下
女性用户的题库方向。把目标写成 `16–25` 会直接包含未成年人；把“更年轻”简单优化为童颜、
校园语境或单一网红脸，又会违反 18+、clearly-adult、synthetic-only 与 anti-homogenization。

## Decision

- The internal synthetic female question-bank should shift its visual age presentation toward
  clearly-adult early-young women. Primary presentation target: 18–25. Secondary range only when
  needed for coverage: 26–30. De-emphasize 31–34 and avoid 35+ looking outputs in the first pack.
- Hard boundary: no under-18, no minor ambiguity, no schoolgirl framing, no childlike presentation.
  “Younger” must not be achieved through infantilization, homogenization, or loss of morphology
  diversity.
- 年龄区间是 Prompt、人工 presentation review 与首包 selection 使用的视觉呈现范围，不是生物
  年龄事实、自动年龄估计、敏感分类或真实用户属性。P2 不引入 age-estimation model。
- `MINOR_AMBIGUOUS`、`CHILDLIKE_PRESENTATION` 与 `SCHOOLGIRL_FRAMING` 是 hard reject，任何人工
  selection 决定都不能覆盖。`ADULT_PRESENTATION_TOO_MATURE_FOR_PRIMARY_PACK` 只阻止进入首包，
  不是全局内容安全失败，也不删除来源、生成或 QA 证据。
- `ADULT_PRESENTATION_SECONDARY_RANGE` 可在连续 morphology/identity coverage 确有需要时保留
  26–30 候选；31–34 降低优先级。明显 35+ 的成年输出不得进入首包，但可作为不可变 rejected/
  excluded evidence 保留。
- PromptTemplate 和 GenerationPolicy 通过新版本前向实施；P2-M2-V01 Prompt、manifest、图片和
  provenance 不修改。V-next 每个 item 仍锁定 Prompt digest、policy reference、coverage cell 与
  source checksum。
- 年龄呈现不能替代连续 morphology coverage。V-next 仍跨多个 coverage cells，保持自然皮肤、
  identity variation、无审美排名、无统一模板脸，并在 admission/review 时检查 adult clarity 与
  identity/morphology diversity。
- Codex native `image_gen` 仍只是 ADR-026 批准的 operator-assisted offline synthetic research
  source，不是 production `ImageGenerationProvider`。真实用户运行时 generation 调用保持 0。

## Alternatives Considered

- 将实现目标写成 `16–25`。
- 只改一个 Prompt 形容词，不增加 policy、review reason code 或 selection boundary。
- 使用自动年龄估计模型为合成人脸分箱。
- 把所有成年但偏成熟的输出作为安全失败删除。
- 用单一年轻模板脸替换不同 morphology cells。

## Consequences

首包获得明确、可审计的年轻成年女性视觉方向，同时 adult safety 与 anti-homogenization 保持
fail closed。现有 schema、公开 API、Provider Adapter、M2 frozen evidence 和 M3 Vision contract
不变。Prompt 内容与生成图片继续保存在 ignored private storage；Git 只记录 policy/rubric、opaque
references、digests、aggregate review 与 checksum evidence。

该决定不批准 QuestionBank release，也不推进 P2-M4。P2-M6 release refinement 必须把 hard reject、
首包 exclusion 与 immutable manifest membership 分开表达。

## Security / Privacy Considerations

禁止真人 reference、名人/网红 imitation、社交平台或搜索结果肖像、真实用户资产、未成年/疑似
未成年呈现、校服/校园未成年 framing 与儿童化 styling。日志和公开 evidence 不记录 Prompt、图片、
private path、object key 或 Provider raw payload。人工 review 只保存 version、reason code、actor、
timestamp、outcome 与 allowlisted aggregate。

## Testing Implications

- 验证 V01 checksum、Prompt digests 和 manifest 不变。
- V-next Prompt negative scan 必须包含 minor、schoolgirl、childlike、juvenile 与 babyface-minor
  ambiguity 的禁止语义，并包含 clearly-adult、young woman 与 primary presentation scope。
- 每张候选先做 hard adult-clarity review，再做首包 presentation selection；未知或 minor ambiguity
  fail closed。
- cohort review 同时记录 coverage-cell occupancy、identity distinctness 与 homogenization risk；
  “看起来更年轻”不能单独构成 admission PASS。
