# Stage 7.4｜Risk-proxy protocol v1

- **状态：** `frozen`
- **方法身份：** `A_geometry_margin_diagnostic / M2_guarded_5pct_v3`
- **冻结阶段：** Stage 7.4 已激活后的第一项写入动作；冻结前只进行了身份、状态、receipt、
  路径、哈希与目标不存在性只读检查，未读取任何 Stage 7.3 residual／alpha／score 结果值。
- **冻结日期：** 2026-08-09（Asia/Shanghai 自然日；不主张日内时刻）
- **机器同伴：** `configs/risk-proxy-config-v1.json`
- **权威 preflight：** `evidence/preflight-manifest-v8.json`，SHA-256
  `872146918cd83017d7a31a110c2ab921930f93c6b2a7c0e5c520c97447da966a`
- **方法裁决页：** `docs/risk-proxy-method-pack-decision-request-v3.md`，SHA-256
  `41e29c75212c8e622a93143399bf119271fed34620202c7d2eff934f7325a861`
- **高层 A 裁决页：** `docs/risk-proxy-decision-request-v2.md`，SHA-256
  `1d792bb402fc45faa5c5452dbe60245f39d99122afb3a507a366082e6775c9ab`

## 0. 权限、时序与解释边界

本协议绑定 PF3 project `proj_6cbeea3266ff`、route `rt_f634f0ab72fb`。冻结前只读现场为
route revision `69`，Stage 7.3 `nd_38d128c40d90=done`，Stage 7.4
`nd_095e71a9eccf=active`。稳定事件链为：

1. M2 决策 `rc_e47f614a7190`：`65→66`；
2. ready 写回 `rc_8f3395bf3f10`：`66→67`；
3. Stage 7.3 关闭 `rc_9fc3d051cf7c`：`67→68`；
4. Stage 7.4 激活 `rc_b9bb7bb94549`：`68→69`。

上述 receipts 均已读回且 `undoneBy=null`。本次冻结以 live revision 等于 activation receipt 的
`afterRevision=69` 为闸门；历史 revision 66 只证明 M2 决策事件，不是运行时 current-revision
常量。项目规则 `pr_d4a37fa568df` revision 1 与 Stage 7.4 contract receipt
`rc_925cc8885871` 继续有效。

本协议只定义当前单 ROI、18 景、B4/B5、五个非独立 spatial folds 的描述性 geometry-risk
diagnostic。它不是 calibrated confidence、概率、统计显著性、跨域泛化或独立确认；已暴露 test
不得再称 independent confirmation。`reconstruction_quality`、`output_uncertainty`、cast shadow、
horizon/view occlusion、disocclusion 与 geometry-instability 均为 `not_evaluated`。

## 1. Unit gate、终态与禁用 fallback

最小 unit 是 `acquisition × band × fold`。逐 unit 先执行：

```text
unit_gate_pass := fold_safe_alpha_state == fitted AND scored_pixel_count > 0
```

机器 gate state 闭集为 `{scored, not_scored}`。失败时顶层 reason 闭集恰为：

- `unsupported_calibration`；其 detail reason 闭集为
  `{calibration_support_below_minimum, nonpositive_mu_squared_denominator}`；
- `no_supported_pixel_in_core`。

输出 `unit_terminal_category` 闭集为
`{scored, unsupported_calibration, not_scored_no_supported_pixel}`，由 gate state/reason 唯一映射。
禁止 fallback 闭集为 `{reference_alpha, default_alpha, imputation, intercept,
diffuse_substitution, holdout_derived_repair}`。失败 unit 不产生 residual、MAE 或 curve point；但必须
保留 acquisition/split/band/fold、机会像元与完整 core coverage 账本、顶层/detail reason 和逐项
`fallback_used=false` receipt，并进入 unit totals 与 `not_scored_unit_count`。

## 2. Scoreable mask、support 与永久 abstention

```text
scoreable_mask = core AND base_valid_land AND Mconf == 1
Mconf == 1     iff cos_i is valid AND cos_i > 0.1
risk_proxy     = 1 - cos_i
acceptance     = ascending risk_proxy, low first
```

`Mconf` 只表示 `geometry_visibility` 单因子，是自阴影许可量，不得编译成总 confidence。core 内
`base_valid_land` 且 finite `cos_i<=0.1` 的像元标为 `unsupported_by_direct_only`：它在所有
operating points 永久 abstain，留在 base-valid 分母与账本中，但永不进入 accepted count、
residual 或 MAE。禁止用 oracle residual 排序。

## 3. Residual 与 risk

沿用 Stage 7.0，不重拟合模型：

```text
mu       = max(cos_i, 0)
rho_hat  = fold_specific_alpha * mu
residual = rho_hat - rho_obs
risk     = accepted_set_MAE
         = mean(abs(residual_i)) over accepted scored pixels only
```

`rho_hat`、`rho_obs`、residual、MAE 与 AURC risk 均使用 dimensionless scaled surface-reflectance
units，不是 raw DN。risk 的来源是高层 Option A 裁决页与 Stage 7.0 MAE；M2 只冻结 operating
points、guards、tolerances、AURC 与 verdict sequence，不重新定义 risk。

