# Core / Topology 子协议 v1

- **状态：** `frozen`
- **合同依据：** Stage 7.3 合同 ①③（core/topology 定义必须结果盲、唯一且可复算，否则不得激活）
- **建立日期：** 2026-08-08
- **批准：** 所有者于 2026-08-08 批准本方案
- **生命周期：** 本子协议在 Stage 7.3 **planned 状态**冻结。激活后不得修订；若发现歧义须记 problem 并终止该 cycle。

## 1. 为什么需要它

合同 ③ 要求 core 形状、尺寸、网格锚点、候选枚举顺序、边缘处理、并列 tie-break，以及从候选 core 到最终 fold 集合的 selection algorithm，全部由 Stage 7.0 冻结定义或已批准子协议**唯一给出**。

Stage 7.0 四份冻结文档一致地把 ROI/core protocol 列为**执行前必须先冻结的 blocker**，而不是已冻结的定义：

| 文档 | 原文要点 |
|---|---|
| `evaluation_protocol.md` | Required before an execution is admitted：a formal Stage 7 ROI protocol with projected/geographic boundaries and non-overlap checks；designated calibration and holdout ROIs |
| `leakage_audit.md` | remaining blocker：Freeze a Stage 7 ROI protocol before execution |
| `baseline_spec.md` | cores are regression-reference geometry with shared calibration；a formal Stage 7 ROI protocol must be used before execution |
| `data_gap_report.md` | minimum gap #2：Define a formal Stage 7 ROI protocol |

故 ③ 的七项在上游全部缺失。本子协议补齐它们。

## 2. 关键事实：现成 core 就落在当前 ROI 内

Stage 7.0 记录的 Shadow-risk B raster bounds 与 Stage 7.1 冻结 ROI bounds 完全相同：

```
Stage 7.0 Shadow-risk B  [292230, 3451230, 311730, 3473790]  EPSG:32648
Stage 7.1 冻结 ROI        [292230, 3451230, 311730, 3473790]  EPSG:32648
```

因此 C5-D3 的 5 个 `shadow_risk_b_combined_risk` core 的投影边界（已冻结于
`data_gap_report.md` 与 `leakage_audit.md` 的表格中）直接落在当前 target grid 上，
无需任何坐标变换或重新构造。

## 3. Core 集合（唯一、冻结）

采用上述 5 个 core 的冻结投影边界，**不新增、不修改、不重新构造**：

| core_id | 投影边界 [left, bottom, right, top] (m, EPSG:32648) | 尺寸 |
|---|---|---|
| `shadow_risk_b_combined_risk_01` | [295110, 3467550, 301350, 3473790] | 6.24 × 6.24 km |
| `shadow_risk_b_combined_risk_02` | [307890, 3451230, 311730, 3455070] | 3.84 × 3.84 km |
| `shadow_risk_b_combined_risk_03` | [308370, 3470430, 311730, 3473790] | 3.36 × 3.36 km |
| `shadow_risk_b_combined_risk_04` | [302790, 3460350, 307590, 3465150] | 4.80 × 4.80 km |
| `shadow_risk_b_combined_risk_05` | [301350, 3466110, 307590, 3472350] | 6.24 × 6.24 km |

**形状**：轴对齐矩形（在 EPSG:32648 中），边界即上表数值。
**尺寸**：由边界唯一确定，不参数化、不缩放。
**网格锚点**：边界坐标均为 30 m 的整数倍，与 target grid transform `[30, 0, 292230, 0, -30, 3473790]` 精确对齐；core 像元集合定义为像元**中心**落在闭区间边界内者。
**非重叠**：Stage 7.0 leakage_audit 已证明五者两两不重叠（`core overlap: none`）；本节点须复算复核。

## 4. Selection algorithm（唯一、可复算）

```
最终 fold 集合 := 上表全部 5 个 core，按 core_id 字典序升序编号 k = 1..5
```

**全取，不筛选。**

