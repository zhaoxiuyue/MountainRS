# Calibration Contract v1｜草案（待所有者批准）

- **状态：** `draft_pending_owner_approval` —— 未获批准前不得读取逐单元 calibration-lit 支持量或执行 alpha 估计
- **合同依据：** Stage 7.2 合同 ③
- **前置：** Mconf 子协议 v1 必须先获批准（本合同引用它）
- **建立日期：** 2026-08-07

## 1. 唯一 target ROI

冻结网格 `shadow-risk-b-b4-grid-v1`：EPSG:32648，650 × 752，30 m，488,800 像元，
transform `[30.0, 0.0, 292230.0, 0.0, -30.0, 3473790.0]`。本合同不涉及第二个 ROI。

## 2. 上游有效掩膜

`base_valid_land`，定义与身份取自 Stage 7.1-R 冻结的
`configs/validity-support-schema-v1.json`，本合同不重新定义：

```
base_valid = Msource(SR_B4 ∧ SR_B5 ∧ QA_PIXEL) ∧ Mqa(qa_clear)
             ∧ reflectance_in_range ∧ terrain_geometry_valid
base_valid_land = base_valid ∧ ¬water
```

`Msource` 与 `Mqa` 由 Stage 7.1-R 交付，逐景计数已登记于
`observation-support-ledger-v1.json`。

## 3. calibration-lit 如何引用 Mconf

```
calibration_lit = base_valid_land ∧ (Mconf == 1)
```

即：**几何许可**（Mconf，纯几何、结果无关）与**观测有效性**（base_valid_land）的交集。

二者保持独立身份。calibration-lit 是本合同定义的派生集合，不得反过来影响 Mconf 的阈值，
也不得被当作 Mconf 或 base_valid_land 中任何一个的替代。

## 4. 最小支持阈值

### 4.1 推导依据（先于任何后果考量）

alpha 是过原点单参数最小二乘：`alpha = Σ(μρ)/Σ(μ²)`，其方差为 `σ²/Σμ²`。因此
统计信息量的正确单位是 `Σμ²`，而不是像元计数。

但本 ROI 上像元**高度空间自相关**，`Σμ²` 会系统性高估有效信息量。Stage 7.0 已经
冻结了本项目认定的空间独立尺度：`calibration-to-holdout-core buffer = 8.13 km = 271 像元`。
在这个尺度以内的像元不能被当作独立样本——这正是 7.0 `leakage_audit.md` 判定
「同一 acquisition 内的多个 core 共享标定支持、不是统计独立重复」的同一条理由。

由此得到一个与「能保住几景」完全无关的推导：

> **一个 calibration 集合若在像元规模上达不到一个空间独立尺度的线性长度（271 像元），
> 它在空间上无法代表该景的地形–光照条件，其 alpha 只是若干个高度相关像元的局部平均。**

顺带一个对 Stage 7.3 有用的数字：ROI 是 650 × 752 像元，即 2.40 × 2.77 个独立尺度，
**整个 ROI 的空间独立样本上限约为 4 到 6 个**。无论有多少像元都不会更多。

### 4.2 候选方案（请你选一个）

| | 方案 A | 方案 B（推荐） |
|---|---|---|
| 阈值 | 仅 `Σμ² > 0`（7.0 冻结硬条件） | `Σμ² > 0` **且** calibration-lit 像元数 ≥ 271 |
| 依据 | 7.0 `baseline_spec` 原文「nonempty, finite, strictly positive denominator」 | 上述空间独立尺度推导；271 来自 7.0 已冻结的 8.13 km buffer，非本节点新造 |
| 优点 | 不丢任何景；不稳健性由一并报告的标准误暴露，而不是被阈值藏起来 | 拒绝空间上无代表性的 alpha；与 7.0 的独立性判据同源 |
| 缺点 | 几十个相关像元也会产出一个看似正常的 alpha | 丢弃两景（见 4.3） |

**方案 C（`Σμ²` 数值阈值）不推荐**：`Σμ²` 的具体数值缺乏独立锚点，定多少都容易变成
按结果反推，正是合同 ③ 禁止的。

无论选哪个方案，都**必须同时记录** `Σμ²`、calibration-lit 像元数、以及 calibration
集合的 bounding-box 对角线长度，作为诊断信息随 alpha 一并发布——记录不等于设阈值。

### 4.3 后果披露（不构成阈值依据）

按合同 ③「阈值不得按期望保留数量、validation/test 结果或 residual 反推」，以下仅为
选定阈值后的**后果告知**，不参与 4.1 的推导：

`calibration_lit ≤ base_valid_land`，故可用 Stage 7.1 readiness 的逐景 `base_valid_land`
给出上界。方案 B 下会落入 `unsupported_calibration` 的是：

| order | product | base_valid_land（上界） | 几何 lit | split |
|---|---|---:|---:|---|
| 20 | LC08_130038_20231203 | 71 | 373,487 | **test** |
| 6 | LC08_130038_20230322 | 226 | 471,498 | train |

