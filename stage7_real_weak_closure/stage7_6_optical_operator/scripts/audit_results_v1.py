#!/usr/bin/env python3
"""Stage 7.6 结果阶段 fail-closed auditor：Y1–Y11 + 负例自检。

审的是判定链本身能否被机械复核，不是重跑科学结论。每条不变量都必须能被
一个具体的伪造数据触发——不能被触发的检查等于没有检查，故 --self-test
对每条注入一个 seeded violation 并要求它被抓到。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

CONTAINER = Path(__file__).resolve().parents[1]

CANDIDATE_TERMINAL_SET = {"qualified", "redundant_equivalent", "non_identifiable",
                          "unsupported_by_evidence", "deferred_missing_required_input"}
IDENTITY_TERMINAL_SET = {"identity_qualified", "identity_qualified_with_fixed_gauge",
                         "non_identifiable_equivalent", "excluded_class_or_path_violation",
                         "deferred_missing_anchor"}
NON_CANDIDATE_STATES = {"not_subject_to_qualification"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


class Ctx:
    def __init__(self, units: dict, verdicts: dict, config: dict, manifest: dict):
        self.units, self.verdicts, self.config, self.manifest = units, verdicts, config, manifest


def y1_config_hash(c: Ctx) -> tuple[bool, str]:
    recorded = c.units["provenance"]["frozen_config_sha256"]
    on_disk = sha256_file(CONTAINER / "configs/optical-operator-config-v1.json")
    expected = c.manifest["artifacts"]["optical_operator_config_v1"]["sha256"]
    ok = recorded == on_disk == expected
    return ok, f"单元表记录 {recorded[:12]}… / 磁盘 {on_disk[:12]}… / 冻结清单 {expected[:12]}…"


def y2_no_unregistered_candidate(c: Ctx) -> tuple[bool, str]:
    registered = {x["id"] for x in c.config["candidates"]}
    in_units = set()
    for unit in c.units["units"]:
        in_units |= set(unit["candidates"].keys())
    in_verdicts = set(c.verdicts["candidates"].keys())
    extra = (in_units | in_verdicts) - registered
    return not extra, f"未登记候选 {sorted(extra) or '无'}"


def y3_terminal_in_closed_set(c: Ctx) -> tuple[bool, str]:
    bad = []
    for cid, entry in c.verdicts["candidates"].items():
        state = entry.get("terminal_state")
        if state in NON_CANDIDATE_STATES:
            continue
        if state not in CANDIDATE_TERMINAL_SET:
            bad.append((cid, state))
    return not bad, f"越界终态 {bad or '无'}"


def y4_qualified_requires_all_checks(c: Ctx) -> tuple[bool, str]:
    bad = []
    for cid, entry in c.verdicts["candidates"].items():
        if entry.get("terminal_state") != "qualified":
            continue
        checks = entry.get("checks", {})
        if not checks or not all(v["passed"] for v in checks.values()):
            bad.append(cid)
    return not bad, f"qualified 但未满足全部判据 {bad or '无'}（本次无 qualified 候选，条件空真）"


def y5_split_discipline(c: Ctx) -> tuple[bool, str]:
    """validation/test 不得影响终态：其数据只能出现在 descriptive_transfer 下。"""
    bad = []
    for cid, entry in c.verdicts["candidates"].items():
        if "checks" not in entry:
            continue
        sizes = entry["comparison_set_size_by_split"]
        if entry.get("train_unit_count") != sizes.get("train"):
            bad.append((cid, "train_unit_count 与比较集不符"))
        transfer = entry.get("descriptive_transfer", {})
        for split, block in transfer.items():
            if block.get("role") != "descriptive_only_does_not_affect_verdict":
                bad.append((cid, f"{split} 缺描述性标记"))
    return not bad, f"split 纪律违规 {bad or '无'}"


def y6_unsupported_kept_in_denominator(c: Ctx) -> tuple[bool, str]:
    """unsupported 单元必须保留身份与 reason code，不得静默消失。"""
    bad = []
    for unit in c.units["units"]:
        for cid, entry in unit["candidates"].items():
            if entry["state"] == "unsupported":
                if not entry.get("reason") or "core_base_valid_land" not in unit:
                    bad.append((unit["order"], unit["band"], unit["fold_index"], cid))
    return not bad, f"缺 reason code 或机会分母的 unsupported 单元 {len(bad)} 个"


def y7_leakage_zero(c: Ctx) -> tuple[bool, str]:
    n = c.units["leakage_audit"]["violation_count"]
    return n == 0, f"泄漏违规 {n}"


def y8_coverage_comparable(c: Ctx) -> tuple[bool, str]:
    tol = c.config["verdict_rules"]["coverage_comparability"]["tolerance"]
    bad = 0
    for unit in c.units["units"]:
        base = unit["candidates"]["C0"]
        if base["state"] != "scored":
            continue
        for cid, entry in unit["candidates"].items():
            if cid == "C0" or entry["state"] != "scored":
                continue
            if abs((entry["coverage"] or 0) - (base["coverage"] or 0)) > tol:
                bad += 1
    return bad == 0, f"coverage 超容差且仍被比较的单元 {bad}（容差 {tol}）"


def y9_two_closed_sets_not_mixed(c: Ctx) -> tuple[bool, str]:
    """候选终态字段不得取身份闭集的值，反之亦然。"""
    bad = []
    for cid, entry in c.verdicts["candidates"].items():
        state = entry.get("terminal_state")
        if state in IDENTITY_TERMINAL_SET:
            bad.append((cid, "terminal_state", state))
        ident = entry.get("identity_side_verdict")
        if ident is not None and ident not in IDENTITY_TERMINAL_SET:
            bad.append((cid, "identity_side_verdict", ident))
    return not bad, f"两套闭集混用 {bad or '无'}"


def y10_unit_count(c: Ctx) -> tuple[bool, str]:
    n_acq = len({u["acquisition_id"] for u in c.units["units"]})
    n_band = len({u["band"] for u in c.units["units"]})
    n_fold = len({u["fold_index"] for u in c.units["units"]})
    expected = n_acq * n_band * n_fold
    got = len(c.units["units"])
    return got == expected, f"{n_acq}×{n_band}×{n_fold} = {expected}，实得 {got}"


def y11_absorption_reported(c: Ctx) -> tuple[bool, str]:
    """新增自由度对 alpha 的吸收必须与误差改善并列报告（合同 passCriteria 5）。"""
    missing = [cid for cid, e in c.verdicts["candidates"].items()
               if "checks" in e and "alpha_absorption" not in e]
    return not missing, f"缺 alpha 吸收报告的候选 {missing or '无'}"


CHECKS: list[tuple[str, str, Callable[[Ctx], tuple[bool, str]]]] = [
    ("Y1", "判定所用配置与冻结清单逐位一致", y1_config_hash),
    ("Y2", "无未登记候选进入单元表或判定表", y2_no_unregistered_candidate),
    ("Y3", "全部终态取自候选闭集", y3_terminal_in_closed_set),
    ("Y4", "qualified 必须满足全部判据", y4_qualified_requires_all_checks),
    ("Y5", "split 纪律：validation/test 仅描述性", y5_split_discipline),
    ("Y6", "unsupported 单元保留 reason code 与机会分母", y6_unsupported_kept_in_denominator),
    ("Y7", "逐 fold 泄漏审计零违规", y7_leakage_zero),
    ("Y8", "比较集 coverage 可比", y8_coverage_comparable),
    ("Y9", "两套闭集未混用", y9_two_closed_sets_not_mixed),
    ("Y10", "单元数 = acquisition × band × fold", y10_unit_count),
    ("Y11", "新增自由度对 alpha 的吸收已报告", y11_absorption_reported),
]

# 负例：每条不变量对应一个能触发它的伪造
SEEDS: dict[str, Callable[[Ctx], None]] = {
    "Y1": lambda c: c.units["provenance"].__setitem__("frozen_config_sha256", "0" * 64),
    "Y2": lambda c: c.verdicts["candidates"].__setitem__("C9_phantom", {"terminal_state": "qualified"}),
    "Y3": lambda c: c.verdicts["candidates"]["C1"].__setitem__("terminal_state", "looks_fine"),
    "Y4": lambda c: c.verdicts["candidates"]["C1"].__setitem__("terminal_state", "qualified"),
    "Y5": lambda c: c.verdicts["candidates"]["C1"].__setitem__("train_unit_count", 999),
    "Y6": lambda c: next(e for u in c.units["units"] for e in u["candidates"].values()
                         if e["state"] == "unsupported").__setitem__("reason", None),
    "Y7": lambda c: c.units["leakage_audit"].__setitem__("violation_count", 3),
    "Y8": lambda c: next(u["candidates"]["C1"] for u in c.units["units"]
                         if u["candidates"]["C1"]["state"] == "scored"
                         and u["candidates"]["C0"]["state"] == "scored").__setitem__("coverage", 0.5),
    "Y9": lambda c: c.verdicts["candidates"]["C1"].__setitem__("terminal_state",
                                                               "non_identifiable_equivalent"),
    "Y10": lambda c: c.units["units"].pop(),
    "Y11": lambda c: c.verdicts["candidates"]["C1"].pop("alpha_absorption"),
}


def run(ctx: Ctx) -> list[dict[str, Any]]:
    out = []
    for cid, desc, fn in CHECKS:
        ok, detail = fn(ctx)
        out.append({"id": cid, "description": desc, "passed": ok, "detail": detail})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--verdicts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    base = Ctx(load_json(args.units.resolve()), load_json(args.verdicts.resolve()),
               load_json(CONTAINER / "configs/optical-operator-config-v1.json"),
               load_json(CONTAINER / "evidence/freeze-manifest-v1.json"))

    results = run(base)
    for r in results:
        print(f"  {r['id']:>4} {'PASS' if r['passed'] else 'FAIL'}  {r['description']}")
        print(f"        {r['detail']}")
    failed = [r["id"] for r in results if not r["passed"]]

    self_test: list[dict[str, Any]] = []
    if args.self_test:
        print("\n负例自检（每条注入一个能触发它的伪造）：")
        for cid, seed in SEEDS.items():
            probe = Ctx(copy.deepcopy(base.units), copy.deepcopy(base.verdicts),
                        base.config, base.manifest)
            seed(probe)
            caught = not next(r["passed"] for r in run(probe) if r["id"] == cid)
            self_test.append({"id": cid, "violation_caught": caught})
            print(f"  {cid:>4} {'捕获' if caught else '未捕获 ← 该检查形同虚设'}")
        missed = [s["id"] for s in self_test if not s["violation_caught"]]
        if missed:
            failed.extend(missed)

    report = {
        "schema": "mountainrs-stage7.6-result-audit-v1",
        "checks": results,
        "self_test": self_test,
        "outcome": "pass" if not failed else "fail",
        "failed_ids": failed,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(f"\n结果: {report['outcome']}" + (f"  未通过 {failed}" if failed else ""))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
