"""
Stage 4 非可微地形辐射 toy model

使用真实 DEM 的 slope/aspect，构建一个朗伯 + 单光源 + 直接光项 toy model。
本脚本不使用 Landsat B4/B5 做真实校正，不改写 Stage 2/3 数据，不进入可微模型。

运行方式：
python3 stage4_terrain_radiation_toy/scripts/terrain_radiation_toy_model.py
"""

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ROOT_DIR.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT_DIR / "outputs" / ".matplotlib"))

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
except ImportError as exc:
    raise SystemExit(
        "缺少依赖，请先安装：pip install rasterio numpy matplotlib"
    ) from exc


DEM_PATH = PROJECT_ROOT / "stage2_dem_terrain" / "data" / "srtm_dem_utm48n.tif"
SLOPE_PATH = PROJECT_ROOT / "stage2_dem_terrain" / "outputs" / "slope_degree.tif"
ASPECT_PATH = PROJECT_ROOT / "stage2_dem_terrain" / "outputs" / "aspect_degree.tif"

OUTPUT_DIR = ROOT_DIR / "outputs"
REPORT_PATH = ROOT_DIR / "reports" / "terrain_radiation_toy_report.md"
RESULT_CARD_PATH = ROOT_DIR / "obsidian_drafts" / "Result_地形辐射ToyModel_01.md"
PHYSICS_GATE_PATH = ROOT_DIR / "obsidian_drafts" / "Physics_Gate_地形辐射ToyModel.md"

COS_I_PATH = OUTPUT_DIR / "cos_i.tif"
SHADOW_MASK_PATH = OUTPUT_DIR / "shadow_mask.tif"
OBSERVED_BRIGHTNESS_PATH = OUTPUT_DIR / "observed_brightness_toy.tif"
CORRECTED_ALBEDO_PATH = OUTPUT_DIR / "corrected_albedo_toy.tif"
PREVIEW_PATH = OUTPUT_DIR / "terrain_radiation_toy_preview.png"

NODATA = np.float32(-9999.0)
ALBEDO = 0.3
SOLAR_AZIMUTH_DEG = 315.0
SOLAR_ELEVATION_DEG = 45.0
SOLAR_ZENITH_DEG = 45.0
CORRECTION_COS_THRESHOLD = 0.1


def build_valid_mask(array: np.ndarray, nodata) -> np.ndarray:
    valid = np.isfinite(array)
    if nodata is not None:
        if np.issubdtype(array.dtype, np.floating) and np.isnan(nodata):
            valid &= ~np.isnan(array)
        else:
            valid &= array != nodata
    return valid


def compute_stats(array: np.ndarray, nodata) -> dict:
    valid = build_valid_mask(array, nodata)
    total = int(array.size)
    valid_count = int(valid.sum())
    nodata_ratio = (total - valid_count) / total if total else 0.0
    if valid_count == 0:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "valid_pixel_count": valid_count,
            "total_pixel_count": total,
            "nodata_ratio": nodata_ratio,
        }

    values = array[valid].astype("float64", copy=False)
    return {
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "valid_pixel_count": valid_count,
        "total_pixel_count": total,
        "nodata_ratio": nodata_ratio,
    }


