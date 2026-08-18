# P2-M4 T07 Calibration Report

## Scope

本报告仅覆盖两个已通过 P2-M3 QA 的 private synthetic identities。另两个 identity 未执行 T07 variant，
保留给 commit 后 holdout。图片、raw landmarks、路径、object key 和 Vision log 均留在 private evidence；
仓库只记录 allowlisted aggregates 和 digest。

## Candidate sweep

第一轮测试 2%、4%、6% 的 broad local field。12 个双向尝试中，10 个产生 one-face output；两个较大
`INCREASE` 在 mesh overlap boundary 被 `INVALID_WARP_PLAN` fail closed 拒绝。4%/6% 同时出现更大的
control drift，因此未选择。

第二轮比较 narrow 与 medium local fields 的 2%/3% 候选。最终选择 narrow 3% 进入预注册，因为四项
calibration directions 均可执行、same-platform replay SHA-256 一致，且没有 foldover、source alias 或
face-count failure。选择依据在 holdout 前冻结，不代表 M5 isolation PASS。

## Selected calibration aggregates

| Calibration identity | Direction | Measured jaw-width relative delta | Nose-width relative delta | Eye-spacing relative delta | Changed pixels | Same-platform replay |
| -------------------- | --------: | --------------------------------: | ------------------------: | -------------------------: | -------------: | -------------------: |
| `calibration-a`      |  INCREASE |           `+0.015802581830319965` |   `+0.004486456612763301` |    `-0.006856322606209692` |       `243397` |                 PASS |
| `calibration-a`      |  DECREASE |           `-0.008805222938683369` |     `-0.0041022454508973` |   `+0.0005404330676924751` |       `237157` |                 PASS |
| `calibration-b`      |  INCREASE |           `+0.013629052249378713` |   `+0.006489571614617649` |   `+0.0024125853379857766` |       `321026` |                 PASS |
| `calibration-b`      |  DECREASE |          `-0.0036939624088014856` |   `-0.008338678971800594` |    `-0.007776075912926895` |       `313052` |                 PASS |

The measured target is directionally correct but materially asymmetric, and the controls are not zero. T07 therefore
tests reproducibility and measurement completeness; it does not claim variable isolation or a supported product
dimension. Those facts must remain visible to P2-M5 rather than being hidden by a post-hoc tolerance.

## Evidence binding

- Private selected-candidate report SHA-256:
  `e0159e9f6f915b7cc82472fbe61ed8f0aaf8a49359ca3aa4ce2f1e282e85d905`
- Windows runtime manifest digest:
  `27b33d646d8587f76d5ca317ac9d6aec95bc04fd87d413bb3dd6394f9694bb7a`
- Linux runtime manifest digest:
  `5d0e9ee323d7daea78e8baaeec63917c7a1867301ec5f7c71685fa9cbed311d8`
- Model SHA-256:
  `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`
- Topology: exact audited MediaPipe source, first 468 points, 852 ordered-list triangles.
- Final replay used `confidence_ppm=500_000` only as the ADR-040 plan-admission floor. It did not change output bytes
  relative to the same selected geometry with the earlier metadata placeholder.

`P2_M4_T07_CALIBRATION: COMPLETE`
