# Stage 6.5.1｜Clean Single-Scene Landsat L2 SR Export Plan

## 目标

Stage 6.5.1 的目标是为 Stage 6.5 真实 Landsat 观测压力测试准备一个干净、可审计、单日的 Landsat Collection 2 Level-2 Surface Reflectance 数据包。

这不是 Stage 7，不做多 ROI，不做多景合成，不做模型训练，也不使用旧 Stage 3 composite 直接跑 Stage 6.5 主模型。

## 为什么需要新导出

Stage 6.5.0 审计显示，旧 Stage 3 aligned B4 / B5 / NDVI 缺少：

- 原始 GEE export script
- `QA_PIXEL`
- metadata CSV
- 唯一 `SUN_AZIMUTH`
- 唯一 `SUN_ELEVATION`
- 可验证的 `filterDate`
- 可验证的 Landsat C2 L2 scale 流程

因此旧 Stage 3 composite 不能作为单日物理地形验证样本。Stage 6.5.1 必须重新准备一个 clean single-scene package。

## GEE 脚本

脚本路径：

```text
stage6_5_real_landsat_observation_stress_test/scripts/gee_export_clean_single_scene_l2sr.js
```

数据源第一版：

```text
LANDSAT/LC08/C02/T1_L2
```

暂不混用 LC09。后续如果 LC08 在目标 ROI 内没有合格样本，再考虑兼容 LC09。

## ROI 设计

保留原始大 ROI 作为黄色线框记录：

```text
left   = 102.79986111114857
bottom = 30.800138888885023
right  = 103.99986111114873
top    = 31.500138888885115
```

第一版 small ROI：

```text
left   = 103.72
bottom = 30.90
right  = 103.92
top    = 31.10
```

它位于原 DEM 范围内，大小约 `0.20° x 0.20°`，用于提高单景 full coverage 的可能性。这个 small ROI 只服务于 Stage 6.5 clean sample，不代表 Stage 7 多 ROI 主线。

## 时间范围

第一版时间范围：

```text
2023-04-01 到 2023-10-31
```

该范围覆盖生长季与较长候选窗口，有利于找到低云且 ROI 有效像元覆盖足够的单日影像。

## 候选影像表字段

GEE Console 会打印 candidate summary table，字段包括：

- `image_id`
- `date`
- `CLOUD_COVER`
- `SUN_AZIMUTH`
- `SUN_ELEVATION`
- `WRS_PATH`
- `WRS_ROW`
- `ROI_GEOM_COVERAGE`
- `VALID_PIXEL_COVERAGE`

## Coverage 定义

### ROI_GEOM_COVERAGE

```text
image.geometry().intersection(smallRoi).area() / smallRoi.area()
```

它检查 Landsat footprint 是否几何覆盖 small ROI。

### VALID_PIXEL_COVERAGE

`VALID_PIXEL_COVERAGE` 基于 `QA_PIXEL` 与 B4/B5 band mask 计算。第一版至少排除：

- fill
- dilated cloud
- cirrus
- cloud
- cloud shadow
- snow

同时要求 `SR_B4` 和 `SR_B5` 都有有效 mask。

## 选择标准

单日影像必须满足：

- `ROI_GEOM_COVERAGE >= 0.95`
- `VALID_PIXEL_COVERAGE >= 0.90`
- 最好 `VALID_PIXEL_COVERAGE >= 0.95`
- `CLOUD_COVER` 尽量低

如果没有候选满足条件，不应导出 partial 或 cloudy sample。应调整时间范围或 small ROI。

## 导出内容

脚本创建 4 个导出任务：

```text
stage6_5_clean_single_l8_l2sr_b4_red
stage6_5_clean_single_l8_l2sr_b5_nir
stage6_5_clean_single_l8_l2sr_qa_pixel
stage6_5_clean_single_l8_l2sr_metadata
```

导出数据：

- scaled SR_B4 red reflectance
- scaled SR_B5 NIR reflectance
- raw `QA_PIXEL`
- metadata CSV

Surface Reflectance scale：

```text
reflectance = DN * 0.0000275 - 0.2
```

metadata CSV 包含：

- image_id
- date
- CLOUD_COVER
- SUN_AZIMUTH
- SUN_ELEVATION
- WRS_PATH
- WRS_ROW
- ROI_GEOM_COVERAGE
- VALID_PIXEL_COVERAGE
- large ROI bounds
- small ROI bounds
- export CRS / scale
- source collection
- date filter
- SR scale formula
- QA excluded bits

## 地图检查

GEE Map 显示：

- original large ROI：黄色线框
- selected small ROI：红色线框
- candidate footprints：青色线框
- selected image footprint：蓝色线框
- selected scaled B4 preview
- selected scaled B5 preview
- selected NDVI preview

## Export Safety Check

在 GEE 中运行脚本后，先检查 Console：

- candidate summary table 是否存在。
- selected image metadata 是否非空。
- `ROI_GEOM_COVERAGE >= 0.95`。
- `VALID_PIXEL_COVERAGE >= 0.90`，最好 `>= 0.95`。
- `SUN_AZIMUTH` 和 `SUN_ELEVATION` 是否存在。

只有这些条件满足时，才点击右侧 Tasks 的 Run。

## 下载后建议放置位置

导出并下载后，建议放入：

```text
stage6_5_real_landsat_observation_stress_test/data/
```

建议文件名：

```text
stage6_5_clean_single_l8_l2sr_b4_red.tif
stage6_5_clean_single_l8_l2sr_b5_nir.tif
stage6_5_clean_single_l8_l2sr_qa_pixel.tif
stage6_5_clean_single_l8_l2sr_metadata.csv
```

如果 GEE 自动增加后缀或分片编号，先保留原始下载文件名，并在后续 Stage 6.5.2 数据体检中记录。

## 当前阶段不做什么

- 不运行 Stage 6.5 主模型。
- 不做真实反演。
- 不做 Stage 7 多 ROI。
- 不做多景合成。
- 不训练 MAE / GeoAI。
- 不修改 Stage 1-6 数据。
- 不删除旧 Stage 3 composite。

## Stage 6.5.2 前置检查

下载完成后，下一步只应做数据体检：

- B4 / B5 / QA_PIXEL / metadata 是否齐全。
- B4 / B5 是否为 scaled reflectance。
- metadata 是否包含唯一太阳几何。
- QA_PIXEL 是否可解码。
- B4 / B5 / QA_PIXEL 是否同 CRS、transform、bounds、shape。
- 是否需要对齐到 DEM 网格。
