#!/usr/bin/env python3
"""生成不可变 dataset / domain / split manifest（Stage 7.8 passCriteria 8）。

manifest 记录证据身份与可复现获取参数，不搬运数据本体——依据见
configs/domain-split-and-leakage-v1.json 的 evidence_stack_form。

逐域报告观测机会、有效支持、主动拒绝与缺失来源（passCriteria 5）：
不合格的 acquisition 保留在机会分母中并携带 reason code，不静默消失。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

CONTAINER = Path(__file__).resolve().parents[1]
COVERAGE_FLOOR, COVERAGE_STRONG = 0.30, 0.50


def load(rel: str) -> dict:
    return json.loads((CONTAINER / rel).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    selection = load("outputs/domain-selection-v2.json")
    stage2 = load("outputs/domain-screening-stage2-v1.json")
    stage3 = load("outputs/domain-screening-stage3-v2.json")
    split = load("configs/domain-split-and-leakage-v1.json")
    registry = load("evidence/reference-registry-v1.json")

    s2_by_id = {c["candidate_id"]: c for c in stage2["candidates"]}
    s3_by_id = {c["candidate_id"]: c for c in stage3["candidates"]}
    ref_entry = next(e for e in registry["entries"]
                     if e["source_id"] == "COPERNICUS/S2_SR_HARMONIZED")
    match_by_id = {m["candidate_id"]: m
                   for m in ref_entry["temporal_matching"]["per_domain"]}

    role_of = {}
    for role in ("calibration", "evaluation"):
        for did in split["split"][role]["domains"]:
            role_of[did] = role

    domains = []
    for entry in selection["selected"]:
        cid = entry["candidate_id"]
        s2rec, s3rec = s2_by_id[cid], s3_by_id[cid]
        rows = s2rec["all_date_coverage"]
        scored = [r for r in rows if r["coverage"] is not None]
        qualified = [r for r in scored if r["coverage"] >= COVERAGE_FLOOR]
        rejected = [r for r in scored if r["coverage"] < COVERAGE_FLOOR]
        unscored = [r for r in rows if r["coverage"] is None]

        domains.append({
            "domain_id": cid,
            "informal_name": entry["informal_name"],
            "split_role": role_of[cid],
            "roi": {
                "epsg": entry["roi"]["epsg"],
                "bounds": entry["roi"]["bounds"],
                "size_m": [entry["roi"]["bounds"][2] - entry["roi"]["bounds"][0],
                           entry["roi"]["bounds"][3] - entry["roi"]["bounds"][1]],
                "construction_rule": "以中心点在其 UTM 带的投影坐标为心，构造与基准同尺寸窗口，四至向下取整到 30 m",
                "center_lonlat": entry.get("center_lonlat"),
            },
            "true_break": {
                "established_categories": s3rec["established_categories"],
                "annual_precip_mm": s3rec["measured"]["annual_precip_mm"],
                "precip_delta_vs_baseline_mm": s3rec["measured"]["precip_delta_vs_baseline_mm"],
                "igbp_dominant": s3rec["measured"]["igbp_name"],
                "igbp_dominant_fraction": s3rec["measured"]["igbp_dominant_fraction"],
                "anthropogenic_fraction": s3rec["A7_anthropogenic"]["value"],
                "categories_not_verified": ["geomorphology", "lithology"],
            },
            "terrain": {
                "elevation_min_m": s2rec and entry["roi"] and None,
                "relief_m": entry["relief_m"],
                "separation_from_baseline_km": entry["separation_km"],
            },
            "observation_opportunity": {
                "total_dates_in_window": len(rows),
                "scored": len(scored),
                "qualified": len(qualified),
                "actively_rejected": len(rejected),
                "unscored_missing_source": len(unscored),
                "reason_codes": {
                    "actively_rejected": "coverage_below_floor（base_valid_land 覆盖率 < 0.30）",
                    "unscored_missing_source": "coverage_not_computable（该日期无可评估像元或数据缺失）",
                },
                "accounting_check": len(scored) + len(unscored) == len(rows),
                "note": "被拒绝与不可评分的日期保留在机会分母中，不静默消失（passCriteria 5）。",
            },
            "effective_support": {
                "strong_scenes": sum(1 for r in qualified if r["coverage"] >= COVERAGE_STRONG),
                "max_coverage": max((r["coverage"] for r in scored), default=None),
                "median_coverage_of_qualified": (
                    sorted(r["coverage"] for r in qualified)[len(qualified) // 2]
                    if qualified else None),
            },
            "reference_matching": {
                "source": "COPERNICUS/S2_SR_HARMONIZED",
                "class": "reference_observation",
                "tight_matched": match_by_id[cid]["tight_matched"],
                "loose_matched": match_by_id[cid]["loose_matched"],
                "unmatched": match_by_id[cid]["unmatched"],
                "landsat_dates_before_s2_era": match_by_id[cid]["landsat_dates_before_s2_era"],
                "note": "S2 时代之前的 acquisition 仍属证据成员，只是无参考匹配。",
            },
            "acquisition_dates_qualified": [r["date"] for r in qualified],
            "acquisition_dates_rejected": [r["date"] for r in rejected],
        })

    manifest = {
        "schema": "mountainrs-stage7.8-dataset-domain-split-manifest-v1",
        "purpose": "不可变 dataset / domain / split manifest。记录证据身份与可复现获取参数，不搬运数据本体。",
        "recorded_on": "2026-08-16",
        "immutability": "本 manifest 一经登记即不可变。domain 集合、split 归属与 acquisition 清单的任何变更须另立版本并说明理由。",
        "baseline_domain": {
            "domain_id": "D0_minshan", "split_role": "train",
            "note": "基准 ROI，其内部 acquisition 级 split（10/3/5）由 Stage 7.1-R 冻结，本节点不改变。",
        },
        "acquisition_source": {
            "collections": ["LANDSAT/LC08/C02/T1_L2", "LANDSAT/LC09/C02/T1_L2"],
            "time_window": ["2013-01-01", "2024-12-31"],
            "acquisition_definition": "单日期为一个 acquisition，同日多景先 mosaic 再算覆盖率（与 Stage 7.1 一致）",
            "base_valid_land": "上游有效 ∩ QA clear ∩ 非水体 ∩ 反射率在 [-0.05, 1.0] ∩ 地形有效（Stage 7.1-R 定义）",
            "screening_scale_m": 120,
            "screening_scale_note": "覆盖率按 120 m 估计用于准入筛选；若日后生成 30 m 证据栈，覆盖率须按 30 m 重算并与此处对账。",
        },
        "reproducible_acquisition": {
            "statement": "本 manifest 的 roi 与 acquisition_source 字段足以重建全部数据。",
            "verification_method": "按同参数重取并比对 sha256——该方法已在 Stage 7.6 的 DEM 上实测通过。",
            "not_yet_performed": "本节点未生成 30 m 证据栈字节，故尚未执行该验证。这是 manifest 形式的已知代价，如实登记。",
        },
        "split": split["split"],
        "macro_averaging": split["macro_averaging"],
        "leakage_boundaries": split["leakage_boundaries"],
        "domains": domains,
        "totals": {
            "domain_count": len(domains),
            "qualified_acquisitions_total": sum(d["observation_opportunity"]["qualified"] for d in domains),
            "actively_rejected_total": sum(d["observation_opportunity"]["actively_rejected"] for d in domains),
            "tight_reference_matches_total": sum(d["reference_matching"]["tight_matched"] for d in domains),
        },
    }

    out = CONTAINER / "evidence/dataset-domain-split-manifest-v1.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"domain {len(domains)}   合格 acquisition 合计 "
          f"{manifest['totals']['qualified_acquisitions_total']}   "
          f"主动拒绝 {manifest['totals']['actively_rejected_total']}   "
          f"tight 匹配 {manifest['totals']['tight_reference_matches_total']}\n")
    for d in domains:
        o = d["observation_opportunity"]
        print(f"  {d['domain_id']:<26} [{d['split_role']:<11}] "
              f"机会 {o['total_dates_in_window']:>4}  合格 {o['qualified']:>3}  "
              f"拒绝 {o['actively_rejected']:>3}  不可评分 {o['unscored_missing_source']:>3}  "
              f"账目闭合 {o['accounting_check']}")
    print(f"\nsha256 {sha256_file(out)[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
