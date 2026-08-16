#!/usr/bin/env python3
"""Stage 7.8 准入汇总与确定性选择。

严格执行 configs/domain-candidate-universe-v1.json 的 deterministic_selection：
排序三级键为「合格 acquisition 数降序 → 与基准大圆距离降序 → 候选 ID 字典序」。
本程序不含任何自由裁量，也不因核验中发现的问题调整规则——发现的问题另行登记，
由所有者裁决，不得静默修改准入条件使某域合格或不合格。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CONTAINER = Path(__file__).resolve().parents[1]
TARGET_MAX, TARGET_MIN = 5, 3


def load(name: str) -> dict:
    return json.loads((CONTAINER / "outputs" / name).read_text(encoding="utf-8"))


def main() -> int:
    s1 = load("domain-screening-stage1-v1.json")
    s2 = load("domain-screening-stage2-v1.json")
    s3 = load("domain-screening-stage3-v1.json")

    by_id = {}
    for record in s1["candidates"]:
        by_id[record["candidate_id"]] = {
            "candidate_id": record["candidate_id"],
            "informal_name": record["informal_name"],
            "roi": record["roi"],
            "separation_km": record["checks"]["A6_geographic_separation"]["great_circle_km"],
            "relief_m": record["checks"]["A5_relief"]["relief_m"],
            "stage1": record["checks"], "stage1_passed": record["stage1_passed"],
        }
    for record in s2["candidates"]:
        entry = by_id[record["candidate_id"]]
        entry["stage2"] = record["checks"]
        entry["stage2_passed"] = record["stage2_passed"]
        entry["qualified_acquisitions"] = record["checks"]["A2_qualified_acquisitions"]["qualified"]
    for record in s3["candidates"]:
        entry = by_id[record["candidate_id"]]
        entry["stage3"] = {k: record[k] for k in
                           ("climate_break", "vegetation_break", "established_categories",
                            "measured")}
        entry["stage3_passed"] = record["a6_category_passed"]

    rows = list(by_id.values())
    for row in rows:
        row["admitted"] = bool(row["stage1_passed"] and row.get("stage2_passed")
                               and row.get("stage3_passed"))
        row["reason_codes"] = []
        if not row["stage1_passed"]:
            row["reason_codes"].append("geometry_or_separation")
        if not row.get("stage2_passed"):
            row["reason_codes"].append("insufficient_landsat_support")
        if not row.get("stage3_passed"):
            row["reason_codes"].append("no_true_break_established")

    admitted = [r for r in rows if r["admitted"]]
    ranked = sorted(admitted, key=lambda r: (-r["qualified_acquisitions"],
                                             -r["separation_km"],
                                             r["candidate_id"]))
    for index, row in enumerate(ranked, 1):
        row["rank"] = index
    selected = ranked[:TARGET_MAX]
    reserves = ranked[TARGET_MAX:]

    verdict = ("sufficient" if len(admitted) >= TARGET_MIN
               else "insufficient_domains")

    output = {
        "schema": "mountainrs-stage7.8-domain-selection-v1",
        "purpose": "准入汇总与确定性选择结果。",
        "rules_source": "configs/domain-candidate-universe-v1.json#deterministic_selection",
        "ranking_keys": ["合格 acquisition 数降序", "与基准大圆距离降序", "候选 ID 字典序"],
        "candidates_evaluated": len(rows),
        "admitted_count": len(admitted),
        "selected": [{"rank": r["rank"], "candidate_id": r["candidate_id"],
                      "informal_name": r["informal_name"],
                      "qualified_acquisitions": r["qualified_acquisitions"],
                      "separation_km": r["separation_km"],
                      "relief_m": r["relief_m"],
                      "established_breaks": r["stage3"]["established_categories"],
                      "roi": r["roi"]} for r in selected],
        "reserves_in_order": [{"rank": r["rank"], "candidate_id": r["candidate_id"],
                               "qualified_acquisitions": r["qualified_acquisitions"],
                               "established_breaks": r["stage3"]["established_categories"]}
                              for r in reserves],
        "rejected": [{"candidate_id": r["candidate_id"], "reason_codes": r["reason_codes"]}
                     for r in rows if not r["admitted"]],
        "verdict": verdict,
        "full_ledger": rows,
        "substitution_note": "冻结后若某域资格失效，只能按 reserves_in_order 顺序替补，"
                             "不得按模型表现换域。本节点不运行模型。",
    }
    out_path = CONTAINER / "outputs/domain-selection-v1.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"候选 {len(rows)}   合格 {len(admitted)}   判定 {verdict}\n")
    print("按冻结排序选定：")
    for r in selected:
        breaks = "+".join(r["stage3"]["established_categories"])
        igbp = r["stage3"]["measured"]["igbp_name"]
        print(f"  {r['rank']}. {r['candidate_id']:<26} 合格景 {r['qualified_acquisitions']:>4}  "
              f"分离 {r['separation_km']:>5.0f} km  高差 {r['relief_m']:>5.0f} m  "
              f"IGBP {igbp:<8} 断裂 {breaks}")
    if reserves:
        print("\n替补（按序）：")
        for r in reserves:
            breaks = "+".join(r["stage3"]["established_categories"])
            print(f"  {r['rank']}. {r['candidate_id']:<26} 合格景 {r['qualified_acquisitions']:>4}  "
                  f"IGBP {r['stage3']['measured']['igbp_name']:<8} 断裂 {breaks}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
