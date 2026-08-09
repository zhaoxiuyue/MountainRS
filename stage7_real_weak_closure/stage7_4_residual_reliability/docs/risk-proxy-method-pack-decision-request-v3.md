# Stage 7.4｜Option A method-pack decision request v3

- **状态：** `decision_required`（不是协议、配置或执行授权）
- **节点生命周期：** `planned`
- **直接前任：** `docs/risk-proxy-method-pack-decision-request-v2.md`，SHA-256
  `659ece5ae1b9966f2ae7176ab94efa744373d5b3aaad7ee82c426cae07a8e11a`
- **更早前任：** `docs/risk-proxy-method-pack-decision-request-v1.md`，SHA-256
  `7891bed6a165300fabab6f39750eded4b67b2fbf1e4be03e70a2b14921b08efb`
- **前任处置：** v1/v2 字节均未改；本文件 append-only supersede 两者。
- **已批准高层方案：** `A_geometry_margin_diagnostic`；PF3 回执
  `rc_6806b9d6224f`，route revision `64`
- **审计日期：** 2026-08-09（Asia/Shanghai 自然日；不声明日内时刻或跨文件先后）
- **结果盲边界：** 未打开或搜索 Stage 7.3 reports、outputs、residual／alpha／score 结果，
  未运行 Stage 7.3 fitter，也未读取 PF3 中既有的 7.3 科学结果正文。

## 0. Supersession scope 与 material-drift ledger

三方案的身份（M1/M2/M3）与 **M2 推荐**保持不变；它们的完整定义并非逐版完全不变。

### v1 → v2 的 material drift

1. 将单一、含混的 coverage 表述拆为 T/D/S/A 计数、三个有名称的 coverage、零分母语义与
   整数乘积恒等式；增加 stratum/risk-curve 两张最低报告表。
2. 将 protocol error 增加 `cos_i outside [-1,1]`，但 v2 错把 cos_i 检查域写成整个 core；
   该过宽范围由 v3 修正为 `base_valid_land`。
3. 将 M1 verdict 输入从 v1 表格中的“全部 exact points”纠正为“全部 **admissible** exact
   points”；M2/M3 明确只用去重 canonical reachable grid points。
4. 引入四个命名 curve scopes；v2 中 M1 仍只建 `unit_all_scored`，M2/M3 建全部四个 scope。
5. 将一个 residual flat tolerance 拆成 proxy `tau_score` 与 outcome/curve `tau_outcome`；明确
   M3 的一个 SR DN 只适用于 outcome，绝不适用于 dimensionless proxy score。
6. 将旧五态 shape verdict 拆成 `curve_shape` 与 PF3 科研 `risk_proxy_verdict`，并区分
   insufficient support 与 score degeneracy。
7. 扩展 fixed-grid 状态、duplicate canonical 记录、unreachable reason、整数 q 比较；将 AURC
   的 J、span、积分公式和禁止从 0/向 1 外推写成机器约束。

### v2 → v3 的 material drift

1. 冻结逐 scope、point filtering/grid **之前**的原始 score-range 定义与退化谓词。
2. 将 v2 过宽的“core 中任一 cos_i”protocol error 域收回到 core 内 `base_valid_land`；core 外或
   非 base-valid 像元不因本协议报错。
3. 将 coverage canonical 字段统一为 `selective_prediction_coverage`，同步全部恒等式；短名仅可作
   显式、逐值相等的 alias。
4. 为 J=0、两端越界、区间内 floor mapping 与 q=cJ 补齐 fixed-grid 完整 piecewise 规则。
5. 以无条件 scoring partition 恒等式取代 v2 的无条件 max-selective 恒等式；后者改为只对存在
   terminal admissible point 的 stratum 断言。
6. 四个 scope 现适用于三个 pack，包括 M1 的三个 secondary stratum curves；verdict 逐 scope
   产生，禁止合成 unit/node verdict，汇总键与 not-evaluable reason 一并冻结。
7. owner reply token 升为 v3；v2 token 不授权 v3。

## 1. 三包共同、不再重选的不变量

