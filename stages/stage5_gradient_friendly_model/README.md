# Stage 5｜Gradient-friendly 正向模型与梯度校验

## 本容器做什么

L2 → L3 的桥：把 Stage 4 的非可微 toy model 改写成可微版本，并用 PyTorch autograd 与
有限差分对照，检查梯度是否可信。

**只检查梯度行为，不做反演，不用 Landsat 做真实地形校正。**

冻结的模型形式（下游沿用）：

- hard 对照保留：`hard_observed = albedo * max(cos_i, 0)`
- soft 可微版：`soft_observed = albedo * softplus(k * cos_i) / k`，`k = 50`
- soft confidence：`confidence = sigmoid(k_conf * (cos_i - tau))`，`tau = 0.1`、`k_conf = 30`

`tau = 0.1` 就是后续几何可见性判据 `cos_i > 0.1` 的来源；`k_conf = 30` 被 Stage 6.5 继承为
`soft_weight` 的经验基线（6.5.3-B 明确它**只是继承的经验基线**，敏感性检查留给后续）。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `outputs/` | `gradient_friendly_response_curves.png`、`synthetic_cases_gradient_check.png` |
| `scripts/` | `gradient_friendly_forward_check.py` |
| `reports/` | `gradient_friendly_forward_check_report.md` |

## 依赖哪些兄弟容器与冻结件

- `../stage4_terrain_radiation_toy/` — 被改写的非可微 toy model 与 `cos_i` 口径

## 终态

通关。softplus 近似的梯度与有限差分一致，hard 版保留为对照。
