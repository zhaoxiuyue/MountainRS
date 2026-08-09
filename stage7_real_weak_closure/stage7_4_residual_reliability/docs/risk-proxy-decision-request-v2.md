# Stage 7.4｜risk-proxy decision request v2

- **状态：** `decision_required`（不是协议、配置或执行授权）
- **节点生命周期：** `planned`
- **前任：** `docs/risk-proxy-decision-request-v1.md`，SHA-256
  `05e6bf3699bc8e0a7482ae56a66da17626d0721d1fd955add70f0470a7d335b0`
- **supersedes：** v1 的其余唯一性结论与 A/B/C 高层选择不变；v2 只关闭 B 的接纳歧义，
  并把 A/B 共用的 fold-safe unit gate 写成不可绕过的不变量。v1 字节未改。
- **审计日期：** 2026-08-09（Asia/Shanghai 自然日；不声明日内时刻或跨文件先后）
- **结果盲边界：** 未打开 Stage 7.3 residual／alpha 结果或报告，未运行 Stage 7.3 fitter。

## 结论与共同 unit gate

冻结上游仍然**不能唯一编译** risk proxy：它唯一给出 residual、支持分母、质量因子身份、
fold-safe 拟合规则与报告单元，但没有唯一给出代理含义、粒度、变换、排序、tie、接纳单位或
跨单元汇总。所有者仍须在下列 A/B/C 中只选一个。

若选择 **A 或 B**，必须先逐 `acquisition × band × fold` 应用同一 fail-closed gate：

```text
unit_gate_pass := fold_safe_alpha_state == fitted AND scored_pixel_count > 0
```

- gate 失败时，整个 unit 必须 typed `not_scored`；顶层原因只能是
  `unsupported_calibration` 或 `no_supported_pixel_in_core`。前者还必须保留既有明细原因
  `calibration_support_below_minimum` 或 `nonpositive_mu_squared_denominator`。不得回退
  reference alpha、默认值、插补、截距或漫射替代。
- gate 失败的 unit 不产生 residual、MAE 或 curve 点，但仍保留 acquisition/split/band/fold
  身份、holdout-core coverage 账本、reason 及证明未修补的 fallback receipt；仍计入冻结机会 universe、unit 总数及
  `not_scored_unit_count`，不得改变 `base_valid_land` 分母，也不得从账本或汇总静默消失。
- 只有 gate 通过的 unit 才进入 A 或 B 的代理计算；任何汇总必须同时报告 passed/not_scored
  数量与 not_scored reason 分解。

## 互斥方案

| 方案 | 冻结内容 | 代价与可声称边界 |
|---|---|---|
| **A. 几何余量诊断（推荐）** | 对 gate 通过的每个 unit，仅在 `base_valid_land ∧ Mconf=1` 内令 `risk_proxy = 1 − cos_i`；按低值先接纳，完全相同值整组进入；每个接纳集合的 risk 为其 MAE。coverage 分母始终为该 core 的全部 `base_valid_land`；unsupported 留在分母但不进入 MAE，禁止跨单元像元池化。 | 需从冻结输入与 fold-safe alpha 复算逐像元 residual。只检验 self-shadow 几何余量，不是 calibrated confidence；不覆盖投射阴影等缺口；跨 acquisition 的 μ 混入太阳几何，故只报逐 unit 曲线与描述性汇总。 |
| **B. 二值 support-only 诊断** | 对 gate 通过的 unit，`supported` 是唯一被接纳、唯一贡献 residual/MAE 的 tie 组。`unsupported_by_direct_only` 是**永久 abstention**：不赋予可接纳的 `threshold=1`，任何阈值下都不得进入 accepted set，绝不贡献 MAE。唯一可评估点为 `coverage = support_coverage = supported_pixel_count / base_valid_land_count`，risk 为 supported 组 MAE。 | 这是新增选择最少的方案，但没有 supported 内部排序，所谓 curve 退化为一个可评估点。unsupported 仍须完整留在 coverage 分母与账本中；本方案只说明 availability，不说明连续或 calibrated reliability。 |
| **C. 延后 reliability** | 当前只做冻结分层与 support/deprivation 账本；等新的 `model_adequacy`、`output_uncertainty` 或 calibration-leverage 子协议在独立 planned-state 合同中结果盲冻结后，再定义 risk proxy。 | risk-proxy/risk-coverage 路径保持阻塞，但避免用 geometry、availability 或未经校正的拟合信息量冒充模型可靠性。需要新增上游协议与产物。 |

**推荐 A**，仅作为最小、可证伪的 `geometry-risk diagnostic`：它使用冻结且结果无关的连续
原语，不引入权重或跨因子合成，并保持 Stage 7.0 的 coverage 分母。批准 A 同时意味着接受
它不是总 reliability/confidence；若目标必须具有模型可靠性语义，应选 C。

候选覆盖不变：冻结 binary support 已完整归入 B；`1 − support_coverage` 只是 B 的账本摘要，
不是另一条逐像元排序。alpha-leverage 的 `1/Σμ²`、像元 leverage 与空间有效样本校正版并不
等价，且原始 `Σμ²` 会因空间自相关高估信息量，故归入 C，须先另立子协议。把 `Mconf` 与
`Msource/Mqa` 等标量合成仍不入围：Stage 7.2 禁止将其合成为总 confidence。

## 所有者回执格式

请回复且只回复其一：`APPROVE A — geometry-risk diagnostic`、
`APPROVE B — binary support-only diagnostic`、或 `APPROVE C — defer reliability`。
回执前不得创建 frozen risk-proxy 协议／配置，不得读取 residual／alpha／score 结果数值。
