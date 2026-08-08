# Stage 7.3｜单 ROI 同域空间阻断与轮换留一诊断

生成时间：2026-08-08
冻结件：`docs/core-topology-subprotocol-v1.md`（frozen，所有者 2026-08-08 批准）、`evidence/topology-manifest-v1.json`（frozen）
产物：`preflight-manifest-v1.json`、`geometric-feasibility-audit-v1.json`、`topology-manifest-v1.json`、`fold-alpha-and-leakage-ledger-v1.json`、`descriptive-residual-summary-v1.json`

> **这是单 ROI、同域空间阻断诊断。** 标定支持与留出区来自同一 ROI、同一气候带与地质背景，按架构 v3.1 §2.7 与 §6 **不能替代 Cross-Domain Isolated Validation**；正式跨域验证属 Stage 7.9 / 7.10。本报告不声称任何泛化能力。

## 0. 采样偏倚（必须先读）

本节点采用的 5 个 core 由 C5-D3 按 **`combined_risk_stress`** 准则选定，**刻意位于阴影与质量风险高处**，不是随机采样，也不是 ROI 的均匀覆盖。

因此：**下列 fold 级结果只代表 direct-only baseline 在本 ROI 内已知最难的那几块地上的表现，不代表 ROI 平均表现，更不代表区域平均表现。**

## 1. 结论

合同 ①–⑩ 全部完成。180 个 `acquisition × band × fold` 单元中 **158 fitted / 22 unsupported_calibration**，其中 **146 个产出描述性 residual**。**泄漏检查零违规。** 测试 23 项 + 上游回归 188 项（stage7.1 的 151、stage7.2 的 37）全绿。

未使用任何全支持 reference alpha 参与成绩；未计算 effective n、p 值或置信区间；未做机制比较或排名。

## 2. Activation pre-flight（①）：先判不可激活，补齐后才开工

首轮 pre-flight 在 **planned 状态**判定**不可激活**：Stage 7.0 四份冻结文档一致地把 ROI/core protocol 列为「执行前必须先冻结的 blocker」，合同③要求的七项（core 形状/尺寸/锚点/枚举顺序/边缘处理/tie-break/selection algorithm）在上游**全部缺失**。

关键事实是此前未被注意到的一处重合：

```
Stage 7.0 Shadow-risk B raster bounds  [292230, 3451230, 311730, 3473790]
Stage 7.1 冻结 ROI bounds              [292230, 3451230, 311730, 3473790]
```

C5-D3 的 5 个 core 的冻结投影边界直接落在当前 target grid 上。所有者据此批准 core-topology 子协议 v1，采用「**全取，按 core_id 字典序升序**」的 selection algorithm——因不存在候选筛选过程，枚举顺序、边缘处理、并列 tie-break 三项**由结构消除而非靠补充规定**。

scoring protocol 的缺口是层级映射：子协议 §5 声明 `fold ≡ Stage 7.0 evaluation_protocol 的 non-overlapping ROI`，二者是同一单元的不同书写顺序，7.0 冻结的口径原样适用。

## 3. 拓扑层（④⑤前半）：冻结时未读任何逐景数据

`build_topology_manifest_v1.py` 在物理上不可能违反合同⑤的分层要求——它只做坐标解析几何，**全程只以写模式打开 GeoTIFF，从不以读模式打开任何影像**。

每个 fold 的三区互斥且穷尽整个 ROI（已逐 fold 断言）：

| fold | core | buffer（隔离带） | 几何标定域 | 合计 | 到自身域最小距离 |
|---|---:|---:|---:|---:|---:|
| 1 | 43,264 | 215,843 | 229,693 | 488,800 | 8130.1 m |
| 2 | 16,384 | 127,056 | 345,360 | 488,800 | 8130.1 m |
| 3 | 12,544 | 118,384 | 357,872 | 488,800 | 8130.1 m |
| 4 | 25,600 | 338,942 | 124,258 | 488,800 | 8130.1 m |
| 5 | 43,264 | 264,379 | 181,157 | 488,800 | 8130.1 m |

5 个 fold 全部满足 8,130 m 隔离准入，达合同④「≥3 为首选」。cores 两两不重叠；其中两对 core 距离为 0（边界接触），与 Stage 7.0 leakage_audit 记录的 `minimum core-to-core gap 0 m (touching boundaries)` 一致。

几何可行性审计在 active 状态复算，**与 planned 状态的预证 sha256 完全相同**。

## 4. Fold-safe alpha（⑤后半⑥）

```
actual_calibration_lit_{acq,band,k}
    = geometric_calibration_domain_k ∩ base_valid_land ∩ geometry_visibility(cos_i > 0.1)
```

公式、辐射缩放链路、`Σμ² > 0` 与操作阈值 `calibration_lit ≥ 271` 全部沿用 Stage 7.2，未放宽。

### unsupported_calibration 分布（22 个单元）

| acquisition | split | unsupported 单元 | 说明 |
|---|---|---|---|
| LC08_130038_20230322 | train | **10 / 10** | 全支持阶段已 unsupported（222 像元） |
| LC08_130038_20231203 | test | **10 / 10** | 全支持阶段已 unsupported（71 像元） |
| **LC08_130038_20231219** | **test** | **2 / 10** | **全支持阶段 fitted（16,078 像元），fold-safe 后跌破阈值** |

全部 reason_code 为 `calibration_support_below_minimum`，无一例 `nonpositive_mu_squared_denominator`；无默认值、无插补、**无一例回退到 reference alpha**。

**order 21 这一条兑现了 Stage 7.2 `fold-safe-alpha-rule-v1` 的预警**：「fold-safe 重估会进一步削减每景可用的 calibration-lit，calibration_lit 在万量级以下的景存在跌破 271 的风险」。这属合同⑥明列的正常结果，未触发任何合同放宽。

