#!/usr/bin/env python3
"""Stage 7.8 准入核验第三阶段：真断裂类别（A6 的类别部分）。

冻结判据列出四类断裂（气候 / 地貌 / 植被 / 岩性），要求至少一类成立。
本阶段只能核验其中两类：

  气候——Köppen-Geiger 分类在本 GEE 环境不可达，故走判据中已写明的替代分支
        「年降水量与基准相差 ≥ 400 mm」，数据取 WorldClim V1 BIO12。
  植被——MODIS MCD12Q1 的 IGBP 主导类别（LC_Type1 众数）。

地貌与岩性两类**未核验**：缺乏可核验的全球栅格，而判据规定无权威栅格时须以
已发表分区图为准并登记出处——由执行手凭印象填写分区结论正是判据所禁止的。
其后果是判定偏严：真有地貌或岩性断裂而气候、植被均不断裂的候选会被判不成立。
偏严不产生假阳性，是安全方向，但必须如实登记而非默认。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import ee

CONTAINER = Path(__file__).resolve().parents[1]
EE_PROJECT = "gee-et-playground"
PRECIP_DELTA_MM = 400.0
MODIS_YEAR = "2022"

IGBP_NAMES = {
    1: "常绿针叶林", 2: "常绿阔叶林", 3: "落叶针叶林", 4: "落叶阔叶林", 5: "混交林",
    6: "郁闭灌丛", 7: "开放灌丛", 8: "木本稀树草原", 9: "稀树草原", 10: "草地",
    11: "永久湿地", 12: "农田", 13: "城市建成区", 14: "农田/自然植被镶嵌",
    15: "永久冰雪", 16: "裸地或稀疏植被", 17: "水体",
}


def region_of(epsg: int, bounds: list[float]) -> ee.Geometry:
    return ee.Geometry.Rectangle(bounds, proj=f"EPSG:{epsg}",
                                 geodesic=False, evenOdd=True)


def climate_and_vegetation(region: ee.Geometry) -> dict:
    bio = ee.Image("WORLDCLIM/V1/BIO")
    precip = bio.select("bio12").reduceRegion(
        ee.Reducer.mean(), region, 1000, maxPixels=int(1e9), bestEffort=True
    ).get("bio12")
    temp = bio.select("bio01").reduceRegion(
        ee.Reducer.mean(), region, 1000, maxPixels=int(1e9), bestEffort=True
    ).get("bio01")
    lc = (ee.ImageCollection("MODIS/061/MCD12Q1")
          .filterDate(f"{MODIS_YEAR}-01-01", f"{MODIS_YEAR}-12-31").first()
          .select("LC_Type1"))
    mode = lc.reduceRegion(ee.Reducer.mode(), region, 500,
                           maxPixels=int(1e9), bestEffort=True).get("LC_Type1")
    hist = lc.reduceRegion(ee.Reducer.frequencyHistogram(), region, 500,
                           maxPixels=int(1e9), bestEffort=True).get("LC_Type1")
    return ee.Dictionary({"annual_precip_mm": precip, "annual_mean_temp_x10": temp,
                          "igbp_mode": mode, "igbp_histogram": hist}).getInfo()


def main() -> int:
    ee.Initialize(project=EE_PROJECT)
    stage1 = json.loads((CONTAINER / "outputs/domain-screening-stage1-v1.json")
                        .read_text(encoding="utf-8"))
    universe = json.loads((CONTAINER / "configs/domain-candidate-universe-v1.json")
                          .read_text(encoding="utf-8"))

    base_bounds = universe["baseline_domain"]["bounds_utm48n"]
    base_region = region_of(32648, base_bounds)
    base = climate_and_vegetation(base_region)
    base_precip = base["annual_precip_mm"]
    base_igbp = int(base["igbp_mode"])
    print(f"基准 D0_minshan：年降水 {base_precip:.0f} mm   "
          f"年均温 {base['annual_mean_temp_x10']/10:.1f} °C   "
          f"IGBP 主导 {base_igbp} {IGBP_NAMES.get(base_igbp, '?')}\n")

    records = []
    for record in stage1["candidates"]:      # 已按候选 ID 字典序
        if not record["stage1_passed"]:
            continue
        cid = record["candidate_id"]
        region = region_of(record["roi"]["epsg"], record["roi"]["bounds"])
        got = climate_and_vegetation(region)
        precip, igbp = got["annual_precip_mm"], int(got["igbp_mode"])

        climate_break = abs(precip - base_precip) >= PRECIP_DELTA_MM
        vegetation_break = igbp != base_igbp
        established = [k for k, v in (("climate", climate_break),
                                      ("vegetation", vegetation_break)) if v]

        entry = {
            "candidate_id": cid,
            "informal_name": record["informal_name"],
            "measured": {
                "annual_precip_mm": precip,
                "annual_mean_temp_c": got["annual_mean_temp_x10"] / 10,
                "igbp_mode": igbp, "igbp_name": IGBP_NAMES.get(igbp, "?"),
                "precip_delta_vs_baseline_mm": precip - base_precip,
            },
            "climate_break": {"criterion": f"|年降水差| ≥ {PRECIP_DELTA_MM} mm",
                              "value_mm": abs(precip - base_precip),
                              "established": climate_break},
            "vegetation_break": {"criterion": "IGBP 主导类别与基准不同",
                                 "baseline": f"{base_igbp} {IGBP_NAMES.get(base_igbp,'?')}",
                                 "candidate": f"{igbp} {IGBP_NAMES.get(igbp,'?')}",
                                 "established": vegetation_break},
            "geomorphology_break": {"verified": False,
                                    "reason": "缺乏可核验的全球栅格；判据规定无权威栅格时须以已发表分区图为准并登记出处，不得由执行手凭印象填写。"},
            "lithology_break": {"verified": False, "reason": "同上。"},
            "established_categories": established,
            "a6_category_passed": len(established) > 0,
            "expected_break_declared": record and next(
                (c["expected_break"] for c in universe["candidate_universe"]["candidates"]
                 if c["id"] == cid), []),
        }
        entry["expectation_vs_verified"] = {
            "declared": entry["expected_break_declared"],
            "verified_subset": established,
            "note": "declared 是冻结时登记的预期，verified 是本次核验成立的类别。"
                    "二者不一致不影响判定——判定只看 verified。",
        }
        records.append(entry)
        mark = "✓" if entry["a6_category_passed"] else "✗"
        print(f"  [{mark}] {cid:<26} 降水 {precip:>5.0f} mm (Δ{precip-base_precip:+6.0f})  "
              f"IGBP {igbp:>2} {IGBP_NAMES.get(igbp,'?'):<10} "
              f"成立: {'+'.join(established) if established else '无'}")

    output = {
        "schema": "mountainrs-stage7.8-domain-screening-stage3-v1",
        "purpose": "准入核验第三阶段：A6 的真断裂类别部分。",
        "baseline": {"id": "D0_minshan", "annual_precip_mm": base_precip,
                     "annual_mean_temp_c": base["annual_mean_temp_x10"] / 10,
                     "igbp_mode": base_igbp, "igbp_name": IGBP_NAMES.get(base_igbp, "?")},
        "data_sources": {
            "climate": "WORLDCLIM/V1/BIO（bio12 年降水、bio01 年均温）",
            "vegetation": f"MODIS/061/MCD12Q1 LC_Type1（IGBP），{MODIS_YEAR} 年",
            "koppen": "不可用——projects/sat-io 的 Köppen 资产在本环境不可达，"
                      "故走判据中已写明的替代分支「年降水差 ≥ 400 mm」",
        },
        "categories_not_verified": {
            "geomorphology": "缺乏可核验的全球栅格",
            "lithology": "缺乏可核验的全球栅格",
            "consequence": "判定偏严——真有地貌或岩性断裂而气候、植被均不断裂的候选会被判不成立。"
                           "偏严不产生假阳性，是安全方向，但如实登记而非默认。",
        },
        "candidates": records,
        "a6_category_passed_count": sum(1 for r in records if r["a6_category_passed"]),
    }
    out_path = CONTAINER / "outputs/domain-screening-stage3-v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n真断裂类别成立 {output['a6_category_passed_count']}/{len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
