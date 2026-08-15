# Personal Information Protection Impact Assessment Baseline

**Gate：`LEGAL_REVIEW_REQUIRED`**
状态：Draft engineering template。Phase 0 不构成正式法律意见，审批前禁止将真实 Facial Data 处理标记为 production ready。

## 评估记录

| 项目                 | 待填写内容                                                                           | 当前状态              |
| -------------------- | ------------------------------------------------------------------------------------ | --------------------- |
| Processing purpose   | 具体功能、用户价值、是否可不用该数据实现                                             | REQUIRED              |
| Necessity            | 最小字段、最小精度、替代方案                                                         | REQUIRED              |
| Data category        | 原图、派生图、landmark、geometry、reference、日志                                    | HIGHLY SENSITIVE      |
| Processing operation | detection、landmark、editing、identity preservation、embedding、recognition 分别判断 | REQUIRED              |
| Sensitivity          | 对个人权益影响与误用风险                                                             | HIGH                  |
| Retention            | 每类数据期限、隔离期、物理删除 SLA                                                   | REQUIRED              |
| Access control       | 用户、后台、Worker、Provider、break-glass 权限                                       | REQUIRED              |
| Provider transfer    | 字段、用途、地域、保留、训练使用、分包商                                             | BLOCKED               |
| Data processor       | 控制者、受托处理者、子处理者与责任                                                   | REQUIRED              |
| Cross-border risk    | 是否跨境、依据、单独同意和替代方案                                                   | BLOCKED               |
| Deletion             | 对象、派生数据、缓存、备份、Provider 删除证据                                        | REQUIRED              |
| Withdrawal           | 撤回后的停止处理、重新授权与历史审计                                                 | REQUIRED              |
| Logging              | 字段白名单、脱敏、访问审计、保留期                                                   | REQUIRED              |
| Abuse                | 冒用、偷拍、未成年人、身份搜索、骚扰与绕过                                           | REQUIRED              |
| Security controls    | 加密、私有桶、签名 URL、隔离、限流、告警                                             | REQUIRED              |
| Residual risk        | 控制后剩余风险与接受人                                                               | REQUIRED              |
| Approval status      | 法务、安全、隐私、产品负责人签署与日期                                               | LEGAL_REVIEW_REQUIRED |

## 工程 Gate

启用真实数据前必须存在已批准评估版本，并把 policy version 写入 ConsentRecord 与 ModelRun/AIContentProvenance。Provider、处理目的、模型或地域实质变化时重新评估。CI/配置层必须保证 Gate 未解除时真实 AI、真人题库和公开注册保持关闭。
