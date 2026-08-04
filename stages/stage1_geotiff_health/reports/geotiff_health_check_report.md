# GeoTIFF 体检报告

## 输入文件

- 文件路径：`/Users/zhaoxiuyue/MountainRS/stage1_geotiff_health/data/srtm_dem.tif`

## 基础信息

- driver：`GTiff`
- width / height：`4320` / `2520`
- band count：`1`
- dtype：`int16`
- CRS：`EPSG:4326`
- transform：
```text
| 0.0002777778, 0.0000000000, 102.7998611111|
| 0.0000000000, -0.0002777778, 31.5001388889|
| 0.0000000000, 0.0000000000, 1.0000000000|
```
- resolution：`(0.0002777777777778146, 0.0002777777777778146)`
- resolution interpretation：
- 原始 resolution：0.0002777778 x 0.0002777778 度
- 约等于 1 arc-second / 30m 级 DEM，但实际地面距离随纬度变化
- bounds：`BoundingBox(left=102.79986111114857, bottom=30.800138888885023, right=103.99986111114873, top=31.500138888885115)`
- nodata：`-32768.0`

## 每波段统计

| Band | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio | NaN Count | Inf Count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 522.0000 | 6024.0000 | 2523.8872 | 1316.5217 | 10886400 | 10886400 | 0.0000% | 0 | 0 |

## 可视化

- 第一波段预览图：`/Users/zhaoxiuyue/MountainRS/stage1_geotiff_health/outputs/geotiff_band1_preview.png`
- 直方图 bins：`50`
- 当前预览图使用 row/column 坐标，仅用于快速查看数组形态，不代表地理坐标图。

## Warnings

- 该数据是经纬度坐标，像元大小单位是度。后续如果要计算坡度/坡向，建议先重投影到米制 CRS，否则坡度可能错误。

## Next-step Notes

- 该数据是经纬度坐标，像元大小单位是度。后续如果要计算坡度/坡向，建议先重投影到米制 CRS，否则坡度可能错误。

## 结论

- 判断结果：**可以进入下一步处理**
- 说明：如果 CRS 缺失、有效像元为空，或存在明显异常值风险，建议先修复后再进入后续遥感/DEM 流程。
