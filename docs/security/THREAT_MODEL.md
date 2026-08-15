# 威胁模型

## 资产

最高敏感：人脸照片、landmark、几何测量、Reference Set、手机号关联、授权证据和签名 URL。高完整性：Profile 历史、Preference Event、额度 Ledger、Payment Event、审计日志和 Provider 运行记录。

## 主要威胁与控制

- 未授权横向访问：对象 key 不可猜测、服务端归属校验、短时签名 URL、私有桶、访问审计。
- 恶意上传：扩展/MIME/magic bytes、大小/像素、解码重编码、EXIF 清理、病毒/畸形检测和频率限制。
- 路径穿越与 SSRF：存储 key 严格语法；Provider 不接受用户给出的任意 URL。
- 验证码滥用：手机号哈希索引、频率/设备/IP 限制、短有效期、尝试次数、一次消费、日志脱敏。
- Prompt 注入：图片/文本均视为不可信数据；Agent 只能调用白名单 Tool，参数由 schema 和领域服务校验。
- 重放与重复扣费：Idempotency-Key、唯一约束、不可变 Ledger、Webhook 签名与事件去重。
- 供应商泄露：数据最小化、用途隔离、禁止公共训练条款、区域/跨境审核、可替换 Adapter。
- 审美同质化/隐藏目标：所有 target 相对 SelfState，人口先验不得给出期望几何；持续执行 no-response convergence 与 cross-user target diversity Gate。
- 敏感路由：routing schema 不含种族、民族、国籍等分类，只允许连续必要几何、可靠性、覆盖和不确定性。
- 内部滥用：最小权限、分权审批、后台访问审计、break-glass 告警和定期复核。
- 日志泄露：字段白名单、手机号/Token/URL/Prompt/图片内容禁止记录。

## 上线安全门

按 OWASP ASVS Level 2 基线完成文件上传、认证、访问控制、会话、密码学、日志和 API 测试；完成渗透测试、依赖扫描、Secret 扫描、备份恢复和删除演练。
