#!/usr/bin/env python3
"""Stage 7.6 消融：逐 acquisition×band×fold 拟合 C0/C1p/C1/C2a 并评分。

数据装载、成员验明、support 构造、fold 几何与评分掩膜逐字沿用 Stage 7.3 的
fit_fold_alpha_and_score_v1.py。本程序新增的只有 v_sky 与三个加性候选——
口径若有任何自行发明，候选之间与跨节点的比较都不成立。

铁律：
  - 每个参数只由该 fold 的 actual calibration（calibration_lit ∩ 标定域）估计；
    held-out core 及其隔离带不参与任何拟合，支持不足即 unsupported，不回退全域。
  - 不读取 Stage 7.2 的全支持 reference alpha。
  - 判定规则已在 optical-operator-config-v1 冻结，本程序只执行，不选择。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

SCRIPT_DIR = Path(__file__).resolve().parent
CONTAINER = SCRIPT_DIR.parent
STAGE_ROOT = CONTAINER.parent
STAGE_7_1 = STAGE_ROOT / "stage7_1_observation_stack"
STAGE_7_2 = STAGE_ROOT / "stage7_2_baseline_fit"
STAGE_7_3 = STAGE_ROOT / "stage7_3_spatial_blocking"

SR_SCALE, SR_OFFSET = 0.0000275, -0.2
SR_MIN, SR_MAX = -0.05, 1.0
QA_CLEAR_MASK, QA_WATER_BIT = 0b111111, 7
MCONF_COS_I_THRESHOLD = 0.1
MIN_CALIBRATION_LIT_PIXELS = 271
FLOAT_NODATA = -9999.0
MIN_VSKY_IQR = 0.05
NUMERICAL_RANK_RTOL = 1e-10  # 与 Stage 7.5 identifiability_toolbox 同值
BANDS = ("SR_B4", "SR_B5")

R_SUPPORT_LOW = "calibration_support_below_minimum"
R_DENOM = "nonpositive_mu_squared_denominator"
R_VSKY_FLAT = "insufficient_v_sky_variation"
R_SINGULAR = "singular_design_matrix"
R_NO_SCORE_PIXEL = "no_supported_pixel_in_core"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def read_terrain_valid(support_audit: dict[str, Any]) -> np.ndarray:
    valid = None
    for _, record in sorted(support_audit["terrain_geometry"].items()):
        if not isinstance(record, dict) or "relative_path" not in record:
            continue
        path = STAGE_ROOT.parents[0] / record["relative_path"]
        if sha256_file(path) != record["sha256"]:
            raise SystemExit(f"stop: terrain component hash drifted: {record['relative_path']}")
        with rasterio.open(path) as dataset:
            array = dataset.read(1)
            mask = array != record["nodata"]
        valid = mask if valid is None else (valid & mask)
    return valid


# 候选 -> 设计矩阵（列顺序即参数顺序；首列恒为 mu，故 theta[0] 恒为 alpha）
DESIGN = {
    "C0":  lambda mu, v: np.column_stack([mu]),
    "C1p": lambda mu, v: np.column_stack([mu, np.ones_like(mu)]),
    "C1":  lambda mu, v: np.column_stack([mu, v]),
    "C2a": lambda mu, v: np.column_stack([mu, 1.0 - v]),
}
PARAM_NAMES = {"C0": ["alpha"], "C1p": ["alpha", "beta_0"],
               "C1": ["alpha", "beta_v"], "C2a": ["alpha", "beta_terr"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()

    config = load_json(CONTAINER / "configs/optical-operator-config-v1.json")
    frozen_order = config["ablation_order"]["frozen_sequence"]
    freeze_manifest = load_json(CONTAINER / "evidence/freeze-manifest-v1.json")

    vsky_record = freeze_manifest["artifacts"]["v_sky_roi_grid_v1"]
    vsky_path = (CONTAINER / "evidence" / vsky_record["relative_path"]).resolve()
    if sha256_file(vsky_path) != vsky_record["sha256"]:
        raise SystemExit("stop: v_sky raster hash drifted")
    with rasterio.open(vsky_path) as dataset:
        v_sky = dataset.read(1).astype("float64")
        vsky_transform, vsky_crs = dataset.transform, dataset.crs

    topology = load_json(STAGE_7_3 / "evidence/topology-manifest-v1.json")
    if topology.get("status") != "frozen":
        raise SystemExit("stop: topology manifest 未冻结")

    input_view = load_json(STAGE_7_1 / "evidence/stage-7.2-direct-only-input-view-v1.json")
    support_audit = load_json(STAGE_7_1 / "evidence/local-support-audit-v1.json")
    export_manifest = load_json(STAGE_7_1 / "evidence/export-manifest-v3.json")
    evidence_manifest = load_json(STAGE_7_1 / "evidence/observation-evidence-manifest-v1.json")
    cos_i_registry = load_json(STAGE_7_2 / "evidence/cos-i-registry-v1.json")

    terrain_valid = read_terrain_valid(support_audit)
    stack_root = STAGE_7_1 / export_manifest["path_policy"]["root_relative_path"]
    stack_bands = export_manifest["execution"]["bands"]
    locator = {e["acquisition_id"]: e["target_relative_to_alias"] for e in export_manifest["acquisitions"]}
    cos_i_by_id = {m["acquisition_id"]: m for m in cos_i_registry["members"]}
    member_sha256 = {m["acquisition_id"]: m["member_sha256"] for m in evidence_manifest["members"]}

    # v_sky 必须与 Stage 7.3 目标网格逐像元对齐，否则 mask 与栅格错位而无声出错
    grid = topology["target_grid"]
    if v_sky.shape != (grid["height"], grid["width"]):
        raise SystemExit(f"stop: v_sky 形状 {v_sky.shape} 与目标网格 "
                         f"{(grid['height'], grid['width'])} 不一致")
    if abs(vsky_transform.c - grid["bounds"][0]) > 1e-6 or abs(vsky_transform.f - grid["bounds"][3]) > 1e-6:
        raise SystemExit("stop: v_sky 原点与目标网格 bounds 不一致")
    if abs(vsky_transform.a - grid["resolution"]) > 1e-9:
        raise SystemExit("stop: v_sky 分辨率与目标网格不一致")

    folds = []
    for record in topology["folds"]:
        mask_path = STAGE_7_3 / record["geometric_calibration_domain"]["relative_path"]
        if sha256_file(mask_path) != record["geometric_calibration_domain"]["sha256"]:
            raise SystemExit(f"stop: geometric calibration domain {record['fold_index']} hash drifted")
        with rasterio.open(mask_path) as dataset:
            domain = dataset.read(1).astype(bool)
        left, bottom, right, top = record["core_projected_bounds"]
        xs = grid["bounds"][0] + (np.arange(grid["width"]) + 0.5) * grid["resolution"]
        ys = grid["bounds"][3] - (np.arange(grid["height"]) + 0.5) * grid["resolution"]
        x, y = np.meshgrid(xs, ys)
        core = (x >= left) & (x <= right) & (y >= bottom) & (y <= top)
        if (core & domain).any():
            raise SystemExit(f"stop: fold {record['fold_index']} 的 core 与几何标定域相交")
        folds.append({"record": record, "domain": domain, "core": core})

    eligible = {c["acquisition_id"]: c for c in input_view["eligible_candidates"]}
    units: list[dict[str, Any]] = []
    leakage_violations: list[dict[str, Any]] = []

    for entry in sorted(export_manifest["acquisitions"], key=lambda e: e["order"]):
        acquisition_id = entry["acquisition_id"]
        if acquisition_id not in eligible:
            continue  # 3 景 operation_scoped_unsupported 不进入标定与评分
        order = entry["order"]

        tif = stack_root / locator[acquisition_id]
        if sha256_file(tif) != member_sha256[acquisition_id]:
            raise SystemExit(f"stop: observation stack member hash drifted for order {order}")
        with rasterio.open(tif) as dataset:
            data = {name: dataset.read(index + 1) for index, name in enumerate(stack_bands)}

        cos_i_record = cos_i_by_id[acquisition_id]
        cos_i_path = STAGE_7_2 / cos_i_record["output"]["relative_path"]
        if sha256_file(cos_i_path) != cos_i_record["output"]["sha256"]:
            raise SystemExit(f"stop: cos_i raster hash drifted for order {order}")
        with rasterio.open(cos_i_path) as dataset:
            cos_i = dataset.read(1).astype("float64")
        cos_i_valid = cos_i != FLOAT_NODATA

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

        # v_sky 有限性并入支持条件：非有限值不得进入拟合或评分
        vsky_finite = np.isfinite(v_sky)

        for fold in folds:
            k = fold["record"]["fold_index"]
            domain, core = fold["domain"], fold["core"]

            actual_calibration = calibration_lit & domain & vsky_finite
            if (actual_calibration & core).any():
                leakage_violations.append({"order": order, "fold": k,
                                           "kind": "calibration_intersects_core"})
            n_pixels = int(actual_calibration.sum())
            scored_mask = base_valid_land & mconf & core & vsky_finite
            core_base_valid = int((base_valid_land & core).sum())

            mu_t, v_t = mu[actual_calibration], v_sky[actual_calibration]
            mu_s, v_s = mu[scored_mask], v_sky[scored_mask]
            denominator = float((mu_t ** 2).sum())
            iqr_v = float(np.subtract(*np.percentile(v_t, [75, 25]))) if n_pixels else 0.0

            for band in BANDS:
                rho_t, rho_s = rho[band][actual_calibration], rho[band][scored_mask]
                unit: dict[str, Any] = {
                    "order": order,
                    "acquisition_id": acquisition_id,
                    "short_product_id": entry["short_product_id"],
                    "split": eligible[acquisition_id]["split"],
                    "band": band,
                    "fold_index": k,
                    "core_id": fold["record"]["core_id"],
                    "calibration_lit": n_pixels,
                    "core_base_valid_land": core_base_valid,
                    "core_scored": int(scored_mask.sum()),
                    "train_v_sky_iqr": iqr_v,
                    "candidates": {},
                }

                for cid in frozen_order:
                    entry_c: dict[str, Any] = {"state": None, "reason": None, "params": None}
                    if n_pixels < MIN_CALIBRATION_LIT_PIXELS:
                        entry_c.update(state="unsupported", reason=R_SUPPORT_LOW)
                    elif denominator <= 0:
                        entry_c.update(state="unsupported", reason=R_DENOM)
                    elif cid != "C0" and iqr_v < MIN_VSKY_IQR:
                        entry_c.update(state="unsupported", reason=R_VSKY_FLAT)
                    else:
                        design = DESIGN[cid](mu_t, v_t)
                        # 秩与条件数用与 Stage 7.5 工具箱相同的 rtol=1e-10 判定，
                        # 不使用 lstsq 自己的默认阈值——否则两处「数值秩亏」含义不同
                        singular_values = np.linalg.svd(design, compute_uv=False)
                        cond = (float(singular_values[0] / singular_values[-1])
                                if singular_values[-1] > 0 else float("inf"))
                        entry_c["condition_number"] = cond
                        entry_c["numerically_rank_deficient"] = bool(
                            singular_values[-1] <= singular_values[0] * NUMERICAL_RANK_RTOL)
                        theta, *_ = np.linalg.lstsq(design, rho_t, rcond=None)
                        if entry_c["numerically_rank_deficient"] or not np.all(np.isfinite(theta)):
                            entry_c.update(state="unsupported", reason=R_SINGULAR)
                        else:
                            entry_c["params"] = {n: float(t) for n, t in zip(PARAM_NAMES[cid], theta)}
                            entry_c["alpha_outside_unit_interval"] = bool(theta[0] < 0.0 or theta[0] > 1.0)
                            if scored_mask.sum() == 0:
                                entry_c.update(state="not_scored", reason=R_NO_SCORE_PIXEL)
                            else:
                                residual = DESIGN[cid](mu_s, v_s) @ theta - rho_s
                                entry_c.update(
                                    state="scored", reason=None,
                                    mae=float(np.mean(np.abs(residual))),
                                    signed_bias=float(np.mean(residual)),
                                    p90_abs=float(np.percentile(np.abs(residual), 90)),
                                    n_scored=int(residual.size),
                                    coverage=(float(residual.size / core_base_valid)
                                              if core_base_valid else None),
                                )
                    unit["candidates"][cid] = entry_c
                units.append(unit)

    output = {
        "schema": "mountainrs-stage7.6-ablation-unit-table-v1",
        "provenance": {
            "frozen_config_sha256": freeze_manifest["artifacts"]["optical_operator_config_v1"]["sha256"],
            "v_sky_sha256": vsky_record["sha256"],
            "v_sky_crs": str(vsky_crs),
            "loading_lineage": "Stage 7.3 fit_fold_alpha_and_score_v1.py 装载段逐字沿用",
        },
        "ablation_order": frozen_order,
        "leakage_audit": {
            "violation_count": len(leakage_violations),
            "violations": leakage_violations,
            "checked": "actual_calibration ∩ core，逐 acquisition×fold",
        },
        "unit_count": len(units),
        "units": units,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"单元 {len(units)}   泄漏违规 {len(leakage_violations)}")
    for cid in frozen_order:
        tally: dict[str, int] = {}
        for unit in units:
            state = unit["candidates"][cid]["state"]
            tally[state] = tally.get(state, 0) + 1
        print(f"  {cid:>4}: " + "  ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    return 1 if leakage_violations else 0


if __name__ == "__main__":
    sys.exit(main())
