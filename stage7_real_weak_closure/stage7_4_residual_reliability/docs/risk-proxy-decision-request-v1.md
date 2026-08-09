# Stage 7.4｜risk-proxy decision request v1

- **状态：** `decision_required`（不是协议、配置或执行授权）
- **节点生命周期：** `planned`
- **审计日期：** 2026-08-09（Asia/Shanghai 自然日；不声明日内时刻或跨文件先后）
- **结果盲边界：** 本轮只读冻结协议、schema／manifest 的结构与质量因子、7.2／7.3
  规则及源码／测试、7.4 既有 planned-state 文件；未打开 Stage 7.3 的 residual／alpha
  结果或报告，未运行 Stage 7.3 fitter。

## 裁决请求

**冻结上游不能唯一编译出一个 risk proxy。** 架构明确把 reliability 与 risk–coverage
精确定义留给独立节点合同（`docs/architecture.md:16,199`）；Stage 7.0 只冻结 residual、
三项单元指标与像元 coverage 分母，并明确没有连续 reliability 或 risk–coverage 排序／曲线
（`baseline_spec.md:24-31`；`evaluation_protocol.md:35-57`）；Stage 7.1-R 只交付支持原语，
不定义 confidence（`validity-support-schema-v1.json:2-5`）；Stage 7.2 的 `Mconf` 只是二值
`geometry_visibility` 单因子，且禁止与其他质量因子合成为总 confidence
（`mconf-subprotocol-v1.md:27-49,114-118`）；Stage 7.3 只把报告单元唯一化为
`acquisition × band × fold`（`core-topology-subprotocol-v1.md:70-87`）；现有 7.4 分层协议也
显式排除 risk proxy、coverage 与阈值定义（`stratification-subprotocol-v1.md:102-105`）。

因此仍需所有者选择**代理含义／粒度、方向与变换、tie 规则、curve coverage 单位与分母、
unsupported 处理及跨单元聚合**。请在以下互斥方案中只选一个：

| 方案 | 冻结内容 | 代价与可声称边界 |
|---|---|---|
| **A. 几何余量诊断（推荐）** | 对每个 `acquisition × band × fold`，仅在 `base_valid_land ∧ Mconf=1` 内令 `risk_proxy = 1 − cos_i`；按低值先接纳，完全相同值整组进入；每个接纳集合的 risk 为其 MAE（平均绝对 residual），coverage 分母仍为该 core 的全部 `base_valid_land`，unsupported 留在分母且绝不计作低误差；禁止跨单元像元池化。 | 需从冻结输入与 fold-safe alpha 复算逐像元 residual（7.3 未保存逐像元产物）。只检验 self-shadow 几何余量，不是 calibrated confidence；不覆盖投射阴影等缺口；跨 acquisition 的 μ 差异混入太阳几何，故只报逐单元曲线与描述性汇总。 |
| **B. 二值 support-only 诊断** | 在每个 core 的 `base_valid_land` 上，直接沿用 Stage 7.0：`supported` 的 risk level 为 0，`unsupported_by_direct_only` 为 1；两类各自整组进入。residual 只在 supported 组计算，unsupported 保持 `not_scored`；coverage 分母仍是全部 `base_valid_land`，并报告既有 `support_coverage`。 | 这是新增选择最少的方案，但只有一个可评分 tie 组，不能在 supported 内排序，所谓 curve 退化为支持边界账本；只说明 availability，不说明连续或 calibrated reliability。 |
| **C. 延后 reliability** | 当前只做冻结分层与 support／deprivation 账本；等新的 `model_adequacy`、`output_uncertainty` 或 calibration-leverage 子协议在独立 planned-state 合同中结果盲冻结后，再定义 risk proxy。 | Stage 7.4 的 risk-proxy／risk–coverage 路径保持阻塞，但避免用 geometry、availability 或未经校正的拟合信息量冒充模型可靠性。需要新增上游协议与产物。 |

**推荐 A**，仅作为最小的、可证伪的 **geometry-risk diagnostic**：它使用已冻结且结果无关的
连续原语，不引入权重或跨因子合成，并保持 Stage 7.0 的像元 coverage 分母与 7.4 已批准分层
一致。批准 A 同时意味着接受其不能被命名为总 reliability／confidence。若目标必须是具有模型
可靠性语义的代理，应选 **C**，不要把 A 或 B 升格。

候选覆盖说明：冻结的 **binary support** 就是 B 的同一谓词，不另造第四个名字；
`1 − support_coverage` 只能作为 B 的单元级账本摘要，不能冒充另一条逐像元排序。
**alpha-leverage** 也可实现，但 `1/Σμ²`、像元 leverage 与带空间有效样本校正的版本并不等价；
Stage 7.2 还明确说明原始 `Σμ²` 会因高度空间自相关而高估信息量
（`calibration-contract-v1.md:47-63`）。它衡量标定参数稳定性而非输出误差，故当前归入 C，
须先裁决粒度、校正与语义后才可入围。标量合成 `Mconf + Msource/Mqa + …` 同样不列为主选：
Stage 7.2 已禁止把 `Mconf` 与其他质量因子合成为总 confidence；若要走该路，须先修订上游。

## 所有者回执格式

请回复且只回复其一：`APPROVE A — geometry-risk diagnostic`、
`APPROVE B — binary support-only diagnostic`、或 `APPROVE C — defer reliability`。
回执前不得创建 frozen risk-proxy 协议／配置，不得读取任何 residual／alpha／score 数值。
