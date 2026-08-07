# Stage 7.2｜修补前 baseline 拟合与诊断配置

生成时间：2026-08-07
冻结合同：`docs/mconf-subprotocol-v1.md`、`docs/calibration-contract-v1.md`（均 frozen，所有者 2026-08-07 批准）
产物：`evidence/cos-i-registry-v1.json`、`mconf-registry-v1.json`、`alpha-reference-full-support-v1.json`、`support-loss-ledger-v1.json`、`fold-safe-alpha-rule-v1.json`

## 1. 结论

合同 ①②④⑤⑥⑦ 已完成，③ 的 calibration contract 已冻结并获批。36 个
`acquisition × band` 拟合单元中 **32 个 fitted、4 个 unsupported_calibration**，
每个单元恰好落入其一，无默认值、无插补、无修补。测试 37 项 + Stage 7.1 回归
151 项全绿。

本节点不评分、不算 residual、不产出任何置信度、不实例化 block 或 fold。

## 2. cos_i（①）：公式自检位级通过

21 个 evidence member 全部复算。硬门槛：用 order 1 的太阳几何复算，**逐像元位级
复现** Stage 6.5 冻结栅格（`afb0728e…`），`max_abs_difference = 0.0`，valid mask
完全一致——公式、角度约定、地形身份三者同时验明。

3 景 `operation_scoped_unsupported` 同样算出并登记，兑现 Stage 7.1-R 合同⑧。

**几何不是瓶颈**：lit（`cos_i > 0.1`）占比从 73.5%（order 1，仰角 31.14°）到
99.9%（order 10，仰角 68.81°），最低一景仍有 359,473 个 lit 像元。

## 3. Mconf（②）：一个因子，不是一个总分

`Mconf = cos_i > 0.1`，阈值逐字取自 Stage 7.0 `baseline_spec.md`，本节点未新增。

绑定为架构 v3 §3 六因子中的 **`geometry_visibility` 单因子**，`is_composite_confidence
= false`，`may_merge_with = []`。它不是 v3 §9 已撤销的那个合成 Mconf。

**覆盖边界（已冻结声明）**：只覆盖自阴影。投射阴影、地平线遮挡、去遮挡边界、
几何不稳定边界、视角遮挡全部未覆盖，归 Stage 7.5 / 7.6。因此本阶段几何支持是
**乐观上界**，且偏差方向已知——低太阳角的景投射阴影最重，而它们恰是 lit 比例
最低的景，真实可用区域只会更小。

## 4. alpha（④⑥）

估计式 `alpha = clip(Σ(μρ)/Σ(μ²), 0, 1)`，`μ = max(cos_i, 0)`，
`ρ = DN × 0.0000275 − 0.2`，全部取自 Stage 7.0，未加截距、漫射项或任何自由度。
拟合键 `acquisition × band`，**未加 stratum**（7.0 四份冻结文档中不存在地表分层定义）。

| order | product | split | calibration-lit | B4 alpha | B5 alpha |
|---|---|---|---:|---:|---:|
| 1 | LC08_130038_20230101 | train | 98,000 | 0.2209 | 0.3847 |
| 2 | LC08_130038_20230117 | train | 28,069 | 0.1997 | 0.3128 |
| 4 | LC08_130038_20230218 | train | 191,562 | 0.1219 | 0.2339 |
| 5 | LC08_130038_20230306 | train | 42,305 | 0.1120 | 0.2708 |
| **6** | **LC08_130038_20230322** | **train** | **222** | **unsupported** | **unsupported** |
| 7 | LC08_130038_20230407 | train | 7,445 | 0.2292 | 0.2898 |
| 8 | LC08_130038_20230509 | train | 72,649 | 0.0923 | 0.2738 |
| 9 | LC08_130038_20230525 | train | 156,048 | 0.1046 | 0.2761 |
| 11 | LC08_130038_20230626 | train | 316,583 | 0.0648 | 0.3621 |
| 13 | LC08_130038_20230728 | train | 22,301 | 0.0404 | 0.4502 |
| 14 | LC08_130038_20230813 | validation | 277,314 | 0.0486 | 0.3695 |
| 15 | LC08_130038_20230914 | validation | 286,700 | 0.0686 | 0.2982 |
| 16 | LC08_130038_20230930 | validation | 117,297 | 0.0914 | 0.2583 |
| 17 | LC08_130038_20231016 | test | 182,709 | 0.0944 | 0.2585 |
| 18 | LC08_130038_20231101 | test | 118,357 | 0.0848 | 0.2358 |
| 19 | LC08_130038_20231117 | test | 74,177 | 0.1194 | 0.2406 |
| **20** | **LC08_130038_20231203** | **test** | **71** | **unsupported** | **unsupported** |
| 21 | LC08_130038_20231219 | test | 16,078 | 0.1061 | 0.2402 |

