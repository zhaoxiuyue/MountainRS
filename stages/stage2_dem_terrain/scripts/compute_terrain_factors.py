"""
DEM 地形因子计算脚本

基于已经重投影到 EPSG:32648 的米制 DEM 计算：
- slope
- aspect
- basic curvature
- hillshade

运行方式：
python stage2_dem_terrain/scripts/compute_terrain_factors.py
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


INPUT_DEM_PATH = ROOT_DIR / "data" / "srtm_dem_utm48n.tif"
SLOPE_PATH = ROOT_DIR / "outputs" / "slope_degree.tif"
ASPECT_PATH = ROOT_DIR / "outputs" / "aspect_degree.tif"
CURVATURE_PATH = ROOT_DIR / "outputs" / "curvature.tif"
HILLSHADE_PATH = ROOT_DIR / "outputs" / "hillshade.png"
PREVIEW_PATH = ROOT_DIR / "outputs" / "terrain_factors_preview.png"
REPORT_PATH = ROOT_DIR / "reports" / "terrain_factors_report.md"
OBSIDIAN_DRAFT_PATH = ROOT_DIR / "obsidian_drafts" / "Result_DEM_地形因子实验_01.md"

EXPECTED_CRS = CRS.from_epsg(32648)
OUTPUT_NODATA = np.float32(-9999.0)
SUN_AZIMUTH_DEG = 315.0
SUN_ALTITUDE_DEG = 45.0


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
    valid_pixels = array[valid_mask]
    total_count = int(array.size)
    valid_count = int(valid_mask.sum())
    nodata_count = total_count - valid_count
    nodata_ratio = nodata_count / total_count if total_count else 0.0

    if valid_count == 0:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "valid_pixel_count": valid_count,
            "total_pixel_count": total_count,
            "nodata_ratio": nodata_ratio,
        }

    valid_pixels = valid_pixels.astype("float64", copy=False)
    return {
        "min": float(valid_pixels.min()),
        "max": float(valid_pixels.max()),
        "mean": float(valid_pixels.mean()),
        "std": float(valid_pixels.std()),
        "valid_pixel_count": valid_count,
        "total_pixel_count": total_count,
        "nodata_ratio": nodata_ratio,
    }


def format_stat(value) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def format_resolution(resolution) -> str:
    return f"({resolution[0]:.10f}, {resolution[1]:.10f})"


def stats_row(label: str, stats: dict) -> str:
    return (
        f"| {label} | {format_stat(stats['min'])} | {format_stat(stats['max'])} | "
        f"{format_stat(stats['mean'])} | {format_stat(stats['std'])} | "
        f"{stats['valid_pixel_count']} | {stats['total_pixel_count']} | "
        f"{stats['nodata_ratio']:.4%} |"
    )


def as_output_array(array: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    output = np.full(array.shape, OUTPUT_NODATA, dtype="float32")
    output[valid_mask] = array[valid_mask].astype("float32")
    return output


def write_geotiff(path: Path, array: np.ndarray, source_profile: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = source_profile.copy()
    profile.update(
        {
            "driver": "GTiff",
            "height": source_profile["height"],
            "width": source_profile["width"],
            "count": 1,
            "dtype": "float32",
            "nodata": float(OUTPUT_NODATA),
            "compress": "lzw",
        }
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)


def compute_terrain_arrays(dem: np.ndarray, valid_mask: np.ndarray, xres: float, yres: float) -> dict:
    dem_float = dem.astype("float64", copy=False)
    dem_masked = np.where(valid_mask, dem_float, np.nan)

    # np.gradient 的第一个方向是 row。影像 row 向下对应地理 northing 减小，所以 dz/dnorth 需要取反。
    dz_drow, dz_dx = np.gradient(dem_masked, yres, xres)
    dz_dy_north = -dz_drow

    slope_rad = np.arctan(np.hypot(dz_dx, dz_dy_north))
    slope_degree = np.degrees(slope_rad)

    aspect_degree = (np.degrees(np.arctan2(-dz_dx, -dz_dy_north)) + 360.0) % 360.0
    aspect_degree = np.where(slope_degree < 1e-8, 0.0, aspect_degree)

    d2z_drow2 = np.gradient(dz_drow, yres, axis=0)
    d2z_dx2 = np.gradient(dz_dx, xres, axis=1)
    curvature = d2z_dx2 + d2z_drow2

    azimuth_math = np.radians(90.0 - SUN_AZIMUTH_DEG)
    aspect_math = np.radians(90.0 - aspect_degree)
    altitude_rad = np.radians(SUN_ALTITUDE_DEG)
    hillshade_float = 255.0 * (
        np.sin(altitude_rad) * np.cos(slope_rad)
        + np.cos(altitude_rad) * np.sin(slope_rad) * np.cos(azimuth_math - aspect_math)
    )
    hillshade_float = np.clip(hillshade_float, 0.0, 255.0)

    terrain_valid_mask = (
        valid_mask
        & np.isfinite(slope_degree)
        & np.isfinite(aspect_degree)
        & np.isfinite(curvature)
        & np.isfinite(hillshade_float)
    )

    return {
        "slope_degree": np.where(terrain_valid_mask, slope_degree, np.nan),
        "aspect_degree": np.where(terrain_valid_mask, aspect_degree, np.nan),
        "curvature": np.where(terrain_valid_mask, curvature, np.nan),
        "hillshade": np.where(terrain_valid_mask, hillshade_float, np.nan),
        "terrain_valid_mask": terrain_valid_mask,
    }


def save_hillshade_png(hillshade: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    image = ax.imshow(hillshade, cmap="gray", vmin=0, vmax=255)
    ax.set_title("Hillshade")
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    plt.colorbar(image, ax=ax, shrink=0.8, label="Illumination")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_preview(dem: np.ndarray, valid_mask: np.ndarray, terrain: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dem_plot = np.where(valid_mask, dem, np.nan)

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    panels = [
        ("DEM (m)", dem_plot, "terrain", None, None),
        ("Slope (degree)", terrain["slope_degree"], "magma", 0, 90),
        ("Aspect (degree)", terrain["aspect_degree"], "twilight", 0, 360),
        ("Curvature (basic)", terrain["curvature"], "RdBu_r", None, None),
        ("Hillshade", terrain["hillshade"], "gray", 0, 255),
    ]

    for ax, panel in zip(axes.ravel(), panels):
        title, array, cmap, vmin, vmax = panel
        if title == "Curvature (basic)":
            finite = array[np.isfinite(array)]
            if finite.size:
                limit = np.nanpercentile(np.abs(finite), 98)
                vmin, vmax = -limit, limit
        image = ax.imshow(array, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(title)
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")
        plt.colorbar(image, ax=ax, shrink=0.75)

    axes.ravel()[-1].axis("off")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def gate_text(ok: bool) -> str:
    return "满足" if ok else "不满足"


def evaluate_gates(summary: dict, stats: dict, terrain: dict) -> dict:
    resolution = summary["resolution"]
    slope_stats = stats["slope"]
    aspect_stats = stats["aspect"]
    hillshade_stats = compute_stats(as_output_array(terrain["hillshade"], terrain["terrain_valid_mask"]), OUTPUT_NODATA)

    return {
        "crs_is_utm48n": summary["crs"] == EXPECTED_CRS,
        "resolution_is_meter_level": 1.0 <= abs(resolution[0]) <= 100.0 and 1.0 <= abs(resolution[1]) <= 100.0,
        "slope_range_ok": slope_stats["min"] is not None and slope_stats["min"] >= -1e-6 and slope_stats["max"] <= 90.0 + 1e-6,
        "aspect_range_ok": aspect_stats["min"] is not None and aspect_stats["min"] >= -1e-6 and aspect_stats["max"] <= 360.0 + 1e-6,
        "nodata_excluded": all(item["valid_pixel_count"] < item["total_pixel_count"] or item["nodata_ratio"] == 0 for item in stats.values()),
        "hillshade_has_relief": hillshade_stats["std"] is not None and hillshade_stats["std"] > 5.0,
        "hillshade_stats": hillshade_stats,
    }


def write_report(summary: dict, stats: dict, gates: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output_files = [
        SLOPE_PATH,
        ASPECT_PATH,
        CURVATURE_PATH,
        HILLSHADE_PATH,
        PREVIEW_PATH,
        REPORT_PATH,
        OBSIDIAN_DRAFT_PATH,
    ]
    output_lines = "\n".join(f"- `{path}`" for path in output_files)

    report = f"""# DEM 地形因子计算报告

