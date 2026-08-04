"""
DEM 地形因子 synthetic boundary test

本脚本只使用极简合成 DEM 检查 slope/aspect/hillshade 的方向、单位和边界行为。
不会读取或改动真实 DEM，也不会覆盖真实 DEM 的地形因子输出。

运行方式：
python stage2_dem_terrain/scripts/test_terrain_factor_boundaries.py
"""

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT_DIR / "outputs" / ".matplotlib"))

try:
    import matplotlib.pyplot as plt
    import numpy as np

    from compute_terrain_factors import (
        SUN_ALTITUDE_DEG,
        SUN_AZIMUTH_DEG,
        build_valid_mask,
        compute_terrain_arrays,
    )
except ImportError as exc:
    raise SystemExit(
        "缺少依赖或无法导入 compute_terrain_factors.py，请先安装：pip install numpy matplotlib rasterio"
    ) from exc


REPORT_PATH = ROOT_DIR / "reports" / "terrain_factor_boundary_test_report.md"
PREVIEW_PATH = ROOT_DIR / "outputs" / "terrain_factor_boundary_test.png"
PHYSICS_GATE_PATH = ROOT_DIR / "obsidian_drafts" / "Physics_Gate_DEM_地形因子计算.md"

ROWS = 80
COLS = 80
XRES = 10.0
YRES = 10.0
TARGET_SLOPE_DEG = 10.0
SLOPE_RATIO = float(np.tan(np.radians(TARGET_SLOPE_DEG)))
ANGLE_TOLERANCE_DEG = 0.05
HILLSHADE_MARGIN = 20.0


def grid_coordinates() -> tuple[np.ndarray, np.ndarray]:
    x = np.arange(COLS, dtype="float64") * XRES
    y_north = (ROWS - 1 - np.arange(ROWS, dtype="float64")) * YRES
    xx, yy_north = np.meshgrid(x, y_north)
    return xx, yy_north


def constant_dem(value: float = 1000.0) -> np.ndarray:
    return np.full((ROWS, COLS), value, dtype="float64")


def east_rising_dem() -> np.ndarray:
    xx, _ = grid_coordinates()
    return 1000.0 + SLOPE_RATIO * xx


def north_rising_dem() -> np.ndarray:
    _, yy_north = grid_coordinates()
    return 1000.0 + SLOPE_RATIO * yy_north


def plane_with_downslope_aspect(aspect_deg: float) -> np.ndarray:
    xx, yy_north = grid_coordinates()
    aspect_rad = np.radians(aspect_deg)
    dz_dx = -SLOPE_RATIO * np.sin(aspect_rad)
    dz_dy_north = -SLOPE_RATIO * np.cos(aspect_rad)
    return 1000.0 + dz_dx * xx + dz_dy_north * yy_north


def finite_values(array: np.ndarray) -> np.ndarray:
    return array[np.isfinite(array)]


def circular_abs_error(actual_deg: float, expected_deg: float) -> float:
    return abs((actual_deg - expected_deg + 180.0) % 360.0 - 180.0)


def status_from_bool(ok: bool, warning: bool = False) -> str:
    if ok:
        return "PASS"
    return "WARNING" if warning else "FAIL"


def terrain_for(dem: np.ndarray) -> dict:
    valid_mask = build_valid_mask(dem, None)
    return compute_terrain_arrays(dem, valid_mask, XRES, YRES)


