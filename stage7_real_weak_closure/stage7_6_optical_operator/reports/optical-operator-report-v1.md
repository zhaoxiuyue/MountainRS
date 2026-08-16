# Stage 7.6 报告｜光学 L2 算子资格化：漫射、邻接与大气边界

**记录日期** 2026-08-16　**结论范围** evidence_scope = local（单 ROI、非独立 fold）
**结果暴露地位** post-result exploratory——Stage 7.3/7.4 的 residual 在本节点激活前已公开，本节点不声称 preregistered；节点内部的候选集、比较关系与判定规则在首次读取本节点结果之前冻结并完成 PF3 写回读回（回执 `rc_8603d0824173`）。

---

## 1. 结论

三个加性项候选全部判 `unsupported_by_evidence`。**没有任何候选进入冻结 L2 栈。本节点结束时，L2 光学算子仍为 direct-only：`rho_hat = alpha · mu`。**

| 候选 | 加性项 | 物理地位 | 中位改善 | fold 正向 | 终态 |
|---|---|---|---|---|---|
| C1 | `beta_v · v_sky` | mechanism_candidate | +0.06% | 2/5 | unsupported_by_evidence |
| C1′ | `beta_0` | empirical_offset（对照） | +0.31% | 3/5 | unsupported_by_evidence |
| C2a | `beta_terr · (1 − v_sky)` | mechanism_candidate_under_assumption | +0.20% | 4/5 | unsupported_by_evidence |
| C3 | `l_path` | 加性路径辐射 | 未运行 | — | non_identifiable（解析） |
| 严格邻接项 | 需 latent 地表状态 | — | 未运行 | — | deferred_missing_required_input |

冻结门槛为中位改善 ≥ 5%、5 个 fold 中至少 4 个方向为正。三个候选的改善量与门槛相差近两个数量级。

算子形式相对 Stage 7.2/7.3 未变化。本节点改变的是：这三个加性项从「尚未检验」变为「已检验且未获支持」，并附带可复核的失败方式。

---

## 2. 判定链与其冻结时序

1. **激活预检** v1 blocked → v2 ready → v3 ready(final)，合同定稿于 route revision 88。
2. **结果盲声明**（激活后首个非只读动作）：声明截至该动作未读取本节点所依赖的既有结果值，绑定 13 项上游 path 与 SHA-256。两层盲分开声明——相对既有结果 NOT_BLIND，相对本节点结果 BLIND。
3. **几何 Gate**：`v_sky` 的方位数与搜索距离由纯几何收敛测试选定，全程只读 DEM。选定 N\* = 36、D\* = 10000 m，含地球曲率。
4. **协议与配置冻结**：候选集、比较关系、消融顺序、指标、阈值、tie 规则、support gate 全部冻结，交叉审计 X1–X11 通过（负例 8/8），PF3 写回读回完成。
5. **消融执行**（首次读取本节点结果值）：180 单元 = 18 acquisition × 2 band × 5 fold，逐单元拟合四个候选。
6. **终态判定**：机械执行冻结的 `verdict_rules`。
7. **结果审计**：Y1–Y11 全通过，负例自检 11/11 全部捕获。

第 5 步之前的每一项都可独立复核其发生在读取结果之前——这是本节点全部结论可信度的前提。

---

## 3. 逐候选结果

### C1｜带地形调制的天空漫射项

`rho_hat = alpha·mu + beta_v·v_sky`，是统一二参数框架在 `beta_0 = 0` 约束下的一维子模型。

- 中位相对改善 **+0.0006**（门槛 0.05）
- fold 中位改善：`1: −0.0274　2: +0.0042　3: −0.0283　4: +0.0260　5: −0.0187`，正向 **2/5**（门槛 4/5）
- `beta_v` 中位绝对值 **0.03634**，达基线 MAE 的 **0.82 倍**；P5–P95 为 −0.0288 至 +0.1675
- alpha 由 0.2446 移至 0.1849，**相对位移 −19.9%**

### C1′｜无地形调制的常数项（对照基线）

`rho_hat = alpha·mu + beta_0`，`beta_v = 0` 约束。

- 中位相对改善 **+0.0031**，fold 正向 **3/5**
- `beta_0` 中位绝对值 0.02426，达基线 MAE 的 0.69 倍
- alpha 相对位移 **−17.2%**

