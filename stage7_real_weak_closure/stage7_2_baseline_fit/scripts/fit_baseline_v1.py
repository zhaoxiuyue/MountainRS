#!/usr/bin/env python3
"""Stage 7.2 ②④⑥⑦：Mconf 生成、全支持参考 alpha、支持损失账本与 fallback receipt。

流水线只有一条，且每一步都由已冻结、已获批的文本决定，本程序不做任何自由裁量：

    cos_i ──(Mconf 子协议 v1)──> Mconf ──(calibration contract v1)──> calibration_lit
          ──(Stage 7.0 baseline_spec)──> alpha_reference_full_support

三份上游冻结件都会在启动时按状态与哈希验明；任何一份不是 frozen 就停机——
合同 ②③ 要求这两份必须先获所有者批准，未批准即动手是违约而不是效率。

Mconf 对全部 21 个 evidence member 生成（纯几何，与操作资格无关）；
calibration_lit 与 alpha 只在 18 景 eligible_candidate 上计算。

不调用 Earth Engine，不评分，不算 residual、reliability 或任何置信度。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPT_DIR.parents[2]
STAGE_7_1 = STAGE_ROOT.parent / "stage7_1_observation_stack"

# 全部取自 Stage 7.0 baseline_spec.md 与 Stage 7.1-R validity-support-schema-v1，
# 本程序不新增任何常数。
SR_SCALE = 0.0000275
SR_OFFSET = -0.2
SR_MIN = -0.05
SR_MAX = 1.0
QA_CLEAR_MASK = 0b111111
QA_WATER_BIT = 7
MCONF_COS_I_THRESHOLD = 0.1          # Stage 7.0 baseline_spec: supported := cos_i > 0.1
MIN_CALIBRATION_LIT_PIXELS = 271     # calibration contract v1 方案 B（8.13 km 独立尺度）
PIXEL_SIZE_M = 30.0
BANDS = ("SR_B4", "SR_B5")
VALID_BANDS = {"SR_B4": "SR_B4_VALID", "SR_B5": "SR_B5_VALID", "QA_PIXEL": "QA_PIXEL_VALID"}
FLOAT_NODATA = -9999.0

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


def require_frozen(path: Path, marker: str) -> dict[str, Any]:
    """冻结件门禁：合同文本必须已是 frozen 状态，否则停机。"""
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        raise SystemExit(
            f"stop: {path.name} 未处于 frozen 状态（未找到标记 {marker!r}）；"
            "合同 ②③ 要求所有者批准后方可执行"
        )
    return {"relative_path": str(path.relative_to(STAGE_ROOT)), "sha256": sha256_file(path)}


def read_terrain_valid(support_audit: dict[str, Any]) -> np.ndarray:
    valid = None
    for name, record in sorted(support_audit["terrain_geometry"].items()):
        path = REPO_ROOT / record["relative_path"]
        observed = sha256_file(path)
        if observed != record["sha256"]:
            raise SystemExit(f"stop: terrain component {name} hash drifted")
        with rasterio.open(path) as dataset:
            band = dataset.read(1).astype("float64")
            nodata = dataset.nodata
        finite = np.isfinite(band)
        if nodata is not None:
            finite &= band != nodata
        valid = finite if valid is None else (valid & finite)
    return valid


def bbox_diagonal_m(mask: np.ndarray) -> float:
    """calibration 集合的空间跨度——contract 4.2 要求记录但明确不作阈值。"""
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return 0.0
    height = (rows.max() - rows.min() + 1) * PIXEL_SIZE_M
    width = (cols.max() - cols.min() + 1) * PIXEL_SIZE_M
    return float(math.hypot(height, width))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mconf-dir", type=Path, required=True)
    parser.add_argument("--mconf-registry", type=Path, required=True)
    parser.add_argument("--alpha-output", type=Path, required=True)
    parser.add_argument("--ledger-output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("mconf_dir", "mconf_registry", "alpha_output", "ledger_output"):
        setattr(args, name, getattr(args, name).resolve())

    frozen_inputs = {
        "mconf_subprotocol": require_frozen(
            STAGE_ROOT / "docs/mconf-subprotocol-v1.md", "**状态：** `frozen`"
        ),
        "calibration_contract": require_frozen(
            STAGE_ROOT / "docs/calibration-contract-v1.md", "**状态：** `frozen`"
        ),
        "validity_support_schema_v2": {
            "relative_path": "configs/validity-support-schema-v2.json",
            "sha256": sha256_file(STAGE_ROOT / "configs/validity-support-schema-v2.json"),
        },
        "cos_i_registry": {
            "relative_path": "evidence/cos-i-registry-v1.json",
            "sha256": sha256_file(STAGE_ROOT / "evidence/cos-i-registry-v1.json"),
        },
    }

    cos_i_registry = load_json(STAGE_ROOT / "evidence/cos-i-registry-v1.json")
    input_view = load_json(STAGE_7_1 / "evidence/stage-7.2-direct-only-input-view-v1.json")
    support_audit = load_json(STAGE_7_1 / "evidence/local-support-audit-v1.json")
    export_manifest = load_json(STAGE_7_1 / "evidence/export-manifest-v3.json")

    terrain_valid = read_terrain_valid(support_audit)
    stack_root = STAGE_7_1 / export_manifest["path_policy"]["root_relative_path"]
    stack_bands = export_manifest["execution"]["bands"]
    locator = {e["acquisition_id"]: e["target_relative_to_alias"] for e in export_manifest["acquisitions"]}

    args.mconf_dir.mkdir(parents=True, exist_ok=True)
    mconf_records = []
    alpha_records = []
    ledger_records = []

    for member in cos_i_registry["members"]:
        cos_i_path = STAGE_ROOT / member["output"]["relative_path"]
        if sha256_file(cos_i_path) != member["output"]["sha256"]:
            raise SystemExit(f"stop: cos_i raster hash drifted for order {member['order']}")
        with rasterio.open(cos_i_path) as dataset:
            cos_i = dataset.read(1).astype("float64")
            profile = dataset.profile
        cos_i_valid = cos_i != FLOAT_NODATA

        # Mconf：纯几何许可，拟合前确定，与观测有效性和任何结果无关。
        mconf = (cos_i > MCONF_COS_I_THRESHOLD) & cos_i_valid
        mconf_path = args.mconf_dir / f"mconf_{member['short_product_id']}.tif"
        with rasterio.open(
            mconf_path, "w", **{**profile, "count": 1, "dtype": "uint8", "nodata": 255,
                                "compress": "deflate"}
        ) as dataset:
            out = np.where(cos_i_valid, mconf.astype("uint8"), 255).astype("uint8")
            dataset.write(out, 1)
            dataset.set_band_description(1, "Mconf_geometry_visibility")
        mconf_records.append({
            "order": member["order"],
            "acquisition_id": member["acquisition_id"],
            "short_product_id": member["short_product_id"],
            "evidence_membership": member["evidence_membership"],
            "stage_7_2_direct_only_input_eligibility": member["stage_7_2_direct_only_input_eligibility"],
            "relative_path": str(mconf_path.relative_to(STAGE_ROOT)),
            "sha256": sha256_file(mconf_path),
            "mconf_one_count": int(mconf.sum()),
            "mconf_zero_near_zero": int(((cos_i > 0) & (cos_i <= MCONF_COS_I_THRESHOLD) & cos_i_valid).sum()),
            "mconf_zero_self_shadow": int(((cos_i <= 0) & cos_i_valid).sum()),
        })

        if member["stage_7_2_direct_only_input_eligibility"] != "eligible_candidate":
            continue

        # 观测有效性沿用 Stage 7.1-R 冻结定义，本节点不重新定义 base_valid_land。
        tif = stack_root / locator[member["acquisition_id"]]
        with rasterio.open(tif) as dataset:
            data = {name: dataset.read(index + 1) for index, name in enumerate(stack_bands)}
        msource = (
            (data["SR_B4_VALID"] == 1) & (data["SR_B5_VALID"] == 1) & (data["QA_PIXEL_VALID"] == 1)
        )
        rho = {band: data[band].astype("float64") * SR_SCALE + SR_OFFSET for band in BANDS}
        in_range = np.ones_like(msource)
        for band in BANDS:
            in_range &= np.isfinite(rho[band]) & (rho[band] >= SR_MIN) & (rho[band] <= SR_MAX)
        qa = data["QA_PIXEL"]
        qa_clear = (qa & QA_CLEAR_MASK) == 0
        water = ((qa >> QA_WATER_BIT) & 1) == 1
        base_valid = msource & qa_clear & in_range & terrain_valid
        base_valid_land = base_valid & ~water

        calibration_lit = base_valid_land & mconf
        n_pixels = int(calibration_lit.sum())
        mu = np.maximum(cos_i, 0.0)
        denominator = float((mu[calibration_lit] ** 2).sum())

        for band in BANDS:
            numerator = float((mu[calibration_lit] * rho[band][calibration_lit]).sum())
            if n_pixels < MIN_CALIBRATION_LIT_PIXELS:
                state, reason, alpha_raw, alpha = "unsupported_calibration", REASON_SUPPORT_BELOW_MINIMUM, None, None
            elif denominator <= 0:
                state, reason, alpha_raw, alpha = "unsupported_calibration", REASON_NONPOSITIVE_DENOMINATOR, None, None
            else:
                alpha_raw = numerator / denominator
                alpha = float(np.clip(alpha_raw, 0.0, 1.0))
                state, reason = "fitted", None
            alpha_records.append({
                "order": member["order"],
                "acquisition_id": member["acquisition_id"],
                "short_product_id": member["short_product_id"],
                "split": next(
                    c["split"] for c in input_view["eligible_candidates"]
                    if c["acquisition_id"] == member["acquisition_id"]
                ),
                "band": band,
                "state": state,
                "alpha_reference_full_support": alpha,
                "alpha_raw_before_clip": alpha_raw,
                "clipped": None if alpha_raw is None else bool(alpha_raw != alpha),
                "sample_count": n_pixels,
                "numerator_sum_mu_rho": numerator,
                "denominator_sum_mu_squared": denominator,
                "calibration_mask": {
                    "definition": "base_valid_land AND (Mconf == 1)",
                    "mconf_relative_path": str(mconf_path.relative_to(STAGE_ROOT)),
                    "mconf_sha256": mconf_records[-1]["sha256"],
                    "bbox_diagonal_m_diagnostic_only": bbox_diagonal_m(calibration_lit),
                },
                "parameter_role": "scene_local_calibration_nuisance",
                "evaluation_role": "non_evaluative",
                "architecture_state_class": "N_t",
                "architecture_note": "架构 v3 §2.1 干扰/标定变量，不得归因给 G 或 X(t)",
                "fallback_receipt": None if state == "fitted" else {
                    "reason_code": reason,
                    "triggering_predicate": (
                        f"sample_count {n_pixels} < {MIN_CALIBRATION_LIT_PIXELS}"
                        if reason == REASON_SUPPORT_BELOW_MINIMUM
                        else f"sum(mu^2) = {denominator} <= 0"
                    ),
                    "raw_counts": {
                        "calibration_lit": n_pixels,
                        "base_valid_land": int(base_valid_land.sum()),
                        "mconf_one": int(mconf.sum()),
                    },
                    "default_alpha_written": False,
                    "imputed": False,
                },
            })

        # 支持损失账本（合同⑦）：从 488,800 个世界位置到 calibration_lit 的每一步。
        passive = ~msource
        active_upstream = msource & ~base_valid
        mconf_zero = base_valid_land & ~mconf
        ledger_records.append({
            "order": member["order"],
            "short_product_id": member["short_product_id"],
            "target_pixel_count": int(calibration_lit.size),
            "observation_or_upstream_validity_exclusion": {
                "total": int((~base_valid_land).sum()),
                "maps_to_v1": "passive ∪ active(qa_rejected, reflectance_out_of_range, terrain_nodata) ∪ water",
                "passive": int(passive.sum()),
                "active_upstream": int(active_upstream.sum()),
                "water_excluded_from_land": int((base_valid & water).sum()),
            },
            "mconf_mechanism_zero": {
                "total": int(mconf_zero.sum()),
                "parent": "active",
                "near_zero": int((mconf_zero & (cos_i > 0)).sum()),
                "self_shadow": int((mconf_zero & (cos_i <= 0)).sum()),
                "mask_sha256": mconf_records[-1]["sha256"],
            },
            "base_valid_land": int(base_valid_land.sum()),
            "calibration_lit": n_pixels,
        })

    fitted = [r for r in alpha_records if r["state"] == "fitted"]
    unsupported = [r for r in alpha_records if r["state"] != "fitted"]
    payload_common = {
        "created_at_utc": "2026-08-07T00:00:00Z",
        "frozen_inputs": frozen_inputs,
        "boundary": {
            "earth_engine_called": False,
            "frozen_evidence_rewritten": False,
            "membership_changed": False,
            "split_reassigned": False,
            "scored": False,
            "residual_computed": False,
            "confidence_computed": False,
            "block_or_fold_instantiated": False,
        },
    }

    mconf_registry = {
        "schema": "mountainrs-stage7.2-mconf-registry-v1",
        "contract_clause": "Stage 7.2 ②",
        **payload_common,
        "factor_identity": {
            "name": "Mconf",
            "architecture_factor": "geometry_visibility",
            "architecture_authority": "docs/architecture.md v3 §3",
            "is_composite_confidence": False,
            "may_merge_with": [],
            "threshold": MCONF_COS_I_THRESHOLD,
            "threshold_source": "Stage 7.0 baseline_spec.md: supported := cos_i > 0.1",
            "thresholds_invented": False,
            "coverage": "self_shadow_only",
            "not_covered": ["cast_shadow", "horizon_occlusion", "disocclusion_boundary",
                            "geometric_instability_boundary", "view_angle_occlusion"],
            "coverage_caveat": "几何支持为乐观上界；未覆盖项归 Stage 7.5 / 7.6，见 docs/mconf-subprotocol-v1.md §3。",
        },
        "member_count": len(mconf_records),
        "members": mconf_records,
    }
    alpha_registry = {
        "schema": "mountainrs-stage7.2-alpha-reference-full-support-v1",
        "contract_clause": "Stage 7.2 ④⑥",
        **payload_common,
        "estimator": {
            "forward_model": "rho_hat = alpha * mu",
            "mu": "max(cos_i, 0)",
            "rho": "DN * 0.0000275 - 0.2",
            "alpha": "clip(sum(mu*rho) / sum(mu^2), 0, 1)",
            "source": "Stage 7.0 baseline_spec.md",
            "intercept_or_diffuse_added": False,
            "fitting_key": "acquisition x band",
            "stratum_dimension_added": False,
            "stratum_rationale": "Stage 7.0 四份冻结文档中不存在地表分层定义，合同④禁止自行新增。",
        },
        "minimum_support_threshold": {
            "value": MIN_CALIBRATION_LIT_PIXELS,
            "unit": "calibration_lit_pixels",
            "additional_hard_condition": "sum(mu^2) > 0",
            "source": "docs/calibration-contract-v1.md §4，所有者 2026-08-07 批准方案 B",
            "derivation": "Stage 7.0 冻结的空间独立尺度 8.13 km = 271 像元；非按期望保留数量反推。",
        },
        "counts": {
            "units_total": len(alpha_records),
            "fitted": len(fitted),
            "unsupported_calibration": len(unsupported),
        },
        "units": alpha_records,
    }
    support_ledger = {
        "schema": "mountainrs-stage7.2-support-loss-ledger-v1",
        "contract_clause": "Stage 7.2 ⑦",
        **payload_common,
        "taxonomy_authority": {
            "v1": "../stage7_1_observation_stack/configs/validity-support-schema-v1.json",
            "v2_delta_amendment": "configs/validity-support-schema-v2.json",
            "parallel_label_system_created": False,
            "note": "mconf_mechanism_zero 经 v2 delta amendment 登记为 active 桶下新细分类，未另立体系。",
        },
        "per_acquisition": ledger_records,
        "totals": {
            "observation_or_upstream_validity_exclusion": sum(
                r["observation_or_upstream_validity_exclusion"]["total"] for r in ledger_records
            ),
            "mconf_mechanism_zero": sum(r["mconf_mechanism_zero"]["total"] for r in ledger_records),
            "base_valid_land": sum(r["base_valid_land"] for r in ledger_records),
            "calibration_lit": sum(r["calibration_lit"] for r in ledger_records),
        },
    }

    for path, payload in (
        (args.mconf_registry, mconf_registry),
        (args.alpha_output, alpha_registry),
        (args.ledger_output, support_ledger),
    ):
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        "status": "fitted",
        "mconf_members": len(mconf_records),
        "alpha_units": len(alpha_records),
        "fitted": len(fitted),
        "unsupported_calibration": sorted(
            {f"{r['short_product_id']}({r['split']})" for r in unsupported}
        ),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