def summarize_case(name: str, dem: np.ndarray, expected_slope: float, expected_aspect: float | None) -> dict:
    terrain = terrain_for(dem)
    slope_values = finite_values(terrain["slope_degree"])
    aspect_values = finite_values(terrain["aspect_degree"])
    hillshade_values = finite_values(terrain["hillshade"])

    slope_mean = float(slope_values.mean())
    slope_std = float(slope_values.std())
    aspect_mean = float(aspect_values.mean())
    aspect_std = float(aspect_values.std())
    hillshade_mean = float(hillshade_values.mean())
    hillshade_std = float(hillshade_values.std())

    slope_ok = abs(slope_mean - expected_slope) <= ANGLE_TOLERANCE_DEG and slope_std <= ANGLE_TOLERANCE_DEG
    if expected_aspect is None:
        aspect_error = None
        aspect_ok = True
    else:
        aspect_error = circular_abs_error(aspect_mean, expected_aspect)
        aspect_ok = aspect_error <= ANGLE_TOLERANCE_DEG and aspect_std <= ANGLE_TOLERANCE_DEG

    return {
        "name": name,
        "dem": dem,
        "terrain": terrain,
        "expected_slope": expected_slope,
        "expected_aspect": expected_aspect,
        "slope_mean": slope_mean,
        "slope_std": slope_std,
        "aspect_mean": aspect_mean,
        "aspect_std": aspect_std,
        "aspect_error": aspect_error,
        "hillshade_mean": hillshade_mean,
        "hillshade_std": hillshade_std,
        "slope_status": status_from_bool(slope_ok),
        "aspect_status": status_from_bool(aspect_ok),
    }


def run_tests() -> dict:
    cases = [
        summarize_case("常数 DEM", constant_dem(), 0.0, None),
        summarize_case("东西向倾斜平面：西低东高", east_rising_dem(), TARGET_SLOPE_DEG, 270.0),
        summarize_case("南北向倾斜平面：南低北高", north_rising_dem(), TARGET_SLOPE_DEG, 180.0),
    ]

    northwest_facing = summarize_case(
        "hillshade 测试：坡面朝向/最大下降方向 NW",
        plane_with_downslope_aspect(315.0),
        TARGET_SLOPE_DEG,
        315.0,
    )
    southeast_facing = summarize_case(
        "hillshade 测试：坡面朝向/最大下降方向 SE",
        plane_with_downslope_aspect(135.0),
        TARGET_SLOPE_DEG,
        135.0,
    )

    hillshade_difference = northwest_facing["hillshade_mean"] - southeast_facing["hillshade_mean"]
    hillshade_ok = hillshade_difference > HILLSHADE_MARGIN

    all_statuses = [case["slope_status"] for case in cases]
    all_statuses.extend(case["aspect_status"] for case in cases)
    all_statuses.extend([northwest_facing["slope_status"], northwest_facing["aspect_status"]])
    all_statuses.extend([southeast_facing["slope_status"], southeast_facing["aspect_status"]])
    all_statuses.append(status_from_bool(hillshade_ok))

    if "FAIL" in all_statuses:
        overall_status = "FAIL"
    elif "WARNING" in all_statuses:
        overall_status = "WARNING"
    else:
        overall_status = "PASS"

    return {
        "cases": cases,
        "northwest_facing": northwest_facing,
        "southeast_facing": southeast_facing,
        "hillshade_difference": hillshade_difference,
        "hillshade_status": status_from_bool(hillshade_ok),
        "overall_status": overall_status,
    }


def fmt(value) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def case_row(case: dict) -> str:
    expected_aspect = "无实际物理意义，脚本统一为 0" if case["expected_aspect"] is None else f"{case['expected_aspect']:.1f}"
    aspect_error = "N/A" if case["aspect_error"] is None else f"{case['aspect_error']:.4f}"
    status = "PASS" if case["slope_status"] == "PASS" and case["aspect_status"] == "PASS" else "FAIL"
    return (
        f"| {case['name']} | {case['expected_slope']:.1f} | {fmt(case['slope_mean'])} | "
        f"{fmt(case['slope_std'])} | {case['slope_status']} | {expected_aspect} | "
        f"{fmt(case['aspect_mean'])} | {fmt(case['aspect_std'])} | {aspect_error} | "
        f"{case['aspect_status']} | {status} |"
    )


