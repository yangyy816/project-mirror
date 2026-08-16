# P2 合成数据集研究协议

## 研究目标

P2 验证可控、可测量、变量隔离且可追溯的合成刺激资产；不定义美、目标脸型或人口模板，也不实施敏感属性推断或路由。

## 预注册与升级规则

- 先测量 repeated-run、re-encode 和 cross-platform variance，再选择 geometry/isolation tolerance。
- 对每个 dimension，先构建 synthetic calibration samples、测量 target/non-target distribution、冻结 versioned tolerance policy，再在未参与 calibration 的 identity holdout 上评估。不得事后放宽 threshold 强行 PASS。
- 每个 `READY` candidate 必须保存 dimension、algorithm/QAPolicy version、sample/identity count、requested/measured target-delta distribution、target error、non-target drift、holdout pass rate、repeat/platform variance、artifact failure、unsupported cases 和 uncertainty representation。
- P2-MVR-v1 的 N=24 只表示技术可行性下限；不稳定时升级 N=48，再升级 N=96。N=96 仍不稳定则重新分类，不无限扩容。
- exact SHA-256 duplicate 可直接拒绝。near duplicate 必须先通过第一方 pHash/Hamming candidate evidence、分布测量和标注校准；不得预设 magic constant。

## 首包 coverage 与 anti-stereotype protocol

- 首包使用 `CN_MAINLAND` market scope 和 `CN_EAST_ASIAN_PRESENTATION_V1` synthetic presentation
  scope，但连续 morphology measurement 才是 coverage、local-neighborhood matching、variant 与
  mode-collapse evidence 的技术依据；presentation scope 不能替代 measurement。
- 24→48→96 cohort 按预注册的 morphology coverage cells 分配，而不是只采样 generator 默认分布。
  每个 cell 记录 occupancy、empty/underrepresented status、nearest-neighbor distribution、duplicate
  rate、generation yield、QA pass、transform/isolation pass 与 Provider/model version effects。
- 检查 generator defaults 周围过度集中，以及 face proportions、makeup、skin finish、hairstyle、face
  shape 和 eye geometry 的重复。用连续 coverage 与独立 StyleContextPack 解决 breadth，禁止引入
  敏感标签、审美评分或人口平均目标。
- 首包 release 必须披露 market/presentation scope、covered/unsupported cells、style contexts、pose/3D
  限制、Provider bias、measurement limits 以及尚未完成最终 questionnaire validation；不得宣称
  globally representative。

## Reference research protocol

默认流程是 `web/literature/licensed research → human review → abstract non-identifying descriptors →
versioned policy/style context → fully synthetic generation`。禁止把公开真人肖像、社交媒体、搜索
结果、名人、网红、未知许可数据或单一真人模板用于 dataset generation。

未来 restricted reference study 必须先记录 source authority、copyright/license、adult model/portrait
release、AI/derivative/commercial/storage/retention/territory/revocation rights、reviewer、review date、
permitted/prohibited purposes、likeness/legal status。权利不完整即 `REQUIRES_LEGAL_REVIEW` 或
`PRODUCTION_BLOCKED`；获清权仍默认只提取 aggregated descriptors，不复制 identity，source pixels
默认不存储。

## 禁止项

- 不使用抓取真人、明星、社交平台或用户图片。
- 不进行年龄估计、颜值评分、敏感分类或人口平均目标。
- 不将 generation/Vision model、OpenCV 或 MediaPipe candidate 状态写成生产批准。
- 不推断或存储真实用户 race、ethnicity、ancestry、nationality 或 regional origin，不引入相应
  classifier 或 routing capability。
- 不在 prompt、fixture、registry 或 corpus 中加入真实姓名、未经许可真人图片或 social-media
  face-source URL；发现可疑 artifact 时 quarantine 并报告 provenance，不自动删除。

任何 failure 输出 `FURTHER_RESEARCH` 或已批准的 unsupported classification，不伪造问卷、变量隔离或科学充分性成功。
