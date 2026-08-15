# 数据保留、导出与删除

## 原则

目的限制、数据最小化、默认不训练公共模型、用户可查看/导出/撤回授权/清除个人审美记忆/删除账户。正式期限必须在法律审核后由版本化政策配置，不在代码中散落常量。

## 生命周期状态

`active → deletion_requested → quarantined → physically_deleted`。删除请求立即阻止新处理和新签名 URL；后台任务按资产依赖顺序清理原图、派生图、Reference Set 和可识别分析数据，并写入不含敏感内容的完成证据。

Baseline 删除、Consent 撤回、账户删除、Baseline 替换、分析失效或政策版本变化必须传播到 BaselineFaceModel/Measurement、SelfState、MorphologyDescriptor、QuestionRoute/Instance、DesiredDelta、self-transfer artifacts 和 Profile evidence。Audit 只有在法律/安全理由成立时去标识保留，不能借审计名义保留不必要的 facial-derived values。

尚未晋升的 quarantine object 使用短 TTL。UploadIntent 过期、取消、用途授权撤回或账户冻结后立即失去处理资格并进入幂等清理；即使旧签名 URL 在 TTL 内收到迟到上传，也只能删除，不能恢复 intent 或晋升。Intent/Event 可按安全审计期限保留不含 URL、token、object bytes 的最小证据。

新完成上传保存版本化 quarantine retention deadline；首个 operational target 为 1 小时且配置上限为 24 小时。成功晋升或 deterministic rejection 后立即请求删除 raw object；删除失败不得复制第二个 Asset，而由幂等 cleanup 重试。对象先写入但晋升事务未提交产生的 sanitized orphan 必须按 job/final evidence 对账删除。Original Asset 的保留与用户删除权在 P1-M5 建立，M4 不提供下载或恢复旁路。

## 导出

P1-M5 将删除请求与物理删除证据分离。请求一经接受即停止新签名和新处理；对象删除由 reference-only Worker 幂等执行，只有对象存储与 PostgreSQL propagation evidence 一致时才能报告完成。Original metadata 不为删除而改写。导出包使用版本化短期 retention deadline，并在到期后由相同的可重试证据链清理。

导出包仅包含当前用户数据，使用一次性短时下载链接，生成与下载均审计。禁止导出内部风控信号、其他用户数据、供应商密钥或系统 Prompt。

## 例外

账务、反欺诈和安全日志如依法需保留，应去标识化、隔离权限并在期限结束后销毁。撤回人脸处理授权后，除执行删除所必需的流程外不得继续分析。