**该候选是本节点唯一能回答「地形调制值多少」的对照。** 即使它通过，因不含地形调制，其结果也不得被引用为漫射机制或路径辐射机制已获支持——本次它未通过，该限定同样适用于对其数值的任何引用。

### C2a｜几何近似邻接项

`rho_hat = alpha·mu + beta_terr·(1 − v_sky)`，`beta_0 = −beta_v` 约束，物理假设为「周围坡面亮度均匀，邻接辐照正比于被地形占据的立体角」。

- 中位相对改善 **+0.0020**，fold 正向 **4/5**——五条判据中唯一通过方向一致性检验的候选
- `beta_terr` 中位 −0.00257，但 **P5 −0.25311 至 P95 +0.43955**，符号在单元间翻转
- 参数幅度达基线 MAE 的 **2.61 倍**而方向不定
- alpha 相对位移仅 **+0.3%**

方向一致但幅度可忽略、参数巨大而符号不稳——这一组合的自然读法是它在拟合噪声，而非捕捉一个弱但真实的效应。

### C3｜加性大气路径辐射（registered_not_run）

对给定 acquisition × band，路径辐射是加性常数，与 `beta_0` 逐点同形，观测无法区分。判定依据是**解析的，不依赖任何实验数据**。候选终态 `non_identifiable`；其引入的对象 `l_path` 在身份侧判 `non_identifiable_equivalent`。两套闭集取值不同，不得互相代入。

显式登记并显式判定，比默默不提更诚实。

### 严格邻接项（deferred）

其严格形式需要周围坡面的地表状态，而该 latent 状态属 Stage 7.7 且尚未激活。**不得用观测值代入充当该状态**——那会使邻接项从 held-out core 的隔离带内读取信息，构成泄漏。终态 `deferred_missing_required_input`。

---

## 4. 必须与误差改善并列报告的项

只报告误差改善会让本节点的结果看起来像「小幅改善但未达标」，而实际情况不是这样。

### 4.1 新增自由度对 alpha 的吸收

| 候选 | alpha 基线 | alpha 候选 | 相对位移 |
|---|---|---|---|
| C1 | 0.2446 | 0.1849 | **−19.9%** |
| C1′ | 0.2446 | 0.1750 | **−17.2%** |
| C2a | 0.2446 | 0.2288 | +0.3% |

C1 与 C1′ 加入一个自由参数后，alpha 系统性下降近两成。新自由度不是在捕捉一个可迁移的物理机制，而是在训练支持区内**重新分配原本归给 alpha 的解释**；分配完成后，外推到 held-out core 便不再成立——这正是改善接近零的机制。

架构 §1.3 与合同 passCriteria 5 要求新增自由度不得吸收其他层错误。此处观察到的正是该吸收，故三个候选即便改善达标也需要单独论证其未发生错误吸收。本次改善未达标，该问题不必进一步展开，但必须记录。

### 4.2 参数边界命中

三个候选的边界命中占比均为 **0.000**（门槛 ≤ 0.10）。alpha 在全部 scored 单元中天然落在 [0, 1]，未发生任何裁剪。本节点不对多参数模型的 alpha 施加 clip——裁剪会破坏最小二乘的最优性并使候选间不可比。

### 4.3 数值稳定性与其原理性局限

全部 scored 单元的设计矩阵条件数远低于 Stage 7.5 工具箱的秩亏判据（`s_min ≤ s_max × 1e-10`）。本节点与工具箱使用**同一个 rtol = 1e-10**，而非 `lstsq` 的默认阈值——否则两处「数值秩亏」含义不同。

**必须复述的局限（合同 passCriteria 5）**：数值方法无法区分「结构不可辨识」与「数据在关键维度变化不足」。Stage 7.5 的 F2/F6 fixture 证明二者的数值秩与秩亏完全相同，而正确处置相反（改模型 vs 补数据）。本节点对该局限的处置是引入独立的几何前置条件——`support_gate` 要求训练支持区内 `v_sky` 的 IQR ≥ 0.05，把「数据变化不足」的情形在数值检查之前就挡下来，而不是指望条件数去分辨它。

### 4.4 coverage

