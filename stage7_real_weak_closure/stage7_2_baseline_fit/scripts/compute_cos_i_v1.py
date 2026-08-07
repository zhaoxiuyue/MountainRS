#!/usr/bin/env python3
"""Stage 7.2 ①：逐景复算并登记全部 21 个 evidence member 的 cos_i。

cos_i 只依赖地形与太阳几何，与 QA、云雪或操作资格无关。因此 3 景
operation_scoped_unsupported 同样算出并登记几何支持——Stage 7.1-R 冻结的
evidence_membership 不因操作资格而失效，几何这一层也不能让它们再消失一次。
这 3 景的 cos_i 只进入几何支持登记，不进入 calibration、不参与 alpha 估计。

公式逐字沿用 Stage 6.5.2-B 既有实现（stage6_5_2b_shadowrisk_local_check.py
的 compute_cos_i），本程序不改公式、不改角度约定、不引入阈值：

    solar_zenith = 90 - sun_elevation
    cos_i = cos(slope)·cos(zenith) + sin(slope)·sin(zenith)·cos(azimuth − aspect)

角度自检是硬门槛：用 catalog 记录的 order 1 太阳几何复算，必须逐像元位级
复现 Stage 6.5 冻结的 cos_i 栅格。复现不了就说明公式、角度约定或地形身份
有出入，此时停机——绝不带着一个对不上的几何往下算。

太阳几何取自 Stage 7.1-R 冻结的 observation-evidence-manifest-v1（其中已按
SUN_AZIMUTH / SUN_ELEVATION 逐景登记），不重新解析 catalog。

不调用 Earth Engine，不认证，不下载，不改任何冻结件。
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

FLOAT_NODATA = np.float32(-9999.0)
EXPECTED_MEMBERS = 21

FORMULA = (
    "solar_zenith_deg = 90 - sun_elevation_deg; "
    "cos_i = cos(slope)*cos(solar_zenith) + sin(slope)*sin(solar_zenith)*cos(sun_azimuth - aspect); "
    "slope/aspect/angles in degrees, converted with numpy.deg2rad / math.radians; "
    "computed in float64, stored as float32 with nodata -9999.0"
)
FORMULA_SOURCE = (
    "stages/stage6_5_real_landsat_observation_stress_test/scripts/"
    "stage6_5_2b_shadowrisk_local_check.py :: compute_cos_i"
)
# Stage 7.0 data_gap_report 已冻结的描述口径。此处只作描述统计，不构成本节点的
# Mconf 或 calibration-lit 判定——那两者要等合同 ②③ 的子协议获批后才成立。
PARTITION_SOURCE = "stage7_real_weak_closure/stage7_0_baseline/docs/data_gap_report.md"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_terrain_component(record: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """读取一个地形分量并按 Stage 7.1-R 登记的哈希验明身份；不符即停。"""
    path = REPO_ROOT / record["relative_path"]
    observed = sha256_file(path)
    if observed != record["sha256"]:
        raise SystemExit(
            f"stop: terrain component hash drifted at {record['relative_path']}\n"
            f"  recorded {record['sha256']}\n  on disk  {observed}"
        )
    with rasterio.open(path) as dataset:
        array = dataset.read(1)
        nodata = dataset.nodata
        profile = dataset.profile
    valid = np.isfinite(array)
    if nodata is not None:
        valid &= array != nodata
    identity = {
        "relative_path": record["relative_path"],
        "sha256": observed,
        "nodata": nodata,
        "valid_count": int(valid.sum()),
    }
    return array.astype("float64"), valid, {"identity": identity, "profile": profile}


def compute_cos_i(
    slope: np.ndarray,
    aspect: np.ndarray,
    terrain_valid: np.ndarray,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
) -> tuple[np.ndarray, np.ndarray]:
    solar_zenith = 90.0 - sun_elevation_deg
    slope_rad = np.deg2rad(slope)
    aspect_rad = np.deg2rad(aspect)
    azimuth_rad = math.radians(sun_azimuth_deg)
    zenith_rad = math.radians(solar_zenith)

    raw = (
        np.cos(slope_rad) * math.cos(zenith_rad)
        + np.sin(slope_rad) * math.sin(zenith_rad) * np.cos(azimuth_rad - aspect_rad)
    )
    valid = terrain_valid & np.isfinite(raw)
    out = np.full(slope.shape, FLOAT_NODATA, dtype="float32")
    out[valid] = raw[valid].astype("float32")
    return out, valid


def verify_against_frozen(
    computed: np.ndarray, valid: np.ndarray, frozen_path: Path
) -> dict[str, Any]:
    """硬门槛：order 1 的复算必须位级复现 Stage 6.5 冻结的 cos_i 栅格。"""
    with rasterio.open(frozen_path) as dataset:
        frozen = dataset.read(1)
        frozen_nodata = dataset.nodata
    frozen_valid = np.isfinite(frozen)
    if frozen_nodata is not None:
        frozen_valid &= frozen != frozen_nodata

    valid_agrees = bool(np.array_equal(valid, frozen_valid))
    identical = bool(np.array_equal(computed, frozen))
    max_abs_diff = float(np.abs(computed[valid] - frozen[valid]).max()) if valid.any() else 0.0
    return {
        "frozen_relative_path": str(frozen_path.relative_to(REPO_ROOT)),
        "frozen_sha256": sha256_file(frozen_path),
        "valid_mask_agrees": valid_agrees,
        "bitwise_identical": identical,
        "max_abs_difference_on_valid": max_abs_diff,
        "passed": valid_agrees and identical,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raster-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="cos_i 登记册落点（JSON）")
    args = parser.parse_args()
    args.raster_dir = args.raster_dir.resolve()
    args.output = args.output.resolve()

    manifest_path = STAGE_7_1 / "evidence/observation-evidence-manifest-v1.json"
    support_audit_path = STAGE_7_1 / "evidence/local-support-audit-v1.json"
    input_view_path = STAGE_7_1 / "evidence/stage-7.2-direct-only-input-view-v1.json"
    frozen_cos_i_path = (
        REPO_ROOT
        / "stages/stage6_5_real_landsat_observation_stress_test/outputs/cos_i_shadowrisk_grid.tif"
    )

    manifest = load_json(manifest_path)
    support_audit = load_json(support_audit_path)
    input_view = load_json(input_view_path)

    members = sorted(manifest["members"], key=lambda m: m["order"])
    if len(members) != EXPECTED_MEMBERS:
        raise SystemExit(f"stop: expected {EXPECTED_MEMBERS} evidence members, got {len(members)}")

    terrain = support_audit["terrain_geometry"]
    slope, slope_valid, slope_meta = read_terrain_component(terrain["slope"])
    aspect, aspect_valid, aspect_meta = read_terrain_component(terrain["aspect"])
    _, dem_valid, dem_meta = read_terrain_component(terrain["dem"])
    terrain_valid = slope_valid & aspect_valid & dem_valid

    eligibility = {
        r["acquisition_id"]: "operation_scoped_unsupported" for r in input_view["unsupported_records"]
    }
    for record in input_view["eligible_candidates"]:
        eligibility[record["acquisition_id"]] = "eligible_candidate"

    args.raster_dir.mkdir(parents=True, exist_ok=True)
    raster_profile = {
        **slope_meta["profile"],
        "count": 1,
        "dtype": "float32",
        "nodata": float(FLOAT_NODATA),
        "compress": "deflate",
    }

    verification = None
    records = []
    for member in members:
        solar = member["solar_geometry"]
        azimuth = solar["sun_azimuth_deg"]
        elevation = solar["sun_elevation_deg"]
        if azimuth is None or elevation is None:
            raise SystemExit(
                f"stop: order {member['order']} has no solar geometry; "
                "缺省值与邻景插值均被合同⑩禁止"
            )
        cos_i, valid = compute_cos_i(slope, aspect, terrain_valid, azimuth, elevation)

        if member["order"] == 1:
            verification = verify_against_frozen(cos_i, valid, frozen_cos_i_path)
            if not verification["passed"]:
                raise SystemExit(
                    "stop: order 1 未能复现 Stage 6.5 冻结的 cos_i 栅格，"
                    "公式、角度约定或地形身份存在出入\n"
                    f"  {json.dumps(verification, ensure_ascii=False)}"
                )

        path = args.raster_dir / f"cos_i_{member['short_product_id']}.tif"
        with rasterio.open(path, "w", **raster_profile) as dataset:
            dataset.write(cos_i, 1)
            dataset.set_band_description(1, "cos_i")
        values = cos_i[valid].astype("float64")

        records.append({
            "order": member["order"],
            "acquisition_id": member["acquisition_id"],
            "short_product_id": member["short_product_id"],
            "system_time_start_utc": member["system_time_start_utc"],
            "evidence_membership": member["evidence_membership"],
            "stage_7_2_direct_only_input_eligibility": eligibility[member["acquisition_id"]],
            "solar_geometry": {
                "sun_azimuth_deg": azimuth,
                "sun_elevation_deg": elevation,
                "solar_zenith_deg": 90.0 - elevation,
                "azimuth_source_field": solar["azimuth_source_field"],
                "elevation_source_field": solar["elevation_source_field"],
            },
            "output": {
                "relative_path": str(path.relative_to(STAGE_ROOT)),
                "sha256": sha256_file(path),
                "dtype": "float32",
                "nodata": float(FLOAT_NODATA),
                "valid_count": int(valid.sum()),
            },
            "cos_i_statistics": {
                "min": float(values.min()),
                "max": float(values.max()),
                "mean": float(values.mean()),
            },
            "descriptive_partition_not_a_support_decision": {
                "shadow_cos_i_le_0": int((values <= 0).sum()),
                "near_zero_0_lt_cos_i_le_0_1": int(((values > 0) & (values <= 0.1)).sum()),
                "lit_cos_i_gt_0_1": int((values > 0.1).sum()),
            },
            "geometry_support_status": "cos_i_computed",
        })

    payload = {
        "schema": "mountainrs-stage7.2-cos-i-registry-v1",
        "created_at_utc": "2026-08-07T00:00:00Z",
        "contract_clause": "Stage 7.2 ①",
        "member_count": len(records),
        "formula": FORMULA,
        "formula_source": FORMULA_SOURCE,
        "formula_modified_by_this_node": False,
        "thresholds_invented": False,
        "inputs": {
            "evidence_manifest": {
                "relative_path": "../stage7_1_observation_stack/evidence/observation-evidence-manifest-v1.json",
                "sha256": sha256_file(manifest_path),
                "manifest_id": manifest["manifest_id"],
                "supplies": ["evidence_membership", "solar_geometry"],
            },
            "direct_only_input_view": {
                "relative_path": "../stage7_1_observation_stack/evidence/stage-7.2-direct-only-input-view-v1.json",
                "sha256": sha256_file(input_view_path),
                "supplies": ["stage_7_2_direct_only_input_eligibility"],
            },
            "terrain_geometry": {
                "dem": dem_meta["identity"],
                "slope": slope_meta["identity"],
                "aspect": aspect_meta["identity"],
                "identity_source": "../stage7_1_observation_stack/evidence/local-support-audit-v1.json",
                "combined_valid_count": int(terrain_valid.sum()),
                "note": "同一冻结地形用于全部 21 景；逐分量按记录哈希验明身份，不符即停。",
            },
        },
        "formula_verification": verification,
        "members": records,
        "coverage": {
            "evidence_members_computed": len(records),
            "eligible_candidate": sum(
                1 for r in records
                if r["stage_7_2_direct_only_input_eligibility"] == "eligible_candidate"
            ),
            "operation_scoped_unsupported": sum(
                1 for r in records
                if r["stage_7_2_direct_only_input_eligibility"] == "operation_scoped_unsupported"
            ),
            "statement": (
                "全部 21 个 evidence member 均已算出 cos_i 并登记几何支持，"
                "满足 Stage 7.1-R 合同⑧。operation_scoped_unsupported 的 3 景只进入几何支持登记，"
                "不进入 calibration、不参与 alpha 估计、不进入任何评分。"
            ),
        },
        "descriptive_partition_boundary": {
            "source": PARTITION_SOURCE,
            "statement": (
                "shadow / near-zero / lit 三分区沿用 Stage 7.0 data_gap_report 的既有描述口径，"
                "只用于描述 cos_i 分布，不构成本节点的 Mconf 或 calibration-lit 判定。"
                "Mconf 须待合同②的子协议获批，calibration-lit 须待合同③的 calibration contract 获批。"
            ),
        },
        "boundary": {
            "earth_engine_called": False,
            "frozen_evidence_rewritten": False,
            "membership_changed": False,
            "split_reassigned": False,
            "mconf_computed": False,
            "calibration_lit_decided": False,
            "alpha_estimated": False,
            "scored": False,
        },
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "status": "computed",
        "members": len(records),
        "formula_verification_passed": verification["passed"] if verification else None,
        "bitwise_identical_to_frozen": verification["bitwise_identical"] if verification else None,
        "eligible_candidate": payload["coverage"]["eligible_candidate"],
        "operation_scoped_unsupported": payload["coverage"]["operation_scoped_unsupported"],
        "registry_sha256": sha256_file(args.output)[:16],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
