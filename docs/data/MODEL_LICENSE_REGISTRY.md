# Model and Dataset License Registry

## Reading this registry

本表分别记录代码、模型/权重和数据集许可。`UNKNOWN` 表示尚未从权威 upstream 完成复核，不表示许可；`PRODUCTION_BLOCKED` 表示当前完整依赖链不得进入商业生产。法律结论只能由授权法律审查给出。

本轮仅登记用户提供的研究线索与治理默认值，没有下载代码、模型、权重或数据，也没有完成权威 upstream 许可证核验。

| Candidate                             | Code license                 | Model / weight license                    | Training / evaluation data           | Research status                    | Production status                       | Required next evidence                                                                         |
| ------------------------------------- | ---------------------------- | ----------------------------------------- | ------------------------------------ | ---------------------------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------- |
| MediaPipe Face Landmarker             | UNKNOWN                      | UNKNOWN                                   | UNKNOWN                              | CANDIDATE                          | REQUIRES_LEGAL_REVIEW                   | 在 P3 从权威来源核验全部 artifact、平台发行与商业条款                                          |
| 3DDFA_V2                              | UNKNOWN                      | UNKNOWN                                   | UNKNOWN                              | APPROVED FOR RESEARCH REVIEW       | PRODUCTION_BLOCKED                      | 仓库、权重、训练数据与传递模型逐项核验                                                         |
| InsightFace pretrained ecosystem      | 与权重分离，未核验           | RESTRICTIONS / REVIEW REQUIRED            | UNKNOWN                              | 条款允许时仅隔离研究               | PRODUCTION_BLOCKED                      | 不得从顶层代码许可推导模型/数据商业权利                                                        |
| CelebAMask-HQ-dependent face parsing  | 各实现不同                   | UNKNOWN                                   | RESTRICTED / UNVERIFIED              | 条款允许时仅架构研究               | PRODUCTION_BLOCKED                      | 为每个 parsing stack 追溯预训练权重和训练数据；优先商业许可或第一方合成替代                    |
| Stable-Makeup family                  | UNKNOWN                      | UNKNOWN                                   | UNKNOWN                              | HIGH; APPROVED FOR RESEARCH REVIEW | REQUIRES FULL DEPENDENCY LICENSE REVIEW | repository → foundation model → weights → data → runtime → auxiliary parsing/landmark 全链复核 |
| FLUX-Makeup family                    | 顶层代码许可不足以定论       | 报告依赖 `FLUX.1-Kontext-dev`，待权威复核 | UNKNOWN                              | HIGH; APPROVED FOR RESEARCH REVIEW | PRODUCTION_BLOCKED                      | 核验当前 foundation-model 商业限制和完整依赖链；不得仅凭仓库许可采用                           |
| Future image-generation/edit Provider | N/A or provider SDK-specific | Provider/model terms UNKNOWN              | Provider training/data terms UNKNOWN | CANDIDATE                          | PRODUCTION_BLOCKED                      | 地域、保留、公共训练、删除、分包商、输出权利、成本和质量 benchmark                             |

## Makeup-transfer dependency chain

每个候选必须按以下链逐项审查：Application code → research repository → foundation model → model weights → training/fine-tuning data → inference runtime → auxiliary models → face parsing model → landmark model → licenses。任一环节阻断即阻断完整生产路径。

Stable-Makeup 是高优先级研究参考，但生产采用需要完整依赖许可证审查。FLUX-Makeup 具有很高的算法与评估研究价值；在其被报告的受限 foundation-model 依赖得到独立商业许可前，直接商业部署保持 `PRODUCTION_BLOCKED`。受限实现提供的研究洞见可以在法律允许的范围内指导基于商业许可模型、合规 hosted API 或第一方模型的独立实现，但不能复制受限权重或规避许可。

## Artifact inventory

`MODEL_ARTIFACTS_ADDED: NONE`

后续新增条目必须包含 artifact identifier、version、checksum、source、storage location、purpose、approval、security review、license evidence、dataset provenance 和 reproduction notes。
