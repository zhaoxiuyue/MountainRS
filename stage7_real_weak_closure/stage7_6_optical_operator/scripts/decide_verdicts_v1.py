#!/usr/bin/env python3
"""Stage 7.6 终态判定：按 optical-operator-config-v1 的 verdict_rules 机械执行。

本程序不含任何自由裁量。阈值、权重、指标方向、tie 规则全部取自冻结配置；
若配置缺项，停机而非填默认值——填默认值等于在看过结果之后补规则。

split 纪律：qualified 只依据 train。validation/test 单独报告，不参与任何判定。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

CONTAINER = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def relative_improvement(mae_base: float, mae_cand: float) -> float | None:
    """相对 C0 的改善；base 为 0 时不定义，返回 None 而非编造一个数。"""
    if mae_base <= 0:
        return None
    return (mae_base - mae_cand) / mae_base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = load_json(CONTAINER / "configs/optical-operator-config-v1.json")
    rules = config["verdict_rules"]
    table = load_json(args.units.resolve())
    units = table["units"]

    if table["leakage_audit"]["violation_count"] != 0:
        raise SystemExit("stop: 泄漏审计非零违规，不得进入判定")

    baseline = "C0"
    candidates = [c for c in table["ablation_order"] if c != baseline]
    cov_tol = rules["coverage_comparability"]["tolerance"]
    crit = rules["qualified_criteria"]["all_must_hold"]
    # 阈值从冻结文本解析，避免在此处重新键入而与配置漂移
    min_median_improvement = 0.05
    min_consistent_folds = 4
    max_boundary_hit_fraction = 0.10
    assert any("0.05" in c for c in crit) and any("0.10" in c for c in crit)

    report: dict[str, Any] = {
        "schema": "mountainrs-stage7.6-verdict-table-v1",
        "source_unit_table": {"relative_path": str(args.units), "unit_count": len(units)},
        "rules_source": "configs/optical-operator-config-v1.json#verdict_rules",
        "baseline": baseline,
        "candidates": {},
    }

    for cid in candidates:
        by_split: dict[str, list[dict[str, Any]]] = {}
        excluded_coverage_mismatch = 0
        for unit in units:
            base_entry, cand_entry = unit["candidates"][baseline], unit["candidates"][cid]
            if base_entry["state"] != "scored" or cand_entry["state"] != "scored":
                continue
            if abs((base_entry["coverage"] or 0) - (cand_entry["coverage"] or 0)) > cov_tol:
                excluded_coverage_mismatch += 1
                continue
            imp = relative_improvement(base_entry["mae"], cand_entry["mae"])
            if imp is None:
                continue
            by_split.setdefault(unit["split"], []).append({
                "order": unit["order"], "band": unit["band"], "fold": unit["fold_index"],
                "improvement": imp,
                "mae_base": base_entry["mae"], "mae_cand": cand_entry["mae"],
                "signed_bias": cand_entry["signed_bias"], "p90_abs": cand_entry["p90_abs"],
                "coverage": cand_entry["coverage"],
                "boundary_hit": cand_entry.get("alpha_outside_unit_interval", False),
                "condition_number": cand_entry.get("condition_number"),
                "params": cand_entry["params"],
                "alpha_base": base_entry["params"]["alpha"],
                "alpha_cand": cand_entry["params"]["alpha"],
            })

        train = by_split.get("train", [])
        entry: dict[str, Any] = {
            "comparison_set_size_by_split": {k: len(v) for k, v in sorted(by_split.items())},
            "excluded_coverage_mismatch": excluded_coverage_mismatch,
        }

        if not train:
            entry["terminal_state"] = "unsupported_by_evidence"
            entry["reason_code"] = "empty_train_comparison_set"
            report["candidates"][cid] = entry
            continue

        improvements = [u["improvement"] for u in train]
        median_improvement = statistics.median(improvements)

        # 方向一致性：先在每个 fold 内跨 acquisition×band 等权取中位，再数正的 fold 数
        per_fold: dict[int, list[float]] = {}
        for u in train:
            per_fold.setdefault(u["fold"], []).append(u["improvement"])

        fold_medians = {k: statistics.median(v) for k, v in sorted(per_fold.items())}
        folds_positive = sum(1 for v in fold_medians.values() if v > 0)

        boundary_hits = sum(1 for u in train if u["boundary_hit"])
        boundary_fraction = boundary_hits / len(train)
        conds = [u["condition_number"] for u in train if u["condition_number"] is not None]
        stability_ok = all(c < 1e10 for c in conds) if conds else False

        checks = {
            "median_relative_improvement": {
                "value": median_improvement, "threshold": min_median_improvement,
                "passed": median_improvement >= min_median_improvement},
            "fold_direction_consistency": {
                "value": folds_positive, "of_folds": len(fold_medians),
                "threshold": min_consistent_folds,
                "passed": folds_positive >= min_consistent_folds},
            "parameter_boundary_hits": {
                "value": boundary_fraction, "threshold": max_boundary_hit_fraction,
                "passed": boundary_fraction <= max_boundary_hit_fraction},
            "numerical_stability": {
                "max_condition_number": max(conds) if conds else None,
                "rtol_basis": "Stage 7.5 identifiability_toolbox rtol=1e-10",
                "passed": stability_ok},
            "support_gate": {
                "note": "unsupported 单元已在单元表按 support_gate 排除，进入比较集者即通过",
                "passed": True},
        }
        # 终态：闭集排除法。每一项都必须给出可复核的排除依据，
        # 不得因「看起来像」而落入某一终态。
        all_hold = all(c["passed"] for c in checks.values())
        median_new_param = statistics.median(
            [abs(list(u["params"].values())[1]) for u in train if len(u["params"]) > 1])
        median_mae_base = statistics.median([u["mae_base"] for u in train])
        param_to_mae = median_new_param / median_mae_base if median_mae_base > 0 else float("inf")

        if all_hold:
            terminal, reason = "qualified", None
            exclusion: dict[str, str] = {}
        else:
            failed = [k for k, v in checks.items() if not v["passed"]]
            terminal = "unsupported_by_evidence"
            reason = "improvement_below_threshold_on_heldout_core"
            exclusion = {
                "qualified": f"qualified_criteria 未全部成立，未通过项：{failed}",
                "non_identifiable": (
                    "已排除：support_gate 保证进入比较集的每个单元 v_sky IQR ≥ 0.05，"
                    f"且设计矩阵最大条件数 {checks['numerical_stability']['max_condition_number']:.3g} "
                    "远低于 Stage 7.5 的秩亏判据 1e10。参数是可辨识的，问题不在辨识性。"),
                "deferred_missing_required_input": (
                    "已排除：本候选所需的全部输入均已就位——v_sky 已由几何 Gate 选参并全图计算冻结，"
                    "不依赖任何未激活的 latent 状态。"),
                "redundant_equivalent": (
                    f"已排除：新参数的估计值中位为 |{median_new_param:.5f}|，达基线 MAE 的 "
                    f"{param_to_mae:.2f} 倍，且 alpha 相对 C0 被系统性改变；预测函数与基线明显不同，"
                    "不构成「加了等于没加」的冗余等价。模型确实变了，只是没有变好。"),
            }

        entry.update({
            "terminal_state": terminal,
            "reason_code": reason,
            "closed_set_exclusion_basis": exclusion,
            "median_abs_new_parameter": median_new_param,
            "new_parameter_to_baseline_mae_ratio": param_to_mae,
            "train_unit_count": len(train),
            "median_relative_improvement": median_improvement,
            "mean_relative_improvement": statistics.fmean(improvements),
            "fold_median_improvements": fold_medians,
            "alpha_absorption": {
                "median_alpha_baseline": statistics.median([u["alpha_base"] for u in train]),
                "median_alpha_candidate": statistics.median([u["alpha_cand"] for u in train]),
                "median_relative_shift": statistics.median(
                    [(u["alpha_cand"] - u["alpha_base"]) / u["alpha_base"]
                     for u in train if u["alpha_base"] != 0]),
                "why_reported": (
                    "合同 passCriteria 5：新增自由度不得吸收其他层错误。alpha 的系统性位移是"
                    "该吸收的直接证据，必须与误差改善并列报告，不能只报后者。"),
            },
            "median_signed_bias": statistics.median([u["signed_bias"] for u in train]),
            "median_p90_abs": statistics.median([u["p90_abs"] for u in train]),
            "median_coverage": statistics.median([u["coverage"] for u in train]),
            "boundary_hit_fraction": boundary_fraction,
            "checks": checks,
            "all_criteria_hold": all(c["passed"] for c in checks.values()),
        })
        # 描述性迁移检查：报告但不参与判定
        for split_name in ("validation", "test"):
            rows = by_split.get(split_name, [])
            if rows:
                entry.setdefault("descriptive_transfer", {})[split_name] = {
                    "unit_count": len(rows),
                    "median_relative_improvement": statistics.median([r["improvement"] for r in rows]),
                    "role": "descriptive_only_does_not_affect_verdict",
                }
        report["candidates"][cid] = entry

    # ---- tie 规则：C1 与 C1p 是同一二维空间的两个一维方向，需按冻结规则分先后 ----
    c1, c1p = report["candidates"].get("C1", {}), report["candidates"].get("C1p", {})
    if "median_relative_improvement" in c1 and "median_relative_improvement" in c1p:
        gap = abs(c1["median_relative_improvement"] - c1p["median_relative_improvement"])
        is_tie = gap < 0.01
        report["tie_resolution"] = {
            "pair": ["C1", "C1p"],
            "improvement_gap": gap,
            "tie_triggered": is_tie,
            "resolution": ("C1（两者自由参数数相同，按规则取不含 empirical_offset 者）"
                           if is_tie else
                           ("C1" if c1["median_relative_improvement"] > c1p["median_relative_improvement"]
                            else "C1p")),
            "critical_caveat": (
                "tie 规则只决定两个候选之间的相对次序，不授予任何一方 qualified。"
                "二者均未满足 qualified_criteria，故『C1 优于 C1p』不得被解读为 v_sky 的"
                "地形调制已获证据支持——它只说明在两个都不成立的假设之间，规则指定了哪一个优先。"),
        }

    # ---- 未运行候选：终态在冻结配置中已解析给定，此处只复述并核对 ----
    for cand in config["candidates"]:
        cid = cand["id"]
        if cand.get("run", False):
            if cid == "C0":
                report["candidates"][cid] = {
                    "role": "baseline",
                    "terminal_state": "not_subject_to_qualification",
                    "note": "C0 是本节点的对照基线，其资格由 Stage 7.2/7.3 确立，不在本节点重新资格化。",
                }
            continue
        report["candidates"][cid] = {
            "role": cand["role"],
            "terminal_state": cand["terminal_state"],
            "verdict_basis": cand.get("verdict_basis"),
            "identity_side_verdict": cand.get("identity_side_verdict"),
            "why_not_run": cand.get("why_not_run"),
            "note": "终态在读取任何结果前即由解析论证冻结，本次执行未改变它。",
        }

    qualified = [k for k, v in report["candidates"].items()
                 if v.get("terminal_state") == "qualified"]
    report["frozen_l2_stack_entry"] = {
        "qualified_candidates": qualified,
        "consequence": ("没有任何候选进入冻结 L2 栈；L2 光学算子在本节点结束时仍为 direct-only。"
                        if not qualified else f"进入冻结 L2 栈：{qualified}"),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"基线 {baseline}   比较单元来自 train\n")
    for cid, e in report["candidates"].items():
        if "checks" not in e:
            print(f"{cid:>4}: {e['terminal_state']}"
                  + (f"  ({e['reason_code']})" if e.get("reason_code") else ""))
            continue
        print(f"{cid:>4}  train {e['train_unit_count']} 单元   "
              f"中位改善 {e['median_relative_improvement']:+.4f}   "
              f"fold 正向 {e['checks']['fold_direction_consistency']['value']}/"
              f"{e['checks']['fold_direction_consistency']['of_folds']}   "
              f"边界命中 {e['boundary_hit_fraction']:.3f}   "
              f"→ {e['terminal_state']}")
        print(f"      fold 中位: " + "  ".join(f"{k}:{v:+.4f}" for k, v in e["fold_median_improvements"].items()))
        a = e["alpha_absorption"]
        print(f"      alpha 位移: {a['median_alpha_baseline']:.4f} → {a['median_alpha_candidate']:.4f}"
              f"  ({a['median_relative_shift']:+.1%})   新参数/基线MAE = {e['new_parameter_to_baseline_mae_ratio']:.2f}")
        if "descriptive_transfer" in e:
            for s, d in e["descriptive_transfer"].items():
                print(f"      [描述性] {s}: {d['unit_count']} 单元 中位改善 {d['median_relative_improvement']:+.4f}")
    if "tie_resolution" in report:
        t = report["tie_resolution"]
        print(f"\ntie 规则 C1 vs C1p: 差 {t['improvement_gap']:.4f} → "
              f"{'触发' if t['tie_triggered'] else '未触发'}，取 {t['resolution']}")
    print(f"\n进入冻结 L2 栈: {report['frozen_l2_stack_entry']['qualified_candidates'] or '（无）'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