逐 `acquisition × band × fold` 先应用已登记的 fail-closed fold-safe unit gate；失败 unit typed
`not_scored`，禁止 reference/default/imputation，并完整保留在机会 universe、账本与汇总。通过
gate 后，在 `base_valid_land ∧ Mconf=1` 上计算原始 `risk_proxy = 1 − cos_i`，低值先接纳。

只有 core 内 `base_valid_land` 像元的 cos_i missing/nonfinite/outside `[-1,1]`，或任一 supported
residual nonfinite，才由本协议判 `protocol_error`：立即 fail-closed，不得降格为 abstention 或
not-evaluable，也不产出科研 verdict。core 外或 core 内非 `base_valid_land` 像元不因本协议判错。
有限且 `cos_i <= 0.1` 的 `unsupported_by_direct_only` 是永久 abstention。

### 1.1 逐 scope 原始 score range 与 exact ties

curve scope 闭集为
`{unit_all_scored, mu_band_low, mu_band_mid, mu_band_high}`。三个 pack 都为四个 scope 独立建 curve、
独立判 gate；`unit_all_scored` role=`primary`，三个 `mu_band_*` role=`secondary`。

对每个 scope，在任何 accepted-point filtering 或 fixed-grid mapping **之前**，用该 scope 全部
finite scored supported pixels 的每像元原始 proxy 值定义：

```text
s_min       = min_i(risk_proxy_i)
s_max       = max_i(risk_proxy_i)
score_range = s_max - s_min
```

计算 min/max 时不得舍入、量化、分箱，也不得先把 bit-exact ties 合并成一条记录；每个像元都
进入 min/max。随后才按冻结存储 dtype 解码后的 bit pattern 识别 exact tie group；无 epsilon tie、
无二级排序，tie group 整组原子接纳。`score_range <= tau_score` 必须在 point filtering/grid 之前
短路为 `not_evaluable_score_degenerate`。S=0 时 s_min/s_max/score_range 均为 null，由 insufficient
support 分支先行结案。

### 1.2 Coverage canonical contract

对每个 unit 令 `T=core_total_pixel_count`（冻结 core footprint 内该 unit 的全部机会像元）、
`D=base_valid_land_count`（完整 core）；对每个 scope 令 `S=scored_pixel_count`、第 j 点
`A_j=accepted_pixel_count`。先以整数断言 `0 <= A_j <= S <= D <= T`，再定义：

```text
evidence_support_coverage          = D / T
scoring_coverage                   = S / D
selective_prediction_coverage_j    = A_j / D
acceptance_given_scored_j          = A_j / S
```

`selective_prediction_coverage` 是唯一 canonical 字段名。若兼容输出短名 `selective_coverage`，必须
声明 `alias_of=selective_prediction_coverage` 且逐值、逐 null 完全相同，不得成为第二定义。

- `T=0` → `protocol_error_zero_core_total`，无科研 verdict。
- `T>0,D=0` → 合法零证据支持，unit typed `not_scored`；evidence coverage=0，其余比例 null，
  reason=`zero_base_valid_land_denominator`，逐 scope verdict 为 insufficient support。
- `D>0,S=0` → scoring/selective-prediction coverage=0；acceptance-given-scored=null，reason=
  `zero_scored_denominator`，该 scope verdict 为 insufficient support。
- 浮点输出前用整数交叉乘法验证：
  `evidence_support_coverage * scoring_coverage = S/T`、
  `evidence_support_coverage * selective_prediction_coverage_j = A_j/T`、
  `selective_prediction_coverage_j = scoring_coverage * acceptance_given_scored_j`（S>0）。

coverage 逐 unit、逐 band 独立，禁止跨 band 相加或跨 unit 像元池化。

### 1.3 Partition、两张最低报告表与汇总

令 h 遍历三个 supported strata。整数 partition `sum_h(S_h)=S_unit_all` 必须成立；D>0 时，无论
scope 是否 evaluable、是否有 admissible/grid point，都无条件断言：

```text
sum_h(stratum_scoring_coverage_h) = unit_all_scored.scoring_coverage
```

