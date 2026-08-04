# Stage 6.5.1-B｜Shadow-risk Single-scene Candidate Audit Plan

## 当前 clean high-sun baseline sample 标记

Stage 6.5.2-A 已完成的 clean single-scene L2 SR 样本保留为：

**clean high-confidence baseline sample**

该样本可用于检查干净单日 Landsat L2 SR 数据包、本地 QA 解析、真实太阳角 `cos_i` 计算和地形栈对齐流程是否可靠。

但它不继续用于 shadow mechanism test：

- near-zero ratio ≈ `0.0006%`
- shadow ratio = `0%`
- confidence mean ≈ `0.999992`
- solar elevation ≈ `62.94°`

这说明当前样本是高太阳高度、高可观测性、低阴影风险样本，不适合专门测试背阴坡 / near-zero 危险域机制。

## 新 audit 的目标

Stage 6.5.1-B 的目标是在原始 DEM 大范围内寻找更适合测试 shadow / near-zero danger mechanism 的单日 Landsat Collection 2 Level-2 Surface Reflectance 候选样本。

本轮只做 GEE audit：

- 不创建 `Export.image.toDrive`
- 不创建 `Export.table.toDrive`
- 不下载影像
- 不运行 Stage 6.5.3-A 或任何残差模型
- 不进入 Stage 7
- 不修改 Stage 1-6 数据
- 不删除旧 Stage 3 composite
- 不删除 Stage 6.5.1-A / 6.5.2-A 已生成数据

## 时间范围为什么扩展到 2022-10-01 到 2024-03-31

当前 clean baseline 样本来自 2023-08-13，太阳高度较高，几乎没有 shadow / near-zero 区域。

为了增加低太阳高度候选，本次搜索扩展到：

```text
2022-10-01 到 2024-03-31
```

这个窗口覆盖秋冬春季，更可能出现较低 `SUN_ELEVATION`。低太阳高度与复杂山地地形叠加，更容易形成 `cos_i <= 0.1` 或 `cos_i <= 0` 的危险域。

## 为什么优先搜索西部 / 西北部高起伏山地 ROI

原始 DEM 大 ROI 的西部、西北部和西南部更可能包含高起伏山地。高坡度、高起伏区域在低太阳高度条件下更容易出现：

- 背光坡
- near-zero illumination
- 阴影风险
- 空间异质性更强的观测条件

因此 Stage 6.5.1-B 先设置多个候选 small ROIs：

- `ROI_MTN_NW`: `[102.82, 31.18, 103.02, 31.38]`
- `ROI_MTN_W`: `[102.88, 30.95, 103.08, 31.15]`
- `ROI_MTN_C`: `[103.00, 31.05, 103.20, 31.25]`
- `ROI_MTN_SW`: `[102.82, 30.82, 103.02, 31.02]`

这些 ROI 只是候选，后续可根据 footprint、DEM bounds 和审计表结果微调。

## GEE 审计脚本

脚本路径：

```text
stage6_5_real_landsat_observation_stress_test/scripts/gee_audit_shadow_risk_single_scene_l2sr.js
```

第一版数据源：

```text
LANDSAT/LC08/C02/T1_L2
```

后续若 LC08 候选不足，可再兼容：

```text
LANDSAT/LC09/C02/T1_L2
```

## 候选评价指标

每一行是一个 `image × ROI` pair，字段包括：

- `roi_name`
- `image_id`
- `date`
- `CLOUD_COVER`
- `SUN_AZIMUTH`
- `SUN_ELEVATION`
- `WRS_PATH`
- `WRS_ROW`
- `ROI_GEOM_COVERAGE`
- `VALID_PIXEL_COVERAGE`
- `shadow_ratio`
- `near_zero_ratio`
- `safe_ratio`
- `mean_slope`
- `p90_slope`
- `mean_cos_i`
- `min_cos_i`
- `shadow_valid_ratio`
- `near_zero_valid_ratio`
- `score`

其中：

- `ROI_GEOM_COVERAGE` 检查 footprint 是否覆盖 ROI。
- `VALID_PIXEL_COVERAGE` 基于 `QA_PIXEL` 与 `SR_B4/SR_B5` mask，排除 fill、dilated cloud、cirrus、cloud、cloud shadow、snow。
- `shadow_valid_ratio` 与 `near_zero_valid_ratio` 只在 QA valid pixels 内计算。

## Score 第一版

第一版推荐分数：

```text
score =
  VALID_PIXEL_COVERAGE
  * ROI_GEOM_COVERAGE
  * (near_zero_valid_ratio + 2 * shadow_valid_ratio)
```

这个分数有意不以最低云量为唯一目标，而是偏向：

- coverage 合格
- QA 可用
- shadow / near-zero 危险域明显

## 通过标准

基本门槛：

- `ROI_GEOM_COVERAGE >= 0.95`
- `VALID_PIXEL_COVERAGE >= 0.80`
- `SUN_ELEVATION` 尽量低
- `near_zero_valid_ratio` 或 `shadow_valid_ratio` 明显高于 clean baseline

参考 clean baseline：

- near-zero ratio ≈ `0.0006%`
- shadow ratio = `0%`

因此新候选至少应明显超过该水平，才值得进入下一步导出。

## 地图审计

GEE Map 显示：

- large ROI：黄色线框
- candidate small ROIs：橙色线框
- candidate footprints：青色线框
- top candidate footprint：蓝色线框
- top candidate ROI：红色线框
- top candidate `cos_i` preview
- top candidate near-zero mask
- top candidate shadow mask

## 下一步

如果找到合格 top candidate，再创建新的 Stage 6.5.1-C export 脚本，导出：

- scaled SR_B4 red
- scaled SR_B5 NIR
- raw QA_PIXEL
- metadata CSV

导出前仍需检查：

- 是否单日 single scene
- 是否有唯一 `SUN_AZIMUTH / SUN_ELEVATION`
- coverage 是否合格
- QA valid coverage 是否合格
- shadow / near-zero 风险是否明显高于 clean baseline

当前不进入 Stage 6.5.3，也不进入 Stage 7。
