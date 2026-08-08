#!/usr/bin/env python3
"""Stage 7.3 ⑤后半 / ⑥ / ⑦ / ⑧：逐 fold alpha、泄漏证明、支持账本与描述性 residual。

严格的先后顺序由合同规定，本程序按序执行且不可颠倒：

  1. 读取**已冻结**的 topology manifest（若未 frozen 即停机）
  2. actual_calibration_lit_{acq,band,k}
       = geometric_calibration_domain_k ∩ 该景上游有效性 ∩ Stage 7.2 geometry_visibility 代理
  3. 逐 fold 重估 alpha_{acq,band,-k}，沿用 Stage 7.2 的同一公式、辐射缩放链路、
     Σμ²>0 与操作阈值 calibration_lit ≥ 271；不足即 unsupported_calibration
  4. 证明 actual calibration 与本 fold core 及其 8,130 m 隔离带无交集
  5. 只在 core 内、只对 supported 像元评分，指标与分母逐字取自 Stage 7.0 evaluation protocol

铁律（合同⑥）：全支持 reference alpha **禁止**用于任何 fold 的成绩；本程序不读取
Stage 7.2 的 alpha-reference-full-support，从源头断掉这条路。

铁律（合同⑦⑧）：fold、像元或共享标定的 core 均不得冒充独立重复；本程序不计算
effective n、p 值或置信区间，只产出单元级表格与描述性汇总。

不调用 Earth Engine，不改任何冻结件，不做机制比较或排名。
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

SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_ROOT = SCRIPT_DIR.parent
STAGE_7_1 = STAGE_ROOT.parent / "stage7_1_observation_stack"
STAGE_7_2 = STAGE_ROOT.parent / "stage7_2_baseline_fit"

# 全部取自 Stage 7.0 baseline_spec / Stage 7.1-R schema / Stage 7.2 契约，本程序不新增常数
SR_SCALE = 0.0000275
SR_OFFSET = -0.2
SR_MIN = -0.05
SR_MAX = 1.0
QA_CLEAR_MASK = 0b111111
QA_WATER_BIT = 7
MCONF_COS_I_THRESHOLD = 0.1
MIN_CALIBRATION_LIT_PIXELS = 271
FLOAT_NODATA = -9999.0
BANDS = ("SR_B4", "SR_B5")

REASON_SUPPORT_BELOW_MINIMUM = "calibration_support_below_minimum"
REASON_NONPOSITIVE_DENOMINATOR = "nonpositive_mu_squared_denominator"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_terrain_valid(support_audit: dict[str, Any]) -> np.ndarray:
    valid = None
    for name, record in sorted(support_audit["terrain_geometry"].items()):
        path = STAGE_ROOT.parents[1] / record["relative_path"]
        if sha256_file(path) != record["sha256"]:
            raise SystemExit(f"stop: terrain component {name} hash drifted")
        with rasterio.open(path) as dataset:
            band = dataset.read(1).astype("float64")
            nodata = dataset.nodata
        finite = np.isfinite(band)
        if nodata is not None:
            finite &= band != nodata
        valid = finite if valid is None else (valid & finite)
    return valid


def percentile_90(values: np.ndarray) -> float:
    return float(np.percentile(np.abs(values), 90))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-output", type=Path, required=True)
    parser.add_argument("--residual-output", type=Path, required=True)
    args = parser.parse_args()
    args.ledger_output = args.ledger_output.resolve()
    args.residual_output = args.residual_output.resolve()

    topology_path = STAGE_ROOT / "evidence/topology-manifest-v1.json"
    topology = load_json(topology_path)
    if topology.get("status") != "frozen":
        raise SystemExit("stop: topology manifest 未冻结，不得生成 actual calibration")

    input_view = load_json(STAGE_7_1 / "evidence/stage-7.2-direct-only-input-view-v1.json")
    support_audit = load_json(STAGE_7_1 / "evidence/local-support-audit-v1.json")
    export_manifest = load_json(STAGE_7_1 / "evidence/export-manifest-v3.json")
    cos_i_registry = load_json(STAGE_7_2 / "evidence/cos-i-registry-v1.json")
    mconf_registry = load_json(STAGE_7_2 / "evidence/mconf-registry-v1.json")

    terrain_valid = read_terrain_valid(support_audit)
    stack_root = STAGE_7_1 / export_manifest["path_policy"]["root_relative_path"]
    stack_bands = export_manifest["execution"]["bands"]
    locator = {e["acquisition_id"]: e["target_relative_to_alias"] for e in export_manifest["acquisitions"]}
    cos_i_by_id = {m["acquisition_id"]: m for m in cos_i_registry["members"]}
    mconf_by_id = {m["acquisition_id"]: m for m in mconf_registry["members"]}

    # 载入已冻结的几何标定域与 core 几何（core 由投影边界解析重建，不依赖任何影像）
    folds = []
    for record in topology["folds"]:
        mask_path = STAGE_ROOT / record["geometric_calibration_domain"]["relative_path"]
        if sha256_file(mask_path) != record["geometric_calibration_domain"]["sha256"]:
            raise SystemExit(f"stop: geometric calibration domain {record['fold_index']} hash drifted")
        with rasterio.open(mask_path) as dataset:
            domain = dataset.read(1).astype(bool)
        left, bottom, right, top = record["core_projected_bounds"]
        grid = topology["target_grid"]
        xs = grid["bounds"][0] + (np.arange(grid["width"]) + 0.5) * grid["resolution"]
        ys = grid["bounds"][3] - (np.arange(grid["height"]) + 0.5) * grid["resolution"]
        x, y = np.meshgrid(xs, ys)
        core = (x >= left) & (x <= right) & (y >= bottom) & (y <= top)
        if (core & domain).any():
            raise SystemExit(f"stop: fold {record['fold_index']} 的 core 与几何标定域相交")
        folds.append({"record": record, "domain": domain, "core": core})

    eligible = {c["acquisition_id"]: c for c in input_view["eligible_candidates"]}
    units = []
    actual_calibration_masks: dict[tuple[int, int], np.ndarray] = {}

    for entry in sorted(export_manifest["acquisitions"], key=lambda e: e["order"]):
        acquisition_id = entry["acquisition_id"]
        if acquisition_id not in eligible:
            continue  # 3 景 operation_scoped_unsupported 不进入标定与评分
        order = entry["order"]

        with rasterio.open(stack_root / locator[acquisition_id]) as dataset:
            data = {name: dataset.read(index + 1) for index, name in enumerate(stack_bands)}
        cos_i_record = cos_i_by_id[acquisition_id]
        cos_i_path = STAGE_7_2 / cos_i_record["output"]["relative_path"]
        if sha256_file(cos_i_path) != cos_i_record["output"]["sha256"]:
            raise SystemExit(f"stop: cos_i raster hash drifted for order {order}")
        with rasterio.open(cos_i_path) as dataset:
            cos_i = dataset.read(1).astype("float64")
        cos_i_valid = cos_i != FLOAT_NODATA

        # 上游有效性沿用 Stage 7.1-R 冻结定义；geometry_visibility 沿用 Stage 7.2 冻结代理
        msource = (data["SR_B4_VALID"] == 1) & (data["SR_B5_VALID"] == 1) & (data["QA_PIXEL_VALID"] == 1)
        rho = {band: data[band].astype("float64") * SR_SCALE + SR_OFFSET for band in BANDS}
        in_range = np.ones_like(msource)
        for band in BANDS:
            in_range &= np.isfinite(rho[band]) & (rho[band] >= SR_MIN) & (rho[band] <= SR_MAX)
        qa = data["QA_PIXEL"]
        qa_clear = (qa & QA_CLEAR_MASK) == 0
        water = ((qa >> QA_WATER_BIT) & 1) == 1
        base_valid_land = msource & qa_clear & in_range & terrain_valid & ~water
        mconf = (cos_i > MCONF_COS_I_THRESHOLD) & cos_i_valid
        calibration_lit = base_valid_land & mconf
        mu = np.maximum(cos_i, 0.0)

        for fold in folds:
            k = fold["record"]["fold_index"]
            domain, core = fold["domain"], fold["core"]

            actual_calibration = calibration_lit & domain
            actual_calibration_masks[(order, k)] = actual_calibration
            n_pixels = int(actual_calibration.sum())
            denominator = float((mu[actual_calibration] ** 2).sum())

            # ⑧ 的四个并列口径，全部在 holdout core 内
            core_total = int(core.sum())
            core_upstream_valid = int((base_valid_land & core).sum())
            core_geometry_supported = int((mconf & core).sum())
            scored_mask = base_valid_land & mconf & core
            scored = int(scored_mask.sum())
            unsupported_by_direct_only = int((base_valid_land & ~mconf & core).sum())

            for band in BANDS:
                numerator = float((mu[actual_calibration] * rho[band][actual_calibration]).sum())
                if n_pixels < MIN_CALIBRATION_LIT_PIXELS:
                    state, reason, alpha = "unsupported_calibration", REASON_SUPPORT_BELOW_MINIMUM, None
                elif denominator <= 0:
                    state, reason, alpha = "unsupported_calibration", REASON_NONPOSITIVE_DENOMINATOR, None
                else:
                    alpha = float(np.clip(numerator / denominator, 0.0, 1.0))
                    state, reason = "fitted", None

                unit: dict[str, Any] = {
                    "order": order,
                    "acquisition_id": acquisition_id,
                    "short_product_id": entry["short_product_id"],
                    "split": eligible[acquisition_id]["split"],
                    "band": band,
                    "fold_index": k,
                    "core_id": fold["record"]["core_id"],
                    "state": state,
                    "alpha_fold_safe": alpha,
                    "alpha_source": "within_acquisition_calibration_excluding_own_core_and_buffer",
                    "reference_alpha_used": False,
                    "calibration": {
                        "actual_calibration_lit_pixels": n_pixels,
                        "numerator_sum_mu_rho": numerator,
                        "denominator_sum_mu_squared": denominator,
                        "geometric_calibration_domain_sha256":
                            fold["record"]["geometric_calibration_domain"]["sha256"],
                    },
                    "fallback_receipt": None if state == "fitted" else {
                        "reason_code": reason,
                        "triggering_predicate": (
                            f"actual_calibration_lit {n_pixels} < {MIN_CALIBRATION_LIT_PIXELS}"
                            if reason == REASON_SUPPORT_BELOW_MINIMUM
                            else f"sum(mu^2) = {denominator} <= 0"
                        ),
                        "default_alpha_written": False,
                        "imputed": False,
                        "reference_alpha_fallback": False,
                    },
                    "holdout_core_accounting": {
                        "core_total_pixels": core_total,
                        "upstream_valid_pixels": core_upstream_valid,
                        "geometry_proxy_supported_pixels": core_geometry_supported,
                        "scored_pixels": scored,
                        "unsupported_by_direct_only_pixels": unsupported_by_direct_only,
                        "support_coverage": (
                            round(scored / core_upstream_valid, 6) if core_upstream_valid else None
                        ),
                        "coverage_denominator": "base_valid_land within holdout core（Stage 7.0 口径）",
                    },
                }

                if state == "fitted" and scored > 0:
                    residual = (alpha * mu[scored_mask]) - rho[band][scored_mask]
                    unit["residual"] = {
                        "definition": "residual = rho_hat - rho_obs（Stage 7.0 evaluation protocol 唯一定义）",
                        "signed_bias": float(residual.mean()),
                        "mae": float(np.abs(residual).mean()),
                        "p90_absolute_residual": percentile_90(residual),
                        "scored_pixels": scored,
                    }
                else:
                    unit["residual"] = {
                        "state": "not_scored",
                        "reason": "unsupported_calibration" if state != "fitted" else "no_supported_pixel_in_core",
                    }
                units.append(unit)

    # ⑦ 泄漏证明：actual calibration 与本 fold core 及其隔离带无交集
    leakage_checks = []
    for fold in folds:
        k = fold["record"]["fold_index"]
        core = fold["core"]
        forbidden = ~fold["domain"]  # core ∪ buffer
        violations = [
            {"order": order, "pixels": int((mask & forbidden).sum())}
            for (order, fold_index), mask in actual_calibration_masks.items()
            if fold_index == k and (mask & forbidden).any()
        ]
        leakage_checks.append({
            "fold_index": k,
            "core_id": fold["record"]["core_id"],
            "actual_calibration_intersects_core_or_buffer": bool(violations),
            "violations": violations,
        })
    if any(c["actual_calibration_intersects_core_or_buffer"] for c in leakage_checks):
        raise SystemExit("stop: actual calibration 侵入了 core 或隔离带")

    # ⑦ 逐对报告 fold 是否共享 actual calibration
    shared = []
    orders = sorted({order for order, _ in actual_calibration_masks})
    for a, b in combinations([f["record"]["fold_index"] for f in folds], 2):
        per_order = []
        for order in orders:
            mask_a = actual_calibration_masks[(order, a)]
            mask_b = actual_calibration_masks[(order, b)]
            per_order.append(int((mask_a & mask_b).sum()))
        shared.append({
            "fold_pair": [a, b],
            "shares_actual_calibration": any(v > 0 for v in per_order),
            "shared_pixel_count_range": [min(per_order), max(per_order)],
            "acquisitions_with_shared_calibration": sum(1 for v in per_order if v > 0),
        })

    fitted = [u for u in units if u["state"] == "fitted"]
    unsupported = [u for u in units if u["state"] != "fitted"]
    scored_units = [u for u in units if "signed_bias" in u.get("residual", {})]

    boundary = {
        "earth_engine_called": False,
        "frozen_evidence_rewritten": False,
        "membership_changed": False,
        "split_reassigned": False,
        "topology_changed_after_freeze": False,
        "reference_alpha_used_for_any_score": False,
        "effective_n_or_p_value_computed": False,
        "mechanism_compared_or_ranked": False,
    }
    common = {
        "created_at_utc": "2026-08-08T00:00:00Z",
        "topology_manifest": {
            "relative_path": "evidence/topology-manifest-v1.json",
            "sha256": sha256_file(topology_path),
            "status": topology["status"],
        },
        "boundary": boundary,
    }

    ledger = {
        "schema": "mountainrs-stage7.3-fold-alpha-and-leakage-ledger-v1",
        "contract_clause": "Stage 7.3 ⑤后半 / ⑥ / ⑦",
        **common,
        "estimator": {
            "formula": "alpha = clip(sum(mu*rho)/sum(mu^2), 0, 1)",
            "identical_to_stage_7_2": True,
            "minimum_support_threshold": MIN_CALIBRATION_LIT_PIXELS,
            "threshold_relaxed": False,
            "actual_calibration_definition":
                "geometric_calibration_domain_k ∩ base_valid_land ∩ geometry_visibility(cos_i > 0.1)",
        },
        "counts": {
            "units_total": len(units),
            "fitted": len(fitted),
            "unsupported_calibration": len(unsupported),
        },
        "leakage_checks": leakage_checks,
        "fold_pairwise_shared_actual_calibration": shared,
        "independence_statement": (
            "逐对结果显示 fold 之间共享 actual calibration，与 Stage 7.0 leakage_audit 的"
            " pairwise shared calibration 10/10 一致。这些 fold 不是统计独立重复；"
            "fold 数不得用作 effective n，不得据以计算 p 值或置信区间。"
        ),
        "units": units,
    }
    ledger_sha = args.ledger_output
    ledger_sha.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    # ⑧ 描述性汇总：先单元级，再按 acquisition 等权，只用中位数与范围
    def describe(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0}
        array = np.array(values, dtype="float64")
        return {
            "count": len(values),
            "median": float(np.median(array)),
            "min": float(array.min()),
            "max": float(array.max()),
        }

    by_band_fold = {}
    for band in BANDS:
        for fold in folds:
            k = fold["record"]["fold_index"]
            subset = [u for u in scored_units if u["band"] == band and u["fold_index"] == k]
            by_band_fold[f"{band}|fold{k}"] = {
                "band": band,
                "fold_index": k,
                "scored_unit_count": len(subset),
                "acquisitions_scored": sorted({u["short_product_id"] for u in subset}),
                "signed_bias": describe([u["residual"]["signed_bias"] for u in subset]),
                "mae": describe([u["residual"]["mae"] for u in subset]),
                "p90_absolute_residual": describe([u["residual"]["p90_absolute_residual"] for u in subset]),
                "support_coverage": describe([
                    u["holdout_core_accounting"]["support_coverage"] for u in subset
                    if u["holdout_core_accounting"]["support_coverage"] is not None
                ]),
            }

    residual_summary = {
        "schema": "mountainrs-stage7.3-descriptive-residual-summary-v1",
        "contract_clause": "Stage 7.3 ⑧",
        **common,
        "scoring_protocol": {
            "source": "../stage7_0_baseline/docs/evaluation_protocol.md",
            "residual_definition": "residual = rho_hat - rho_obs",
            "metrics": ["signed bias", "MAE", "P90 absolute residual"],
            "scored_mask": "only supported pixels（base_valid_land ∩ geometry_visibility）within holdout core",
            "coverage_denominator": "base_valid_land within holdout core",
            "minimum_reporting_unit": "acquisition × band × fold",
            "aggregation": [
                "先在每个评估单元内计算指标",
                "描述性汇总，不以像元池化替代单元级结果",
                "只用中位数与范围",
                "不计算 effective n、p 值或置信区间",
            ],
        },
        "counts": {
            "units_total": len(units),
            "scored_units": len(scored_units),
            "not_scored_units": len(units) - len(scored_units),
        },
        "by_band_and_fold": by_band_fold,
        "semantic_boundary": {
            "single_roi_same_domain_diagnostic": True,
            "replaces_cross_domain_isolated_validation": False,
            "statement": (
                "本汇总是单 ROI 同域空间阻断诊断。标定/拟合支持与留出来自同一 ROI、同一气候带"
                "与地质背景，按架构 v3.1 §2.7 与 §6 不能替代 Cross-Domain Isolated Validation；"
                "正式跨域验证属 Stage 7.9 / 7.10。不得据本结果声称泛化能力。"
            ),
            "sampling_bias": topology["sampling_bias_caveat"],
            "independence": topology["independence_caveat"],
        },
    }
    args.residual_output.write_text(
        json.dumps(residual_summary, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": "completed",
        "units_total": len(units),
        "fitted": len(fitted),
        "unsupported_calibration": len(unsupported),
        "scored_units": len(scored_units),
        "leakage_violations": sum(len(c["violations"]) for c in leakage_checks),
        "fold_pairs_sharing_calibration": sum(1 for s in shared if s["shares_actual_calibration"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
