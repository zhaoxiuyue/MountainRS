# Stage 7.4｜Option A method-pack decision request v2

- **状态：** `decision_required`（不是协议、配置或执行授权）
- **节点生命周期：** `planned`
- **前任：** `docs/risk-proxy-method-pack-decision-request-v1.md`，SHA-256
  `7891bed6a165300fabab6f39750eded4b67b2fbf1e4be03e70a2b14921b08efb`
- **supersedes scope：** 只修复 coverage 术语、科研 verdict 映射、双 tolerance、fixed-grid
  记录及 reporting granularity；M1/M2/M3、高层 A 与 M2 推荐保持不变。v1 字节未改。
- **已批准高层方案：** `A_geometry_margin_diagnostic`；PF3 回执
  `rc_6806b9d6224f`，route revision `64`
- **审计日期：** 2026-08-09（Asia/Shanghai 自然日；不声明日内时刻或跨文件先后）
- **结果盲边界：** 未打开或搜索 Stage 7.3 reports、outputs、residual／alpha／score 结果，
  未运行 Stage 7.3 fitter，也未读取 PF3 中既有的 7.3 科学结果正文。

## 1. 三包共同、不再重选的不变量

逐 `acquisition × band × fold` 先应用 v2 已登记的 fail-closed fold-safe unit gate；失败 unit
typed `not_scored`，禁止 reference/default/imputation，并完整保留在机会 universe、账本与汇总。
通过 gate 后，在 `base_valid_land ∧ Mconf=1` 上计算 `risk_proxy = 1 − cos_i`，低值先接纳。
冻结 cos_i 按存储 dtype 解码后的位模式完全相同才是同一 `unique_proxy_value`；无 epsilon tie、
四舍五入或二级排序，tie 整组原子接纳。

只有有限且 `cos_i <= 0.1` 的 `unsupported_by_direct_only` 是永久 abstention。冻结 core 中任一
cos_i missing/nonfinite/outside `[-1,1]`，或任一 supported residual nonfinite，均为
`protocol_error`：立即 fail-closed，不得降格为 abstention／not_evaluable，也不产出科研 verdict。

### 1.1 Coverage 计数与零分母

对每个 curve scope 令：`T = core_total_pixel_count`（该 unit 冻结 core footprint 的全部观测机会
像元）、`D = base_valid_land_count`（完整 core）、`S = scored_pixel_count`（该 scope）、
`A_j = accepted_pixel_count`（该 scope 第 j 点）。必须先用整数断言
`0 <= A_j <= S <= D <= T`，再定义：

```text
evidence_support_coverage = D / T
scoring_coverage          = S / D
selective_coverage_j      = A_j / D
acceptance_given_scored_j = A_j / S
```

- `T = 0` 是 `protocol_error_zero_core_total`，无科研 verdict。
- `T > 0, D = 0` 是合法的零证据支持：`evidence_support_coverage = 0`；其余三个比例为 `null`
  且 reason=`zero_base_valid_land_denominator`，unit typed `not_scored`，科研 verdict 为
  `not_evaluable_insufficient_scored_support`。
- `D > 0, S = 0` 时 scoring/selective coverage 为 `0`、`acceptance_given_scored=null`，reason=
  `zero_scored_denominator`，科研 verdict同为 `not_evaluable_insufficient_scored_support`。
- 浮点输出之前必须以整数交叉乘法验证恒等式：
  `evidence_support_coverage * scoring_coverage = S/T`、
  `evidence_support_coverage * selective_coverage_j = A_j/T`、
  `selective_coverage_j = scoring_coverage * acceptance_given_scored_j`（`S>0`）。

coverage 全部逐 unit、逐 band 独立，禁止跨 band 相加或跨 unit 像元池化。

### 1.2 两张最低报告表

1. `stratum_table`：最小行键为 `acquisition × band × fold × stratum`，五个 stratum 必须全报。
   每行含 T/D、统一的 evidence_support_coverage、stratum footprint/base-valid/scored counts、
   scoring/selective coverage、status 与支持层 residual metrics。`self_shadow`、`near_zero` 是
   `by_design_unsupported` 账本行，不强塞科研 verdict；三条 `mu_band_*` 行保留支持层指标。
