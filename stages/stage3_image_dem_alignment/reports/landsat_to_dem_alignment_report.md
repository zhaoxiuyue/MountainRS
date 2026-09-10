# Landsat 对齐到 DEM 网格报告

## DEM Grid 信息

- DEM：`stages/stage2_dem_terrain/data/srtm_dem_utm48n.tif`
- CRS：`EPSG:32648`
- resolution：`(27.6422871066, 27.6422871066)`
- shape：`(2867, 4179)`
- bounds：`left=289499.838109, bottom=3407878.491219, right=405016.955927, top=3487128.928354`
- transform：

```text
| 27.6422871066, 0.0000000000, 289499.8381090912|
| 0.0000000000, -27.6422871066, 3487128.9283539364|
| 0.0000000000, 0.0000000000, 1.0000000000|
```

## 原始 Landsat B4/B5 Grid 信息

| 数据 | 文件路径 | CRS | dtype | nodata | resolution | shape | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Original B4 red | `stages/stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b4_red.tif` | `EPSG:32648` | `float64` | `None` | `(30.0000000000, 30.0000000000)` | `(2642, 3852)` | -0.199093 | 1.022251 | 0.048851 | 0.043173 | 9844882 | 10176984 | 3.2633% |
| Original B5 nir | `stages/stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b5_nir.tif` | `EPSG:32648` | `float64` | `None` | `(30.0000000000, 30.0000000000)` | `(2642, 3852)` | -0.164663 | 0.930195 | 0.159644 | 0.089024 | 9844917 | 10176984 | 3.2629% |

### 原始 B4 transform

```text
| 30.0000000000, 0.0000000000, 289470.0000000000|
| 0.0000000000, -30.0000000000, 3487140.0000000000|
| 0.0000000000, 0.0000000000, 1.0000000000|
```

### 原始 B5 transform

```text
| 30.0000000000, 0.0000000000, 289470.0000000000|
| 0.0000000000, -30.0000000000, 3487140.0000000000|
| 0.0000000000, 0.0000000000, 1.0000000000|
```

## 对齐后 B4/B5/NDVI Grid 信息

| 数据 | 文件路径 | CRS | dtype | nodata | resolution | shape | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Aligned B4 red | `stages/stage3_image_dem_alignment/outputs/landsat_b4_red_aligned_to_dem.tif` | `EPSG:32648` | `float32` | `-9999.0` | `(27.6422871066, 27.6422871066)` | `(2867, 4179)` | -0.049987 | 0.881550 | 0.048889 | 0.042202 | 11592452 | 11981193 | 3.2446% |
| Aligned B5 nir | `stages/stage3_image_dem_alignment/outputs/landsat_b5_nir_aligned_to_dem.tif` | `EPSG:32648` | `float32` | `-9999.0` | `(27.6422871066, 27.6422871066)` | `(2867, 4179)` | -0.049548 | 0.873407 | 0.159661 | 0.087152 | 11595137 | 11981193 | 3.2222% |
| Aligned NDVI | `stages/stage3_image_dem_alignment/outputs/ndvi_aligned_to_dem.tif` | `EPSG:32648` | `float32` | `-9999.0` | `(27.6422871066, 27.6422871066)` | `(2867, 4179)` | -0.975209 | 0.999944 | 0.549400 | 0.197304 | 10087604 | 11981193 | 15.8047% |

## 对齐检查：Aligned B4 vs DEM

- same_crs：**PASS**
- same_transform：**PASS**
- same_resolution：**PASS**
- same_shape：**PASS**
- same_bounds：**PASS**

## 对齐检查：Aligned B5 vs DEM

- same_crs：**PASS**
- same_transform：**PASS**
- same_resolution：**PASS**
- same_shape：**PASS**
- same_bounds：**PASS**

## 对齐检查：Aligned NDVI vs DEM

- same_crs：**PASS**
- same_transform：**PASS**
- same_resolution：**PASS**
- same_shape：**PASS**
- same_bounds：**PASS**

## NDVI Mask 规则

- NDVI = `(B5 - B4) / (B5 + B4)`
- B4/B5 有效反射率宽松范围：`-0.05` 到 `1.0`
- denominator 阈值：只有 `abs(B5 + B4) > 0.05` 时才计算
- NDVI 输出进一步保留 `[-1, 1]` 内的物理有效值，其他像元写为 nodata
- denominator 阈值过滤像元数：`1503739`
- NDVI 物理范围过滤像元数：`925`

## 正确性闸门

1. aligned B4/B5/NDVI 必须与 DEM 同 CRS、同 transform、同 shape：**PASS**
2. B4/B5 反射率值应主要在 0-1 附近，允许少量负值但需要 warning：B4 **PASS**，B5 **PASS**
3. NDVI 有效值应主要在 -1 到 1；如果仍出现极端值，说明 mask/denominator 阈值失败：**PASS**
4. nodata 不得参与统计：**PASS**。统计均基于 nodata mask 后的有效像元。
5. preview 中 NDVI 应大体表现为山地/植被区偏高，裸地/城镇/低植被区偏低：**需人工查看**，预览图为 `stages/stage3_image_dem_alignment/outputs/alignment_preview.png`。

## Warnings

- B4/B5 对齐后仍有少量负反射率：B4=293553，B5=92444；Landsat SR 允许少量负值，后续建模/NDVI 可继续使用更严格 mask。

## 重要说明

- Landsat 从 30m 重采样到约 27.64m DEM 网格，只是为了对齐，不代表影像真实空间分辨率提高。
- 本阶段只做 L0 多源对齐，不做地形校正，不做 BRDF，不做可微模型。
- 本次没有重采样 DEM，没有改写 DEM/地形因子。

## 输出文件

- aligned B4：`stages/stage3_image_dem_alignment/outputs/landsat_b4_red_aligned_to_dem.tif`
- aligned B5：`stages/stage3_image_dem_alignment/outputs/landsat_b5_nir_aligned_to_dem.tif`
- aligned NDVI：`stages/stage3_image_dem_alignment/outputs/ndvi_aligned_to_dem.tif`
- preview：`stages/stage3_image_dem_alignment/outputs/alignment_preview.png`