只有 stratum h 存在 terminal admissible point（其 `A_terminal=S_h`）时，才断言
`max_selective_prediction_coverage_h=S_h/D`；不存在时该 max 字段为 null，且该 h 不进入任何
max-selective 等式。不得再无条件声称三个 stratum max 之和等于 unit-all scoring coverage。

1. `stratum_table`：最小行键 `acquisition × band × fold × stratum`，五 strata 全报；含 T/D、
   evidence coverage、stratum footprint/base-valid/scored counts、canonical coverage、status 与支持层
   residual metrics。`self_shadow`、`near_zero` 为 `by_design_unsupported` 账本行，不强塞科研 verdict。
2. `risk_curve_table`：行键 `acquisition × band × fold × curve_scope`；四 scope 全报，用完整 core
   的 D，并按所选 pack 对各自 S/points 独立判 gate。每行保留 scope role、curve_shape、PF3
   risk_proxy_verdict 与 not_evaluable_reason。

verdict 只逐 curve_scope 产生；禁止合成 unit-level 或 node-level verdict。连续量先逐 unit 形成，
每个 acquisition × band × curve_scope 内只以 fold median/range 描述；跨 acquisition 每景等权且仍
只报 median/range。分类汇总键为 `band × curve_scope × PF3 risk_proxy_verdict`，分别计数五个值并
保留各 not-evaluable reason；禁止 pass/fail 合并、打分或排名。

### 1.4 Fixed-grid 完整映射

M2/M3 先取得 coverage 升序的 admissible exact points `j=1..J`，其中
`c_j=A_j/D`。每个 q 记录字段为
`target_q/status/exact_point_index/selective_prediction_coverage/reason/canonical_target_q`。
`realized_coverage` 如为兼容而出现，只能显式声明为 `selective_prediction_coverage` 的逐值 alias。

对 q=k/m，全部比较使用整数交叉乘法，禁止 float：

```text
J = 0                 -> 所有 q: unreachable / below_min_accepted_support
J > 0 and q < c_1     -> unreachable / below_min_accepted_support
J > 0 and q > c_J     -> unreachable / above_max_reachable_coverage
c_1 <= q <= c_J       -> j* = max{j : c_j <= q}; provisional mapping to j*
```

例如 q 与 c_j 的 `c_j<=q` 只用 `m*A_j <= k*D`；q=cJ 必须映射 J。对映射到同一 j* 的全部 q，
最小 q 是唯一 `reachable`：`reason=null`、`canonical_target_q=target_q`；其余为 `duplicate`，保留
exact index 与 canonical coverage，`reason=duplicate_exact_point`、canonical_target_q 指向该最小
q。所有 unreachable 的 exact index、canonical coverage、canonical_target_q 均为 null。
status 闭集为 `{reachable,unreachable,duplicate}`；unreachable reason 闭集恰为上述两个值。
禁止拆 tie、插值、超调或 forward-fill。

## 2. 互斥完整 method packs

