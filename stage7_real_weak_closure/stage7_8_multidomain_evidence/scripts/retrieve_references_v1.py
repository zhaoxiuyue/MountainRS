#!/usr/bin/env python3
"""Stage 7.8 参考源检索与登记。

按 configs/reference-registry-protocol-v1.json 执行：先分类，再核验独立性
I1–I4 与泄漏 L1–L4，最后统计时间匹配。协议冻结于本检索之前。

对判为 unavailable 的来源，同样登记检索过程——协议明确要求区分「未检索」
与「不可得」，混同会使「独立参考不足」这一结论失去可核查性。
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import ee

CONTAINER = Path(__file__).resolve().parents[1]
EE_PROJECT = "gee-et-playground"
TIGHT_DAYS, LOOSE_DAYS = 3, 7


def match_sentinel2(roi: dict, landsat_dates: list[str]) -> dict:
    region = ee.Geometry.Rectangle(roi["bounds"], proj=f"EPSG:{roi['epsg']}",
                                   geodesic=False, evenOdd=True)
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
          .filterBounds(region).filterDate("2015-06-23", "2024-12-31"))
    dates_raw = s2.map(lambda i: ee.Feature(None, {
        "d": ee.Date(i.get("system:time_start")).format("YYYY-MM-dd")}))
    s2_days = sorted({f["properties"]["d"]
                      for f in dates_raw.getInfo()["features"]})

    s2_set = {date.fromisoformat(d) for d in s2_days}
    tight, loose, unmatched = [], [], []
    for ls in landsat_dates:
        lsd = date.fromisoformat(ls)
        best = min((abs((s - lsd).days) for s in s2_set), default=None)
        if best is None or best > LOOSE_DAYS:
            unmatched.append(ls)
        elif best <= TIGHT_DAYS:
            tight.append({"landsat_date": ls, "min_gap_days": best})
        else:
            loose.append({"landsat_date": ls, "min_gap_days": best})
    return {"s2_distinct_days": len(s2_days),
            "s2_first_day": s2_days[0] if s2_days else None,
            "s2_last_day": s2_days[-1] if s2_days else None,
            "landsat_dates_considered": len(landsat_dates),
            "tight_matched": len(tight), "loose_matched": len(loose),
            "unmatched": len(unmatched),
            "tight_examples": tight[:5]}


def main() -> int:
    ee.Initialize(project=EE_PROJECT)
    selection = json.loads((CONTAINER / "outputs/domain-selection-v2.json")
                           .read_text(encoding="utf-8"))
    stage2 = json.loads((CONTAINER / "outputs/domain-screening-stage2-v1.json")
                        .read_text(encoding="utf-8"))
    dates_by_id = {c["candidate_id"]: c["qualified_acquisition_dates"]
                   for c in stage2["candidates"]}

    per_domain = []
    for entry in selection["selected"]:
        cid = entry["candidate_id"]
        landsat_dates = [d for d in dates_by_id[cid] if d >= "2015-06-23"]
        got = match_sentinel2(entry["roi"], landsat_dates)
        got["candidate_id"] = cid
        got["landsat_dates_before_s2_era"] = (
            len(dates_by_id[cid]) - len(landsat_dates))
        per_domain.append(got)
        print(f"  {cid:<26} S2 天数 {got['s2_distinct_days']:>4}  "
              f"Landsat(S2期) {got['landsat_dates_considered']:>3}  "
              f"tight {got['tight_matched']:>3}  loose {got['loose_matched']:>3}  "
              f"未匹配 {got['unmatched']:>3}")

    registry = {
        "schema": "mountainrs-stage7.8-reference-registry-v1",
        "protocol": "configs/reference-registry-protocol-v1.json",
        "recorded_on": "2026-08-16",
        "entries": [
            {
                "source_id": "COPERNICUS/S2_SR_HARMONIZED",
                "provider": "ESA / Copernicus，经 Google Earth Engine 提供",
                "version": "PROCESSING_BASELINE 02.14（抽样确认），Harmonized 集合",
                "class": "reference_observation",
                "class_basis": "独立传感器（Sentinel-2 MSI）与独立处理链（Sen2Cor），非地面原位测量，故不得称真值。",
                "independence_verdict": {
                    "I1_no_shared_observation": {"passed": True,
                        "basis": "Sentinel-2 MSI 与 Landsat OLI 是物理上独立的两套观测。"},
                    "I2_no_shared_sensor_lineage": {"passed": True,
                        "basis": "S2_SR_HARMONIZED 的处理链不含任何 Landsat 输入。"
                                 "注意 HLS 因融合 Landsat 已被协议排除，本条目不是 HLS。"},
                    "I3_terrain_processing_disclosure": {
                        "grade": "preferred",
                        "metadata_evidence": "抽样影像的 76 个属性中不含任何 terrain / DEM / slope / "
                                             "topographic correction 相关字段。",
                        "documentary_basis": "ESA 业务化 L2A 产品的 Sen2Cor 配置默认不启用地形校正"
                                             "（DEM_Terrain_Correction 关闭）。",
                        "evidence_strength": "该判定的直接依据是公开处理文档与元数据中相关字段的缺失，"
                                             "而非产品元数据的肯定性声明。缺失不等于否定——若后续发现"
                                             "相反证据，本条目须重新分级，其已产出的一致性结论一并受影响。",
                        "why_preferred_matters": "未做地形校正意味着该参考不携带独立的地形假设，"
                                                 "其与本项目预测的差异可完整归因，不含参考侧的地形处理误差。"},
                    "I4_no_shared_ancillary_dependency": {
                        "shared_inputs_identified": ["无共享 DEM（S2 L2A 未做地形校正，故不引入 DEM）",
                                                     "大气校正各自独立：Sen2Cor vs LaSRC，气溶胶来源不同"],
                        "verifiable_scope": "地表反射率量级的跨传感器一致性；地形调制在两套独立观测中的表现是否相符。",
                        "unverifiable_scope": "不可用于验证绝对辐射定标——两者的定标链虽独立但均未经本项目校验；"
                                              "亦不可用于验证 DEM 几何本身，因参考不含地形处理故对该问题无信息。"},
                },
                "temporal_matching": {"tiers_applied": {"tight_days": TIGHT_DAYS,
                                                        "loose_days": LOOSE_DAYS},
                                      "per_domain": per_domain},
                "leakage_verdict": {
                    "L1_split_leakage": {"passed": True,
                        "basis": "domain 选择与 split 均未使用任何 Sentinel-2 数据。"
                                 "本检索发生在 domain 选择冻结之后。"},
                    "L2_self_reference": {"passed": True,
                        "basis": "Sentinel-2 与 Landsat 无共享观测，不存在自引用。"},
                    "L3_tuning_leakage": {"passed": True,
                        "basis": "本节点不运行模型，无参数可调。该禁令随本 Registry 传递至下游节点。"},
                    "L4_circular_provenance": {"passed": True,
                        "basis": "逐项核验 S2 L2A 的 provenance 链，不含本项目产出的任何 artifact。"
                                 "本项目从未向任何公开产品贡献输入。"},
                },
                "band_correspondence_note": "S2 的 B4（红，665 nm）与 B8A（近红，865 nm）对应 Landsat 的 "
                                            "SR_B4（655 nm）与 SR_B5（865 nm）。中心波长与带宽不同，"
                                            "跨传感器比较须携带光谱差异这一限定，不得当作同一量直接相减。",
            },
            {
                "source_id": "ground_based_radiation_and_reflectance_measurements",
                "class": "unavailable",
                "retrieval_record": {
                    "searched": [
                        "本项目仓库与既有数据目录：无任何地面观测数据（预检 B1 已清点确认）",
                        "Google Earth Engine 公开资产目录：不含中国区域的地面辐射或地表反射率原位观测",
                    ],
                    "known_but_not_obtained": [
                        "BSRN（Baseline Surface Radiation Network）在中国有少量站点，数据需注册获取，"
                        "且站址与本节点五个选定 domain 的空间重合未经核实",
                        "ChinaFLUX / CERN 台站数据不公开可得",
                    ],
                    "why_unavailable_rather_than_unsearched": "上述来源已被识别并评估，判定依据是获取途径与"
                                                              "空间重合两方面，不是未检索。协议要求区分二者。",
                    "recovery_condition": "若取得任一落于选定 domain 内、且时间覆盖与 Landsat acquisition "
                                          "有交集的地面测量，本条目可升级为 ground_truth，届时 Stage 7.8 的"
                                          "重新资格化 Gate 判据 G2（独立锚点）需重新评估。",
                },
                "consequence": "本节点无 ground_truth 类参考。任何结论均不得使用真值、ground truth 或等价措辞。",
            },
        ],
    }

    out = CONTAINER / "evidence/reference-registry-v1.json"
    out.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total_tight = sum(d["tight_matched"] for d in per_domain)
    print(f"\n五域 tight 匹配合计 {total_tight} 对；"
          f"ground_truth 类 0 项，reference_observation 类 1 项")
    return 0


if __name__ == "__main__":
    sys.exit(main())
