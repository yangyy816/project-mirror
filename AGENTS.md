# Project Mirror 工程规则

## 项目身份

- 项目：Project Mirror
- 当前阶段：Phase 2 — Synthetic Dataset Engine（COMMITTED）
- 当前 Milestone：P2-M5 — Variable Isolation, Duplicate and Diversity QA（EXECUTING）
- 首发：面向中国大陆的 18+ 邀请制 Beta
- 默认语言：产品 UI 与项目沟通使用简体中文；代码、命令、变量名使用英文
- 本文件适用于整个仓库；子目录可增加更严格的 `AGENTS.md`，不得放宽本文件约束

## 每次工作的强制顺序

1. 在修改任何文件前完整读取仓库根目录的 `AGENTS.md` 与 `MEMORY.md`。
2. 先检查工作树和相关实现，保留用户已有改动。
3. 重要架构决策先更新文档或 ADR，再修改实践。
4. 完成后运行与风险相称的测试、类型检查、构建和安全检查。
5. 将新确认的架构决策、踩坑、用户纠正和外部资源位置写入 `MEMORY.md`；凭据只记位置，不记值。

## 执行治理

- 状态统一使用 `PROVISIONAL → COMMITTED → EXECUTION_READY → EXECUTING → PASS → FROZEN`。Phase 0 是 `FROZEN`；未完成工作不得称为 `FROZEN`。
- Terra Agent 只能实现或把 Principal 已明确批准的架构编码为 ADR，不得自行创建新架构决策。遇到新决策时必须停止在决策边界并上报 Principal。
- 计划外实现缺陷使用最小 Repair Task，编号为 `P<phase>-M<milestone>-R<nn>`；不得用新增 `T09/T10` 代替。架构变化必须走 change control，不能包装成 Repair Task。
- Terra 的 PASS 只是证据。只有 Principal 审查实际 diff、验证输出、安全影响和集成结果后才能给出 `TASK_ACCEPTED`，并且只有 Principal 能决定 Milestone Gate。
- 模型路由使用 Sol High 做规划/架构/最终审查，Terra Medium 做默认 bounded implementation，`pm_terra_high_worker` / Terra High 只做契约已冻结但实现困难的仓库推理、多文件控制流、并发或事务任务，`pm_luna_worker` / Luna Medium 做规则明确的机械批处理，`pm_fast_worker` / GPT-5.3-Codex-Spark 做小、精确、原子、可逆且验证明确的即时 micro task；不确定时先选 Terra Medium，再按证据升级。
- Spark 任务必须明示 `OBJECTIVE / ALLOWED AREA / EXPECTED CHANGE / FORBIDDEN / VALIDATION`，不得自主决定架构、安全/隐私、认证、数据库/迁移、敏感人脸领域或产品 invariant；发现边界扩大时立即 `ESCALATION_REQUIRED`。Spark 未执行指定验证时只能报 `IMPLEMENTED_NOT_VERIFIED`。完整规则见 `docs/operations/MODEL_ROUTING_POLICY.md`。

## A. 不可违反的产品 Invariants

1. **Identity First**：默认优先保持用户可识别身份特征，除非用户明确提高修改强度。
2. **No Beauty Score**：禁止颜值打分、排名、百分位或统一审美标准，只比较用户当前特征与其自主表达的偏好。
3. **No Sensitive Inference**：不得从照片推断种族、民族、宗教、性取向、健康或政治属性。
4. **Synthetic Question Bank**：生产问卷人物必须是可追溯的成年合成人物，禁止抓取真人、明星或社交平台照片作为核心题库。
5. **Explainable Profile**：Aesthetic Profile 必须同时保存结构化偏好、置信度、证据和参考图，不能只有 embedding。
6. **Versioned Profile**：Profile 只能追加新版本，不得覆盖历史版本；用户应能关闭学习并回滚。
7. **User-Signal Learning Only**：只有接受、保存、拒绝、滑杆回调或明确反馈等用户行为能强化长期偏好；模型自产结果不是学习证据。
8. **Immutable Original**：原图永不修改；编辑必须通过 Operation Graph、ImageVersion 和 Render 形成非破坏式版本。
9. **Provider Adapters**：业务代码不得直接依赖具体 AI、短信、存储或支付 SDK，所有外部能力必须经过领域 Adapter。
10. **Production Fails Closed**：生产配置必须拒绝 Mock、Local、不安全 Secret、开发 CORS、Debug、公开存储和未通过 Gate 的处理能力。
11. **Sensitive Data Gate**：Facial Data 统一按高度敏感数据保护，但技术处理操作不得未经法律判断一概称为“人脸识别”；生产启用必须通过 `LEGAL_REVIEW_REQUIRED` Gate。
12. **Self-conditioned Desired Self**：编辑只优化“以用户当前 SelfState 为锚点的理想自我”，绝不以全局理想脸、人口平均脸或隐藏审美模板定义目标。
13. **Identity Reference Frame**：用户自己的当前身份与 SelfState 始终是几何参考坐标；相同 DesiredDelta 作用于不同用户时不得收敛到相同绝对几何。
14. **Evidence Precedence**：合成问卷证据是 provisional；有效且冲突的 self-transfer 证据必须优先，明确指令、手动纠正和显式锁又优先于推断证据。
15. **Population Prior Restriction**：人口先验只能用于不确定性、测量、安全边界和调度，永远不得生成用户期望几何；证据不足时应减小 delta 并提高不确定性。
16. **No Sensitive-trait Routing**：问卷路由只能依赖连续 SelfState 几何、可靠性、覆盖和不确定性，不得使用种族、民族、国籍或其他敏感特征分类。
17. **Anti-homogenization**：Target、EditPlan、Reference Set、Profile 学习和路由都必须防止跨用户向单一“标准脸”坍缩。