两景的几何都没问题（lit 分别占 76.4% 和 96.5%），支持不足纯粹来自云雪——它们的
QA-clear 像元分别只有 100 和 257。这是 Stage 7.1-R 账本里 `active.qa_rejected` 的
同一现象在 acquisition 尺度上的表现。

方案 B 的实际后果：train 10 → 9，test 5 → 4，validation 3 不变。三者仍非空。

order 7（`base_valid_land` 7,447）是下一个最接近的，仍远高于 271，不受影响。

## 5. 拟合键

`acquisition × band`。B4 与 B5 独立估计、独立报告。

**不加 `stratum` 维度**：合同 ④ 规定只有 Stage 7.0 已明确冻结地表分层及唯一归属规则时
才可增加该维度。我已确认 7.0 四份冻结文档中不存在任何地表分层定义，故本合同不引入分层，
也不得在 safe / transition / near-zero / shadow 等评价分区内分别重拟合。

## 6. 辐射缩放链路

```
rho = DN × 0.0000275 − 0.2        （Landsat 8 Collection 2 Level 2 SR）
mu  = max(cos_i, 0)
rho_hat = alpha × mu
alpha = clip(Σ(mu·rho) / Σ(mu²), 0, 1)
```

全部逐字取自 Stage 7.0 `baseline_spec.md`，本合同不改公式、不加截距、漫射项或任何自由度。
`rho` 必须能从原始 DN 复算，缩放常数不得写死在中间产物里而丢失来源。

在 calibration-lit 集合内 `cos_i > 0.1 > 0`，故 `mu = cos_i` 恒成立。

## 7. 支持损失记账

逐 acquisition × band 记录从 488,800 个世界位置到最终 calibration-lit 的每一步损失：

| 阶段 | 记账项 |
|---|---|
| 观测/上游有效性 | `observation_or_upstream_validity_exclusion`，细分沿用 Stage 7.1-R 的 `passive` / `active` 二分 |
| 几何机制 | `mconf_mechanism_zero`，即 `base_valid_land ∧ (Mconf == 0)` |

按合同 ⑦，`mconf_mechanism_zero` 须登记为 Stage 7.1-R
`validity-support-schema-v1.json` 中 **`active` 桶下的新细分类**，走该 schema 自身
规定的修订流程，**不另立平行标签体系**；`observation_or_upstream_validity_exclusion`
须声明其与既有 `passive` / `active` 二分的映射。顶层 passive / active 计数分别报告
且可相加，细分类计数不可相加为互斥分解。全部标签映射到架构 v3 §3 三类来源类别，
本节点不得产出 `observed_inferred`。

## 8. fold-safe calibration / evaluation 隔离规则（本节点只冻结规则，7.3 实例化）

1. 全支持 `alpha_reference_full_support` 标记 `evaluation_role = non_evaluative`，
   **禁止**用于任何 held-out block 的正式成绩。
2. 对任一 held-out block k，正式评测使用的 `alpha_{acquisition,band,−k}` 只能由该景
   位于 block k **及其冻结 buffer 之外**的 calibration-lit 像元，按本合同同一公式与
   同一阈值重估。
3. 重估后支持不足或分母非正 → 该 fold 记 `unsupported_calibration`，使用闭集
   reason_codes：`calibration_support_below_minimum`、`nonpositive_mu_squared_denominator`。
   **不得**回退全支持 alpha、默认值、插补、截距或漫射替代。
4. validation / test 的观测**不得**参与阈值、掩膜、公式、分层、模型选择或停止条件的制定。
5. block 拓扑、buffer 宽度与 fold 成员由 Stage 7.3 在查看任何 residual 或分数之前冻结，
   本节点不实例化。

**已知风险（转告 Stage 7.3）**：8.13 km buffer 在 19.5 × 22.56 km 的单 ROI 内，
空间独立单元上限约 4–6 个（见 4.1）。fold-safe 重估会进一步削减每景可用的 calibration-lit，
`base_valid_land` 在千量级的景（order 7 = 7,447 是最低的一个）可能在排除 block 后跌破阈值。
这属于正常路径，须如实登记，不得为提高有效 fold 数而缩小 buffer 或放宽阈值。

## 9. 本合同不做的事

不评分、不比较机制、不排名；不产出 sigmoid 置信度、连续 reliability 分或 risk–coverage
曲线；不裁决 model_eligible；不实例化 block/fold；不改变 evidence membership、split、
ROI、网格或成员集合；不把 3 景 `operation_scoped_unsupported` 放回拟合。

---

## 待你批准的事项

1. **最小支持阈值选 A 还是 B**（4.2）。我推荐 B——理由是它的数字来自 7.0 已冻结的
   独立性判据，而不是本节点新造；代价是 train 10→9、test 5→4。
2. **确认拟合键不加 stratum**（第 5 节）。这一条只是复核我对 7.0 的检查结论：
   四份冻结文档里确实没有地表分层定义。
3. **确认支持损失记账走 schema 修订而非新建标签体系**（第 7 节）。

批准后我会把两份草案冻结、登记 registry 别名，然后执行合同 ④⑤⑥⑦。
