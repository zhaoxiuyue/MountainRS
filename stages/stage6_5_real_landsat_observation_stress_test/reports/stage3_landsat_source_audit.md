# Stage 6.5.0｜Stage 3 Landsat 数据源审计

## 审计目标

本审计只回答一个问题：Stage 3 已经对齐到 DEM 网格的 B4 / B5 / NDVI 到底来自什么数据源，以及它是否适合做单日物理地形验证。

本阶段没有运行 Stage 6.5 主模型，没有下载新影像，没有进入 Stage 7 多 ROI 留一验证，也没有修改 Stage 1-6 的数据。

## 执行的项目搜索

已在项目根目录执行关键词搜索：

```bash
rg -n "LANDSAT|LC08|C02|T1_L2|T1_TOA|SR_B4|SR_B5|QA_PIXEL|median\\(|mosaic\\(|mean\\(|qualityMosaic|filterDate|SUN_AZIMUTH|SUN_ELEVATION|Export.image|stage3_landsat|landsat_composite" .
```

补充搜索了 Stage 3 相关文件、GEE / export / metadata / composite / 2023 / 2024 等关键词。

## 找到的 Stage 3 源代码 / 报告文件

### Stage 3 本地脚本

- `stage3_image_dem_alignment/scripts/check_landsat_and_dem_spatial_match.py`
  - 作用：读取本地 B4 / B5 GeoTIFF，做 GeoTIFF 体检、B4/B5 同网格检查、Landsat 与 DEM 空间关系检查。
  - 不包含 GEE collection、filterDate、median、mosaic、Export.image 或 QA_PIXEL 导出逻辑。

- `stage3_image_dem_alignment/scripts/align_landsat_to_dem_grid.py`
  - 作用：把本地 B4 / B5 重采样到 DEM 网格，并计算带 mask 的 NDVI。
  - 不包含 GEE collection、filterDate、median、mosaic、Export.image 或 QA_PIXEL 导出逻辑。

### Stage 3 本地报告

- `stage3_image_dem_alignment/reports/stage3_data_requirement.md`
  - 说明第一版推荐 Landsat Collection 2 Surface Reflectance。
  - 明确建议保存数据来源、产品 ID、band 名称和缩放系数，但当前项目中未找到对应 Stage 3 原始 metadata 文件。

- `stage3_image_dem_alignment/reports/landsat_dem_spatial_check_report.md`
  - 记录输入文件：
    - `stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b4_red.tif`
    - `stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b5_nir.tif`
  - 记录 B4/B5 为 `EPSG:32648`、`30m`、同 transform / bounds / shape。
  - 记录 B4/B5 为 `float64`，nodata 为 `None`，存在 NaN mask。

- `stage3_image_dem_alignment/reports/landsat_to_dem_alignment_report.md`
  - 记录原始 B4/B5 的 30m 网格。
  - 记录 aligned B4/B5/NDVI 已对齐到 DEM 网格。
  - 记录 aligned NDVI 使用 denominator 阈值和反射率有效范围 mask。

- `stage3_image_dem_alignment/reports/stage3_obsidian_closure_report.md`
  - 记录 Stage 3.1 和 Stage 3.2 已完成。
  - 记录进入后续阶段前需要确认是否从 Landsat metadata 或 GEE 导出太阳方位角、太阳高度角。

### Stage 3 Obsidian / 正式卡片

- `MRS Obsidian/Mountain RS Foundation Project/01_Stage_Index/Stage 3｜DEM + 影像对齐闭环.md`
  - 描述 Stage 3 使用 Landsat Collection 2 Surface Reflectance 的 B4 Red、B5 NIR。
  - 记录当前已形成 `elevation/slope/aspect/curvature/B4/B5/NDVI` 的 L0 aligned data stack。
  - 明确 Stage 3 不代表地形校正、BRDF 校正或真实太阳几何解释。

- `MRS Obsidian/Mountain RS Foundation Project/04_Results/Result_Landsat_影像体检与DEM空间检查_01.md`
  - 描述输入为 GEE 导出的 Landsat Collection 2 Surface Reflectance B4/B5 GeoTIFF。

- `MRS Obsidian/Mountain RS Foundation Project/04_Results/Result_Landsat_对齐到DEM网格_01.md`
  - 记录 B4/B5 已对齐到 DEM 网格，并说明这只是空间框架统一。

