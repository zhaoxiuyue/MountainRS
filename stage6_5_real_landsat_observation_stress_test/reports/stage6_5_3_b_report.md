# Stage 6.5.3-B｜First Action：规范掩膜与空间隔离预检

- **预检结论：** `BLOCKED`
- **执行边界：** deterministic preflight only；未拟合三种机制、未评分 holdout、未计算 residual/risk–coverage、未形成最终实验结论。
- **Architecture basis：** docs/architecture.md V3。

## 冻结口径

- `base_valid`：QA_PIXEL bits 0–5 均为 0，B4/B5/cos_i 均 finite、非 nodata，且 B4/B5 都在 [-0.05, 1.0]。
- 分区：`shadow=cos_i<=0`、`near_zero=0<cos_i<=0.1`、`lit=cos_i>0.1`；完整性在 `base_valid` 上验证。
- water bit 7 单独统计，并从主要 land 指标和空间相关估计排除；更高 QA confidence bits 本轮明确不作为 hard exclusion。
- `soft_weight` k=30 只是继承的经验基线；k={15,30,60} 留给同一机制的后续敏感性检查。bounded diffuse 的数值界限尚未裁决，只能由 calibration-only 证据冻结。

## A/B 规范统计

| Scene | base_valid | base_valid_land | water in base_valid | shadow land | near_zero land | lit land | partition integrity |
|---|---:|---:|---:|---:|---:|---:|---|
| clean_a | 471670 (0.980256) | 469534 (0.975817) | 2136 | 0 (0.000000) | 3 (0.000006) | 469531 (0.999994) | PASS |
| shadow_risk_b | 240187 (0.491381) | 102222 (0.209128) | 137965 | 4063 (0.039747) | 4559 (0.044599) | 93600 (0.915654) | PASS |

## Grid / nodata 检查

- **clean_a**：CRS=EPSG:32648，shape=[746, 645]，resolution=[30.0, 30.0]，主输入 grid=PASS。
- **shadow_risk_b**：CRS=EPSG:32648，shape=[752, 650]，resolution=[30.0, 30.0]，主输入 grid=PASS。

## 空间相关范围与候选隔离

### clean_a
- cos_i: reliable range=806.250 m；tail sill=0.0025733258。
- b4: reliable range=2015.625 m；tail sill=0.0010808709。
- b5: reliable range=1612.500 m；tail sill=0.0039230642。
- candidate blocks: **BLOCKED** — 独立候选 blocks 不足：calibration=1, holdout=0, minimum=2。
### shadow_risk_b
- cos_i: reliable range=2437.500 m；tail sill=0.10595167。
- b4: reliable range=8125.000 m；tail sill=0.01680663。
- b5: reliable range=7718.750 m；tail sill=0.022000338。
- candidate blocks: **BLOCKED** — 独立候选 blocks 不足：calibration=1, holdout=0, minimum=2。

## Prior-result 差异核对

已有 QA/mask/confidence 仅作 cross-check，并未作为 canonical mask 真相源。旧 near-zero mask 的 `cos_i<=0.1` 口径包含 shadow；因此它与本轮严格 `0<cos_i<=0.1` 的差异是预期可解释差异，而非补写或拟合。

## Verdict / blockers

- **BLOCKER：** clean_a 独立 calibration/holdout candidate blocks 不足：独立候选 blocks 不足：calibration=1, holdout=0, minimum=2
- **BLOCKER：** shadow_risk_b 独立 calibration/holdout candidate blocks 不足：独立候选 blocks 不足：calibration=1, holdout=0, minimum=2

## 尚待裁决

- bounded_scene_constant_diffuse 的数值边界与依据必须在 calibration-only 条件下另行冻结；不得读取 holdout 后调整。
- 本报告不提供三种机制的拟合、残差、risk–coverage 或最终优劣结论。
