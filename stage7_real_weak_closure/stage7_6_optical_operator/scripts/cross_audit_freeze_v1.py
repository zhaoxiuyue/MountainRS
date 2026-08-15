#!/usr/bin/env python3
"""Stage 7.6 冻结前交叉审计。

检查三份自产冻结件之间、以及它们与上游、与合同之间是否一致。
fail-closed：任何不一致即非零退出，不产出「部分通过」。

存在的理由：Stage 7.4 的 runtime freeze 事故就出在这一层——protocol 与
config 各自单独看都对，合起来错误码字符串对不齐，而两份文件是同一次
apply_patch 写的、同一个作者写的、自审也说 pass。跨文件一致性不能靠肉眼。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CONTAINER = Path(__file__).resolve().parents[1]
GATE = CONTAINER / "configs" / "svf-geometry-gate-v1.json"
CONFIG = CONTAINER / "configs" / "optical-operator-config-v1.json"
REGISTRY = CONTAINER / "evidence" / "operator-identity-registry-v1.json"
DECL = CONTAINER / "evidence" / "result-blind-declaration-v1.json"

PLACEHOLDER = re.compile(r"PENDING[_A-Z]*|PLACEHOLDER[_A-Z]*")


def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def walk_strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def audit(freeze_mode: bool) -> list[str]:
    V: list[str] = []

    def fail(cid: str, msg: str) -> None:
        V.append(f"[{cid}] {msg}")

    gate = json.loads(GATE.read_text(encoding="utf-8"))
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    decl = json.loads(DECL.read_text(encoding="utf-8"))

    # X1 registry 声明的参数必须在 config 的候选里被用到，反之亦然
    reg_params = {e["object_id"] for e in reg["entries"]}
    cfg_params = set()
    for c in cfg["candidates"]:
        cfg_params.update(c.get("new_parameters", []))
    cfg_params.update(cfg["unified_candidate_framework"]["free_parameters"])
    # v_sky 是条件量，出现在 terrain_modulation_factor
    for c in cfg["candidates"]:
        if c.get("terrain_modulation_factor"):
            cfg_params.add(c["terrain_modulation_factor"])
    only_reg = reg_params - cfg_params
    only_cfg = cfg_params - reg_params
    if only_reg:
        fail("X1", f"registry 登记但 config 未使用的对象: {sorted(only_reg)}")
    if only_cfg:
        fail("X1", f"config 使用但 registry 未登记的对象: {sorted(only_cfg)}")

    # X2 终态闭集必须三处一致（config 的 terminal_states、候选的 terminal_state、gate 的 outcomes）
    closed = set(cfg["terminal_states"]["closed_set"])
    for c in cfg["candidates"]:
        ts = c.get("terminal_state")
        if ts and ts not in closed:
            fail("X2", f"候选 {c['id']} 的 terminal_state={ts!r} 不在 config 闭集内")
    for key in ("gate_outcomes.fail", "post_experiment_sensitivity"):
        node = gate
        for part in key.split("."):
            node = node[part]
        ts = node.get("terminal_state")
        if ts and ts not in closed:
            fail("X2", f"gate.{key} 的 terminal_state={ts!r} 不在 config 闭集内")
    for g in cfg["support_gate"]["additional_for_two_parameter_models"].get("on_fail", {}).values():
        pass
    ofs = cfg["support_gate"]["additional_for_two_parameter_models"]["on_fail"]["terminal_state"]
    if ofs not in closed:
        fail("X2", f"support_gate.on_fail 的 terminal_state={ofs!r} 不在闭集内")

    # X3 registry 的 disposition 用的是 7.5 的闭集，与 config 的候选终态闭集是两套，不得混用
    s75 = {"identity_qualified", "identity_qualified_with_fixed_gauge",
           "non_identifiable_equivalent", "excluded_class_or_path_violation",
           "deferred_missing_anchor"}
    for e in reg["entries"]:
        d = e.get("disposition")
        if d and d not in s75:
            fail("X3", f"registry 对象 {e['object_id']} 的 disposition={d!r} 不在 Stage 7.5 闭集内")
        if d in closed - s75:
            fail("X3", f"registry 对象 {e['object_id']} 误用了候选终态闭集的值 {d!r}")

    # X4 equivalence_partner 必须在同一 registry 内且互相可达
    ids = {e["object_id"] for e in reg["entries"]}
    for e in reg["entries"]:
        if e.get("disposition") == "non_identifiable_equivalent":
            p = e.get("equivalence_partner")
            if p not in ids:
                fail("X4", f"{e['object_id']} 的 equivalence_partner={p!r} 不在本 registry")
    # config 里 C3 的 partner 必须与 registry 一致
    c3 = next((c for c in cfg["candidates"] if c["id"] == "C3"), None)
    l_path = next((e for e in reg["entries"] if e["object_id"] == "l_path"), None)
    if c3 and l_path:
        if c3.get("equivalence_partner") != l_path.get("equivalence_partner"):
            fail("X4", f"C3 的 partner({c3.get('equivalence_partner')!r}) 与 registry 中 l_path 的 partner"
                       f"({l_path.get('equivalence_partner')!r}) 不一致")
        # 候选终态与身份判定来自两套不同闭集，取值不同、语义对应，按映射核对
        mapping = cfg["terminal_states"].get("cross_set_mapping", {})
        expect = mapping.get(c3.get("terminal_state"))
        if expect is None:
            fail("X4", f"候选终态 {c3.get('terminal_state')!r} 在 cross_set_mapping 中无对应身份判定")
        elif expect != l_path.get("disposition"):
            fail("X4", f"C3 终态 {c3.get('terminal_state')!r} 应对应身份判定 {expect!r}，"
                       f"但 registry 中 l_path 为 {l_path.get('disposition')!r}")

    # X5 C2a 不得声明 new_parameters（它是 C_full 的约束子模型）
    c2a = next((c for c in cfg["candidates"] if c["id"] == "C2a"), None)
    if c2a and c2a.get("new_parameters"):
        fail("X5", "C2a 声明了 new_parameters，但它是 C_full 的一维约束，不引入独立参数")

    # X6 消融顺序只能含 run=true 的候选，且必须覆盖全部 run=true
    runnable = {c["id"] for c in cfg["candidates"] if c.get("run")}
    order = set(cfg["ablation_order"]["frozen_sequence"])
    if order != runnable:
        fail("X6", f"消融顺序 {sorted(order)} 与 run=true 的候选 {sorted(runnable)} 不一致")

    # X7 gate 选定参数与曲率规则的一致性
    sel_d = gate["frozen_parameters_pending_gate"]["search_distance_D_m"]["selected"]
    curv = gate["frozen_parameters_pending_gate"]["earth_curvature"]["selected"]
    thr = gate["curvature_rule"]["threshold_m"]
    if sel_d is not None:
        if sel_d > thr and curv is not True:
            fail("X7", f"D={sel_d} > {thr} 但曲率未纳入（selected={curv!r}）")
        buf = gate["frozen_parameters_pending_gate"]["dem_buffer_m"]["selected"]
        if buf is None or buf < sel_d:
            fail("X7", f"dem_buffer_m({buf!r}) 必须 ≥ 选定的 D({sel_d})")
    elif freeze_mode:
        fail("X7", "冻结模式下 search_distance_D_m.selected 仍为 null")

    # X8 偏差方向必须成对且相反
    bd = gate["bias_directions"]
    a = bd["search_truncation"]["effect_on_v_sky"]
    b = bd["curvature_omitted"]["effect_on_v_sky"]
    if not (("高估" in a and "低估" in b) or ("低估" in a and "高估" in b)):
        fail("X8", f"两类偏差对 v_sky 的方向未构成相反关系：{a!r} vs {b!r}")

    # X9 结果盲声明的两层必须都在，且相对既有结果必须为 NOT_BLIND
    tb = decl["two_kinds_of_blindness"]
    if tb["relative_to_existing_results"]["status"] != "NOT_BLIND":
        fail("X9", "相对既有结果的状态必须为 NOT_BLIND（7.3/7.4 residual 已公开）")
    if cfg["exposure_status"]["relative_to_existing_results"] != "post_result_exploratory":
        fail("X9", "config 的 exposure_status 与结果盲声明不一致")

    # X10 冻结模式下不得残留占位符
    if freeze_mode:
        for name, doc in (("gate", gate), ("config", cfg), ("registry", reg), ("declaration", decl)):
            for path, s in walk_strings(doc):
                if PLACEHOLDER.search(s):
                    fail("X10", f"{name}{path} 仍含占位符: {s[:40]!r}")

    # X11 上游绑定 hash 必须与磁盘一致（结果盲声明里的 13 项）
    base = DECL.parent
    for b in decl["upstream_bindings"]:
        p = (base / b["relative_path"]).resolve()
        if not p.exists():
            fail("X11", f"上游绑定不存在: {b['relative_path']}")
        elif sha256_of(p) != b["sha256"]:
            fail("X11", f"上游 hash 漂移: {p.name}")

    return V


def main() -> int:
    freeze = "--freeze" in sys.argv
    V = audit(freeze)
    mode = "冻结模式" if freeze else "预检模式"
    print(f"Stage 7.6 交叉审计（{mode}）")
    if V:
        print(f"\nFAIL — {len(V)} 项不一致:")
        for v in V:
            print(f"  {v}")
        return 1
    print("PASS — X1–X11 全部通过" + ("" if freeze else "（占位符与 Gate 选参检查在 --freeze 下才启用）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