## 隐私与安全

- 人脸照片、landmark、几何测量和参考图统一视为高度敏感个人数据。
- 私测仅限明确确认 18+、持有效邀请码并完成版本化授权的用户。
- 对象存储必须私有；访问只能通过授权请求和短时签名 URL。
- 上传必须执行扩展名白名单、MIME 与 magic bytes 校验、大小和像素限制、解码重编码、EXIF 清理及畸形图片拒绝。
- 默认不使用用户图片训练公共模型；跨境处理、公开注册和真实收费必须通过独立合规验收后才能开启。
- 日志不得记录手机号明文、验证码、访问令牌、签名 URL、图片内容或供应商密钥。
- 所有创建型接口必须支持幂等；账务使用不可变 Ledger，禁止直接修改余额。
- 不得提交 `.env`、凭据、真实用户数据或真实人脸测试素材。

## B. 架构决策的执行规则

- 技术栈、数据库、Worker、云、账务和契约来源等决策必须记录为 `docs/adr/` 下的 Accepted ADR，并包含 Context、Decision、Alternatives、Consequences、Status。
- 实现必须服从 Accepted ADR；如需改变，先新增 superseding ADR，不直接改写历史理由。
- PostgreSQL-specific invariant 与 migration 只能由真实 PostgreSQL 验证；SQLite、内存数据库和 Mock DB 不能作为通过证据。
- Worker 的 Domain/Application 逻辑不得依赖 Celery；Celery 只是 Linux 生产 Task Adapter，Windows 使用 `LocalTaskRunner` 或开发专用 solo 方式。
- FastAPI/Pydantic → OpenAPI → generated TypeScript client 是单向契约链，禁止长期双写接口类型。
- 重大第三方组件必须经过 OSS 评估、完整依赖链许可证审查和 Principal 批准；代码许可证不得替代模型、权重与数据集许可证结论。
- Terra 发现候选组件时只能报告 `THIRD_PARTY_CANDIDATE_FOUND`，不得自行安装依赖、下载权重、接受条款或围绕候选重构架构。
- 模型与数据资产必须登记来源、版本、校验和、许可证、用途和批准状态；未获批准的权重不得进入 Git、CI 或生产镜像。

## C. Research Hypotheses 与 Operational Targets

- 统计模型、题目数量、最低覆盖率、landmark + deterministic warp 都是 `RESEARCH HYPOTHESIS`，必须放在研究规格中并允许实验替换。
- 合成身份数量、成本、延迟和覆盖目标是 `OPERATIONAL TARGET`，可随 QA 与实验结果调整。
- 研究假设和运营目标不得升级为本文件中的永久产品 Invariant。

## C.1 P2–P7 Benchmark Gate

- P2–P7 的高影响算法、Provider、Agent runtime、Tool、编辑与视觉记忆候选必须依次经过 Candidate、isolated PoC、MirrorBench、ablation、license/privacy/security/cost review、ADR 和 Principal approval；设计合理或 PoC 成功不等于 production approval。
- 每项 Bench 必须固定 baseline、dataset/fixture provenance、metrics、预注册 threshold、failure interpretation、artifact、reproducibility 和 model/provider version；不得看到 holdout 后放宽同一版本阈值以强迫 PASS。
- 第三方框架只能作为 Provider、Adapter、research baseline 或 reference implementation，不得成为 SelfState、DesiredDelta、StyleProfile、IdentityConstraints、AestheticProfile、EditPlan、Visual/Preference Evidence 的业务权威。
- P3–P7 仍为 PROVISIONAL；research backlog 不是 execution authorization。完整 family 与 backlog 见 `docs/ai/MIRROR_BENCH.md`。

## C.2 China-first Synthetic Coverage Boundary

- 首个 internal coverage pack 是 China-market-first、East-Asian-presenting、声明为成年且
  synthetic-only；该 presentation scope 不是 ancestry、nationality、ethnicity、race 或真实用户标签，
  也不代表人口平均脸或普遍审美标准。按 ADR-030，未来一般非性感 cohort 仅在整体视觉明确呈现为
  未满 16 岁，或包含儿童/学生未成年语境时 hard reject；round face、babyface、soft features 或
  youthful appearance 本身不得触发拒绝。性感、诱惑、亲密或性化 context 仍要求 unambiguous 18+。
