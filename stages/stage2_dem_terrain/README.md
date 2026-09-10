# Stage 2｜DEM 地形状态闭环

## 本容器做什么

把 Stage 1 体检通过的经纬度 DEM 推进到**米制地形状态底座**，并算出地形几何因子。
两步：`EPSG:4326 → EPSG:32648`（分辨率 0.0002777778° → 约 27.64 m，高程 522–6024 m →
522–6022 m，极值的轻微变化来自 bilinear 重采样平滑）；然后计算 slope / aspect /
curvature / hillshade。

**本阶段不做影像对齐**，只确认 DEM 自身的坐标、单位与地形因子处在物理上可解释的状态。

`curvature` 是 basic curvature，**不是完整地貌学曲率体系**——引用时不要当后者用。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `data/` | `srtm_dem.tif`（源）、`srtm_dem_utm48n.tif`（重投影结果，**下游都用这个**）、`dem_roi_plus_20km_utm48n.tif`（外扩 20 km 版） |
| `outputs/` | `slope_degree.tif`（0–87.09°）、`aspect_degree.tif`（0–359.85°）、`curvature.tif`、`hillshade.png`、预览与边界测试图 |
| `scripts/` | `reproject_dem_to_utm.py`、`compute_terrain_factors.py`、`test_terrain_factor_boundaries.py` |
| `reports/` | 重投影、地形因子、边界测试三份报告 |

脚本用 `Path(__file__).resolve().parent.parent` 定位容器根，不写仓库名或绝对路径。

## 依赖哪些兄弟容器与冻结件

- `../stage1_geotiff_health/data/srtm_dem.tif` — 体检通过的 DEM 源

下游用得最多的容器：Stage 3 的对齐目标网格、Stage 4 的 `cos_i` 输入、Stage 6.5 的地形栅格
都出自这里。**整个项目的 G（地形几何）源头在本容器。**

## 终态

通关。DEM 与三个地形因子均在物理可解释范围内，hillshade 明暗结构合理。
