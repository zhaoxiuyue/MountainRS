"""
Stage 6.5.2 clean single-scene L2 SR local check + terrain stack alignment.

This script:
- checks the clean single-scene Landsat L2 SR package
- parses QA_PIXEL into a local valid mask
- aligns Stage 2 DEM / slope / aspect to the Landsat single-scene grid
- computes cos_i with the real SUN_AZIMUTH / SUN_ELEVATION metadata

It does not:
- download imagery
- run Stage 6.5.3 residual analysis
- create synthetic observed brightness
- run inversion or Stage 7 validation
- modify Stage 1-6 data

Recommended runtime:
~/miniforge3/bin/python stages/stage6_5_real_landsat_observation_stress_test/scripts/stage6_5_2_single_scene_local_check.py
"""

import csv
import math
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT_DIR / "outputs" / ".matplotlib"))

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import reproject
except ImportError as exc:
    raise SystemExit(
        "Missing dependencies. Use a Python environment with rasterio, numpy, and matplotlib."
    ) from exc


DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
REPORT_DIR = ROOT_DIR / "reports"

B4_PATH = DATA_DIR / "stage6_5_single_scene_l8_l2sr_b4_red.tif"
B5_PATH = DATA_DIR / "stage6_5_single_scene_l8_l2sr_b5_nir.tif"
QA_PATH = DATA_DIR / "stage6_5_single_scene_l8_l2sr_qa_pixel.tif"
METADATA_PATH = DATA_DIR / "stage6_5_single_scene_l8_l2sr_metadata.csv"

STAGE2_DIR = ROOT_DIR.parent / "stage2_dem_terrain"
DEM_PATH = STAGE2_DIR / "data" / "srtm_dem_utm48n.tif"
SLOPE_PATH = STAGE2_DIR / "outputs" / "slope_degree.tif"
ASPECT_PATH = STAGE2_DIR / "outputs" / "aspect_degree.tif"

DEM_ON_GRID_PATH = OUTPUT_DIR / "dem_on_single_scene_grid.tif"
SLOPE_ON_GRID_PATH = OUTPUT_DIR / "slope_on_single_scene_grid.tif"
ASPECT_ON_GRID_PATH = OUTPUT_DIR / "aspect_on_single_scene_grid.tif"
COS_I_PATH = OUTPUT_DIR / "cos_i_single_scene_grid.tif"
CONFIDENCE_PATH = OUTPUT_DIR / "confidence_single_scene_grid.tif"
QA_VALID_MASK_PATH = OUTPUT_DIR / "qa_valid_mask_single_scene_grid.tif"
NEAR_ZERO_MASK_PATH = OUTPUT_DIR / "near_zero_mask_single_scene_grid.tif"
SHADOW_MASK_PATH = OUTPUT_DIR / "shadow_mask_single_scene_grid.tif"
PREVIEW_PATH = OUTPUT_DIR / "stage6_5_2_single_scene_local_check_preview.png"
REPORT_PATH = REPORT_DIR / "stage6_5_2_single_scene_local_check_report.md"

FLOAT_NODATA = np.float32(-9999.0)
MASK_NODATA = np.uint8(255)
REFLECTANCE_MIN = -0.05
REFLECTANCE_MAX = 1.0
CONFIDENCE_TAU = 0.1
CONFIDENCE_K = 30.0

REQUIRED_METADATA_FIELDS = [
    "image_id",
    "date",
    "CLOUD_COVER",
    "SUN_AZIMUTH",
    "SUN_ELEVATION",
    "WRS_PATH",
    "WRS_ROW",
    "ROI_GEOM_COVERAGE",
    "VALID_PIXEL_COVERAGE",
]


def ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def check_required_files():
    paths = [B4_PATH, B5_PATH, QA_PATH, METADATA_PATH, DEM_PATH, SLOPE_PATH, ASPECT_PATH]
    return {str(path): path.exists() for path in paths}