另有 12 个单元 fitted 但**未评分**：其 holdout core 内没有 supported 像元——core 本就选在风险高处，某些景在那几块地上全部被上游有效性或几何代理拒绝。它们记为 `not_scored`，**未编码为零误差或低误差成功**。

## 5. 泄漏证明与独立性（⑦）

- **actual calibration 与本 fold core 及其 8,130 m 隔离带的交集：全部为空，零违规。**
- **10 对 fold 全部共享 actual calibration**——与 Stage 7.0 leakage_audit 的 `pairwise shared calibration 10/10` 完全一致。

> **这 5 个 fold 不是统计独立重复。** fold 数不得用作 effective n，不得据以计算 p 值或置信区间。本节点未计算上述任何一项。

## 6. 描述性 residual 汇总（⑧）

口径逐字取自 Stage 7.0 evaluation protocol：`residual = rho_hat − rho_obs`；只有 supported 像元进入 supported-residual 指标；coverage 分母为 holdout core 内的 `base_valid_land`。**只给中位数与范围，不做像元池化。**

| band \| fold | 评分单元 | signed bias 中位 | MAE 中位 | P90 中位 | coverage 中位 |
|---|---:|---:|---:|---:|---:|
| B4 \| fold1 | 15 | +0.0318 | 0.0368 | 0.0696 | 0.974 |
| B4 \| fold2 | 14 | −0.0034 | 0.0242 | 0.0505 | 0.996 |
| B4 \| fold3 | 14 | +0.0282 | 0.0328 | 0.0593 | 0.972 |
| B4 \| fold4 | 14 | +0.0039 | 0.0256 | 0.0536 | 0.968 |
| B4 \| fold5 | 16 | +0.0256 | 0.0344 | 0.0645 | 0.978 |
| B5 \| fold1 | 15 | −0.0074 | 0.0528 | 0.1022 | 0.974 |
| B5 \| fold2 | 14 | −0.0264 | 0.0512 | 0.1040 | 0.996 |
| B5 \| fold3 | 14 | +0.0118 | 0.0430 | 0.0898 | 0.972 |
| B5 \| fold4 | 14 | +0.0071 | 0.0560 | 0.1062 | 0.968 |
| B5 \| fold5 | 16 | +0.0022 | 0.0460 | 0.0994 | 0.978 |

逐单元均并列报告了四个口径：holdout core 总像元、上游有效像元、geometry proxy 支持像元、实际 scored 像元。

**两处纯描述性观察（不作机制解释——机制比较属后续节点）**：

1. B5 的 MAE 中位数（0.043–0.056）系统性高于 B4（0.024–0.037）。
2. B4 的 signed bias 在 fold 1／3／5 偏正（+0.026 ~ +0.032），在 fold 2／4 接近零（−0.003 ~ +0.004）。

本节点**不解释**这两个现象，也不据此对模型充分性下任何结论。

## 7. 质量因子来源语义（⑨）

架构 v3.1 §3 的六因子中，本节点的评估状态如下。**未评估者一律不由 residual 外观反推为已评估**：

| 因子 | 本节点状态 | 来源 |
|---|---|---|
| `support_mask` | 已使用 | Stage 7.1-R `base_valid_land` |
| `geometry_visibility` | 已使用（**仅 self-shadow 代理**） | Stage 7.2 Mconf 子协议 |
| `sensor_quality` | 已使用 | QA_PIXEL bits 0–5 |
| `reconstruction_quality` | **本节点未评估** | 无无人机重建输入 |
| `model_adequacy` | **本节点未评估** | 见下方说明 |
| `output_uncertainty` | **本节点未评估** | 属 Stage 7.4 及以后 |

**关于 `model_adequacy` 的特别声明**：本节点产出了 residual 指标，但 residual 的存在**不等于**模型充分性已被评估。第 6 节的两处观察是描述性的，未做任何充分性诊断。按合同⑨，此处只在 limitations 中声明「未评估」，**未临场发明新的 schema 枚举或平行分类体系**。

全部原因标签沿用 Stage 7.1-R provenance／deprivation taxonomy 及 Stage 7.2 delta amendment。任何 operation-level unsupported **未撤销** 任何景的 `evidence_membership = included`（21 景成员资格全程未变）。本节点未产出 `observed_inferred`。

## 8. 语义边界（⑩）

- 本节点是**单 ROI 同域空间阻断诊断**，不能替代架构 v3.1 §2.7／§6 的 Cross-Domain Isolated Validation。
- 5 个 fold **共享 actual calibration，不是独立重复**；fold 数不是样本量。
- core 由 `combined_risk_stress` 准则选定，结果只代表本 ROI 内已知最难区域。
- 引用 Stage 7.2 数字时的口径限定（沿用其关闭前科学语义修正，不得扩写）：
  - **0.92%** 仅是 Stage 7.2 当前 self-shadow／near-zero 代理下**已识别**的几何清零比例，是下界，不代表完整地形遮挡影响；
  - **76.26%** 仅是 `observation_or_upstream_validity_exclusion` 桶，**不得整体改称云雪造成**；
  - `calibration_lit ≥ 271` 是操作性最低像元支持量，**不证明空间独立**——本节点的空间隔离由 EPSG:32648 中真实 8,130 m 距离的拓扑构造与审计证明，与 271 无关。

## 9. 操作边界

未调用 Earth Engine；未改写任何冻结件；未改变成员集合、ROI、网格、split 或资格谓词；未在 topology 冻结后调整拓扑；未使用 reference alpha 参与任何成绩；未计算 reliability、risk–coverage、置信度、effective n、p 值或置信区间；未裁决 model_eligible；未激活 Stage 7.4。
