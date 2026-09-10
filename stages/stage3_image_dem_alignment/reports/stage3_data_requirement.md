# Stage 3 数据需求说明

## Stage 3 目标

Stage 3｜DEM + 影像对齐闭环 的目标，是把一个光学遥感影像波段与 Stage 2 已生成的 DEM / slope / aspect / curvature 对齐到同一空间框架中。这里的“对齐”不是只看 shape 是否一样，而是要求 CRS、bounds、resolution、transform、nodata/mask 等空间语义能够被明确检查和处理。

本阶段当前只做项目准备和数据需求定义，不下载影像，不处理影像。

## 当前已有 DEM / 地形因子数据

Stage 2 已形成一个共同 DEM 网格框架：

- CRS：`EPSG:32648`
- resolution：`(27.6422871066m, 27.6422871066m)`
- shape：`(2867, 4179)`，格式为 `(height, width)`
- bounds：`left=289499.838109, bottom=3407878.491219, right=405016.955927, top=3487128.928354`
- transform：

```text
| 27.64, 0.00, 289499.84|
| 0.00,-27.64, 3487128.93|
| 0.00, 0.00, 1.00|
```

已有数据：

- DEM：`stages/stage2_dem_terrain/data/srtm_dem_utm48n.tif`
- slope：`stages/stage2_dem_terrain/outputs/slope_degree.tif`
- aspect：`stages/stage2_dem_terrain/outputs/aspect_degree.tif`
- curvature：`stages/stage2_dem_terrain/outputs/curvature.tif`

这些 Stage 2 产物已经共 CRS、共 bounds、共 resolution、共 transform、共 shape。

## 需要新增的影像数据类型

需要新增一个可作为 Stage 3 对齐测试输入的光学遥感影像 GeoTIFF。第一版只需要至少一个反射率 band，不需要一开始就引入完整多波段产品。

### 推荐第一版：Landsat Collection 2 Surface Reflectance

推荐第一版使用 Landsat Collection 2 Surface Reflectance。

理由：

- Landsat 反射率产品的 30m 分辨率与当前 DEM 的约 `27.64m` 接近，适合先做 DEM + 影像对齐闭环。
- 与 Sentinel-2 10m 产品相比，第一版重采样比例更温和，便于检查 CRS、bounds、transform 和 nodata/mask。
- Landsat Collection 2 Surface Reflectance 是已经过大气校正的地表反射率产品，更适合后续进入物理解释或地形校正前的准备。
- 第一版可选择单个反射率 band 作为 alignment smoke test，降低 Stage 3 的复杂度。

### 可选第二版：Sentinel-2 L2A

第二版可考虑 Sentinel-2 L2A。

理由：

- Sentinel-2 L2A 也是地表反射率产品，空间分辨率更高，适合更细致的山地影像分析。
- 10m/20m/60m 多分辨率 band 让后续多光谱分析更丰富。

复杂点：

- Sentinel-2 各 band 分辨率不一致，需要先决定使用 10m、20m 还是统一目标网格。
- 与约 27.64m DEM 对齐时，重采样策略更敏感。
- 云、阴影、SCL 分类、nodata/mask 和不同 tile 边界需要额外处理。
- 如果第一版直接使用 Sentinel-2，可能会把“影像产品复杂性”和“DEM 影像对齐逻辑”混在一起。

## 影像数据需要满足的条件

影像 GeoTIFF 至少需要满足：

1. 覆盖 DEM bounds 附近，最好与 DEM 空间范围有明确重叠。
2. 云量尽量低，避免 Stage 3 第一版被云/云影干扰。
3. 有 CRS。
4. 有 transform。
5. 有 nodata 或 mask 信息。
6. 至少包含一个可用于测试的反射率 band。

## 下一步要做的检查

拿到影像后，下一步检查顺序建议为：

1. 影像 GeoTIFF 体检：driver、CRS、transform、bounds、resolution、shape、dtype、nodata/mask、min/max/mean/std。
2. DEM 与影像 CRS 比较：确认是否同 CRS，或需要重投影。
3. bounds 是否重叠：确认影像与 DEM 是否覆盖同一区域。
4. resolution 是否一致：确认是否需要重采样。
5. transform 是否一致：即使 shape 一样，也要检查原点、像元大小、旋转项和行列方向。
6. 选择对齐策略：
   - 把影像重采样到 DEM 网格。
   - 或把 DEM / slope / aspect / curvature 重采样到影像网格。

## 本阶段暂不做

Stage 3 数据准备阶段暂不做：

1. 地形校正。
2. BRDF 校正。
3. 可微建模。
4. GeoAI。
5. SAR/InSAR。

## 建议的第一版输入清单

- 一个 Landsat Collection 2 Surface Reflectance 反射率 band GeoTIFF。
- 对应的 QA 或 cloud mask 文件，如果可用。
- 数据来源、下载时间、产品 ID、band 名称和缩放系数说明。
- 影像原始 CRS、bounds、resolution、transform、nodata/mask 记录。

## 暂定通关标准

Stage 3 第一版通关标准建议为：

- 影像 GeoTIFF 体检通过。
- 影像与 DEM bounds 有有效重叠。
- 明确选择并执行一种对齐策略。
- 对齐后的影像与目标 DEM/影像网格具有一致 CRS、transform、resolution、shape。
- 对齐报告中记录 nodata/mask 的传播方式。
- 输出一张 DEM / slope / aspect / image band 的组合预览图，用于人工检查空间对应关系。