## 4. Missing、domain、tie 与 protocol error

对每个 curve scope，在任何 point filtering/grid 前，以该 scope 全部 finite scored supported
pixel 的逐像元原始 proxy 计算：

```text
s_min       = min(raw risk_proxy_i)
s_max       = max(raw risk_proxy_i)
score_range = s_max - s_min
```

min/max 前不得舍入、量化、分箱或折叠 tie records。随后 exact tie 只按冻结存储 dtype 解码后的
bit pattern 相等识别；无 epsilon tie、四舍五入或 secondary sort，tie group 整组原子接纳。
数值相等但 bit pattern 不同且会需要 secondary order 时，必须以
`numeric_equal_bit_distinct_proxy_order_undefined` fail closed。

以下 reason 闭集均为 `protocol_error`，优先于科研 verdict 并停止整次执行：

- `identity_or_hash_mismatch`
- `zero_core_total_pixel_count`
- `count_order_violation`
- `base_valid_land_cos_i_missing`
- `base_valid_land_cos_i_nonfinite`
- `base_valid_land_cos_i_outside_minus1_plus1`
- `mconf_cos_i_inconsistency`
- `supported_residual_nonfinite`
- `numeric_equal_bit_distinct_proxy_order_undefined`
- `strata_partition_failure`
- `coverage_identity_failure`
- `fixed_grid_invariant_failure`
- `output_reconciliation_failure`

cos_i 的 protocol-error 检查域仅为 core 内 `base_valid_land`；core 外或非 base-valid 像元不因本
协议报错。禁止 missing imputation。protocol_error 时 `curve_shape=null`、
`risk_proxy_verdict=null`，不得降格为 abstention 或 not-evaluable。

## 5. Strata、curve scopes 与角色

五层闭集、互斥且穷尽 finite `cos_i∈[-1,1]`：

| stratum | predicate | scoring |
|---|---|---|
| `self_shadow` | `cos_i <= 0` | `by_design_unsupported` |
| `near_zero` | `0 < cos_i <= 0.1` | `by_design_unsupported` |
| `mu_band_low` | `0.1 < cos_i <= 0.4` | scored |
| `mu_band_mid` | `0.4 < cos_i <= 0.7` | scored |
| `mu_band_high` | `0.7 < cos_i <= 1.0` | scored |

逐 acquisition 断言 partition；失败即 protocol_error。分箱是中性 μ 分段，不主张物理风险区，
跨 acquisition 不得表述为不同地形风险的直接比较。

curve scope 闭集为
`{unit_all_scored, mu_band_low, mu_band_mid, mu_band_high}`；前者 role=`primary`，后三者
role=`secondary`。四 scope 独立应用 support/degeneracy gate 并产生 scope-local verdict；禁止合成
unit-level 或 node-level verdict。

## 6. Counts、coverage 与 partition identities

逐 unit 定义 `T=core_total_pixel_count`（冻结 core 的全部机会像元）、
`D=base_valid_land_count`；逐 scope 定义 `S=scored_pixel_count`、第 j 点
`A_j=accepted_pixel_count`。先以整数断言：

```text
0 <= A_j <= S <= D <= T
```

canonical coverage：

```text
evidence_support_coverage       = D / T
scoring_coverage                = S / D
selective_prediction_coverage_j = A_j / D
acceptance_given_scored_j       = A_j / S
```

`selective_prediction_coverage` 是唯一 canonical 字段。兼容短名 `selective_coverage` 只有同时带
`alias_of=selective_prediction_coverage` 且 value/null 完全相同时才允许。

- `T=0`：`protocol_error_zero_core_total`；
- `T>0,D=0`：unit typed not_scored；evidence coverage=0，其余 D-based ratio=null，reason=
  `zero_base_valid_land_denominator`；
- `D>0,S=0`：scoring/selective-prediction coverage=0，acceptance-given-scored=null，reason=
  `zero_scored_denominator`。

浮点输出前，以整数交叉乘法验证：

```text
evidence_support_coverage * scoring_coverage = S/T
evidence_support_coverage * selective_prediction_coverage_j = A_j/T
selective_prediction_coverage_j = scoring_coverage * acceptance_given_scored_j  (S>0)
```

令 h 为三个 scored strata，必须先断言 `sum_h(S_h)=S_unit_all`；D>0 时无条件断言
`sum_h(stratum_scoring_coverage_h)=unit_all_scored.scoring_coverage`。只有 h 存在
`A_terminal=S_h` 的 terminal admissible point 时才报告
`max_selective_prediction_coverage_h=S_h/D`；否则该 max=null 且不进入 max 等式。
禁止跨 band 相加或跨 unit 像元池化。

## 7. M2 support/resolution guards 与 5% grid

每个 scope 必须同时满足：

- `N_scored >= 271`；
- 每个 admissible exact point `accepted_n >= 271`；
- `unique_proxy_values >= 3`；
- `admissible_exact_points >= 3`；
- 去重 `canonical_reachable_grid_points >= 3`。

271 只是 governance guard，不是统计阈值、effective n 或独立样本数。

