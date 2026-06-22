# DEM 重投影报告

## 文件路径

- 输入文件路径：`/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem.tif`
- 输出文件路径：`/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem_utm48n.tif`
- 预览图路径：`/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/dem_utm48n_preview.png`

## CRS

- 输入 CRS：`EPSG:4326`
- 输出 CRS：`EPSG:32648`

## Resolution

- 输入 resolution：`(0.0002777778, 0.0002777778)`，单位为度
- 输出 resolution：`(27.6422871066, 27.6422871066)`，单位为米

## Bounds

- 输入 bounds：`left=102.799861, bottom=30.800139, right=103.999861, top=31.500139`
- 输出 bounds：`left=289499.838109, bottom=3407878.491219, right=405016.955927, top=3487128.928354`

## Shape

- 输入 shape：`(2520, 4320)`，格式为 `(height, width)`
- 输出 shape：`(2867, 4179)`，格式为 `(height, width)`

## Nodata

- nodata：`-32768.0`

## 高程统计

| 数据 | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count |
| --- | --- | --- | --- | --- | --- | --- |
| 重投影前 | 522.0000 | 6024.0000 | 2523.8872 | 1316.5217 | 10886400 | 10886400 |
| 重投影后 | 522.0000 | 6022.0000 | 2523.1099 | 1316.8339 | 11620222 | 11981193 |

## 正确性闸门

1. 输出 CRS 应为 EPSG:32648：**满足**
2. 输出 resolution 应约为 30m 级，而不是 0.000277 度：**满足**
3. 高程 min/max 不应剧烈变化，仍应大约在 522-6024m 附近：**满足**
4. 输出 shape 可以变化：**满足**
5. 输出 bounds 应从经纬度范围变成 UTM 米制坐标范围：**满足**

## 结论

- 重投影后像元单位从度变成米，后续才适合计算 slope/aspect。
- 本次仅完成 DEM 重投影闭环，未执行 slope/aspect 计算。
