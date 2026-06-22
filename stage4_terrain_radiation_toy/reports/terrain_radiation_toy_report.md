# 地形辐射 Toy Model 报告

## 输入文件

- DEM：`/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/data/srtm_dem_utm48n.tif`
- slope：`/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/slope_degree.tif`
- aspect：`/Users/zhaoxiuyue/MountainRS/stage2_dem_terrain/outputs/aspect_degree.tif`

## DEM Grid

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

## Slope / Aspect 约定

- slope 单位：degree
- aspect 来自 Stage 2，表示最大下降方向
- aspect 方位约定：`0/360 = 北，90 = 东，180 = 南，270 = 西`

## 太阳参数

- solar azimuth：`315.0°`，表示光源来自西北
- solar elevation：`45.0°`
- solar zenith：`45.0°`
- constant albedo：`0.3`

## 公式

```text
cos_i = cos(slope) * cos(zenith)
      + sin(slope) * sin(zenith) * cos(solar_azimuth - aspect)

observed_brightness = albedo * max(cos_i, 0)
shadow_mask = cos_i <= 0
corrected_albedo = observed_brightness / cos_i, only where cos_i > 0.1
```

角度在计算前全部转换为 radians。

## 统计结果

| 数据 | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cos_i | -0.632178 | 0.999999 | 0.588442 | 0.272466 | 11592772 | 11981193 | 3.2419% |
| shadow_mask | 0.000000 | 1.000000 | 0.021537 | 0.145166 | 11592772 | 11981193 | 3.2419% |
| observed_brightness | 0.000000 | 0.300000 | 0.177147 | 0.080207 | 11592772 | 11981193 | 3.2419% |
| corrected_albedo | 0.300000 | 0.300000 | 0.300000 | 0.000000 | 10980734 | 11981193 | 8.3502% |

## Shadow / Invalid Correction

- shadow ratio：`2.1537%`
- invalid correction ratio：`5.2795%`
- shadow 区域：`cos_i <= 0`
- invalid correction 区域：`cos_i <= 0.1`，包括背阴坡和入射角接近 90° 的区域
- corrected_albedo 是否接近输入 albedo=`0.3`：**PASS**，mean=`0.300000`

## 为什么 cos_i 接近 0 时不能直接除

当 `cos_i` 接近 0 时，`observed_brightness / cos_i` 会把非常小的噪声或数值误差放大成巨大值。背阴坡或接近掠射光照的区域，直接除以 `cos_i` 不再是稳定的物理校正，而是数值爆炸风险。因此本 toy model 明确把 `cos_i <= 0.1` 作为失效域，不硬校正。

## 为什么这不是完整地形校正

- 只包含朗伯、单光源和直接光项。
- 没有真实太阳几何随时间/影像变化的 metadata。
- 没有天空散射、邻近地形反射、阴影投射、BRDF、地表各向异性或大气效应。
- 使用常数 albedo，不代表真实地表材料差异。
- 当前 Landsat 是 2023-2024 median composite，不是单日影像，不适合直接做单日物理地形校正。

## 正确性闸门

1. 平地 slope=0 时，cos_i 理论上应等于 cos(zenith)：**PASS**，cos(zenith)=`0.707107`
2. 坡面 aspect 接近 solar azimuth 且坡度适中时，cos_i 应较大：**PASS**，30° facing cos_i=`0.965926`
3. 背光坡 cos_i <= 0 时应进入 shadow_mask：**PASS**，60° back-facing cos_i=`-0.258819`
4. 常数 albedo=0.3 时，非阴影区 corrected_albedo 应恢复到约 0.3：**PASS**
5. cos_i <= 0.1 区域不应硬校正：**PASS**
6. observed_brightness 的亮暗结构应主要来自地形光照，而不是地表属性变化，因为 albedo 是常数：**PASS**，本模型未引入空间变化 albedo。

## 输出文件

- `cos_i.tif`：`/Users/zhaoxiuyue/MountainRS/stage4_terrain_radiation_toy/outputs/cos_i.tif`
- `shadow_mask.tif`：`/Users/zhaoxiuyue/MountainRS/stage4_terrain_radiation_toy/outputs/shadow_mask.tif`
- `observed_brightness_toy.tif`：`/Users/zhaoxiuyue/MountainRS/stage4_terrain_radiation_toy/outputs/observed_brightness_toy.tif`
- `corrected_albedo_toy.tif`：`/Users/zhaoxiuyue/MountainRS/stage4_terrain_radiation_toy/outputs/corrected_albedo_toy.tif`
- preview：`/Users/zhaoxiuyue/MountainRS/stage4_terrain_radiation_toy/outputs/terrain_radiation_toy_preview.png`

## 本次未做

- 未使用 Landsat B4/B5 做真实校正。
- 未改写 Stage 2 或 Stage 3 数据。
- 未进入可微模型。
