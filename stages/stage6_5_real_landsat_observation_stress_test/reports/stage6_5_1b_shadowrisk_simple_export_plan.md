# Stage 6.5.1-B｜Shadow-risk Single-scene Simple Export Plan

## 阶段定位

Stage 6.5.1-B 的目标是准备一个更可能包含 near-zero / shadow 危险域的单日 Landsat Collection 2 Level-2 Surface Reflectance 样本。

本阶段仍然不是 Stage 7：

- 不做多 ROI 留一验证
- 不做多景合成
- 不做 GeoAI / MAE
- 不进入真实反演
- 不运行 Stage 6.5.3 残差模型
- 不使用旧 Stage 3 composite
- 不修改 Stage 1-6 数据

## 为什么放弃复杂 GEE shadow-risk audit

复杂版 `gee_audit_shadow_risk_single_scene_l2sr.js` 试图在 GEE 中同时完成：

- 多 ROI 候选审计
- Landsat coverage / QA 统计
- DEM slope / aspect 计算
- 真实太阳角下的 `cos_i`
- near-zero / shadow ratio
- shadow-risk score

这条路线信息量大，但调试成本也高。GEE 中同时处理影像集合、多个 ROI、DEM 派生地形和 per-image 太阳角，容易把主要目标卡在脚本工程细节上。

当前主线先停止修复复杂 audit 脚本。该脚本保留为后续可参考的复杂审计草稿，但不再作为当前 Stage 6.5.1-B 的执行路线。

## 为什么改成 GEE 低太阳角筛选 + 本地 near-zero / shadow 检查

简化路线把任务拆开：

1. GEE 只负责找一个合法单日 Landsat L2 SR 样本。
2. 本地 Stage 6.5.2-B 再用项目已有 DEM / slope / aspect 计算 `cos_i`、confidence、near-zero mask 和 shadow mask。

这样分工更清楚：

- GEE 擅长筛选 Landsat scene、读取 metadata、解析 `QA_PIXEL`、导出小 ROI GeoTIFF。
- 本地脚本更适合复用 Stage 4 / Stage 5 已验证过的 `cos_i` 与 confidence 逻辑。
- near-zero / shadow 是否足够明显，不在 GEE 中预判，而在本地用同一套项目物理约定判定。

## 当前 A 样本封存为 clean high-sun baseline

Stage 6.5.2-A 已完成的 clean single-scene L2 SR 样本保留为：

**clean high-confidence baseline sample**

它的关键特征是：

- near-zero ratio ≈ `0.0006%`
- shadow ratio = `0%`
- confidence mean ≈ `0.999992`
- solar elevation ≈ `62.94°`

因此 A 样本适合证明：

- 单日 Landsat L2 SR 数据包可以被本地读取
- `QA_PIXEL` 可以解析
- DEM / slope / aspect 可以对齐到 Landsat 小 ROI 网格
- 真实太阳角下的 `cos_i` 与 confidence 字段可以生成

但它不适合继续作为 shadow mechanism test 样本。

## B 样本目标

B 样本定位为：

**shadow-risk candidate sample**

它的目标不是保证一定包含强阴影，而是通过低太阳高度和山地小 ROI 提高 near-zero / shadow 危险域出现的概率。

当前 GEE 脚本：

```text
stage6_5_real_landsat_observation_stress_test/scripts/gee_export_shadow_risk_single_scene_l2sr_simple.js
```

数据源：

```text
LANDSAT/LC08/C02/T1_L2
```

时间范围：

```text
2022-10-01 到 2024-03-31
```

主 small ROI：

```text
ROI_MTN_NW = [102.82, 31.18, 103.02, 31.38]
```

备用 ROI：

```text
ROI_MTN_W  = [102.88, 30.95, 103.08, 31.15]
ROI_MTN_C  = [103.00, 31.05, 103.20, 31.25]
ROI_MTN_SW = [102.82, 30.82, 103.02, 31.02]
```

## GEE 筛选逻辑

GEE 脚本只检查：

- `ROI_GEOM_COVERAGE >= 0.95`
- `VALID_PIXEL_COVERAGE >= 0.80`
- `VALID_PIXEL_COVERAGE` 基于 `QA_PIXEL`，排除 fill、dilated cloud、cirrus、cloud、cloud shadow、snow
- `SR_B4` / `SR_B5` 同时有效
- 合格候选中按 `SUN_ELEVATION` 升序排序，优先选择太阳高度最低的一景

如果最低太阳高度候选视觉上云太多，可以人工对比 `CLOUD_COVER` 后选择更合适的一景。

## 导出内容

导出文件名前缀使用 B 后缀语义，避免覆盖 A 样本：

```text
stage6_5_shadowrisk_single_scene_l8_l2sr_b4_red
stage6_5_shadowrisk_single_scene_l8_l2sr_b5_nir
stage6_5_shadowrisk_single_scene_l8_l2sr_qa_pixel
stage6_5_shadowrisk_single_scene_l8_l2sr_metadata
```

其中：

- `SR_B4` / `SR_B5` 已在 GEE 中转换为 scaled reflectance：

```text
reflectance = DN * 0.0000275 - 0.2
```

- `QA_PIXEL` 保留原始 bit mask。
- metadata CSV 包含 image id、date、cloud、sun azimuth/elevation、WRS、coverage、ROI bounds、导出 CRS 和 scale。

## 下一步

下载完成后，进入 Stage 6.5.2-B：

1. 本地体检 B4 / B5 / QA / metadata。
2. 检查 B4 / B5 / QA 是否同网格。
3. 将 DEM / slope / aspect 对齐到 B 样本 Landsat grid。
4. 使用 metadata 中真实 `SUN_AZIMUTH` / `SUN_ELEVATION` 计算 `cos_i`。
5. 输出 near-zero ratio、shadow ratio、confidence 和 QA valid mask。
6. 判断 B 样本是否真的适合进入 shadow mechanism stress test。

只有当 B 样本在本地 Stage 6.5.2-B 中显示 near-zero / shadow 危险域明显高于 A 样本，才考虑进入后续 Stage 6.5.3。