目标 q 是 exact rationals `k/20, k=1..20`。admissible exact points 按 coverage 升序记
`c_j=A_j/D, j=1..J`。全部比较只用 `20*A_j <= k*D` 等整数交叉乘法：

```text
J=0              -> all q unreachable / below_min_accepted_support
J>0 and q<c_1    -> unreachable / below_min_accepted_support
J>0 and q>c_J    -> unreachable / above_max_reachable_coverage
c_1<=q<=c_J      -> j*=max{j:c_j<=q}; q=c_J maps to J before deduplication
```

每条 grid record 字段闭集为
`target_q/status/exact_point_index/selective_prediction_coverage/reason/canonical_target_q`；status
闭集 `{reachable,unreachable,duplicate}`。映射到同一 j* 的最小 q 是唯一 reachable，reason=null，
canonical_target_q=self；其余是 duplicate，reason=`duplicate_exact_point`，保留 exact index、
coverage 并指向最小 q。unreachable 的后三个 identity/coverage/canonical 字段为 null；reason 闭集
`{below_min_accepted_support, above_max_reachable_coverage}`。禁止拆 tie、插值、超调和
forward-fill。

## 8. Tolerances、AURC、shape 与 verdict

```text
tau_score   = 1e-12 + 1e-12*max(abs(s_min),abs(s_max))
tau_outcome = 1e-12 + 1e-12*max(abs(R_a),abs(R_b))
```

`score_range<=tau_score` 在 point filtering/grid 前短路为 score degeneracy。AURC 使用全部
coverage-ordered admissible exact points（每点 accepted_n>=271），5% grid 不参与积分：

```text
area       = sum_{j=1}^{J-1} R_j*(c_{j+1}-c_j)
span       = c_J-c_1
normalized = area/span
```

需本包 admissible-point minimum 且 `span>0`；只积分 `[c_1,c_J]`，报告 span，不从 0、向 1 或
abstention 区外推。

machine precedence 逐 scope 短路：

1. protocol_error：停止执行，无科学 verdict；
2. unit gate 失败、D=0、S=0 或 `N_scored<271`：
   `not_evaluable_insufficient_scored_support`；
3. score range、unique/admissible/canonical points 或 AURC span 退化：
   `not_evaluable_score_degenerate`；
4. 否则在 coverage-ordered canonical reachable 5% verdict sequence 上，对相邻
   `delta=R_b-R_a` 判：`delta>tau_outcome => +`、`abs(delta)<=tau_outcome => 0`、
   `delta<-tau_outcome => -`。

shape 闭集与映射：全 0=`flat`；有 + 无 −=`order_consistent`；有 − 无 +=`order_inverted`；
同时有 +/−=`mixed`。PF3 verdict 闭集恰为：

- `not_evaluable_insufficient_scored_support`
- `not_evaluable_score_degenerate`
- `descriptive_ordering_signal`
- `directionally_adverse`
- `descriptive_non_discriminative`

`order_consistent -> descriptive_ordering_signal`；`order_inverted -> directionally_adverse`；
`flat|mixed -> descriptive_non_discriminative`。必须保留 shape；mixed 只能称“无一致方向”，不得称
“统计无信号”。not-evaluable reason 采用 config 中冻结的闭集并逐 scope 保留。

## 9. Aggregation 与 frozen outputs

连续量先逐 `acquisition × band × fold × curve_scope` 形成；每个
`acquisition × band × curve_scope` 内只报 fold median/range；跨 acquisition 每景等权，仍只报
median/range。分类键为 `band × curve_scope × PF3 risk_proxy_verdict`，五态分别计数并保留
not-evaluable reasons。禁止 pixel pooling 代替 unit、pass/fail 合并、排名、effective n、p 值、
置信区间或显著性声称。

实验输出身份闭集：

| logical output | exact path |
|---|---|
| `unit_status_ledger` | `evidence/risk-proxy-unit-status-ledger-v1.json` |
| `stratum_table` | `outputs/risk-proxy-stratum-table-v1.json` |
| `risk_curve_table` | `outputs/risk-proxy-risk-curve-table-v1.json` |
| `aggregation_table` | `outputs/risk-proxy-aggregation-table-v1.json` |
| `reconciliation_manifest` | `evidence/risk-proxy-reconciliation-manifest-v1.json` |
| `scientific_report` | `reports/residual-reliability-report-v1.md` |

每个 JSON 的 schema、row key 与 required fields 以 machine config 为准。reconciliation 必须覆盖
member/hash、mask、unit terminal state、三种 coverage denominator、fold ledger、scope verdict 与
全部完成产物 hash。任何 drift、时间顺序失真或 reconciliation 失败都是 protocol_error，不是科学
负结果。

## 10. Runtime stop boundary

任一权威 hash、PF3 receipt/identity、active state、live revision、input identity、closed set、整数／
有理数不变量或 cross-artifact 一致性失败即停机。目标或未来 output 已存在时不得覆盖；不得静默
新增版本、默认、fallback、阈值、score、grid、积分、verdict 或 output category。冻结完成后仍未
授权本窗口读取结果或运行实验；本次动作仅冻结本协议及其 machine config。
