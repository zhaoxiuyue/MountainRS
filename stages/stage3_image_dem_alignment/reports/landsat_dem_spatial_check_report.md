# Landsat 影像体检与 DEM 空间检查报告

## 输入文件

- Landsat B4 red：`/Users/zhaoxiuyue/MountainRS/stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b4_red.tif`
- Landsat B5 nir：`/Users/zhaoxiuyue/MountainRS/stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b5_nir.tif`
- DEM：`/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem_utm48n.tif`

## Metadata 与统计

| 数据 | 文件路径 | CRS | dtype | nodata | resolution | shape | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | NaN Count | Inf Count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B4 red | `/Users/zhaoxiuyue/MountainRS/stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b4_red.tif` | `EPSG:32648` | `float64` | `None` | `(30.0000000000, 30.0000000000)` | `(2642, 3852)` | -0.199093 | 1.022251 | 0.048851 | 0.043173 | 9844882 | 10176984 | 332102 | 0 |
| B5 nir | `/Users/zhaoxiuyue/MountainRS/stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b5_nir.tif` | `EPSG:32648` | `float64` | `None` | `(30.0000000000, 30.0000000000)` | `(2642, 3852)` | -0.164663 | 0.930195 | 0.159644 | 0.089024 | 9844917 | 10176984 | 332067 | 0 |
| DEM | `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem_utm48n.tif` | `EPSG:32648` | `int16` | `-32768.0` | `(27.6422871066, 27.6422871066)` | `(2867, 4179)` | 522.000000 | 6022.000000 | 2523.109947 | 1316.833854 | 11620222 | 11981193 | 0 | 0 |

## Transform

### B4 red

```text
| 30.0000000000, 0.0000000000, 289470.0000000000|
| 0.0000000000, -30.0000000000, 3487140.0000000000|
| 0.0000000000, 0.0000000000, 1.0000000000|
```

### B5 nir

```text
| 30.0000000000, 0.0000000000, 289470.0000000000|
| 0.0000000000, -30.0000000000, 3487140.0000000000|
| 0.0000000000, 0.0000000000, 1.0000000000|
```

### DEM

```text
| 27.6422871066, 0.0000000000, 289499.8381090912|
| 0.0000000000, -27.6422871066, 3487128.9283539364|
| 0.0000000000, 0.0000000000, 1.0000000000|
```

## Bounds

- B4 red：`left=289470.000000, bottom=3407880.000000, right=405030.000000, top=3487140.000000`
- B5 nir：`left=289470.000000, bottom=3407880.000000, right=405030.000000, top=3487140.000000`
- DEM：`left=289499.838109, bottom=3407878.491219, right=405016.955927, top=3487128.928354`

## NDVI 快速预览统计

- NDVI 公式：`(B5 - B4) / (B5 + B4)`
- 说明：这是 Stage 3.1 的快速预览 NDVI，尚未做正式质量掩膜；当 `B5 + B4` 接近 0 或反射率含负值时，NDVI 可能出现极端值。
- min：`-2989.800000`
- max：`19657.000000`
- mean：`0.591577`
- std：`20.336107`
- valid pixel count：`9844882`
- total pixel count：`10176984`
- 预览图：`/Users/zhaoxiuyue/MountainRS/stage3_image_dem_alignment/outputs/landsat_preview.png`

## Nodata / Mask 说明

- B4 nodata=None，但存在 332102 个 NaN；本脚本将有限值作为有效像元，NaN 视作 mask。
- B5 nodata=None，但存在 332067 个 NaN；本脚本将有限值作为有效像元，NaN 视作 mask。

## B4/B5 同网格检查

- same_crs：**PASS**
- same_resolution：**PASS**
- same_transform：**PASS**
- same_bounds：**PASS**
- same_shape：**PASS**

- B4/B5 是否同网格：**PASS**

## Landsat 与 DEM 空间关系检查

- same_crs：**PASS**
- bounds_overlap：**PASS**
- resolution_close：**PASS**
- same_transform：**WARNING**
- same_shape：**WARNING**

- Landsat 与 DEM 是否已经完全对齐：**WARNING**
- 说明：shape 不一致不一定是错误，因为还没有执行对齐；这一步只是检查，不是最终对齐。

## 正确性闸门

1. B4/B5 反射率值大致应在合理范围内，通常主要在 0-1 附近：B4 **PASS**，B5 **PASS**。
2. B4/B5 应该同 CRS、同 transform、同 shape：**PASS**。
3. Landsat 与 DEM CRS 应该都是 EPSG:32648：**PASS**。
4. Landsat 与 DEM bounds 应该重叠：**PASS**。
5. 如果 transform/shape 不一致，报告应明确：还未完成最终对齐。当前 transform 一致性：**WARNING**；shape 一致性：**WARNING**。

## Warnings

- Landsat 与 DEM transform/shape 不一致：这一步只是检查，还未完成最终对齐。
- 快速 NDVI 出现超出 [-1, 1] 的极端值，主要来自反射率接近 0 或含负值时的近零分母；后续正式 NDVI 应增加有效反射率/mask 规则。

## 结论

- 当前影像是否健康：**PASS**。
- B4/B5 是否同网格：**PASS**。
- Landsat 与 DEM 是否已经完全对齐：**WARNING**。
- Landsat 与 DEM 当前同 CRS 且 bounds 重叠，但 resolution、transform、shape 不完全一致，因此还不能视为最终对齐。
- 下一步建议：第一版推荐把 Landsat B4/B5 重采样/对齐到 DEM/地形因子网格，这样后续每个像元可以同时拥有 elevation/slope/aspect/curvature/B4/B5/NDVI。

## 本次未做

- 未执行重采样。
- 未改写 DEM 或地形因子。
- 未进入地形校正。