这一决定同时消除了合同 ③ 中另外三项歧义——**没有候选筛选过程，就不存在枚举顺序、边缘处理与并列 tie-break 问题**：

- **候选枚举顺序**：不适用（无候选池，集合即全集）
- **边缘处理**：不适用（core 边界为既定常数，不由 ROI 边缘裁剪或生成规则产生）
- **并列 tie-break**：不适用（无排序择优步骤）

若将来需要从更大候选池中择选 core，必须另立 v2 子协议并重新经所有者批准；本 v1 不授权任何筛选。

## 5. Fold 层级映射（补齐合同 ⑧ 的唯一解析）

```
fold  ≡  Stage 7.0 evaluation_protocol 中的 "non-overlapping ROI" 层
```

因此：

```
Stage 7.0 最小评估单元  acquisition × non-overlapping ROI × band
Stage 7.3 最小报告单元  acquisition × band × fold
```

二者是**同一单元的不同书写顺序**，不是两套口径。Stage 7.0 冻结的
`residual = rho_hat − rho_obs`、signed bias / MAE / P90 absolute residual、
`coverage 分母 = base_valid_land`、"only supported pixels contribute to
supported-residual metrics"、以及聚合四条规则，全部原样适用于 Stage 7.3 的
`acquisition × band × fold`，无需改写。

## 6. 采样偏倚声明（必须随每次报告一并出现）

这 5 个 core 是 C5-D3 按 **`combined_risk_stress`** 准则选定的，即**刻意选在阴影与
质量风险高的位置**。它们不是随机采样，也不是 ROI 的均匀覆盖。

因此：

> Stage 7.3 的 fold 级结果只代表 **direct-only baseline 在本 ROI 内已知最难的那几块地上的表现**，不代表 ROI 平均表现，更不代表区域平均表现。

任何把 fold 级汇总表述为「该 ROI 的整体精度」的写法都是违约。这一条不得省略、不得
压缩为脚注。

## 7. 几何可行性预证（planned 状态，纯几何）

在冻结 ROI（650 × 752，30 m）上，对每个 core 计算「几何标定域」——即 ROI 内到该
core 最小欧氏距离 ≥ 8,130 m 的像元集合（合同 ② 的隔离准入判据）：

| core | 几何标定域像元数 | 占 ROI |
|---|---:|---:|
| 01 | 229,693 | 47.0% |
| 02 | 345,360 | 70.7% |
| 03 | 357,872 | 73.2% |
| 04 | 124,258 | 25.4% |
| 05 | 181,157 | 37.1% |

**五者全部非空**，最小者仍有 12 万像元。按合同 ④ 的 `minimum_viable_fold_count = 2`，
几何上可形成 5 个 fold，满足「≥3 为首选」。

**重叠事实（不是阻塞，但必须声明）**：几何标定域两两 Jaccard 重叠 0.207–0.625
（最高为 01–05 的 0.625）。这与 Stage 7.0 leakage_audit 的
`pairwise shared calibration: 10/10` 一致。故合同 ⑤⑦ 要求的「共享 actual calibration
的 fold 不是统计独立重复」在本 topology 下是**必然成立的约束**，不是套话：
**5 个 fold 在任何意义上都不构成 5 个独立样本。**

本节数值由 `scripts/audit_geometric_feasibility_v1.py` 可复算，只使用 ROI/grid 坐标与
本子协议第 3 节的 core 边界，**未读取任何逐景 radiance、QA/validity 支持量、alpha、
residual 或分数**，符合合同 ① 对 pre-flight 读取范围的限制。

## 8. 本子协议不做的事

不定义 residual 指标、阈值、评分口径（那些在 Stage 7.0 已冻结，见第 5 节映射）；
不读取任何逐景支持量；不实例化 actual calibration；不计算 alpha；不改变 ROI、
target grid、成员集合、split 或 Stage 7.2 的任何冻结件；不授权从候选池筛选 core。