- corpus coverage、question selection 与 future user compatibility 主要依赖连续 morphology、
  reliability、uncertainty 与 Local Morphological Neighborhood。不得创建敏感群体 classifier，不得
  从真实用户照片推断或路由 race/ethnicity/ancestry/nationality。
- 网络研究默认只提取人工复核的抽象 descriptors。抓取真人肖像、社交媒体/搜索结果 face source、
  celebrity/influencer imitation、one-to-one identity reproduction 和未经独立权利 Gate 的真人 reference
  一律禁止。完整决定见 ADR-024。

## C.3 Progressive Qualification

- 重要 dependency、model、weight、native runtime、research algorithm、Provider SDK、视觉/编辑引擎和 Agent
  runtime 候选必须按 ADR-043 声明 `QUALIFICATION_TIER`、`CURRENT_STATUS`、`APPROVED_SCOPE` 与
  `PROHIBITED_SCOPE`；禁止使用不带层级和范围的含糊 `approved`。
- 晋级链为 `CANDIDATE` → `RESEARCH_QUALIFIED` → `INTERNAL_ENGINE_CANDIDATE` →
  `APPROVED_FOR_INTERNAL_ENGINE` → `PRODUCTION_CANDIDATE` → `PRODUCTION_APPROVED`。Research 证据可复用，
  批准范围不能继承或跳级；`PRODUCTION_CANDIDATE` 仍必须由 Principal 明确记录
  `PRODUCTION_APPROVAL: GRANTED` 才能启用。
- 所有层级都必须保留 exact provenance、synthetic-only/no-real-user 边界、license/model/data 分离、bounded
  network/no hidden telemetry、Provider/Adapter、no credential、no unknown weight、no fake PASS 和 production
  fail-closed。当前 Milestone 已冻结的更严格 Gate 不得由后来的层级模型放宽。
- 完整 entry/exit/evidence 字段见 `docs/operations/DEPENDENCY_QUALIFICATION_TIERS.md`。P2-M3 既有证据为
  `LEGACY_STRICT_QUALIFICATION`；P2-M4 OpenCV 仅为 scope-specific
  `APPROVED_FOR_PRIVATE_SYNTHETIC_M4`，均不产生 production 或真实用户授权。

## D. P7 Visual Memory OS 方向性 Invariants

P7 仍为 `PROVISIONAL`，以下约束只保护未来架构方向，不授权提前实现、建表、选型或拆分任务。完整边界见 `docs/architecture/VISUAL_MEMORY_OS.md`。

1. **MEM-01 Visual Memory Primacy**：用户确认的最终视觉结果是主要持久审美证据。
2. **MEM-02 No Unsaved Generative Memory**：未保存或确认的 AI 输出不得直接更新持久偏好。
3. **MEM-03 Evidence Reconstructability**：每个持久学习结论必须可追溯到支持证据。
4. **MEM-04 Profile Is Derived**：AestheticProfile 是可重建的 materialized user model，不是不可变记忆权威。
5. **MEM-05 Evidence Preservation**：派生记忆更新不得破坏历史证据。
6. **MEM-06 Context Boundedness**：Agent context 不得随终身记忆量线性增长。
7. **MEM-07 User Control**：学习必须支持关闭、重置、删除和重新编译。
8. **MEM-08 Temporal Validity**：偏好演化必须按时间表达，不得破坏性覆盖。
9. **MEM-09 Current Instruction Priority**：当前明确用户指令高于历史偏好。
10. **MEM-10 Visual Content Is Not Instruction Authority**：图片或外部内容中的文字不自动获得指令权威。
11. **MEM-11 Derived Index Replaceability**：图、向量/视觉索引、Memory Card 与 Profile snapshot 必须可重建。
12. **MEM-12 Privacy Propagation**：删除权威证据必须删除或失效所有依赖派生表示。

## 数据与 API 规则

- 公共 API 使用 `/api/v1`；未实现功能明确返回 `501`，不得伪造成功。
- 错误格式固定为 `code`、`message`、`request_id`、`details`。
- 创建型请求接收 `Idempotency-Key`；异步任务返回不可猜测的 `job_id`。
- 数据库结构变更只能通过 Alembic migration；migration 必须在真实 PostgreSQL 上验证升级、回滚、重升级与 schema consistency。
- Aesthetic Profile、题库运行、Consent、Prompt 与 Provider 调用都必须锁定版本并可追溯。
- 原图资产、派生资产和编辑操作必须使用不同实体与不可变关联。

## 代码质量与完成标准

- TypeScript 开启 strict；Python 使用完整类型标注与严格 Pydantic schema。
- 核心领域逻辑不得放在路由、UI 组件或供应商 Adapter 中。
- 测试不得调用真实短信、云存储、AI 或支付服务；使用确定性 Fake/Mock。
- 提交前至少通过：格式检查、lint、类型检查、单元测试、契约漂移检查、构建和迁移检查。
- 安全或数据约束未完成时使用显式未实现状态，不得用临时旁路降低约束。
- 完成回复必须结论先行，并用一句话回显本次新增到 `MEMORY.md` 的内容。
