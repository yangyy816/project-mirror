# Model and Dataset License Registry

## Reading this registry

本表分别记录代码、模型/权重和数据集许可。`UNKNOWN` 表示尚未从权威 upstream 完成复核，不表示许可；`PRODUCTION_BLOCKED` 表示当前完整依赖链不得进入商业生产。法律结论只能由授权法律审查给出。

本 registry 同时登记研究线索和已执行的隔离 PoC；private acquisition 不等于仓库 artifact、项目依赖或生产批准。

外部研究主张与许可事实分开记录。重要候选必须包含 `SOURCE`、`SOURCE_TYPE`、
`ACCESSED_AT`、`CLAIM`、`CLAIM_STATUS`、`REPRODUCED`、`PROJECT_MIRROR_EVIDENCE`、
`LICENSE_EVIDENCE` 和 `CONFIDENCE`。允许的 claim status 为 `UPSTREAM_CLAIM`、
`INDEPENDENTLY_VERIFIED`、`PROJECT_MIRROR_REPRODUCED`、`INFERENCE` 和 `UNVERIFIED`。
“可研究”不表示“许可证允许”或“Project Mirror 已复现”。

| Candidate                                    | Code license                                                   | Model / weight license                        | Training / evaluation data           | Research status                       | Production status                           | Required next evidence                                                                             |
| -------------------------------------------- | -------------------------------------------------------------- | --------------------------------------------- | ------------------------------------ | ------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| MediaPipe source code                        | Apache-2.0 verified at tag `v0.10.35` / `f8ef212d...`          | N/A                                           | N/A                                  | LICENSE_REVIEW_REQUIRED               | PRODUCTION_BLOCKED                          | 完成逐文件/包内 notices、传递依赖与发行义务审计                                                    |
| MediaPipe source-built Face Landmarker C ABI | Apache-2.0 source；Linux reproducible artifact evidence        | N/A until separate bundle admission           | N/A                                  | STAGE_B LINUX REPRODUCIBLE            | DISTRIBUTION / PRODUCTION BLOCKED           | 解决 OouraFFT binary redistribution、剩余漏洞处置、Windows build/runtime 和完整 notice closure     |
| MediaPipe package/runtime `0.10.35`          | PyPI top-level Apache-2.0；private wheel/native audit evidence | N/A                                           | N/A                                  | POC_FAIL — WINDOWS CLEARCUT TELEMETRY | PRODUCTION_BLOCKED                          | exact candidate rejected；new build/version requires fresh change control and zero-telemetry proof |
| MediaPipe Face Landmarker artifact           | N/A                                                            | 三个官方 component model card 均标 Apache-2.0 | 仅有官方高层来源描述，逐项权利未证明 | PRIVATE POC ARTIFACT / NOT ADOPTED    | PRODUCTION_BLOCKED                          | bundle SHA-256 recorded；data rights/commercial redistribution remain unresolved                   |
| MediaPipe model/data distribution terms      | N/A                                                            | UNKNOWN                                       | UNKNOWN                              | LICENSE_REVIEW_REQUIRED               | PRODUCTION_BLOCKED                          | 核验下载、再分发、留存、地域、遥测、数据来源和 usage terms；代码许可不得替代此结论                 |
| 3DDFA_V2                                     | UNKNOWN                                                        | UNKNOWN                                       | UNKNOWN                              | APPROVED FOR RESEARCH REVIEW          | PRODUCTION_BLOCKED                          | 仓库、权重、训练数据与传递模型逐项核验                                                             |
| InsightFace pretrained ecosystem             | 与权重分离，未核验                                             | RESTRICTIONS / REVIEW REQUIRED                | UNKNOWN                              | 条款允许时仅隔离研究                  | PRODUCTION_BLOCKED                          | 不得从顶层代码许可推导模型/数据商业权利                                                            |
| CelebAMask-HQ-dependent face parsing         | 各实现不同                                                     | UNKNOWN                                       | RESTRICTED / UNVERIFIED              | 条款允许时仅架构研究                  | PRODUCTION_BLOCKED                          | 为每个 parsing stack 追溯预训练权重和训练数据；优先商业许可或第一方合成替代                        |
| Stable-Makeup family                         | UNKNOWN                                                        | UNKNOWN                                       | UNKNOWN                              | HIGH; APPROVED FOR RESEARCH REVIEW    | REQUIRES FULL DEPENDENCY LICENSE REVIEW     | repository → foundation model → weights → data → runtime → auxiliary parsing/landmark 全链复核     |
| MagicMakeup family                           | UNKNOWN                                                        | UNKNOWN                                       | UNKNOWN                              | RESEARCH REVIEW CANDIDATE             | PRODUCTION_BLOCKED                          | 锁定 exact upstream 后逐项核验代码、foundation model、weights、data、runtime 与辅助模型            |
| FLUX-Makeup family                           | 顶层代码许可不足以定论                                         | 报告依赖 `FLUX.1-Kontext-dev`，待权威复核     | UNKNOWN                              | HIGH; APPROVED FOR RESEARCH REVIEW    | PRODUCTION_BLOCKED                          | 核验当前 foundation-model 商业限制和完整依赖链；不得仅凭仓库许可采用                               |
| FLUX.1 Kontext-dev                           | N/A or runtime-specific                                        | USER-REPORTED RESTRICTED; NOT VERIFIED        | UNKNOWN                              | ARCHITECTURE INSIGHT ONLY             | PRODUCTION_BLOCKED                          | 权威复核 non-commercial/biometric 条款、模型卡、数据和衍生使用；未经法律清除不得下载或处理真人     |
| P7 visual embedding candidate                | UNKNOWN until selected                                         | UNKNOWN                                       | UNKNOWN                              | DEFERRED RESEARCH                     | PRODUCTION_BLOCKED                          | facet benchmark、biometric minimization、license/data/privacy/deletion Gate                        |
| Future image-generation/edit Provider        | N/A or provider SDK-specific                                   | Provider/model terms UNKNOWN                  | Provider training/data terms UNKNOWN | CANDIDATE                             | PRODUCTION_BLOCKED                          | 地域、保留、公共训练、删除、分包商、输出权利、成本和质量 benchmark                                 |
| Codex native image-generation entitlement    | N/A；非仓库 runtime dependency                                 | Exact model/version not exposed               | Service-side data facts not exposed  | OWNER-APPROVED P2 OFFLINE SOURCE      | NOT A RUNTIME PROVIDER / PRODUCTION_BLOCKED | 只记录 `PROVENANCE_ONLY` 已知事实；生产仍需独立国内 Provider、条款、Adapter 与 benchmark Gate      |

