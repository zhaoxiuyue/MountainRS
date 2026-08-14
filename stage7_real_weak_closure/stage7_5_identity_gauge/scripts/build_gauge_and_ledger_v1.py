#!/usr/bin/env python3
"""从 identity registry 派生 gauge/等价矩阵与 disposition ledger，并运行工具箱 fixture。

三份产物全部由本脚本从冻结输入重新计算，不手写：
  evidence/gauge-equivalence-matrix-v1.json
  evidence/disposition-ledger-v1.json
  outputs/toolbox-fixture-results-v1.json

fail-closed：registry auditor 未通过时拒绝产出。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

CONTAINER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTAINER / "scripts"))
sys.path.insert(0, str(CONTAINER / "scripts" / "tests"))

from identifiability_toolbox_v1 import run_all  # noqa: E402
from test_identifiability_toolbox_v1 import (  # noqa: E402
    f1_single_param, f2_multiplicative_collinear, f3_additive_separable,
    f4_scaled_affine, f5_condition_quantity_excluded, f6_practically_unidentifiable,
)

REGISTRY = CONTAINER / "evidence" / "identity-registry-v1.json"
AUDITOR = CONTAINER / "scripts" / "audit_identity_registry_v1.py"


def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def require_registry_audit_pass() -> None:
    r = subprocess.run([sys.executable, str(AUDITOR)], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        raise SystemExit("stop: registry auditor 未通过，拒绝产出派生件")


def build_gauge_matrix(reg: dict) -> dict:
    rows, equivalences = [], []
    for e in reg["entries"]:
        if e["identity_class"] == "not_applicable":
            continue
        g = e.get("gauge") or {}
        rows.append({
            "object_id": e["object_id"],
            "identity_class": e["identity_class"],
            "granularity": e.get("granularity"),
            "gauge_fixed": bool(g.get("fixed")),
            "gauge_rule": g.get("rule"),
            "anchor": e.get("anchor"),
            "disposition": e.get("disposition"),
            "evidence_scope": e.get("evidence_scope"),
            "global_justification_kind": e.get("global_justification_kind"),
            "value_is_gauge_relative": bool(g.get("fixed")),
        })
        if e.get("disposition") == "non_identifiable_equivalent":
            equivalences.append({
                "pair": sorted([e["object_id"], e["equivalence_partner"]]),
                "form": e.get("equivalence_form"),
                "proof": e.get("equivalence_proof"),
                "unblocking_conditions": e.get("unblocking_conditions", []),
                "instantiation_status": e.get("instantiation_status", "instantiated"),
            })
        w = e.get("equivalence_watch")
        if w:
            equivalences.append({
                "pair": sorted([e["object_id"], w["object_id"]]),
                "form": "conditional",
                "condition": w["condition"],
                "note": w.get("note"),
                "instantiation_status": "watch_only",
            })

    fixed = [r["object_id"] for r in rows if r["gauge_fixed"]]
    return {
        "schema": "mountainrs-stage7.5-gauge-equivalence-matrix-v1",
        "derived_from": {"relative_path": "identity-registry-v1.json",
                         "sha256": sha256_of(REGISTRY)},
        "rows": rows,
        "equivalence_relations": equivalences,
        "gauge_fixed_objects": fixed,
        "reading_rule": "gauge_fixed=true 的对象，其数值是 gauge-relative 的合成量，"
                        "不得作为该物理量的独立测量结果报告。",
    }


def build_disposition_ledger(reg: dict) -> dict:
    counts: dict[str, int] = {}
    by_disp: dict[str, list[str]] = {}
    for e in reg["entries"]:
        d = e.get("disposition") or "not_applicable(no_disposition)"
        counts[d] = counts.get(d, 0) + 1
        by_disp.setdefault(d, []).append(e["object_id"])
    for d in reg.get("deferred_identities", []):
        k = f"{d['disposition']}(deferred_section)"
        counts[k] = counts.get(k, 0) + 1
        by_disp.setdefault(k, []).append(d["object_id"])

    gate = ["identity_qualified", "identity_qualified_with_fixed_gauge"]
    admitted = [o for d in gate for o in by_disp.get(d, [])]
    blocked = [o for d, objs in by_disp.items()
               for o in objs if d not in gate and not d.startswith("not_applicable")]

    return {
        "schema": "mountainrs-stage7.5-disposition-ledger-v1",
        "derived_from": {"relative_path": "identity-registry-v1.json",
                         "sha256": sha256_of(REGISTRY)},
        "counts": counts,
        "by_disposition": by_disp,
        "admitted_to_stage_7_6": admitted,
        "blocked_from_stage_7_6": blocked,
        "unresolved_conflicts": 0,
        "section_7f_open_items": reg["section_7f_closure_statement"]["not_closed_in_this_node"],
        "open_items_notice": "上列 §7-F 项目在本节点未关闭，不得因本节点完成而视作已解决。",
    }


def build_fixture_results() -> dict:
    fixtures = [
        (f1_single_param(), np.array([0.4]), None),
        (f2_multiplicative_collinear(), np.array([0.8, 0.5]),
         [np.array([0.8, 0.5]), np.array([0.3, 1.2]), np.array([1.5, 0.2])]),
        (f3_additive_separable(), np.array([0.4, 0.05]), None),
        (f4_scaled_affine(), np.array([0.9, 0.4, 0.05]), None),
        (f5_condition_quantity_excluded(), np.array([0.4]), None),
        (f6_practically_unidentifiable(), np.array([0.4, 0.05]), None),
    ]
    out = []
    for model, theta, ms in fixtures:
        checks = []
        for res in run_all(model, theta, ms):
            checks.append({"check": res.check, "status": res.status,
                           "reason": res.reason, "evidence_scope": res.evidence_scope,
                           "values": res.values})
        out.append({"fixture": model.name, "params": model.params,
                    "conditions": model.conditions, "theta": [float(t) for t in theta],
                    "checks": checks})

    na = sum(1 for f in out for c in f["checks"] if c["status"] == "not_applicable")
    total = sum(len(f["checks"]) for f in out)
    return {
        "schema": "mountainrs-stage7.5-toolbox-fixture-results-v1",
        "fixtures": out,
        "summary": {
            "fixture_count": len(out),
            "check_invocations": total,
            "not_applicable_count": na,
            "not_applicable_note": "not_applicable 是合法终态，代表该检查对该对象在数学上"
                                   "不适用；它不是失败，也不应通过制造无意义的测试来消除。",
        },
        "toolbox_limitation": {
            "statement": "全部检查均为数值方法，无法区分『结构不可辨识』与『数据在关键"
                         "维度变化不足』。F2 与 F6 的数值秩与秩亏完全相同，而二者的正确"
                         "处置相反：前者须改模型或固定 gauge，后者补数据即可。",
            "consequence": "凡由本工具箱得出的秩亏结论，其 evidence_scope 上限为 local 或"
                           "profile；判定为结构不可辨识必须另有符号分析或解析证明。",
            "demonstrated_by": ["F2_multiplicative_collinear", "F6_practically_unidentifiable"],
        },
    }


def main() -> int:
    require_registry_audit_pass()
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))

    targets = [
        (CONTAINER / "evidence" / "gauge-equivalence-matrix-v1.json", build_gauge_matrix(reg)),
        (CONTAINER / "evidence" / "disposition-ledger-v1.json", build_disposition_ledger(reg)),
        (CONTAINER / "outputs" / "toolbox-fixture-results-v1.json", build_fixture_results()),
    ]
    for path, payload in targets:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"  写出 {path.relative_to(CONTAINER)}  sha256={sha256_of(path)[:16]}…")

    ledger = targets[1][1]
    print("\ndisposition 分布:")
    for k, v in sorted(ledger["counts"].items(), key=lambda kv: -kv[1]):
        print(f"  {v:>3}  {k}")
    print(f"\n可进入 Stage 7.6: {ledger['admitted_to_stage_7_6']}")
    print(f"被挡在 7.6 之外: {ledger['blocked_from_stage_7_6']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
