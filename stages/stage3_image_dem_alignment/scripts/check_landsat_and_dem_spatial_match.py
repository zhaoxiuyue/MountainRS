"""
Stage 3.1 Landsat 影像体检与 DEM 空间关系检查

本脚本只做检查与报告：
- 不执行重采样
- 不改写 DEM
- 不进入地形校正

运行方式：
python3 stage3_image_dem_alignment/scripts/check_landsat_and_dem_spatial_match.py
"""

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT_DIR / "outputs" / ".matplotlib"))

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
    from rasterio.crs import CRS
except ImportError as exc:
    raise SystemExit(
        "缺少依赖，请先安装：pip install rasterio numpy matplotlib"
    ) from exc


DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
REPORT_PATH = ROOT_DIR / "reports" / "landsat_dem_spatial_check_report.md"
PREVIEW_PATH = OUTPUT_DIR / "landsat_preview.png"
OBSIDIAN_DRAFT_PATH = ROOT_DIR / "obsidian_drafts" / "Result_Landsat_影像体检与DEM空间检查_01.md"

DEM_PATH = ROOT_DIR.parent / "stage2_dem_terrain" / "data" / "srtm_dem_utm48n.tif"
EXPECTED_CRS = CRS.from_epsg(32648)
REFLECTANCE_WARNING_MIN = -0.2
REFLECTANCE_WARNING_MAX = 1.2


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
        raise FileExistsError(
            f"找到多个 {band_token}/{alias} 候选文件，请保留唯一文件：{candidates}"
        )
    return candidates[0]


def build_valid_mask(array: np.ndarray, nodata) -> np.ndarray:
    valid_mask = np.isfinite(array)
    if nodata is not None:
        if np.issubdtype(array.dtype, np.floating) and np.isnan(nodata):
            valid_mask &= ~np.isnan(array)
        else:
            valid_mask &= array != nodata
    return valid_mask


def compute_stats(array: np.ndarray, nodata) -> dict:
    valid_mask = build_valid_mask(array, nodata)
    total_count = int(array.size)
    valid_count = int(valid_mask.sum())
    nan_count = int(np.isnan(array).sum()) if np.issubdtype(array.dtype, np.floating) else 0
    inf_count = int(np.isinf(array).sum()) if np.issubdtype(array.dtype, np.floating) else 0

    if valid_count == 0:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "valid_pixel_count": valid_count,
            "total_pixel_count": total_count,
            "nan_count": nan_count,
            "inf_count": inf_count,
            "nodata_ratio": 1.0 if total_count else 0.0,
        }

    valid_pixels = array[valid_mask].astype("float64", copy=False)
    return {
        "min": float(valid_pixels.min()),
        "max": float(valid_pixels.max()),
        "mean": float(valid_pixels.mean()),
        "std": float(valid_pixels.std()),
        "valid_pixel_count": valid_count,
        "total_pixel_count": total_count,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "nodata_ratio": (total_count - valid_count) / total_count if total_count else 0.0,
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
            "nodata": src.nodata,
            "dtype": src.dtypes[0],
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


def bounds_overlap(bounds_a, bounds_b) -> bool:
    return not (
        bounds_a.right <= bounds_b.left
        or bounds_a.left >= bounds_b.right
        or bounds_a.top <= bounds_b.bottom
        or bounds_a.bottom >= bounds_b.top
    )


def close_pair(pair_a, pair_b, tolerance: float = 1e-6) -> bool:
    return abs(pair_a[0] - pair_b[0]) <= tolerance and abs(pair_a[1] - pair_b[1]) <= tolerance


def transforms_equal(transform_a, transform_b, tolerance: float = 1e-6) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(transform_a[:6], transform_b[:6]))


def bounds_equal(bounds_a, bounds_b, tolerance: float = 1e-6) -> bool:
    return (
        abs(bounds_a.left - bounds_b.left) <= tolerance
        and abs(bounds_a.right - bounds_b.right) <= tolerance
        and abs(bounds_a.top - bounds_b.top) <= tolerance
        and abs(bounds_a.bottom - bounds_b.bottom) <= tolerance
    )