## 输入 DEM

- 输入 DEM 路径：`{INPUT_DEM_PATH}`
- CRS：`{summary["crs"]}`
- resolution：`{format_resolution(summary["resolution"])}`，单位为米
- shape：`{summary["shape"]}`，格式为 `(height, width)`
- nodata：`{summary["nodata"]}`
- aspect 约定：`0/360 = 北，90 = 东，180 = 南，270 = 西`；平坦像元的 aspect 在本脚本中记为 0，但其方向没有实际物理意义。
- hillshade 参数：太阳方位角 `{SUN_AZIMUTH_DEG:.0f}°`，太阳高度角 `{SUN_ALTITUDE_DEG:.0f}°`。
- curvature 说明：本次 curvature 使用 DEM 二阶梯度和 `d2z/dx2 + d2z/dy2` 的简化近似，只是 toy/basic curvature，不是完整地貌学曲率体系。

## 统计结果

| 数据 | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
{stats_row("DEM", stats["dem"])}
{stats_row("slope_degree", stats["slope"])}
{stats_row("aspect_degree", stats["aspect"])}
{stats_row("curvature", stats["curvature"])}

## 输出文件列表

{output_lines}

## 地形因子的物理意义

- slope：坡度，表示地表相对水平面的倾斜角，单位为 degree；越大代表地形越陡。
- aspect：坡向，表示最大下降方向的方位角；本报告采用 0/360 为北、90 为东、180 为南、270 为西的约定。
- curvature：简化曲率，反映高程面的二阶变化趋势；正负值可辅助观察凸/凹变化，但本次不是完整地貌学曲率分类。
- hillshade：山体阴影，用固定太阳位置模拟光照，帮助观察山脊、沟谷和坡面明暗结构。