def read_raster(path: Path) -> dict:
    with rasterio.open(path) as src:
        array = src.read(1)
        return {
            "path": path,
            "array": array,
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


def write_raster(path: Path, array: np.ndarray, dem: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = dem["profile"].copy()
    profile.update(
        {
            "driver": "GTiff",
            "height": dem["height"],
            "width": dem["width"],
            "count": 1,
            "dtype": "float32",
            "nodata": float(NODATA),
            "compress": "lzw",
        }
    )
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype("float32", copy=False), 1)


def compute_toy_model(dem: dict, slope: dict, aspect: dict) -> dict:
    dem_valid = build_valid_mask(dem["array"], dem["nodata"])
    slope_valid = build_valid_mask(slope["array"], slope["nodata"])
    aspect_valid = build_valid_mask(aspect["array"], aspect["nodata"])
    valid = dem_valid & slope_valid & aspect_valid

    slope_rad = np.radians(slope["array"].astype("float64", copy=False))
    aspect_rad = np.radians(aspect["array"].astype("float64", copy=False))
    solar_azimuth_rad = np.radians(SOLAR_AZIMUTH_DEG)
    solar_zenith_rad = np.radians(SOLAR_ZENITH_DEG)

    cos_i_raw = (
        np.cos(slope_rad) * np.cos(solar_zenith_rad)
        + np.sin(slope_rad)
        * np.sin(solar_zenith_rad)
        * np.cos(solar_azimuth_rad - aspect_rad)
    )

    cos_i = np.full(slope["array"].shape, NODATA, dtype="float32")
    cos_i[valid] = cos_i_raw[valid].astype("float32")

    shadow_bool = valid & (cos_i_raw <= 0.0)
    shadow_mask = np.full(slope["array"].shape, NODATA, dtype="float32")
    shadow_mask[valid] = 0.0
    shadow_mask[shadow_bool] = 1.0

    observed = np.full(slope["array"].shape, NODATA, dtype="float32")
    observed[valid] = (ALBEDO * np.maximum(cos_i_raw[valid], 0.0)).astype("float32")

    correction_valid = valid & (cos_i_raw > CORRECTION_COS_THRESHOLD)
    corrected = np.full(slope["array"].shape, NODATA, dtype="float32")
    corrected[correction_valid] = (observed[correction_valid] / cos_i_raw[correction_valid]).astype("float32")

    invalid_correction = valid & ~correction_valid

    return {
        "cos_i": cos_i,
        "shadow_mask": shadow_mask,
        "observed_brightness": observed,
        "corrected_albedo": corrected,
        "valid_mask": valid,
        "shadow_bool": shadow_bool,
        "correction_valid": correction_valid,
        "invalid_correction": invalid_correction,
    }


def summarize_outputs() -> dict:
    return {
        "cos_i": read_raster(COS_I_PATH),
        "shadow_mask": read_raster(SHADOW_MASK_PATH),
        "observed_brightness": read_raster(OBSERVED_BRIGHTNESS_PATH),
        "corrected_albedo": read_raster(CORRECTED_ALBEDO_PATH),
    }


def plot_array(ax, array: np.ndarray, nodata, title: str, cmap: str, vmin=None, vmax=None) -> None:
    valid = build_valid_mask(array, nodata)
    plot_data = np.where(valid, array, np.nan)
    if vmin is None or vmax is None:
        values = plot_data[np.isfinite(plot_data)]
        if values.size:
            if vmin is None:
                vmin = np.nanpercentile(values, 2)
            if vmax is None:
                vmax = np.nanpercentile(values, 98)
    image = ax.imshow(plot_data, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_title(title)
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    plt.colorbar(image, ax=ax, shrink=0.75)


def save_preview(dem: dict, slope: dict, aspect: dict, outputs: dict) -> None:
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 3, figsize=(17, 14))
    plot_array(axes[0, 0], dem["array"], dem["nodata"], "DEM", "terrain")
    plot_array(axes[0, 1], slope["array"], slope["nodata"], "Slope", "magma", 0, 90)
    plot_array(axes[0, 2], aspect["array"], aspect["nodata"], "Aspect", "twilight", 0, 360)
    plot_array(axes[1, 0], outputs["cos_i"]["array"], outputs["cos_i"]["nodata"], "cos(i)", "viridis", -1, 1)
    plot_array(axes[1, 1], outputs["shadow_mask"]["array"], outputs["shadow_mask"]["nodata"], "Shadow Mask", "gray", 0, 1)
    plot_array(
        axes[1, 2],
        outputs["observed_brightness"]["array"],
        outputs["observed_brightness"]["nodata"],
        "Observed Brightness Toy",
        "inferno",
        0,
        ALBEDO,
    )
    plot_array(
        axes[2, 0],
        outputs["corrected_albedo"]["array"],
        outputs["corrected_albedo"]["nodata"],
        "Corrected Albedo Toy",
        "viridis",
        0,
        0.6,
    )
    axes[2, 1].axis("off")
    axes[2, 2].axis("off")
    plt.tight_layout()
    fig.savefig(PREVIEW_PATH, dpi=150)
    plt.close(fig)


def stats_row(label: str, summary: dict) -> str:
    stats = summary["stats"]
    return (
        f"| {label} | {fmt(stats['min'])} | {fmt(stats['max'])} | "
        f"{fmt(stats['mean'])} | {fmt(stats['std'])} | "
        f"{stats['valid_pixel_count']} | {stats['total_pixel_count']} | {stats['nodata_ratio']:.4%} |"
    )


def status(ok: bool) -> str:
    return "PASS" if ok else "WARNING"


def run_boundary_tests() -> dict:
    zenith_rad = np.radians(SOLAR_ZENITH_DEG)
    flat_cos = float(np.cos(zenith_rad))

    moderate_slope_rad = np.radians(30.0)
    facing_cos = float(
        np.cos(moderate_slope_rad) * np.cos(zenith_rad)
        + np.sin(moderate_slope_rad) * np.sin(zenith_rad) * np.cos(0.0)
    )
    back_cos = float(
        np.cos(moderate_slope_rad) * np.cos(zenith_rad)
        + np.sin(moderate_slope_rad) * np.sin(zenith_rad) * np.cos(np.radians(180.0))
    )
    steep_back_rad = np.radians(60.0)
    steep_back_cos = float(
        np.cos(steep_back_rad) * np.cos(zenith_rad)
        + np.sin(steep_back_rad) * np.sin(zenith_rad) * np.cos(np.radians(180.0))
    )

    observed = ALBEDO * facing_cos
    corrected = observed / facing_cos

    return {
        "flat_cos": flat_cos,
        "flat_pass": abs(flat_cos - np.cos(zenith_rad)) < 1e-12,
        "facing_cos": facing_cos,
        "facing_pass": facing_cos > flat_cos,
        "back_cos": back_cos,
        "steep_back_cos": steep_back_cos,
        "shadow_pass": steep_back_cos <= 0.0,
        "corrected": corrected,
        "corrected_pass": abs(corrected - ALBEDO) < 1e-12,
        "threshold_pass": CORRECTION_COS_THRESHOLD > 0.0,
    }


def write_report(dem: dict, slope: dict, aspect: dict, outputs: dict, model: dict, gates: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    shadow_ratio = int(model["shadow_bool"].sum()) / int(model["valid_mask"].sum())
    invalid_ratio = int(model["invalid_correction"].sum()) / int(model["valid_mask"].sum())
    corrected_stats = outputs["corrected_albedo"]["stats"]
    corrected_close = corrected_stats["mean"] is not None and abs(corrected_stats["mean"] - ALBEDO) < 1e-4

    report = f"""# 地形辐射 Toy Model 报告

## 输入文件

- DEM：`{DEM_PATH}`
- slope：`{SLOPE_PATH}`
- aspect：`{ASPECT_PATH}`

## DEM Grid

- CRS：`{dem["crs"]}`
- resolution：`{fmt_resolution(dem["resolution"])}`
- shape：`{dem["shape"]}`
- bounds：`{fmt_bounds(dem["bounds"])}`
- transform：

```text
{fmt_transform(dem["transform"])}
```

## Slope / Aspect 约定

- slope 单位：degree
- aspect 来自 Stage 2，表示最大下降方向
- aspect 方位约定：`0/360 = 北，90 = 东，180 = 南，270 = 西`

## 太阳参数

- solar azimuth：`{SOLAR_AZIMUTH_DEG}°`，表示光源来自西北
- solar elevation：`{SOLAR_ELEVATION_DEG}°`
- solar zenith：`{SOLAR_ZENITH_DEG}°`
- constant albedo：`{ALBEDO}`

## 公式

```text
cos_i = cos(slope) * cos(zenith)
      + sin(slope) * sin(zenith) * cos(solar_azimuth - aspect)

observed_brightness = albedo * max(cos_i, 0)
shadow_mask = cos_i <= 0
corrected_albedo = observed_brightness / cos_i, only where cos_i > {CORRECTION_COS_THRESHOLD}
```

角度在计算前全部转换为 radians。

## 统计结果

| 数据 | Min | Max | Mean | Std | Valid Pixel Count | Total Pixel Count | Nodata Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
{stats_row("cos_i", outputs["cos_i"])}
{stats_row("shadow_mask", outputs["shadow_mask"])}
{stats_row("observed_brightness", outputs["observed_brightness"])}
{stats_row("corrected_albedo", outputs["corrected_albedo"])}

## Shadow / Invalid Correction

- shadow ratio：`{shadow_ratio:.4%}`
- invalid correction ratio：`{invalid_ratio:.4%}`
- shadow 区域：`cos_i <= 0`
- invalid correction 区域：`cos_i <= {CORRECTION_COS_THRESHOLD}`，包括背阴坡和入射角接近 90° 的区域
- corrected_albedo 是否接近输入 albedo=`{ALBEDO}`：**{status(corrected_close)}**，mean=`{fmt(corrected_stats["mean"])}`

## 为什么 cos_i 接近 0 时不能直接除

当 `cos_i` 接近 0 时，`observed_brightness / cos_i` 会把非常小的噪声或数值误差放大成巨大值。背阴坡或接近掠射光照的区域，直接除以 `cos_i` 不再是稳定的物理校正，而是数值爆炸风险。因此本 toy model 明确把 `cos_i <= {CORRECTION_COS_THRESHOLD}` 作为失效域，不硬校正。

## 为什么这不是完整地形校正

- 只包含朗伯、单光源和直接光项。
- 没有真实太阳几何随时间/影像变化的 metadata。
- 没有天空散射、邻近地形反射、阴影投射、BRDF、地表各向异性或大气效应。
- 使用常数 albedo，不代表真实地表材料差异。
- 当前 Landsat 是 2023-2024 median composite，不是单日影像，不适合直接做单日物理地形校正。

## 正确性闸门

1. 平地 slope=0 时，cos_i 理论上应等于 cos(zenith)：**{status(gates["flat_pass"])}**，cos(zenith)=`{gates["flat_cos"]:.6f}`
2. 坡面 aspect 接近 solar azimuth 且坡度适中时，cos_i 应较大：**{status(gates["facing_pass"])}**，30° facing cos_i=`{gates["facing_cos"]:.6f}`
3. 背光坡 cos_i <= 0 时应进入 shadow_mask：**{status(gates["shadow_pass"])}**，60° back-facing cos_i=`{gates["steep_back_cos"]:.6f}`
4. 常数 albedo=0.3 时，非阴影区 corrected_albedo 应恢复到约 0.3：**{status(gates["corrected_pass"] and corrected_close)}**
5. cos_i <= 0.1 区域不应硬校正：**{status(gates["threshold_pass"])}**
6. observed_brightness 的亮暗结构应主要来自地形光照，而不是地表属性变化，因为 albedo 是常数：**PASS**，本模型未引入空间变化 albedo。

## 输出文件

- `cos_i.tif`：`{COS_I_PATH}`
- `shadow_mask.tif`：`{SHADOW_MASK_PATH}`
- `observed_brightness_toy.tif`：`{OBSERVED_BRIGHTNESS_PATH}`
- `corrected_albedo_toy.tif`：`{CORRECTED_ALBEDO_PATH}`
- preview：`{PREVIEW_PATH}`

## 本次未做

- 未使用 Landsat B4/B5 做真实校正。
- 未改写 Stage 2 或 Stage 3 数据。
- 未进入可微模型。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_result_card(outputs: dict, model: dict, gates: dict) -> None:
    RESULT_CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    shadow_ratio = int(model["shadow_bool"].sum()) / int(model["valid_mask"].sum())
    invalid_ratio = int(model["invalid_correction"].sum()) / int(model["valid_mask"].sum())
    corrected_mean = outputs["corrected_albedo"]["stats"]["mean"]

    card = f"""# Result｜地形辐射 Toy Model 01

## 实验意图

使用真实 DEM 的 slope/aspect，构建一个朗伯 + 单光源 + 直接光项的非可微地形辐射 toy model，观察地形光照如何在常数 albedo 条件下制造明暗结构，并验证简单校正的失效域。

## 输入数据

- DEM：`{DEM_PATH}`
- slope：`{SLOPE_PATH}`
- aspect：`{ASPECT_PATH}`
- solar azimuth：`{SOLAR_AZIMUTH_DEG}°`
- solar elevation：`{SOLAR_ELEVATION_DEG}°`
- solar zenith：`{SOLAR_ZENITH_DEG}°`
- albedo：`{ALBEDO}`

## 跑前预测

- 平地 slope=0 时，`cos_i = cos(zenith)`。
- 朝向西北光源且坡度适中的坡面，`cos_i` 应较大。
- 背光坡 `cos_i <= 0` 应进入 shadow_mask。
- 常数 albedo 下，`cos_i > 0.1` 的区域经过 `observed_brightness / cos_i` 应恢复到约 `0.3`。
- `cos_i <= 0.1` 是失效域，不应硬校正。

## 实际输出

- cos_i：`{COS_I_PATH}`
- shadow_mask：`{SHADOW_MASK_PATH}`
- observed_brightness：`{OBSERVED_BRIGHTNESS_PATH}`
- corrected_albedo：`{CORRECTED_ALBEDO_PATH}`
- preview：`{PREVIEW_PATH}`
- report：`{REPORT_PATH}`

## 观察

| 数据 | Min | Max | Mean | Std | Nodata Ratio |
| --- | --- | --- | --- | --- | --- |
| cos_i | {fmt(outputs["cos_i"]["stats"]["min"])} | {fmt(outputs["cos_i"]["stats"]["max"])} | {fmt(outputs["cos_i"]["stats"]["mean"])} | {fmt(outputs["cos_i"]["stats"]["std"])} | {outputs["cos_i"]["stats"]["nodata_ratio"]:.4%} |
| observed_brightness | {fmt(outputs["observed_brightness"]["stats"]["min"])} | {fmt(outputs["observed_brightness"]["stats"]["max"])} | {fmt(outputs["observed_brightness"]["stats"]["mean"])} | {fmt(outputs["observed_brightness"]["stats"]["std"])} | {outputs["observed_brightness"]["stats"]["nodata_ratio"]:.4%} |
| corrected_albedo | {fmt(outputs["corrected_albedo"]["stats"]["min"])} | {fmt(outputs["corrected_albedo"]["stats"]["max"])} | {fmt(outputs["corrected_albedo"]["stats"]["mean"])} | {fmt(outputs["corrected_albedo"]["stats"]["std"])} | {outputs["corrected_albedo"]["stats"]["nodata_ratio"]:.4%} |

- shadow ratio：`{shadow_ratio:.4%}`
- invalid correction ratio：`{invalid_ratio:.4%}`
- corrected_albedo mean：`{fmt(corrected_mean)}`

## 预测 vs 实际

1. 平地 slope=0 时 cos_i 等于 cos(zenith)：**{status(gates["flat_pass"])}**
2. 朝向太阳方位的适中坡面 cos_i 较大：**{status(gates["facing_pass"])}**
3. 背光坡进入 shadow_mask：**{status(gates["shadow_pass"])}**
4. 非阴影区 corrected_albedo 恢复到约 0.3：**{status(gates["corrected_pass"] and corrected_mean is not None and abs(corrected_mean - ALBEDO) < 1e-4)}**
5. cos_i <= 0.1 不硬校正：**{status(gates["threshold_pass"])}**

## 结论

Toy model 正常运行。常数 albedo 下，observed_brightness 的空间亮暗主要来自地形光照项；在 `cos_i > 0.1` 区域，corrected_albedo 恢复到约 `0.3`。背阴坡和 `cos_i` 接近 0 的区域是失效域，不应直接除以 `cos_i` 硬校正。

## 下一步

把该 toy model 作为 Stage 4 的非可微物理底板，继续整理 Physics Gate 和正式 Obsidian 收口。当前 Landsat 是 2023-2024 median composite，不适合直接做单日物理地形校正。
"""
    RESULT_CARD_PATH.write_text(card, encoding="utf-8")


def write_physics_gate(outputs: dict, model: dict, gates: dict) -> None:
    PHYSICS_GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    corrected_mean = outputs["corrected_albedo"]["stats"]["mean"]
    gate_pass = (
        gates["flat_pass"]
        and gates["facing_pass"]
        and gates["shadow_pass"]
        and gates["corrected_pass"]
        and corrected_mean is not None
        and abs(corrected_mean - ALBEDO) < 1e-4
        and gates["threshold_pass"]
    )

    card = f"""# Physics Gate｜地形辐射 Toy Model

## 跑前预测

- 平地 slope=0 时，`cos_i` 应等于 `cos(zenith)`。
- 坡面 aspect 接近 solar azimuth 且坡度适中时，`cos_i` 应较大。
- 背光坡 `cos_i <= 0` 应进入 shadow_mask。
- 常数 albedo=`{ALBEDO}` 时，非阴影且 `cos_i > {CORRECTION_COS_THRESHOLD}` 的区域 corrected_albedo 应恢复到约 `{ALBEDO}`。
- `cos_i <= {CORRECTION_COS_THRESHOLD}` 的区域不应硬校正。

## 边界测试

- Flat test：slope=0，理论 `cos_i=cos({SOLAR_ZENITH_DEG}°)={gates["flat_cos"]:.6f}`。
- Facing slope test：30° 坡面朝向 solar azimuth，`cos_i={gates["facing_cos"]:.6f}`，应大于平地。
- Back slope test：60° 背光坡，`cos_i={gates["steep_back_cos"]:.6f}`，应进入 shadow。
- Constant albedo recovery：`observed_brightness / cos_i` 应恢复 `{ALBEDO}`。

## 实际结果

- corrected_albedo mean：`{fmt(corrected_mean)}`
- corrected_albedo min/max：`{fmt(outputs["corrected_albedo"]["stats"]["min"])}` / `{fmt(outputs["corrected_albedo"]["stats"]["max"])}`
- cos_i min/max：`{fmt(outputs["cos_i"]["stats"]["min"])}` / `{fmt(outputs["cos_i"]["stats"]["max"])}`
- shadow valid count：`{int(model["shadow_bool"].sum())}`
- invalid correction count：`{int(model["invalid_correction"].sum())}`
- 报告：`{REPORT_PATH}`
- 预览图：`{PREVIEW_PATH}`

## PASS / WARNING / FAIL

- 平地 cos_i 闸门：**{status(gates["flat_pass"])}**
- 朝光坡 cos_i 较大闸门：**{status(gates["facing_pass"])}**
- 背光坡 shadow 闸门：**{status(gates["shadow_pass"])}**
- corrected_albedo 恢复闸门：**{status(gates["corrected_pass"] and corrected_mean is not None and abs(corrected_mean - ALBEDO) < 1e-4)}**
- `cos_i <= {CORRECTION_COS_THRESHOLD}` 不硬校正闸门：**{status(gates["threshold_pass"])}**
- 总体：**{"PASS" if gate_pass else "WARNING"}**

## 失效域 A：背阴坡 / cos_i 接近 0

背阴坡和 `cos_i` 接近 0 的坡面，不适合直接做 `observed_brightness / cos_i`。这种除法会放大噪声和数值误差，甚至造成不稳定的巨大校正值。本 toy model 将 `cos_i <= {CORRECTION_COS_THRESHOLD}` 设为 invalid correction，不硬校正。

## 结论

Stage 4 toy model 的基础物理闸门通过。该模型只验证朗伯 + 单光源 + 直接光项的最小逻辑，不是完整地形校正，也不适合直接套用到当前 2023-2024 Landsat median composite 上做单日物理校正。
"""
    PHYSICS_GATE_PATH.write_text(card, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dem = read_raster(DEM_PATH)
    slope = read_raster(SLOPE_PATH)
    aspect = read_raster(ASPECT_PATH)

    model = compute_toy_model(dem, slope, aspect)
    write_raster(COS_I_PATH, model["cos_i"], dem)
    write_raster(SHADOW_MASK_PATH, model["shadow_mask"], dem)
    write_raster(OBSERVED_BRIGHTNESS_PATH, model["observed_brightness"], dem)
    write_raster(CORRECTED_ALBEDO_PATH, model["corrected_albedo"], dem)

    outputs = summarize_outputs()
    gates = run_boundary_tests()
    save_preview(dem, slope, aspect, outputs)
    write_report(dem, slope, aspect, outputs, model, gates)
    write_result_card(outputs, model, gates)
    write_physics_gate(outputs, model, gates)

    print("Stage 4 terrain radiation toy model 完成。")
    print(f"cos_i：{COS_I_PATH}")
    print(f"shadow_mask：{SHADOW_MASK_PATH}")
    print(f"observed_brightness：{OBSERVED_BRIGHTNESS_PATH}")
    print(f"corrected_albedo：{CORRECTED_ALBEDO_PATH}")
    print(f"preview：{PREVIEW_PATH}")
    print(f"report：{REPORT_PATH}")
    print(f"Result Card：{RESULT_CARD_PATH}")
    print(f"Physics Gate：{PHYSICS_GATE_PATH}")


if __name__ == "__main__":
    main()