def read_metadata():
    with METADATA_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Metadata CSV is empty: {METADATA_PATH}")
    return rows[0]


def metadata_missing_fields(metadata):
    return [field for field in REQUIRED_METADATA_FIELDS if field not in metadata or metadata[field] in ("", None)]


def as_float(metadata, field):
    return float(metadata[field])


def valid_mask_for_array(array, nodata):
    mask = np.isfinite(array) if np.issubdtype(array.dtype, np.floating) else np.ones(array.shape, dtype=bool)
    if nodata is not None:
        if np.issubdtype(array.dtype, np.floating) and np.isnan(nodata):
            mask &= ~np.isnan(array)
        else:
            mask &= array != nodata
    return mask


def stats_for_array(array, nodata=None):
    valid = valid_mask_for_array(array, nodata)
    total = int(array.size)
    finite = np.isfinite(array) if np.issubdtype(array.dtype, np.floating) else np.ones(array.shape, dtype=bool)
    finite_count = int(finite.sum())
    valid_count = int(valid.sum())
    if valid_count == 0:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "valid_count": valid_count,
            "total_count": total,
            "finite_ratio": finite_count / total if total else 0,
            "nodata_ratio": 1.0 if total else 0,
        }
    values = array[valid].astype("float64", copy=False)
    return {
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "valid_count": valid_count,
        "total_count": total,
        "finite_ratio": finite_count / total if total else 0,
        "nodata_ratio": (total - valid_count) / total if total else 0,
    }


def read_raster(path):
    with rasterio.open(path) as src:
        array = src.read(1)
        summary = {
            "path": path,
            "array": array,
            "crs": src.crs,
            "transform": src.transform,
            "bounds": src.bounds,
            "resolution": src.res,
            "shape": (src.height, src.width),
            "height": src.height,
            "width": src.width,
            "dtype": src.dtypes[0],
            "nodata": src.nodata,
            "profile": src.profile.copy(),
        }
    summary["stats"] = stats_for_array(array, summary["nodata"])
    return summary


def fmt(value, digits=6):
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def fmt_ratio(value):
    return f"{value:.6f} ({value * 100:.4f}%)"


def fmt_bounds(bounds):
    return (
        f"left={bounds.left:.6f}, bottom={bounds.bottom:.6f}, "
        f"right={bounds.right:.6f}, top={bounds.top:.6f}"
    )


def fmt_transform(transform):
    return (
        f"| {transform.a:.10f}, {transform.b:.10f}, {transform.c:.10f}|\n"
        f"| {transform.d:.10f}, {transform.e:.10f}, {transform.f:.10f}|\n"
        f"| 0.0000000000, 0.0000000000, 1.0000000000|"
    )


def transforms_equal(a, b, tolerance=1e-6):
    return all(abs(x - y) <= tolerance for x, y in zip(a[:6], b[:6]))


def bounds_equal(a, b, tolerance=1e-6):
    return (
        abs(a.left - b.left) <= tolerance
        and abs(a.right - b.right) <= tolerance
        and abs(a.top - b.top) <= tolerance
        and abs(a.bottom - b.bottom) <= tolerance
    )


def same_grid_checks(b4, b5, qa):
    return {
        "B4/B5 same CRS": b4["crs"] == b5["crs"],
        "B4/QA same CRS": b4["crs"] == qa["crs"],
        "B4/B5 same transform": transforms_equal(b4["transform"], b5["transform"]),
        "B4/QA same transform": transforms_equal(b4["transform"], qa["transform"]),
        "B4/B5 same shape": b4["shape"] == b5["shape"],
        "B4/QA same shape": b4["shape"] == qa["shape"],
        "B4/B5 same bounds": bounds_equal(b4["bounds"], b5["bounds"]),
        "B4/QA same bounds": bounds_equal(b4["bounds"], qa["bounds"]),
    }


