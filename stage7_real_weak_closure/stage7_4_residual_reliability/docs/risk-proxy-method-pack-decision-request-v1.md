# Stage 7.4｜Option A method-pack decision request v1

- **状态：** `decision_required`（不是协议、配置或执行授权）
- **节点生命周期：** `planned`
- **已批准高层方案：** `A_geometry_margin_diagnostic`
- **批准回执：** PF3 `rc_6806b9d6224f`，route revision `64`
- **高层依据：** `docs/risk-proxy-decision-request-v2.md`，SHA-256
  `1d792bb402fc45faa5c5452dbe60245f39d99122afb3a507a366082e6775c9ab`
- **审计日期：** 2026-08-09（Asia/Shanghai 自然日；不声明日内时刻或跨文件先后）
- **结果盲边界：** 未打开或搜索 Stage 7.3 reports、outputs、residual／alpha／score 结果，
  未运行 Stage 7.3 fitter，也未读取 PF3 中既有的 7.3 科学结果正文。

## 为什么还需要一次裁决

Elara 已批准 `risk_proxy = 1 − cos_i` 的 geometry-risk diagnostic，但冻结上游与该回执均未
唯一给出 operating-point 网格、AURC 积分、最低 scored support／唯一分数／点数、flat
tolerance，以及五态 verdict 在什么点列上判定。下面三套均与 A、Stage 7.0 分母和 fold-safe
边界相容；任取一套都会新增实质方法选择，不能由执行者伪装成 A 回执已经批准。

三套共同且不再重选的不变量：逐 `acquisition × band × fold` 先应用 v2 的 fail-closed unit
gate；失败 unit typed `not_scored`、禁止 reference/default/imputation，并完整保留在机会 universe、
coverage 账本与汇总中。通过 gate 后，在 `base_valid_land ∧ Mconf=1` 上计算
`risk_proxy = 1 − cos_i`，低值先接纳；原始冻结 cos_i 按存储 dtype 解码后的位模式完全相同才算
tie（无 epsilon、四舍五入或二级排序），tie 整组原子接纳。coverage 分子为 accepted supported
像元数，分母为完整 core 的全部 `base_valid_land`；只有有限且 `cos_i <= 0.1` 的
`unsupported_by_direct_only` 永久 abstain、留在分母且绝不贡献 MAE。gate 通过后若任一
`base_valid_land` 像元的 cos_i missing/nonfinite，或任一 supported residual nonfinite，属于
`protocol_error` 并 fail-closed，**不得**降格为 abstention 或 not_evaluable。

risk 始终是 accepted set 的 MAE。全部逐 unit、逐 band 分开计算，禁止跨 unit 像元池化。
连续量先在 `acquisition × band × fold` 形成，再在每个 acquisition × band 内以 median/range
描述 folds，跨 acquisition 时每景等权且仍只报 median/range；B4/B5 永不合并。五态 verdict
只按原始五类分别计数，不合并成 pass/fail，也不据此排名 acquisition。任何输出都只是描述性
顺序诊断，不是 calibrated confidence/reliability 或统计显著性结论。

M2/M3 的每个 fixed-grid target 必须输出
`target_q / status / exact_point_index / realized_coverage / reason`。同一 exact point 被多个 q
映射时只在 verdict 点列保留一次，其余记录 `duplicate_exact_point`；unreachable reason 闭集为
`below_min_accepted_support`、`above_max_reachable_coverage`。禁止插值、拆 tie 或 forward-fill。

## 互斥完整 method packs

