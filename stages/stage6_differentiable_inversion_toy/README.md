# Stage 6｜可微反演 Toy Model + 置信度字段

## 本容器做什么

**L3 弱闭环**：在 synthetic `cos_i` 与 synthetic observed brightness 已知的条件下，用 Stage 5 的
gradient-friendly 正向模型与 forward prediction loss 反演 `albedo`，同时输出 `confidence`、
`uncertainty_proxy` 与 `reliability_label`。

「弱」在哪里：它已经从「正向算观测」进入「用观测反推参数」，但**观测仍是 synthetic，不是
真实遥感反演**。本阶段不用真实 Landsat，不改写 Stage 2–5 的任何数据。

`uncertainty_proxy` 与 `reliability_label` 在本阶段只是 toy 产物，**不构成任何校准过的
不确定性**——正式校准要到 Stage 7.11，且至今未做。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `outputs/` | `inversion_loss_curves.png`、`inversion_summary.png` |
| `scripts/` | `differentiable_albedo_inversion_toy.py` |
| `reports/` | `differentiable_albedo_inversion_toy_report.md`、Obsidian 收口报告 |

## 依赖哪些兄弟容器与冻结件

- `../stage5_gradient_friendly_model/` — 正向模型形式与 `k=50`、`tau=0.1`、`k_conf=30`

## 终态

通关。synthetic 条件下 albedo 可恢复，置信度与可靠性字段成形。

**下一步不是 Stage 7 而是 Stage 6.5**——真实观测压力测试插在这里，因为 toy 闭环通关
不等于真实数据上能闭环。见 `../stage6_5_real_landsat_observation_stress_test/`。
