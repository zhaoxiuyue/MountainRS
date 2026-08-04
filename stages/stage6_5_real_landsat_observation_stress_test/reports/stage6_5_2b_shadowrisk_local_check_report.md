# Stage 6.5.2-B｜Shadow-risk Single-Scene 本地体检与封存

## 阶段目标

本阶段检查 Stage 6.5.1-B 导出的 shadow-risk single-scene Landsat L2 SR 数据包是否完整、是否具有真实单日太阳几何与 QA_PIXEL，并将 Stage 2 DEM / slope / aspect 对齐到 B 样本 Landsat grid。

核心目标不是运行残差模型，而是判断 B 样本是否比 A 样本更适合测试背阴坡 / near-zero 危险域机制。

本阶段不下载新数据，不进入 Stage 7，不使用旧 Stage 3 composite，不运行 Stage 6.5.3 残差模型，不生成 synthetic observed brightness，不做 residual model，不覆盖 Stage 6.5.1-A / 6.5.2-A clean baseline 样本。

## 输入文件列表

- B4 red: `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_shadowrisk_single_scene_l8_l2sr_b4_red.tif`
- B5 NIR: `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_shadowrisk_single_scene_l8_l2sr_b5_nir.tif`
- QA_PIXEL: `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_shadowrisk_single_scene_l8_l2sr_qa_pixel.tif`
- metadata CSV: `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_shadowrisk_single_scene_l8_l2sr_metadata.csv`
- DEM: `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem_utm48n.tif`
- slope: `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/slope_degree.tif`
- aspect: `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/aspect_degree.tif`

## 文件存在性检查

- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_shadowrisk_single_scene_l8_l2sr_b4_red.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_shadowrisk_single_scene_l8_l2sr_b5_nir.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_shadowrisk_single_scene_l8_l2sr_qa_pixel.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/data/stage6_5_shadowrisk_single_scene_l8_l2sr_metadata.csv`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem_utm48n.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/slope_degree.tif`: **PASS**
- `/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/aspect_degree.tif`: **PASS**

## Metadata 关键字段

- `image_id`: `LANDSAT/LC08/C02/T1_L2/LC08_130038_20230101`
- `date`: `2023-01-01`
- `CLOUD_COVER`: `28.74`
- `SUN_AZIMUTH`: `155.66673554`
- `SUN_ELEVATION`: `31.1368308`
- `WRS_PATH`: `130.0`
- `WRS_ROW`: `38.0`
- `ROI_GEOM_COVERAGE`: `1.0`
- `VALID_PIXEL_COVERAGE`: `0.5199480114198468`

缺失字段：`None`

## B4 / B5 / QA_PIXEL 空间信息

| 数据 | CRS | dtype | nodata | resolution | shape | bounds | min | max | mean | std | finite pixel ratio |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|
| B4 red | `EPSG:32648` | `float32` | `None` | `(30.0000000000, 30.0000000000)` | `(752, 650)` | `left=292230.000000, bottom=3451230.000000, right=311730.000000, top=3473790.000000` | -0.199972 | 1.599985 | 0.273001 | 0.380911 | 0.961792 (96.1792%) |
| B5 NIR | `EPSG:32648` | `float32` | `None` | `(30.0000000000, 30.0000000000)` | `(752, 650)` | `left=292230.000000, bottom=3451230.000000, right=311730.000000, top=3473790.000000` | -0.186057 | 1.599985 | 0.307027 | 0.354592 | 0.962817 (96.2817%) |
| QA_PIXEL | `EPSG:32648` | `uint16` | `None` | `(30.0000000000, 30.0000000000)` | `(752, 650)` | `left=292230.000000, bottom=3451230.000000, right=311730.000000, top=3473790.000000` | 0.000000 | 30304.000000 | 24220.757475 | 6106.538004 | 1.000000 (100.0000%) |

### B4 Transform

```text
| 30.0000000000, 0.0000000000, 292230.0000000000|
| 0.0000000000, -30.0000000000, 3473790.0000000000|
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

- B4 below `-0.05`: 7649 (1.6270%)
- B4 above `1.0`: 37867 (8.0547%)
- B5 below `-0.05`: 2180 (0.4632%)
- B5 above `1.0`: 30852 (6.5555%)

## QA valid pixel ratio

- 本地 QA valid ratio: `0.500829` (50.0829%)
- metadata VALID_PIXEL_COVERAGE: `0.519948` (51.9948%)
- Stage 6.5.1-B target VALID_PIXEL_COVERAGE: `0.80` (80.0%)
- absolute difference: `0.019119`
- 对比结论：**PASS**

如果差异较大，可能来自 GEE `reduceRegion` 与本地 raster 边界像元、mask 定义或导出裁剪方式差异。当前 B 样本的 QA coverage 低于原导出目标时，后续若进入 Stage 6.5.3-B，必须带 QA valid mask 与反射率 analysis mask 使用。

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

- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/dem_on_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/slope_on_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/aspect_on_shadowrisk_grid.tif`

