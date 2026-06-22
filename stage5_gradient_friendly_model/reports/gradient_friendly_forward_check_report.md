# Gradient-friendly 正向模型梯度校验报告

## Stage 5 目标

Stage 5 的目标是把 Stage 4 的非可微正向 toy model 改写成 gradient-friendly 版本，并用 PyTorch autograd 与 finite difference 做梯度校验。本阶段不是反演，不使用 Landsat 做真实地形校正，也不是完整物理校正。

## Hard Model 公式

```text
hard_observed = albedo * max(cos_i, 0)
```

## Soft Model 公式

```text
soft_observed = albedo * softplus(k * cos_i) / k
k = 50
```

## Soft Confidence / Observability Weight

```text
confidence = sigmoid(k_conf * (cos_i - tau))
tau = 0.1
k_conf = 30
```

confidence 是可微的软权重，不是硬 mask。它表示 `cos_i` 是否足够远离 near-zero correction danger zone。

## 为什么 hard max / hard mask / hard threshold 会造成梯度问题

- `max(cos_i, 0)` 在 `cos_i=0` 处不可导，在阴影区梯度为 0。
- hard shadow mask 会直接切断梯度流。
- hard threshold `cos_i > 0.1` 会让阈值两侧的输出突然跳变。
- 如果后续反演直接用 `observed / cos_i`，near-zero `cos_i` 会造成梯度爆炸。

## 为什么 softplus 可以近似 max(cos_i, 0)

`softplus(k*x)/k` 是 `max(x, 0)` 的平滑近似。`k` 越大，曲线越接近 hard max，但在阴影区会有小的 smooth leakage。这是数值近似，不是真实物理光照。

## 为什么 sigmoid confidence 可以替代硬阈值作为可微权重

`sigmoid(k_conf * (cos_i - tau))` 在 `cos_i` 远大于 `tau` 时接近 1，在 `cos_i < tau` 时接近 0，并在阈值附近平滑过渡。它不会把 hard shadow 区域伪装成可靠反演区域，而是用低 confidence 表示低可观测性。

## Synthetic Cases

| Case | slope | aspect | albedo | cos_i | hard_observed | soft_observed | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flat slope | 0.0000 | 0.0000 | 0.3000 | 0.707107 | 0.212132 | 0.212132 | 1.000000 |
| facing slope | 30.0000 | 315.0000 | 0.3000 | 0.965926 | 0.289778 | 0.289778 | 1.000000 |
| back-facing slope | 60.0000 | 135.0000 | 0.3000 | -0.258819 | 0.000000 | 0.000000 | 0.000021 |
| near-zero cos_i | 65.0000 | 63.0753 | 0.3000 | 0.100000 | 0.030000 | 0.030040 | 0.500000 |

## Finite Difference Gradient Check

