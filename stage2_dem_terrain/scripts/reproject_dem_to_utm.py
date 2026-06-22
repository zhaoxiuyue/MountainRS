"""
DEM 重投影脚本：EPSG:4326 -> EPSG:32648

运行方式：
python stage2_dem_terrain/scripts/reproject_dem_to_utm.py
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
    from rasterio.warp import Resampling, calculate_default_transform, reproject
except ImportError as exc:
    raise SystemExit(
        "缺少依赖，请先安装：pip install rasterio numpy matplotlib"
    ) from exc


INPUT_PATH = ROOT_DIR / "data" / "srtm_dem.tif"
OUTPUT_PATH = ROOT_DIR / "data" / "srtm_dem_utm48n.tif"
PREVIEW_PATH = ROOT_DIR / "outputs" / "dem_utm48n_preview.png"
REPORT_PATH = ROOT_DIR / "reports" / "reproject_dem_report.md"
OBSIDIAN_DRAFT_PATH = ROOT_DIR / "obsidian_drafts" / "Result_DEM_重投影实验_01.md"

EXPECTED_INPUT_CRS = CRS.from_epsg(4326)
TARGET_CRS = CRS.from_epsg(32648)


def format_bounds(bounds) -> str:
    return (
        f"left={bounds.left:.6f}, bottom={bounds.bottom:.6f}, "
        f"right={bounds.right:.6f}, top={bounds.top:.6f}"
    )


def format_resolution(resolution) -> str:
    return f"({resolution[0]:.10f}, {resolution[1]:.10f})"


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

    if valid_count == 0:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "valid_pixel_count": valid_count,
            "total_pixel_count": total_count,
        }

    valid_pixels = valid_pixels.astype("float64", copy=False)
    return {
        "min": float(valid_pixels.min()),
        "max": float(valid_pixels.max()),
        "mean": float(valid_pixels.mean()),
        "std": float(valid_pixels.std()),
        "valid_pixel_count": valid_count,
        "total_pixel_count": total_count,
    }


def format_stat(value) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def read_dataset_summary(path: Path) -> dict:
    with rasterio.open(path) as src:
        band = src.read(1)
        return {
            "path": path,
            "crs": src.crs,
            "resolution": src.res,
            "bounds": src.bounds,
            "shape": (src.height, src.width),
            "dtype": src.dtypes[0],
            "nodata": src.nodata,
            "stats": compute_stats(band, src.nodata),
        }


def reproject_dem() -> tuple[dict, dict]:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(INPUT_PATH) as src:
        if src.crs != EXPECTED_INPUT_CRS:
            raise ValueError(
                f"输入 CRS 应为 EPSG:4326，但实际为 {src.crs}。请先检查输入 DEM。"
            )

        transform, width, height = calculate_default_transform(
            src.crs,
            TARGET_CRS,
            src.width,
            src.height,
            *src.bounds,
        )

        profile = src.profile.copy()
        profile.update(
            {
                "driver": "GTiff",
                "crs": TARGET_CRS,
                "transform": transform,
                "width": width,
                "height": height,
                "dtype": src.dtypes[0],
                "nodata": src.nodata,
                "compress": "lzw",
            }
        )

        with rasterio.open(OUTPUT_PATH, "w", **profile) as dst:
            for band_index in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band_index),
                    destination=rasterio.band(dst, band_index),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata,
                    dst_transform=transform,
                    dst_crs=TARGET_CRS,
                    dst_nodata=src.nodata,
                    resampling=Resampling.bilinear,
                )

    input_summary = read_dataset_summary(INPUT_PATH)
    output_summary = read_dataset_summary(OUTPUT_PATH)
    return input_summary, output_summary


def create_preview(path: Path, preview_path: Path) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(path) as src:
        band = src.read(1)
        valid_mask = build_valid_mask(band, src.nodata)
        masked_band = np.where(valid_mask, band, np.nan)
        valid_pixels = band[valid_mask]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    image = axes[0].imshow(masked_band, cmap="terrain")
    axes[0].set_title("DEM UTM 48N Preview")
    axes[0].set_xlabel("Column")
    axes[0].set_ylabel("Row")
    plt.colorbar(image, ax=axes[0], shrink=0.8, label="Elevation (m)")

    if valid_pixels.size > 0:
        axes[1].hist(valid_pixels.ravel(), bins=60, color="seagreen", edgecolor="black")
    axes[1].set_title("Elevation Histogram")
    axes[1].set_xlabel("Elevation (m)")
    axes[1].set_ylabel("Count")

    plt.tight_layout()
    fig.savefig(preview_path, dpi=150)
    plt.close(fig)


def evaluate_gates(input_summary: dict, output_summary: dict) -> dict:
    input_stats = input_summary["stats"]
    output_stats = output_summary["stats"]
    output_res = output_summary["resolution"]

    output_crs_ok = output_summary["crs"] == TARGET_CRS
    output_res_ok = 20 <= abs(output_res[0]) <= 40 and 20 <= abs(output_res[1]) <= 40
    elevation_range_ok = (
        input_stats["min"] is not None
        and output_stats["min"] is not None
        and abs(output_stats["min"] - input_stats["min"]) < 100
        and abs(output_stats["max"] - input_stats["max"]) < 100
        and 450 <= output_stats["min"] <= 700
        and 5800 <= output_stats["max"] <= 6200
    )
    shape_can_change_ok = output_summary["shape"] != input_summary["shape"]
    bounds_changed_to_meter_ok = (
        output_summary["bounds"].left > 100000
        and output_summary["bounds"].right > 100000
        and abs(output_summary["bounds"].top) > 100000
        and abs(output_summary["bounds"].bottom) > 100000
    )

    return {
        "output_crs_ok": output_crs_ok,
        "output_res_ok": output_res_ok,
        "elevation_range_ok": elevation_range_ok,
        "shape_can_change_ok": shape_can_change_ok,
        "bounds_changed_to_meter_ok": bounds_changed_to_meter_ok,
    }


def gate_text(ok: bool) -> str:
    return "满足" if ok else "不满足"


def stats_table_row(label: str, summary: dict) -> str:
    stats = summary["stats"]
    return (
        f"| {label} | {format_stat(stats['min'])} | {format_stat(stats['max'])} | "
        f"{format_stat(stats['mean'])} | {format_stat(stats['std'])} | "
        f"{stats['valid_pixel_count']} | {stats['total_pixel_count']} |"
    )


def write_report(input_summary: dict, output_summary: dict, gates: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    report = f"""# DEM 重投影报告

