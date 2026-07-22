# Stage 6.5.3-B｜方法与评价合同草案

- **状态：** `proposal_pending_user_confirmation`。本文件不是 Node Contract，也不授权执行 hard_mask、soft_weight 或 bounded_scene_constant_diffuse。
- **适用范围：**只限 Stage 6.5.3-B 的 Clean A lit/control 与 Shadow-risk B shadow/near-zero 压力测试。它不验证完整 L0–L5，不形成反演真误差结论，也不推断真实漫射、sky-view、邻坡散射或大气机制。
- **空间边界：**正式执行前只可使用 `proposed_fold_manifest.json` 中经确认的 8,130 m buffered leave-region-out folds。每折是描述性挑战；其 calibration 区可重叠，不能当作独立统计重复。

## 1. 通用记号、输入和训练边界

对 scene `s`、band `b∈{B4,B5}`、fold `f`、像元 `p`：

```text
rho_obs(s,b,p) = Landsat L2 SR B4 或 B5 的观测 surface reflectance（无量纲）
mu(p)          = max(cos_i(p), 0)
tau            = 0.1
w_k(p)         = sigmoid(k * (cos_i(p) - tau))
```

输入只限正式 alias 所解析的 B4、B5、QA_PIXEL、metadata、cos_i、Architecture source，以及 Stage 6.5.2-A/B 的 prior reports。canonical analysis domain 仍由本节点 config 重新生成：QA_PIXEL bits 0–5 clear、B4/B5/cos_i 有效且 B4/B5 位于 `[-0.05,1.0]`；water bit 7 从 land 指标排除。`shadow=cos_i<=0`、`near_zero=0<cos_i<=0.1`、`lit=cos_i>0.1`。

任何可拟合参数都只由当前 fold 的 calibration land 估计。holdout core、其 buffer，及 holdout 中的 `rho_obs` 均不得参与参数、边界、模型选择或阈值选择。每个 `(s,b,f)` 是独立的 calibration-only 拟合实例；这不允许任何逐像元、逐块或依据 holdout 调整的自由参数。

`alpha(s,b,f)` 表示 scene×band×fold 共享的直接光 gain/albedo-like scalar，并继承 Stage 6 toy 中 sigmoid parameterization 的物理范围：`0<=alpha<=1`。它是前向 baseline 的受限比例参数，不是已验证的地表真 albedo 产品。

## 2. hard_mask 合同

**精确输入。** canonical base-valid land 中的 `rho_obs` 与 `cos_i`；QA/water 规则同上。仅以 `C_hard = calibration ∩ {cos_i>0.1}` 训练。

**前向式与拟合。**

```text
rho_hat_hard(s,b,p) = alpha_hard(s,b,f) * mu(p)

alpha_hard = clip_[0,1]( sum_{p in C_hard}(mu(p)*rho_obs(s,b,p))
                          / sum_{p in C_hard}(mu(p)^2) )
```

若分母为零或 `C_hard` 为空，该 `(s,b,f)` 是 execution blocker，不能以替代参数、邻折或 holdout 补足。

**输出与 unsupported。** `cos_i<=0.1` 的像元固定标为 `unsupported_by_hard_mask`：不拟合、不在 hard-mask residual/risk 成功集合中，也不能因被排除而被记为低风险成功。hard_mask 的最大可覆盖比例因此可能低于 1；coverage 分母仍是所有 base-valid land，而不是只取 lit。

## 3. soft_weight 合同

**精确公式。** Stage 5/6 已有 observability 形式被冻结为：

```text
w_k(p) = sigmoid(k * (cos_i(p) - 0.1))
rho_hat_soft(s,b,p) = alpha_soft(s,b,f;k) * mu(p)

alpha_soft(k) = clip_[0,1]( sum_{p in calibration}(w_k(p)*mu(p)*rho_obs(s,b,p))
                             / sum_{p in calibration}(w_k(p)*mu(p)^2) )
```

主配置是 `k=30`；这是继承 Stage 5/6 的经验基线，不是真理值。`k∈{15,30,60}` 仅是同一 soft_weight 机制的预注册敏感性检查，不能计作额外三种方法，也不能用 holdout 表现选择其中一个。

**权重进入何处。** `w_k` 进入 calibration 的加权平方前向损失，等价于上式闭式解；在 holdout 它只作为 reliability/ranking score。主要 holdout risk 一律以未加权 `|rho_hat-rho_obs|` 计算，不能用低 `w_k` 把高残差折减为成功。若保存加权诊断，它必须明确为次要诊断，不能替代主要风险统计。

`w_k` 是照明可观测性排序分数，不是正确概率、校准概率、云质量概率或阴影真值概率；shadow 与 near_zero 仍须按 canonical 分区单独报告。

## 4. bounded_scene_constant_diffuse 合同

**精确方程与单位。**

```text
rho_hat_diffuse(s,b,p) = alpha_diffuse(s,b,f) * mu(p) + d(s,b,f)
```

`rho_hat`、`alpha`、`d` 都以无量纲 surface-reflectance 标度表达；`mu` 无量纲。`d` 是每个 scene×band×fold 的单一、空间常数 additive term。一个 fold 内的所有 calibration 与 holdout 像元共享同一个 `d`；严禁逐像元 diffuse、逐像元自由残差项、按 shadow/near_zero 区分别拟合，或从 holdout 重估 `d`。

给定一个预先确认的边界 `0<=d<=D(s,b,f)`，参数由 calibration-only 的 `k=30` 加权最小二乘共同拟合：

