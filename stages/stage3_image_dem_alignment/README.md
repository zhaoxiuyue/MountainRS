# Stage 3｜DEM + 影像对齐闭环

## 本容器做什么

完成 L0 多源对齐：把 Landsat Collection 2 Surface Reflectance 的 B4 Red、B5 NIR 对齐到
Stage 2 的 DEM 网格，使每个像元同时拥有 `elevation / slope / aspect / curvature / B4 / B5 / NDVI`。

**只解决空间框架一致性**，不进入地形校正、BRDF 校正或可微建模。

⚠️ **本容器的 Landsat 是 2023–2024 median composite，不是单景。**
Stage 6.5 的溯源审计给出两条结论（见
`../stage6_5_real_landsat_observation_stress_test/reports/stage3_landsat_source_audit.md`）：

1. 该 composite **不适合直接做单日物理地形校正**——单日的太阳几何与多日中位合成不对应；
2. **精确的 start / end date 已不可确认**，只能确认知识库描述为 2023–2024。这是一处
   provenance 缺口，如实登记而不是补一个看起来合理的日期。

因此 Stage 6.5 起改用单景 L2SR，本容器影像不再进入物理链路。**引用前先确认用途。**

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `data/` | `stage3_landsat_composite_sr_b4_red.tif`、`..._b5_nir.tif`（composite，见上方警示） |
| `outputs/` | `landsat_b4_red_aligned_to_dem.tif`、`..._b5_nir_...tif`、`ndvi_aligned_to_dem.tif`、对齐预览 |
| `scripts/` | `check_landsat_and_dem_spatial_match.py`、`align_landsat_to_dem_grid.py` |
| `reports/` | 空间检查、对齐、数据需求、Obsidian 收口四份 |

## 依赖哪些兄弟容器与冻结件

- `../stage2_dem_terrain/` — 对齐的目标网格与地形因子

## 终态

通关。B4/B5 影像健康 PASS、同网格 PASS、CRS 为 `EPSG:32648`。