## 文件路径

- 输入文件路径：`{input_summary["path"]}`
- 输出文件路径：`{output_summary["path"]}`
- 预览图路径：`{PREVIEW_PATH}`

## CRS

- 输入 CRS：`{input_summary["crs"]}`
- 输出 CRS：`{output_summary["crs"]}`

## Resolution

- 输入 resolution：`{format_resolution(input_summary["resolution"])}`，单位为度
- 输出 resolution：`{format_resolution(output_summary["resolution"])}`，单位为米

## Bounds

- 输入 bounds：`{format_bounds(input_summary["bounds"])}`
- 输出 bounds：`{format_bounds(output_summary["bounds"])}`

## Shape

- 输入 shape：`{input_summary["shape"]}`，格式为 `(height, width)`
- 输出 shape：`{output_summary["shape"]}`，格式为 `(height, width)`

## Nodata

- nodata：`{input_summary["nodata"]}`

## 高程统计

| 数据 | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count |
| --- | --- | --- | --- | --- | --- | --- |
{stats_table_row("重投影前", input_summary)}
{stats_table_row("重投影后", output_summary)}

## 正确性闸门

1. 输出 CRS 应为 EPSG:32648：**{gate_text(gates["output_crs_ok"])}**
2. 输出 resolution 应约为 30m 级，而不是 0.000277 度：**{gate_text(gates["output_res_ok"])}**
3. 高程 min/max 不应剧烈变化，仍应大约在 522-6024m 附近：**{gate_text(gates["elevation_range_ok"])}**
4. 输出 shape 可以变化：**{gate_text(gates["shape_can_change_ok"])}**
5. 输出 bounds 应从经纬度范围变成 UTM 米制坐标范围：**{gate_text(gates["bounds_changed_to_meter_ok"])}**

