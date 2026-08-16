# P2 合成数据集研究协议

## 研究目标

P2 验证可控、可测量、变量隔离且可追溯的合成刺激资产；不定义美、目标脸型或人口模板，也不实施敏感属性推断或路由。

## 预注册与升级规则

- 先测量 repeated-run、re-encode 和 cross-platform variance，再选择 geometry/isolation tolerance。
- 对每个 dimension，先构建 synthetic calibration samples、测量 target/non-target distribution、冻结 versioned tolerance policy，再在未参与 calibration 的 identity holdout 上评估。不得事后放宽 threshold 强行 PASS。
- 每个 `READY` candidate 必须保存 dimension、algorithm/QAPolicy version、sample/identity count、requested/measured target-delta distribution、target error、non-target drift、holdout pass rate、repeat/platform variance、artifact failure、unsupported cases 和 uncertainty representation。
- P2-MVR-v1 的 N=24 只表示技术可行性下限；不稳定时升级 N=48，再升级 N=96。N=96 仍不稳定则重新分类，不无限扩容。
- exact SHA-256 duplicate 可直接拒绝。near duplicate 必须先通过第一方 pHash/Hamming candidate evidence、分布测量和标注校准；不得预设 magic constant。

## 禁止项

- 不使用抓取真人、明星、社交平台或用户图片。
- 不进行年龄估计、颜值评分、敏感分类或人口平均目标。
- 不将 generation/Vision model、OpenCV 或 MediaPipe candidate 状态写成生产批准。

任何 failure 输出 `FURTHER_RESEARCH` 或已批准的 unsupported classification，不伪造问卷、变量隔离或科学充分性成功。
