"""
Stage 3.2 Landsat 对齐到 DEM 网格

本脚本只做 L0 多源对齐：
- 把 Landsat B4/B5 重采样到 DEM 网格
- 在 DEM 网格上计算 NDVI
- 不重采样 DEM
- 不改写 DEM 或地形因子
- 不进入地形校正、BRDF 或可微模型

运行方式：
python3 stage3_image_dem_alignment/scripts/align_landsat_to_dem_grid.py
"""

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT_DIR / "outputs" / ".matplotlib"))

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
    from rasterio.warp import Resampling, reproject
except ImportError as exc:
    raise SystemExit(
        "缺少依赖，请先安装：pip install rasterio numpy matplotlib"
    ) from exc


DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
REPORT_PATH = ROOT_DIR / "reports" / "landsat_to_dem_alignment_report.md"
PREVIEW_PATH = OUTPUT_DIR / "alignment_preview.png"
OBSIDIAN_DRAFT_PATH = ROOT_DIR / "obsidian_drafts" / "Result_Landsat_对齐到DEM网格_01.md"

STAGE2_DIR = ROOT_DIR.parent / "stage2_dem_terrain"
DEM_PATH = STAGE2_DIR / "data" / "srtm_dem_utm48n.tif"
SLOPE_PATH = STAGE2_DIR / "outputs" / "slope_degree.tif"
ASPECT_PATH = STAGE2_DIR / "outputs" / "aspect_degree.tif"
CURVATURE_PATH = STAGE2_DIR / "outputs" / "curvature.tif"

B4_ALIGNED_PATH = OUTPUT_DIR / "landsat_b4_red_aligned_to_dem.tif"
B5_ALIGNED_PATH = OUTPUT_DIR / "landsat_b5_nir_aligned_to_dem.tif"
NDVI_ALIGNED_PATH = OUTPUT_DIR / "ndvi_aligned_to_dem.tif"

OUTPUT_NODATA = np.float32(-9999.0)
REFLECTANCE_MIN = -0.05
REFLECTANCE_MAX = 1.0
NDVI_DENOMINATOR_THRESHOLD = 0.05


def find_landsat_band(data_dir: Path, band_token: str, alias: str) -> Path:
    candidates = sorted(
        [
            path
            for path in list(data_dir.glob("*.tif")) + list(data_dir.glob("*.tiff"))
            if band_token.lower() in path.name.lower() or alias.lower() in path.name.lower()
        ]
    )
    if not candidates:
        raise FileNotFoundError(f"未在 {data_dir} 找到 {band_token}/{alias} 对应的 GeoTIFF。")
    if len(candidates) > 1:
        preferred = [path for path in candidates if band_token.lower() in path.name.lower()]
        if len(preferred) == 1:
            return preferred[0]
        raise FileExistsError(f"找到多个 {band_token}/{alias} 候选文件：{candidates}")
    return candidates[0]


def build_valid_mask(array: np.ndarray, nodata) -> np.ndarray:
    valid_mask = np.isfinite(array)
    if nodata is not None:
        if np.issubdtype(array.dtype, np.floating) and np.isnan(nodata):
            valid_mask &= ~np.isnan(array)
        else:
            valid_mask &= array != nodata
    return valid_mask


def build_reflectance_mask(array: np.ndarray, nodata) -> np.ndarray:
    valid_mask = build_valid_mask(array, nodata)
    valid_mask &= array >= REFLECTANCE_MIN
    valid_mask &= array <= REFLECTANCE_MAX
    return valid_mask


def compute_stats(array: np.ndarray, nodata) -> dict:
    valid_mask = build_valid_mask(array, nodata)
    total_count = int(array.size)
    valid_count = int(valid_mask.sum())
    nan_count = int(np.isnan(array).sum()) if np.issubdtype(array.dtype, np.floating) else 0
    inf_count = int(np.isinf(array).sum()) if np.issubdtype(array.dtype, np.floating) else 0
    nodata_ratio = (total_count - valid_count) / total_count if total_count else 0.0

    if valid_count == 0:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "valid_pixel_count": valid_count,
            "total_pixel_count": total_count,
            "nodata_ratio": nodata_ratio,
            "nan_count": nan_count,
            "inf_count": inf_count,
        }

    valid_pixels = array[valid_mask].astype("float64", copy=False)
    return {
        "min": float(valid_pixels.min()),
        "max": float(valid_pixels.max()),
        "mean": float(valid_pixels.mean()),
        "std": float(valid_pixels.std()),
        "valid_pixel_count": valid_count,
        "total_pixel_count": total_count,
        "nodata_ratio": nodata_ratio,
        "nan_count": nan_count,
        "inf_count": inf_count,
    }


