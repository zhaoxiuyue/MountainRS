#!/usr/bin/env python3
"""生成逐项 Gate receipt：把冻结判据原文、实测值与通过状态并列成可复核收据。

收据由判定表与单元表机械生成，不手工誊抄——手抄一遍就是引入不一致的机会。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

CONTAINER = Path(__file__).resolve().parents[1]

# 判据文本 → 收据字段的对应关系。文本取自冻结配置，此处只做定位不做改写。
CRITERION_KEYS = {
    "median_relative_improvement": "相对 C0 的 MAE 中位相对改善 ≥ 0.05",
    "fold_direction_consistency": "5 个 fold 中至少 4 个方向一致（改善为正）",
    "parameter_boundary_hits": "参数未大量命中边界：边界命中单元占比 ≤ 0.10",
    "numerical_stability": "梯度/数值稳定性检查通过（条件数与 Stage 7.5 工具箱的 support_gate 一致）",
    "support_gate": "该候选的支持域通过 support_gate",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--verdicts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = load_json(CONTAINER / "configs/optical-operator-config-v1.json")
    units = load_json(args.units.resolve())
    verdicts = load_json(args.verdicts.resolve())
    frozen_criteria = config["verdict_rules"]["qualified_criteria"]["all_must_hold"]

    # support_gate 的逐单元账本：谁被挡住、为什么，全部保留在机会分母里
    gate_ledger: dict[str, dict[str, int]] = {}
    for unit in units["units"]:
        for cid, entry in unit["candidates"].items():
            tally = gate_ledger.setdefault(cid, Counter())
            tally[entry["state"]] += 1
            if entry["state"] == "unsupported":
                tally[f"reason::{entry['reason']}"] += 1

    receipts = []
    for cid, verdict in verdicts["candidates"].items():
        receipt: dict[str, Any] = {
            "candidate_id": cid,
            "terminal_state": verdict.get("terminal_state"),
            "opportunity_denominator": dict(sorted(gate_ledger.get(cid, {}).items())),
        }
        if "checks" not in verdict:
            receipt["basis"] = verdict.get("verdict_basis") or verdict.get("note")
            receipt["criteria_not_applicable"] = (
                "本候选未运行或不参与资格化，qualified_criteria 不适用。")
            receipts.append(receipt)
            continue

        items = []
        for key, check in verdict["checks"].items():
            text = CRITERION_KEYS.get(key)
            if text is None or text not in frozen_criteria:
                raise SystemExit(f"stop: 判据 {key} 无法在冻结配置中定位，拒绝生成收据")
            items.append({
                "criterion_frozen_text": text,
                "measured": {k: v for k, v in check.items() if k != "passed"},
                "passed": check["passed"],
            })
        receipt.update({
            "criteria": items,
            "all_criteria_hold": verdict["all_criteria_hold"],
            "reason_code": verdict.get("reason_code"),
            "closed_set_exclusion_basis": verdict.get("closed_set_exclusion_basis"),
            "secondary_reported": {
                "median_signed_bias": verdict["median_signed_bias"],
                "median_p90_abs": verdict["median_p90_abs"],
                "median_coverage": verdict["median_coverage"],
                "boundary_hit_fraction": verdict["boundary_hit_fraction"],
                "alpha_absorption": verdict["alpha_absorption"],
            },
            "descriptive_transfer": verdict.get("descriptive_transfer"),
        })
        receipts.append(receipt)

    output = {
        "schema": "mountainrs-stage7.6-gate-receipts-v1",
        "purpose": "逐候选逐项判据收据。每一条都并列冻结判据原文与实测值，使『为何是这个终态』可被独立复核。",
        "criteria_source": "configs/optical-operator-config-v1.json#verdict_rules.qualified_criteria",
        "generated_from": {
            "unit_table": str(args.units),
            "verdict_table": str(args.verdicts),
        },
        "support_gate_note": (
            "opportunity_denominator 保留每个候选在全部 180 个单元上的状态分布与 reason code。"
            "unsupported 单元不产生指标，但不从分母中消失——这是防止『收缩 support 使失败消失』的账本。"),
        "tie_resolution": verdicts.get("tie_resolution"),
        "frozen_l2_stack_entry": verdicts.get("frozen_l2_stack_entry"),
        "receipts": receipts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for r in receipts:
        if "criteria" not in r:
            print(f"{r['candidate_id']:>4}  {r['terminal_state']}  （不适用资格判据）")
            continue
        passed = sum(1 for c in r["criteria"] if c["passed"])
        print(f"{r['candidate_id']:>4}  {r['terminal_state']}   判据 {passed}/{len(r['criteria'])} 通过")
        for c in r["criteria"]:
            print(f"        [{'✓' if c['passed'] else '✗'}] {c['criterion_frozen_text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