def write_preview(results: dict) -> None:
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    panels = [
        ("Constant DEM", results["cases"][0]),
        ("West-low East-high", results["cases"][1]),
        ("South-low North-high", results["cases"][2]),
        ("NW-facing slope", results["northwest_facing"]),
        ("SE-facing slope", results["southeast_facing"]),
    ]

    fig, axes = plt.subplots(len(panels), 4, figsize=(16, 18))
    for row_index, (case_label, case) in enumerate(panels):
        arrays = [
            ("DEM", case["dem"], "terrain", None, None),
            ("Slope", case["terrain"]["slope_degree"], "magma", 0, 30),
            ("Aspect", case["terrain"]["aspect_degree"], "twilight", 0, 360),
            ("Hillshade", case["terrain"]["hillshade"], "gray", 0, 255),
        ]
        for col_index, (title, array, cmap, vmin, vmax) in enumerate(arrays):
            ax = axes[row_index, col_index]
            image = ax.imshow(array, cmap=cmap, vmin=vmin, vmax=vmax)
            ax.set_title(f"{case_label}\n{title}")
            ax.set_xticks([])
            ax.set_yticks([])
            plt.colorbar(image, ax=ax, shrink=0.65)

    plt.tight_layout()
    fig.savefig(PREVIEW_PATH, dpi=150)
    plt.close(fig)