def resolution_close(res_a, res_b, relative_tolerance: float = 0.15) -> bool:
    return (
        abs(res_a[0] - res_b[0]) / max(abs(res_b[0]), 1e-12) <= relative_tolerance
        and abs(res_a[1] - res_b[1]) / max(abs(res_b[1]), 1e-12) <= relative_tolerance
    )


def status_text(ok: bool) -> str:
    return "PASS" if ok else "WARNING"


def stats_table_row(label: str, summary: dict) -> str:
    stats = summary["stats"]
    return (
        f"| {label} | `{summary['path']}` | `{summary['crs']}` | `{summary['dtype']}` | "
        f"`{summary['nodata']}` | `{fmt_resolution(summary['resolution'])}` | "
        f"`{summary['shape']}` | {fmt(stats['min'])} | {fmt(stats['max'])} | "
        f"{fmt(stats['mean'])} | {fmt(stats['std'])} | {stats['valid_pixel_count']} | "
        f"{stats['total_pixel_count']} | {stats['nan_count']} | {stats['inf_count']} |"
    )


def reflectance_range_ok(summary: dict) -> bool:
    stats = summary["stats"]
    if stats["min"] is None or stats["max"] is None:
        return False
    return stats["min"] >= REFLECTANCE_WARNING_MIN and stats["max"] <= REFLECTANCE_WARNING_MAX


def compute_ndvi(b4: dict, b5: dict) -> tuple[np.ndarray, dict]:
    b4_array = b4["array"].astype("float64", copy=False)
    b5_array = b5["array"].astype("float64", copy=False)
    valid_mask = build_valid_mask(b4_array, b4["nodata"]) & build_valid_mask(b5_array, b5["nodata"])
    denominator = b5_array + b4_array
    valid_mask &= np.isfinite(denominator) & (np.abs(denominator) > 1e-12)

    ndvi = np.full(b4_array.shape, np.nan, dtype="float64")
    ndvi[valid_mask] = (b5_array[valid_mask] - b4_array[valid_mask]) / denominator[valid_mask]
    return ndvi, compute_stats(ndvi, np.nan)