**没有任何单元触发 clip**——全部 `alpha_raw` 天然落在 [0, 1] 内。

每个 alpha 标记 `parameter_role = scene_local_calibration_nuisance`、
`evaluation_role = non_evaluative`、`architecture_state_class = N_t`
（架构 v3 §2.1 干扰/标定变量，不得归因给 G 或 X(t)）。

B5 系统性高于 B4。本节点**不解释**这个现象——机制解释属后续节点，此处只登记。

### unsupported 的两个单元

阈值 271 由 Stage 7.0 冻结的 8.13 km 空间独立尺度推导，非按期望保留数量反推。

| order | calibration-lit | 几何 lit | QA-clear | calibration bbox 对角线 |
|---|---:|---:|---:|---:|
| 6 | 222 | 471,498 | 257 | 19.2 km |
| 20 | 71 | 373,487 | 100 | **2.3 km** |

两景几何都正常，支持不足**纯由云雪造成**。order 20 的 calibration 集合空间跨度
只有 2.3 km，**远小于 8.13 km 独立尺度**——71 个像元挤成一小块，连一个独立空间
单元都不到。这是阈值 271 的空间代表性论证在实测上的独立佐证（bbox 只作诊断记录，
未作阈值使用）。

结果：train 10→9、validation 3 不变、test 5→4，三者仍非空。

## 5. 支持损失账本（⑦）

18 景 × 488,800 = 8,798,400 个像元级单位：

| 阶段 | 计数 | 占比 |
|---|---:|---:|
| `observation_or_upstream_validity_exclusion` | 6,709,508 | 76.26% |
| `base_valid_land` | 2,088,892 | 23.74% |
| `mconf_mechanism_zero` | 81,005 | 0.92% |
| **`calibration_lit`** | **2,007,887** | **22.82%** |

账本逐景精确闭合：`base_valid_land − mconf_mechanism_zero = calibration_lit`，
且 `mconf_mechanism_zero = near_zero 45,480 + self_shadow 35,525`（互斥且穷尽）。

`mconf_mechanism_zero` 经 `configs/validity-support-schema-v2.json` 以 **delta
amendment** 形式登记为 Stage 7.1-R schema `active` 桶下的新细分类——v1 字节未动，
未另立平行标签体系。它与既有三类 active 细分类互斥（其谓词要求 `base_valid_land`
为真，而其余三类蕴含其为假），但 active 细分类整体仍不可相加。

值得记下的一个对比：几何机制拒绝只占 0.92%，而观测/上游有效性排除占 76.26%。
在这个 ROI 上，**限制标定的是云雪，不是地形**。这与 Stage 7.1-R 得出的
「主动清零是被动无观测的 1,322 倍」是同一事实的不同切面——那里比的是缺失的成因，
这里比的是缺失的规模。

## 6. fold-safe 规则（⑤）：只冻结，不实例化

`evidence/fold-safe-alpha-rule-v1.json` 冻结五条规则供 Stage 7.3 实例化：
reference alpha 非评价性、block 与 buffer 之外重估、支持不足记 typed unsupported
且禁止一切 fallback、holdout 不得参与任何选择、拓扑须在看到结果之前冻结。

阈值 271 与 buffer 8.13 km 同时冻结，`threshold_may_be_relaxed_by_stage_7_3 = false`。

**已量化转交 Stage 7.3 的风险**：ROI 为 2.40 × 2.77 个独立尺度，**空间独立样本
上限约 4–6 个，与像元数无关**。fold-safe 重估会进一步削减每景 calibration-lit；
当前最低的 fitted 景是 order 7（7,445）。Stage 7.3 合同①已要求先做几何可行性
审计，容纳不下时停机由所有者裁决，不得自行缩小 buffer 或降低阈值。

## 7. 边界

未调用 Earth Engine，未改写任何冻结件，未改变成员集合、资格谓词、ROI、网格或
split；未评分、未算 residual/reliability/risk–coverage、未裁决 model_eligible、
未实例化 block 或 fold、未把 3 景 `operation_scoped_unsupported` 放回拟合。
