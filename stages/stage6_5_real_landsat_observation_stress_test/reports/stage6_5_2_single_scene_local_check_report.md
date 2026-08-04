# Stage 6.5.2｜Clean Single-Scene L2 SR 本地体检 + 地形栈对齐检查

## 阶段目标

本阶段检查 Stage 6.5 clean single-scene Landsat L2 SR 数据包是否完整、是否具有真实单日太阳几何与 QA_PIXEL，并将 Stage 2 DEM / slope / aspect 对齐到 Landsat single-scene grid，为后续 Stage 6.5.3 真实观测压力测试做准备。

本阶段不下载新数据，不进入 Stage 7，不运行 Stage 6.5.3 模型残差分析，不生成 synthetic observed brightness，不做 residual model。

## 输入文件列表

- B4 red: `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_single_scene_l8_l2sr_b4_red.tif`
- B5 NIR: `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_single_scene_l8_l2sr_b5_nir.tif`
- QA_PIXEL: `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_single_scene_l8_l2sr_qa_pixel.tif`
- metadata CSV: `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_single_scene_l8_l2sr_metadata.csv`
- DEM: `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem_utm48n.tif`
- slope: `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/slope_degree.tif`
- aspect: `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/aspect_degree.tif`

## 文件存在性检查

- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_single_scene_l8_l2sr_b4_red.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_single_scene_l8_l2sr_b5_nir.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_single_scene_l8_l2sr_qa_pixel.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_single_scene_l8_l2sr_metadata.csv`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem_utm48n.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/slope_degree.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/aspect_degree.tif`: **PASS**

## Metadata 关键字段

- `image_id`: `LANDSAT/LC08/C02/T1_L2/LC08_130038_20230813`
- `date`: `2023-08-13`
- `CLOUD_COVER`: `12.52`
- `SUN_AZIMUTH`: `123.53706884`
- `SUN_ELEVATION`: `62.94220054`
- `WRS_PATH`: `130.0`
- `WRS_ROW`: `38.0`
- `ROI_GEOM_COVERAGE`: `1.0`
- `VALID_PIXEL_COVERAGE`: `1.0`

缺失字段：`None`

## B4 / B5 / QA_PIXEL 空间信息

| 数据 | CRS | dtype | nodata | resolution | shape | bounds | min | max | mean | std | finite pixel ratio |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|
| B4 red | `EPSG:32648` | `float32` | `None` | `(30.0000000000, 30.0000000000)` | `(746, 645)` | `left=377670.000000, bottom=3419010.000000, right=397020.000000, top=3441390.000000` | -0.043525 | 0.713302 | 0.050119 | 0.032360 | 0.980256 (98.0256%) |
| B5 NIR | `EPSG:32648` | `float32` | `None` | `(30.0000000000, 30.0000000000)` | `(746, 645)` | `left=377670.000000, bottom=3419010.000000, right=397020.000000, top=3441390.000000` | -0.012285 | 0.777653 | 0.304417 | 0.066428 | 0.980256 (98.0256%) |
| QA_PIXEL | `EPSG:32648` | `uint16` | `None` | `(30.0000000000, 30.0000000000)` | `(746, 645)` | `left=377670.000000, bottom=3419010.000000, right=397020.000000, top=3441390.000000` | 0.000000 | 21952.000000 | 21393.685159 | 3036.197240 | 1.000000 (100.0000%) |

### B4 Transform

```text
| 30.0000000000, 0.0000000000, 377670.0000000000|
| 0.0000000000, -30.0000000000, 3441390.0000000000|
| 0.0000000000, 0.0000000000, 1.0000000000|
```

## B4 / B5 / QA_PIXEL 同网格检查

- B4/B5 same CRS: **PASS**
- B4/QA same CRS: **PASS**
- B4/B5 same transform: **PASS**
- B4/QA same transform: **PASS**
- B4/B5 same shape: **PASS**
- B4/QA same shape: **PASS**
- B4/B5 same bounds: **PASS**
- B4/QA same bounds: **PASS**

## B4 / B5 反射率统计

B4 / B5 应表现为 scaled reflectance，主要位于 `[-0.05, 1.0]`。本阶段不删除异常值，只记录比例。