## 结论

- 重投影后像元单位从度变成米，后续才适合计算 slope/aspect。
- 本次仅完成 DEM 重投影闭环，未执行 slope/aspect 计算。
"""

    REPORT_PATH.write_text(report, encoding="utf-8")


def write_obsidian_draft(input_summary: dict, output_summary: dict, gates: dict) -> None:
    OBSIDIAN_DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)

    draft = f"""# Result｜DEM 重投影实验 01

## 实验意图

将 Stage 2 的 DEM 从 EPSG:4326 经纬度坐标重投影到 EPSG:32648 米制坐标，避免后续 slope/aspect 计算把角度单位误当作距离单位。

## 输入数据

- 输入 DEM：`{input_summary["path"]}`
- 输入 CRS：`{input_summary["crs"]}`
- 输入 resolution：`{format_resolution(input_summary["resolution"])}`，单位为度
- 输入 shape：`{input_summary["shape"]}`
- nodata：`{input_summary["nodata"]}`

## 跑前预测

- 输出 CRS 应为 EPSG:32648。
- 输出 resolution 应约为 30m 级，而不是 0.000277 度。
- 高程 min/max 不应剧烈变化，仍应大约在 522-6024m 附近。
- 输出 shape 可以变化。
- 输出 bounds 应从经纬度范围变成 UTM 米制坐标范围。

## 实际输出

- 输出 DEM：`{output_summary["path"]}`
- 输出 CRS：`{output_summary["crs"]}`
- 输出 resolution：`{format_resolution(output_summary["resolution"])}`，单位为米
- 输出 bounds：`{format_bounds(output_summary["bounds"])}`
- 输出 shape：`{output_summary["shape"]}`
- 预览图：`{PREVIEW_PATH}`
- 报告：`{REPORT_PATH}`

## 观察

| 数据 | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count |
| --- | --- | --- | --- | --- | --- | --- |
{stats_table_row("重投影前", input_summary)}
{stats_table_row("重投影后", output_summary)}

## 预测 vs 实际

1. 输出 CRS 应为 EPSG:32648：**{gate_text(gates["output_crs_ok"])}**
2. 输出 resolution 应约为 30m 级，而不是 0.000277 度：**{gate_text(gates["output_res_ok"])}**
3. 高程 min/max 不应剧烈变化，仍应大约在 522-6024m 附近：**{gate_text(gates["elevation_range_ok"])}**
4. 输出 shape 可以变化：**{gate_text(gates["shape_can_change_ok"])}**
5. 输出 bounds 应从经纬度范围变成 UTM 米制坐标范围：**{gate_text(gates["bounds_changed_to_meter_ok"])}**

## 结论

重投影后像元单位从度变成米，后续才适合计算 slope/aspect。本次只完成 DEM 重投影闭环。

## 下一步

在确认输出 DEM 的 CRS、resolution、bounds、nodata 和高程统计均合理后，再进入 slope/aspect 计算。
"""

    OBSIDIAN_DRAFT_PATH.write_text(draft, encoding="utf-8")


def main() -> None:
    input_summary, output_summary = reproject_dem()
    create_preview(OUTPUT_PATH, PREVIEW_PATH)
    gates = evaluate_gates(input_summary, output_summary)
    write_report(input_summary, output_summary, gates)
    write_obsidian_draft(input_summary, output_summary, gates)

    print(f"DEM 重投影完成：{OUTPUT_PATH}")
    print(f"预览图已保存：{PREVIEW_PATH}")
    print(f"报告已保存：{REPORT_PATH}")
    print(f"Obsidian 草稿已保存：{OBSIDIAN_DRAFT_PATH}")


if __name__ == "__main__":
    main()