重采样策略：

- DEM: bilinear
- slope: bilinear
- aspect: nearest，避免角度环绕导致 0/360 附近被错误平均

是否成功生成 terrain stack on Landsat grid：**PASS**

## cos_i 与 confidence

真实太阳几何来自 metadata：

- solar azimuth: `155.666736`
- solar elevation: `31.136831`
- solar zenith: `58.863169`

使用 Stage 4 同一套 `cos_i` 公式和 Stage 2 aspect 约定：aspect 表示最大下降方向，`0/360=北，90=东，180=南，270=西`。

| 数据 | min | max | mean | std | valid count | total count |
|---|---:|---:|---:|---:|---:|---:|
| cos_i | -0.691891 | 0.999999 | 0.399604 | 0.371410 | 488800 | 488800 |
| confidence | 0.000000 | 1.000000 | 0.736034 | 0.408076 | 488800 | 488800 |

### cos_i 分位数

- min: `-0.691891`
- p5: `-0.194944`
- p50: `0.417538`
- p95: `0.917179`
- mean: `0.399604`

### slope 统计

- mean slope: `34.120863`
- p90 slope: `48.177573`

confidence 使用 Stage 5 逻辑：

```text
tau = 0.1
k_conf = 30.0
confidence = sigmoid(k_conf * (cos_i - tau))
```

## near-zero / shadow 区域比例

- QA valid ratio: `0.500829` (50.0829%)
- near-zero ratio (`cos_i <= 0.1`): `0.264581` (26.4581%)
- shadow ratio (`cos_i <= 0`): `0.178889` (17.8889%)
- near-zero valid ratio (`QA valid 且 cos_i <= 0.1`): `0.393775` (39.3775%)
- shadow valid ratio (`QA valid 且 cos_i <= 0`): `0.270399` (27.0399%)
- safe ratio (`cos_i > 0.3`): `0.581371` (58.1371%)

## 与 A 样本对照

A 样本已封存为 clean high-confidence baseline sample：

- near_zero ratio ≈ 0.0006%
- shadow ratio = 0%

B 样本判断：

- near-zero valid ratio 是否明显高于 A：**PASS**
- shadow valid ratio 是否明显高于 A：**PASS**
- 综合判定：**PASS**

解释：

B 样本文件健康，且 near-zero_valid_ratio 或 shadow_valid_ratio 明显高于 A clean high-sun baseline，可作为 shadow / near-zero mechanism test 候选。

## 输出文件

- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/dem_on_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/slope_on_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/aspect_on_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/cos_i_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/confidence_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/qa_valid_mask_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/near_zero_mask_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/shadow_mask_shadowrisk_grid.tif`
- `/Users/zhaoxiuyue/MountainRS/stage6_5_real_landsat_observation_stress_test/outputs/stage6_5_2b_shadowrisk_local_check_preview.png`

## PASS / WARNING / FAIL 总结

- **PASS** B4 / B5 / QA_PIXEL must be same grid: CRS / transform / shape / bounds checked.
- **PASS** metadata must contain real SUN_AZIMUTH / SUN_ELEVATION: SUN_AZIMUTH=155.66673554, SUN_ELEVATION=31.1368308
- **WARNING** B4 / B5 must behave like scaled reflectance: Out-of-range reflectance ratios recorded; analysis_valid_ratio=0.491381.
- **PASS** QA_PIXEL must parse into valid mask: local_valid_ratio=0.500829
- **WARNING** B sample QA valid coverage should be interpreted cautiously: metadata VALID_PIXEL_COVERAGE=0.519948; target was 0.80. Use QA/analysis masks downstream.
- **PASS** Landsat small ROI must be inside DEM terrain bounds: same_crs=True, within_dem_bounds=True
- **PASS** cos_i must use real metadata sun angle: solar_azimuth=155.666736, solar_elevation=31.136831
- **PASS** Do not generate synthetic observed brightness: No synthetic observed brightness output is created.
- **PASS** Do not run residual model: No residual model or Stage 6.5.3 analysis is run.
- **PASS** Do not enter Stage 7: Only Stage 6.5.2 local check files are generated.
- **PASS** B sample should have clearly more near-zero / shadow danger than A baseline: near_zero_valid_ratio=0.393775, shadow_valid_ratio=0.270399, A_near_zero_ratio≈0.000006, A_shadow_ratio=0.000000

## 是否值得进入 Stage 6.5.3-B

**可以进入 Stage 6.5.3-B，但只做 shadow-risk single-scene 真实观测压力测试，不进入 Stage 7。**

如果综合判定为 WARNING，则 B 样本文件健康但 near-zero / shadow 比例仍低，应封存为 low-sun partial sample，不直接进入背阴坡机制测试。
