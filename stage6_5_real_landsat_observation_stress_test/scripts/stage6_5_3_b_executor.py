#!/usr/bin/env python3
"""Deterministic Stage 6.5.3-B First Action preflight only.

This executor recomputes canonical masks, validates grids and estimates a
spatial-isolation design.  It intentionally contains no model fitting,
holdout scoring, residual computation, risk-coverage curve, or final
mechanism comparison.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "stage6_5_real_landsat_observation_stress_test/configs/stage6_5_3_b.yaml"
MASK_NODATA = np.uint8(255)


class PreflightError(RuntimeError):
    """Raised for an input or declared-output invariant violation."""


@dataclass
class Raster:
    path: Path
    data: np.ndarray
    profile: dict[str, Any]
    crs: Any
    transform: Any
    nodata: Any
    shape: tuple[int, int]
    resolution: tuple[float, float]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def relative_path(root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PreflightError(f"配置路径必须是 root-relative 且不得逃逸：{raw}")
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise PreflightError(f"配置路径逃逸 Workspace：{raw}")
    return resolved


def relative_text(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def load_config(path: Path) -> dict[str, Any]:
    # JSON is a YAML 1.2 subset.  Keeping this formal .yaml file JSON-compatible
    # avoids a non-declared PyYAML dependency in the local preflight executor.
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PreflightError(f"config 不是 JSON-compatible YAML：{exc}") from exc
    if parsed.get("schema") != "mountainrs-stage-6-5-3-b-preflight-v1":
        raise PreflightError("不支持的 Stage 6.5.3-B config schema")
    if parsed.get("execution", {}).get("mode") != "deterministic_preflight_only":
        raise PreflightError("executor 只接受 deterministic_preflight_only")
    forbidden = parsed.get("execution", {}).get("forbidden_operations", [])
    if "score a holdout" not in forbidden or "fit hard_mask, soft_weight, or bounded_scene_constant_diffuse" not in forbidden:
        raise PreflightError("config 未冻结本轮禁止的正式实验操作")
    return parsed


def read_raster(path: Path) -> Raster:
    if not path.is_file():
        raise PreflightError(f"声明输入不存在：{path.name}")
    with rasterio.open(path) as source:
        if source.count != 1:
            raise PreflightError(f"只支持单波段输入：{path.name}")
        return Raster(
            path=path,
            data=source.read(1),
            profile=source.profile.copy(),
            crs=source.crs,
            transform=source.transform,
            nodata=source.nodata,
            shape=(source.height, source.width),
            resolution=tuple(float(value) for value in source.res),
        )


def read_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PreflightError(f"声明输入不存在：{path.name}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise PreflightError(f"metadata 为空：{path.name}")
    record = rows[0]
    fields = ("image_id", "date", "SUN_AZIMUTH", "SUN_ELEVATION", "VALID_PIXEL_COVERAGE")
    return {
        "relative_path": relative_text(PROJECT_ROOT, path),
        "row_count": len(rows),
        "selected_fields": {field: record.get(field) for field in fields},
    }


def nodata_valid(array: np.ndarray, nodata: Any) -> np.ndarray:
    if np.issubdtype(array.dtype, np.floating):
        valid = np.isfinite(array)
    else:
        valid = np.ones(array.shape, dtype=bool)
    if nodata is not None:
        if isinstance(nodata, float) and math.isnan(nodata):
            valid &= ~np.isnan(array)
        else:
            valid &= array != nodata
    return valid


def grid_summary(raster: Raster) -> dict[str, Any]:
    return {
        "shape": list(raster.shape),
        "crs": raster.crs.to_string() if raster.crs else None,
        "is_projected": bool(raster.crs and raster.crs.is_projected),
        "resolution": list(raster.resolution),
        "transform": [float(value) for value in raster.transform[:6]],
        "nodata": raster.nodata,
        "dtype": str(raster.data.dtype),
    }


def same_grid(master: Raster, candidate: Raster) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if master.crs != candidate.crs:
        failures.append("CRS")
    if master.shape != candidate.shape:
        failures.append("shape")
    if not np.allclose(tuple(master.transform[:6]), tuple(candidate.transform[:6]), rtol=0, atol=1e-9):
        failures.append("transform")
    return not failures, failures


def qa_masks(qa: Raster, clear_bits: dict[str, str], water_bit: int) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    valid = nodata_valid(qa.data, qa.nodata)
    qa_values = qa.data.astype(np.uint32, copy=False)
    clear = valid.copy()
    flagged: dict[str, int] = {}
    for raw_bit, label in clear_bits.items():
        bit = int(raw_bit)
        set_mask = valid & ((qa_values & (1 << bit)) != 0)
        flagged[label] = int(set_mask.sum())
        clear &= ~set_mask
    water = valid & ((qa_values & (1 << water_bit)) != 0)
    return clear, water, flagged


def count_ratio(mask: np.ndarray, denominator: int) -> dict[str, Any]:
    count = int(mask.sum())
    return {"count": count, "ratio": (count / denominator if denominator else None)}


def comparison_counts(reference: np.ndarray, candidate: np.ndarray, support: np.ndarray) -> dict[str, Any]:
    supported = int(support.sum())
    if supported == 0:
        return {"support_count": 0, "agreement_count": 0, "symmetric_difference_count": 0, "symmetric_difference_ratio": None}
    difference = (reference != candidate) & support
    agreement = (reference == candidate) & support
    return {
        "support_count": supported,
        "agreement_count": int(agreement.sum()),
        "symmetric_difference_count": int(difference.sum()),
        "symmetric_difference_ratio": float(difference.sum() / supported),
        "reference_only_count": int((reference & ~candidate & support).sum()),
        "canonical_only_count": int((candidate & ~reference & support).sum()),
    }


def prior_mask(path: Path, master: Raster, canonical: np.ndarray, support: np.ndarray) -> dict[str, Any]:
    prior = read_raster(path)
    matches, failures = same_grid(master, prior)
    result: dict[str, Any] = {"relative_path": relative_text(PROJECT_ROOT, path), "grid_matches": matches, "grid_failures": failures}
    if not matches:
        return result
    valid = nodata_valid(prior.data, prior.nodata)
    value = prior.data == 1
    result["comparison"] = comparison_counts(value, canonical, support & valid)
    return result


def prior_confidence(path: Path, master: Raster, cos_i: np.ndarray, base_valid: np.ndarray, k: float) -> dict[str, Any]:
    prior = read_raster(path)
    matches, failures = same_grid(master, prior)
    result: dict[str, Any] = {"relative_path": relative_text(PROJECT_ROOT, path), "grid_matches": matches, "grid_failures": failures}
    if not matches:
        return result
    valid = nodata_valid(prior.data, prior.nodata) & base_valid
    if not valid.any():
        result["comparison"] = {"support_count": 0, "median_absolute_difference": None, "p95_absolute_difference": None}
        return result
    logits = np.clip(k * (cos_i.astype("float64") - 0.1), -700, 700)
    expected = 1.0 / (1.0 + np.exp(-logits))
    difference = np.abs(prior.data.astype("float64") - expected)
    result["comparison"] = {
        "support_count": int(valid.sum()),
        "median_absolute_difference": float(np.median(difference[valid])),
        "p95_absolute_difference": float(np.percentile(difference[valid], 95)),
        "interpretation": "仅核对既有 confidence 与冻结 sigmoid 公式；不拟合、校准或将其解释为正确概率。",
    }
    return result


def scene_seed(seed: int, scene: str, field: str) -> int:
    text = f"{seed}:{scene}:{field}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "big")


def semivariogram(values: np.ndarray, mask: np.ndarray, transform: Any, config: dict[str, Any], seed: int) -> dict[str, Any]:
    rows, cols = np.nonzero(mask)
    total = len(rows)
    sample_min = int(config["sample_min_points"])
    if total < sample_min:
        return {"reliable": False, "reason": f"base-valid land 像元 {total} 少于 {sample_min}", "land_pixel_count": total}

    rng = np.random.default_rng(seed)
    sample_count = min(total, int(config["sample_max_points"]))
    if sample_count < total:
        chosen = rng.choice(total, size=sample_count, replace=False)
        rows, cols = rows[chosen], cols[chosen]
    sampled_values = values[rows, cols].astype("float64", copy=False)
    x = transform.c + transform.a * (cols + 0.5) + transform.b * (rows + 0.5)
    y = transform.f + transform.d * (cols + 0.5) + transform.e * (rows + 0.5)
    pixel_x = math.hypot(transform.a, transform.d)
    pixel_y = math.hypot(transform.b, transform.e)
    if pixel_x <= 0 or pixel_y <= 0:
        return {"reliable": False, "reason": "transform 未提供正的线性像元尺度", "land_pixel_count": total}
    shorter_extent = min(pixel_x * mask.shape[1], pixel_y * mask.shape[0])
    max_lag = shorter_extent * float(config["maximum_lag_fraction_of_shorter_scene_extent"])
    if not np.isfinite(max_lag) or max_lag <= 0:
        return {"reliable": False, "reason": "maximum lag 不可解释", "land_pixel_count": total}

    bins = int(config["lag_bin_count"])
    edges = np.linspace(0.0, max_lag, bins + 1)
    pair_counts = np.zeros(bins, dtype=np.int64)
    distance_sums = np.zeros(bins, dtype="float64")
    semivariance_sums = np.zeros(bins, dtype="float64")
    remaining = int(config["candidate_pair_samples"])
    while remaining > 0:
        take = min(remaining, 250000)
        left = rng.integers(0, sample_count, size=take)
        right = rng.integers(0, sample_count, size=take)
        dx = x[left] - x[right]
        dy = y[left] - y[right]
        distance = np.hypot(dx, dy)
        keep = (left != right) & (distance > 0) & (distance <= max_lag)
        if keep.any():
            distance = distance[keep]
            difference = sampled_values[left[keep]] - sampled_values[right[keep]]
            index = np.searchsorted(edges, distance, side="right") - 1
            index = np.clip(index, 0, bins - 1)
            pair_counts += np.bincount(index, minlength=bins)
            distance_sums += np.bincount(index, weights=distance, minlength=bins)
            semivariance_sums += np.bincount(index, weights=0.5 * difference * difference, minlength=bins)
        remaining -= take

    min_pairs = int(config["minimum_pairs_per_lag"])
    populated = pair_counts >= min_pairs
    mean_distance = np.full(bins, np.nan, dtype="float64")
    gamma = np.full(bins, np.nan, dtype="float64")
    available = pair_counts > 0
    mean_distance[available] = distance_sums[available] / pair_counts[available]
    gamma[available] = semivariance_sums[available] / pair_counts[available]
    diagnostics = {
        "land_pixel_count": total,
        "sample_point_count": sample_count,
        "candidate_pair_samples": int(config["candidate_pair_samples"]),
        "accepted_pair_count": int(pair_counts.sum()),
        "maximum_lag_m": float(max_lag),
        "lag_bins": [
            {
                "lag_lower_m": float(edges[index]),
                "lag_upper_m": float(edges[index + 1]),
                "mean_lag_m": (float(mean_distance[index]) if np.isfinite(mean_distance[index]) else None),
                "pair_count": int(pair_counts[index]),
                "semivariance": (float(gamma[index]) if np.isfinite(gamma[index]) else None),
                "sufficient_pairs": bool(populated[index]),
            }
            for index in range(bins)
        ],
    }
    if int(populated.sum()) < int(config["minimum_populated_lag_bins"]):
        diagnostics.update({"reliable": False, "reason": "有效 lag bins 不足"})
        return diagnostics
    tail_count = int(config["sill_tail_lag_bins"])
    tail = np.arange(bins - tail_count, bins)
    if not populated[tail].all() or not np.isfinite(gamma[tail]).all():
        diagnostics.update({"reliable": False, "reason": "tail bins 不足，无法可靠估计 sill"})
        return diagnostics
    sill = float(np.median(gamma[tail]))
    if not np.isfinite(sill) or sill <= 0:
        diagnostics.update({"reliable": False, "reason": "tail-sill 非正或不可用"})
        return diagnostics
    threshold = float(config["range_sill_fraction"]) * sill
    tolerance = float(config["post_threshold_stability_relative_tolerance"]) * sill
    range_index: int | None = None
    for index in range(bins):
        subsequent = np.arange(index, bins)
        if not populated[subsequent].all() or not np.isfinite(gamma[subsequent]).all():
            continue
        if gamma[index] >= threshold and np.all(np.abs(gamma[subsequent] - sill) <= tolerance):
            range_index = index
            break
    diagnostics.update({"tail_sill": sill, "threshold_95pct_sill": threshold, "stability_tolerance": tolerance})
    if range_index is None:
        diagnostics.update({"reliable": False, "reason": "未达到并保持稳定的 95% sill correlation range"})
        return diagnostics
    diagnostics.update({
        "reliable": True,
        "correlation_range_m": float(edges[range_index + 1]),
        "range_lag_index": range_index,
        "range_rule": "使用首次满足阈值的 lag 上边界，保持 buffer 的保守性。",
    })
    return diagnostics


def write_canonical_masks(path: Path, master: Raster, qa_valid: np.ndarray, base_valid: np.ndarray, water: np.ndarray, shadow: np.ndarray, near_zero: np.ndarray, lit: np.ndarray) -> None:
    if path.exists():
        raise PreflightError(f"拒绝覆盖既有输出：{path.name}")
    arrays = []
    base = np.zeros(master.shape, dtype="uint8")
    base[base_valid] = 1
    arrays.append(base)
    water_band = np.full(master.shape, MASK_NODATA, dtype="uint8")
    water_band[qa_valid] = 0
    water_band[water] = 1
    arrays.append(water_band)
    for mask in (shadow, near_zero, lit):
        band = np.full(master.shape, MASK_NODATA, dtype="uint8")
        band[base_valid] = 0
        band[mask] = 1
        arrays.append(band)
    profile = master.profile.copy()
    profile.update(driver="GTiff", count=5, dtype="uint8", nodata=int(MASK_NODATA), compress="lzw")
    with rasterio.open(path, "w", **profile) as destination:
        for index, array in enumerate(arrays, start=1):
            destination.write(array, index)
        for index, description in enumerate(("base_valid", "qa_water_bit_7", "shadow", "near_zero", "lit"), start=1):
            destination.set_band_description(index, description)


def design_blocks(mask: np.ndarray, master: Raster, buffer_m: float, config: dict[str, Any]) -> tuple[dict[str, Any], np.ndarray]:
    pixel_size = max(math.hypot(master.transform.a, master.transform.d), math.hypot(master.transform.b, master.transform.e))
    if pixel_size <= 0:
        return {"reliable": False, "reason": "像元尺度不可解释"}, np.full(master.shape, MASK_NODATA, dtype="uint8")
    buffer_pixels = int(math.ceil(buffer_m / pixel_size))
    edge_pixels = max(int(math.ceil(2.0 * buffer_m / pixel_size)), 1)
    stride = edge_pixels + buffer_pixels
    height, width = master.shape
    row_count = 0 if height < edge_pixels else 1 + (height - edge_pixels) // stride
    col_count = 0 if width < edge_pixels else 1 + (width - edge_pixels) // stride
    minimum_pixels = int(config["minimum_land_pixels_per_block"])
    plan: list[dict[str, Any]] = []
    block_map = np.full(master.shape, MASK_NODATA, dtype="uint8")
    block_map[mask] = 0
    for row_index in range(row_count):
        row_start = row_index * stride
        for col_index in range(col_count):
            col_start = col_index * stride
            row_slice = slice(row_start, row_start + edge_pixels)
            col_slice = slice(col_start, col_start + edge_pixels)
            count = int(mask[row_slice, col_slice].sum())
            if count < minimum_pixels:
                continue
            split = "calibration_candidate" if (row_index + col_index) % 2 == 0 else "holdout_candidate"
            block_map[row_slice, col_slice][mask[row_slice, col_slice]] = 1 if split == "calibration_candidate" else 2
            plan.append({
                "grid_row": row_index,
                "grid_column": col_index,
                "row_start": row_start,
                "column_start": col_start,
                "edge_pixels": edge_pixels,
                "land_pixel_count": count,
                "split": split,
            })
    calibration = sum(item["split"] == "calibration_candidate" for item in plan)
    holdout = sum(item["split"] == "holdout_candidate" for item in plan)
    minimum_blocks = int(config["minimum_blocks_per_split"])
    reliable = calibration >= minimum_blocks and holdout >= minimum_blocks
    reason = None if reliable else f"独立候选 blocks 不足：calibration={calibration}, holdout={holdout}, minimum={minimum_blocks}"
    return {
        "reliable": reliable,
        "reason": reason,
        "pixel_size_m": pixel_size,
        "buffer_m": buffer_m,
        "buffer_pixels": buffer_pixels,
        "block_edge_m": edge_pixels * pixel_size,
        "block_edge_pixels": edge_pixels,
        "gap_pixels": buffer_pixels,
        "candidate_grid_rows": row_count,
        "candidate_grid_columns": col_count,
        "calibration_candidate_blocks": calibration,
        "holdout_candidate_blocks": holdout,
        "blocks": plan,
        "no_scoring_performed": True,
    }, block_map


def write_block_map(path: Path, master: Raster, block_map: np.ndarray) -> None:
    if path.exists():
        raise PreflightError(f"拒绝覆盖既有输出：{path.name}")
    profile = master.profile.copy()
    profile.update(driver="GTiff", count=1, dtype="uint8", nodata=int(MASK_NODATA), compress="lzw")
    with rasterio.open(path, "w", **profile) as destination:
        destination.write(block_map, 1)
        destination.set_band_description(1, "0_unassigned_land_1_calibration_candidate_2_holdout_candidate")


def process_scene(scene_name: str, paths: dict[str, Any], config: dict[str, Any], results_dir: Path) -> tuple[dict[str, Any], dict[str, np.ndarray], Raster]:
    rasters = {key: read_raster(relative_path(PROJECT_ROOT, paths[key])) for key in ("b4", "b5", "qa_pixel", "cos_i")}
    metadata = read_metadata(relative_path(PROJECT_ROOT, paths["metadata"]))
    master = rasters["b4"]
    grid_failures: dict[str, list[str]] = {}
    for key in ("b5", "qa_pixel", "cos_i"):
        matches, failures = same_grid(master, rasters[key])
        if not matches:
            grid_failures[key] = failures
    if not master.crs or not master.crs.is_projected:
        grid_failures["b4"] = ["CRS 必须是可解释线性距离的投影 CRS"]
    qa_clear, water, qa_flagged = qa_masks(rasters["qa_pixel"], config["canonical_analysis_domain"]["qa_pixel_clear_bits"], int(config["canonical_analysis_domain"]["qa_water_bit"]))
    b4_valid = nodata_valid(rasters["b4"].data, rasters["b4"].nodata)
    b5_valid = nodata_valid(rasters["b5"].data, rasters["b5"].nodata)
    cos_valid = nodata_valid(rasters["cos_i"].data, rasters["cos_i"].nodata)
    reflectance = config["canonical_analysis_domain"]["reflectance_range"]
    b4 = rasters["b4"].data.astype("float64", copy=False)
    b5 = rasters["b5"].data.astype("float64", copy=False)
    cos_i = rasters["cos_i"].data.astype("float64", copy=False)
    in_range = (b4 >= float(reflectance["minimum"])) & (b4 <= float(reflectance["maximum"])) & (b5 >= float(reflectance["minimum"])) & (b5 <= float(reflectance["maximum"]))
    base_valid = qa_clear & b4_valid & b5_valid & cos_valid & in_range
    land = base_valid & ~water
    shadow = base_valid & (cos_i <= 0)
    near_zero = base_valid & (cos_i > 0) & (cos_i <= 0.1)
    lit = base_valid & (cos_i > 0.1)
    overlap = (shadow & near_zero) | (shadow & lit) | (near_zero & lit)
    partition_union = shadow | near_zero | lit
    integrity = {
        "pairwise_overlap_count": int(overlap.sum()),
        "union_difference_count": int((partition_union != base_valid).sum()),
        "passes": bool(not overlap.any() and np.array_equal(partition_union, base_valid)),
    }
    total = int(base_valid.size)
    base_count = int(base_valid.sum())
    land_count = int(land.sum())
    scene: dict[str, Any] = {
        "scene": scene_name,
        "metadata": metadata,
        "grid": {key: grid_summary(value) for key, value in rasters.items()},
        "grid_failures": grid_failures,
        "qa": {
            "clear_bits": config["canonical_analysis_domain"]["qa_pixel_clear_bits"],
            "flagged_counts": qa_flagged,
            "water_bit": 7,
            "water_all_qa_valid": count_ratio(water, int(nodata_valid(rasters["qa_pixel"].data, rasters["qa_pixel"].nodata).sum())),
            "water_in_base_valid": count_ratio(water & base_valid, base_count),
        },
        "canonical": {
            "total_pixel_count": total,
            "base_valid": count_ratio(base_valid, total),
            "base_valid_land": count_ratio(land, total),
            "water_excluded_from_land_count": int((base_valid & water).sum()),
            "partitions_on_base_valid": {
                "shadow": count_ratio(shadow, base_count),
                "near_zero": count_ratio(near_zero, base_count),
                "lit": count_ratio(lit, base_count),
            },
            "partitions_on_base_valid_land": {
                "shadow": count_ratio(shadow & land, land_count),
                "near_zero": count_ratio(near_zero & land, land_count),
                "lit": count_ratio(lit & land, land_count),
            },
            "integrity": integrity,
        },
    }
    prior = paths["prior_results"]
    qa_valid = nodata_valid(rasters["qa_pixel"].data, rasters["qa_pixel"].nodata)
    scene["prior_cross_checks"] = {
        "qa_valid_mask_vs_qa_bits_only": prior_mask(relative_path(PROJECT_ROOT, prior["qa_valid_mask"]), master, qa_clear, qa_valid),
        "qa_valid_mask_vs_base_valid": prior_mask(relative_path(PROJECT_ROOT, prior["qa_valid_mask"]), master, base_valid, qa_valid),
        "shadow_mask_vs_canonical_shadow": prior_mask(relative_path(PROJECT_ROOT, prior["shadow_mask"]), master, shadow, base_valid),
        "near_zero_mask_vs_canonical_near_zero": prior_mask(relative_path(PROJECT_ROOT, prior["near_zero_mask"]), master, near_zero, base_valid),
        "confidence_vs_frozen_sigmoid": prior_confidence(relative_path(PROJECT_ROOT, prior["confidence"]), master, cos_i, base_valid, float(config["mechanisms"]["soft_weight"]["primary_k"])),
    }
    output = results_dir / f"preflight_{scene_name}_canonical_masks.tif"
    write_canonical_masks(output, master, qa_valid, base_valid, water, shadow, near_zero, lit)
    scene["canonical_mask_output"] = relative_text(PROJECT_ROOT, output)
    arrays = {"base_valid": base_valid, "base_valid_land": land, "shadow": shadow, "near_zero": near_zero, "lit": lit, "cos_i": cos_i, "b4": b4, "b5": b5}
    return scene, arrays, master


def markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Stage 6.5.3-B｜First Action：规范掩膜与空间隔离预检",
        "",
        f"- **预检结论：** `{summary['verdict']}`",
        "- **执行边界：** deterministic preflight only；未拟合三种机制、未评分 holdout、未计算 residual/risk–coverage、未形成最终实验结论。",
        "- **Architecture basis：** docs/architecture.md V3。",
        "",
        "## 冻结口径",
        "",
        "- `base_valid`：QA_PIXEL bits 0–5 均为 0，B4/B5/cos_i 均 finite、非 nodata，且 B4/B5 都在 [-0.05, 1.0]。",
        "- 分区：`shadow=cos_i<=0`、`near_zero=0<cos_i<=0.1`、`lit=cos_i>0.1`；完整性在 `base_valid` 上验证。",
        "- water bit 7 单独统计，并从主要 land 指标和空间相关估计排除；更高 QA confidence bits 本轮明确不作为 hard exclusion。",
        "- `soft_weight` k=30 只是继承的经验基线；k={15,30,60} 留给同一机制的后续敏感性检查。bounded diffuse 的数值界限尚未裁决，只能由 calibration-only 证据冻结。",
        "",
        "## A/B 规范统计",
        "",
        "| Scene | base_valid | base_valid_land | water in base_valid | shadow land | near_zero land | lit land | partition integrity |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, scene in summary["scenes"].items():
        canonical = scene["canonical"]
        part = canonical["partitions_on_base_valid_land"]
        lines.append(
            f"| {name} | {canonical['base_valid']['count']} ({canonical['base_valid']['ratio']:.6f}) | {canonical['base_valid_land']['count']} ({canonical['base_valid_land']['ratio']:.6f}) | {canonical['water_excluded_from_land_count']} | {part['shadow']['count']} ({part['shadow']['ratio']:.6f}) | {part['near_zero']['count']} ({part['near_zero']['ratio']:.6f}) | {part['lit']['count']} ({part['lit']['ratio']:.6f}) | {'PASS' if canonical['integrity']['passes'] else 'FAIL'} |"
        )
    lines.extend(["", "## Grid / nodata 检查", ""])
    for name, scene in summary["scenes"].items():
        failures = scene["grid_failures"]
        grid = scene["grid"]["b4"]
        lines.append(f"- **{name}**：CRS={grid['crs']}，shape={grid['shape']}，resolution={grid['resolution']}，主输入 grid={'PASS' if not failures else 'FAIL: ' + json.dumps(failures, ensure_ascii=False)}。")
    lines.extend(["", "## 空间相关范围与候选隔离", ""])
    for name, fields in summary["semivariograms"].items():
        lines.append(f"### {name}")
        for field, item in fields.items():
            if item.get("reliable"):
                lines.append(f"- {field}: reliable range={item['correlation_range_m']:.3f} m；tail sill={item['tail_sill']:.8g}。")
            else:
                lines.append(f"- {field}: **unreliable** — {item.get('reason')}。")
        block = summary["candidate_blocks"].get(name)
        if block:
            if block.get("reliable"):
                lines.append(f"- candidate blocks: buffer={block['buffer_m']:.3f} m ({block['buffer_pixels']} px), edge={block['block_edge_m']:.3f} m ({block['block_edge_pixels']} px), calibration={block['calibration_candidate_blocks']}, holdout={block['holdout_candidate_blocks']}；未评分。")
            else:
                lines.append(f"- candidate blocks: **BLOCKED** — {block.get('reason')}。")
    lines.extend(["", "## Prior-result 差异核对", "", "已有 QA/mask/confidence 仅作 cross-check，并未作为 canonical mask 真相源。旧 near-zero mask 的 `cos_i<=0.1` 口径包含 shadow；因此它与本轮严格 `0<cos_i<=0.1` 的差异是预期可解释差异，而非补写或拟合。", "", "## Verdict / blockers", ""])
    if summary["blockers"]:
        for blocker in summary["blockers"]:
            lines.append(f"- **BLOCKER：** {blocker}")
    else:
        lines.append("- 无 execution blocker；预检口径、规范掩膜与候选空间隔离设计可以进入下一项裁决，但不代表 Stage 6.5.3-B 完成。")
    lines.extend(["", "## 尚待裁决", "", "- bounded_scene_constant_diffuse 的数值边界与依据必须在 calibration-only 条件下另行冻结；不得读取 holdout 后调整。", "- 本报告不提供三种机制的拟合、残差、risk–coverage 或最终优劣结论。", ""])
    return "\n".join(lines)


def write_text(path: Path, text: str) -> None:
    if path.exists():
        raise PreflightError(f"拒绝覆盖既有输出：{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    outputs = config["outputs"]
    results_dir = relative_path(PROJECT_ROOT, outputs["results_directory"])
    report_path = relative_path(PROJECT_ROOT, outputs["report"])
    evidence_path = relative_path(PROJECT_ROOT, outputs["evidence"])
    for path in (results_dir, report_path.parent, evidence_path.parent):
        relative = relative_text(PROJECT_ROOT, path)
        if not any(relative == prefix or relative.startswith(prefix + "/") for prefix in outputs["allowed_output_prefixes"]):
            raise PreflightError(f"输出越过 Workspace Contract 边界：{relative}")
    if not results_dir.exists():
        results_dir.mkdir(parents=True)
    if any(results_dir.iterdir()):
        raise PreflightError("拒绝覆盖既有 Stage 6.5.3-B 结果目录")
    scenes: dict[str, Any] = {}
    arrays: dict[str, dict[str, np.ndarray]] = {}
    masters: dict[str, Raster] = {}
    blockers: list[str] = []
    for name, scene_paths in config["inputs"].items():
        scene, scene_arrays, master = process_scene(name, scene_paths, config, results_dir)
        scenes[name] = scene
        arrays[name] = scene_arrays
        masters[name] = master
        if scene["grid_failures"]:
            blockers.append(f"{name} 主输入 grid/CRS 不一致：{scene['grid_failures']}")
        if not scene["canonical"]["integrity"]["passes"]:
            blockers.append(f"{name} canonical partitions 未满足互斥并集完整性")
    semivariograms: dict[str, dict[str, Any]] = {}
    all_ranges: list[float] = []
    spatial = config["spatial_isolation"]
    for scene_name, scene_arrays in arrays.items():
        semivariograms[scene_name] = {}
        for field in spatial["fields"]:
            item = semivariogram(scene_arrays[field], scene_arrays["base_valid_land"], masters[scene_name].transform, spatial, scene_seed(int(spatial["seed"]), scene_name, field))
            semivariograms[scene_name][field] = item
            if item.get("reliable"):
                all_ranges.append(float(item["correlation_range_m"]))
            else:
                blockers.append(f"{scene_name}.{field} correlation range 不可靠：{item.get('reason')}")
    candidate_blocks: dict[str, Any] = {}
    if not blockers and all_ranges:
        conservative_range = max(all_ranges)
        for scene_name, scene_arrays in arrays.items():
            plan, block_map = design_blocks(scene_arrays["base_valid_land"], masters[scene_name], conservative_range, spatial["candidate_block_design"])
            candidate_blocks[scene_name] = plan
            if plan.get("reliable"):
                block_path = results_dir / f"preflight_{scene_name}_candidate_blocks.tif"
                write_block_map(block_path, masters[scene_name], block_map)
                plan["block_map_output"] = relative_text(PROJECT_ROOT, block_path)
            else:
                blockers.append(f"{scene_name} 独立 calibration/holdout candidate blocks 不足：{plan.get('reason')}")
    conservative_range = max(all_ranges) if len(all_ranges) == 6 else None
    verdict = "PASS" if not blockers else "BLOCKED"
    summary = {
        "schema": "mountainrs-stage-6-5-3-b-preflight-evidence-v1",
        "stage": config["stage"],
        "preflight_only": True,
        "project_guard": config["project_guard"],
        "config_sha256": sha256_file(config_path),
        "executor_sha256": sha256_file(SCRIPT_PATH),
        "verdict": verdict,
        "blockers": blockers,
        "scenes": scenes,
        "semivariograms": semivariograms,
        "conservative_correlation_range_m": conservative_range,
        "candidate_blocks": candidate_blocks,
        "mechanism_execution": {
            "hard_mask_fitted": False,
            "soft_weight_fitted": False,
            "bounded_scene_constant_diffuse_fitted": False,
            "holdout_scored": False,
            "residual_computed": False,
            "risk_coverage_computed": False,
        },
        "pending_decisions": [
            "bounded_scene_constant_diffuse 的数值边界必须以 calibration-only 证据冻结。",
            "仅在本预检 PASS 后，才可另行授权正式拟合与严格空间隔离 holdout 评分。",
        ],
    }
    write_text(evidence_path, json.dumps(json_ready(summary), ensure_ascii=False, indent=2) + "\n")
    write_text(report_path, markdown(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 6.5.3-B deterministic preflight only.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    try:
        summary = run(args.config.resolve())
    except PreflightError as exc:
        print(f"PRECHECK_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"verdict": summary["verdict"], "blocker_count": len(summary["blockers"]), "config_sha256": summary["config_sha256"], "executor_sha256": summary["executor_sha256"]}, ensure_ascii=False))
    return 0 if summary["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
