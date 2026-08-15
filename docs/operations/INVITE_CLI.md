# 邀请码管理 CLI

此工具仅供受控运维环境使用；不提供 HTTP 管理接口，不列出邀请码，也不能恢复既有明文邀请码。

仅允许从具名环境变量读取非生产 PostgreSQL URL，避免将凭据放在命令行或 shell history 中。当前里程碑会拒绝 production 执行。

```powershell
python -m mirror_api.scripts.manage_invites --database-env TEST_DATABASE_URL --environment test create --max-uses 1
python -m mirror_api.scripts.manage_invites --database-env TEST_DATABASE_URL --environment test disable --invite-id <invite-id>
python -m mirror_api.scripts.manage_invites --database-env TEST_DATABASE_URL --environment test audit --invite-id <invite-id>
```

`create` 仅在成功提交后于标准输出中一次性给出明文 code 和非秘密 invite ID。所有状态变更命令仅在成功提交后输出成功结果；数据库与审计记录不保存或显示 code 原文。