三个候选与基线在每个单元上使用**同一个评分掩膜**，故 coverage 逐单元恒等，无一单元因 coverage 超容差（0.001）而被排除比较。train 单元的中位 coverage 已登记在判定表中。

### 4.5 unsupported 与机会分母

| 候选 | scored | not_scored | unsupported |
|---|---|---|---|
| C0 | 146 | 12 | 22 |
| C1 / C1′ / C2a | 132 | 8 | 40 |

两参数候选比基线多 18 个 unsupported 单元，全部来自 `insufficient_v_sky_variation`——训练支持区内 `v_sky` 的 IQR < 0.05。train 单元中该比例为 26/100。

这些单元**保留 acquisition/band/fold 身份、coverage 账本与 reason code，仍计入机会分母，不产生指标也不静默消失**。support_gate 触发时判 unsupported 而非硬解出一个由数值噪声决定的参数——这是 Stage 7.5 F6 情形的正确处置。

### 4.6 描述性迁移检查（不参与判定）

| 候选 | validation 中位改善 | test 中位改善 |
|---|---|---|
| C1 | −0.0034 | +0.0048 |
| C1′ | −0.0043 | +0.0223 |
| C2a | +0.0205 | +0.0230 |

**这些数字不改变任何终态。** 按冻结的 split 纪律，train 决定资格，validation/test 只做描述性报告，独立确认留给 Stage 7.10。

值得记录的一点：C2a 在 validation/test 上的改善（约 +2%）高于其在 train 上的改善（+0.2%）。留出集表现优于训练集，在一个参数由训练集估计的模型里是反常的，通常指示噪声而非效应。这一观察本身也只是描述性的。

---

## 5. tie 规则的执行及其边界

C1 与 C1′ 的中位改善差为 0.0025 < 0.01，触发 tie 规则。二者自由参数数相同，按冻结规则取不含 empirical_offset 者，即 **C1 优先于 C1′**。

**该结论不授予 C1 任何资格。** 两者均未满足 `qualified_criteria`，故「C1 优于 C1′」只说明在两个都不成立的假设之间规则指定了哪一个优先，**不得被解读为 v_sky 的地形调制已获证据支持**。

事实上就实测数字而言，C1 的改善（+0.06%）低于 C1′（+0.31%）、方向一致性也更差（2/5 vs 3/5）。tie 规则的偏好方向与实测方向相反，这一点必须与规则结论一并陈述。

---

## 6. 这次失败的方式

三条排除依据构成闭集排除法，使 `unsupported_by_evidence` 成为唯一终态：

- **不是 `non_identifiable`**：`support_gate` 保证进入比较集的每个单元 `v_sky` IQR ≥ 0.05，条件数远低于秩亏判据。参数是可辨识的，问题不在辨识性。
- **不是 `deferred_missing_required_input`**：所需输入全部就位——`v_sky` 已由几何 Gate 选参并全图计算冻结，不依赖任何未激活的 latent 状态。
- **不是 `redundant_equivalent`**：新参数估计值达基线 MAE 的 0.69–2.61 倍，alpha 被系统性改变，预测函数与基线明显不同。**模型确实变了，只是没有变好。**

同样重要的是，失败**不是**因为没给机会：

- `v_sky` 全图取值 0.4361–1.0000，中位 0.8356，训练单元 IQR 中位 0.0621——它远不是一个可以用常数近似掉的量。
- 几何精度经三步收敛测试选定，交叉复核 (36, 10 km) vs (72, 20 km) 通过；DEM 外扩 20010 m > D，**边界截断像元为 0**。
- 三个候选覆盖了统一二参数框架中三个不同的一维方向，不是只试了一种形式。

---

## 7. 泄漏封堵的实际情况

逐 fold 泄漏审计报告零违规。但必须说明该检查的性质：**它在数学上恒真**——`actual_calibration ⊆ 几何标定域`，而`标定域 ∩ core = ∅` 在装载时已 fail-closed 检查。它复述一个已被结构保证的事实，不是一次独立发现。

本节点的真实泄漏通道是另外两条，分别由不同机制封堵：