### 未找到的关键文件

- 未找到 Stage 3 原始 GEE export script。
- 未找到 Stage 3 metadata CSV。
- 未找到 Stage 3 QA_PIXEL GeoTIFF。
- 未找到包含 `LANDSAT/LC08/C02/T1_L2`、`filterDate`、`median()`、`Export.image` 的 Stage 3 导出记录。

**Stage 3 original GEE export script not found in current project search; current data source description must be treated as unverified until the script or export metadata is recovered.**

## 审计问答

### 1. 找到了哪些 Stage 3 源代码/报告文件？

找到了两个 Stage 3 Python 脚本和四个 Stage 3 报告：

- `check_landsat_and_dem_spatial_match.py`
- `align_landsat_to_dem_grid.py`
- `stage3_data_requirement.md`
- `landsat_dem_spatial_check_report.md`
- `landsat_to_dem_alignment_report.md`
- `stage3_obsidian_closure_report.md`

也找到了 Stage 3 Obsidian Stage Index、Result Cards 和 Code Templates。

未找到 Stage 3 原始 GEE 导出脚本。

### 2. Stage 3 使用哪个 GEE collection？

本地 Stage 3 文档描述为 Landsat Collection 2 Surface Reflectance，但没有找到原始 GEE 脚本或 metadata 来确认具体 collection ID。

因此不能严格确认是：

- `LANDSAT/LC08/C02/T1_L2`
- `LANDSAT/LC09/C02/T1_L2`
- 或其他 Landsat C2 SR collection

当前只能写为：**项目文档描述为 Landsat Collection 2 Surface Reflectance，但 collection ID 未被本地原始导出脚本验证。**

### 3. 是 Level-2 Surface Reflectance 还是 TOA？

Stage 3 文件名包含 `sr`，报告与 Obsidian 卡片均描述为 Surface Reflectance；反射率值也表现为 scaled reflectance 型浮点值。

但由于未找到原始 GEE 脚本和 metadata，严格证据级别应为：

- **倾向判断：Level-2 Surface Reflectance**
- **未验证：具体 collection ID 与导出缩放流程**

未发现 `T1_TOA` 相关 Stage 3 证据。

### 4. 是 single scene、median composite、mosaic、mean composite，还是其他方式？

本地 Stage 3 输入文件名为：

- `stage3_landsat_composite_sr_b4_red.tif`
- `stage3_landsat_composite_sr_b5_nir.tif`

后续 Stage 4 / Stage 6 相关正式笔记中明确记录“当前 Landsat composite 是 2023-2024 median composite，不适合直接做单日物理地形校正”。

但是本次项目搜索没有找到 Stage 3 原始 GEE 脚本中的 `median()`、`mosaic()`、`mean()` 或 `qualityMosaic()` 调用。

审计结论：

- **项目知识库描述：2023-2024 median composite**
- **脚本级证据：未找到**
- **不能视为 single scene**

### 5. filterDate 起止时间是什么？

Stage 3 原始 GEE export script not found。

当前项目搜索未找到 Stage 3 对应的 `filterDate` 起止时间。

只能确认后续笔记描述为 2023-2024 composite，但不能确认精确 start / end date。

### 6. exported bands 是哪些？

本地 Stage 3 数据明确存在：

- B4 red：`stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b4_red.tif`
- B5 NIR：`stage3_image_dem_alignment/data/stage3_landsat_composite_sr_b5_nir.tif`

Stage 3 本地脚本进一步生成：

- aligned B4：`stage3_image_dem_alignment/outputs/landsat_b4_red_aligned_to_dem.tif`
- aligned B5：`stage3_image_dem_alignment/outputs/landsat_b5_nir_aligned_to_dem.tif`
- aligned NDVI：`stage3_image_dem_alignment/outputs/ndvi_aligned_to_dem.tif`

NDVI 是本地用 B5 / B4 计算的派生结果，不是 GEE 原始导出 band。

### 7. 是否使用 QA/cloud mask？

未找到 Stage 3 `QA_PIXEL` 文件。

未找到 Stage 3 原始 GEE 脚本中的 QA/cloud mask 逻辑。

Stage 3 本地处理使用的是：

- NaN / finite mask
- 反射率范围 mask
- NDVI denominator 阈值

这些是数值有效性 mask，不等价于 QA_PIXEL 的云、云影、雪、水体或填充值质量掩膜。

