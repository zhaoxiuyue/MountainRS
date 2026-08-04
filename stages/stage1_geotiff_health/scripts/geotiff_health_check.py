"""
GeoTIFF 栅格体检脚本

运行方式：
python scripts/geotiff_health_check.py
"""

from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
except ImportError as exc:
    raise SystemExit(
        "缺少依赖，请先安装：pip install rasterio numpy matplotlib"
    ) from exc


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
REPORT_PATH = ROOT_DIR / "reports" / "geotiff_health_check_report.md"
PLOT_PATH = OUTPUT_DIR / "geotiff_band1_preview.png"


# 中文注释：把 affine transform 格式化为高精度字符串，避免报告里只显示 0.00。
def format_transform(transform) -> str:
    return (
        f"| {transform.a:.10f}, {transform.b:.10f}, {transform.c:.10f}|\n"
        f"| {transform.d:.10f}, {transform.e:.10f}, {transform.f:.10f}|\n"
        f"| 0.0000000000, 0.0000000000, 1.0000000000|"
    )


# 中文注释：在 data/ 目录中查找第一个 tif 或 tiff 文件。
def find_tif_file(data_dir: Path) -> Path:
    tif_files = sorted(list(data_dir.glob("*.tif")) + list(data_dir.glob("*.tiff")))
    if not tif_files:
        raise FileNotFoundError(f"在 {data_dir} 中没有找到 GeoTIFF 文件。")
    return tif_files[0]


# 中文注释：读取 GeoTIFF 的基础元数据，整理成后续报告需要的字典结构。
def read_metadata(tif_path: Path) -> dict:
    with rasterio.open(tif_path) as src:
        transform = src.transform
        resolution = src.res
        crs = src.crs
        is_geographic = bool(crs and crs.is_geographic)
        metadata = {
            "path": tif_path,
            "driver": src.driver,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtype": str(src.dtypes[0]) if src.dtypes else "unknown",
            "crs": crs.to_string() if crs else None,
            "transform": transform,
            "transform_pretty": format_transform(transform),
            "resolution": resolution,
            "bounds": src.bounds,
            "nodata": src.nodata,
            "profile": src.profile,
            "total_pixel_count": src.width * src.height,
            "is_geographic": is_geographic,
        }
    return metadata


# 中文注释：按波段计算统计量，并确保 nodata、NaN、inf 不参与统计结果。
def compute_band_stats(tif_path: Path, nodata_value) -> tuple[list[dict], list[str], dict]:
    band_stats = []
    warnings = []
    overall_flags = {
        "has_nan": False,
        "has_inf": False,
    }

    with rasterio.open(tif_path) as src:
        for band_index in range(1, src.count + 1):
            band = src.read(band_index)

            valid_mask = np.isfinite(band)
            nan_count = int(np.isnan(band).sum())
            inf_count = int(np.isinf(band).sum())

            if nodata_value is not None:
                if np.issubdtype(band.dtype, np.floating) and np.isnan(nodata_value):
                    valid_mask &= ~np.isnan(band)
                else:
                    valid_mask &= band != nodata_value

            valid_pixels = band[valid_mask]
            total_pixels = band.size
            valid_count = int(valid_mask.sum())
            invalid_count = total_pixels - valid_count
            nodata_ratio = invalid_count / total_pixels if total_pixels else 0.0

            if nan_count > 0:
                overall_flags["has_nan"] = True
                warnings.append(f"Band {band_index} 检测到 NaN：{nan_count} 个。")
            if inf_count > 0:
                overall_flags["has_inf"] = True
                warnings.append(f"Band {band_index} 检测到 inf：{inf_count} 个。")

            if valid_count == 0:
                band_stats.append(
                    {
                        "band": band_index,
                        "min": None,
                        "max": None,
                        "mean": None,
                        "std": None,
                        "nodata_ratio": nodata_ratio,
                        "nan_count": nan_count,
                        "inf_count": inf_count,
                        "valid_count": valid_count,
                        "total_count": total_pixels,
                    }
                )
                warnings.append(f"Band {band_index} 没有有效像元，无法计算统计量。")
                continue

            band_min = float(valid_pixels.min())
            band_max = float(valid_pixels.max())
            band_mean = float(valid_pixels.mean())
            band_std = float(valid_pixels.std())

            if band_min == band_max:
                warnings.append(f"Band {band_index} 数值范围退化，最小值与最大值相同。")
            elif not np.isfinite([band_min, band_max, band_mean, band_std]).all():
                warnings.append(f"Band {band_index} 统计结果存在非有限值，请检查数据。")
            elif abs(band_max) > 1e7 or abs(band_min) > 1e7:
                warnings.append(
                    f"Band {band_index} 数值范围异常：min={band_min:.4f}, max={band_max:.4f}。"
                )

            band_stats.append(
                {
                    "band": band_index,
                    "min": band_min,
                    "max": band_max,
                    "mean": band_mean,
                    "std": band_std,
                    "nodata_ratio": nodata_ratio,
                    "nan_count": nan_count,
                    "inf_count": inf_count,
                    "valid_count": valid_count,
                    "total_count": total_pixels,
                }
            )

    unique_warnings = list(dict.fromkeys(warnings))
    return band_stats, unique_warnings, overall_flags


