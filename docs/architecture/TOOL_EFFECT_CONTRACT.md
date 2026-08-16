# P6 Tool Effect Contract 与 Agent Runtime 方向

## 状态与边界

- 状态：`PROVISIONAL` P6 directional contract。
- 本文不授权 P6 实现、schema、SDK、Provider、依赖或模型选择。
- Project Mirror 始终拥有 `AgentContext`、`EditPlan`、`ImageVersion`、`EditOperation`、`ToolRun`、`VerificationResult`、`PreferenceEvent` 与 evidence semantics。Agent SDK、Provider 或模型不能成为 domain authority。

## Agent Runtime state machine

```text
CLARIFY
→ RETRIEVE
→ PLAN
→ SIMULATE
→ AUTHORIZE
→ EXECUTE
→ VERIFY
→ PRESENT
→ LEARN
```

- `RETRIEVE` 的 memory 必须经过 user/authorization/purpose/validity/current-instruction Gate。
- `SIMULATE` 在昂贵、生成式或不可逆操作前固定 planned operations、estimated cost、authorized regions、preserve constraints 和 required verifiers。
- `AUTHORIZE` 检查用户意图、feature locks、identity constraints、成本和政策；未通过不得执行。
- `LEARN` 只接纳可信的 visual/behavioral/explicit user evidence；Agent 自产结果和未保存候选没有长期权威。

未来必须通过 benchmark 比较 Project Mirror-owned Responses orchestration 与 OpenAI Agents SDK adapter；winner 由证据和 ADR 决定，SDK 不得渗入领域状态。

## Tool Effect Contract

任何能修改图片的 Tool 必须声明一个 versioned contract：

- `ToolInputSchema`、`ToolOutputSchema`；
- `TargetRegion`；
- `AllowedEffects`、`ForbiddenEffects`；
- `Preconditions`、`Postconditions`；
- `CostEstimate`、`LatencyBudget`；
- `Idempotency`、`RollbackPolicy`；
- `VerificationPolicy`、`EvidencePolicy`；
- `ProviderProvenance`。

工具调用成功只证明 transport/runtime 完成，不证明视觉效果正确。例如 `adjust_face_geometry(jaw_width=-0.03)` 不得静默改变 eye/nose geometry、skin、hair 或 background。实际效果必须落在授权效果集合内，非目标变化必须落在 versioned tolerance 内。

## EffectVerifier

统一 `EffectVerifier` 至少研究：

- target-effect correctness；
- non-target/landmark/pose/expression drift；
- region leakage；
- identity、geometry 与 skin-texture preservation；
- artifact detection；
- feature-lock violation。

Verifier 输出固定为 `PASS | FAIL | HUMAN_REVIEW`，并绑定 verifier、policy、measurement、threshold、source/result checksum、reason code 与 uncertainty。生成式结果在通过 Verifier 前不得成为 accepted `ImageVersion`；人工复核只能追加证据，不能删除自动失败。

## Hybrid editor ordering

默认执行偏好为：

```text
DETERMINISTIC
→ LIGHTWEIGHT LOCAL MODEL
→ FULL GENERATIVE EDIT
```

crop、exposure、color、基础 skin、简单 mask/warp 等不得无条件交给 full generative model。Identity-Preserving Makeup Transfer 与 Deterministic、Geometry、Generative Editor 和 Agent Tool Layer 并列，并受同一 Tool Effect Contract、feature lock 和 verification 约束。

完整评估进入 `MirrorToolBench`、`MirrorRetouchBench` 与 `MirrorMakeupBench`；指标、ablation 和生产选择见 `docs/ai/MIRROR_BENCH.md`。

`DEPENDENCIES_ADDED: NONE`

`MODEL_ARTIFACTS_ADDED: NONE`
