#!/usr/bin/env python3
"""Stage 7.8 准入核验第二阶段：Landsat 可用性与支持（A1/A2/A3）。

acquisition 定义与 Stage 7.1 一致：单日期为一个 acquisition，同日多景先 mosaic
再算覆盖率。base_valid_land 的构成沿用 Stage 7.1-R 冻结定义。

覆盖率按 120 m 尺度估计。该量是面积比例，尺度对其影响可忽略；正式证据栈仍按
30 m 生成。此为准入筛选的计算折中，如实登记而非默认。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee

CONTAINER = Path(__file__).resolve().parents[1]
EE_PROJECT = "gee-et-playground"
SRTM = "USGS/SRTMGL1_003"

START, END = "2013-01-01", "2024-12-31"        # A1
MIN_QUALIFIED_ACQUISITIONS = 10                # A2
COVERAGE_FLOOR = 0.30                          # A3 每景下限
COVERAGE_STRONG = 0.50                         # A3 强景阈值
MIN_STRONG_SCENES = 5                          # A3 强景数量
SCREEN_SCALE_M = 120

SR_SCALE, SR_OFFSET = 0.0000275, -0.2
SR_MIN, SR_MAX = -0.05, 1.0
QA_CLEAR_MASK, QA_WATER_BIT = 0b111111, 7


def base_valid_land(image: ee.Image, dem_valid: ee.Image) -> ee.Image:
    """沿用 Stage 7.1-R：上游有效 ∩ QA clear ∩ 非水体 ∩ 反射率在域 ∩ 地形有效。"""
    qa = image.select("QA_PIXEL")
    clear = qa.bitwiseAnd(QA_CLEAR_MASK).eq(0)
    not_water = qa.rightShift(QA_WATER_BIT).bitwiseAnd(1).eq(0)
    b4 = image.select("SR_B4").multiply(SR_SCALE).add(SR_OFFSET)
    b5 = image.select("SR_B5").multiply(SR_SCALE).add(SR_OFFSET)
    in_range = (b4.gte(SR_MIN).And(b4.lte(SR_MAX))
                .And(b5.gte(SR_MIN)).And(b5.lte(SR_MAX)))
    return clear.And(not_water).And(in_range).And(dem_valid).unmask(0)


def screen_one(roi_record: dict) -> dict:
    epsg, bounds = roi_record["roi"]["epsg"], roi_record["roi"]["bounds"]
    region = ee.Geometry.Rectangle(bounds, proj=f"EPSG:{epsg}",
                                   geodesic=False, evenOdd=True)
    dem_valid = ee.Image(SRTM).select("elevation").mask()

    collection = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
                  .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
                  .filterBounds(region).filterDate(START, END))
    dates = collection.aggregate_array("DATE_ACQUIRED").distinct().sort()

    def per_date(date):
        same_day = collection.filter(ee.Filter.eq("DATE_ACQUIRED", date))
        valid = base_valid_land(same_day.mosaic(), dem_valid)
        fraction = valid.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=SCREEN_SCALE_M,
            maxPixels=int(1e9), bestEffort=True).get("QA_PIXEL")
        return ee.Feature(None, {"date": date, "coverage": fraction,
                                 "scene_count": same_day.size()})

    features = ee.FeatureCollection(dates.map(per_date)).getInfo()["features"]
    rows = [{"date": f["properties"]["date"],
             "coverage": f["properties"].get("coverage"),
             "scene_count": f["properties"].get("scene_count")}
            for f in features]
    scored = [r for r in rows if r["coverage"] is not None]
    qualified = [r for r in scored if r["coverage"] >= COVERAGE_FLOOR]
    strong = [r for r in qualified if r["coverage"] >= COVERAGE_STRONG]

    checks = {
        "A1_sensor_and_window": {
            "collections": ["LANDSAT/LC08/C02/T1_L2", "LANDSAT/LC09/C02/T1_L2"],
            "window": [START, END], "passed": True,
            "note": "查询条件本身即 A1，与基准同传感器世代与处理链。"},
        "A2_qualified_acquisitions": {
            "total_dates": len(rows), "qualified": len(qualified),
            "threshold": MIN_QUALIFIED_ACQUISITIONS,
            "passed": len(qualified) >= MIN_QUALIFIED_ACQUISITIONS},
        "A3_coverage": {
            "floor": COVERAGE_FLOOR, "strong_threshold": COVERAGE_STRONG,
            "strong_count": len(strong), "strong_required": MIN_STRONG_SCENES,
            "max_coverage": max((r["coverage"] for r in scored), default=None),
            "median_coverage_of_qualified": (
                sorted(r["coverage"] for r in qualified)[len(qualified) // 2]
                if qualified else None),
            "passed": len(strong) >= MIN_STRONG_SCENES},
    }
    return {"candidate_id": roi_record["candidate_id"],
            "informal_name": roi_record["informal_name"],
            "checks": checks,
            "stage2_passed": all(c["passed"] for c in checks.values()),
            "stage2_reason_codes": [k for k, c in checks.items() if not c["passed"]],
            "qualified_acquisition_dates": [r["date"] for r in qualified],
            "all_date_coverage": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="只跑指定候选 ID（用于测速）")
    parser.add_argument("--output", type=Path,
                        default=CONTAINER / "outputs/domain-screening-stage2-v1.json")
    args = parser.parse_args()

    ee.Initialize(project=EE_PROJECT)
    stage1 = json.loads((CONTAINER / "outputs/domain-screening-stage1-v1.json")
                        .read_text(encoding="utf-8"))
    candidates = [c for c in stage1["candidates"] if c["stage1_passed"]]
    if args.only:
        candidates = [c for c in candidates if c["candidate_id"] == args.only]

    results = []
    for record in candidates:      # stage1 已按候选 ID 字典序
        result = screen_one(record)
        results.append(result)
        checks = result["checks"]
        print(f"  [{'✓' if result['stage2_passed'] else '✗'}] "
              f"{result['candidate_id']:<26} "
              f"日期 {checks['A2_qualified_acquisitions']['total_dates']:>4}  "
              f"合格 {checks['A2_qualified_acquisitions']['qualified']:>4}  "
              f"强景 {checks['A3_coverage']['strong_count']:>4}  "
              f"最高覆盖 {checks['A3_coverage']['max_coverage']:.3f}"
              if checks["A3_coverage"]["max_coverage"] is not None else "")

    if args.only:
        print("\n（单候选测速模式，未写出汇总）")
        return 0

    output = {
        "schema": "mountainrs-stage7.8-domain-screening-stage2-v1",
        "purpose": "准入核验第二阶段：A1 传感器与时间范围、A2 合格 acquisition 数、A3 覆盖率。",
        "acquisition_definition": "单日期为一个 acquisition，同日多景先 mosaic 再算覆盖率，与 Stage 7.1 一致。",
        "base_valid_land_definition": "上游有效 ∩ QA clear ∩ 非水体 ∩ 反射率在 [-0.05, 1.0] ∩ 地形有效，沿用 Stage 7.1-R。",
        "screening_scale_m": SCREEN_SCALE_M,
        "screening_scale_note": "覆盖率按 120 m 估计。该量是面积比例，尺度对其影响可忽略；"
                                "正式证据栈仍按 30 m 生成。此为准入筛选的计算折中，如实登记。",
        "candidates": results,
        "stage2_passed_count": sum(1 for r in results if r["stage2_passed"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"\n第二阶段通过 {output['stage2_passed_count']}/{len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
