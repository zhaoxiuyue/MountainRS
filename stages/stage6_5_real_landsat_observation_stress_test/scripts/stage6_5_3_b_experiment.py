"""Approved Stage 6.5.3-B runner.

This module implements only the C5-D3 contract: deterministic per-fold
calibration, held-out scoring, compact diagnostics, and idempotent evidence.
It deliberately has no PF2 writeback or node-completion path.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import rasterio


PROTOCOL_VERSION = "c5-d3-approved-experiment-v1"
CONTRACT_ANCHORS = {
    "config_sha256": "dc6224964aca5ca910dc38952aebaae6a0429597137286ffc1d5add3057d5d59",
    "executor_contract_sha256": "2c91e41c77aa4ab5dbb69c27979f59a4b0d2978f20cdc0c1bd785853934e9ee3",
    "approved_manifest_content_hash": "d0dc8cc339edef91ff2bf519d37af08549385de88eab4119ce0b882f30ff3b37",
    "approved_manifest_file_sha256": "4430bf356a0f8661a510326fca1d709bca43bbc5deb0cdad9a2536c2e3f97fe8",
    "method_contract_sha256": "0662e61b78fb110e19eb40243848d5a07589cca56a9b774e8bd70621edb1c910",
}
MAIN_METHODS = ("hard_mask", "soft_weight_k30", "bounded_scene_constant_diffuse")
ALL_METHODS = ("hard_mask", "soft_weight_k15", "soft_weight_k30", "soft_weight_k60", "bounded_scene_constant_diffuse")
FLOAT_NODATA = np.float32(-9999.0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(json_ready(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    return value


def root_relative(project_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise RuntimeError(f"合同路径必须是 workspace-relative：{raw}")
    resolved = (project_root / candidate).resolve()
    if resolved != project_root and project_root not in resolved.parents:
        raise RuntimeError(f"合同路径逃逸 workspace：{raw}")
    return resolved


def rel(project_root: Path, path: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def write_new_text(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"拒绝覆盖既有正式产物：{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_new_json(path: Path, value: Any) -> None:
    write_new_text(path, json.dumps(json_ready(value), ensure_ascii=False, indent=2) + "\n")


def write_new_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"拒绝写入空表：{path.name}")
    if path.exists():
        raise RuntimeError(f"拒绝覆盖既有正式产物：{path.name}")
    fields = list(rows[0].keys())
    if any(list(row.keys()) != fields for row in rows):
        raise RuntimeError(f"CSV 字段不一致：{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def git_head_file_sha(project_root: Path, relative_path: str) -> str:
    try:
        content = subprocess.check_output(["git", "show", f"HEAD:{relative_path}"], cwd=project_root)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"无法读取 approved contract 的 HEAD source：{relative_path}") from exc
    return hashlib.sha256(content).hexdigest()


def git_head(project_root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_root, text=True).strip()


def combined_execution_source_hash(parent_executor: Path) -> str:
    digest = hashlib.sha256()
    for path in (parent_executor, Path(__file__).resolve()):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def mask_hash(mask: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(mask.astype(np.uint8, copy=False)).tobytes()).hexdigest()


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"approved manifest 不可解析：{exc}") from exc
    claimed = manifest.get("manifest_sha256")
    stable = dict(manifest)
    stable.pop("manifest_sha256", None)
    if claimed != canonical_sha256(stable):
        raise RuntimeError("approved manifest self-hash 不匹配")
    if claimed != CONTRACT_ANCHORS["approved_manifest_content_hash"]:
        raise RuntimeError("approved manifest content hash 不匹配")
    if manifest.get("status") != "approved_for_stage_6_5_3_b" or manifest.get("formal_experiment_eligibility") is not True:
        raise RuntimeError("manifest 未获正式实验资格")
    if manifest.get("approval", {}).get("approval_basis_proposal_manifest_sha256") != "d45df2aceeeb3607b08ced88ca04d154bbe78015ff03af9ed3bcd82776ad4fdc":
        raise RuntimeError("manifest proposal 来源锚点不匹配")
    return manifest


def verify_contract_anchors(config_path: Path, project_root: Path, parent_executor: Path) -> dict[str, str]:
    manifest_path = root_relative(project_root, "stage6_5_real_landsat_observation_stress_test/evidence/stage6_5_3_b/proposed_fold_manifest.json")
    method_path = root_relative(project_root, "stage6_5_real_landsat_observation_stress_test/reports/stage6_5_3_b_method_contract_proposal.md")
    if sha256_file(config_path) != CONTRACT_ANCHORS["config_sha256"]:
        raise RuntimeError("approved config SHA-256 不匹配")
    if sha256_file(manifest_path) != CONTRACT_ANCHORS["approved_manifest_file_sha256"]:
        raise RuntimeError("approved manifest file SHA-256 不匹配")
    if sha256_file(method_path) != CONTRACT_ANCHORS["method_contract_sha256"]:
        raise RuntimeError("approved method contract SHA-256 不匹配")
    executor_rel = rel(project_root, parent_executor)
    if git_head_file_sha(project_root, executor_rel) != CONTRACT_ANCHORS["executor_contract_sha256"]:
        raise RuntimeError("approved executor contract SHA-256 不匹配")
    return {
        "config_sha256": CONTRACT_ANCHORS["config_sha256"],
        "executor_contract_sha256": CONTRACT_ANCHORS["executor_contract_sha256"],
        "approved_manifest_content_hash": CONTRACT_ANCHORS["approved_manifest_content_hash"],
        "approved_manifest_file_sha256": CONTRACT_ANCHORS["approved_manifest_file_sha256"],
        "method_contract_sha256": CONTRACT_ANCHORS["method_contract_sha256"],
    }


def sigmoid(value: np.ndarray | float) -> np.ndarray | float:
    clipped = np.clip(value, -700.0, 700.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def finite_stats(values: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype="float64")
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"count": 0, "bias": None, "mae": None, "median_absolute_error": None, "p90_absolute_error": None}
    absolute = np.abs(values)
    return {
        "count": int(values.size),
        "bias": float(values.mean()),
        "mae": float(absolute.mean()),
        "median_absolute_error": float(np.median(absolute)),
        "p90_absolute_error": float(np.percentile(absolute, 90)),
    }


def solve_one_parameter(mu: np.ndarray, observed: np.ndarray, weights: np.ndarray | None) -> tuple[float, float]:
    if weights is None:
        weights = np.ones(mu.shape, dtype="float64")
    denominator = float(np.sum(weights * mu * mu))
    if not np.isfinite(denominator) or denominator <= 0.0:
        raise RuntimeError("直接光模型 calibration design matrix 退化")
    alpha = float(np.clip(np.sum(weights * mu * observed) / denominator, 0.0, 1.0))
    residual = alpha * mu - observed
    return alpha, float(np.sum(weights * residual * residual))


def fit_diffuse_d1(mu: np.ndarray, observed: np.ndarray) -> tuple[float, float, float, float, str, bool]:
    """Exact convex OLS for y=alpha*mu+d, 0<=alpha<=1, 0<=d<=0.1*alpha."""
    x = np.asarray(mu, dtype="float64")
    y = np.asarray(observed, dtype="float64")
    n = float(x.size)
    if n == 0:
        raise RuntimeError("diffuse calibration 样本为空")
    sxx = float(np.dot(x, x))
    sx = float(x.sum())
    sy = float(y.sum())
    sxy = float(np.dot(x, y))
    candidates: list[tuple[float, float, str]] = []

    def add(alpha: float, d: float, status: str) -> None:
        if not np.isfinite(alpha) or not np.isfinite(d):
            return
        if -1e-12 <= alpha <= 1.0 + 1e-12 and -1e-12 <= d <= 0.1 * alpha + 1e-12:
            candidates.append((float(np.clip(alpha, 0.0, 1.0)), float(max(0.0, d)), status))

    determinant = sxx * n - sx * sx
    if determinant > 1e-12:
        add((sxy * n - sx * sy) / determinant, (sxx * sy - sx * sxy) / determinant, "analytic_interior")
    if sxx > 0.0:
        add(sxy / sxx, 0.0, "analytic_delta_lower")
    shifted = x + 0.1
    shifted_norm = float(np.dot(shifted, shifted))
    if shifted_norm > 0.0:
        upper_alpha = float(np.clip(np.dot(shifted, y) / shifted_norm, 0.0, 1.0))
        add(upper_alpha, 0.1 * upper_alpha, "analytic_delta_upper")
    add(1.0, float(np.clip(np.mean(y - x), 0.0, 0.1)), "analytic_alpha_upper")
    add(0.0, 0.0, "analytic_zero")
    if not candidates:
        raise RuntimeError("diffuse D1 约束优化没有可行候选")
    best = min(candidates, key=lambda item: float(np.sum((item[0] * x + item[1] - y) ** 2)))
    alpha, d, status = best
    delta = 0.0 if alpha <= 1e-12 else float(np.clip(d / alpha, 0.0, 0.1))
    objective = float(np.sum((alpha * x + d - y) ** 2))
    boundary_hit = bool(delta <= 1e-12 or delta >= 0.1 - 1e-12)
    return alpha, delta, d, objective, status, boundary_hit


def open_scene(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    with rasterio.open(path) as source:
        return source.read(1).astype("float64"), {
            "profile": source.profile.copy(),
            "crs": source.crs,
            "transform": source.transform,
            "shape": (source.height, source.width),
            "resolution": tuple(float(item) for item in source.res),
        }


def read_canonical_masks(path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    with rasterio.open(path) as source:
        expected = ("base_valid", "qa_water_bit_7", "shadow", "near_zero", "lit")
        if source.count != 5 or tuple(source.descriptions) != expected:
            raise RuntimeError(f"canonical mask schema 不匹配：{path.name}")
        arrays = source.read()
        base = arrays[0] == 1
        water = arrays[1] == 1
        land = base & ~water
        masks = {
            "base_valid_land": land,
            "shadow": (arrays[2] == 1) & land,
            "near_zero": (arrays[3] == 1) & land,
            "lit": (arrays[4] == 1) & land,
        }
        if not np.array_equal(masks["shadow"] | masks["near_zero"] | masks["lit"], land):
            raise RuntimeError(f"canonical partition 不完整：{path.name}")
        return masks, {
            "profile": source.profile.copy(),
            "crs": source.crs,
            "transform": source.transform,
            "shape": (source.height, source.width),
            "resolution": tuple(float(item) for item in source.res),
        }


def verify_grid(scene: str, canonical: dict[str, Any], raster: dict[str, Any]) -> None:
    if canonical["shape"] != raster["shape"] or canonical["crs"] != raster["crs"] or not np.allclose(tuple(canonical["transform"][:6]), tuple(raster["transform"][:6]), rtol=0, atol=1e-9):
        raise RuntimeError(f"{scene} 输入 grid/CRS/transform 与 canonical mask 不一致")


def fold_masks(shape: tuple[int, int], land: np.ndarray, fold: dict[str, Any], resolution: tuple[float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    bounds = fold["core"]["pixel_bounds"]
    row_start, row_end = int(bounds["row_start"]), int(bounds["row_end_exclusive"])
    col_start, col_end = int(bounds["column_start"]), int(bounds["column_end_exclusive"])
    rows = np.arange(shape[0], dtype="float64")[:, None]
    cols = np.arange(shape[1], dtype="float64")[None, :]
    dy = np.maximum(np.maximum(row_start - rows, rows - (row_end - 1)), 0.0)
    dx = np.maximum(np.maximum(col_start - cols, cols - (col_end - 1)), 0.0)
    distance_px = np.hypot(dx, dy)
    core = (rows >= row_start) & (rows < row_end) & (cols >= col_start) & (cols < col_end)
    holdout = land & core
    buffer = land & ~holdout & (distance_px < 271.0)
    calibration = land & (distance_px >= 271.0)
    if not holdout.any() or not calibration.any():
        raise RuntimeError(f"{fold['fold_id']} 无法形成 holdout/calibration")
    minimum_m = float(distance_px[calibration].min() * max(resolution))
    return calibration, holdout, buffer, minimum_m


def metric_row(scene: str, fold_id: str, band: str, method: str, partition: str, residual: np.ndarray, support: np.ndarray, population: np.ndarray, reliability: str) -> dict[str, Any]:
    supported = support & population
    stats = finite_stats(residual[supported])
    denominator = int(population.sum())
    return {
        "scene": scene,
        "fold_id": fold_id,
        "band": band,
        "method": method,
        "partition": partition,
        "population_count": denominator,
        "supported_count": int(supported.sum()),
        "unsupported_count": int(denominator - supported.sum()),
        "coverage": (float(supported.sum() / denominator) if denominator else None),
        "reliability": reliability,
        **stats,
    }


def write_residual(path: Path, profile: dict[str, Any], residual: np.ndarray) -> None:
    if path.exists():
        raise RuntimeError(f"拒绝覆盖 residual：{path.name}")
    output = np.full(residual.shape, FLOAT_NODATA, dtype="float32")
    finite = np.isfinite(residual)
    output[finite] = residual[finite].astype("float32")
    profile = profile.copy()
    profile.update(count=1, dtype="float32", nodata=float(FLOAT_NODATA), compress="lzw")
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(output, 1)
        dst.set_band_description(1, "model_minus_observation_residual")


def risk_curve_rows(scene: str, fold_id: str, band: str, method: str, residual: np.ndarray, support: np.ndarray, reliability: np.ndarray, holdout: np.ndarray, common_maximum: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    flat_holdout = np.flatnonzero(holdout.ravel())
    flat_support = np.flatnonzero((holdout & support).ravel())
    denominator = len(flat_holdout)
    if denominator == 0:
        raise RuntimeError(f"{fold_id} holdout 分母为空")
    rel_values = reliability.ravel()[flat_support]
    order = np.lexsort((flat_support, -rel_values))
    ordered = flat_support[order]
    maximum = len(ordered) / denominator
    rows: list[dict[str, Any]] = []
    for percent in range(1, 101):
        target = percent / 100.0
        requested = int(math.ceil(target * denominator))
        reachable = requested <= len(ordered)
        selected = ordered[:requested] if reachable else np.empty(0, dtype=np.int64)
        values = residual.ravel()[selected] if reachable else np.empty(0, dtype="float64")
        stats = finite_stats(values)
        rows.append({
            "scene": scene,
            "fold_id": fold_id,
            "band": band,
            "method": method,
            "target_coverage": target,
            "actual_coverage": (len(selected) / denominator if reachable else None),
            "maximum_coverage": maximum,
            "comparison_scope": "common_reachable" if reachable and target <= common_maximum + 1e-12 else "extended_or_unreachable",
            "status": "reachable" if reachable else "not_reachable",
            "selected_count": int(len(selected)),
            "denominator_count": int(denominator),
            "median_absolute_error": stats["median_absolute_error"],
            "p90_absolute_error": stats["p90_absolute_error"],
            "mae": stats["mae"],
        })
    return rows, {"method": method, "maximum_coverage": maximum, "supported_count": len(ordered), "denominator_count": denominator}


def quartile_rows(scene: str, fold_id: str, band: str, calibration: np.ndarray, holdout: np.ndarray, lit: np.ndarray, b4: np.ndarray, b5: np.ndarray, caches: dict[str, dict[str, np.ndarray]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    denominator = b5 + b4
    ndvi_valid = np.isfinite(b4) & np.isfinite(b5) & (np.abs(denominator) >= 1e-6)
    ndvi = np.full(b4.shape, np.nan, dtype="float64")
    ndvi[ndvi_valid] = (b5[ndvi_valid] - b4[ndvi_valid]) / denominator[ndvi_valid]
    brightness = (b4 + b5) / 2.0
    definitions = {
        "ndvi": (ndvi, ndvi_valid),
        "brightness": (brightness, np.isfinite(brightness)),
    }
    rows: list[dict[str, Any]] = []
    verdicts: list[dict[str, Any]] = []
    common_lit = holdout & lit
    for name, (values, valid) in definitions.items():
        calibration_values = values[calibration & valid]
        if calibration_values.size == 0:
            raise RuntimeError(f"{fold_id} {name} calibration 分位点为空")
        thresholds = [float(value) for value in np.quantile(calibration_values, [0.25, 0.5, 0.75])]
        hold_common = common_lit & valid
        global_metrics = {method: finite_stats(caches[method]["residual"][hold_common]) for method in MAIN_METHODS}
        global_ranking = [method for method, _ in sorted(global_metrics.items(), key=lambda item: (math.inf if item[1]["mae"] is None else item[1]["mae"], item[0]))]
        stratum_rankings: list[list[str]] = []
        winner_count = 0
        for index in range(4):
            low = -math.inf if index == 0 else thresholds[index - 1]
            high = math.inf if index == 3 else thresholds[index]
            if index == 0:
                stratum = hold_common & (values <= high)
            elif index == 3:
                stratum = hold_common & (values > low)
            else:
                stratum = hold_common & (values > low) & (values <= high)
            sufficient = int(stratum.sum()) >= 100
            metrics = {method: finite_stats(caches[method]["residual"][stratum]) for method in MAIN_METHODS}
            ranking = [method for method, _ in sorted(metrics.items(), key=lambda item: (math.inf if item[1]["mae"] is None else item[1]["mae"], item[0]))]
            if sufficient:
                stratum_rankings.append(ranking)
                maes = [metrics[item]["mae"] for item in ranking]
                if len(maes) >= 2 and maes[0] is not None and maes[1] is not None and maes[0] < maes[1]:
                    if ranking[0] == global_ranking[0]:
                        winner_count += 1
            for method in MAIN_METHODS:
                rows.append({
                    "scene": scene,
                    "fold_id": fold_id,
                    "band": band,
                    "stratification": name,
                    "stratum": f"q{index + 1}",
                    "lower_bound": None if not np.isfinite(low) else low,
                    "upper_bound": None if not np.isfinite(high) else high,
                    "holdout_count": int(stratum.sum()),
                    "support_status": "sufficient" if sufficient else "insufficient_support",
                    "method": method,
                    "mae": metrics[method]["mae"],
                    "p90_absolute_error": metrics[method]["p90_absolute_error"],
                    "comparison_population": "common_lit_support",
                })
        reversals = sum(1 for ranking in stratum_rankings if ranking != global_ranking)
        sensitive = reversals >= 2 or (len(stratum_rankings) > 0 and winner_count <= 1)
        verdicts.append({
            "scene": scene,
            "fold_id": fold_id,
            "band": band,
            "stratification": name,
            "global_ranking": ">".join(global_ranking),
            "sufficient_strata": len(stratum_rankings),
            "reversed_strata": reversals,
            "global_winner_strict_advantage_strata": winner_count,
            "surface_heterogeneity_sensitive": sensitive,
        })
    return rows, verdicts


def spatial_row(scene: str, fold_id: str, band: str, method: str, residual: np.ndarray, support: np.ndarray, holdout: np.ndarray, transform: Any, seed: int) -> dict[str, Any]:
    mask = holdout & support & np.isfinite(residual)
    rows, cols = np.nonzero(mask)
    if len(rows) < 200:
        return {"scene": scene, "fold_id": fold_id, "band": band, "method": method, "status": "inconclusive_insufficient_residual_support", "spatial_dependence_warning": False, "support_count": int(len(rows)), "maximum_pair_distance_m": None, "bin_1_pair_count": None, "bin_1_semivariance": None, "bin_2_pair_count": None, "bin_2_semivariance": None, "tail_sill": None}
    x = transform.c + transform.a * (cols + 0.5) + transform.b * (rows + 0.5)
    y = transform.f + transform.d * (cols + 0.5) + transform.e * (rows + 0.5)
    maximum = float(math.hypot(float(x.max() - x.min()), float(y.max() - y.min())))
    if maximum <= 8130.0:
        return {"scene": scene, "fold_id": fold_id, "band": band, "method": method, "status": "inconclusive_core_extent_below_8130m", "spatial_dependence_warning": False, "support_count": int(len(rows)), "maximum_pair_distance_m": maximum, "bin_1_pair_count": None, "bin_1_semivariance": None, "bin_2_pair_count": None, "bin_2_semivariance": None, "tail_sill": None}
    rng = np.random.default_rng(seed)
    sample = min(len(rows), 4000)
    if sample < len(rows):
        chosen = rng.choice(len(rows), sample, replace=False)
        x, y = x[chosen], y[chosen]
        values = residual[rows[chosen], cols[chosen]].astype("float64")
    else:
        values = residual[rows, cols].astype("float64")
    pair_count = 500000
    left = rng.integers(0, sample, size=pair_count)
    right = rng.integers(0, sample, size=pair_count)
    distances = np.hypot(x[left] - x[right], y[left] - y[right])
    semivariances = 0.5 * (values[left] - values[right]) ** 2
    edges = np.linspace(8130.0, maximum, 3)
    result: list[tuple[int, float | None]] = []
    for start, end in zip(edges[:-1], edges[1:]):
        keep = (left != right) & (distances >= start) & ((distances < end) if end < maximum else (distances <= end))
        count = int(keep.sum())
        result.append((count, float(semivariances[keep].mean()) if count else None))
    sill = float(np.var(values))
    enough = all(count >= 200 and gamma is not None for count, gamma in result) and sill > 0.0
    warning = bool(enough and all(float(gamma) < 0.95 * sill for _, gamma in result))
    return {
        "scene": scene,
        "fold_id": fold_id,
        "band": band,
        "method": method,
        "status": "spatial_dependence_warning" if warning else ("no_warning_at_resolved_lags" if enough else "inconclusive_insufficient_lag_support"),
        "spatial_dependence_warning": warning,
        "support_count": int(len(rows)),
        "maximum_pair_distance_m": maximum,
        "bin_1_pair_count": result[0][0],
        "bin_1_semivariance": result[0][1],
        "bin_2_pair_count": result[1][0],
        "bin_2_semivariance": result[1][1],
        "tail_sill": sill if sill > 0.0 else None,
    }


def make_figures(results_dir: Path, risk_rows: list[dict[str, Any]]) -> list[Path]:
    os.environ.setdefault("MPLCONFIGDIR", str(results_dir / ".matplotlib"))
    import matplotlib.pyplot as plt

    paths: list[Path] = []
    for scene in ("clean_a", "shadow_risk_b"):
        for band in ("B4", "B5"):
            subset = [row for row in risk_rows if row["scene"] == scene and row["band"] == band and row["status"] == "reachable"]
            if not subset:
                continue
            figure, axes = plt.subplots(1, 2, figsize=(13, 5))
            for method in MAIN_METHODS:
                method_rows = [row for row in subset if row["method"] == method]
                grouped: dict[float, list[float]] = {}
                coverage: dict[float, list[float]] = {}
                for row in method_rows:
                    if row["median_absolute_error"] is not None:
                        grouped.setdefault(float(row["target_coverage"]), []).append(float(row["median_absolute_error"]))
                        coverage.setdefault(float(row["target_coverage"]), []).append(float(row["actual_coverage"]))
                xs = sorted(grouped)
                if xs:
                    axes[0].plot(xs, [float(np.median(grouped[x])) for x in xs], label=method)
                    axes[1].plot(xs, [float(np.median(coverage[x])) for x in xs], label=method)
            axes[0].set_title(f"{scene} {band}: median absolute residual")
            axes[0].set_xlabel("target coverage")
            axes[0].set_ylabel("median |model-observation residual|")
            axes[1].set_title(f"{scene} {band}: attained coverage")
            axes[1].set_xlabel("target coverage")
            axes[1].set_ylabel("attained coverage")
            for axis in axes:
                axis.grid(alpha=0.25)
                axis.legend(fontsize=8)
            figure.tight_layout()
            path = results_dir / "figures" / f"{scene}_{band}_risk_coverage.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(path, dpi=160)
            plt.close(figure)
            paths.append(path)
    return paths


def median_or_none(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.median(clean)) if clean else None


def report_text(run_id: str, summary: dict[str, Any], manifest_rel: str, evidence_rel: str) -> str:
    lines = [
        "# Stage 6.5.3-B｜C5-D3 正式机制实验报告",
        "",
        f"- **run ID：** `{run_id}`",
        f"- **合同 manifest：** `{manifest_rel}`，content hash `{summary['contract_anchors']['approved_manifest_content_hash']}`。",
        "- **范围：**Clean A lit/control 与 Shadow-risk B shadow/near-zero stress；每折为描述性 buffered leave-region-out 挑战，不是独立统计重复。",
        "- **不做的推断：**residual 是指定 forward baseline 的 model–observation residual，不是真值反演误差；D1 diffuse 是受 tau=0.1 约束的场景常数探针，不是真实 diffuse irradiance。",
        "",
        "## 运行 Gate",
        "",
        f"- contract anchors：config `{summary['contract_anchors']['config_sha256']}`；approved method contract `{summary['contract_anchors']['method_contract_sha256']}`；D2 executor contract `{summary['contract_anchors']['executor_contract_sha256']}`。",
        f"- 所有 10 folds 均复核 calibration/holdout/buffer 计数与 manifest 一致；最小隔离距离均不低于 8,130 m。",
        f"- scalar results hash：`{summary['scalar_results_hash']}`。",
        "",
        "## 各场景 / 波段 / 方法的 fold-level 描述性摘要",
        "",
        "| scene | band | method | median fold MAE | median fold P90 | median maximum coverage |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in summary["method_summary"]:
        lines.append(f"| {row['scene']} | {row['band']} | {row['method']} | {row['median_fold_mae'] if row['median_fold_mae'] is not None else '—'} | {row['median_fold_p90'] if row['median_fold_p90'] is not None else '—'} | {row['median_maximum_coverage'] if row['median_maximum_coverage'] is not None else '—'} |")
    lines.extend(["", "## 反证与空间诊断", ""])
    lines.append(f"- `surface_heterogeneity_sensitive`：{summary['surface_heterogeneity_sensitive_count']} / {summary['surface_heterogeneity_diagnostic_count']} 个 scene×fold×band×stratification 诊断被标记。被标记的单元不得宣称稳定光照机制优势。")
    lines.append(f"- residual spatial diagnostics：warning={summary['spatial_warning_count']}，no-warning={summary['spatial_no_warning_count']}，inconclusive={summary['spatial_inconclusive_count']}。inconclusive 是 holdout core 尺度或 lag 支持不足，不是空间独立性的证明。")
    lines.extend(["", "## 合同范围内 verdict", ""])
    for item in summary["method_verdicts"]:
        lines.append(f"- **{item['method']}：{item['verdict']}** — {item['reason']}")
    lines.append(f"- **Stage 6.5.3-B：{summary['overall_verdict']}** — {summary['overall_reason']}")
    lines.extend(["", "## 产物与边界", "", f"- 紧凑表、evidence manifest 与本报告均可追溯；大体量 residual GeoTIFF 与图像只在 approved outputs 路径生成，遵循 Git ignore。", f"- Evidence manifest：`{evidence_rel}`。", "- 本轮没有写回 PF2 结论、没有完成节点，也没有清除 current-task。", ""])
    return "\n".join(lines)


def run_approved_experiment(config_path: Path, project_root: Path, parent_executor: Path) -> dict[str, Any]:
    """Run the approved D3 experiment once, or verify a prior idempotent run."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    anchors = verify_contract_anchors(config_path, project_root, parent_executor)
    manifest_path = root_relative(project_root, config["approved_experiment_contract"]["manifest"]["relative_path"])
    manifest = read_manifest(manifest_path)
    execution_hash = combined_execution_source_hash(parent_executor)
    run_material = f"{PROTOCOL_VERSION}:{anchors['config_sha256']}:{anchors['approved_manifest_content_hash']}:{anchors['method_contract_sha256']}"
    run_id = "c5_d3_" + hashlib.sha256(run_material.encode("utf-8")).hexdigest()[:16]
    results_dir = root_relative(project_root, config["outputs"]["results_directory"]) / run_id
    evidence_dir = root_relative(project_root, "stage6_5_real_landsat_observation_stress_test/evidence/stage6_5_3_b") / run_id
    evidence_path = evidence_dir / "experiment_manifest.json"
    if evidence_path.exists():
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if evidence.get("execution_source_hash") != execution_hash:
            raise RuntimeError("既有同一 run ID 的执行源 hash 不同；拒绝静默覆盖或漂移")
        if evidence.get("contract_anchors") != anchors:
            raise RuntimeError("既有同一 run ID 的合同锚点不同；拒绝静默覆盖或漂移")
        return {"status": "idempotent_existing", "run_id": run_id, "scalar_results_hash": evidence["scalar_results_hash"], "evidence_manifest_sha256": evidence["evidence_manifest_sha256"], "results_directory": rel(project_root, results_dir), "side_effects": "none"}
    if results_dir.exists() or evidence_dir.exists():
        raise RuntimeError("run output 目录已部分存在，拒绝混合或覆盖")
    if config.get("project_guard", {}).get("project_revision") != 40 or config["project_guard"].get("route_revision") != 1 or config["project_guard"].get("node_contract_revision") != 2:
        raise RuntimeError("config project/node guard 不匹配 approved C5-D3 基线")
    if config.get("approved_experiment_contract", {}).get("this_round") != {"execute_fits": False, "score_holdout": False, "compute_residuals": False, "compute_risk_coverage": False}:
        raise RuntimeError("D2 frozen contract 状态被改写；需要新的显式实验合同")
    results_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    fit_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    partition_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    heterogeneity_rows: list[dict[str, Any]] = []
    heterogeneity_verdicts: list[dict[str, Any]] = []
    spatial_rows: list[dict[str, Any]] = []
    residual_paths: list[Path] = []
    canonical_dir = root_relative(project_root, config["outputs"]["results_directory"])
    scene_groups = {"clean_a": "clean_a_lit_control", "shadow_risk_b": "shadow_risk_b_combined_risk"}
    for scene, group_name in scene_groups.items():
        masks, canonical_meta = read_canonical_masks(canonical_dir / f"preflight_{scene}_canonical_masks.tif")
        b4, b4_meta = open_scene(root_relative(project_root, config["inputs"][scene]["b4"]))
        b5, b5_meta = open_scene(root_relative(project_root, config["inputs"][scene]["b5"]))
        verify_grid(scene, canonical_meta, b4_meta)
        verify_grid(scene, canonical_meta, b5_meta)
        bands = {"B4": b4, "B5": b5}
        folds = manifest["fold_groups"][group_name]["folds"]
        for fold in folds:
            calibration, holdout, buffer, minimum_m = fold_masks(canonical_meta["shape"], masks["base_valid_land"], fold, canonical_meta["resolution"])
            expected = fold["counts"]
            if int(calibration.sum()) != expected["calibration_land"] or int(holdout.sum()) != expected["holdout_land"] or int(buffer.sum()) != expected["buffer_excluded_land"]:
                raise RuntimeError(f"{fold['fold_id']} geometry counts 与 manifest 不一致")
            if minimum_m + 1e-9 < 8130.0:
                raise RuntimeError(f"{fold['fold_id']} 实测最小隔离距离低于 8,130 m")
            for partition in ("shadow", "near_zero", "lit"):
                if int((holdout & masks[partition]).sum()) != expected["holdout"][partition]:
                    raise RuntimeError(f"{fold['fold_id']} {partition} holdout count 与 manifest 不一致")
            cos_i, cos_meta = open_scene(root_relative(project_root, config["inputs"][scene]["cos_i"]))
            verify_grid(scene, canonical_meta, cos_meta)
            mu = np.maximum(cos_i, 0.0)
            calibration_lit = calibration & masks["lit"]
            calibration_hashes = {"all": mask_hash(calibration), "lit": mask_hash(calibration_lit)}
            holdout_hash = mask_hash(holdout)
            for band, observed in bands.items():
                w15 = sigmoid(15.0 * (cos_i - 0.1)).astype("float64")
                w30 = sigmoid(30.0 * (cos_i - 0.1)).astype("float64")
                w60 = sigmoid(60.0 * (cos_i - 0.1)).astype("float64")
                methods: dict[str, dict[str, Any]] = {}
                hard_alpha, hard_objective = solve_one_parameter(mu[calibration_lit], observed[calibration_lit], None)
                methods["hard_mask"] = {"alpha": hard_alpha, "delta": None, "d": None, "objective": hard_objective, "optimizer": "closed_form_bounded_ols", "converged": True, "fit_status": "converged", "boundary_hit": False, "fit_mask": calibration_lit, "support": holdout & masks["lit"], "reliability": np.where(masks["lit"], 1.0, -np.inf), "prediction": hard_alpha * mu, "reliability_label": "lit=1; cos_i<=0.1 unsupported"}
                for k, weights in ((15, w15), (30, w30), (60, w60)):
                    alpha, objective = solve_one_parameter(mu[calibration], observed[calibration], weights[calibration])
                    key = f"soft_weight_k{k}"
                    methods[key] = {"alpha": alpha, "delta": None, "d": None, "objective": objective, "optimizer": "closed_form_bounded_weighted_ols", "converged": True, "fit_status": "converged", "boundary_hit": False, "fit_mask": calibration, "support": holdout, "reliability": w30, "prediction": alpha * mu, "reliability_label": "w_30 observation-support ranking"}
                diffuse_alpha, diffuse_delta, diffuse_d, diffuse_objective, diffuse_status, diffuse_boundary = fit_diffuse_d1(mu[calibration], observed[calibration])
                methods["bounded_scene_constant_diffuse"] = {"alpha": diffuse_alpha, "delta": diffuse_delta, "d": diffuse_d, "objective": diffuse_objective, "optimizer": "analytic_convex_boundary_enumeration", "converged": True, "fit_status": diffuse_status, "boundary_hit": diffuse_boundary, "fit_mask": calibration, "support": holdout, "reliability": w30, "prediction": diffuse_alpha * mu + diffuse_d, "reliability_label": "w_30 observation-support ranking; not diffuse-success probability"}
                main_cache: dict[str, dict[str, np.ndarray]] = {}
                for method, item in methods.items():
                    support = item["support"]
                    residual = np.full(observed.shape, np.nan, dtype="float64")
                    residual[support] = item["prediction"][support] - observed[support]
                    fit_mask = item["fit_mask"]
                    fit_rows.append({
                        "scene": scene, "fold_id": fold["fold_id"], "band": band, "method": method,
                        "alpha": item["alpha"], "delta": item["delta"], "d": item["d"], "optimizer": item["optimizer"],
                        "converged": item["converged"], "fit_status": item["fit_status"], "boundary_hit": item["boundary_hit"],
                        "calibration_sample_count": int(fit_mask.sum()), "calibration_objective": item["objective"],
                        "calibration_index_hash": calibration_hashes["lit"] if method == "hard_mask" else calibration_hashes["all"], "holdout_index_hash": holdout_hash,
                    })
                    fold_rows.append(metric_row(scene, fold["fold_id"], band, method, "all", residual, support, holdout, item["reliability_label"]))
                    for partition in ("shadow", "near_zero", "lit"):
                        partition_rows.append(metric_row(scene, fold["fold_id"], band, method, partition, residual, support, holdout & masks[partition], item["reliability_label"]))
                    if method in MAIN_METHODS:
                        main_cache[method] = {"residual": residual, "support": support, "reliability": item["reliability"]}
                        residual_path = results_dir / "residuals" / f"{scene}_{fold['fold_id']}_{band}_{method}.tif"
                        write_residual(residual_path, canonical_meta["profile"], residual)
                        residual_paths.append(residual_path)
                maximums = {method: float((main_cache[method]["support"] & holdout).sum() / holdout.sum()) for method in MAIN_METHODS}
                common_maximum = min(maximums.values())
                for method in MAIN_METHODS:
                    rows, maximum = risk_curve_rows(scene, fold["fold_id"], band, method, main_cache[method]["residual"], main_cache[method]["support"], main_cache[method]["reliability"], holdout, common_maximum)
                    risk_rows.extend(rows)
                    coverage_rows.append({"scene": scene, "fold_id": fold["fold_id"], "band": band, **maximum, "common_maximum_coverage": common_maximum})
                hetero, hetero_verdict = quartile_rows(scene, fold["fold_id"], band, calibration, holdout, masks["lit"], b4, b5, main_cache)
                heterogeneity_rows.extend(hetero)
                heterogeneity_verdicts.extend(hetero_verdict)
                for method in MAIN_METHODS:
                    seed = int.from_bytes(hashlib.sha256(f"{scene}:{fold['fold_id']}:{band}:{method}".encode("utf-8")).digest()[:8], "big")
                    spatial_rows.append(spatial_row(scene, fold["fold_id"], band, method, main_cache[method]["residual"], main_cache[method]["support"], holdout, canonical_meta["transform"], seed))
    figures = make_figures(results_dir, risk_rows)
    table_paths = {
        "fit_parameters": evidence_dir / "fit_parameters.csv",
        "fold_metrics": evidence_dir / "fold_metrics.csv",
        "partition_metrics": evidence_dir / "partition_metrics.csv",
        "risk_coverage": evidence_dir / "risk_coverage.csv",
        "coverage_summary": evidence_dir / "coverage_summary.csv",
        "heterogeneity": evidence_dir / "heterogeneity_diagnostics.csv",
        "heterogeneity_verdict": evidence_dir / "heterogeneity_verdicts.csv",
        "residual_spatial": evidence_dir / "residual_spatial_diagnostics.csv",
    }
    for path, rows in ((table_paths["fit_parameters"], fit_rows), (table_paths["fold_metrics"], fold_rows), (table_paths["partition_metrics"], partition_rows), (table_paths["risk_coverage"], risk_rows), (table_paths["coverage_summary"], coverage_rows), (table_paths["heterogeneity"], heterogeneity_rows), (table_paths["heterogeneity_verdict"], heterogeneity_verdicts), (table_paths["residual_spatial"], spatial_rows)):
        write_new_csv(path, rows)
    method_summary: list[dict[str, Any]] = []
    for scene in ("clean_a", "shadow_risk_b"):
        for band in ("B4", "B5"):
            for method in MAIN_METHODS:
                selected = [row for row in fold_rows if row["scene"] == scene and row["band"] == band and row["method"] == method]
                covers = [row for row in coverage_rows if row["scene"] == scene and row["band"] == band and row["method"] == method]
                method_summary.append({"scene": scene, "band": band, "method": method, "median_fold_mae": median_or_none([row["mae"] for row in selected]), "median_fold_p90": median_or_none([row["p90_absolute_error"] for row in selected]), "median_maximum_coverage": median_or_none([row["maximum_coverage"] for row in covers])})
    sensitive_count = sum(1 for row in heterogeneity_verdicts if row["surface_heterogeneity_sensitive"])
    spatial_warning = sum(1 for row in spatial_rows if row["status"] == "spatial_dependence_warning")
    spatial_ok = sum(1 for row in spatial_rows if row["status"] == "no_warning_at_resolved_lags")
    spatial_inconclusive = len(spatial_rows) - spatial_warning - spatial_ok
    hard_max = [row["maximum_coverage"] for row in coverage_rows if row["method"] == "hard_mask"]
    diffuse_boundaries = sum(1 for row in fit_rows if row["method"] == "bounded_scene_constant_diffuse" and row["boundary_hit"])
    method_verdicts = [
        {"method": "hard_mask", "verdict": "WARNING", "reason": f"硬掩膜的最大 coverage 中位数为 {median_or_none(hard_max)}；cos_i<=0.1 保留为 unsupported，不能把排除当作低风险成功。"},
        {"method": "soft_weight_k30", "verdict": "INCONCLUSIVE", "reason": "只在当前样本、当前 shared-fold 设计下描述 residual 与 coverage；w30 不是正确概率。"},
        {"method": "bounded_scene_constant_diffuse", "verdict": "WARNING" if diffuse_boundaries else "INCONCLUSIVE", "reason": f"D1 边界命中 {diffuse_boundaries} / {sum(1 for row in fit_rows if row['method']=='bounded_scene_constant_diffuse')} 个 scene×fold×band 拟合；只检验当前场景级常数参数化。"},
    ]
    overall_verdict = "WARNING" if sensitive_count or spatial_warning or spatial_inconclusive else "INCONCLUSIVE"
    overall_reason = "当前结果受表面异质性敏感或 residual 空间诊断限制；不得宣称稳定机制优势。" if sensitive_count or spatial_warning else "当前样本与机制级压力测试只能给出限定描述，不能外推为一般光照/散射结论。"
    scalar_payload = {"fit_parameters": fit_rows, "fold_metrics": fold_rows, "partition_metrics": partition_rows, "risk_coverage": risk_rows, "heterogeneity_verdicts": heterogeneity_verdicts, "spatial": spatial_rows}
    scalar_hash = canonical_sha256(scalar_payload)
    summary = {
        "schema": "mountainrs-stage-6-5-3-b-result-summary-v1",
        "run_id": run_id,
        "contract_anchors": anchors,
        "execution_source_hash": execution_hash,
        "git_commit_before_run": git_head(project_root),
        "scalar_results_hash": scalar_hash,
        "method_summary": method_summary,
        "surface_heterogeneity_sensitive_count": sensitive_count,
        "surface_heterogeneity_diagnostic_count": len(heterogeneity_verdicts),
        "spatial_warning_count": spatial_warning,
        "spatial_no_warning_count": spatial_ok,
        "spatial_inconclusive_count": spatial_inconclusive,
        "method_verdicts": method_verdicts,
        "overall_verdict": overall_verdict,
        "overall_reason": overall_reason,
    }
    summary_path = evidence_dir / "result_summary.json"
    write_new_json(summary_path, summary)
    report_path = root_relative(project_root, "stage6_5_real_landsat_observation_stress_test/reports/stage6_5_3_b_experiment_report.md")
    report = report_text(run_id, summary, rel(project_root, manifest_path), rel(project_root, evidence_dir / "experiment_manifest.json"))
    write_new_text(report_path, report)
    formal_files = list(table_paths.values()) + [summary_path, report_path]
    evidence = {
        "schema": "mountainrs-stage-6-5-3-b-experiment-evidence-v1",
        "run_id": run_id,
        "protocol_version": PROTOCOL_VERSION,
        "contract_anchors": anchors,
        "execution_source_hash": execution_hash,
        "git_commit_before_run": git_head(project_root),
        "approved_manifest": {"relative_path": rel(project_root, manifest_path), "content_hash": manifest["manifest_sha256"]},
        "guard": config["project_guard"],
        "scalar_results_hash": scalar_hash,
        "result_summary_sha256": sha256_file(summary_path),
        "formal_files": [{"relative_path": rel(project_root, path), "sha256": sha256_file(path)} for path in formal_files],
        "generated_output_files": [{"relative_path": rel(project_root, path), "sha256": sha256_file(path)} for path in residual_paths + figures],
        "idempotency": "同一合同输入与同一 execution source hash 重跑时复用现有 evidence，不覆盖结果。",
        "pf2_writeback": "none",
        "node_completed": False,
    }
    evidence["evidence_manifest_sha256"] = canonical_sha256(evidence)
    write_new_json(evidence_path, evidence)
    return {"status": "succeeded", "run_id": run_id, "scalar_results_hash": scalar_hash, "evidence_manifest_sha256": evidence["evidence_manifest_sha256"], "results_directory": rel(project_root, results_dir), "evidence_manifest": rel(project_root, evidence_path), "side_effects": "local_results_only"}