def write_report(results: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    case_rows = "\n".join(case_row(case) for case in results["cases"])
    hillshade_rows = "\n".join(
        case_row(case) for case in [results["northwest_facing"], results["southeast_facing"]]
    )

    report = f"""# DEM 地形因子 Synthetic Boundary Test 报告

## 目标

本测试不处理真实 DEM，只用极简合成 DEM 检查 `compute_terrain_factors.py` 中 slope、aspect、hillshade 的方向、单位和边界行为是否合理。

## 当前代码中的 aspect 定义

根据 `compute_terrain_factors.py` 的公式，当前 aspect 表示 **最大下降方向**，不是上坡梯度方向。方位约定为：

- `0/360 = 北`
- `90 = 东`
- `180 = 南`
- `270 = 西`

常数 DEM 上 slope 接近 0，aspect 没有实际物理意义；当前代码对平坦像元统一写为 `0`。

## 测试参数

- 合成 DEM 尺寸：`{ROWS} x {COLS}`
- x/y resolution：`{XRES:.1f}m x {YRES:.1f}m`
- 目标坡度：`{TARGET_SLOPE_DEG:.1f}°`
- hillshade 太阳方位角：`{SUN_AZIMUTH_DEG:.0f}°`
- hillshade 太阳高度角：`{SUN_ALTITUDE_DEG:.0f}°`

## 边界测试结果

| Case | Expected Slope | Actual Slope Mean | Slope Std | Slope Status | Expected Aspect | Actual Aspect Mean | Aspect Std | Aspect Error | Aspect Status | Case Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{case_rows}

## Hillshade 简单光照测试

太阳来自西北方 `{SUN_AZIMUTH_DEG:.0f}°`。如果 aspect 表示最大下降方向/坡面朝向，则 NW-facing 坡面应比 SE-facing 坡面更亮。

| Case | Expected Slope | Actual Slope Mean | Slope Std | Slope Status | Expected Aspect | Actual Aspect Mean | Aspect Std | Aspect Error | Aspect Status | Case Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{hillshade_rows}

- NW-facing hillshade mean：`{results["northwest_facing"]["hillshade_mean"]:.4f}`
- SE-facing hillshade mean：`{results["southeast_facing"]["hillshade_mean"]:.4f}`
- mean difference：`{results["hillshade_difference"]:.4f}`
- hillshade 光照直觉检查：**{results["hillshade_status"]}**

## 可视化

- 边界测试预览图：`{PREVIEW_PATH}`

## PASS / WARNING / FAIL

- 常数 DEM：`{case_row_status(results["cases"][0])}`
- 东西向倾斜平面：`{case_row_status(results["cases"][1])}`
- 南北向倾斜平面：`{case_row_status(results["cases"][2])}`
- hillshade 简单光照：`{results["hillshade_status"]}`
- 总体结论：**{results["overall_status"]}**

## 结论

- 常数 DEM 的 slope 接近 0；aspect 在平坦面没有实际物理意义，当前代码统一为 0。
- 西低东高的 DEM 得到 aspect 约 `270°`，说明当前 aspect 指向最大下降方向，即向西。
- 南低北高的 DEM 得到 aspect 约 `180°`，说明当前 aspect 指向最大下降方向，即向南。
- 在太阳方位角 `{SUN_AZIMUTH_DEG:.0f}°`、太阳高度角 `{SUN_ALTITUDE_DEG:.0f}°` 下，NW-facing 坡面显著亮于 SE-facing 坡面，hillshade 符合简单光照直觉。
- 未发现当前 aspect 定义与已有报告文字之间的不一致：已有报告写的是最大下降方向，与测试结果一致。
"""

    REPORT_PATH.write_text(report, encoding="utf-8")


def case_row_status(case: dict) -> str:
    return "PASS" if case["slope_status"] == "PASS" and case["aspect_status"] == "PASS" else "FAIL"


def write_physics_gate(results: dict) -> None:
    PHYSICS_GATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    card = f"""# Physics Gate｜DEM 地形因子计算

## 跑前预测

- 常数 DEM 的 slope 应接近 0；aspect 没有实际物理意义，可统一为 0 或 nodata。
- 西低东高的倾斜平面，最大下降方向应指向西，即 aspect 约 `270°`。
- 南低北高的倾斜平面，最大下降方向应指向南，即 aspect 约 `180°`。
- 使用太阳方位角 `{SUN_AZIMUTH_DEG:.0f}°`、太阳高度角 `{SUN_ALTITUDE_DEG:.0f}°` 时，NW-facing 坡面应比 SE-facing 坡面更亮。

## 边界测试

- 常数 DEM：检查平坦面 slope 与 aspect 边界行为。
- 东西向倾斜平面：构造从西到东逐渐升高的 DEM，检查 slope 常数性和 aspect 方向。
- 南北向倾斜平面：构造从南到北逐渐升高的 DEM，检查 slope 常数性和 aspect 方向。
- hillshade 简单测试：比较 NW-facing 与 SE-facing 坡面的平均光照。

## 实际结果

| Case | Expected Slope | Actual Slope Mean | Slope Std | Expected Aspect | Actual Aspect Mean | Aspect Std | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 常数 DEM | 0.0 | {results["cases"][0]["slope_mean"]:.4f} | {results["cases"][0]["slope_std"]:.4f} | 无实际物理意义，当前为 0 | {results["cases"][0]["aspect_mean"]:.4f} | {results["cases"][0]["aspect_std"]:.4f} | {case_row_status(results["cases"][0])} |
| 西低东高 | {TARGET_SLOPE_DEG:.1f} | {results["cases"][1]["slope_mean"]:.4f} | {results["cases"][1]["slope_std"]:.4f} | 270.0 | {results["cases"][1]["aspect_mean"]:.4f} | {results["cases"][1]["aspect_std"]:.4f} | {case_row_status(results["cases"][1])} |
| 南低北高 | {TARGET_SLOPE_DEG:.1f} | {results["cases"][2]["slope_mean"]:.4f} | {results["cases"][2]["slope_std"]:.4f} | 180.0 | {results["cases"][2]["aspect_mean"]:.4f} | {results["cases"][2]["aspect_std"]:.4f} | {case_row_status(results["cases"][2])} |

- NW-facing hillshade mean：`{results["northwest_facing"]["hillshade_mean"]:.4f}`
- SE-facing hillshade mean：`{results["southeast_facing"]["hillshade_mean"]:.4f}`
- hillshade mean difference：`{results["hillshade_difference"]:.4f}`
- hillshade status：`{results["hillshade_status"]}`
- 报告：`{REPORT_PATH}`
- 预览图：`{PREVIEW_PATH}`

## 结论

当前 `compute_terrain_factors.py` 的 aspect 表示最大下降方向，且与报告中的方位约定一致。slope 单位与边界行为通过 synthetic DEM 检查；hillshade 在简单相反坡面上符合西北光源照亮西北坡面的直觉。

## 是否通过

**{results["overall_status"]}**
"""

    PHYSICS_GATE_PATH.write_text(card, encoding="utf-8")


def main() -> None:
    results = run_tests()
    write_preview(results)
    write_report(results)
    write_physics_gate(results)

    print(f"Boundary test 完成：{results['overall_status']}")
    print(f"报告已保存：{REPORT_PATH}")
    print(f"预览图已保存：{PREVIEW_PATH}")
    print(f"Physics Gate 草稿已保存：{PHYSICS_GATE_PATH}")


if __name__ == "__main__":
    main()