2. `risk_curve_table`：行键为 `acquisition × band × fold × curve_scope`。scope 闭集为
   `{unit_all_scored, mu_band_low, mu_band_mid, mu_band_high}`；每个 scope 的 coverage 分母都用
   完整 core 的 D，并按所选 pack 对该 scope 的 S/points 单独判 gate。恒等式：
   三个 supported-stratum scope 的 `max_selective_coverage` 之和必须等于
   `unit_all_scored.scoring_coverage`。不得跨 band 求和。

连续量先逐 unit 形成；每个 acquisition × band 内只以 median/range 描述 folds，跨 acquisition
时每景等权且仍只报 median/range。科研 verdict 只按五个原始值分别计数，禁止合并为 pass/fail、
打分或排名。

### 1.3 Fixed-grid 记录

M2/M3 每个 q 必须输出
`target_q/status/exact_point_index/realized_coverage/reason/canonical_target_q`。q 与 exact coverage
用整数交叉乘法比较（5% grid：`20*A_j <= k*D`；decile：`10*A_j <= k*D`），禁止 float 比较。

- `status` 闭集：`reachable | unreachable | duplicate`。
- reachable：`reason=null`；同一 exact point 被多个 q 映射时，最小 q 是唯一 canonical reachable。
- duplicate：保留 canonical/exact index 与 realized coverage，`reason=duplicate_exact_point`；不进入
  verdict 点列。
- unreachable：`exact_point_index=null`、`realized_coverage=null`、`canonical_target_q=null`；
  reason 闭集为 `below_min_accepted_support | above_max_reachable_coverage`。
- 禁止拆 tie、插值、超调或 forward-fill。

## 2. 互斥完整 method packs

| 项 | **M1｜最小数学包** | **M2｜受保护 5% 包（推荐）** | **M3｜粗粒度传感器包** |
|---|---|---|---|
| curve scopes | 只对 `unit_all_scored` 建 curve；五 strata 仍完整进入 stratum_table。 | 四个 curve_scope 全建，各自独立判 gate。 | 四个 curve_scope 全建，各自独立判 gate。 |
| operating/grid | 每个 atomic tie 后形成 exact point；`accepted_n>=2` 才 admissible。actual coverages 自身为 empirical grid。 | exact points 先按 `accepted_n>=271` 过滤；q=`1/20…20/20` 只映射到 admissible points。 | exact points 先按 `accepted_n>=271` 过滤；q=`1/10…10/10` 只映射到 admissible points。 |
| N/point minimum | 每 scope `N_scored>=2`、`unique_proxy_values>=2`、admissible exact points `>=2`。 | 每 scope 两层 guard：`N_scored>=271` 且每个 admissible point `accepted_n>=271`；另需 `unique_proxy_values>=3`、admissible exact points `>=3`、去重 canonical reachable grid points `>=3`。271 只是 governance guard，不是统计阈值或独立样本数。 | 与 M2 相同的两层 271 guard 与三项最低分辨率，但 grid 为 decile。 |
| score-flat tolerance | 对 proxy score range：`tau_score=64*eps64*max(1,abs(s_min),abs(s_max))`，`eps64=2^-52`。 | `tau_score=1e-12+1e-12*max(abs(s_min),abs(s_max))`；批准 M2 才成为 owner-chosen numerical tolerance。 | score 仍为 dimensionless cos_i proxy，故沿用 M2 的 `tau_score`；**不得**使用 reflectance DN。 |
| outcome/curve-flat tolerance | 对相邻 ΔMAE：`tau_outcome=64*eps64*max(1,abs(R_a),abs(R_b))`。 | `tau_outcome=1e-12+1e-12*max(abs(R_a),abs(R_b))`；同为待批准 numerical tolerance。 | 只对 ΔMAE 用 `tau_outcome=0.0000275` reflectance（一个冻结 SR DN 步长）；绝不用于 proxy score range。 |
| verdict 点列 | 全部 **admissible** exact points。 | coverage 升序的 canonical reachable 5% points。 | coverage 升序的 canonical reachable decile points。 |
| AURC | 对 coverage 升序的 admissible exact points `j=1..J`：`area=sum[j=1..J-1](R_j*(c_{j+1}-c_j))`；`span=c_J-c_1`；`normalized=area/span`。需 `J>=2, span>0`。 | 与 M1 同一 empirical staircase，但只在 `accepted_n>=271` 的 exact points 上；grid 不参与积分。 | 对 canonical reachable decile points：`area=sum(0.5*(R_j+R_{j+1})*(c_{j+1}-c_j))`，同样报告 span 与 area/span。 |
| 积分边界 | 三包都只积分 `[c_start=c_1,c_max=c_J]`，报告 span；不从 0 外推，也不向 1 或 abstention 区外推。staircase/trapezoid 均是待批准方法约定，不是冻结上游推导。 | 同左。 | 同左。 |
| 主要代价 | 允许极小、强相关支持形成 verdict；无共同 grid、无 per-stratum curve，exact 微步敏感。 | 新增 5%/3-point/1e-12 约定，并把 271 外推成两层 governance guard；会更频繁产生 not-evaluable，但 exact AURC 不受报告 grid 影响。 | decile 稳定但隐藏 10% 间结构；梯形积分非 empirical exact area，一个 DN outcome tolerance 可能把真实聚合差异判 flat。 |

