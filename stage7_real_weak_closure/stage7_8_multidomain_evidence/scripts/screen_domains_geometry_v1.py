#!/usr/bin/env python3
"""Stage 7.8 准入核验第一阶段：ROI 构造、地理分离、DEM 高差与外扩覆盖。

核验 A4（DEM 外扩 ≥ 10 km）、A5（高差 ≥ 1000 m）与 A6 的地理分离条件。
规则取自 configs/domain-candidate-universe-v1.json，本程序只执行不选择；
核验顺序取候选 ID 字典序，与任何结果无关。

Landsat 相关的 A1/A2/A3 属第二阶段，见 screen_domains_landsat_v1.py。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import ee

CONTAINER = Path(__file__).resolve().parents[1]
UNIVERSE = CONTAINER / "configs/domain-candidate-universe-v1.json"
EE_PROJECT = "gee-et-playground"
SRTM = "USGS/SRTMGL1_003"

MIN_DEM_BUFFER_M = 10000.0     # A4
MIN_RELIEF_M = 1000.0          # A5
MIN_SEPARATION_KM = 200.0      # A6 地理分离


def load_universe() -> dict:
    with UNIVERSE.open(encoding="utf-8") as stream:
        return json.load(stream)


def great_circle_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = 2 * math.asin(math.sqrt(
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2))
    return 6371.0088 * d


def utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def build_roi(center_lonlat: list[float], size_m: list[float]) -> dict:
    """确定性 ROI 构造：中心对齐后四至向下取整到 30 m 网格。"""
    lon, lat = center_lonlat
    epsg = utm_epsg(lon, lat)
    point = ee.Geometry.Point([lon, lat])
    coords = point.transform(f"EPSG:{epsg}", 1).coordinates().getInfo()
    cx, cy = coords[0], coords[1]
    half_w, half_h = size_m[0] / 2, size_m[1] / 2
    left = math.floor((cx - half_w) / 30) * 30
    bottom = math.floor((cy - half_h) / 30) * 30
    return {"epsg": epsg, "bounds": [left, bottom, left + size_m[0], bottom + size_m[1]],
            "center_projected": [cx, cy]}


def rect(bounds: list[float], epsg: int, buffer_m: float = 0.0) -> ee.Geometry:
    left, bottom, right, top = bounds
    return ee.Geometry.Rectangle(
        [left - buffer_m, bottom - buffer_m, right + buffer_m, top + buffer_m],
        proj=f"EPSG:{epsg}", geodesic=False, evenOdd=True)


def main() -> int:
    ee.Initialize(project=EE_PROJECT)
    universe = load_universe()
    size_m = [19500.0, 22560.0]
    baseline_center = [
        (universe["baseline_domain"]["bounds_lonlat"]["lon_min"]
         + universe["baseline_domain"]["bounds_lonlat"]["lon_max"]) / 2,
        (universe["baseline_domain"]["bounds_lonlat"]["lat_min"]
         + universe["baseline_domain"]["bounds_lonlat"]["lat_max"]) / 2,
    ]
    dem = ee.Image(SRTM).select("elevation")

    print(f"基准中心 {baseline_center[0]:.4f}, {baseline_center[1]:.4f}")
    print(f"ROI 尺寸 {size_m[0]:.0f} × {size_m[1]:.0f} m\n")

    records = []
    for cand in sorted(universe["candidate_universe"]["candidates"], key=lambda c: c["id"]):
        cid = cand["id"]
        roi = build_roi(cand["center_lonlat"], size_m)
        sep_km = great_circle_km(tuple(cand["center_lonlat"]), tuple(baseline_center))

        inner = rect(roi["bounds"], roi["epsg"])
        outer = rect(roi["bounds"], roi["epsg"], MIN_DEM_BUFFER_M)

        stats = dem.reduceRegion(
            reducer=ee.Reducer.minMax(), geometry=inner, scale=30,
            maxPixels=int(1e9), bestEffort=True).getInfo()
        elev_min, elev_max = stats.get("elevation_min"), stats.get("elevation_max")
        relief = (elev_max - elev_min) if (elev_min is not None and elev_max is not None) else None

        # A4：SRTM 在外扩域内是否完整覆盖——用无遮罩像元占比判定
        cover = dem.mask().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=outer, scale=90,
            maxPixels=int(1e9), bestEffort=True).getInfo().get("elevation")

        checks = {
            "A4_dem_buffer": {
                "required_buffer_m": MIN_DEM_BUFFER_M,
                "srtm_coverage_fraction_in_buffered_rect": cover,
                "passed": bool(cover is not None and cover >= 0.999),
                "note": "SRTM 在外扩域内的有效像元占比。覆盖率按 90 m 估计——"
                        "该量是面积比例，尺度对其影响可忽略。",
            },
            "A5_relief": {
                "elevation_min_m": elev_min, "elevation_max_m": elev_max,
                "relief_m": relief, "threshold_m": MIN_RELIEF_M,
                "passed": bool(relief is not None and relief >= MIN_RELIEF_M),
            },
            "A6_geographic_separation": {
                "great_circle_km": sep_km, "threshold_km": MIN_SEPARATION_KM,
                "passed": bool(sep_km >= MIN_SEPARATION_KM),
            },
        }
        stage1_pass = all(c["passed"] for c in checks.values())
        records.append({
            "candidate_id": cid, "informal_name": cand["informal_name"],
            "center_lonlat": cand["center_lonlat"],
            "roi": roi, "checks": checks, "stage1_passed": stage1_pass,
            "stage1_reason_codes": [k for k, c in checks.items() if not c["passed"]],
        })
        mark = "✓" if stage1_pass else "✗"
        print(f"  [{mark}] {cid:<26} 分离 {sep_km:6.0f} km   "
              f"高程 {elev_min if elev_min is not None else '—'}–"
              f"{elev_max if elev_max is not None else '—'} m   "
              f"高差 {relief if relief is not None else '—'}   "
              f"DEM 外扩覆盖 {cover:.4f}" if cover is not None else "")

    output = {
        "schema": "mountainrs-stage7.8-domain-screening-stage1-v1",
        "purpose": "准入核验第一阶段：A4（DEM 外扩）、A5（高差）、A6 地理分离。",
        "rules_source": "configs/domain-candidate-universe-v1.json",
        "verification_order": "候选 ID 字典序，与任何结果无关",
        "roi_construction": {
            "rule": "以中心点在其 UTM 带的投影坐标为心，构造与基准同尺寸窗口，四至向下取整到 30 m",
            "size_m": size_m,
        },
        "baseline_center_lonlat": baseline_center,
        "srtm_asset": SRTM,
        "candidates": records,
        "stage1_passed_count": sum(1 for r in records if r["stage1_passed"]),
        "not_yet_verified": ["A1 传感器与时间范围", "A2 合格 acquisition 数",
                             "A3 覆盖率", "A6 真断裂类别"],
    }
    out_path = CONTAINER / "outputs/domain-screening-stage1-v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n第一阶段通过 {output['stage1_passed_count']}/8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
