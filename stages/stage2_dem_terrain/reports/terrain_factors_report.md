# DEM 地形因子计算报告

## 输入 DEM

- 输入 DEM 路径：`stages/stage2_dem_terrain/data/srtm_dem_utm48n.tif`
- CRS：`EPSG:32648`
- resolution：`(27.6422871066, 27.6422871066)`，单位为米
- shape：`(2867, 4179)`，格式为 `(height, width)`
- nodata：`-32768.0`
- aspect 约定：`0/360 = 北，90 = 东，180 = 南，270 = 西`；平坦像元的 aspect 在本脚本中记为 0，但其方向没有实际物理意义。
- hillshade 参数：太阳方位角 `315°`，太阳高度角 `45°`。
- curvature 说明：本次 curvature 使用 DEM 二阶梯度和 `d2z/dx2 + d2z/dy2` 的简化近似，只是 toy/basic curvature，不是完整地貌学曲率体系。

## 统计结果

| 数据 | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEM | 522.0000 | 6022.0000 | 2523.1099 | 1316.8339 | 11620222 | 11981193 | 3.0128% |
| slope_degree | 0.0000 | 87.0913 | 27.7093 | 14.9133 | 11592772 | 11981193 | 3.2419% |
| aspect_degree | 0.0000 | 359.8539 | 172.0215 | 102.0404 | 11592772 | 11981193 | 3.2419% |
| curvature | -0.6868 | 1.0519 | -0.0000 | 0.0089 | 11592772 | 11981193 | 3.2419% |

## 输出文件列表

- `stages/stage2_dem_terrain/outputs/slope_degree.tif`
- `stages/stage2_dem_terrain/outputs/aspect_degree.tif`
- `stages/stage2_dem_terrain/outputs/curvature.tif`
- `stages/stage2_dem_terrain/outputs/hillshade.png`
- `stages/stage2_dem_terrain/outputs/terrain_factors_preview.png`
- `stages/stage2_dem_terrain/reports/terrain_factors_report.md`
- `stages/stage2_dem_terrain/obsidian_drafts/Result_DEM_地形因子实验_01.md`

## 地形因子的物理意义

- slope：坡度，表示地表相对水平面的倾斜角，单位为 degree；越大代表地形越陡。
- aspect：坡向，表示最大下降方向的方位角；本报告采用 0/360 为北、90 为东、180 为南、270 为西的约定。
- curvature：简化曲率，反映高程面的二阶变化趋势；正负值可辅助观察凸/凹变化，但本次不是完整地貌学曲率分类。
- hillshade：山体阴影，用固定太阳位置模拟光照，帮助观察山脊、沟谷和坡面明暗结构。

## 正确性闸门

1. 输入 CRS 是否为 EPSG:32648：**满足**
2. resolution 是否为米级：**满足**
3. slope 是否大致在 0-90 度：**满足**
4. aspect 是否大致在 0-360 度：**满足**
5. nodata 是否未参与统计：**满足**
6. hillshade 是否显示出合理的山脊/沟谷明暗结构：**满足**。自动检查依据为 hillshade 有效像元 std = `68.1755`，并已生成 PNG 供人工查看。
7. 常数平面边界测试说明：如果 DEM 是常数平面，理论上 dz/dx 和 dz/dy 应接近 0，因此 slope 应接近 0；该边界测试后续可单独构造一个常数 DEM 再验证。

## 结论

- 输入 DEM 已是 EPSG:32648 米制 CRS，适合进行基于距离单位的地形因子计算。
- slope、aspect、basic curvature 和 hillshade 已生成；本次未进入影像对齐。