## 3. Machine precedence、curve shape 与科研 verdict

按下列顺序短路，后级不得覆盖前级：

1. identity/hash/count invariant、`T=0`、cos_i/residual missing/nonfinite/out-of-domain 任一失败 →
   `protocol_error`，停止该执行；`curve_shape=null`、`risk_proxy_verdict=null`，不写科研结论。
2. fold-safe gate 失败、`D=0`、`S=0` 或 `N_scored < pack minimum` →
   `risk_proxy_verdict=not_evaluable_insufficient_scored_support`，shape=null。
3. `score_range <= tau_score`、`unique_proxy_values`、admissible points、canonical reachable grid points
   或 AURC `J/span` 未达本包 minimum →
   `risk_proxy_verdict=not_evaluable_score_degenerate`，shape=null。
4. 否则对 verdict 点列每个 `delta=R_b-R_a`：`delta>tau_outcome => +`；
   `abs(delta)<=tau_outcome => 0`；`delta < -tau_outcome => -`。机器谓词闭合：
   - 全 0 → `curve_shape=flat`
   - 有 + 且无 − → `curve_shape=order_consistent`
   - 有 − 且无 + → `curve_shape=order_inverted`
   - 同时有 +/− → `curve_shape=mixed`
5. PF3 科研 verdict 映射闭集：
   - `order_consistent -> descriptive_ordering_signal`
   - `order_inverted -> directionally_adverse`
   - `flat | mixed -> descriptive_non_discriminative`

最终 `risk_proxy_verdict` 闭集恰为
`{not_evaluable_insufficient_scored_support, not_evaluable_score_degenerate,
descriptive_ordering_signal, directionally_adverse, descriptive_non_discriminative}`。
必须同时保留 curve_shape；`mixed` 只能表述为“无一致方向”，不得表述为“统计无信号”。

**推荐 M2**：共同展示 grid 与 exact AURC 分离，且 per-stratum curves 可直接审计。但 5%、三点、
双层 271 与两个 1e-12 tolerance 全是等待 Elara 批准的新治理选择，不是 A 回执或上游定理。

## 4. 所有者回执格式

请回复且只回复其一：`APPROVE M1 — exact-minimal-v2`、
`APPROVE M2 — guarded-5pct-v2`、或 `APPROVE M3 — sensor-decile-v2`。
回执前不得创建 frozen risk-proxy protocol/config、不得标记 activation ready，也不得读取任何
Stage 7.3 residual／alpha／score 结果数值。