## Makeup-transfer dependency chain

每个候选必须按以下链逐项审查：Application code → research repository → foundation model → model weights → training/fine-tuning data → inference runtime → auxiliary models → face parsing model → landmark model → licenses。任一环节阻断即阻断完整生产路径。

Stable-Makeup 是高优先级研究参考，但生产采用需要完整依赖许可证审查。FLUX-Makeup 具有很高的算法与评估研究价值；在其被报告的受限 foundation-model 依赖得到独立商业许可前，直接商业部署保持 `PRODUCTION_BLOCKED`。受限实现提供的研究洞见可以在法律允许的范围内指导基于商业许可模型、合规 hosted API 或第一方模型的独立实现，但不能复制受限权重或规避许可。

## Artifact inventory

`EXPECTED_MODEL_ARTIFACTS_ADDED: NONE`

ADR-026 和 P2-M2-V01 不把 Codex entitlement 或其输出登记为仓库模型 artifact。八个 V01 synthetic
raw binaries 保存在 ignored private storage，Git 中只保留不含 Prompt、路径、object key 或图片 bytes
的 checksum-bound redacted manifest。该 owner research approval 不能推导 exact model/data license
或 production hosted-service approval。

任何当前 active milestone 都不得因为本 registry 安装 MediaPipe、OpenCV、imagededup 或未来
候选，也不得添加 `.pt`、`.pth`、`.onnx`、`.ckpt`、`.safetensors`、`.bin`、`.gguf`、
`.mlmodel`、`.tflite`、`.task`、模型 archive 或 cache。Gate 必须同时比较 tracked 和新
untracked artifact manifest，并记录模型下载命令；发现基线已有 artifact 时只报告并核验
provenance，不得自动删除。

P2-M1 的组件级 upstream 与依赖证据见 `docs/security/P2_SUPPLY_CHAIN_DECISIONS.md`；本表仍是模型、权重和数据批准状态的权威。

后续新增条目必须包含 artifact identifier、version、checksum、source、storage location、purpose、approval、security review、license evidence、dataset provenance 和 reproduction notes。

未来 AI-BOM 必须与本 registry 和 package SBOM 可交叉核验，但不得把尚未批准的候选、模型或权重写入 production manifest。当前新增条目仅记录用户批准的研究/阻断方向；未进行实时 upstream 法律核验。

## Research evidence status

2026-08-16 用户提供的研究报告是二级来源。本次没有实时刷新上游条款或复现实验，因此
MediaPipe/3DDFA、Stable-Makeup、MagicMakeup、FLUX-Makeup 和 future visual embedding 的能力主张
保持 `UPSTREAM_CLAIM` 或 `UNVERIFIED`，`REPRODUCED: NO`，
`PROJECT_MIRROR_EVIDENCE: NONE`。现有 `PRODUCTION_BLOCKED` 和
`REQUIRES FULL DEPENDENCY LICENSE REVIEW` 结论不放宽。

MediaPipe release metadata 的独立核验只证明当时的 upstream release/version observation，不证明
Face Landmarker artifact、模型数据、商业用途或 Project Mirror measurement reliability。FLUX-Makeup
及其被报告的 foundation-model 限制在权威 dependency-chain 与法律复核前继续
`PRODUCTION_BLOCKED`。

2026-08-17 T06 进一步核验三份官方 component model cards，均明确标注 Apache-2.0；其 PDF
SHA-256 分别为 `cd335c06fc0de7807cd815a0777a697932598bcdb28fa98adaaabf847485f758`、
`c8e9cf60a39998f4b341740623917590e050d1c97004e2de4568d84e026445ae` 与
`c6add060f4ebfb37b2690136b6c711c7e5fcb7038baa2649ae3338b83979565a`。GCS metadata 将
Face Landmarker bundle 固定到 generation `1683136941468629`。授权后的 private acquisition 得到
bundle SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`。Windows CPython 3.13
inference 在出站阻断下仍尝试 Google Clearcut telemetry，故 exact `0.10.35` runtime PoC 为
`FAIL`；Linux `--network none` 的单次成功不改变该结论。未进入 calibration/holdout，且
`MODEL_ARTIFACTS_ADDED: NONE`、`PROJECT_DEPENDENCIES_ADDED: NONE`。

## Real-person reference rights boundary

该 registry 不把 source-image rights 混入 model license。未来任何 restricted reference study 必须在
独立 rights evidence 中记录 copyright/license、adult model release、portrait/privacy permission、AI
processing、derivative/commercial use、storage/retention、territory、redistribution、revocation、reviewer
与 likeness/legal status。缺失项使完整用途保持 `REQUIRES_LEGAL_REVIEW` 或
`PRODUCTION_BLOCKED`；当前 `REAL_PERSON_IMAGES_ADDED: NONE`。
