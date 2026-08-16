# Model and Dataset License Registry

## Reading this registry

本表分别记录代码、模型/权重和数据集许可。`UNKNOWN` 表示尚未从权威 upstream 完成复核，不表示许可；`PRODUCTION_BLOCKED` 表示当前完整依赖链不得进入商业生产。法律结论只能由授权法律审查给出。

本轮仅登记用户提供的研究线索与治理默认值，没有下载代码、模型、权重或数据，也没有完成权威 upstream 许可证核验。

| Candidate                               | Code license                                          | Model / weight license                    | Training / evaluation data           | Research status                    | Production status                       | Required next evidence                                                                         |
| --------------------------------------- | ----------------------------------------------------- | ----------------------------------------- | ------------------------------------ | ---------------------------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------- |
| MediaPipe source code                   | Apache-2.0 upstream claim，待 exact tag notice review | N/A                                       | N/A                                  | LICENSE_REVIEW_REQUIRED            | PRODUCTION_BLOCKED                      | 锁定 source tag，核验 LICENSE/NOTICE、传递依赖与发行义务                                       |
| MediaPipe package/runtime               | UNKNOWN until exact package selected                  | N/A                                       | N/A                                  | LICENSE_REVIEW_REQUIRED            | PRODUCTION_BLOCKED                      | 锁定 Python/runtime distribution，核验 bundled native deps、wheel、SBOM 与平台条款             |
| MediaPipe Face Landmarker artifact      | N/A                                                   | UNKNOWN                                   | UNKNOWN                              | LICENSE_REVIEW_REQUIRED            | PRODUCTION_BLOCKED                      | 单独核验 artifact identifier、source、checksum、许可、训练/评估数据与商业用途                  |
| MediaPipe model/data distribution terms | N/A                                                   | UNKNOWN                                   | UNKNOWN                              | LICENSE_REVIEW_REQUIRED            | PRODUCTION_BLOCKED                      | 核验下载、再分发、留存、地域、遥测、数据来源和 usage terms；代码许可不得替代此结论             |
| 3DDFA_V2                                | UNKNOWN                                               | UNKNOWN                                   | UNKNOWN                              | APPROVED FOR RESEARCH REVIEW       | PRODUCTION_BLOCKED                      | 仓库、权重、训练数据与传递模型逐项核验                                                         |
| InsightFace pretrained ecosystem        | 与权重分离，未核验                                    | RESTRICTIONS / REVIEW REQUIRED            | UNKNOWN                              | 条款允许时仅隔离研究               | PRODUCTION_BLOCKED                      | 不得从顶层代码许可推导模型/数据商业权利                                                        |
| CelebAMask-HQ-dependent face parsing    | 各实现不同                                            | UNKNOWN                                   | RESTRICTED / UNVERIFIED              | 条款允许时仅架构研究               | PRODUCTION_BLOCKED                      | 为每个 parsing stack 追溯预训练权重和训练数据；优先商业许可或第一方合成替代                    |
| Stable-Makeup family                    | UNKNOWN                                               | UNKNOWN                                   | UNKNOWN                              | HIGH; APPROVED FOR RESEARCH REVIEW | REQUIRES FULL DEPENDENCY LICENSE REVIEW | repository → foundation model → weights → data → runtime → auxiliary parsing/landmark 全链复核 |
| MagicMakeup family                      | UNKNOWN                                               | UNKNOWN                                   | UNKNOWN                              | RESEARCH REVIEW CANDIDATE          | PRODUCTION_BLOCKED                      | 锁定 exact upstream 后逐项核验代码、foundation model、weights、data、runtime 与辅助模型        |
| FLUX-Makeup family                      | 顶层代码许可不足以定论                                | 报告依赖 `FLUX.1-Kontext-dev`，待权威复核 | UNKNOWN                              | HIGH; APPROVED FOR RESEARCH REVIEW | PRODUCTION_BLOCKED                      | 核验当前 foundation-model 商业限制和完整依赖链；不得仅凭仓库许可采用                           |
| FLUX.1 Kontext-dev                      | N/A or runtime-specific                               | USER-REPORTED RESTRICTED; NOT VERIFIED    | UNKNOWN                              | ARCHITECTURE INSIGHT ONLY          | PRODUCTION_BLOCKED                      | 权威复核 non-commercial/biometric 条款、模型卡、数据和衍生使用；未经法律清除不得下载或处理真人 |
| P7 visual embedding candidate           | UNKNOWN until selected                                | UNKNOWN                                   | UNKNOWN                              | DEFERRED RESEARCH                  | PRODUCTION_BLOCKED                      | facet benchmark、biometric minimization、license/data/privacy/deletion Gate                    |
| Future image-generation/edit Provider   | N/A or provider SDK-specific                          | Provider/model terms UNKNOWN              | Provider training/data terms UNKNOWN | CANDIDATE                          | PRODUCTION_BLOCKED                      | 地域、保留、公共训练、删除、分包商、输出权利、成本和质量 benchmark                             |

## Makeup-transfer dependency chain

每个候选必须按以下链逐项审查：Application code → research repository → foundation model → model weights → training/fine-tuning data → inference runtime → auxiliary models → face parsing model → landmark model → licenses。任一环节阻断即阻断完整生产路径。

Stable-Makeup 是高优先级研究参考，但生产采用需要完整依赖许可证审查。FLUX-Makeup 具有很高的算法与评估研究价值；在其被报告的受限 foundation-model 依赖得到独立商业许可前，直接商业部署保持 `PRODUCTION_BLOCKED`。受限实现提供的研究洞见可以在法律允许的范围内指导基于商业许可模型、合规 hosted API 或第一方模型的独立实现，但不能复制受限权重或规避许可。

## Artifact inventory

`MODEL_ARTIFACTS_ADDED: NONE`

P2-M1 不得安装 MediaPipe、OpenCV 或 imagededup，也不得添加 `.pt`、`.pth`、`.onnx`、`.ckpt`、`.safetensors`、`.tflite`、`.task`、模型 archive 或 cache。发现基线已有 artifact 时只报告并核验 provenance，不得自动删除。

P2-M1 的组件级 upstream 与依赖证据见 `docs/security/P2_SUPPLY_CHAIN_DECISIONS.md`；本表仍是模型、权重和数据批准状态的权威。

后续新增条目必须包含 artifact identifier、version、checksum、source、storage location、purpose、approval、security review、license evidence、dataset provenance 和 reproduction notes。

未来 AI-BOM 必须与本 registry 和 package SBOM 可交叉核验，但不得把尚未批准的候选、模型或权重写入 production manifest。当前新增条目仅记录用户批准的研究/阻断方向；未进行实时 upstream 法律核验。

## Real-person reference rights boundary

该 registry 不把 source-image rights 混入 model license。未来任何 restricted reference study 必须在
独立 rights evidence 中记录 copyright/license、adult model release、portrait/privacy permission、AI
processing、derivative/commercial use、storage/retention、territory、redistribution、revocation、reviewer
与 likeness/legal status。缺失项使完整用途保持 `REQUIRES_LEGAL_REVIEW` 或
`PRODUCTION_BLOCKED`；当前 `REAL_PERSON_IMAGES_ADDED: NONE`。
