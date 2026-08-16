#!/usr/bin/env python3
"""生成 Stage 7.7 passCriteria 6 要求的证据集。

发布：state-observation matrix、activation registry、dependency graph、
fixture/oracle hash、传播审计 manifest 与 fail-closed receipt。

传播审计以 Stage 7.6 引入外扩 DEM 这一真实变更为对象——它是本项目中实际
发生过的几何 artifact 变更，不是为了产出证据而编造的场景。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from geometry_propagation_v1 import (  # noqa: E402
    INVALIDATED, QUARANTINED, VALID, Artifact, ConsumerRegistry, DependencyGraph,
    Geometry, Grid, classify_change, geometry_version_digest, load_rules, propagate,
)

CONTAINER = Path(__file__).resolve().parents[1]
REPO = CONTAINER.parents[1]
FROZEN_DEM = REPO / "stages/stage6_5_real_landsat_observation_stress_test/outputs/dem_on_shadowrisk_grid.tif"
EXTENDED_DEM = REPO / "stages/stage2_dem_terrain/data/dem_roi_plus_20km_utm48n.tif"
ROI = (292230.0, 3451230.0, 311730.0, 3473790.0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_geometry(path: Path, artifact_id: str) -> Geometry:
    import rasterio
    with rasterio.open(path) as dataset:
        values = dataset.read(1).astype("float64")
        t = dataset.transform
        grid = Grid(t.c, t.f, t.a, dataset.width, dataset.height)
    return Geometry(artifact_id, values, grid)


def write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sha256_file(path)


def main() -> int:
    rules = load_rules()
    registry = ConsumerRegistry(rules)

    artifacts = [
        Artifact("dem", "geometry"),
        Artifact("slope", "geometry_consumer", ["dem"], consumer_name="slope"),
        Artifact("aspect", "geometry_consumer", ["dem"], consumer_name="aspect"),
        Artifact("cos_i", "geometry_consumer", ["dem"], consumer_name="cos_i"),
        Artifact("v_sky", "geometry_consumer", ["dem"], consumer_name="v_sky"),
        Artifact("alpha_fit", "derived", ["cos_i"]),
        Artifact("ablation_table", "derived", ["alpha_fit", "v_sky"]),
        Artifact("qa_mask", "observation"),
    ]
    graph = DependencyGraph(artifacts)

    # ---- 1. 依赖图 ----
    dep_graph = {
        "schema": "mountainrs-stage7.7-dependency-graph-v1",
        "purpose": "几何失效传播所依据的 artifact 依赖图。只登记与几何有依赖关系的对象及一个对照对象。",
        "scope_limit": "本图覆盖光学链路。SAR 斜距几何的消费者属 Stage 8.0，未登记。",
        "nodes": [{"id": a.id, "kind": a.kind, "consumer_name": a.consumer_name,
                   "depends_on": a.depends_on} for a in artifacts],
        "edges": [{"from": d, "to": a.id} for a in artifacts for d in a.depends_on],
        "influence_radii_m": {e["consumer"]: e["influence_radius_m"]
                              for e in rules["consumer_registry"]["entries"]},
        "why_radii_matter": "依赖图给出『谁依赖谁』，影响半径给出『依赖到多远』。只有前者会把"
                            "ROI 外 10 km 的地形变化对 v_sky 的影响判成无关。",
    }

    # ---- 2. 传播审计：真实变更 ----
    old = open_geometry(FROZEN_DEM, "dem@frozen")
    new = open_geometry(EXTENDED_DEM, "dem@roi_plus_20km")
    res = old.grid.resolution
    inset = (ROI[0] + res, ROI[1] + res, ROI[2] - res, ROI[3] - res)

    verdicts = []
    for consumer in ("slope", "aspect", "cos_i"):
        verdicts.append(classify_change(old, new, consumer, inset, registry))
    # v_sky 在本次变更之前不存在产出，属 scope_extension 的新增能力分支
    v_sky_verdict = classify_change(old, new, "v_sky", ROI, registry,
                                    consumer_had_prior_output=False)
    verdicts.append(v_sky_verdict)

    marks_before = {a.id: VALID for a in artifacts}
    manifest = propagate(graph, "dem", verdicts)

    audit = {
        "schema": "mountainrs-stage7.7-propagation-audit-v1",
        "purpose": "对一次真实发生的几何 artifact 变更执行失效传播，并留全量留痕。",
        "change_source": {
            "old_artifact": {"path": str(FROZEN_DEM.relative_to(REPO)),
                             "sha256": sha256_file(FROZEN_DEM)},
            "new_artifact": {"path": str(EXTENDED_DEM.relative_to(REPO)),
                             "sha256": sha256_file(EXTENDED_DEM)},
            "context": "Stage 7.6 为计算 v_sky 引入外扩 DEM。ROI 窗口内与冻结 DEM 逐位相同。",
        },
        "compute_rect_note": (
            "slope / aspect / cos_i 的 compute_rect 取 ROI 内缩一个像元（30 m）。"
            "冻结 DEM 的覆盖恰好等于 ROI 且无余量，故 ROI 最外一圈像元的影响域已伸出其外——"
            "这是既有事实，非本次引入。不内缩时该三者判 scope_extension。"),
        "per_consumer_verdict": verdicts,
        "marks_before": marks_before,
        "marks_after": manifest["marks"],
        "reason_codes": manifest["reason_codes"],
        "propagation_path": manifest["propagation_path"],
        "unaffected_artifacts": manifest["unaffected_artifacts"],
        "counts": manifest["counts"],
        "outcome": (
            "本次变更不触发任何失效。slope/aspect/cos_i 判 artifact_only——影响域内 488,800 "
            "像元逐位相同；v_sky 判 scope_extension 且此前无产出，属新增能力而非失效。"),
        "why_recording_a_no_op_matters": (
            "不传播也必须留痕。若只记录发生了传播的事件，『规则判定不传播』与『规则漏检』"
            "在事后无法区分。"),
        "geometry_version_digests": {
            c: geometry_version_digest(new, c, inset if c != "v_sky" else ROI, registry)
            for c in ("slope", "aspect", "cos_i", "v_sky")
        },
    }

    receipt = {
        "schema": "mountainrs-stage7.7-propagation-receipt-v1",
        "purpose": "fail-closed receipt：据其可回滚到传播前的标记状态。",
        "marks_before": marks_before,
        "marks_after": manifest["marks"],
        "rollback_contract": "rollback(marks_before, receipt) 在 receipt 与给定状态不符时拒绝执行。",
        "raw_observation_permanence": {
            "statement": "原始观测的证据身份与可追溯性不受本次传播影响。",
            "basis": "Stage 7.1-R 冻结 evidence_membership 在 universe version 内不可撤销；"
                     "架构 v3.3 §2.2 明确永久保留的对象是证据身份与可追溯性，不必然是本地热存储字节。",
        },
        "fail_closed_points": [
            "未登记的几何消费者 → UnregisteredConsumer，停机（不默认半径 0）",
            "cache 的 geometry version 摘要不符 → CacheVersionMismatch，停机（不静默重算）",
            "receipt 与给定状态不符 → 拒绝回滚",
        ],
    }

    # ---- 3. 状态侧：空集 ----
    state_matrix = {
        "schema": "mountainrs-stage7.7-state-observation-matrix-v1",
        "purpose": "状态与观测的对应矩阵。",
        "rows_states": [],
        "columns_observations": ["Landsat SR_B4", "Landsat SR_B5"],
        "cells": [],
        "matrix_is_empty": True,
        "why_empty": "候选状态 universe 为空集（见 evidence/candidate-state-universe-v1.json）。"
                     "矩阵无行，不是无列——观测侧存在且已冻结，缺的是状态侧。",
        "must_not_be_read_as": "空矩阵不表示状态与观测无关系，只表示当前无任何状态获准进入。",
    }
    activation_registry = {
        "schema": "mountainrs-stage7.7-activation-registry-v1",
        "purpose": "L1 状态激活登记表。",
        "entries": [],
        "counts": {"activated": 0, "inactive_non_identifiable": 0, "inactive_redundant": 0,
                   "inactive_insufficient_evidence": 0, "deferred_missing_anchor": 0},
        "activated_count": 0,
        "derivation": "由 passCriteria 1 的依赖绑定与 Stage 7.6 的零 qualified 算子唯一推出。",
        "exposure_status": "post_result_exploratory",
        "downstream_constraint": "activated_count = 0 使 Stage 7.9 无法激活，见节点约束 nc_8fe5b4709440。",
    }

    # ---- 4. fixture 与实现的字节身份 ----
    fixture_path = CONTAINER / "scripts/tests/test_geometry_propagation_v1.py"
    impl_path = CONTAINER / "scripts/geometry_propagation_v1.py"
    rules_path = CONTAINER / "configs/geometry-version-and-propagation-v1.json"
    proc = subprocess.run([sys.executable, str(fixture_path)],
                          capture_output=True, text=True, cwd=str(CONTAINER))
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""

    fixture_manifest = {
        "schema": "mountainrs-stage7.7-fixture-manifest-v1",
        "purpose": "fixture、oracle 与实现的字节身份，以及本次运行结果。",
        "rules_frozen_before_fixture": {"path": "configs/geometry-version-and-propagation-v1.json",
                                        "sha256": sha256_file(rules_path)},
        "implementation": {"path": "scripts/geometry_propagation_v1.py",
                           "sha256": sha256_file(impl_path)},
        "fixture": {"path": "scripts/tests/test_geometry_propagation_v1.py",
                    "sha256": sha256_file(fixture_path)},
        "run_result": {"exit_code": proc.returncode, "summary_line": tail},
        "cases": [c["id"] for c in rules["fixture_specification"]["cases"]]
                 + [rules["fixture_specification"]["boundary_case_not_avoided"]["id"]],
        "adjustments_to_frozen_spec": [
            {"case": "F1",
             "adjustment": "compute_rect 内缩一个像元（30 m）",
             "reason": "冻结 DEM 覆盖恰等于 ROI 且无余量，ROI 最外一圈的 cos_i 影响域已伸出其外。"
                       "这是既有事实，fixture 使其显形并单独断言（不内缩时判 scope_extension）。"},
            {"case": "F9",
             "adjustment": "采用真实接缝的统计量级（std 7.792 m）但构造扰动位置",
             "reason": "Stage 7.6 的替换前 DEM 版本未归档，无法取得纯真实的接缝前后对照。"
                       "本用例因此是半合成的，如实标注，不冒充真实素材。"},
        ],
        "each_case_kills_a_wrong_implementation": {
            c["id"]: c.get("kills_which_wrong_implementation", "—")
            for c in rules["fixture_specification"]["cases"]},
    }

    outputs = {
        "evidence/dependency-graph-v1.json": dep_graph,
        "evidence/propagation-audit-v1.json": audit,
        "evidence/propagation-receipt-v1.json": receipt,
        "evidence/state-observation-matrix-v1.json": state_matrix,
        "evidence/activation-registry-v1.json": activation_registry,
        "evidence/fixture-manifest-v1.json": fixture_manifest,
    }
    hashes = {}
    for rel, payload in outputs.items():
        hashes[rel] = write(CONTAINER / rel, payload)
        print(f"  {rel:<48} {hashes[rel][:16]}…")

    print(f"\n传播结果: {audit['counts']}")
    print(f"fixture: {tail}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
