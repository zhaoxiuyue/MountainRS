#!/usr/bin/env python3
"""Stage 7.3 ⑤前半：冻结 topology manifest（纯几何层）。

合同⑤把拓扑与逐景标定支持强制分层：topology 层只允许记录由 ROI/grid/core/
8,130 m 距离关系得到的量，**不得在 topology 选择或冻结时读取逐景
calibration_lit、QA/validity 或 alpha**。

本程序据此设计为物理上不可能违反该约束：它只对栅格坐标做解析几何运算，
全程只以写模式打开 GeoTIFF（输出 mask），**从不以读模式打开任何影像**。
逐景数据要等 topology 冻结之后，才由 fit_fold_alpha_and_score_v1.py 求交生成。

每个 fold 的三个区在几何上互斥且穷尽整个 ROI：

    core   : 到本 core 距离 = 0
    buffer : 0 < 距离 < 8,130 m        （隔离带，既不评分也不标定）
    domain : 距离 >= 8,130 m           （几何可标定域，合同②的隔离准入）

不调用 Earth Engine，不读影像，不评分，不生成 actual calibration。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.transform import Affine

SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_ROOT = SCRIPT_DIR.parent

GRID = {
    "grid_id": "shadow-risk-b-b4-grid-v1",
    "crs": "EPSG:32648",
    "bounds": [292230.0, 3451230.0, 311730.0, 3473790.0],
    "width": 650,
    "height": 752,
    "resolution": 30.0,
    "transform": [30.0, 0.0, 292230.0, 0.0, -30.0, 3473790.0],
}
ISOLATION_M = 8130.0

# core-topology-subprotocol-v1.md §3；§4 规定全取并按 core_id 字典序升序编号
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


def distance_to_rect(x: np.ndarray, y: np.ndarray, bounds: list[float]) -> np.ndarray:
    left, bottom, right, top = bounds
    dx = np.maximum(np.maximum(left - x, x - right), 0.0)
    dy = np.maximum(np.maximum(bottom - y, y - top), 0.0)
    return np.hypot(dx, dy)


def rect_to_rect_distance(a: list[float], b: list[float]) -> float:
    """两个轴对齐矩形之间的最小距离；相交或接触为 0。"""
    dx = max(max(a[0] - b[2], b[0] - a[2]), 0.0)
    dy = max(max(a[1] - b[3], b[1] - a[3]), 0.0)
    return float(np.hypot(dx, dy))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mask-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.mask_dir = args.mask_dir.resolve()
    args.output = args.output.resolve()

    subprotocol = STAGE_ROOT / "docs/core-topology-subprotocol-v1.md"
    if "**状态：** `frozen`" not in subprotocol.read_text(encoding="utf-8"):
        raise SystemExit("stop: core-topology 子协议未处于 frozen 状态")
    feasibility_path = STAGE_ROOT / "evidence/geometric-feasibility-audit-v1.json"
    feasibility = json.loads(feasibility_path.read_text(encoding="utf-8"))
    if not feasibility["verdict"]["viable"]:
        raise SystemExit("stop: 几何可行性审计判定本 ROI 下不可行")

    left, _, _, top = GRID["bounds"][0], None, None, GRID["bounds"][3]
    res = GRID["resolution"]
    xs = left + (np.arange(GRID["width"]) + 0.5) * res
    ys = top - (np.arange(GRID["height"]) + 0.5) * res
    x, y = np.meshgrid(xs, ys)
    total = GRID["width"] * GRID["height"]

    args.mask_dir.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "count": 1,
        "width": GRID["width"],
        "height": GRID["height"],
        "crs": GRID["crs"],
        "transform": Affine(*GRID["transform"]),
        "nodata": None,
        "compress": "deflate",
    }

    core_ids = sorted(CORES)
    folds = []
    for index, core_id in enumerate(core_ids, start=1):
        bounds = CORES[core_id]
        distance = distance_to_rect(x, y, bounds)
        core = distance == 0.0
        buffer_ring = (distance > 0.0) & (distance < ISOLATION_M)
        domain = distance >= ISOLATION_M

        partition_ok = bool(
            int(core.sum()) + int(buffer_ring.sum()) + int(domain.sum()) == total
            and not (core & buffer_ring).any()
            and not (core & domain).any()
            and not (buffer_ring & domain).any()
        )
        if not partition_ok:
            raise SystemExit(f"stop: fold {index} 的 core/buffer/domain 未构成互斥穷尽划分")

        mask_path = args.mask_dir / f"geometric_calibration_domain_{index:02d}.tif"
        with rasterio.open(mask_path, "w", **profile) as dataset:
            dataset.write(domain.astype("uint8"), 1)
            dataset.set_band_description(1, f"geometric_calibration_domain_{core_id}")

        nearest_other = min(
            (rect_to_rect_distance(bounds, CORES[other]) for other in core_ids if other != core_id)
        )
        folds.append({
            "fold_index": index,
            "geometric_calibration_domain_id": f"geometric_calibration_domain_{index:02d}",
            "core_id": core_id,
            "core_projected_bounds": bounds,
            "core_pixel_count": int(core.sum()),
            "buffer_pixel_count": int(buffer_ring.sum()),
            "geometric_calibration_domain": {
                "relative_path": str(mask_path.relative_to(STAGE_ROOT)),
                "sha256": sha256_file(mask_path),
                "pixel_count": int(domain.sum()),
                "share_of_roi": round(float(domain.mean()), 6),
            },
            "min_distance_core_to_own_domain_m": float(distance[domain].min()),
            "isolation_admitted": bool(float(distance[domain].min()) >= ISOLATION_M),
            "nearest_other_core_distance_m": nearest_other,
            "partition_exhaustive_and_exclusive": partition_ok,
        })

    pairwise = []
    for a, b in combinations(core_ids, 2):
        pairwise.append({
            "pair": [a, b],
            "core_to_core_distance_m": rect_to_rect_distance(CORES[a], CORES[b]),
            "cores_overlap": rect_to_rect_distance(CORES[a], CORES[b]) == 0.0
            and not (CORES[a][2] <= CORES[b][0] or CORES[b][2] <= CORES[a][0]
                     or CORES[a][3] <= CORES[b][1] or CORES[b][3] <= CORES[a][1]),
        })

    payload = {
        "schema": "mountainrs-stage7.3-topology-manifest-v1",
        "status": "frozen",
        "created_at_utc": "2026-08-08T00:00:00Z",
        "contract_clause": "Stage 7.3 ⑤（前半：拓扑层，冻结于查看任何 residual / alpha / 分数之前）",
        "authority": {
            "core_topology_subprotocol": {
                "relative_path": "docs/core-topology-subprotocol-v1.md",
                "sha256": sha256_file(subprotocol),
            },
            "geometric_feasibility_audit": {
                "relative_path": "evidence/geometric-feasibility-audit-v1.json",
                "sha256": sha256_file(feasibility_path),
                "admitted_fold_count": feasibility["verdict"]["admitted_fold_count"],
            },
            "selection_algorithm": "全取，按 core_id 字典序升序编号（子协议 §4）",
        },
        "target_grid": GRID,
        "isolation_distance_m": ISOLATION_M,
        "region_definitions": {
            "core": "到本 core 距离 = 0（holdout 区，评分发生在这里）",
            "buffer": f"0 < 距离 < {ISOLATION_M:.0f} m（隔离带，既不标定也不评分）",
            "geometric_calibration_domain": f"距离 >= {ISOLATION_M:.0f} m（合同②的隔离准入）",
            "note": "三者对每个 fold 互斥且穷尽整个 ROI，已逐 fold 断言。",
        },
        "shared_topology": {
            "applies_to_all_18_acquisitions": True,
            "applies_to_both_bands": True,
            "statement": "topology 对全部 18 景与 B4/B5 共用，不得逐 acquisition、逐 band 或按支持量重新选择（合同③）。",
        },
        "folds": folds,
        "pairwise_cores": pairwise,
        "layering_boundary": {
            "required_by": "合同⑤：不得在 topology 选择或冻结时读取逐景 calibration_lit、QA/validity 或 alpha",
            "opened_any_raster_for_reading": False,
            "read_per_acquisition_data": False,
            "read_alpha_or_residual": False,
            "note": (
                "本 manifest 的全部数值仅由 ROI/grid 坐标与 core 投影边界的解析几何得到。"
                "actual_calibration_lit 只能在本 manifest 冻结之后，由 geometric_calibration_domain_k "
                "与逐景上游有效性及 Stage 7.2 geometry_visibility 代理求交生成，其计数不得反向影响 topology。"
            ),
        },
        "independence_caveat": (
            "几何标定域两两重叠显著（见 geometric-feasibility-audit-v1.json 的 pairwise），"
            "与 Stage 7.0 leakage_audit 的 pairwise shared calibration 10/10 一致。"
            "这些 fold 不构成独立样本；fold 数不得用作 effective n，不得据以计算 p 值或置信区间。"
        ),
        "sampling_bias_caveat": (
            "5 个 core 由 C5-D3 按 combined_risk_stress 准则选定，刻意位于阴影与质量风险高处，"
            "非随机采样、非均匀覆盖。fold 级结果只代表本 ROI 内已知最难区域的表现。"
        ),
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": "frozen",
        "folds": len(folds),
        "all_isolation_admitted": all(f["isolation_admitted"] for f in folds),
        "all_partitions_valid": all(f["partition_exhaustive_and_exclusive"] for f in folds),
        "min_core_to_core_m": min(p["core_to_core_distance_m"] for p in pairwise),
        "any_cores_overlap": any(p["cores_overlap"] for p in pairwise),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