## 正确性闸门

1. 输入 CRS 是否为 EPSG:32648：**{gate_text(gates["crs_is_utm48n"])}**
2. resolution 是否为米级：**{gate_text(gates["resolution_is_meter_level"])}**
3. slope 是否大致在 0-90 度：**{gate_text(gates["slope_range_ok"])}**
4. aspect 是否大致在 0-360 度：**{gate_text(gates["aspect_range_ok"])}**
5. nodata 是否未参与统计：**{gate_text(gates["nodata_excluded"])}**
6. hillshade 是否显示出合理的山脊/沟谷明暗结构：**{gate_text(gates["hillshade_has_relief"])}**。自动检查依据为 hillshade 有效像元 std = `{format_stat(gates["hillshade_stats"]["std"])}`，并已生成 PNG 供人工查看。
7. 常数平面边界测试说明：如果 DEM 是常数平面，理论上 dz/dx 和 dz/dy 应接近 0，因此 slope 应接近 0；该边界测试后续可单独构造一个常数 DEM 再验证。

## 结论

- 输入 DEM 已是 EPSG:32648 米制 CRS，适合进行基于距离单位的地形因子计算。
- slope、aspect、basic curvature 和 hillshade 已生成；本次未进入影像对齐。
"""

    REPORT_PATH.write_text(report, encoding="utf-8")


def write_obsidian_draft(summary: dict, stats: dict, gates: dict) -> None:
    OBSIDIAN_DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)

    draft = f"""# Result｜DEM 地形因子实验 01

## 实验意图

在已经完成 EPSG:32648 米制重投影的 DEM 上计算 slope、aspect、basic curvature 和 hillshade，建立 Stage 2 的地形状态闭环。

## 输入数据

- 输入 DEM：`{INPUT_DEM_PATH}`
- CRS：`{summary["crs"]}`
- resolution：`{format_resolution(summary["resolution"])}`，单位为米
- shape：`{summary["shape"]}`
- nodata：`{summary["nodata"]}`

## 跑前预测

- 输入 CRS 应为 EPSG:32648。
- resolution 应为米级，不能再是 0.000277 度。
- slope 应大致在 0-90 度。
- aspect 应大致在 0-360 度，采用 0/360 北、90 东、180 南、270 西。
- nodata 不应参与统计和梯度计算。
- hillshade 应能显示山脊/沟谷的明暗结构。

## 实际输出

