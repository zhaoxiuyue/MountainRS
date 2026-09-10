# DEM 地形因子 Synthetic Boundary Test 报告

## 目标

本测试不处理真实 DEM，只用极简合成 DEM 检查 `compute_terrain_factors.py` 中 slope、aspect、hillshade 的方向、单位和边界行为是否合理。

## 当前代码中的 aspect 定义

根据 `compute_terrain_factors.py` 的公式，当前 aspect 表示 **最大下降方向**，不是上坡梯度方向。方位约定为：

- `0/360 = 北`
- `90 = 东`
- `180 = 南`
- `270 = 西`

常数 DEM 上 slope 接近 0，aspect 没有实际物理意义；当前代码对平坦像元统一写为 `0`。

## 测试参数

- 合成 DEM 尺寸：`80 x 80`
- x/y resolution：`10.0m x 10.0m`
- 目标坡度：`10.0°`
- hillshade 太阳方位角：`315°`
- hillshade 太阳高度角：`45°`

## 边界测试结果

| Case | Expected Slope | Actual Slope Mean | Slope Std | Slope Status | Expected Aspect | Actual Aspect Mean | Aspect Std | Aspect Error | Aspect Status | Case Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 常数 DEM | 0.0 | 0.0000 | 0.0000 | PASS | 无实际物理意义，脚本统一为 0 | 0.0000 | 0.0000 | N/A | PASS | PASS |
| 东西向倾斜平面：西低东高 | 10.0 | 10.0000 | 0.0000 | PASS | 270.0 | 270.0000 | 0.0000 | 0.0000 | PASS | PASS |
| 南北向倾斜平面：南低北高 | 10.0 | 10.0000 | 0.0000 | PASS | 180.0 | 180.0000 | 0.0000 | 0.0000 | PASS | PASS |

## Hillshade 简单光照测试

太阳来自西北方 `315°`。如果 aspect 表示最大下降方向/坡面朝向，则 NW-facing 坡面应比 SE-facing 坡面更亮。

| Case | Expected Slope | Actual Slope Mean | Slope Std | Slope Status | Expected Aspect | Actual Aspect Mean | Aspect Std | Aspect Error | Aspect Status | Case Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hillshade 测试：坡面朝向/最大下降方向 NW | 10.0 | 10.0000 | 0.0000 | PASS | 315.0 | 315.0000 | 0.0000 | 0.0000 | PASS | PASS |
| hillshade 测试：坡面朝向/最大下降方向 SE | 10.0 | 10.0000 | 0.0000 | PASS | 135.0 | 135.0000 | 0.0000 | 0.0000 | PASS | PASS |

- NW-facing hillshade mean：`208.8838`
- SE-facing hillshade mean：`146.2620`
- mean difference：`62.6218`
- hillshade 光照直觉检查：**PASS**

## 可视化

- 边界测试预览图：`stages/stage2_dem_terrain/outputs/terrain_factor_boundary_test.png`

## PASS / WARNING / FAIL

- 常数 DEM：`PASS`
- 东西向倾斜平面：`PASS`
- 南北向倾斜平面：`PASS`
- hillshade 简单光照：`PASS`
- 总体结论：**PASS**

## 结论

- 常数 DEM 的 slope 接近 0；aspect 在平坦面没有实际物理意义，当前代码统一为 0。
- 西低东高的 DEM 得到 aspect 约 `270°`，说明当前 aspect 指向最大下降方向，即向西。
- 南低北高的 DEM 得到 aspect 约 `180°`，说明当前 aspect 指向最大下降方向，即向南。
- 在太阳方位角 `315°`、太阳高度角 `45°` 下，NW-facing 坡面显著亮于 SE-facing 坡面，hillshade 符合简单光照直觉。
- 未发现当前 aspect 定义与已有报告文字之间的不一致：已有报告写的是最大下降方向，与测试结果一致。