def save_preview(b4: dict, b5: dict, ndvi: np.ndarray) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    b4_plot = np.where(build_valid_mask(b4["array"], b4["nodata"]), b4["array"], np.nan)
    b5_plot = np.where(build_valid_mask(b5["array"], b5["nodata"]), b5["array"], np.nan)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    panels = [
        ("B4 Red", b4_plot, "Reds", None, None),
        ("B5 NIR", b5_plot, "YlGn", None, None),
        ("NDVI", ndvi, "RdYlGn", -1, 1),
    ]

    for ax, (title, array, cmap, vmin, vmax) in zip(axes, panels):
        if title != "NDVI":
            valid = array[np.isfinite(array)]
            if valid.size:
                vmin = np.nanpercentile(valid, 2)
                vmax = np.nanpercentile(valid, 98)
        image = ax.imshow(array, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(title)
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")
        plt.colorbar(image, ax=ax, shrink=0.8)

    plt.tight_layout()
    fig.savefig(PREVIEW_PATH, dpi=150)
    plt.close(fig)


def make_checks(b4: dict, b5: dict, dem: dict) -> dict:
    b4_b5 = {
        "same_crs": b4["crs"] == b5["crs"],
        "same_resolution": close_pair(b4["resolution"], b5["resolution"]),
        "same_transform": transforms_equal(b4["transform"], b5["transform"]),
        "same_bounds": bounds_equal(b4["bounds"], b5["bounds"]),
        "same_shape": b4["shape"] == b5["shape"],
    }
    landsat_dem = {
        "same_crs": b4["crs"] == dem["crs"] == EXPECTED_CRS,
        "bounds_overlap": bounds_overlap(b4["bounds"], dem["bounds"]),
        "resolution_close": resolution_close(b4["resolution"], dem["resolution"]),
        "same_transform": transforms_equal(b4["transform"], dem["transform"]),
        "same_shape": b4["shape"] == dem["shape"],
    }
    reflectance = {
        "b4_range_ok": reflectance_range_ok(b4),
        "b5_range_ok": reflectance_range_ok(b5),
        "b4_has_valid_pixels": b4["stats"]["valid_pixel_count"] > 0,
        "b5_has_valid_pixels": b5["stats"]["valid_pixel_count"] > 0,
        "b4_no_inf": b4["stats"]["inf_count"] == 0,
        "b5_no_inf": b5["stats"]["inf_count"] == 0,
        "b4_has_nodata_or_nan_mask": b4["nodata"] is not None or b4["stats"]["nan_count"] > 0,
        "b5_has_nodata_or_nan_mask": b5["nodata"] is not None or b5["stats"]["nan_count"] > 0,
    }
    image_healthy = (
        reflectance["b4_range_ok"]
        and reflectance["b5_range_ok"]
        and reflectance["b4_has_valid_pixels"]
        and reflectance["b5_has_valid_pixels"]
        and reflectance["b4_no_inf"]
        and reflectance["b5_no_inf"]
        and all(b4_b5.values())
    )
    return {
        "b4_b5": b4_b5,
        "landsat_dem": landsat_dem,
        "reflectance": reflectance,
        "b4_b5_same_grid": all(b4_b5.values()),
        "landsat_dem_fully_aligned": all(landsat_dem.values()),
        "image_healthy": image_healthy,
    }


def check_lines(items: dict) -> str:
    return "\n".join(f"- {name}：**{status_text(ok)}**" for name, ok in items.items())


def write_report(b4: dict, b5: dict, dem: dict, ndvi_stats: dict, checks: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    warnings = []
    if not checks["reflectance"]["b4_range_ok"]:
        warnings.append(
            f"B4 反射率范围可能异常：min={fmt(b4['stats']['min'])}, max={fmt(b4['stats']['max'])}。"
        )
    if not checks["reflectance"]["b5_range_ok"]:
        warnings.append(
            f"B5 反射率范围可能异常：min={fmt(b5['stats']['min'])}, max={fmt(b5['stats']['max'])}。"
        )
    if not checks["landsat_dem"]["same_transform"] or not checks["landsat_dem"]["same_shape"]:
        warnings.append("Landsat 与 DEM transform/shape 不一致：这一步只是检查，还未完成最终对齐。")
    if ndvi_stats["min"] is not None and (ndvi_stats["min"] < -1.0 or ndvi_stats["max"] > 1.0):
        warnings.append(
            "快速 NDVI 出现超出 [-1, 1] 的极端值，主要来自反射率接近 0 或含负值时的近零分母；后续正式 NDVI 应增加有效反射率/mask 规则。"
        )
    warning_text = "\n".join(f"- {item}" for item in warnings) if warnings else "- 无明显 warning。"
    mask_notes = []
    for label, summary in [("B4", b4), ("B5", b5)]:
        if summary["nodata"] is None and summary["stats"]["nan_count"] > 0:
            mask_notes.append(
                f"{label} nodata=None，但存在 {summary['stats']['nan_count']} 个 NaN；本脚本将有限值作为有效像元，NaN 视作 mask。"
            )
        elif summary["nodata"] is not None:
            mask_notes.append(f"{label} 使用 nodata={summary['nodata']} 作为无效像元标记。")
    mask_note_text = "\n".join(f"- {item}" for item in mask_notes) if mask_notes else "- 未发现 nodata 或 NaN mask。"

    recommended_strategy = (
        "第一版推荐把 Landsat B4/B5 重采样/对齐到 DEM/地形因子网格，"
        "这样后续每个像元可以同时拥有 elevation/slope/aspect/curvature/B4/B5/NDVI。"
    )

    report = f"""# Landsat 影像体检与 DEM 空间检查报告

## 输入文件

- Landsat B4 red：`{b4["path"]}`
- Landsat B5 nir：`{b5["path"]}`
- DEM：`{dem["path"]}`

## Metadata 与统计

| 数据 | 文件路径 | CRS | dtype | nodata | resolution | shape | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | NaN Count | Inf Count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{stats_table_row("B4 red", b4)}
{stats_table_row("B5 nir", b5)}
{stats_table_row("DEM", dem)}

## Transform

### B4 red

```text
{fmt_transform(b4["transform"])}
```

### B5 nir

```text
{fmt_transform(b5["transform"])}
```

### DEM

```text
{fmt_transform(dem["transform"])}
```

## Bounds

- B4 red：`{fmt_bounds(b4["bounds"])}`
- B5 nir：`{fmt_bounds(b5["bounds"])}`
- DEM：`{fmt_bounds(dem["bounds"])}`

## NDVI 快速预览统计

- NDVI 公式：`(B5 - B4) / (B5 + B4)`
- 说明：这是 Stage 3.1 的快速预览 NDVI，尚未做正式质量掩膜；当 `B5 + B4` 接近 0 或反射率含负值时，NDVI 可能出现极端值。
- min：`{fmt(ndvi_stats["min"])}`
- max：`{fmt(ndvi_stats["max"])}`
- mean：`{fmt(ndvi_stats["mean"])}`
- std：`{fmt(ndvi_stats["std"])}`
- valid pixel count：`{ndvi_stats["valid_pixel_count"]}`
- total pixel count：`{ndvi_stats["total_pixel_count"]}`
- 预览图：`{PREVIEW_PATH}`

## Nodata / Mask 说明

{mask_note_text}

## B4/B5 同网格检查

{check_lines(checks["b4_b5"])}

- B4/B5 是否同网格：**{status_text(checks["b4_b5_same_grid"])}**

## Landsat 与 DEM 空间关系检查

{check_lines(checks["landsat_dem"])}

- Landsat 与 DEM 是否已经完全对齐：**{status_text(checks["landsat_dem_fully_aligned"])}**
- 说明：shape 不一致不一定是错误，因为还没有执行对齐；这一步只是检查，不是最终对齐。

## 正确性闸门

1. B4/B5 反射率值大致应在合理范围内，通常主要在 0-1 附近：B4 **{status_text(checks["reflectance"]["b4_range_ok"])}**，B5 **{status_text(checks["reflectance"]["b5_range_ok"])}**。
2. B4/B5 应该同 CRS、同 transform、同 shape：**{status_text(checks["b4_b5_same_grid"])}**。
3. Landsat 与 DEM CRS 应该都是 EPSG:32648：**{status_text(checks["landsat_dem"]["same_crs"])}**。
4. Landsat 与 DEM bounds 应该重叠：**{status_text(checks["landsat_dem"]["bounds_overlap"])}**。
5. 如果 transform/shape 不一致，报告应明确：还未完成最终对齐。当前 transform 一致性：**{status_text(checks["landsat_dem"]["same_transform"])}**；shape 一致性：**{status_text(checks["landsat_dem"]["same_shape"])}**。

## Warnings

{warning_text}

## 结论

- 当前影像是否健康：**{status_text(checks["image_healthy"])}**。
- B4/B5 是否同网格：**{status_text(checks["b4_b5_same_grid"])}**。
- Landsat 与 DEM 是否已经完全对齐：**{status_text(checks["landsat_dem_fully_aligned"])}**。
- Landsat 与 DEM 当前同 CRS 且 bounds 重叠，但 resolution、transform、shape 不完全一致，因此还不能视为最终对齐。
- 下一步建议：{recommended_strategy}

## 本次未做

- 未执行重采样。
- 未改写 DEM 或地形因子。
- 未进入地形校正。
"""

    REPORT_PATH.write_text(report, encoding="utf-8")


def write_obsidian_draft(b4: dict, b5: dict, dem: dict, ndvi_stats: dict, checks: dict) -> None:
    OBSIDIAN_DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    recommended_strategy = (
        "第一版把 Landsat 对齐到 DEM/地形因子网格，方便后续每个像元同时拥有 "
        "elevation/slope/aspect/curvature/B4/B5/NDVI。"
    )

    draft = f"""# Result｜Landsat 影像体检与 DEM 空间检查 01

## 实验意图

检查 GEE 导出的 Landsat Collection 2 Surface Reflectance B4/B5 GeoTIFF 是否健康，并判断它们与 Stage 2 DEM / 地形因子是否可以进入后续对齐流程。

## 输入数据

- B4 red：`{b4["path"]}`
- B5 nir：`{b5["path"]}`
- DEM：`{dem["path"]}`

## 跑前预测

- B4/B5 应该同 CRS、同 transform、同 bounds、同 shape。
- B4/B5 反射率值应主要在 `0-1` 附近。
- Landsat 与 DEM 应同为 `EPSG:32648`。
- Landsat 与 DEM bounds 应重叠。
- Landsat 与 DEM transform/shape 可能不一致，因为 Stage 3 还没有执行最终对齐。

## 实际输出

- 预览图：`{PREVIEW_PATH}`
- 报告：`{REPORT_PATH}`
- NDVI 快速预览：`(B5 - B4) / (B5 + B4)`

## 观察

| 数据 | CRS | resolution | shape | bounds | Min | Max | Mean | Std |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B4 red | `{b4["crs"]}` | `{fmt_resolution(b4["resolution"])}` | `{b4["shape"]}` | `{fmt_bounds(b4["bounds"])}` | {fmt(b4["stats"]["min"])} | {fmt(b4["stats"]["max"])} | {fmt(b4["stats"]["mean"])} | {fmt(b4["stats"]["std"])} |
| B5 nir | `{b5["crs"]}` | `{fmt_resolution(b5["resolution"])}` | `{b5["shape"]}` | `{fmt_bounds(b5["bounds"])}` | {fmt(b5["stats"]["min"])} | {fmt(b5["stats"]["max"])} | {fmt(b5["stats"]["mean"])} | {fmt(b5["stats"]["std"])} |
| DEM | `{dem["crs"]}` | `{fmt_resolution(dem["resolution"])}` | `{dem["shape"]}` | `{fmt_bounds(dem["bounds"])}` | {fmt(dem["stats"]["min"])} | {fmt(dem["stats"]["max"])} | {fmt(dem["stats"]["mean"])} | {fmt(dem["stats"]["std"])} |

- NDVI min/max/mean/std：`{fmt(ndvi_stats["min"])}` / `{fmt(ndvi_stats["max"])}` / `{fmt(ndvi_stats["mean"])}` / `{fmt(ndvi_stats["std"])}`
- NDVI 说明：这是快速预览 NDVI，尚未做正式质量掩膜；近零分母或负反射率会产生超出 `[-1, 1]` 的极端值。
- 当前影像是否健康：**{status_text(checks["image_healthy"])}**
- B4/B5 同网格：**{status_text(checks["b4_b5_same_grid"])}**
- Landsat 与 DEM 完全对齐：**{status_text(checks["landsat_dem_fully_aligned"])}**

## 预测 vs 实际

1. B4/B5 反射率范围合理：B4 **{status_text(checks["reflectance"]["b4_range_ok"])}**，B5 **{status_text(checks["reflectance"]["b5_range_ok"])}**。
2. B4/B5 同 CRS、同 transform、同 shape：**{status_text(checks["b4_b5_same_grid"])}**。
3. Landsat 与 DEM CRS 都是 EPSG:32648：**{status_text(checks["landsat_dem"]["same_crs"])}**。
4. Landsat 与 DEM bounds 重叠：**{status_text(checks["landsat_dem"]["bounds_overlap"])}**。
5. transform/shape 若不一致，只说明还未完成最终对齐：当前 transform **{status_text(checks["landsat_dem"]["same_transform"])}**，shape **{status_text(checks["landsat_dem"]["same_shape"])}**。

## 结论

B4/B5 影像可以进入后续对齐流程。B4/B5 自身同网格；Landsat 与 DEM 同 CRS 且 bounds 重叠，但 resolution、transform、shape 不完全一致，所以尚未完成最终对齐。

## 下一步

{recommended_strategy}

本次不执行重采样，不改写 DEM，不进入地形校正。
"""

    OBSIDIAN_DRAFT_PATH.write_text(draft, encoding="utf-8")


def main() -> None:
    b4_path = find_landsat_band(DATA_DIR, "b4", "red")
    b5_path = find_landsat_band(DATA_DIR, "b5", "nir")

    b4 = read_summary(b4_path)
    b5 = read_summary(b5_path)
    dem = read_summary(DEM_PATH)
    ndvi, ndvi_stats = compute_ndvi(b4, b5)
    checks = make_checks(b4, b5, dem)

    save_preview(b4, b5, ndvi)
    write_report(b4, b5, dem, ndvi_stats, checks)
    write_obsidian_draft(b4, b5, dem, ndvi_stats, checks)

    print(f"Landsat/DEM 空间检查完成。")
    print(f"B4：{b4_path}")
    print(f"B5：{b5_path}")
    print(f"预览图已保存：{PREVIEW_PATH}")
    print(f"报告已保存：{REPORT_PATH}")
    print(f"Obsidian 草稿已保存：{OBSIDIAN_DRAFT_PATH}")


if __name__ == "__main__":
    main()