def reflectance_checks(summary):
    array = summary["array"].astype("float64", copy=False)
    valid = valid_mask_for_array(array, summary["nodata"])
    total_valid = int(valid.sum())
    low = int((valid & (array < REFLECTANCE_MIN)).sum())
    high = int((valid & (array > REFLECTANCE_MAX)).sum())
    return {
        "below_min_count": low,
        "above_max_count": high,
        "below_min_ratio": low / total_valid if total_valid else 0,
        "above_max_ratio": high / total_valid if total_valid else 0,
        "range_ok": (low + high) / total_valid <= 0.05 if total_valid else False,
    }


def parse_qa_valid_mask(qa_array):
    qa = qa_array.astype("uint32", copy=False)
    fill_clear = (qa & (1 << 0)) == 0
    dilated_cloud_clear = (qa & (1 << 1)) == 0
    cirrus_clear = (qa & (1 << 2)) == 0
    cloud_clear = (qa & (1 << 3)) == 0
    cloud_shadow_clear = (qa & (1 << 4)) == 0
    snow_clear = (qa & (1 << 5)) == 0
    return (
        fill_clear
        & dilated_cloud_clear
        & cirrus_clear
        & cloud_clear
        & cloud_shadow_clear
        & snow_clear
    )


def landsat_within_dem(landsat_bounds, dem_bounds):
    return (
        landsat_bounds.left >= dem_bounds.left
        and landsat_bounds.right <= dem_bounds.right
        and landsat_bounds.bottom >= dem_bounds.bottom
        and landsat_bounds.top <= dem_bounds.top
    )


def reproject_to_master(source_summary, master_summary, output_path, resampling):
    destination = np.full(master_summary["shape"], FLOAT_NODATA, dtype="float32")
    source = source_summary["array"].astype("float32", copy=True)
    src_nodata = source_summary["nodata"]
    if src_nodata is None:
        src_valid = valid_mask_for_array(source, src_nodata)
        source[~src_valid] = FLOAT_NODATA
        src_nodata = FLOAT_NODATA

    reproject(
        source=source,
        destination=destination,
        src_transform=source_summary["transform"],
        src_crs=source_summary["crs"],
        src_nodata=src_nodata,
        dst_transform=master_summary["transform"],
        dst_crs=master_summary["crs"],
        dst_nodata=float(FLOAT_NODATA),
        resampling=resampling,
    )
    write_float_raster(output_path, destination, master_summary)
    return read_raster(output_path)


def write_float_raster(path, array, master_summary):
    profile = master_summary["profile"].copy()
    profile.update(
        driver="GTiff",
        height=master_summary["height"],
        width=master_summary["width"],
        count=1,
        dtype="float32",
        nodata=float(FLOAT_NODATA),
        compress="lzw",
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype("float32", copy=False), 1)


