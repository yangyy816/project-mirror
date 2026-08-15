# 腾讯云部署蓝图

## Beta 拓扑

- DNS/证书 → WAF/CLB → 无状态 Web/API 容器。
- API/Worker 使用私网访问 RDS PostgreSQL、Redis 和私有 COS。
- Worker 分独立进程和最小权限 CAM 角色；模型、短信、COS 使用不同凭据。
- 日志服务只收结构化脱敏日志；审计日志独立保留并限制查询权限。

小规模 Beta 使用 CVM 容器部署以控制复杂度；镜像、配置、健康检查和无状态边界保持 TKE 兼容。数据库、Redis 和对象存储不放在同一 CVM。

## 发布流程

CI 测试 → 构建不可变镜像 → 漏洞扫描 → 测试环境迁移 → smoke test → 人工批准 → 生产备份 → expand-compatible migration → 滚动发布 → readiness/指标验证 → 清理旧版本。失败时回滚应用；破坏性 schema 变更拆分多个版本。

## 可观测性

统一 request_id、job_id、model_run_id。监控 API/Worker 错误率、延迟、队列深度、数据库连接、COS 签名失败、Provider 失败/成本、上传拒绝、短信滥用、授权撤回和删除任务 SLA。

## 外部发布前

完成域名与备案、TLS、WAF、限流、备份恢复、RPO/RTO、密钥轮换、供应商条款、隐私文本、应急预案和真实用户支持流程。当前 Compose 只供开发，不是生产编排。
