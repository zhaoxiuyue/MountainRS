#!/usr/bin/env python3
"""Stage 7.8 对账与终态判定（passCriteria 6、8）。

对账检查各证据件之间的一致性；任一不闭合即停机，不产出终态。
终态判据取自合同 passCriteria 6，本程序只执行不解释。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

CONTAINER = Path(__file__).resolve().parents[1]


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
    manifest = load("evidence/dataset-domain-split-manifest-v1.json")
    registry = load("evidence/reference-registry-v1.json")
    gate = load("evidence/requalification-gate-result-v1.json")
    split = load("configs/domain-split-and-leakage-v1.json")
    freeze = load("evidence/freeze-manifest-v1.json")
    stage2 = load("outputs/domain-screening-stage2-v1.json")

    checks: list[dict] = []

    def check(cid: str, desc: str, ok: bool, detail: str) -> None:
        checks.append({"id": cid, "description": desc, "passed": bool(ok), "detail": detail})

    sel_ids = [d["candidate_id"] for d in selection["selected"]]
    man_ids = [d["domain_id"] for d in manifest["domains"]]
    check("R1", "选择结果与 manifest 的 domain 集合一致",
          sel_ids == man_ids, f"{sel_ids} vs {man_ids}")

    roles = {}
    for role in ("train", "calibration", "evaluation"):
        for did in split["split"][role]["domains"]:
            roles.setdefault(did, []).append(role)
    multi = {k: v for k, v in roles.items() if len(v) > 1}
    covered = set(man_ids) <= set(roles)
    check("R2", "每个 domain 恰好归属一个 split 角色且无遗漏",
          not multi and covered, f"多重归属 {multi or '无'}；未归属 {set(man_ids) - set(roles) or '无'}")

    s2_by_id = {c["candidate_id"]: c for c in stage2["candidates"]}
    mismatch = []
    for domain in manifest["domains"]:
        did = domain["domain_id"]
        o = domain["observation_opportunity"]
        if o["scored"] + o["unscored_missing_source"] != o["total_dates_in_window"]:
            mismatch.append((did, "机会分母不闭合"))
        if o["qualified"] + o["actively_rejected"] != o["scored"]:
            mismatch.append((did, "合格+拒绝 ≠ 可评分"))
        if o["qualified"] != s2_by_id[did]["checks"]["A2_qualified_acquisitions"]["qualified"]:
            mismatch.append((did, "合格数与第二阶段不符"))
    check("R3", "逐域观测机会账目闭合且与筛选阶段一致",
          not mismatch, f"不符项 {mismatch or '无'}")

    ref_entry = next(e for e in registry["entries"]
                     if e["source_id"] == "COPERNICUS/S2_SR_HARMONIZED")
    match_by_id = {m["candidate_id"]: m for m in ref_entry["temporal_matching"]["per_domain"]}
    ref_mismatch = [d["domain_id"] for d in manifest["domains"]
                    if d["reference_matching"]["tight_matched"]
                    != match_by_id[d["domain_id"]]["tight_matched"]]
    check("R4", "manifest 的参考匹配数与 Reference Registry 一致",
          not ref_mismatch, f"不符 {ref_mismatch or '无'}")

    gate_ids = [r["domain_id"] for r in gate["G1_variation_range"]["per_domain"]]
    check("R5", "Gate 覆盖全部选定 domain",
          sorted(gate_ids) == sorted(man_ids), f"{len(gate_ids)}/{len(man_ids)}")

    drift = []
    for key, rec in freeze["artifacts"].items():
        path = (CONTAINER / "evidence" / rec["relative_path"]).resolve()
        if not path.exists():
            drift.append((key, "缺失"))
        elif sha256_file(path) != rec["sha256"]:
            drift.append((key, "hash 漂移"))
    check("R6", "冻结清单登记的产物字节未漂移", not drift, f"{drift or '无'}")

    classes = {e["source_id"]: e["class"] for e in registry["entries"]}
    valid_classes = {"ground_truth", "reference_observation", "proxy", "unavailable"}
    check("R7", "参考分类取自协议闭集",
          set(classes.values()) <= valid_classes, f"{classes}")

    qualifying_refs = [sid for sid, cls in classes.items()
                       if cls in ("ground_truth", "reference_observation")]
    audited = []
    for e in registry["entries"]:
        if e["class"] not in ("ground_truth", "reference_observation"):
            continue
        ok = (all(v["passed"] for v in e["independence_verdict"].values()
                  if isinstance(v, dict) and "passed" in v)
              and all(v["passed"] for v in e["leakage_verdict"].values()))
        if ok:
            audited.append(e["source_id"])
    check("R8", "至少一个参考通过全部独立性与泄漏审计",
          bool(audited), f"通过审计 {audited or '无'}")

    check("R9", "无 ground_truth 时不得出现真值措辞",
          "ground_truth" not in classes.values(),
          "本节点无 ground_truth 类，报告与结论一律不得使用真值/GT 措辞")

    check("R10", "Gate 结论未解除 nc_8fe5b4709440",
          any("nc_8fe5b4709440" in s for s in gate["does_not_affect"]),
          "Stage 7.9 的阻断独立于本 Gate 结论")

    failed = [c["id"] for c in checks if not c["passed"]]
    for c in checks:
        print(f"  {c['id']:>4} {'PASS' if c['passed'] else 'FAIL'}  {c['description']}")
        print(f"        {c['detail']}")
    if failed:
        print(f"\n对账未通过 {failed}，不产出终态")
        Path(CONTAINER / "evidence/reconciliation-report-v1.json").write_text(
            json.dumps({"schema": "mountainrs-stage7.8-reconciliation-report-v1",
                        "checks": checks, "outcome": "fail", "failed": failed},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1

    domain_count = len(man_ids)
    terminal = ("qualified_multidomain_evidence_frozen"
                if 3 <= domain_count <= 5 and audited
                else "deferred_insufficient_domains_or_references")

    report = {
        "schema": "mountainrs-stage7.8-reconciliation-report-v1",
        "checks": checks,
        "outcome": "pass",
        "terminal_state": terminal,
        "terminal_basis": {
            "domain_count": domain_count,
            "domain_count_requirement": "3–5（passCriteria 6）",
            "qualifying_reference": audited,
            "reference_requirement": "至少一个 ground_truth 或 reference_observation 通过全部独立性与泄漏审计",
            "note": "proxy 数量再多也不能使终态从 deferred 变为 qualified（协议 verdict_impact）。",
        },
        "what_qualified_means": [
            "qualified 只表示证据可用于评估（合同 boundaries），不表示模型跨域成功。",
            "本节点不训练、不运行、不比较任何候选模型。",
            "本节点无 ground_truth 类参考，任何结论不得使用真值措辞。",
        ],
        "requalification_gate": {
            "verdict": gate["verdict"],
            "consequence": gate["consequence"],
            "independent_of_terminal_state": "Gate 判 not_warranted 不影响本节点终态——"
                                             "证据是否合格与既有负结果是否值得重开，是两个独立问题。",
        },
        "downstream_blocks_not_released": [
            "nc_8fe5b4709440：Stage 7.9 因 activated_count = 0 被独立阻断。"
            "合同 passCriteria 7 的『deferred 不阻断 7.9』只声明本节点的 deferred 不构成阻断，"
            "无权声明 7.9 没有其他阻断源；且本节点终态为 qualified 而非 deferred，该句更不适用。",
            "Stage 7.10 Track B 须保持 deferred（passCriteria 7）。",
        ],
    }
    (CONTAINER / "evidence/reconciliation-report-v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n对账 {len(checks)}/{len(checks)} 通过")
    print(f"终态：{terminal}")
    print(f"  domain {domain_count} 个（要求 3–5）；通过审计的独立参考：{audited}")
    print(f"重新资格化 Gate：{gate['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
