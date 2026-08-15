# PRD：Project Mirror

## 产品定义

Project Mirror 是一个拥有长期个人审美记忆的 AI Photo Editing Agent。它学习的不是“用户通常觉得什么脸好看”，而是“以用户自己的当前结构为参照，用户希望自己如何改变”。

核心计算原则是 `TargetState = IdentityAnchor + DesiredDelta`，并受身份保持、显式锁、测量/偏好置信度、编辑强度、安全边界和场景覆盖限制。不存在全局理想脸或人口平均目标。

它不是颜值评分、换脸、真人搜索、统一审美、美容医疗建议或公共图片训练平台。

## 首发用户与目标

- 中国大陆、年满 18 周岁、持邀请码的早期私测用户。
- 核心任务：上传一张自拍后，得到一张保持身份、符合本人偏好且修改过程可解释的结果图。
- Beta 目标：验证偏好测量有效性、身份保持、结果接受率、单次编辑成本和隐私操作闭环。

## 用户生命周期

邀请码与手机号验证 → 18+ 确认 → 版本化授权 → Baseline 上传/质量检查 → BaselineFaceModel 测量证据 → SelfState → SelfState-conditioned 合成问卷 → DesiredDeltaProfile + StyleProfile → self-transfer validation → 正面/3⁄4/侧面 Aesthetic Reference → 用户审批 Profile V1 → 日常非破坏式修图 → 接受/拒绝/回调 → 新 Profile 版本。

只提供正脸时，侧面必须标记为“审美参考侧脸”，不得宣称是真实侧脸预测。

## Phase 0 + 骨架范围

包含：工程规则、文档、self-conditioned 领域模型、迁移、概念契约、纯数值合成 fixture、评估规格、健康与版本 API、版本化占位路由、Provider 协议与 Fake、中文状态页、Worker、契约生成、测试、CI 和部署蓝图。

不包含：真实注册、图片上传、真人分析、正式题库、生产路由、真实 self-transfer、模型调用、生成结果、支付、运营后台、公开部署。

## MVP 及非目标

后续 MVP 包含邀请注册、授权、单人自拍上传、自动选脸、初始问卷、Profile V1、单图编辑、版本对比、用户确认和行为事件。

首版不做未成年人、社区、视频、身体塑形、实时相机、跨账号人脸识别、复杂多人编辑、Android、公开作品广场或自训练大模型。

## 产品指标

- 问卷完成率、有效回答一致性、各维度 posterior confidence。
- Reference Set 审批轮数与最终接受率。
- 编辑结果接受/拒绝/手动回调率，身份保持 QA 通过率。
- 单次有效编辑延迟、成本、失败率与退款/额度补偿率。
- 删除、导出、撤回授权和安全事件 SLA。
