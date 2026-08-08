#!/usr/bin/env python3
"""Stage 7.3｜几何可行性审计（合同 ①④，pre-flight 阶段亦可运行）。

只回答一个问题：按 core-topology 子协议冻结的 core 集合，在冻结 ROI 上能形成
多少个满足 8,130 m 隔离准入的 fold。

**读取范围受合同 ① 限制**：本程序只使用冻结 ROI/target grid 的坐标与子协议
第 3 节的 core 投影边界。它不打开任何影像、不读取逐景 radiance、QA/validity
支持量、alpha、residual 或分数——因此可在 planned 状态运行而不污染
activation 的结果盲要求。

隔离判据逐字取自合同 ②：holdout-core 像元中心到其本 fold 任一 calibration 像元
中心的最小欧氏距离 ≥ 8,130 m（EPSG:32648）。core 为轴对齐矩形，故点到 core 的
最小距离用解析式计算，不做近似、不做栅格膨胀。

不调用 Earth Engine，不评分，不实例化 actual calibration。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_ROOT = SCRIPT_DIR.parent

# 冻结 target grid（Stage 7.1 shadow-risk-b-b4-grid-v1）
GRID = {
    "grid_id": "shadow-risk-b-b4-grid-v1",
    "crs": "EPSG:32648",
    "bounds": [292230.0, 3451230.0, 311730.0, 3473790.0],
    "width": 650,
    "height": 752,
    "resolution": 30.0,
}
ISOLATION_M = 8130.0          # 合同②：calibration-to-own-core 最小欧氏距离
MIN_VIABLE_FOLD_COUNT = 2     # 合同④

# core-topology-subprotocol-v1.md §3，字典序即 fold 编号顺序（§4 全取，不筛选）
CORES = {
    "shadow_risk_b_combined_risk_01": [295110.0, 3467550.0, 301350.0, 3473790.0],
    "shadow_risk_b_combined_risk_02": [307890.0, 3451230.0, 311730.0, 3455070.0],
    "shadow_risk_b_combined_risk_03": [308370.0, 3470430.0, 311730.0, 3473790.0],
    "shadow_risk_b_combined_risk_04": [302790.0, 3460350.0, 307590.0, 3465150.0],
    "shadow_risk_b_combined_risk_05": [301350.0, 3466110.0, 307590.0, 3472350.0],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pixel_centres() -> tuple[np.ndarray, np.ndarray]:
    left, _, _, top = GRID["bounds"][0], None, None, GRID["bounds"][3]
    res = GRID["resolution"]
    xs = left + (np.arange(GRID["width"]) + 0.5) * res
    ys = top - (np.arange(GRID["height"]) + 0.5) * res
    return np.meshgrid(xs, ys)


def distance_to_core(x: np.ndarray, y: np.ndarray, bounds: list[float]) -> np.ndarray:
    """点到轴对齐矩形的最小欧氏距离；core 内部为 0。"""
    left, bottom, right, top = bounds
    dx = np.maximum(np.maximum(left - x, x - right), 0.0)
    dy = np.maximum(np.maximum(bottom - y, y - top), 0.0)
    return np.hypot(dx, dy)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()

    subprotocol = STAGE_ROOT / "docs/core-topology-subprotocol-v1.md"
    if "**状态：** `frozen`" not in subprotocol.read_text(encoding="utf-8"):
        raise SystemExit("stop: core-topology 子协议未处于 frozen 状态")

    x, y = pixel_centres()
    total = GRID["width"] * GRID["height"]

    core_masks: dict[str, np.ndarray] = {}
    domain_masks: dict[str, np.ndarray] = {}
    folds = []
    for index, core_id in enumerate(sorted(CORES), start=1):
        bounds = CORES[core_id]
        distance = distance_to_core(x, y, bounds)
        core = distance == 0.0
        domain = distance >= ISOLATION_M
        core_masks[core_id] = core
        domain_masks[core_id] = domain
        # 隔离准入的实测最小距离：core 像元到该 fold 几何标定域的最近距离
        min_gap = float(distance[domain].min()) if domain.any() else None
        folds.append({
            "fold_index": index,
            "core_id": core_id,
            "projected_bounds": bounds,
            "core_pixel_count": int(core.sum()),
            "geometric_calibration_domain_pixel_count": int(domain.sum()),
            "geometric_calibration_domain_share_of_roi": round(float(domain.mean()), 6),
            "min_core_to_domain_distance_m": min_gap,
            "isolation_admitted": bool(domain.any() and min_gap is not None and min_gap >= ISOLATION_M),
        })

    core_ids = sorted(CORES)
    overlaps = []
    for a, b in combinations(core_ids, 2):
        core_intersection = int((core_masks[a] & core_masks[b]).sum())
        inter = int((domain_masks[a] & domain_masks[b]).sum())
        union = int((domain_masks[a] | domain_masks[b]).sum())
        overlaps.append({
            "pair": [a, b],
            "core_overlap_pixels": core_intersection,
            "geometric_domain_intersection": inter,
            "geometric_domain_union": union,
            "geometric_domain_jaccard": round(inter / union, 6) if union else 0.0,
        })

    cores_disjoint = all(o["core_overlap_pixels"] == 0 for o in overlaps)
    admitted = [f for f in folds if f["isolation_admitted"]]
    viable = len(admitted) >= MIN_VIABLE_FOLD_COUNT

    payload = {
        "schema": "mountainrs-stage7.3-geometric-feasibility-audit-v1",
        "created_at_utc": "2026-08-08T00:00:00Z",
        "contract_clause": "Stage 7.3 ①④（pre-flight 可行性预证）",
        "authority": {
            "core_topology_subprotocol": {
                "relative_path": "docs/core-topology-subprotocol-v1.md",
                "sha256": sha256_file(subprotocol),
                "status": "frozen",
            },
            "isolation_predicate": (
                "合同②：holdout-core 像元中心到其本 fold 任一 calibration 像元中心的"
                "最小欧氏距离 ≥ 8,130 m（EPSG:32648）"
            ),
            "selection_algorithm": "core-topology-subprotocol-v1 §4：全取，按 core_id 字典序升序编号",
        },
        "target_grid": GRID,
        "isolation_distance_m": ISOLATION_M,
        "minimum_viable_fold_count": MIN_VIABLE_FOLD_COUNT,
        "folds": folds,
        "cores_pairwise_disjoint": cores_disjoint,
        "pairwise": overlaps,
        "verdict": {
            "admitted_fold_count": len(admitted),
            "viable": viable,
            "tier": (
                "preferred_at_least_three" if len(admitted) >= 3
                else "minimum_descriptive_only" if len(admitted) == 2
                else "not_viable_in_this_roi"
            ),
            "statement": (
                f"按冻结 core 集合与 §4 全取算法，{len(admitted)} 个 fold 满足 8,130 m 隔离准入。"
                if viable else
                "满足隔离准入的 fold 数低于 minimum_viable_fold_count，本 ROI 下不可行。"
            ),
        },
        "independence_caveat": {
            "statement": (
                "几何标定域两两重叠显著（见 pairwise.geometric_domain_jaccard），"
                "与 Stage 7.0 leakage_audit 的 pairwise shared calibration 10/10 一致。"
                "这些 fold 在任何意义上都不构成独立样本；fold 数不得用作 effective n，"
                "不得据以计算 p 值或置信区间。"
            ),
            "max_pairwise_jaccard": max(o["geometric_domain_jaccard"] for o in overlaps),
        },
        "sampling_bias_caveat": (
            "core 由 C5-D3 按 combined_risk_stress 准则选定，刻意位于阴影与质量风险高处，"
            "非随机采样、非均匀覆盖。fold 级结果只代表本 ROI 内已知最难区域的表现。"
        ),
        "read_scope_boundary": {
            "read_only_grid_and_core_geometry": True,
            "opened_any_raster": False,
            "read_per_acquisition_radiance": False,
            "read_qa_or_validity_support": False,
            "read_alpha_or_residual_or_score": False,
            "note": "符合合同①对 pre-flight 读取范围的限制，可在 planned 状态运行。",
        },
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": "audited",
        "admitted_folds": len(admitted),
        "tier": payload["verdict"]["tier"],
        "cores_disjoint": cores_disjoint,
        "max_pairwise_jaccard": payload["independence_caveat"]["max_pairwise_jaccard"],
    }, ensure_ascii=False))
    return 0 if viable else 1


if __name__ == "__main__":
    raise SystemExit(main())