| 项 | **M1｜最小数学包** | **M2｜受保护 5% 包（推荐）** | **M3｜粗粒度传感器包** |
|---|---|---|---|
| curve scopes | 四 scope 全建，逐 scope 独立判 gate。 | 同左。 | 同左。 |
| operating/grid | 每个 atomic tie 后为 exact point；`accepted_n>=2` 才 admissible；actual coverages 为 empirical grid。 | exact points 先按 `accepted_n>=271` 过滤；q=`1/20…20/20` 依 1.4 只映射 admissible points。 | exact points 同样先按 `accepted_n>=271` 过滤；q=`1/10…10/10` 依 1.4 映射。 |
| N/point minimum | 每 scope `N_scored>=2`、`unique_proxy_values>=2`、admissible exact points `>=2`。 | 每 scope `N_scored>=271`；每个 verdict/AURC admissible point `accepted_n>=271`；另需 unique values、admissible points、canonical reachable grid points 各 `>=3`。271 只是 governance guard。 | 与 M2 相同的双层 271 与三项最低分辨率；grid 为 decile。 |
| score-flat tolerance | 对 1.1 原始 score endpoints：`tau_score=64*eps64*max(1,abs(s_min),abs(s_max))`，`eps64=2^-52`。 | `tau_score=1e-12+1e-12*max(abs(s_min),abs(s_max))`；批准后才成为 owner-chosen tolerance。 | dimensionless proxy 沿用 M2 `tau_score`；绝不使用 reflectance DN。 |
| outcome/curve-flat tolerance | 相邻 ΔMAE：`tau_outcome=64*eps64*max(1,abs(R_a),abs(R_b))`。 | `tau_outcome=1e-12+1e-12*max(abs(R_a),abs(R_b))`。 | 只对 ΔMAE 用 `tau_outcome=0.0000275` reflectance（一个冻结 SR DN）；绝不用于 score range。 |
| verdict 点列 | 全部 **admissible** exact points。 | coverage 升序的 canonical reachable 5% points。 | coverage 升序的 canonical reachable decile points。 |
| AURC | admissible exact points `j=1..J`：`area=sum[j=1..J-1](R_j*(c_{j+1}-c_j))`；`span=c_J-c_1`；`normalized=area/span`；需 `J>=2,span>0`。 | 同一 exact staircase，只用 `accepted_n>=271` admissible exact points；grid 不参与积分。 | canonical reachable decile points做梯形：`area=sum[0.5*(R_j+R_{j+1})*(c_{j+1}-c_j)]`；同报 span、area/span。 |
| 积分边界 | 三包都只积分 `[c_start=c_1,c_max=c_J]`；报告 span，不从 0 外推，也不向 1 或 abstention 区外推。 | 同左。 | 同左。 |
| 主要代价 | 可由极小、强相关支持形成 verdict；无共同 grid，exact 微步敏感；v3 新增 secondary curves。 | 5%/3-point/双层271/1e-12 都是待批准治理选择，但 exact AURC 不受展示 grid 影响。 | decile 隐藏 10% 间结构；梯形非 empirical exact area；一个 DN outcome tolerance 可能判 flat。 |

## 3. 逐 scope machine precedence、shape 与 PF3 verdict

以下按每个 curve_scope 独立短路，后级不得覆盖前级：

1. identity/hash/count invariant、T=0、1 节限定域内 cos_i/residual 错误任一发生 →
   `protocol_error`，停止执行；`curve_shape=null`、`risk_proxy_verdict=null`。
2. unit gate 失败、D=0、S=0 或 `N_scored<pack minimum` →
   `not_evaluable_insufficient_scored_support`，shape=null，并保留精确 reason。
3. 在 filtering/grid 前计算 1.1 原始范围；`score_range<=tau_score`，或 unique values、admissible
   points、canonical reachable grid points、AURC J/span 未达本包 minimum →
   `not_evaluable_score_degenerate`，shape=null，并保留精确 reason。
4. 否则对 verdict 点列相邻 `delta=R_b-R_a`：`delta>tau_outcome => +`；
   `abs(delta)<=tau_outcome => 0`；`delta<-tau_outcome => -`。全 0=`flat`；有 + 无 −=
   `order_consistent`；有 − 无 +=`order_inverted`；同时有 +/−=`mixed`。
5. 映射：`order_consistent -> descriptive_ordering_signal`；`order_inverted ->
   directionally_adverse`；`flat|mixed -> descriptive_non_discriminative`。

最终 PF3 verdict 闭集恰为
`{not_evaluable_insufficient_scored_support,not_evaluable_score_degenerate,
descriptive_ordering_signal,directionally_adverse,descriptive_non_discriminative}`。必须保留 shape；
`mixed` 只能称“无一致方向”，不得称“统计无信号”。protocol_error 不产生科研 verdict。

**推荐 M2**，但这不是授权。M1/M2/M3 的全部 v3 约定须由 Elara 选一；高层 A 回执不替代选择。

## 4. 所有者回执格式

请回复且只回复其一：`APPROVE M1 — exact-minimal-v3`、
`APPROVE M2 — guarded-5pct-v3`、或 `APPROVE M3 — sensor-decile-v3`。
回执前不得创建 frozen risk-proxy protocol/config、不得标记 activation ready，也不得读取任何
Stage 7.3 residual／alpha／score 结果数值。