def read_summary(path: Path) -> dict:
    with rasterio.open(path) as src:
        array = src.read(1)
        return {
            "path": path,
            "crs": src.crs,
            "transform": src.transform,
            "resolution": src.res,
            "bounds": src.bounds,
            "shape": (src.height, src.width),
            "width": src.width,
            "height": src.height,
            "nodata": src.nodata,
            "dtype": src.dtypes[0],
            "profile": src.profile.copy(),
            "array": array,
            "stats": compute_stats(array, src.nodata),
        }


def fmt(value) -> str:
    return "N/A" if value is None else f"{value:.6f}"


def fmt_resolution(resolution) -> str:
    return f"({resolution[0]:.10f}, {resolution[1]:.10f})"


def fmt_bounds(bounds) -> str:
    return (
        f"left={bounds.left:.6f}, bottom={bounds.bottom:.6f}, "
        f"right={bounds.right:.6f}, top={bounds.top:.6f}"
    )


def fmt_transform(transform) -> str:
    return (
        f"| {transform.a:.10f}, {transform.b:.10f}, {transform.c:.10f}|\n"
        f"| {transform.d:.10f}, {transform.e:.10f}, {transform.f:.10f}|\n"
        f"| 0.0000000000, 0.0000000000, 1.0000000000|"
    )


def transforms_equal(transform_a, transform_b, tolerance: float = 1e-6) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(transform_a[:6], transform_b[:6]))


def bounds_equal(bounds_a, bounds_b, tolerance: float = 1e-3) -> bool:
    return (
        abs(bounds_a.left - bounds_b.left) <= tolerance
        and abs(bounds_a.right - bounds_b.right) <= tolerance
        and abs(bounds_a.top - bounds_b.top) <= tolerance
        and abs(bounds_a.bottom - bounds_b.bottom) <= tolerance
    )


def close_pair(pair_a, pair_b, tolerance: float = 1e-6) -> bool:
    return abs(pair_a[0] - pair_b[0]) <= tolerance and abs(pair_a[1] - pair_b[1]) <= tolerance