| 项 | **M1｜最小数学包** | **M2｜受保护 5% 包（推荐）** | **M3｜粗粒度传感器包** |
|---|---|---|---|
| operating points / coverage grid | 每个原子 tie 组接纳后形成 exact point；`accepted_n >= 2` 才是 admissible point。这些实际 coverage 自身就是 empirical grid，不另建共同网格。 | exact tie points 先按 `accepted_n >= 271` 过滤为 admissible points；目标 grid `q = 0.05, 0.10, …, 1.00` 只映射到不超过 q 的最大 admissible point。 | exact tie points 同样先按 `accepted_n >= 271` 过滤；报告 grid `q = 0.10, 0.20, …, 1.00`，映射规则同 M2。 |
| AURC / 积分 | 在首末 admissible exact coverage `[c_start,c_max]` 上按右连续 empirical staircase 精确积分，报告 `raw_area`、`coverage_span=c_max−c_start` 与 `raw_area/coverage_span`；不从 0 或向 1 外推。 | 与 M1 同一 exact staircase，但 `c_start` 是首个 `accepted_n>=271` 的点；5% grid 不参与积分。 | 只在去重 reachable decile 点的 `[c_start,c_max]` 上做线性梯形积分并除以实际 span；两端均不外推。三种积分约定都不是冻结上游推导，而是待批准方法选择。 |
| 最低 scored support | unit 级 `N_scored >= 2`。 | 两层 guard：unit 级 `N_scored >= 271`，且 verdict/AURC admissible point 级 `accepted_n >= 271`。271 只是候选 governance guard，**不是统计阈值或 271 个独立样本**。 | 与 M2 相同的两层 271 governance guard。 |
| 最低分辨率 | `unique_proxy_values >= 2`；admissible exact points `>= 2`。 | `unique_proxy_values >= 3`；admissible exact points `>= 3`；去重后 reachable 5% grid points `>= 3`。 | `unique_proxy_values >= 3`；admissible exact points `>= 3`；去重后 reachable decile points `>= 3`。 |
| flat tolerance | 纯数值容差：每对点 `τ = 64·ε64·max(1, |R_a|, |R_b|)`，其中 binary64 `ε64 = 2^−52`。 | 候选 owner-chosen numerical tolerance：`τ = 1e−12 + 1e−12·max(|R_a|, |R_b|)`；不是上游已批准 effect size。 | 绝对容差 `τ = 0.0000275` reflectance，即冻结 SR 缩放的一个 DN 步长；把亚量化步长变化视为 flat。 |
| 五态 verdict 的输入点列 | 全部 exact points。 | coverage 升序的去重 reachable 5% grid points。 | coverage 升序的去重 reachable decile points。 |
| 五态规则与优先级 | 三包同一机器谓词：先检查 gate 与本包 minimum，失败=`not_evaluable`；否则将 verdict 点列相邻 `ΔR` 按本包 τ 分为 `+ / 0 / −`。全 0=`flat`；有 + 无 −=`order_consistent`；有 − 无 +=`order_inverted`；同时有 +/−=`mixed`。 | 同左。 | 同左。 |
| 主要代价 | 最少新增约定，但允许极小、强相关支持形成 verdict；无共同 grid，exact 微步对局部波动敏感。 | 新增 5%/3-point/1e−12 约定，并把 calibration 的 271 外推成仅 governance guard；会更频繁产生 `not_evaluable`。优点是 exact 积分不受报告网格影响。 | decile 展示稳定，但隐藏 10% 之间结构；梯形积分不是 empirical staircase 精确面积，一个 DN tolerance 也可能把真实聚合差异判为 flat。 |

五态集合严格闭合为
`{not_evaluable, flat, order_consistent, order_inverted, mixed}`。`not_evaluable` reason 闭集为
`unit_gate_not_scored`、`N_scored_below_pack_minimum`、
`unique_proxy_values_below_pack_minimum`、`admissible_exact_points_below_pack_minimum`，以及仅
M2/M3 可用的 `reachable_grid_points_below_pack_minimum`。上述 protocol_error 优先于五态，
发生时终止并不产出 verdict。

**推荐 M2。** 它把共同展示网格与权威 exact 曲线分开，AURC 不受 5% 离散化影响；最低三点
形成非退化曲线，271 则是唯一已有的结果无关操作性支持锚点。代价已显式限定：5%/3 points/
1e−12 与把 271 用于 `N_scored`、`accepted_n` 都是等待 Elara 批准的新治理选择，不是上游
定理，也不得把 271 解释为空间独立样本数。

## 所有者回执格式

请回复且只回复其一：`APPROVE M1 — exact-minimal`、
`APPROVE M2 — guarded-5pct`、或 `APPROVE M3 — sensor-decile`。
回执前不得创建 frozen risk-proxy 协议／配置，不得把 activation 标为 ready，也不得读取任何
Stage 7.3 residual／alpha／score 结果数值。