| Case | Variable | cos_i | Autograd | Finite Difference | Abs Error | Rel Error |
| --- | --- | --- | --- | --- | --- | --- |
| flat slope | albedo | 0.707107 | 7.07106772e-01 | 7.07106772e-01 | 1.64313008e-14 | 2.32373687e-14 |
| flat slope | slope | 0.707107 | 2.61799453e-03 | 2.61799453e-03 | 1.07586466e-12 | 4.10949926e-10 |
| flat slope | aspect | 0.707107 | -0.00000000e+00 | 0.00000000e+00 | 0.00000000e+00 | 0.00000000e+00 |
| facing slope | albedo | 0.965926 | 9.65925826e-01 | 9.65925826e-01 | 1.72362125e-12 | 1.78442402e-12 |
| facing slope | slope | 0.965926 | 1.35517335e-03 | 1.35517335e-03 | 5.61022583e-14 | 4.13985843e-11 |
| facing slope | aspect | 0.965926 | 0.00000000e+00 | 0.00000000e+00 | 0.00000000e+00 | 0.00000000e+00 |
| back-facing slope | albedo | -0.258819 | 1.01354306e-12 | 1.01354306e-12 | 2.16024195e-24 | 2.13137659e-12 |
| back-facing slope | slope | -0.258819 | -4.10082109e-13 | -4.10082110e-13 | 4.64126326e-22 | 4.64126326e-10 |
| back-facing slope | aspect | -0.258819 | 3.18385683e-29 | 0.00000000e+00 | 3.18385683e-29 | 3.18385683e-17 |
| near-zero cos_i | albedo | 0.100000 | 5.00671535e-02 | 5.00671535e-02 | 1.02515219e-13 | 2.04755436e-12 |
| near-zero cos_i | slope | 0.100000 | -4.79225419e-03 | -4.79225419e-03 | 9.51929507e-15 | 1.98639194e-12 |
| near-zero cos_i | aspect | 0.100000 | -3.97993866e-03 | -3.97993865e-03 | 4.38811747e-12 | 1.10255907e-09 |
| random small batch[2,3] | albedo | -0.234741 | 3.47812013e-13 | 0.00000000e+00 | 3.47812013e-13 | 3.47812013e-01 |
| random small batch[2,3] | slope | -0.234741 | -1.92930391e-13 | 0.00000000e+00 | 1.92930391e-13 | 1.92930391e-01 |
| random small batch[2,3] | aspect | -0.234741 | -4.48153698e-14 | 0.00000000e+00 | 4.48153698e-14 | 4.48153698e-02 |

- max absolute error：`4.38811747e-12`
- max relative error：`3.47812013e-01`
- autograd vs finite difference 是否接近：**PASS**

## Near-zero cos_i 为什么危险

`corrected_albedo = observed / cos_i` 在 `cos_i` 接近 0 时会把微小误差放大。这个区域既可能是背阴坡，也可能是接近掠射光照的弱可观测区。Stage 5 不把 corrected_albedo 作为主要可微目标，推荐后续反演使用 forward prediction loss，而不是直接除以 `cos_i` 做硬校正。

## 正确性闸门

1. softplus 曲线应近似 `max(cos_i,0)`，但在阴影区会有小的 smooth leakage：**PASS**。这是数值近似，不是真实物理光照。
2. autograd 梯度与 finite difference 梯度应接近：**PASS**。
3. near-zero `cos_i` 区域必须被标为梯度危险区：**PASS**。
4. confidence 应在 `cos_i >> 0.1` 时接近 1，在 `cos_i < 0.1` 时接近 0：**PASS**。
5. 不允许把 hard shadow 区域伪装成可可靠反演区域：**PASS**。
6. Stage 5 是 gradient behavior test，不是完整物理校正：**PASS**。

## 本阶段是否通过梯度校验

**PASS**

## 哪些地方仍然不代表真实物理

- softplus 阴影区 leakage 是数值平滑，不是真实阴影光照。
- confidence 是可微权重，不是真实云/阴影/BRDF 物理模型。
- synthetic cases 只验证梯度行为，不代表真实地表反射机制。
- 没有使用真实太阳 metadata、天空散射、邻近地形反射或大气项。

## 为什么本阶段仍不使用 Landsat 做真实校正

当前 Landsat 是 2023-2024 median composite，不是单日观测。单日地形辐射校正需要对应日期的太阳几何、观测几何和质量掩膜。本阶段只验证 gradient-friendly 正向模型的行为。

## 下一步如何进入可微反演 toy model

- 保留 softplus forward model。
- 使用 confidence 作为 loss weight。
- 构造 synthetic observed brightness。
- 先反演 albedo toy parameter，再逐步加入 slope/aspect 或太阳几何扰动。
- 严格监控 near-zero `cos_i` 区域的梯度爆炸风险。

## 输出图

- `/Users/zhaoxiuyue/MountainRS/stage5_gradient_friendly_model/outputs/gradient_friendly_response_curves.png`
- `/Users/zhaoxiuyue/MountainRS/stage5_gradient_friendly_model/outputs/synthetic_cases_gradient_check.png`