def write_mask_raster(path, mask_array, master_summary):
    profile = master_summary["profile"].copy()
    profile.update(
        driver="GTiff",
        height=master_summary["height"],
        width=master_summary["width"],
        count=1,
        dtype="uint8",
        nodata=int(MASK_NODATA),
        compress="lzw",
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(mask_array.astype("uint8", copy=False), 1)


def compute_cos_i(slope_summary, aspect_summary, metadata):
    slope = slope_summary["array"].astype("float64")
    aspect = aspect_summary["array"].astype("float64")
    slope_valid = valid_mask_for_array(slope_summary["array"], slope_summary["nodata"])
    aspect_valid = valid_mask_for_array(aspect_summary["array"], aspect_summary["nodata"])

    solar_azimuth = as_float(metadata, "SUN_AZIMUTH")
    solar_elevation = as_float(metadata, "SUN_ELEVATION")
    solar_zenith = 90.0 - solar_elevation

    slope_rad = np.deg2rad(slope)
    aspect_rad = np.deg2rad(aspect)
    azimuth_rad = math.radians(solar_azimuth)
    zenith_rad = math.radians(solar_zenith)

    cos_i = (
        np.cos(slope_rad) * math.cos(zenith_rad)
        + np.sin(slope_rad) * math.sin(zenith_rad) * np.cos(azimuth_rad - aspect_rad)
    )
    valid = slope_valid & aspect_valid & np.isfinite(cos_i)
    out = np.full(slope.shape, FLOAT_NODATA, dtype="float32")
    out[valid] = cos_i[valid].astype("float32")
    return out, valid, {
        "solar_azimuth": solar_azimuth,
        "solar_elevation": solar_elevation,
        "solar_zenith": solar_zenith,
    }


def compute_confidence(cos_i_array, cos_i_valid):
    confidence = np.full(cos_i_array.shape, FLOAT_NODATA, dtype="float32")
    x = cos_i_array.astype("float64")
    conf = 1.0 / (1.0 + np.exp(-CONFIDENCE_K * (x - CONFIDENCE_TAU)))
    confidence[cos_i_valid] = conf[cos_i_valid].astype("float32")
    return confidence


def ratio_from_bool(mask):
    return float(mask.sum()) / mask.size if mask.size else 0.0


def make_preview(b4, b5, qa_valid, dem_on_grid, slope_on_grid, cos_i, confidence, near_zero, shadow):
    def plot_float(ax, array, nodata, title, cmap, vmin=None, vmax=None):
        data = array.astype("float64", copy=True)
        data[array == nodata] = np.nan
        if vmin is None or vmax is None:
            values = data[np.isfinite(data)]
            if values.size:
                vmin = np.nanpercentile(values, 2) if vmin is None else vmin
                vmax = np.nanpercentile(values, 98) if vmax is None else vmax
        image = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(title)
        ax.set_axis_off()
        plt.colorbar(image, ax=ax, shrink=0.7)

    fig, axes = plt.subplots(2, 4, figsize=(18, 9))
    plot_float(axes[0, 0], b4["array"], b4["nodata"], "B4 reflectance", "Reds", -0.05, 0.4)
    plot_float(axes[0, 1], b5["array"], b5["nodata"], "B5 reflectance", "YlGn", -0.05, 0.7)
    axes[0, 2].imshow(qa_valid, cmap="gray", vmin=0, vmax=1)
    axes[0, 2].set_title("QA valid mask")
    axes[0, 2].set_axis_off()
    plot_float(axes[0, 3], dem_on_grid["array"], dem_on_grid["nodata"], "DEM on Landsat grid", "terrain")

    plot_float(axes[1, 0], slope_on_grid["array"], slope_on_grid["nodata"], "Slope on Landsat grid", "magma", 0, 90)
    plot_float(axes[1, 1], cos_i, FLOAT_NODATA, "cos_i real sun geometry", "coolwarm", -1, 1)
    plot_float(axes[1, 2], confidence, FLOAT_NODATA, "confidence", "viridis", 0, 1)
    combined = np.zeros(near_zero.shape, dtype="uint8")
    combined[near_zero == 1] = 1
    combined[shadow == 1] = 2
    axes[1, 3].imshow(combined, cmap="plasma", vmin=0, vmax=2)
    axes[1, 3].set_title("near-zero / shadow mask")
    axes[1, 3].set_axis_off()

    plt.tight_layout()
    fig.savefig(PREVIEW_PATH, dpi=150)
    plt.close(fig)


def status(ok):
    return "PASS" if ok else "WARNING"


def write_report(context):
    metadata = context["metadata"]
    b4 = context["b4"]
    b5 = context["b5"]
    qa = context["qa"]
    dem = context["dem"]
    slope = context["slope"]
    aspect = context["aspect"]

    def raster_row(name, summary):
        stats = summary["stats"]
        return (
            f"| {name} | `{summary['crs']}` | `{summary['dtype']}` | `{summary['nodata']}` | "
            f"`({summary['resolution'][0]:.10f}, {summary['resolution'][1]:.10f})` | "
            f"`{summary['shape']}` | `{fmt_bounds(summary['bounds'])}` | "
            f"{fmt(stats['min'])} | {fmt(stats['max'])} | {fmt(stats['mean'])} | "
            f"{fmt(stats['std'])} | {fmt_ratio(stats['finite_ratio'])} |"
        )

    grid_lines = "\n".join(
        f"- {key}: **{status(value)}**" for key, value in context["grid_checks"].items()
    )

    reflectance_lines = "\n".join(
        [
            f"- B4 below `{REFLECTANCE_MIN}`: {context['b4_refl']['below_min_count']} ({context['b4_refl']['below_min_ratio'] * 100:.4f}%)",
            f"- B4 above `{REFLECTANCE_MAX}`: {context['b4_refl']['above_max_count']} ({context['b4_refl']['above_max_ratio'] * 100:.4f}%)",
            f"- B5 below `{REFLECTANCE_MIN}`: {context['b5_refl']['below_min_count']} ({context['b5_refl']['below_min_ratio'] * 100:.4f}%)",
            f"- B5 above `{REFLECTANCE_MAX}`: {context['b5_refl']['above_max_count']} ({context['b5_refl']['above_max_ratio'] * 100:.4f}%)",
        ]
    )

    gate_lines = "\n".join(
        f"- **{item['status']}** {item['name']}: {item['detail']}" for item in context["gates"]
    )

    metadata_lines = "\n".join(
        f"- `{field}`: `{metadata.get(field, 'MISSING')}`" for field in REQUIRED_METADATA_FIELDS
    )

    text = f"""# Stage 6.5.2｜Clean Single-Scene L2 SR 本地体检 + 地形栈对齐检查

## 阶段目标

本阶段检查 Stage 6.5 clean single-scene Landsat L2 SR 数据包是否完整、是否具有真实单日太阳几何与 QA_PIXEL，并将 Stage 2 DEM / slope / aspect 对齐到 Landsat single-scene grid，为后续 Stage 6.5.3 真实观测压力测试做准备。

本阶段不下载新数据，不进入 Stage 7，不运行 Stage 6.5.3 模型残差分析，不生成 synthetic observed brightness，不做 residual model。

## 输入文件列表

- B4 red: `{B4_PATH}`
- B5 NIR: `{B5_PATH}`
- QA_PIXEL: `{QA_PATH}`
- metadata CSV: `{METADATA_PATH}`
- DEM: `{DEM_PATH}`
- slope: `{SLOPE_PATH}`
- aspect: `{ASPECT_PATH}`

## 文件存在性检查

{chr(10).join(f"- `{path}`: **{'PASS' if exists else 'FAIL'}**" for path, exists in context['file_checks'].items())}

## Metadata 关键字段

{metadata_lines}

缺失字段：`{context['metadata_missing'] if context['metadata_missing'] else 'None'}`

## B4 / B5 / QA_PIXEL 空间信息

| 数据 | CRS | dtype | nodata | resolution | shape | bounds | min | max | mean | std | finite pixel ratio |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|
{raster_row('B4 red', b4)}
{raster_row('B5 NIR', b5)}
{raster_row('QA_PIXEL', qa)}

### B4 Transform

```text
{fmt_transform(b4['transform'])}
```

## B4 / B5 / QA_PIXEL 同网格检查

{grid_lines}

## B4 / B5 反射率统计

B4 / B5 应表现为 scaled reflectance，主要位于 `[-0.05, 1.0]`。本阶段不删除异常值，只记录比例。

{reflectance_lines}

## QA valid pixel ratio

- 本地 QA valid ratio: `{context['local_valid_ratio']:.6f}` ({context['local_valid_ratio'] * 100:.4f}%)
- metadata VALID_PIXEL_COVERAGE: `{context['metadata_valid_coverage']:.6f}` ({context['metadata_valid_coverage'] * 100:.4f}%)
- absolute difference: `{context['valid_coverage_diff']:.6f}`
- 对比结论：**{context['valid_coverage_status']}**

如果差异较大，可能来自 GEE `reduceRegion` 与本地 raster 边界像元、mask 定义或导出裁剪方式差异。

## DEM / slope / aspect 与 Landsat grid 的空间关系

- Landsat CRS: `{b4['crs']}`
- DEM CRS: `{dem['crs']}`
- slope CRS: `{slope['crs']}`
- aspect CRS: `{aspect['crs']}`
- CRS 一致：**{status(context['terrain_same_crs'])}**
- Landsat small ROI 是否落在 DEM bounds 内：**{status(context['landsat_within_dem'])}**

不要求 DEM 与 Landsat 同 transform / shape，因为 Landsat 是 30m small ROI，DEM 是大范围约 27.64m 网格。

## Terrain stack on Landsat grid

已生成：

- `{DEM_ON_GRID_PATH}`
- `{SLOPE_ON_GRID_PATH}`
- `{ASPECT_ON_GRID_PATH}`

重采样策略：

- DEM: bilinear
- slope: bilinear
- aspect: nearest，避免角度环绕导致 0/360 附近被错误平均

是否成功生成 terrain stack on Landsat grid：**{status(context['terrain_stack_success'])}**

## cos_i 与 confidence

真实太阳几何来自 metadata：

- solar azimuth: `{context['sun']['solar_azimuth']:.6f}`
- solar elevation: `{context['sun']['solar_elevation']:.6f}`
- solar zenith: `{context['sun']['solar_zenith']:.6f}`

使用 Stage 4 同一套 `cos_i` 公式和 Stage 2 aspect 约定：aspect 表示最大下降方向，`0/360=北，90=东，180=南，270=西`。

| 数据 | min | max | mean | std | valid count | total count |
|---|---:|---:|---:|---:|---:|---:|
| cos_i | {fmt(context['cos_stats']['min'])} | {fmt(context['cos_stats']['max'])} | {fmt(context['cos_stats']['mean'])} | {fmt(context['cos_stats']['std'])} | {context['cos_stats']['valid_count']} | {context['cos_stats']['total_count']} |
| confidence | {fmt(context['confidence_stats']['min'])} | {fmt(context['confidence_stats']['max'])} | {fmt(context['confidence_stats']['mean'])} | {fmt(context['confidence_stats']['std'])} | {context['confidence_stats']['valid_count']} | {context['confidence_stats']['total_count']} |

confidence 使用 Stage 5 逻辑：

```text
tau = {CONFIDENCE_TAU}
k_conf = {CONFIDENCE_K}
confidence = sigmoid(k_conf * (cos_i - tau))
```

## near-zero / shadow 区域比例

- near-zero mask (`0 < cos_i <= 0.1`): `{context['near_zero_ratio']:.6f}` ({context['near_zero_ratio'] * 100:.4f}%)
- shadow mask (`cos_i <= 0`): `{context['shadow_ratio']:.6f}` ({context['shadow_ratio'] * 100:.4f}%)

## 输出文件

- `{DEM_ON_GRID_PATH}`
- `{SLOPE_ON_GRID_PATH}`
- `{ASPECT_ON_GRID_PATH}`
- `{COS_I_PATH}`
- `{CONFIDENCE_PATH}`
- `{QA_VALID_MASK_PATH}`
- `{NEAR_ZERO_MASK_PATH}`
- `{SHADOW_MASK_PATH}`
- `{PREVIEW_PATH}`

## PASS / WARNING / FAIL 总结

{gate_lines}

## 下一步是否可以进入 Stage 6.5.3

**{context['next_step_status']}**

进入 Stage 6.5.3 前仍需确认：不进入 Stage 7，不使用旧 Stage 3 composite，不生成 synthetic observed brightness，只针对当前 clean single-scene 数据包做真实观测压力测试。
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main():
    ensure_dirs()
    file_checks = check_required_files()
    missing_files = [path for path, exists in file_checks.items() if not exists]
    if missing_files:
        raise FileNotFoundError(f"Missing required files: {missing_files}")

    metadata = read_metadata()
    metadata_missing = metadata_missing_fields(metadata)
    if metadata_missing:
        raise ValueError(f"Metadata missing fields: {metadata_missing}")

    b4 = read_raster(B4_PATH)
    b5 = read_raster(B5_PATH)
    qa = read_raster(QA_PATH)
    dem = read_raster(DEM_PATH)
    slope = read_raster(SLOPE_PATH)
    aspect = read_raster(ASPECT_PATH)

    grid_checks = same_grid_checks(b4, b5, qa)
    b4_refl = reflectance_checks(b4)
    b5_refl = reflectance_checks(b5)

    qa_valid = parse_qa_valid_mask(qa["array"])
    b4_valid = valid_mask_for_array(b4["array"], b4["nodata"])
    b5_valid = valid_mask_for_array(b5["array"], b5["nodata"])
    local_valid = qa_valid & b4_valid & b5_valid
    local_valid_ratio = ratio_from_bool(local_valid)
    metadata_valid_coverage = as_float(metadata, "VALID_PIXEL_COVERAGE")
    valid_coverage_diff = abs(local_valid_ratio - metadata_valid_coverage)
    valid_coverage_status = "PASS" if valid_coverage_diff <= 0.02 else "WARNING"

    terrain_same_crs = b4["crs"] == dem["crs"] == slope["crs"] == aspect["crs"]
    small_roi_within_dem = landsat_within_dem(b4["bounds"], dem["bounds"])

    dem_on_grid = reproject_to_master(dem, b4, DEM_ON_GRID_PATH, Resampling.bilinear)
    slope_on_grid = reproject_to_master(slope, b4, SLOPE_ON_GRID_PATH, Resampling.bilinear)
    aspect_on_grid = reproject_to_master(aspect, b4, ASPECT_ON_GRID_PATH, Resampling.nearest)

    cos_i, cos_i_valid, sun = compute_cos_i(slope_on_grid, aspect_on_grid, metadata)
    confidence = compute_confidence(cos_i, cos_i_valid)

    qa_valid_out = np.full(qa_valid.shape, 0, dtype="uint8")
    qa_valid_out[local_valid] = 1
    near_zero = np.full(cos_i.shape, MASK_NODATA, dtype="uint8")
    shadow = np.full(cos_i.shape, MASK_NODATA, dtype="uint8")
    near_zero[cos_i_valid] = ((cos_i[cos_i_valid] > 0) & (cos_i[cos_i_valid] <= CONFIDENCE_TAU)).astype("uint8")
    shadow[cos_i_valid] = (cos_i[cos_i_valid] <= 0).astype("uint8")

    write_float_raster(COS_I_PATH, cos_i, b4)
    write_float_raster(CONFIDENCE_PATH, confidence, b4)
    write_mask_raster(QA_VALID_MASK_PATH, qa_valid_out, b4)
    write_mask_raster(NEAR_ZERO_MASK_PATH, near_zero, b4)
    write_mask_raster(SHADOW_MASK_PATH, shadow, b4)

    cos_stats = stats_for_array(cos_i, FLOAT_NODATA)
    confidence_stats = stats_for_array(confidence, FLOAT_NODATA)
    near_zero_ratio = int((near_zero == 1).sum()) / int(cos_i_valid.sum()) if int(cos_i_valid.sum()) else 0
    shadow_ratio = int((shadow == 1).sum()) / int(cos_i_valid.sum()) if int(cos_i_valid.sum()) else 0

    make_preview(b4, b5, qa_valid_out, dem_on_grid, slope_on_grid, cos_i, confidence, near_zero, shadow)

    gates = [
        {
            "name": "B4 / B5 / QA_PIXEL must be same grid",
            "status": "PASS" if all(grid_checks.values()) else "FAIL",
            "detail": "CRS / transform / shape / bounds checked.",
        },
        {
            "name": "metadata must contain real SUN_AZIMUTH / SUN_ELEVATION",
            "status": "PASS" if not metadata_missing and metadata.get("SUN_AZIMUTH") and metadata.get("SUN_ELEVATION") else "FAIL",
            "detail": f"SUN_AZIMUTH={metadata.get('SUN_AZIMUTH')}, SUN_ELEVATION={metadata.get('SUN_ELEVATION')}",
        },
        {
            "name": "B4 / B5 must behave like scaled reflectance",
            "status": "PASS" if b4_refl["range_ok"] and b5_refl["range_ok"] else "WARNING",
            "detail": "Out-of-range reflectance ratios recorded without deleting pixels.",
        },
        {
            "name": "QA_PIXEL must parse into valid mask",
            "status": "PASS" if 0 < local_valid_ratio <= 1 else "FAIL",
            "detail": f"local_valid_ratio={local_valid_ratio:.6f}",
        },
        {
            "name": "Landsat small ROI must be inside DEM terrain bounds",
            "status": "PASS" if terrain_same_crs and small_roi_within_dem else "FAIL",
            "detail": f"same_crs={terrain_same_crs}, within_dem_bounds={small_roi_within_dem}",
        },
        {
            "name": "cos_i must use real metadata sun angle",
            "status": "PASS",
            "detail": f"solar_azimuth={sun['solar_azimuth']:.6f}, solar_elevation={sun['solar_elevation']:.6f}",
        },
        {
            "name": "Do not generate synthetic observed brightness",
            "status": "PASS",
            "detail": "No synthetic observed brightness output is created.",
        },
        {
            "name": "Do not run residual model",
            "status": "PASS",
            "detail": "No residual model or Stage 6.5.3 analysis is run.",
        },
        {
            "name": "Do not enter Stage 7",
            "status": "PASS",
            "detail": "Only Stage 6.5.2 local check files are generated.",
        },
    ]

    hard_fail = any(item["status"] == "FAIL" for item in gates)
    next_step_status = (
        "可以进入 Stage 6.5.3，但只能做 clean single-scene 真实观测压力测试。"
        if not hard_fail
        else "不建议进入 Stage 6.5.3；需要先修复 FAIL 项。"
    )

    context = {
        "file_checks": file_checks,
        "metadata": metadata,
        "metadata_missing": metadata_missing,
        "b4": b4,
        "b5": b5,
        "qa": qa,
        "dem": dem,
        "slope": slope,
        "aspect": aspect,
        "grid_checks": grid_checks,
        "b4_refl": b4_refl,
        "b5_refl": b5_refl,
        "local_valid_ratio": local_valid_ratio,
        "metadata_valid_coverage": metadata_valid_coverage,
        "valid_coverage_diff": valid_coverage_diff,
        "valid_coverage_status": valid_coverage_status,
        "terrain_same_crs": terrain_same_crs,
        "landsat_within_dem": small_roi_within_dem,
        "terrain_stack_success": all(path.exists() for path in [DEM_ON_GRID_PATH, SLOPE_ON_GRID_PATH, ASPECT_ON_GRID_PATH]),
        "sun": sun,
        "cos_stats": cos_stats,
        "confidence_stats": confidence_stats,
        "near_zero_ratio": near_zero_ratio,
        "shadow_ratio": shadow_ratio,
        "gates": gates,
        "next_step_status": next_step_status,
    }
    write_report(context)

    print("Stage 6.5.2 local check complete.")
    print(f"Report: {REPORT_PATH}")
    print(f"Preview: {PREVIEW_PATH}")
    print(f"Next step: {next_step_status}")


if __name__ == "__main__":
    main()
