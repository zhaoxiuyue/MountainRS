# Stage 6.1｜可微反演 Toy Model + 置信度字段报告

## Stage 6 目标

本阶段构建一个最小可微反演 toy model：已知 synthetic `cos_i` 与 synthetic observed brightness，通过梯度下降反演 `albedo`，同时输出 observability confidence 与 uncertainty proxy。

## 为什么本阶段是 L3 弱闭环

Stage 6 已经从 L2 正向观测算子进入 L3 反演思维：模型不只计算观测亮度，而是用观测亮度反推潜在参数 `albedo`。但它仍然是 synthetic toy，不使用真实 Landsat，不包含真实大气、BRDF、传感器响应、地表异质性或多时相太阳几何，因此只能称为 L3 弱闭环。

## 为什么不用真实 Landsat

当前 Landsat 是 2023-2024 median composite，不是单日观测。单日地形辐射校正需要影像获取时刻的太阳几何、真实地表 BRDF/阴影/大气条件。把 composite 直接塞进单日物理反演会制造假的物理对应关系，所以本阶段只使用 synthetic observed brightness。

## Forward Model 公式

```text
soft_illumination = softplus(k * cos_i) / k
predicted_observed = albedo_param * soft_illumination
k = 50
```

softplus 是 `max(cos_i, 0)` 的 gradient-friendly 近似。它在阴影区会有 smooth leakage，这是数值近似，不是真实物理光照。

## Loss 公式

```text
loss = mean(confidence * (predicted_observed - observed)^2)
```

这里推荐使用 forward prediction loss，而不是把 `corrected_albedo = observed / cos_i` 作为主要可微目标，因为 near-zero `cos_i` 会造成除法和梯度爆炸风险。

## Confidence 公式

```text
confidence = sigmoid(k_conf * (cos_i - tau))
tau = 0.1
k_conf = 30
```

`confidence` 是 observability weight，不是真实地表可靠性，也不是真实云/阴影/BRDF 概率。

## Synthetic Cases

- `well_observed_case`: cos_i=[0.5, 0.7, 0.9], true_albedo=0.3, noise_std=0.0. 预测：albedo_hat 接近 0.3，confidence 高，uncertainty 低。
- `near_zero_case`: cos_i=[0.08, 0.1, 0.12], true_albedo=0.3, noise_std=0.0. 预测：可能拟合出数值，但 confidence 中低，uncertainty 升高。
- `shadow_case`: cos_i=[-0.3, -0.1, 0.02], true_albedo=0.3, noise_std=0.0. 预测：反演不可可靠，必须标记为 low observability / unreliable。
- `sparse_observation_case`: cos_i=[0.65, 0.72], true_albedo=0.3, noise_std=0.0. 预测：可能估得准，但观测数量少，uncertainty 高于 well_observed。
- `noisy_case`: cos_i=[0.4, 0.6, 0.8, 0.9], true_albedo=0.3, noise_std=0.02. 预测：albedo_hat 接近但不完全等于 0.3，residual 和 uncertainty 上升。

## 反演结果表

| case | albedo_true | albedo_hat | abs_error | final_loss | mean_confidence | effective_count | residual_std | uncertainty_proxy | reliability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| well_observed_case | 0.3 | 0.3 | 0 | 0 | 0.999998 | 2.99999 | 0 | 4.10629e-06 | HIGH |
| near_zero_case | 0.3 | 0.3 | 0 | 0 | 0.5 | 1.5 | 0 | 1 | MEDIUM |
| shadow_case | 0.3 | 0.3 | 0 | 0 | 0.0285505 | 0.0856515 | 0 | 1.9429 | LOW |
| sparse_observation_case | 0.3 | 0.3 | 5.55112e-17 | 3.08149e-33 | 1 | 2 | 0 | 0.333333 | MEDIUM |
| noisy_case | 0.3 | 0.28764 | 0.0123598 | 5.31656e-05 | 0.999969 | 3.99988 | 0.00712752 | 0.00359474 | HIGH |

## 结果解释

- `well_observed_case` 的 `cos_i` 都明显大于 0.1，illumination 稳定，weighted forward loss 对 `albedo` 有清晰约束，因此应高可信。
- `shadow_case` 即使优化器能输出一个 `albedo_hat`，也不代表反演可靠；它的 illumination 与 confidence 极低，属于 low observability / unreliable 区域。
- `sparse_observation_case` 可能数值上估得准，但观测数量少，effective observation count 低于 well-observed，因此不应过度自信。
- `near_zero_case` 位于 `cos_i≈tau` 附近，confidence 中低；如果改用 `observed / cos_i` 的硬校正形式，除法与梯度都会变危险。
- `noisy_case` 加入 synthetic Gaussian noise 后，residual 和 uncertainty proxy 应高于无噪声 well-observed case。
- `uncertainty_proxy = residual_std / sqrt(effective_count + eps) + near_zero_penalty + sparse_penalty` 只是工程 proxy，不是真实贝叶斯后验或置信区间。

## 正确性闸门

- **PASS** `well_observed_case 的 albedo_hat 接近 true_albedo=0.3`：absolute_error=0
- **PASS** `shadow_case 必须标记为 LOW reliability`：label=LOW, mean_confidence=0.0285505
- **PASS** `near_zero_case 显示较低 confidence 或较高 uncertainty`：mean_confidence=0.5, uncertainty=1
- **PASS** `sparse_observation_case 体现观测数量少带来的不确定性`：sparse_uncertainty=0.333333, well_uncertainty=4.10629e-06
- **PASS** `noisy_case residual 和 uncertainty 高于无噪声 well_observed_case`：noisy_residual=0.00712752, well_residual=0
- **PASS** `所有 case 输出 confidence 和 uncertainty_proxy`：每个 case 均包含 mean/min confidence、effective count、uncertainty proxy。
- **PASS** `Stage 6.1 是 synthetic inversion toy，不是真实 Landsat 地形校正`：脚本不读取 Landsat，不改写 Stage 2/3/4/5 数据。

## 是否通过 Stage 6.1

**PASS**。本阶段完成 synthetic differentiable inversion toy，并输出 confidence 与 uncertainty proxy；但它不是完整物理校正，也不是 Landsat 真实地形校正。

## 输出文件

- `stages/stage6_differentiable_inversion_toy/outputs/inversion_loss_curves.png`
- `stages/stage6_differentiable_inversion_toy/outputs/inversion_summary.png`
- `stages/stage6_differentiable_inversion_toy/reports/differentiable_albedo_inversion_toy_report.md`
- `stages/stage6_differentiable_inversion_toy/obsidian_drafts/Result_可微反演ToyModel_01.md`
- `stages/stage6_differentiable_inversion_toy/obsidian_drafts/Physics_Gate_可微反演ToyModel.md`