### 8. 是否做了 Landsat C2 L2 scale：reflectance = DN * 0.0000275 - 0.2？

Stage 3 本地报告显示 B4/B5 已经是浮点反射率，且数值范围接近 Surface Reflectance。

但未找到 Stage 3 原始 GEE 脚本或 metadata 来确认是否在 GEE 端执行了：

```text
reflectance = DN * 0.0000275 - 0.2
```

审计结论：

- **结果表现：像 scaled reflectance**
- **导出流程：未验证**

### 9. 是否存在唯一 SUN_AZIMUTH / SUN_ELEVATION？

未找到 Stage 3 metadata CSV。

未找到 Stage 3 原始 GEE 脚本中的 `SUN_AZIMUTH` 或 `SUN_ELEVATION` 导出。

如果 Stage 3 确实是 2023-2024 median composite，则它天然不对应唯一单日太阳几何。

审计结论：**不存在可验证的唯一 SUN_AZIMUTH / SUN_ELEVATION。**

### 10. 它是否适合单日物理地形校正？

不适合。

原因：

- 本地证据显示 Stage 3 是 composite，而不是 single scene。
- 未找到唯一 `SUN_AZIMUTH` / `SUN_ELEVATION`。
- 未找到 QA_PIXEL / cloud mask 导出。
- 未找到原始 GEE 脚本验证 scale、filterDate 和 composite 方法。
- 多日期 composite 的亮度不对应单日太阳-地形几何关系。

因此 Stage 3 aligned B4/B5/NDVI 不能作为单日物理地形校正或单日 local incidence angle 验证输入。

### 11. 它是否适合 real-observation stress test？

适合，但只能作为**弱 stress test / failure-awareness test**，不能作为单日物理验证。

可用方向：

- 检查真实 Landsat-like reflectance 与 DEM / slope / aspect / curvature 对齐后的统计关系。
- 测试 NDVI mask、反射率范围 mask、nodata 传播和对齐稳定性。
- 测试模型在“不具备单日太阳几何”的真实 composite 上是否会产生过度解释。
- 作为 hallucination risk 的反例：如果模型声称能从该 composite 做单日物理校正，应被标记为高风险。

不可用方向：

- 不可用于验证单日 `cos_i` 物理光照关系。
- 不可用于真实单日 terrain correction。
- 不可用于估计真实 albedo。
- 不可用于训练或评价 MAE / GeoAI 业务模型。

### 12. 可用于第二篇正文的一句话结论

Stage 3 的 Landsat B4/B5/NDVI 已完成与 DEM 地形栈的空间对齐，但其原始 GEE 导出脚本和太阳几何 metadata 未在项目中恢复，且项目记录表明它是多日期 median composite，因此它只能用于真实观测压力测试与幻觉风险暴露，不能作为单日物理地形校正验证样本。

## 证据摘要

| 项目 | 审计结果 | 证据强度 |
|---|---|---|
| B4/B5 文件存在 | 是 | 强 |
| B4/B5 已对齐到 DEM 网格 | 是 | 强 |
| 输入是 Landsat SR | 项目文档如此描述 | 中 |
| 具体 GEE collection ID | 未找到 | 弱 / 未验证 |
| 是否 TOA | 未发现 TOA 证据 | 中 |
| 是否 median composite | 项目笔记记录为 2023-2024 median composite | 中 |
| 精确 filterDate | 未找到 | 未验证 |
| 是否使用 QA_PIXEL | 未找到 | 未验证 / 倾向否 |
| 是否导出唯一太阳几何 | 未找到 | 否 |
| 是否适合单日物理地形校正 | 不适合 | 强 |
| 是否适合 real-observation stress test | 适合弱 stress test | 中到强 |

## 后续建议

- 如果要做单日物理验证，必须恢复或重新生成单日 Landsat export script，并导出 B4/B5、QA_PIXEL、metadata CSV、`SUN_AZIMUTH`、`SUN_ELEVATION`。
- 如果继续使用 Stage 3 composite，应明确标注为 real-observation stress test，而不是 physical correction validation。
- Stage 6.5 后续可以专门测试：模型是否会在缺少唯一太阳几何和 QA_PIXEL 的情况下产生过度自信输出。
- 不应把 Stage 3 aligned NDVI 与 LAI、albedo 或单日地形校正结果直接等同。
