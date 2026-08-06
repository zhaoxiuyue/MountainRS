#!/usr/bin/env python3
"""Stage 7.1-R L0 证据语义层构建：evidence universe、支持账本与两个 successor 清单。

本程序把 Stage 7.1 留下的「18 景可用 / 3 景不合格」这一操作结论，重写成
证据语义：21 景全部是不可撤销的证据成员，18/3 只是 direct-only 这一个操作
下的资格投影。缺失与拒绝的原因成为可追溯的证据字段，而不在建模前消失。

产出（全部新建，不覆盖任何既有文件）：
- evidence/observation-support-ledger-v1.json     逐景逐波段与逐世界位置的支持账本
- evidence/observation-evidence-manifest-v1.json  21 景证据清单（旧 stack_manifest 的语义后继）
- evidence/stage-7.2-direct-only-input-view-v1.json  Stage 7.2 的操作视图
- outputs/support/*.tif                            逐世界位置计数层

语义口径全部来自 configs/validity-support-schema-v1.json，本程序不自行定义
任何谓词、阈值或原因标签。前置条件是 evidence-reconciliation-audit-v1 已通过：
地基没验过就不动工。

不调用 Earth Engine，不认证，不下载，不改任何冻结件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPT_DIR.parents[2]

UNIVERSE_ID = "mountainrs-stage7.1-landsat8-c2t1l2-p130r38-2023"
UNIVERSE_VERSION = "v1"
CREATED_AT_UTC = "2026-08-06T00:00:00Z"

SR_SCALE = 0.0000275
SR_OFFSET = -0.2
SR_MIN = -0.05
SR_MAX = 1.0
QA_CLEAR_MASK = 0b111111  # bits 0-5：fill / dilated_cloud / cirrus / cloud / cloud_shadow / snow
QA_WATER_BIT = 7
VALID_BANDS = {"SR_B4": "SR_B4_VALID", "SR_B5": "SR_B5_VALID", "QA_PIXEL": "QA_PIXEL_VALID"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> str:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return sha256_file(path)


def read_terrain(support_audit: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """地形几何有效性沿用 Stage 7.1 的身份与口径：dem / slope / aspect 均 finite 且非 nodata。

    路径与 SHA-256 都从既有 support audit 复用；哈希不符即停，绝不换一份地形来迁就。
    """
    valid = None
    identities = {}
    for name, record in sorted(support_audit["terrain_geometry"].items()):
        path = REPO_ROOT / record["relative_path"]
        observed = sha256_file(path)
        if observed != record["sha256"]:
            raise SystemExit(
                f"stop: terrain component {name} hash drifted\n"
                f"  recorded {record['sha256']}\n  on disk  {observed}"
            )
        with rasterio.open(path) as dataset:
            band = dataset.read(1).astype("float64")
            nodata = dataset.nodata
        finite = np.isfinite(band)
        if nodata is not None:
            finite &= band != nodata
        identities[name] = {
            "relative_path": record["relative_path"],
            "sha256": observed,
            "nodata": nodata,
            "finite_count": int(finite.sum()),
        }
        valid = finite if valid is None else (valid & finite)
    return valid, identities


def evaluate_acquisition(tif: Path, bands: list[str], terrain_valid: np.ndarray) -> dict[str, Any]:
    """按冻结 schema 逐像元求出该景的全部有效性与支持原语，并给出互斥的剥夺归因。"""
    with rasterio.open(tif) as dataset:
        data = {name: dataset.read(index + 1) for index, name in enumerate(bands)}
        profile = dataset.profile

    band_valid = {band: data[valid_band] == 1 for band, valid_band in VALID_BANDS.items()}
    msource = band_valid["SR_B4"] & band_valid["SR_B5"] & band_valid["QA_PIXEL"]

    b4 = data["SR_B4"].astype("float64") * SR_SCALE + SR_OFFSET
    b5 = data["SR_B5"].astype("float64") * SR_SCALE + SR_OFFSET
    in_range = (
        np.isfinite(b4) & np.isfinite(b5)
        & (b4 >= SR_MIN) & (b4 <= SR_MAX) & (b5 >= SR_MIN) & (b5 <= SR_MAX)
    )

    qa = data["QA_PIXEL"]
    qa_clear = (qa & QA_CLEAR_MASK) == 0
    water = ((qa >> QA_WATER_BIT) & 1) == 1

    base_valid = msource & qa_clear & in_range & terrain_valid
    base_valid_land = base_valid & ~water

    # 顶层二分互斥且穷尽 ~base_valid：源观测都不存在时不得再声称是被主动拒绝的。
    passive = ~msource
    active = msource & ~base_valid
    # 细分类可重叠，因此只能各自计数，不能相加当成互斥分解。
    kinds = {
        "source_band_missing": passive,
        "qa_rejected": msource & ~qa_clear,
        "reflectance_out_of_range": msource & ~in_range,
        "terrain_nodata": msource & ~terrain_valid,
    }

    return {
        "profile": profile,
        "masks": {
            "band_valid": band_valid,
            "qa_clear": qa_clear,
            "base_valid_land": base_valid_land,
        },
        "record": {
            "target_pixel_count": int(base_valid_land.size),
            "source_band_validity": {
                band: {
                    "valid_band": VALID_BANDS[band],
                    "source_valid_count": int(mask.sum()),
                    "source_native_missing_count": int((~mask).sum()),
                }
                for band, mask in sorted(band_valid.items())
            },
            "msource_count": int(msource.sum()),
            "qa_clear_support_count": int(qa_clear.sum()),
            "reflectance_in_range_count": int(in_range.sum()),
            "water_count": int(water.sum()),
            "terrain_valid_count": int(terrain_valid.sum()),
            "base_valid_count": int(base_valid.sum()),
            "base_valid_land_count": int(base_valid_land.sum()),
            "deprivation": {
                "top_level_mutually_exclusive_counts": {
                    "passive": int(passive.sum()),
                    "active": int(active.sum()),
                },
                "kind_counts_not_additive": {
                    name: int(mask.sum()) for name, mask in sorted(kinds.items())
                },
                "active_kind_overlap_count": int(
                    (
                        kinds["qa_rejected"].astype("uint8")
                        + kinds["reflectance_out_of_range"].astype("uint8")
                        + kinds["terrain_nodata"].astype("uint8")
                        > 1
                    ).sum()
                ),
                "water_excluded_from_land_count": int((base_valid & water).sum()),
                "partition_check": {
                    "passive_plus_active": int(passive.sum()) + int(active.sum()),
                    "not_base_valid": int((~base_valid).sum()),
                    "exhaustive_and_exclusive": bool(
                        int(passive.sum()) + int(active.sum()) == int((~base_valid).sum())
                        and not bool((passive & active).any())
                    ),
                },
            },
        },
    }


def build_universe(ev: dict[str, Any], reconciliation: dict[str, Any]) -> dict[str, Any]:
    """合同②：版本化 evidence universe。成员不可撤销只在本 version 内成立。"""
    grid = ev["stack_manifest"]["target_grid"]
    scope = ev["catalog"]["query_scope"]
    return {
        "universe_id": UNIVERSE_ID,
        "universe_version": UNIVERSE_VERSION,
        "sensor_product": "Landsat 8 Collection 2 Tier 1 Level 2",
        "collection": scope["collection"],
        "temporal_scope": {
            "label": "2023",
            "start_utc": scope["time_window"]["start_utc"],
            "start_inclusive": scope["time_window"]["start_inclusive"],
            "end_utc": scope["time_window"]["end_utc"],
            "end_inclusive": scope["time_window"]["end_inclusive"],
        },
        "spatial_scope": {
            "wrs_path": scope["wrs_path"],
            "wrs_row": scope["wrs_row"],
            "frozen_roi_grid_id": grid["grid_id"],
            "bounds": grid["bounds"],
            "crs": grid["crs"],
        },
        "grid_identity": {
            "grid_id": grid["grid_id"],
            "crs": grid["crs"],
            "transform": grid["transform"],
            "shape": grid["shape"],
            "pixel_count": grid["pixel_count"],
            "resolution": grid["resolution"],
        },
        "member_count": len(ev["manifest"]["acquisitions"]),
        "enumeration_completeness": scope["candidate_enumeration"],
        "existing_universe_hashes": {
            "acquisition_catalog_sha256": reconciliation["reconciled_evidence"][
                "acquisition_catalog"
            ]["sha256"],
            "export_manifest_v3_sha256": reconciliation["reconciled_evidence"][
                "export_manifest_v3"
            ]["sha256"],
            "stack_manifest_sha256": reconciliation["reconciled_evidence"]["stack_manifest"][
                "sha256"
            ],
        },
        "membership_irrevocability": {
            "scope": "within_this_universe_version_only",
            "statement": (
                "成员资格不因 cloud、QA、source mask、residual、fit、split 或模型结果改变。"
                "更换年份、产品、ROI 或网格必须建立新的 universe version，不得在本 version 内增删成员。"
            ),
            "new_universe_required_on": ["temporal_scope", "sensor_product", "spatial_scope", "grid_identity"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--evidence-manifest", type=Path, required=True)
    parser.add_argument("--input-view", type=Path, required=True)
    parser.add_argument("--raster-dir", type=Path, required=True)
    args = parser.parse_args()
    for name in ("reconciliation", "schema", "ledger", "evidence_manifest", "input_view", "raster_dir"):
        setattr(args, name, getattr(args, name).resolve())

    reconciliation = load_json(args.reconciliation)
    if reconciliation["status"] != "passed_reconciliation":
        raise SystemExit(
            f"stop: reconciliation audit is {reconciliation['status']}; "
            "地基未验过不得动工（合同⑨ fail-closed）"
        )
    schema = load_json(args.schema)

    ev = {
        "catalog": load_json(STAGE_ROOT / "data/raw/acquisition-catalog.json"),
        "manifest": load_json(STAGE_ROOT / "evidence/export-manifest-v3.json"),
        "stack_manifest": load_json(STAGE_ROOT / "evidence/stack_manifest.json"),
        "support_audit": load_json(STAGE_ROOT / "evidence/local-support-audit-v1.json"),
    }
    bands = ev["manifest"]["execution"]["bands"]
    stack_root = STAGE_ROOT / ev["manifest"]["path_policy"]["root_relative_path"]
    catalog_by_id = {c["acquisition_id"]: c for c in ev["catalog"]["candidates"]}
    stack_by_order = {m["order"]: m for m in ev["stack_manifest"]["members"]}

    terrain_valid, terrain_identities = read_terrain(ev["support_audit"])

    members: list[dict[str, Any]] = []
    accumulators: dict[str, np.ndarray] = {}
    profile = None

    for entry in sorted(ev["manifest"]["acquisitions"], key=lambda e: e["order"]):
        order = entry["order"]
        tif = stack_root / entry["target_relative_to_alias"]
        evaluated = evaluate_acquisition(tif, bands, terrain_valid)
        profile = profile or evaluated["profile"]
        masks = evaluated["masks"]

        if not accumulators:
            shape = masks["base_valid_land"].shape
            accumulators = {
                f"source_valid_count_{band}": np.zeros(shape, dtype="uint16")
                for band in VALID_BANDS
            }
            accumulators["qa_clear_support_count"] = np.zeros(shape, dtype="uint16")
            accumulators["base_valid_land_count"] = np.zeros(shape, dtype="uint16")
        for band, mask in masks["band_valid"].items():
            accumulators[f"source_valid_count_{band}"] += mask.astype("uint16")
        accumulators["qa_clear_support_count"] += masks["qa_clear"].astype("uint16")
        accumulators["base_valid_land_count"] += masks["base_valid_land"].astype("uint16")

        catalog_entry = catalog_by_id[entry["acquisition_id"]]
        historical = stack_by_order[order]
        record = evaluated["record"]
        supported = record["base_valid_land_count"] > 0

        members.append({
            "order": order,
            "acquisition_id": entry["acquisition_id"],
            "short_product_id": entry["short_product_id"],
            "system_time_start_utc": entry["system_time_start_utc"],
            "member_relative_to_alias": entry["target_relative_to_alias"],
            "member_sha256": sha256_file(tif),
            "member_byte_size": tif.stat().st_size,
            "evidence_membership": "included",
            "acquisition_status": "acquired",
            "observation_opportunity": {
                "target_roi_footprint_coverage": catalog_entry["target_roi_footprint_coverage"],
                "counts_toward_denominator": True,
                "note": "观测机会只要求 acquisition 在冻结 footprint 内发生，不要求形成有效支持。",
            },
            "solar_geometry": {
                "sun_azimuth_deg": catalog_entry["sun_azimuth_deg"],
                "sun_elevation_deg": catalog_entry["sun_elevation_deg"],
                "azimuth_source_field": catalog_entry["sun_azimuth_source_field"],
                "elevation_source_field": catalog_entry["sun_elevation_source_field"],
                "transcribed_not_computed": True,
            },
            "geometry_support_status": "not_computed",
            "target_surface_support_status": (
                "supported_somewhere" if supported else "zero_base_valid_land"
            ),
            "provenance_class": "support_ready" if supported else "unsupported",
            "historical_operation_eligibility": historical["stack_eligible"],
            "stage_7_2_direct_only_input_eligibility": (
                "eligible_candidate" if supported else "operation_scoped_unsupported"
            ),
            "unsupported_reason": None if supported else "zero_base_valid_land",
            "split": historical["split"],
            **{k: v for k, v in record.items() if k != "profile"},
        })

    # 逐世界位置计数层：观测机会是常数场，不写栅格，避免伪装成有空间变化的独立层。
    args.raster_dir.mkdir(parents=True, exist_ok=True)
    raster_profile = {
        **profile,
        "count": 1,
        "dtype": "uint16",
        "compress": "deflate",
        "nodata": None,
    }
    raster_records = {}
    for name, array in sorted(accumulators.items()):
        path = args.raster_dir / f"{name}.tif"
        with rasterio.open(path, "w", **raster_profile) as dataset:
            dataset.write(array, 1)
            dataset.set_band_description(1, name)
        raster_records[name] = {
            "relative_path": str(path.relative_to(STAGE_ROOT)),
            "sha256": sha256_file(path),
            "dtype": "uint16",
            "granularity": "world_position",
            "value_range": [int(array.min()), int(array.max())],
        }

    support_gap = accumulators["base_valid_land_count"] == 0
    universe = build_universe(ev, reconciliation)
    universe_size = universe["member_count"]

    passive_total = sum(m["deprivation"]["top_level_mutually_exclusive_counts"]["passive"] for m in members)
    active_total = sum(m["deprivation"]["top_level_mutually_exclusive_counts"]["active"] for m in members)
    partition_ok = all(m["deprivation"]["partition_check"]["exhaustive_and_exclusive"] for m in members)
    if not partition_ok:
        raise SystemExit("stop: passive/active 顶层二分未能对 ~base_valid 形成互斥且穷尽的划分")

    ledger = {
        "schema": "mountainrs-stage7.1r-observation-support-ledger-v1",
        "created_at_utc": CREATED_AT_UTC,
        "semantics_schema": {
            "relative_path": str(args.schema.relative_to(STAGE_ROOT)),
            "sha256": sha256_file(args.schema),
            "schema_id": schema["schema"],
        },
        "reconciliation_audit": {
            "relative_path": str(args.reconciliation.relative_to(STAGE_ROOT)),
            "sha256": sha256_file(args.reconciliation),
            "status": reconciliation["status"],
        },
        "universe": {
            "universe_id": universe["universe_id"],
            "universe_version": universe["universe_version"],
            "member_count": universe_size,
        },
        "terrain_geometry": terrain_identities,
        "per_acquisition": members,
        "per_world_position": {
            "observation_opportunity_count": {
                "granularity": "world_position",
                "constant_field": True,
                "value": universe_size,
                "justification": (
                    "21 景 target_roi_footprint_coverage 均为 1.0（full cover），"
                    "故冻结 ROI 上每个世界位置的观测机会恒等于成员数。该值由 full-cover 事实导出，"
                    "不是逐像元重算结果，因此不写栅格层。"
                ),
                "evidence": "evidence/evidence-reconciliation-audit-v1.json check C10",
            },
            "count_rasters": raster_records,
            "support_gap": {
                "definition": "base_valid_land_count == 0 的世界位置：21 次观测机会中一次也没有形成目标地表支持",
                "pixel_count": int(support_gap.sum()),
                "share_of_roi": round(float(support_gap.mean()), 6),
                "raster_reference": raster_records["base_valid_land_count"]["relative_path"],
                "note": "support gap 不是地表状态结论，也不是低置信度；它是缺少支持这一事实本身。",
            },
            "base_valid_land_count_range": [
                int(accumulators["base_valid_land_count"].min()),
                int(accumulators["base_valid_land_count"].max()),
            ],
            "pixels_with_full_support": int(
                (accumulators["base_valid_land_count"] == universe_size).sum()
            ),
        },
        "deprivation_totals": {
            "authority": "configs/validity-support-schema-v1.json deprivation_taxonomy",
            "top_level_mutually_exclusive": {"passive": passive_total, "active": active_total},
            "additive": True,
            "kind_totals_not_additive": {
                name: sum(m["deprivation"]["kind_counts_not_additive"][name] for m in members)
                for name in ("source_band_missing", "qa_rejected", "reflectance_out_of_range", "terrain_nodata")
            },
            "kind_totals_additive": False,
            "overlap_evidence": {
                "active_kind_overlap_pixel_events": sum(
                    m["deprivation"]["active_kind_overlap_count"] for m in members
                ),
                "note": (
                    "细分类可在同一像元重叠，因此其计数不可相加为互斥分解；"
                    "只有 passive / active 两个顶层桶可以相加。"
                ),
            },
            "water_excluded_from_land_total": sum(
                m["deprivation"]["water_excluded_from_land_count"] for m in members
            ),
            "reporting_rule": "passive 与 active 分别报告，禁止合并为单一低支持总数（架构 v3 §3 与未决问题 I）。",
        },
        "boundary": {
            "earth_engine_called": False,
            "frozen_evidence_rewritten": False,
            "membership_changed": False,
            "split_reassigned": False,
            "cos_i_computed": False,
            "confidence_computed": False,
        },
    }
    ledger_sha = write_json(args.ledger, ledger)

    eligible = [m for m in members if m["stage_7_2_direct_only_input_eligibility"] == "eligible_candidate"]
    unsupported = [m for m in members if m["stage_7_2_direct_only_input_eligibility"] != "eligible_candidate"]

    # acquisition 级剥夺归因由实测计数导出，不是断言：
    # 主导 active 细分类必须真的占优，且 qa_rejected 必须以 qa_clear = 0 为证据，否则停机。
    for member in unsupported:
        kind_counts = member["deprivation"]["kind_counts_not_additive"]
        active_kinds = {k: v for k, v in kind_counts.items() if k != "source_band_missing"}
        dominant = max(active_kinds, key=lambda name: active_kinds[name])
        if member["deprivation"]["top_level_mutually_exclusive_counts"]["active"] == 0:
            raise SystemExit(
                f"stop: {member['short_product_id']} 无支持但 active 剥夺计数为 0，无法归因"
            )
        if dominant == "qa_rejected" and member["qa_clear_support_count"] != 0:
            raise SystemExit(
                f"stop: {member['short_product_id']} 归因为 qa_rejected 但 "
                f"qa_clear_support_count = {member['qa_clear_support_count']} ≠ 0"
            )
        member["_deprivation_kind"] = "active"
        member["_deprivation_detail"] = dominant

    evidence_manifest = {
        "schema": "mountainrs-stage7.1r-observation-evidence-manifest-v1",
        "manifest_id": "observation-evidence-manifest-v1",
        "created_at_utc": CREATED_AT_UTC,
        "evidence_universe": universe,
        "semantics_schema": ledger["semantics_schema"],
        "support_ledger": {
            "relative_path": str(args.ledger.relative_to(STAGE_ROOT)),
            "sha256": ledger_sha,
        },
        "provenance": {
            "reconciliation_audit": ledger["reconciliation_audit"],
            "frozen_inputs": schema["frozen_inputs"],
            "terrain_geometry": terrain_identities,
        },
        "supersession": {
            "semantic_successor_of": "mountainrs-stage7.1-stack-manifest-v1",
            "predecessor_relative_path": "evidence/stack_manifest.json",
            "predecessor_sha256": reconciliation["reconciled_evidence"]["stack_manifest"]["sha256"],
            "supersession_scope": "validity_semantics_and_support_projection",
            "predecessor_edited": False,
            "statement": (
                "本清单只在有效性语义与支持投影这一范围内后继旧 stack_manifest："
                "旧清单的 stack_eligible 从此读作历史操作资格映射，成员资格改由 evidence_membership 承担。"
                "旧清单的成员身份、网格、计数、split 算术与文件字节一律不变，也不得被本清单覆盖或改名。"
            ),
        },
        "members": [
            {
                key: member[key]
                for key in (
                    "order", "acquisition_id", "short_product_id", "system_time_start_utc",
                    "member_relative_to_alias", "member_sha256", "member_byte_size",
                    "evidence_membership", "acquisition_status", "observation_opportunity",
                    "solar_geometry", "geometry_support_status", "source_band_validity",
                    "qa_clear_support_count", "base_valid_land_count",
                    "target_surface_support_status", "provenance_class",
                    "historical_operation_eligibility",
                    "stage_7_2_direct_only_input_eligibility", "unsupported_reason",
                    "deprivation",
                )
            }
            for member in members
        ],
        "counts": {
            "member_count": universe_size,
            "evidence_membership_included": sum(
                1 for m in members if m["evidence_membership"] == "included"
            ),
            "target_surface_supported_somewhere": len(eligible),
            "target_surface_zero_base_valid_land": len(unsupported),
        },
        "confidence_projection_status": "not_computed",
        "confidence_boundary": schema["confidence_boundary"],
        "training_semantics": schema["training_semantics"],
        "mask_identities": schema["mask_identities"],
        "state_boundary": {
            "membership_revocable": False,
            "operation_level_unsupported_may_not_revoke_membership": True,
            "model_eligible": "not_adjudicated_stage_7_2",
            "geometry_support_owner": "stage_7_2",
        },
        "boundary": ledger["boundary"],
    }
    evidence_manifest_sha = write_json(args.evidence_manifest, evidence_manifest)

    input_view = {
        "schema": "mountainrs-stage7.1r-stage-7.2-direct-only-input-view-v1",
        "view_id": "stage-7.2-direct-only-input-view-v1",
        "created_at_utc": CREATED_AT_UTC,
        "source_evidence_manifest": {
            "manifest_id": evidence_manifest["manifest_id"],
            "relative_path": str(args.evidence_manifest.relative_to(STAGE_ROOT)),
            "sha256": evidence_manifest_sha,
            "universe_id": universe["universe_id"],
            "universe_version": universe["universe_version"],
        },
        "operation_scope": "stage_7_2_direct_only",
        "frozen_predicate": {
            "source": "docs/selection-protocol.md §3 与 configs/validity-support-schema-v1.json",
            "predicate": "target_surface_support_status = supported_somewhere（即 base_valid_land_count > 0）",
            "thresholds_invented": False,
            "re_adjudicated_by_this_node": False,
        },
        "counts": {
            "universe": universe_size,
            "eligible_candidate": len(eligible),
            "operation_scoped_unsupported": len(unsupported),
        },
        "eligible_candidates": [
            {
                "order": m["order"],
                "acquisition_id": m["acquisition_id"],
                "short_product_id": m["short_product_id"],
                "system_time_start_utc": m["system_time_start_utc"],
                "split": m["split"],
                "base_valid_land_count": m["base_valid_land_count"],
            }
            for m in eligible
        ],
        "unsupported_records": [
            {
                "order": m["order"],
                "acquisition_id": m["acquisition_id"],
                "short_product_id": m["short_product_id"],
                "system_time_start_utc": m["system_time_start_utc"],
                "evidence_membership": m["evidence_membership"],
                "reason": m["unsupported_reason"],
                "deprivation_kind": m["_deprivation_kind"],
                "deprivation_detail": m["_deprivation_detail"],
                "qa_clear_support_count": m["qa_clear_support_count"],
                "base_valid_land_count": m["base_valid_land_count"],
                "provenance_class": "unsupported",
                "scope_statement": (
                    "只表示当前冻结 ROI、目标地表支持谓词与 direct-only 操作下无直接支持；"
                    "不断言整景对其他 ROI 或其他任务无价值，也不撤销证据成员资格。"
                ),
            }
            for m in unsupported
        ],
        "split": {
            "split_scope": "stage_7_2_direct_only_eligible_subset",
            "counts": {
                name: sum(1 for m in eligible if m["split"] == name)
                for name in ("train", "validation", "test")
            },
            "reassigned_by_this_node": False,
            "members_outside_split_remain_evidence_members": len(unsupported),
            "rule_source": "docs/selection-protocol.md §5（本节点只复读，不重算分配）",
        },
        "handoff_to_stage_7_2": {
            "geometry_support_evaluation_scope": "all_21_acquisitions",
            "geometry_support_inputs_ready": True,
            "geometry_support_status": "not_computed",
            "calibration_gate_population": len(eligible),
            "not_fitted": len(unsupported),
            "masks_delivered_here": ["Msource", "Mqa"],
            "masks_owned_by_stage_7_2": ["Mgeom_support", "Mloss_support"],
            "note": (
                "全部 21 景都进入逐景几何支持评估范围：能算则登记 cos_i / geometry support，"
                "不能算则产出有原因的 typed unsupported。18 景进入 direct-only calibration Gate，3 景不拟合。"
            ),
        },
        "state_boundary": {
            "changes_evidence_membership": False,
            "training_semantics": schema["training_semantics"],
        },
        "boundary": ledger["boundary"],
    }
    input_view_sha = write_json(args.input_view, input_view)

    print(json.dumps({
        "status": "built",
        "universe": universe_size,
        "membership_included": evidence_manifest["counts"]["evidence_membership_included"],
        "eligible_candidate": len(eligible),
        "operation_scoped_unsupported": len(unsupported),
        "support_gap_pixels": ledger["per_world_position"]["support_gap"]["pixel_count"],
        "deprivation_passive": passive_total,
        "deprivation_active": active_total,
        "ledger_sha256": ledger_sha[:16],
        "evidence_manifest_sha256": evidence_manifest_sha[:16],
        "input_view_sha256": input_view_sha[:16],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
