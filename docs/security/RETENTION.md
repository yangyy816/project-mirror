# 数据保留、导出与删除

## 原则

目的限制、数据最小化、默认不训练公共模型、用户可查看/导出/撤回授权/清除个人审美记忆/删除账户。正式期限必须在法律审核后由版本化政策配置，不在代码中散落常量。

## 生命周期状态

`active → deletion_requested → quarantined → physically_deleted`。删除请求立即阻止新处理和新签名 URL；后台任务按资产依赖顺序清理原图、派生图、Reference Set 和可识别分析数据，并写入不含敏感内容的完成证据。

Baseline 删除、Consent 撤回、账户删除、Baseline 替换、分析失效或政策版本变化必须传播到 BaselineFaceModel/Measurement、SelfState、MorphologyDescriptor、QuestionRoute/Instance、DesiredDelta、self-transfer artifacts 和 Profile evidence。Audit 只有在法律/安全理由成立时去标识保留，不能借审计名义保留不必要的 facial-derived values。

尚未晋升的 quarantine object 使用短 TTL。UploadIntent 过期、取消、用途授权撤回或账户冻结后立即失去处理资格并进入幂等清理；即使旧签名 URL 在 TTL 内收到迟到上传，也只能删除，不能恢复 intent 或晋升。Intent/Event 可按安全审计期限保留不含 URL、token、object bytes 的最小证据。

## 导出

导出包仅包含当前用户数据，使用一次性短时下载链接，生成与下载均审计。禁止导出内部风控信号、其他用户数据、供应商密钥或系统 Prompt。

## 例外

账务、反欺诈和安全日志如依法需保留，应去标识化、隔离权限并在期限结束后销毁。撤回人脸处理授权后，除执行删除所必需的流程外不得继续分析。
