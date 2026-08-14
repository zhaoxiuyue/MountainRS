#!/usr/bin/env python3
"""Stage 7.5 identity registry auditor.

fail-closed：任何不变量违规即非零退出，不产出「部分通过」。

不变量取自 configs/identity-registry-schema-v1.json 的 auditor_invariants，
本脚本是它的可执行形式；两者不一致时以 schema 为准并修本脚本。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

CONTAINER = Path(__file__).resolve().parents[1]
STAGE_ROOT = CONTAINER.parent
REPO_ROOT = STAGE_ROOT.parent

SCHEMA_PATH = CONTAINER / "configs" / "identity-registry-schema-v1.json"
REGISTRY_PATH = CONTAINER / "evidence" / "identity-registry-v1.json"

IDENTITY_CLASSES = {"G", "X_t", "Z_t", "N_t", "E", "not_applicable"}
IN_GRAPH_CLASSES = IDENTITY_CLASSES - {"not_applicable"}
DISPOSITIONS = {
    "identity_qualified",
    "identity_qualified_with_fixed_gauge",
    "non_identifiable_equivalent",
    "excluded_class_or_path_violation",
    "deferred_missing_anchor",
}
QUALIFIED = {"identity_qualified", "identity_qualified_with_fixed_gauge"}
EVIDENCE_SCOPES = {"local", "profile", "global"}
# 数值实验不构成任何一种合法 kind——多起点、重复采样、profile 扫描都不在内
GLOBAL_JUSTIFICATION_KINDS = {
    "analytic_proof",
    "structural_argument",
    "domain_covering_evidence",
}
QUALITY_PHASES = {"pre_inference", "post_inference"}
# 架构 v3.3 §3 的六类质量因子名，禁止出现在 identity_class 里
QUALITY_FACTOR_NAMES = {
    "support_mask",
    "geometry_visibility",
    "reconstruction_quality",
    "sensor_quality",
    "model_adequacy",
    "output_uncertainty",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(relative_path: str) -> Path:
    """registry 里的相对路径一律相对 evidence/ 目录解析。"""
    return (REGISTRY_PATH.parent / relative_path).resolve()


def audit() -> list[str]:
    violations: list[str] = []

    def fail(inv: str, obj: str, msg: str) -> None:
        violations.append(f"[{inv}] {obj}: {msg}")

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = registry["entries"]
    deferred = registry.get("deferred_identities", [])

    # conforms_to 指向的 schema 必须与磁盘一致
    conf = registry["conforms_to"]
    actual = sha256_of(resolve(conf["relative_path"]))
    if actual != conf["sha256"]:
        fail("I8", "conforms_to", f"schema hash 漂移: 声明 {conf['sha256'][:16]}… 实际 {actual[:16]}…")

    ids = [e["object_id"] for e in entries]
    if len(ids) != len(set(ids)):
        fail("I1", "<registry>", "object_id 不唯一")

    for e in entries:
        oid = e["object_id"]
        cls = e.get("identity_class")

        # I1 类别取自闭集，且不得是质量因子名
        if cls not in IDENTITY_CLASSES:
            fail("I1", oid, f"identity_class={cls!r} 不在闭集内")
        if cls in QUALITY_FACTOR_NAMES:
            fail("I1", oid, f"identity_class 被写成了质量因子名 {cls!r}")

        # I2 E 类不占自由度、不接受梯度、不吸收残差
        if cls == "E":
            forbidden = " ".join(e.get("forbidden_paths", []))
            for token in ("可拟合量", "梯度落点"):
                if token not in forbidden:
                    fail("I2", oid, f"E 类必须在 forbidden_paths 中禁止「{token}」")

        # I3 not_applicable 不得携带 disposition / evidence_scope
        if cls == "not_applicable":
            for banned in ("disposition", "evidence_scope"):
                if banned in e:
                    fail("I3", oid, f"not_applicable 对象不得携带 {banned}")
            if "not_applicable_reason" not in e:
                fail("I3", oid, "not_applicable 对象必须给出 not_applicable_reason")
            qp = e.get("quality_phase")
            if qp is not None and qp not in QUALITY_PHASES:
                fail("I3", oid, f"quality_phase={qp!r} 不在闭集内")
            if e.get("architecture_factor") and qp is None:
                fail("I3", oid, "标注了 architecture_factor 的质量因子必须给出 quality_phase")
            continue  # 以下不变量只针对 in-graph 对象

        # in-graph 对象必须有 disposition
        disp = e.get("disposition")
        if disp not in DISPOSITIONS:
            fail("I1", oid, f"disposition={disp!r} 不在闭集内")

        # I4 qualified 必须带 evidence_scope
        if disp in QUALIFIED:
            scope = e.get("evidence_scope")
            if scope not in EVIDENCE_SCOPES:
                fail("I4", oid, f"qualified 对象缺少合法 evidence_scope（得到 {scope!r}）")
            # I5 global 必须声明结构化的证明种类
            #
            # 早期版本用关键词匹配散文 justification，同时产生误报与漏报：
            # 「不是多起点数值实验」会被判成数值实验；而只要写上「解析」二字
            # 却不给出任何证明即可通过。判据改为结构化枚举，散文只供人读。
            if scope == "global":
                kind = e.get("global_justification_kind")
                if kind not in GLOBAL_JUSTIFICATION_KINDS:
                    fail("I5", oid,
                         f"evidence_scope=global 必须声明 global_justification_kind"
                         f"（合法值 {sorted(GLOBAL_JUSTIFICATION_KINDS)}，得到 {kind!r}）")
                if not e.get("evidence_scope_justification"):
                    fail("I5", oid, "evidence_scope=global 必须同时给出人读的 justification")

        # I6 non_identifiable_equivalent 必须成对且反向可追溯
        if disp == "non_identifiable_equivalent":
            partner = e.get("equivalence_partner")
            if not partner:
                fail("I6", oid, "缺少 equivalence_partner")
            elif partner not in ids:
                fail("I6", oid, f"equivalence_partner={partner!r} 不在 registry 中")
            else:
                back = next(x for x in entries if x["object_id"] == partner)
                linked = (
                    back.get("equivalence_partner") == oid
                    or (back.get("equivalence_watch") or {}).get("object_id") == oid
                )
                if not linked:
                    fail("I6", oid, f"partner {partner!r} 未反向引用本对象")

        # I7 gauge.fixed 蕴含 with_fixed_gauge
        gauge = e.get("gauge") or {}
        if gauge.get("fixed") is True and disp != "identity_qualified_with_fixed_gauge":
            fail("I7", oid, f"gauge.fixed=true 但 disposition={disp!r}")
        if gauge.get("fixed") is True and not gauge.get("rule"):
            fail("I7", oid, "gauge.fixed=true 必须给出 rule")

        # I8 source_binding hash 与磁盘一致
        sb = e.get("source_binding")
        if not sb:
            fail("I8", oid, "缺少 source_binding")
        else:
            p = resolve(sb["relative_path"])
            if not p.exists():
                fail("I8", oid, f"source_binding 指向的文件不存在: {sb['relative_path']}")
            else:
                got = sha256_of(p)
                if got != sb["sha256"]:
                    fail("I8", oid, f"hash 漂移: 声明 {sb['sha256'][:16]}… 实际 {got[:16]}…")

    # deferred 段：只允许 deferred_missing_anchor，且必须有 distinctness 断言
    for d in deferred:
        oid = d["object_id"]
        if d.get("disposition") != "deferred_missing_anchor":
            fail("D1", oid, f"deferred 段的 disposition 只能是 deferred_missing_anchor，得到 {d.get('disposition')!r}")
        if "identity_class" in d:
            fail("D2", oid, "deferred 段对象不得携带 identity_class——类别归属正是被推迟的东西")
        if not d.get("distinctness_assertions"):
            fail("D3", oid, "deferred 段对象必须给出 distinctness_assertions")
        sb = d.get("source_binding")
        if sb:
            p = resolve(sb["relative_path"])
            if p.exists() and sha256_of(p) != sb["sha256"]:
                fail("I8", oid, "source_binding hash 漂移")

    return violations


def main() -> int:
    violations = audit()
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    n_entries = len(registry["entries"])
    n_deferred = len(registry.get("deferred_identities", []))
    n_graph = sum(1 for e in registry["entries"] if e["identity_class"] != "not_applicable")
    n_na = n_entries - n_graph

    print(f"registry: {n_entries} entries ({n_graph} in-graph / {n_na} not_applicable)"
          f" + {n_deferred} deferred")

    if violations:
        print(f"\nFAIL — {len(violations)} 项违规:")
        for v in violations:
            print(f"  {v}")
        return 1

    print("PASS — 全部不变量通过 (I1-I8, D1-D3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
