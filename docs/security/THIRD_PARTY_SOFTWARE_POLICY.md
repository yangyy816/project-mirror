# Third-Party Software and AI Supply-Chain Policy

## Adoption gate

重大第三方组件进入生产依赖前，必须从权威上游验证并保存证据：repository license、model license、model card、dataset license、商业/SaaS/再分发条款、归属/NOTICE、隐私与数据传输、遥测、已知漏洞、维护状态和全部传递依赖。任何重要条款含糊时，状态只能是 `REQUIRES_LEGAL_REVIEW` 或 `PRODUCTION_BLOCKED`。

代码许可证、模型许可证、权重许可证和训练数据许可证是独立结论。顶层仓库采用 permissive license 不能证明其预训练权重、训练数据或完整推理栈可用于商业 SaaS。

## Architecture and privacy controls

- 优先选择商业许可清晰、用途单一、维护健康、可固定版本、可复现、无隐藏网络/强制遥测并能在 Adapter 后替换的组件。
- 拒绝会接管领域状态、静默上传图片、捆绑来源不明权重、依赖非商业数据、无法禁用或无法替换的候选。
- 外部能力必须服从 Provider Adapter；第三方 SDK、Canvas 或 Agent framework 不能成为 Project Mirror 领域模型或状态权威。
- 真实用户图片不得进入研究仓库、公开 benchmark 或第三方调用，除非对应 Phase 的 Consent、法律、隐私、安全、数据地域和 Provider Gate 全部通过。
- 研究实现与商业实现必须分离。受限模型可在条款允许的隔离环境中提供算法研究证据，但不得把受限权重、代码路径或衍生镜像带入生产。

## Model artifact and dataset controls

任何 `.pth`、`.pt`、`.onnx`、`.ckpt`、`.safetensors` 或等价模型资产都必须登记 identifier、upstream、version、checksum、license、purpose、approval、storage、security review 与 reproduction notes；大型权重默认不进入 Git。

所有训练、微调、benchmark、评估、问卷生成和回归数据集必须登记 source、license、permitted/commercial use、redistribution、privacy、real/synthetic classification 与 retention。生产问卷仍只允许可追溯成年合成人物，禁止以抓取真人脸数据作为捷径。

## SBOM and change control

传统 package SBOM 必须覆盖进入生产的代码依赖；AI 供应链还必须登记模型校验和、权重 provenance、数据 provenance、运行时、辅助模型和外部 Provider 版本。单个受阻依赖会阻断完整生产路径。

Terra 不得自行安装重大依赖、下载权重、接受条款、采用 hosted service 或重构架构。候选从 `RESEARCH_ONLY` 到 `CANDIDATE` 再到 `APPROVED` 的每次跃迁都需要 Principal；Vision、Canvas、Agent、生成模型、分割模型、模型 runtime、支付和认证框架等高影响项还需 ADR。

本政策不改变当前 P1-M1：不新增依赖、模型资产或 Gate。