1. **几何算法参数依 held-out residual 调节**——由 `svf-geometry-gate` 在读取任何结果之前纯几何选定全部参数封堵。这是本节点最实质的泄漏风险：使用全域 DEM（含 core 外部）计算 `v_sky` 本身不构成泄漏，因为地形是已冻结的 G；泄漏只可能来自「用留出结果挑了几何算法」。
2. **邻接项读取 core 邻域观测**——由严格邻接项判 `deferred_missing_required_input` 封堵。该通道长在物理项内部而非拟合代码里，是激活预检 v1/v2 均未识别、由关闭前审计发现的真实缺口。

---

## 8. 结论边界

- **空间**：单 ROI（Stage 7.1 冻结范围）。
- **统计**：fold 与像元均不构成独立重复；不声称概率、校准置信度或统计显著性。像元池化产生的伪样本量在本节点被显式禁止，全部指标按 acquisition × band 等权。
- **evidence_scope = local**。引用 Stage 7.5 判定时其 evidence_scope 一并继承——本节点以 alpha 的 `identity_qualified_with_fixed_gauge` 为前提，该身份的 gauge 限定同样适用于此处的全部 alpha 数值。

**不能得出的结论**：

- 不得表述为「天空漫射项在山地遥感中无用」——本结论限于本 ROI 的这套观测、这套 fold 拓扑与这一种线性加性形式。
- 不得表述为「地形调制不存在」——未获支持的是该假设在本数据上的可检测性，不是该物理过程的存在性。
- 不得以本节点结果为依据放宽或收紧下游任何阈值。

---

## 9. 未覆盖项

- **DEM 接缝**：外扩 DEM 由「原始获取 + ROI 窗口整体替换为冻结 DEM」合成，ROI 内与冻结 DEM 逐位相同（max|d| = 0.0000 m），但 ROI 边界存在一条接缝（mean +0.049 m / std 7.792 m / max 103.6 m）。7.8 m 的高程落差在数公里外对应约 0.09° 的地平线角误差，低于 Gate 收敛阈值一个量级，但该项作为未覆盖项登记，不作为已解决问题处理。
- **alpha 吸收未被独立量化**：本节点观察到吸收并记录了幅度，但未构造独立实验分离「吸收」与「真实效应」。因三个候选均未达改善门槛，该分离在本节点不影响任何终态；若未来有候选达标，该分离必须先行完成。
- **`v_sky` 的其他使用方式未检验**：本节点只检验了线性加性形式。乘性形式、与 mu 的交互形式均未登记为候选，不在本节点结论范围内。

---

## 10. 产物

| 文件 | 角色 |
|---|---|
| `configs/svf-geometry-gate-v1.json` | 几何精度选择协议（结果前冻结） |
| `configs/optical-operator-config-v1.json` | 候选集、判定规则、support gate（结果前冻结） |
| `evidence/freeze-manifest-v1.json` | 冻结件唯一 hash 权威 |
| `evidence/result-blind-declaration-v1.json` | 两层结果盲声明 + 13 项上游绑定 |
| `evidence/operator-identity-registry-v1.json` | 算子与推断对象分开登记 |
| `evidence/dem-extension-provenance-v1.json` | 外扩 DEM 来源、合成、可复现性验证 |
| `evidence/optical-operator-contract-v1.json` | 冻结算子形式、参数来源表、依赖图 |
| `evidence/gate-receipts-v1.json` | 逐候选逐项判据收据 |
| `outputs/v_sky_roi_grid_v1.tif` | v_sky 全图（488,800 像元） |
| `outputs/svf-gate-run-v1.json` | 几何 Gate 执行记录 |
| `outputs/ablation-unit-table-v1.json` | 180 单元逐候选拟合与评分 |
| `outputs/verdict-table-v1.json` | 终态判定与闭集排除依据 |
| `outputs/result-audit-v1.json` | Y1–Y11 + 负例自检 |
| `scripts/compute_svf_v1.py` / `run_svf_gate_v1.py` | v_sky 计算与几何 Gate |
| `scripts/run_ablation_v1.py` | 消融执行（装载段沿用 Stage 7.3） |
| `scripts/decide_verdicts_v1.py` | 终态机械判定 |
| `scripts/cross_audit_freeze_v1.py` | 冻结阶段交叉审计 X1–X11 |
| `scripts/audit_results_v1.py` | 结果阶段 fail-closed 审计 Y1–Y11 |
| `scripts/emit_gate_receipts_v1.py` | 收据生成 |
