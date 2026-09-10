# Stage 1｜GeoTIFF 栅格体检闭环

## 本容器做什么

链条的起点：判断一个栅格文件是否具备进入后续 DEM/影像处理链的资格。检查 CRS 是否存在、
分辨率与 bounds、shape、dtype、nodata 是否污染统计、数值范围是否异常。

**只做体检，不做任何加工。** 本容器的 DEM 未经重投影——重投影在 Stage 2。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `data/` | `srtm_dem.tif`（EPSG:4326 原始 SRTM，全链条的 DEM 源头） |
| `scripts/` | `geotiff_health_check.py` |
| `reports/` | `geotiff_health_check_report.md` |
| `outputs/` | `geotiff_band1_preview.png` |

根目录另有 `requirements.txt`。

## 依赖哪些兄弟容器与冻结件

**无兄弟依赖——本容器是链条起点。** 下游：`../stage2_dem_terrain/` 取 `data/srtm_dem.tif` 做重投影。

## 终态

通关。CRS、分辨率、bounds、shape 均可报告，nodata 语义清楚。
