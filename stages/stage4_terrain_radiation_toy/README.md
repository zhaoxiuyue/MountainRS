# Stage 4｜非可微地形辐射 Toy Model

## 本容器做什么

L2 正向观测算子的第一版：用 Stage 2 的**真实** DEM/slope/aspect，在**常数 albedo** 条件下
模拟地形光照如何产生 observed brightness，并验证「简单除以 `cos_i` 做校正」为什么必须避开
背阴坡与 `cos_i` 接近 0 的区域。

**这是 toy model。** 输入的地形是真的，但 albedo 是常数、观测是模拟的。
本阶段不用 Landsat 做真实地形校正，不进入可微模型。**其结论不可外推到真实数据。**

本容器产出的 `cos_i` 与 `shadow_mask` 定义了后续整条链路沿用的地形入射几何口径。
Stage 6.5 的三分区 `shadow=cos_i<=0` / `near_zero=0<cos_i<=0.1` / `lit=cos_i>0.1` 由两处拼成：
`cos_i` 本身与 `shadow` 的边界来自本容器，而 `0.1` 这个近零阈值来自
`../stage5_gradient_friendly_model/` 的 `tau`——**不是本容器定的**，别记混。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `outputs/` | `cos_i.tif`、`shadow_mask.tif`、`observed_brightness_toy.tif`、`corrected_albedo_toy.tif`、预览图 |
| `scripts/` | `terrain_radiation_toy_model.py` |
| `reports/` | `terrain_radiation_toy_report.md` |

`data/` 为空——本容器不持有原始输入，地形全部取自 Stage 2。

## 依赖哪些兄弟容器与冻结件

- `../stage2_dem_terrain/data/srtm_dem_utm48n.tif` 与 `outputs/slope_degree.tif`、`outputs/aspect_degree.tif`

## 终态

通关。除以 `cos_i` 的校正在背阴坡与近零入射区失效，这一失效被显式刻画而不是回避。