# 中文注释：绘制第一波段的可视化图，并附带一个简单直方图，输出到 outputs/。
def plot_band(tif_path: Path, output_path: Path, nodata_value) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(tif_path) as src:
        band = src.read(1)
        valid_mask = np.isfinite(band)

        if nodata_value is not None:
            if np.issubdtype(band.dtype, np.floating) and np.isnan(nodata_value):
                valid_mask &= ~np.isnan(band)
            else:
                valid_mask &= band != nodata_value

        masked_band = np.where(valid_mask, band, np.nan)
        valid_pixels = band[valid_mask]

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        image = axes[0].imshow(masked_band, cmap="terrain")
        axes[0].set_title("Band 1 Preview")
        axes[0].set_xlabel("Column")
        axes[0].set_ylabel("Row")
        plt.colorbar(image, ax=axes[0], shrink=0.8, label="Value")

        if valid_pixels.size > 0:
            axes[1].hist(valid_pixels.ravel(), bins=50, color="steelblue", edgecolor="black")
        axes[1].set_title("Band 1 Histogram")
        axes[1].set_xlabel("Value")
        axes[1].set_ylabel("Count")

        plt.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

    return {
        "plot_path": output_path,
        "histogram_bins": 50,
    }


# 中文注释：把元数据、统计量、告警和结论写入 markdown 报告文件。
def write_report(
    report_path: Path,
    metadata: dict,
    band_stats: list[dict],
    warnings: list[str],
    plot_info: dict,
    can_proceed: bool,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    proceed_text = "可以进入下一步处理" if can_proceed else "暂不建议进入下一步处理"
    warning_lines = "\n".join(f"- {item}" for item in warnings) if warnings else "- 无明显警告"
    next_step_notes = []
    if metadata["is_geographic"]:
        next_step_notes.append(
            "该数据是经纬度坐标，像元大小单位是度。后续如果要计算坡度/坡向，建议先重投影到米制 CRS，否则坡度可能错误。"
        )

    if metadata["is_geographic"]:
        resolution_interpretation = (
            f"- 原始 resolution：{metadata['resolution'][0]:.10f} x {metadata['resolution'][1]:.10f} 度\n"
            "- 约等于 1 arc-second / 30m 级 DEM，但实际地面距离随纬度变化"
        )
    else:
        resolution_interpretation = (
            f"- 原始 resolution：{metadata['resolution'][0]:.10f} x {metadata['resolution'][1]:.10f}\n"
            "- 当前 CRS 不是经纬度坐标，请结合其坐标单位理解像元大小"
        )

    band_lines = []
    for item in band_stats:
        band_lines.append(
            "| {band} | {min_v} | {max_v} | {mean_v} | {std_v} | {valid_count} | {total_count} | {nodata_ratio:.4%} | {nan_count} | {inf_count} |".format(
                band=item["band"],
                min_v="N/A" if item["min"] is None else f"{item['min']:.4f}",
                max_v="N/A" if item["max"] is None else f"{item['max']:.4f}",
                mean_v="N/A" if item["mean"] is None else f"{item['mean']:.4f}",
                std_v="N/A" if item["std"] is None else f"{item['std']:.4f}",
                valid_count=item["valid_count"],
                total_count=item["total_count"],
                nodata_ratio=item["nodata_ratio"],
                nan_count=item["nan_count"],
                inf_count=item["inf_count"],
            )
        )

    report = f"""# GeoTIFF 体检报告

## 输入文件

- 文件路径：`{metadata["path"]}`

## 基础信息

- driver：`{metadata["driver"]}`
- width / height：`{metadata["width"]}` / `{metadata["height"]}`
- band count：`{metadata["count"]}`
- dtype：`{metadata["dtype"]}`
- CRS：`{metadata["crs"]}`
- transform：
```text
{metadata["transform_pretty"]}
```
- resolution：`{metadata["resolution"]}`
- resolution interpretation：
{resolution_interpretation}
- bounds：`{metadata["bounds"]}`
- nodata：`{metadata["nodata"]}`

## 每波段统计

| Band | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio | NaN Count | Inf Count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(band_lines)}

## 可视化

- 第一波段预览图：`{plot_info["plot_path"]}`
- 直方图 bins：`{plot_info["histogram_bins"]}`
- 当前预览图使用 row/column 坐标，仅用于快速查看数组形态，不代表地理坐标图。

## Warnings

{warning_lines}

## Next-step Notes

{chr(10).join(f"- {note}" for note in next_step_notes) if next_step_notes else "- 无额外说明"}

## 结论

- 判断结果：**{proceed_text}**
- 说明：如果 CRS 缺失、有效像元为空，或存在明显异常值风险，建议先修复后再进入后续遥感/DEM 流程。
"""

    report_path.write_text(report, encoding="utf-8")


# 中文注释：串联完整流程，完成文件查找、元数据读取、统计分析、绘图和报告写出。
def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    tif_path = find_tif_file(DATA_DIR)
    metadata = read_metadata(tif_path)
    band_stats, warnings, overall_flags = compute_band_stats(tif_path, metadata["nodata"])
    plot_info = plot_band(tif_path, PLOT_PATH, metadata["nodata"])

    if metadata["crs"] is None:
        warnings.append("CRS 缺失。")
    if metadata["nodata"] is None:
        warnings.append("nodata 缺失。")
    if any(item["valid_count"] == 0 for item in band_stats):
        warnings.append("至少有一个波段没有有效像元。")
    if overall_flags["has_nan"]:
        warnings.append("存在 NaN。")
    if overall_flags["has_inf"]:
        warnings.append("存在 inf。")
    if metadata["is_geographic"]:
        warnings.append(
            "该数据是经纬度坐标，像元大小单位是度。后续如果要计算坡度/坡向，建议先重投影到米制 CRS，否则坡度可能错误。"
        )

    warnings = list(dict.fromkeys(warnings))

    can_proceed = True
    if metadata["crs"] is None:
        can_proceed = False
    if any(item["valid_count"] == 0 for item in band_stats):
        can_proceed = False
    if any(
        item["min"] is not None and (abs(item["min"]) > 1e7 or abs(item["max"]) > 1e7)
        for item in band_stats
    ):
        can_proceed = False

    write_report(REPORT_PATH, metadata, band_stats, warnings, plot_info, can_proceed)

    print(f"GeoTIFF 体检完成：{tif_path}")
    print(f"预览图已保存：{PLOT_PATH}")
    print(f"报告已保存：{REPORT_PATH}")


if __name__ == "__main__":
    main()