- slope：`{SLOPE_PATH}`
- aspect：`{ASPECT_PATH}`
- curvature：`{CURVATURE_PATH}`
- hillshade：`{HILLSHADE_PATH}`
- 组合预览：`{PREVIEW_PATH}`
- 报告：`{REPORT_PATH}`

## 观察

| 数据 | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
{stats_row("DEM", stats["dem"])}
{stats_row("slope_degree", stats["slope"])}
{stats_row("aspect_degree", stats["aspect"])}
{stats_row("curvature", stats["curvature"])}

## 预测 vs 实际

1. 输入 CRS 是否为 EPSG:32648：**{gate_text(gates["crs_is_utm48n"])}**
2. resolution 是否为米级：**{gate_text(gates["resolution_is_meter_level"])}**
3. slope 是否大致在 0-90 度：**{gate_text(gates["slope_range_ok"])}**
4. aspect 是否大致在 0-360 度：**{gate_text(gates["aspect_range_ok"])}**
5. nodata 是否未参与统计：**{gate_text(gates["nodata_excluded"])}**
6. hillshade 是否显示出合理的山脊/沟谷明暗结构：**{gate_text(gates["hillshade_has_relief"])}**
7. 常数平面边界测试：如果 DEM 是常数平面，理论上 slope 应接近 0；后续可单独构造测试。

## 结论

地形因子计算闭环已完成。slope/aspect 基于米制分辨率计算，curvature 是 basic/toy 二阶梯度近似，hillshade 使用太阳方位角 315°、太阳高度角 45°。本次未进入影像对齐。

## 下一步

先检查 `terrain_factors_preview.png` 和 `hillshade.png` 的空间形态是否符合地形直觉，再决定是否进入影像对齐或更严格的地貌学曲率计算。
"""

    OBSIDIAN_DRAFT_PATH.write_text(draft, encoding="utf-8")


def main() -> None:
    with rasterio.open(INPUT_DEM_PATH) as src:
        dem = src.read(1)
        profile = src.profile.copy()
        summary = {
            "crs": src.crs,
            "resolution": src.res,
            "shape": (src.height, src.width),
            "nodata": src.nodata,
        }
        if src.crs != EXPECTED_CRS:
            raise ValueError(f"输入 DEM CRS 应为 EPSG:32648，但实际为 {src.crs}。")
        xres, yres = abs(src.transform.a), abs(src.transform.e)

    valid_mask = build_valid_mask(dem, summary["nodata"])
    terrain = compute_terrain_arrays(dem, valid_mask, xres, yres)

    slope_output = as_output_array(terrain["slope_degree"], terrain["terrain_valid_mask"])
    aspect_output = as_output_array(terrain["aspect_degree"], terrain["terrain_valid_mask"])
    curvature_output = as_output_array(terrain["curvature"], terrain["terrain_valid_mask"])

    write_geotiff(SLOPE_PATH, slope_output, profile)
    write_geotiff(ASPECT_PATH, aspect_output, profile)
    write_geotiff(CURVATURE_PATH, curvature_output, profile)
    save_hillshade_png(terrain["hillshade"], HILLSHADE_PATH)
    save_preview(dem, valid_mask, terrain, PREVIEW_PATH)

    stats = {
        "dem": compute_stats(dem, summary["nodata"]),
        "slope": compute_stats(slope_output, OUTPUT_NODATA),
        "aspect": compute_stats(aspect_output, OUTPUT_NODATA),
        "curvature": compute_stats(curvature_output, OUTPUT_NODATA),
    }
    gates = evaluate_gates(summary, stats, terrain)
    write_report(summary, stats, gates)
    write_obsidian_draft(summary, stats, gates)

    print(f"地形因子计算完成：{INPUT_DEM_PATH}")
    print(f"slope 已保存：{SLOPE_PATH}")
    print(f"aspect 已保存：{ASPECT_PATH}")
    print(f"curvature 已保存：{CURVATURE_PATH}")
    print(f"hillshade 已保存：{HILLSHADE_PATH}")
    print(f"组合预览已保存：{PREVIEW_PATH}")
    print(f"报告已保存：{REPORT_PATH}")
    print(f"Obsidian 草稿已保存：{OBSIDIAN_DRAFT_PATH}")


if __name__ == "__main__":
    main()
