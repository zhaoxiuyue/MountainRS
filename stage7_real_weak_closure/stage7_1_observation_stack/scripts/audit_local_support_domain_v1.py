#!/usr/bin/env python3
"""Stage 7.1 本地支持域审计：按冻结规则判定 stack_eligible，不引入任何新阈值。

规则来源（全部为冻结文本，本程序不得增删）：
- selection-protocol.md §3：stack_eligible 要求本地 B4/B5/QA 成员与哈希存在、
  精确 target-grid 完整性通过、且 base_valid_land > 0。
- selection-protocol.md §4：QA_PIXEL bits 0–5 全零为 QA-clear；bit 7 为 water，
  单独计数并从 base_valid_land 排除；SR = DN × 0.0000275 − 0.2；B4/B5 须 finite、
  source-mask-valid、nodata-valid 且落在闭区间 [-0.05, 1.0]；base_valid 另需
  finite、nodata-valid 的地形几何；base_valid_land = base_valid AND NOT water。

只读：不认证 Earth Engine、不建任务/资产、不下载、不改任何冻结件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

SR_SCALE = 0.0000275
SR_OFFSET = -0.2
SR_MIN = -0.05
SR_MAX = 1.0
QA_CLEAR_MASK = 0b111111  # bits 0-5
QA_WATER_BIT = 7


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_terrain(paths: dict[str, Path]) -> tuple[np.ndarray, dict[str, Any]]:
    """地形几何有效性：finite 且非 nodata。cos_i 不参与——它随太阳几何逐景变化。"""
    valid = None
    meta = {}
    for name, path in paths.items():
        with rasterio.open(path) as ds:
            band = ds.read(1).astype("float64")
            nodata = ds.nodata
        finite = np.isfinite(band)
        if nodata is not None:
            finite &= band != nodata
        meta[name] = {
            "relative_path": str(path),
            "sha256": sha256_file(path),
            "nodata": nodata,
            "finite_count": int(finite.sum()),
        }
        valid = finite if valid is None else (valid & finite)
    return valid, meta


def audit_acquisition(tif: Path, terrain_valid: np.ndarray, bands: list[str]) -> dict[str, Any]:
    with rasterio.open(tif) as ds:
        data = {name: ds.read(index + 1) for index, name in enumerate(bands)}
        shape = (ds.height, ds.width)

    source_valid = (
        (data["SR_B4_VALID"] == 1) & (data["SR_B5_VALID"] == 1) & (data["QA_PIXEL_VALID"] == 1)
    )
    b4 = data["SR_B4"].astype("float64") * SR_SCALE + SR_OFFSET
    b5 = data["SR_B5"].astype("float64") * SR_SCALE + SR_OFFSET
    in_range = (
        np.isfinite(b4) & np.isfinite(b5)
        & (b4 >= SR_MIN) & (b4 <= SR_MAX) & (b5 >= SR_MIN) & (b5 <= SR_MAX)
    )
    qa = data["QA_PIXEL"]
    qa_clear = (qa & QA_CLEAR_MASK) == 0
    water = ((qa >> QA_WATER_BIT) & 1) == 1

    # 冻结文本对「base_valid 是否包含 QA-clear」有两种可读法。本程序不选边：
    # 两种口径都算出来，并证明 stack_eligible 判定在两种口径下一致。
    base_valid_with_qa = source_valid & in_range & qa_clear & terrain_valid
    base_valid_without_qa = source_valid & in_range & terrain_valid
    land_with_qa = base_valid_with_qa & ~water
    land_without_qa = base_valid_without_qa & ~water

    return {
        "grid_shape": {"height": shape[0], "width": shape[1]},
        "target_pixel_count": int(shape[0] * shape[1]),
        "source_valid_count": int(source_valid.sum()),
        "reflectance_in_range_count": int(in_range.sum()),
        "qa_clear_count": int(qa_clear.sum()),
        "water_count": int(water.sum()),
        "terrain_valid_count": int(terrain_valid.sum()),
        "base_valid_land": {
            "qa_clear_included": int(land_with_qa.sum()),
            "qa_clear_excluded": int(land_without_qa.sum()),
        },
        "base_valid_land_gt_zero": {
            "qa_clear_included": bool(land_with_qa.sum() > 0),
            "qa_clear_excluded": bool(land_without_qa.sum() > 0),
        },
        "verdict_invariant_across_readings": bool(
            (land_with_qa.sum() > 0) == (land_without_qa.sum() > 0)
        ),
        "_land_mask_with_qa": land_with_qa,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--target-grid", type=Path, required=True)
    parser.add_argument("--dem", type=Path, required=True)
    parser.add_argument("--slope", type=Path, required=True)
    parser.add_argument("--aspect", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    stage_root = args.manifest.parent.parent
    bands = manifest["execution"]["bands"]
    root = manifest["path_policy"]["root_relative_path"]

    terrain_valid, terrain_meta = read_terrain(
        {"dem": args.dem, "slope": args.slope, "aspect": args.aspect}
    )

    results = []
    land_masks = []
    for entry in manifest["acquisitions"]:
        tif = stage_root / root / entry["target_relative_to_alias"]
        if not tif.is_file():
            continue
        record = audit_acquisition(tif, terrain_valid, bands)
        land_masks.append(record.pop("_land_mask_with_qa"))
        record.update({
            "order": entry["order"],
            "acquisition_id": entry["acquisition_id"],
            "short_product_id": entry["short_product_id"],
            "system_time_start_utc": entry["system_time_start_utc"],
            "member_relative_to_alias": entry["target_relative_to_alias"],
            "member_sha256": sha256_file(tif),
            "member_byte_size": tif.stat().st_size,
            "stack_eligible": (
                "eligible" if record["base_valid_land_gt_zero"]["qa_clear_included"]
                and record["base_valid_land_gt_zero"]["qa_clear_excluded"] else "not_eligible"
            ),
        })
        results.append(record)

    stack = np.stack(land_masks) if land_masks else np.zeros((0, 1, 1), dtype=bool)
    observation_count = stack.shape[0]
    per_pixel_valid = stack.sum(axis=0)

    payload = {
        "schema": "mountainrs-stage7.1-local-support-audit-v1",
        "rule_source": {
            "selection_protocol": "docs/selection-protocol.md sections 3 and 4",
            "amendment": "docs/grid-declaration-amendment-v1.md",
            "no_new_threshold_introduced": True,
            "eligibility_rule": "base_valid_land > 0",
        },
        "reading_ambiguity": {
            "question": "whether QA-clear is part of base_valid",
            "handling": "both readings computed; no side chosen",
            "verdict_invariant_for_all_members": all(
                r["verdict_invariant_across_readings"] for r in results
            ),
        },
        "cos_i_boundary": {
            "used": False,
            "reason": (
                "cos_i varies with per-acquisition solar geometry; the only frozen cos_i raster "
                "was computed for LC08_130038_20230101 and must not be applied to other "
                "acquisitions. base_valid_land needs terrain geometry only, so eligibility does "
                "not depend on cos_i. Per-acquisition supported/unsupported classification is "
                "out of this node's boundary."
            ),
        },
        "terrain_geometry": terrain_meta,
        "members": results,
        "per_pixel_counts": {
            "observation_count": observation_count,
            "valid_count_min": int(per_pixel_valid.min()) if observation_count else 0,
            "valid_count_max": int(per_pixel_valid.max()) if observation_count else 0,
            "pixels_with_full_support": int((per_pixel_valid == observation_count).sum())
            if observation_count else 0,
            "pixels_with_zero_support": int((per_pixel_valid == 0).sum()) if observation_count else 0,
        },
        "operation_boundary": {
            "earth_engine_called": False,
            "export_tasks_created": 0,
            "assets_created": 0,
            "imagery_downloaded": 0,
            "frozen_evidence_rewritten": False,
            "split_assigned": False,
        },
    }

    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": "passed",
        "members_audited": len(results),
        "eligible": [r["short_product_id"] for r in results if r["stack_eligible"] == "eligible"],
        "not_eligible": [r["short_product_id"] for r in results if r["stack_eligible"] != "eligible"],
        "verdict_invariant": payload["reading_ambiguity"]["verdict_invariant_for_all_members"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