def write_raster(path: Path, array: np.ndarray, dem_summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = dem_summary["profile"].copy()
    profile.update(
        {
            "driver": "GTiff",
            "height": dem_summary["height"],
            "width": dem_summary["width"],
            "count": 1,
            "dtype": "float32",
            "nodata": float(OUTPUT_NODATA),
            "compress": "lzw",
        }
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype("float32", copy=False), 1)


def align_band_to_dem(source_summary: dict, dem_summary: dict) -> np.ndarray:
    source_array = source_summary["array"].astype("float32", copy=True)
    source_mask = build_reflectance_mask(source_array, source_summary["nodata"])
    source_array[~source_mask] = OUTPUT_NODATA

    destination = np.full(
        (dem_summary["height"], dem_summary["width"]),
        OUTPUT_NODATA,
        dtype="float32",
    )

    reproject(
        source=source_array,
        destination=destination,
        src_transform=source_summary["transform"],
        src_crs=source_summary["crs"],
        src_nodata=float(OUTPUT_NODATA),
        dst_transform=dem_summary["transform"],
        dst_crs=dem_summary["crs"],
        dst_nodata=float(OUTPUT_NODATA),
        resampling=Resampling.bilinear,
    )

    aligned_mask = build_reflectance_mask(destination, OUTPUT_NODATA)
    destination[~aligned_mask] = OUTPUT_NODATA
    return destination


def compute_ndvi_aligned(b4: np.ndarray, b5: np.ndarray) -> tuple[np.ndarray, dict]:
    b4_valid = build_reflectance_mask(b4, OUTPUT_NODATA)
    b5_valid = build_reflectance_mask(b5, OUTPUT_NODATA)

    denominator = b5.astype("float64") + b4.astype("float64")
    valid_mask = b4_valid & b5_valid
    valid_mask &= np.isfinite(denominator)
    valid_mask &= np.abs(denominator) > NDVI_DENOMINATOR_THRESHOLD

    ndvi_float = np.full(b4.shape, np.nan, dtype="float64")
    ndvi_float[valid_mask] = (b5[valid_mask].astype("float64") - b4[valid_mask].astype("float64")) / denominator[valid_mask]
    valid_mask &= np.isfinite(ndvi_float)
    valid_mask &= ndvi_float >= -1.0
    valid_mask &= ndvi_float <= 1.0

    ndvi = np.full(b4.shape, OUTPUT_NODATA, dtype="float32")
    ndvi[valid_mask] = ndvi_float[valid_mask].astype("float32")
    return ndvi, {
        "denominator_filtered_count": int((b4_valid & b5_valid & (np.abs(denominator) <= NDVI_DENOMINATOR_THRESHOLD)).sum()),
        "physical_range_filtered_count": int(((b4_valid & b5_valid) & np.isfinite(ndvi_float) & ((ndvi_float < -1.0) | (ndvi_float > 1.0))).sum()),
    }


def aligned_summary(path: Path) -> dict:
    return read_summary(path)


def status(ok: bool) -> str:
    return "PASS" if ok else "WARNING"


def stats_row(label: str, summary: dict) -> str:
    stats = summary["stats"]
    return (
        f"| {label} | `{summary['path']}` | `{summary['crs']}` | `{summary['dtype']}` | "
        f"`{summary['nodata']}` | `{fmt_resolution(summary['resolution'])}` | "
        f"`{summary['shape']}` | {fmt(stats['min'])} | {fmt(stats['max'])} | "
        f"{fmt(stats['mean'])} | {fmt(stats['std'])} | {stats['valid_pixel_count']} | "
        f"{stats['total_pixel_count']} | {stats['nodata_ratio']:.4%} |"
    )


def grid_check(summary: dict, dem_summary: dict) -> dict:
    return {
        "same_crs": summary["crs"] == dem_summary["crs"],
        "same_transform": transforms_equal(summary["transform"], dem_summary["transform"]),
        "same_resolution": close_pair(summary["resolution"], dem_summary["resolution"]),
        "same_shape": summary["shape"] == dem_summary["shape"],
        "same_bounds": bounds_equal(summary["bounds"], dem_summary["bounds"]),
    }


def all_grid_checks(checks: dict) -> bool:
    return all(checks.values())


def reflectance_gate(summary: dict) -> dict:
    array = summary["array"]
    valid_mask = build_valid_mask(array, summary["nodata"])
    valid = array[valid_mask]
    negative_count = int((valid < 0).sum()) if valid.size else 0
    below_count = int((valid < REFLECTANCE_MIN).sum()) if valid.size else 0
    above_count = int((valid > REFLECTANCE_MAX).sum()) if valid.size else 0
    range_ok = summary["stats"]["min"] is not None and summary["stats"]["max"] is not None
    range_ok = range_ok and summary["stats"]["min"] >= REFLECTANCE_MIN and summary["stats"]["max"] <= REFLECTANCE_MAX
    return {
        "range_ok": range_ok,
        "negative_count": negative_count,
        "below_count": below_count,
        "above_count": above_count,
    }


def ndvi_gate(summary: dict) -> dict:
    stats = summary["stats"]
    range_ok = stats["min"] is not None and stats["min"] >= -1.0 and stats["max"] <= 1.0
    return {"range_ok": range_ok}


def plot_array(ax, array: np.ndarray, nodata, title: str, cmap: str, vmin=None, vmax=None) -> None:
    valid_mask = build_valid_mask(array, nodata)
    plot_data = np.where(valid_mask, array, np.nan)
    if vmin is None or vmax is None:
        valid = plot_data[np.isfinite(plot_data)]
        if valid.size:
            if vmin is None:
                vmin = np.nanpercentile(valid, 2)
            if vmax is None:
                vmax = np.nanpercentile(valid, 98)
    image = ax.imshow(plot_data, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_title(title)
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    plt.colorbar(image, ax=ax, shrink=0.75)


def save_preview(dem: dict, slope: dict, aspect: dict, b4: dict, b5: dict, ndvi: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    plot_array(axes[0, 0], dem["array"], dem["nodata"], "DEM", "terrain")
    plot_array(axes[0, 1], b4["array"], b4["nodata"], "Aligned B4 Red", "Reds", 0, 0.35)
    plot_array(axes[0, 2], b5["array"], b5["nodata"], "Aligned B5 NIR", "YlGn", 0, 0.6)
    plot_array(axes[1, 0], ndvi["array"], ndvi["nodata"], "Aligned NDVI", "RdYlGn", -1, 1)
    plot_array(axes[1, 1], slope["array"], slope["nodata"], "Slope", "magma", 0, 90)
    plot_array(axes[1, 2], aspect["array"], aspect["nodata"], "Aspect", "twilight", 0, 360)
    plt.tight_layout()
    fig.savefig(PREVIEW_PATH, dpi=150)
    plt.close(fig)


def checks_lines(checks: dict) -> str:
    return "\n".join(f"- {name}：**{status(value)}**" for name, value in checks.items())


def write_report(
    dem: dict,
    slope: dict,
    aspect: dict,
    original_b4: dict,
    original_b5: dict,
    aligned_b4: dict,
    aligned_b5: dict,
    ndvi: dict,
    ndvi_mask_info: dict,
    b4_grid_checks: dict,
    b5_grid_checks: dict,
    ndvi_grid_checks: dict,
    b4_reflectance_gate: dict,
    b5_reflectance_gate: dict,
    ndvi_range_gate: dict,
) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_aligned = all_grid_checks(b4_grid_checks) and all_grid_checks(b5_grid_checks) and all_grid_checks(ndvi_grid_checks)
    reflectance_warning = b4_reflectance_gate["negative_count"] > 0 or b5_reflectance_gate["negative_count"] > 0
    warnings = []
    if reflectance_warning:
        warnings.append(
            f"B4/B5 对齐后仍有少量负反射率：B4={b4_reflectance_gate['negative_count']}，B5={b5_reflectance_gate['negative_count']}；Landsat SR 允许少量负值，后续建模/NDVI 可继续使用更严格 mask。"
        )
    if not ndvi_range_gate["range_ok"]:
        warnings.append("NDVI 仍存在 [-1, 1] 之外的极端值，说明 mask 或 denominator 阈值失败。")
    warning_text = "\n".join(f"- {item}" for item in warnings) if warnings else "- 无明显 warning。"

    report = f"""# Landsat 对齐到 DEM 网格报告

## DEM Grid 信息

- DEM：`{dem["path"]}`
- CRS：`{dem["crs"]}`
- resolution：`{fmt_resolution(dem["resolution"])}`
- shape：`{dem["shape"]}`
- bounds：`{fmt_bounds(dem["bounds"])}`
- transform：

```text
{fmt_transform(dem["transform"])}
```

## 原始 Landsat B4/B5 Grid 信息

| 数据 | 文件路径 | CRS | dtype | nodata | resolution | shape | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{stats_row("Original B4 red", original_b4)}
{stats_row("Original B5 nir", original_b5)}

### 原始 B4 transform

```text
{fmt_transform(original_b4["transform"])}
```

### 原始 B5 transform

```text
{fmt_transform(original_b5["transform"])}
```

## 对齐后 B4/B5/NDVI Grid 信息

| 数据 | 文件路径 | CRS | dtype | nodata | resolution | shape | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{stats_row("Aligned B4 red", aligned_b4)}
{stats_row("Aligned B5 nir", aligned_b5)}
{stats_row("Aligned NDVI", ndvi)}

## 对齐检查：Aligned B4 vs DEM

{checks_lines(b4_grid_checks)}

## 对齐检查：Aligned B5 vs DEM

{checks_lines(b5_grid_checks)}

## 对齐检查：Aligned NDVI vs DEM

{checks_lines(ndvi_grid_checks)}

## NDVI Mask 规则

- NDVI = `(B5 - B4) / (B5 + B4)`
- B4/B5 有效反射率宽松范围：`{REFLECTANCE_MIN}` 到 `{REFLECTANCE_MAX}`
- denominator 阈值：只有 `abs(B5 + B4) > {NDVI_DENOMINATOR_THRESHOLD}` 时才计算
- NDVI 输出进一步保留 `[-1, 1]` 内的物理有效值，其他像元写为 nodata
- denominator 阈值过滤像元数：`{ndvi_mask_info["denominator_filtered_count"]}`
- NDVI 物理范围过滤像元数：`{ndvi_mask_info["physical_range_filtered_count"]}`

## 正确性闸门

1. aligned B4/B5/NDVI 必须与 DEM 同 CRS、同 transform、同 shape：**{status(all_aligned)}**
2. B4/B5 反射率值应主要在 0-1 附近，允许少量负值但需要 warning：B4 **{status(b4_reflectance_gate["range_ok"])}**，B5 **{status(b5_reflectance_gate["range_ok"])}**
3. NDVI 有效值应主要在 -1 到 1；如果仍出现极端值，说明 mask/denominator 阈值失败：**{status(ndvi_range_gate["range_ok"])}**
4. nodata 不得参与统计：**PASS**。统计均基于 nodata mask 后的有效像元。
5. preview 中 NDVI 应大体表现为山地/植被区偏高，裸地/城镇/低植被区偏低：**需人工查看**，预览图为 `{PREVIEW_PATH}`。

## Warnings

{warning_text}

## 重要说明

- Landsat 从 30m 重采样到约 27.64m DEM 网格，只是为了对齐，不代表影像真实空间分辨率提高。
- 本阶段只做 L0 多源对齐，不做地形校正，不做 BRDF，不做可微模型。
- 本次没有重采样 DEM，没有改写 DEM/地形因子。

## 输出文件

- aligned B4：`{B4_ALIGNED_PATH}`
- aligned B5：`{B5_ALIGNED_PATH}`
- aligned NDVI：`{NDVI_ALIGNED_PATH}`
- preview：`{PREVIEW_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_obsidian_draft(
    dem: dict,
    original_b4: dict,
    original_b5: dict,
    aligned_b4: dict,
    aligned_b5: dict,
    ndvi: dict,
    b4_grid_checks: dict,
    b5_grid_checks: dict,
    ndvi_grid_checks: dict,
    b4_reflectance_gate: dict,
    b5_reflectance_gate: dict,
    ndvi_range_gate: dict,
) -> None:
    OBSIDIAN_DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_aligned = all_grid_checks(b4_grid_checks) and all_grid_checks(b5_grid_checks) and all_grid_checks(ndvi_grid_checks)

    draft = f"""# Result｜Landsat 对齐到 DEM 网格 01

## 实验意图

把 Landsat B4/B5 从原始 30m 网格重采样到 Stage 2 DEM 网格，使每个像元可以同时拥有 elevation / slope / aspect / curvature / B4 / B5 / NDVI。

## 输入数据

- DEM：`{dem["path"]}`
- slope：`{SLOPE_PATH}`
- aspect：`{ASPECT_PATH}`
- curvature：`{CURVATURE_PATH}`
- Landsat B4 red：`{original_b4["path"]}`
- Landsat B5 nir：`{original_b5["path"]}`

## 跑前预测

- 对齐后的 B4/B5/NDVI 应与 DEM 同 CRS、同 transform、同 resolution、同 shape、同 bounds。
- B4/B5 反射率应主要在 `0-1` 附近，允许少量负值。
- NDVI 使用 denominator 阈值后应落在 `[-1, 1]`。
- 这一步只做 L0 多源对齐，不代表 Landsat 真实空间分辨率提高。

## 实际输出

- aligned B4：`{B4_ALIGNED_PATH}`
- aligned B5：`{B5_ALIGNED_PATH}`
- aligned NDVI：`{NDVI_ALIGNED_PATH}`
- preview：`{PREVIEW_PATH}`
- report：`{REPORT_PATH}`

## 观察

| 数据 | CRS | resolution | shape | Min | Max | Mean | Std | Valid Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Aligned B4 | `{aligned_b4["crs"]}` | `{fmt_resolution(aligned_b4["resolution"])}` | `{aligned_b4["shape"]}` | {fmt(aligned_b4["stats"]["min"])} | {fmt(aligned_b4["stats"]["max"])} | {fmt(aligned_b4["stats"]["mean"])} | {fmt(aligned_b4["stats"]["std"])} | {aligned_b4["stats"]["valid_pixel_count"]} | {aligned_b4["stats"]["nodata_ratio"]:.4%} |
| Aligned B5 | `{aligned_b5["crs"]}` | `{fmt_resolution(aligned_b5["resolution"])}` | `{aligned_b5["shape"]}` | {fmt(aligned_b5["stats"]["min"])} | {fmt(aligned_b5["stats"]["max"])} | {fmt(aligned_b5["stats"]["mean"])} | {fmt(aligned_b5["stats"]["std"])} | {aligned_b5["stats"]["valid_pixel_count"]} | {aligned_b5["stats"]["nodata_ratio"]:.4%} |
| Aligned NDVI | `{ndvi["crs"]}` | `{fmt_resolution(ndvi["resolution"])}` | `{ndvi["shape"]}` | {fmt(ndvi["stats"]["min"])} | {fmt(ndvi["stats"]["max"])} | {fmt(ndvi["stats"]["mean"])} | {fmt(ndvi["stats"]["std"])} | {ndvi["stats"]["valid_pixel_count"]} | {ndvi["stats"]["nodata_ratio"]:.4%} |

## 预测 vs 实际

1. aligned B4/B5/NDVI 与 DEM 同 CRS、同 transform、同 shape：**{status(all_aligned)}**
2. B4/B5 反射率范围合理：B4 **{status(b4_reflectance_gate["range_ok"])}**，B5 **{status(b5_reflectance_gate["range_ok"])}**
3. NDVI 有效值在 `[-1, 1]`：**{status(ndvi_range_gate["range_ok"])}**
4. nodata 不参与统计：**PASS**
5. preview 可用于人工检查 NDVI 空间形态：`{PREVIEW_PATH}`

## 结论

Landsat B4/B5 已对齐到 DEM/地形因子网格。现在每个 DEM 网格像元可以同时连接 elevation、slope、aspect、curvature、B4、B5 和 NDVI。本次对齐只是 L0 多源对齐，不代表 Landsat 真实空间分辨率提高。

## 下一步

检查 `alignment_preview.png` 中 DEM、slope、aspect 与 B4/B5/NDVI 的空间形态是否合理。通过后再考虑 Stage 3 的正式收口或进入后续地形校正设计；本次不进入地形校正、不下载新影像、不改写 DEM。
"""
    OBSIDIAN_DRAFT_PATH.write_text(draft, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    b4_path = find_landsat_band(DATA_DIR, "b4", "red")
    b5_path = find_landsat_band(DATA_DIR, "b5", "nir")

    dem = read_summary(DEM_PATH)
    slope = read_summary(SLOPE_PATH)
    aspect = read_summary(ASPECT_PATH)
    _curvature = read_summary(CURVATURE_PATH)
    original_b4 = read_summary(b4_path)
    original_b5 = read_summary(b5_path)

    b4_aligned_array = align_band_to_dem(original_b4, dem)
    b5_aligned_array = align_band_to_dem(original_b5, dem)
    ndvi_array, ndvi_mask_info = compute_ndvi_aligned(b4_aligned_array, b5_aligned_array)

    write_raster(B4_ALIGNED_PATH, b4_aligned_array, dem)
    write_raster(B5_ALIGNED_PATH, b5_aligned_array, dem)
    write_raster(NDVI_ALIGNED_PATH, ndvi_array, dem)

    aligned_b4 = aligned_summary(B4_ALIGNED_PATH)
    aligned_b5 = aligned_summary(B5_ALIGNED_PATH)
    ndvi = aligned_summary(NDVI_ALIGNED_PATH)

    b4_grid_checks = grid_check(aligned_b4, dem)
    b5_grid_checks = grid_check(aligned_b5, dem)
    ndvi_grid_checks = grid_check(ndvi, dem)
    b4_reflectance_gate = reflectance_gate(aligned_b4)
    b5_reflectance_gate = reflectance_gate(aligned_b5)
    ndvi_range_check = ndvi_gate(ndvi)

    save_preview(dem, slope, aspect, aligned_b4, aligned_b5, ndvi)
    write_report(
        dem,
        slope,
        aspect,
        original_b4,
        original_b5,
        aligned_b4,
        aligned_b5,
        ndvi,
        ndvi_mask_info,
        b4_grid_checks,
        b5_grid_checks,
        ndvi_grid_checks,
        b4_reflectance_gate,
        b5_reflectance_gate,
        ndvi_range_check,
    )
    write_obsidian_draft(
        dem,
        original_b4,
        original_b5,
        aligned_b4,
        aligned_b5,
        ndvi,
        b4_grid_checks,
        b5_grid_checks,
        ndvi_grid_checks,
        b4_reflectance_gate,
        b5_reflectance_gate,
        ndvi_range_check,
    )

    print("Landsat 已对齐到 DEM 网格。")
    print(f"aligned B4：{B4_ALIGNED_PATH}")
    print(f"aligned B5：{B5_ALIGNED_PATH}")
    print(f"aligned NDVI：{NDVI_ALIGNED_PATH}")
    print(f"preview：{PREVIEW_PATH}")
    print(f"report：{REPORT_PATH}")
    print(f"Obsidian 草稿：{OBSIDIAN_DRAFT_PATH}")


if __name__ == "__main__":
    main()
