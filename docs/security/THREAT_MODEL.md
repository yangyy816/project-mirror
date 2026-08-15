# 威胁模型

## 资产

最高敏感：人脸照片、landmark、几何测量、Reference Set、手机号关联、授权证据和签名 URL。高完整性：Profile 历史、Preference Event、额度 Ledger、Payment Event、审计日志和 Provider 运行记录。

## 主要威胁与控制

- 未授权横向访问：对象 key 不可猜测、服务端归属校验、短时签名 URL、私有桶、访问审计。
- 恶意上传：不接受客户端文件名/扩展名作为信任输入；重新验证 MIME/magic、大小/像素/单帧/畸形与解压炸弹，并通过 canonical 解码重编码、metadata 清理和频率限制隔离 payload。通用 malware scanner 仅是未来 production defense-in-depth Gate，P1-M4 不伪造已执行病毒扫描。
- 上传控制绕过：只有 active + exact purpose grant 可创建 owner-bound intent；key 由服务端生成，短时签名只允许精确 PUT 和声明约束。complete 只形成 quarantine `uploaded_unverified`，不能绕过 M4 晋升。
- 摄入绕过与 decoder 攻击：只有 owner-bound authoritative Job 可读取 quarantine；实际 magic/format/MIME、单帧、raw byte、边长、像素和解压炸弹均重新验证。raw container 永不 server-side copy 为 Asset；只晋升经过 EXIF orientation、metadata 清除、canonical 重编码和二次解码验证的输出。
- 异步双写与崩溃：PostgreSQL Job 是权威，Celery 采用 at-least-once。固定 sanitized key、create-if-absent、同 digest 验证、行锁、唯一 final evidence、stale lease recovery 和幂等 orphan/quarantine cleanup 防止重复 Asset 或半晋升。
- 撤回竞态与迟到上传：withdrawal 立即禁止新签名并 tombstone 未晋升 intents；已签 URL 仅在短 TTL 内残余有效，迟到对象不可处理且必须删除。complete/cancel/withdraw 使用行锁和 event evidence。
- 路径穿越与 SSRF：存储 key 严格语法；Provider 不接受用户给出的任意 URL。
- 验证码滥用：手机号哈希索引、频率/设备/IP 限制、短有效期、尝试次数、一次消费、日志脱敏。
- 账户枚举、邀请码滥用与会话劫持：新用户仅在有效邀请码验证后可取得 challenge，挑战阶段不消费邀请码；响应不得暴露账户或邀请码存在性。access token 短时有效，Web refresh token 仅在 HttpOnly/Secure/SameSite=Lax Cookie 中传输，刷新与 Cookie 会话撤销执行 CSRF/Origin 校验；refresh token 重用撤销整个 session family。
- 年龄凭证过度收集或供应商泄露：只通过 `AgeAssuranceProvider` 获取最小 18+ 结论与版本化不可逆引用，不保存证件、姓名、生日、精确年龄、凭证或原始响应。真实 Provider、法律审查、数据驻留和删除条款未验证前 production 注册必须关闭。
- Prompt 注入：图片/文本均视为不可信数据；Agent 只能调用白名单 Tool，参数由 schema 和领域服务校验。
- 重放与重复扣费：Idempotency-Key、唯一约束、不可变 Ledger、Webhook 签名与事件去重。
- 供应商泄露：数据最小化、用途隔离、禁止公共训练条款、区域/跨境审核、可替换 Adapter。
- 审美同质化/隐藏目标：所有 target 相对 SelfState，人口先验不得给出期望几何；持续执行 no-response convergence 与 cross-user target diversity Gate。
- 敏感路由：routing schema 不含种族、民族、国籍等分类，只允许连续必要几何、可靠性、覆盖和不确定性。
- 内部滥用：最小权限、分权审批、后台访问审计、break-glass 告警和定期复核。
- 日志泄露：字段白名单、手机号/Token/URL/Prompt/图片内容禁止记录。
- 本地存储逃逸：Local ingress 仅非生产、write-only、tokenized；解析后的路径必须在固定 root 内，拒绝路径/软链接逃逸、oversize、MIME/checksum 不一致和 token replay。生产拒绝 Local。
- Decoder 供应链：图片解析库是高风险 runtime dependency，必须锁定精确版本、许可证、wheel feature 和漏洞证据；不得由 Worker 调用 shell、ImageMagick CLI、任意动态插件或网络 decoder。原始异常和 metadata 不得进入日志/错误。

## 上线安全门

按 OWASP ASVS Level 2 基线完成文件上传、认证、访问控制、会话、密码学、日志和 API 测试；完成渗透测试、依赖扫描、Secret 扫描、备份恢复和删除演练。