```text
(alpha_diffuse, d) = argmin_{0<=alpha<=1, 0<=d<=D}
  sum_{p in calibration} w_30(p) * (rho_obs(s,b,p) - alpha*mu(p) - d)^2
```

这是场景级常数化近似，不是可识别的真实 sky-view、邻坡反射、地形遮挡、大气路径辐射、BRDF 或散射模型。即使获得改善，也不能把该项解释成真实 diffuse 机制量。

### 两个 calibration-only diffuse 边界候选

两案均不预读 holdout，并共同禁止逐像元自由度。它们只允许从当前 fold 的 calibration land 求解；若必要集合为空，返回 blocker，不能回填默认数值。

| 候选 | 数学边界与单位 | calibration-only 依据与共享 | 防止吸收 residual | 已知物理缺项与可证伪范围 |
|---|---|---|---|---|
| **D1：geometry-anchored（推荐）** | `D_1(s,b,f)=tau*alpha_diffuse(s,b,f)`，即 `0<=d<=0.1*alpha`；`d` 为 reflectance，`d/alpha` 为无量纲 illumination-equivalent。 | `tau=0.1` 是本节点已冻结的 near-zero/lit 分界；每个 scene×band×fold 仅一个 `alpha,d`。只由 calibration 加权目标求解。 | 上界把常数项限制为在 observability 门槛 `mu=tau` 处不超过直接项；没有像元/区域自由项，也不以 holdout 调边界。 | 缺 sky-view、邻坡散射、遮挡、BRDF、大气与真实谱间关系。若无改善，只能证伪“当前以 `d/alpha<=0.1` 限制的 scene-constant 参数化”在本节点可验证改善。 |
| **D2：calibration-envelope（保守备选）** | `D_2(s,b,f)=min(0.1*alpha_diffuse, max(0, min_{p in calibration∩lit} rho_obs(s,b,p)))`；`d` 为 reflectance。 | 第二项只使用 calibration lit 观测，确保拟合常数项不超过任一 calibration lit 观测；仍是 scene×band×fold 单一参数。 | 同时受 D1 几何限制与 calibration lit non-negative envelope 约束；无逐像元参数、无 holdout。 | 同样缺所有真实辐射传输项；且可能被单个低值/噪声观测压至零。若无改善，只能证伪这个更保守的场景常数近似。 |

**推荐 D1。** 它只使用已冻结的 `tau=0.1` 与参数单位关系，避免为边界另造数值；比 D2 不易被单一低 reflectance 像元偶然钳死。D2 仍保留为用户可选的更保守方案。两案不得通过拟合或 holdout 比较来选择，必须由用户在执行前确认其一。

## 5. 评价合同草案（定义，不计算结果）

**Residual baseline。** 对已评分像元，

```text
r(s,b,p) = rho_hat(s,b,p) - rho_obs(s,b,p)
abs_r     = |r|
```

单位为无量纲 Landsat surface reflectance；`r>0` 表示该指定 forward baseline 过预测，`r<0` 表示低预测。它是 model–observation residual，绝不是反演真误差、地表真 albedo error 或机制真实性证明。

**Reliability 与 coverage。** reliability 是固定的排序键：hard_mask 为 lit-support indicator（unsupported 无键）；soft_weight 与 diffuse 为 `w_k`（主值 `k=30`）。把可评分像元按 reliability 降序、再按稳定像元索引升序排序；每个可达前缀的 coverage 为：

```text
coverage = scored_selected_base_valid_land_pixels / all_base_valid_land_pixels_in_holdout_core
```

water 不在分母；hard_mask 的 unsupported 仍留在分母并单列，因此不能凭排除而提高 coverage。主要 risk 统计为所选前缀的 band-specific `median(abs_r)` 与 `p90(abs_r)`；每个 fold、每个 band、每个 canonical 分区单独报告。低 reliability 或低 coverage 从不是自动低 risk。

**Unsupported / prior_only。** hard_mask 的 unsupported 必须分别计数、报告来源与 coverage 影响；不与 QA、water 或其他失效原因合并。既有 `qa_valid_mask`、`shadow_mask`、`near_zero_mask`、`confidence` 只属 `prior_only` cross-check：它们既不重写 canonical mask，也不充当正式 residual、reliability 或评分输入。

**样本职责与汇总。** A 只承担 lit/control；B 承担 shadow/near-zero stress。报告先逐 fold、逐 band、逐分区给出值；允许跨五折做纯描述性的 median/range，但不得输出像元级 p-value、置信区间，或宣称五个重叠 calibration folds 是五个独立区域。

## 6. 本草案的最小待确认项

1. 在正式实验前，确认使用 **D1（推荐）** 或 **D2（更保守）** 的 diffuse 上界；确认后不得依据 holdout 修改。
2. 单独授权正式机制执行与 holdout 评分；本次 proposal 本身不构成该授权。

## 7. 依据（只读审计）

- `docs/architecture.md`（V3 canonical architecture）。
- `stage5_gradient_friendly_model/scripts/gradient_friendly_forward_check.py` 与其报告：`hard_observed=albedo*max(cos_i,0)`、softplus forward toy、`sigmoid(k*(cos_i-0.1))` observability。
- `stage6_differentiable_inversion_toy/scripts/differentiable_albedo_inversion_toy.py` 与其报告：bounded sigmoid albedo toy 与 weighted forward loss。
- Stage 6.5.2-A/B local checks、当前 Stage 6.5.3-B config/executor、以及 C5-D1A geometry-only audit。

本草案未读取或生成任何正式机制结果、residual、risk–coverage 曲线或方法排名。