- B4 below `-0.05`: 0 (0.0000%)
- B4 above `1.0`: 0 (0.0000%)
- B5 below `-0.05`: 0 (0.0000%)
- B5 above `1.0`: 0 (0.0000%)

## QA valid pixel ratio

- 本地 QA valid ratio: `0.980256` (98.0256%)
- metadata VALID_PIXEL_COVERAGE: `1.000000` (100.0000%)
- absolute difference: `0.019744`
- 对比结论：**PASS**

如果差异较大，可能来自 GEE `reduceRegion` 与本地 raster 边界像元、mask 定义或导出裁剪方式差异。

## DEM / slope / aspect 与 Landsat grid 的空间关系

- Landsat CRS: `EPSG:32648`
- DEM CRS: `EPSG:32648`
- slope CRS: `EPSG:32648`
- aspect CRS: `EPSG:32648`
- CRS 一致：**PASS**
- Landsat small ROI 是否落在 DEM bounds 内：**PASS**

不要求 DEM 与 Landsat 同 transform / shape，因为 Landsat 是 30m small ROI，DEM 是大范围约 27.64m 网格。

## Terrain stack on Landsat grid

已生成：

- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/dem_on_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/slope_on_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/aspect_on_single_scene_grid.tif`

重采样策略：

- DEM: bilinear
- slope: bilinear
- aspect: nearest，避免角度环绕导致 0/360 附近被错误平均

是否成功生成 terrain stack on Landsat grid：**PASS**

## cos_i 与 confidence

真实太阳几何来自 metadata：

- solar azimuth: `123.537069`
- solar elevation: `62.942201`
- solar zenith: `27.057799`

使用 Stage 4 同一套 `cos_i` 公式和 Stage 2 aspect 约定：aspect 表示最大下降方向，`0/360=北，90=东，180=南，270=西`。

| 数据 | min | max | mean | std | valid count | total count |
|---|---:|---:|---:|---:|---:|---:|
| cos_i | 0.051713 | 0.999995 | 0.885166 | 0.052806 | 481170 | 481170 |
| confidence | 0.190215 | 1.000000 | 0.999992 | 0.001871 | 481170 | 481170 |

confidence 使用 Stage 5 逻辑：

```text
tau = 0.1
k_conf = 30.0
confidence = sigmoid(k_conf * (cos_i - tau))
```

## near-zero / shadow 区域比例

- near-zero mask (`0 < cos_i <= 0.1`): `0.000006` (0.0006%)
- shadow mask (`cos_i <= 0`): `0.000000` (0.0000%)

## 输出文件

- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/dem_on_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/slope_on_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/aspect_on_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/cos_i_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/confidence_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/qa_valid_mask_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/near_zero_mask_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/shadow_mask_single_scene_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/stage6_5_2_single_scene_local_check_preview.png`

## PASS / WARNING / FAIL 总结

- **PASS** B4 / B5 / QA_PIXEL must be same grid: CRS / transform / shape / bounds checked.
- **PASS** metadata must contain real SUN_AZIMUTH / SUN_ELEVATION: SUN_AZIMUTH=123.53706884, SUN_ELEVATION=62.94220054
- **PASS** B4 / B5 must behave like scaled reflectance: Out-of-range reflectance ratios recorded without deleting pixels.
- **PASS** QA_PIXEL must parse into valid mask: local_valid_ratio=0.980256
- **PASS** Landsat small ROI must be inside DEM terrain bounds: same_crs=True, within_dem_bounds=True
- **PASS** cos_i must use real metadata sun angle: solar_azimuth=123.537069, solar_elevation=62.942201
- **PASS** Do not generate synthetic observed brightness: No synthetic observed brightness output is created.
- **PASS** Do not run residual model: No residual model or Stage 6.5.3 analysis is run.
- **PASS** Do not enter Stage 7: Only Stage 6.5.2 local check files are generated.

## 下一步是否可以进入 Stage 6.5.3

**可以进入 Stage 6.5.3，但只能做 clean single-scene 真实观测压力测试。**

进入 Stage 6.5.3 前仍需确认：不进入 Stage 7，不使用旧 Stage 3 composite，不生成 synthetic observed brightness，只针对当前 clean single-scene 数据包做真实观测压力测试。
