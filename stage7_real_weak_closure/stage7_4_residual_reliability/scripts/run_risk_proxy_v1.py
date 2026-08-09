#!/usr/bin/env python3
"""Stage 7.4 M2 result-blind verifier and post-freeze executor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import rasterio

SCRIPT_DIR = Path(__file__).resolve().parent
NODE_ROOT = SCRIPT_DIR.parent
WORK_PACKAGE_ROOT = NODE_ROOT.parent
REPOSITORY_ROOT = WORK_PACKAGE_ROOT.parent
STAGE_7_1 = WORK_PACKAGE_ROOT / "stage7_1_observation_stack"
STAGE_7_2 = WORK_PACKAGE_ROOT / "stage7_2_baseline_fit"
STAGE_7_3 = WORK_PACKAGE_ROOT / "stage7_3_spatial_blocking"

SR_SCALE = 0.0000275
SR_OFFSET = -0.2
SR_MIN = -0.05
SR_MAX = 1.0
QA_CLEAR_MASK = 0b111111
QA_WATER_BIT = 7
MCONF_THRESHOLD = 0.1
FLOAT_NODATA = -9999.0
BANDS = ("SR_B4", "SR_B5")
SCOPES = ("unit_all_scored", "mu_band_low", "mu_band_mid", "mu_band_high")
STRATA = ("self_shadow", "near_zero", "mu_band_low", "mu_band_mid", "mu_band_high")
CONTINUOUS_SCOPE_FIELDS = (
    "s_min",
    "s_max",
    "score_range",
    "AURC_area",
    "AURC_span",
    "AURC_normalized",
)
R1_UNREACHABLE_REASON = "numeric_equal_bit_distinct_proxy_order_undefined"
PROTOCOL_ERROR_REASONS = {
    "identity_or_hash_mismatch",
    "zero_core_total_pixel_count",
    "count_order_violation",
    "base_valid_land_cos_i_missing",
    "base_valid_land_cos_i_nonfinite",
    "base_valid_land_cos_i_outside_minus1_plus1",
    "mconf_cos_i_inconsistency",
    "supported_residual_nonfinite",
    R1_UNREACHABLE_REASON,
    "strata_partition_failure",
    "coverage_identity_failure",
    "fixed_grid_invariant_failure",
    "output_reconciliation_failure",
}


class ProtocolStop(RuntimeError):
    def __init__(self, reason: str, detail: str = "") -> None:
        if reason not in PROTOCOL_ERROR_REASONS:
            raise ValueError(f"non-canonical protocol reason: {reason}")
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_hash(path: Path, expected: str) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise ProtocolStop("identity_or_hash_mismatch", str(path))


def ensure_grid(dataset: rasterio.io.DatasetReader, grid: dict[str, Any], path: Path) -> None:
    expected_transform = tuple(float(value) for value in grid["transform"])
    actual_transform = tuple(float(value) for value in dataset.transform[:6])
    expected_bounds = tuple(float(value) for value in grid["bounds"])
    actual_bounds = tuple(float(value) for value in dataset.bounds)
    actual_crs = dataset.crs.to_string() if dataset.crs is not None else None
    if (
        dataset.width != int(grid["width"])
        or dataset.height != int(grid["height"])
        or actual_crs != grid["crs"]
        or actual_transform != expected_transform
        or actual_bounds != expected_bounds
    ):
        raise ProtocolStop("identity_or_hash_mismatch", f"grid drift: {path}")


def path_roots() -> dict[str, Path]:
    return {
        "repository_root": REPOSITORY_ROOT,
        "work_package_root": WORK_PACKAGE_ROOT,
        "node_container_root": NODE_ROOT,
    }


def resolve_bound_path(record: dict[str, Any]) -> Path:
    root = path_roots().get(record["path_base"])
    if root is None:
        raise ProtocolStop("identity_or_hash_mismatch", f"unknown path base {record['path_base']}")
    return root / record["relative_path"]


def verify_upstream_hashes(config: dict[str, Any]) -> list[dict[str, str]]:
    bindings = config.get("upstream_bindings", {})
    if len(bindings) != 22:
        raise ProtocolStop("identity_or_hash_mismatch", f"expected 22 bindings, got {len(bindings)}")
    checks, seen = [], set()
    for name, record in sorted(bindings.items()):
        path = resolve_bound_path(record).resolve()
        if path in seen:
            raise ProtocolStop("identity_or_hash_mismatch", f"duplicate upstream path {path}")
        seen.add(path)
        ensure_hash(path, record["sha256"])
        checks.append({"binding_id": name, "path": str(path), "sha256": record["sha256"]})
    return checks


def verify_contract(
    protocol_path: Path,
    config_path: Path,
    preflight_path: Path,
    audit_path: Path,
    protocol_sha: str,
    config_sha: str,
    preflight_sha: str,
    audit_sha: str,
    require_outputs_absent: bool = True,
) -> dict[str, Any]:
    canonical_paths = {
        protocol_path: NODE_ROOT / "docs/risk-proxy-protocol-v2.md",
        config_path: NODE_ROOT / "configs/risk-proxy-config-v2.json",
        preflight_path: NODE_ROOT / "evidence/preflight-manifest-v9.json",
        audit_path: NODE_ROOT / "evidence/risk-proxy-runtime-freeze-audit-v2.json",
    }
    if any(actual.resolve() != expected.resolve() for actual, expected in canonical_paths.items()):
        raise ProtocolStop("identity_or_hash_mismatch", "noncanonical contract path")
    ensure_hash(protocol_path, protocol_sha)
    ensure_hash(config_path, config_sha)
    ensure_hash(preflight_path, preflight_sha)
    ensure_hash(audit_path, audit_sha)
    config, preflight, audit = (
        load_json(config_path),
        load_json(preflight_path),
        load_json(audit_path),
    )
    if (
        config.get("schema") != "mountainrs-stage7.4-risk-proxy-config-v2"
        or config.get("version") != 2
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "config schema")
    if config.get("status") != "frozen":
        raise ProtocolStop("identity_or_hash_mismatch", "config status")
    if (
        preflight.get("schema") != "mountainrs-stage7.4-activation-preflight-manifest-v9"
        or preflight.get("version") != 9
        or preflight.get("status") != "recovery_preflight_ready"
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "preflight schema")
    declaration = preflight.get("result_blind_declaration", {})
    required = {
        "stage_7_3_result_values_read": False,
        "stage_7_4_experiment_executed": False,
        "upstream_hashes_frozen": True,
    }
    for key, expected in required.items():
        if declaration.get(key) is not expected:
            raise ProtocolStop("identity_or_hash_mismatch", f"v9 flag {key}")
    declaration_asset = declaration.get("declaration_asset", {})
    declaration_path = resolve_bound_path(declaration_asset)
    ensure_hash(declaration_path, declaration_asset.get("sha256", ""))
    declared_bindings = {
        record["binding_id"]: {
            key: value for key, value in record.items() if key != "binding_id"
        }
        for record in declaration.get("upstream_bindings", [])
    }
    if declared_bindings != config.get("upstream_bindings"):
        raise ProtocolStop("identity_or_hash_mismatch", "v9/config upstream bindings")
    snapshot = preflight.get("pf3_snapshot_binding", {})
    if (
        snapshot.get("project_id") != config.get("identity", {}).get("project_id")
        or snapshot.get("route_id") != config.get("identity", {}).get("route_id")
        or snapshot.get("stage_7_3", {}).get("state") != "done"
        or snapshot.get("stage_7_4", {}).get("state") != "active"
        or snapshot.get("project_rule", {}).get("revision") != 2
        or declaration.get("pf3_readback_route_revision")
        != snapshot.get("live_route_revision")
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "v9 PF3 snapshot")
    if preflight.get("unresolved_substantive_decisions") != []:
        raise ProtocolStop("identity_or_hash_mismatch", "v9 unresolved decisions")
    formal_audit = audit.get("formal_cross_audit", {})
    reviewer_results = formal_audit.get("reviewer_results", [])
    audit_blind = audit.get("result_blind_compliance", {})
    if (
        audit.get("schema") != "mountainrs-stage7.4-risk-proxy-runtime-freeze-audit-v2"
        or audit.get("status") != "pass"
        or formal_audit.get("round_count") != 1
        or formal_audit.get("unanimous_pass") is not True
        or len(reviewer_results) < 2
        or any(result.get("verdict") != "PASS" for result in reviewer_results)
        or audit_blind.get("stage_7_3_result_values_read") is not False
        or audit_blind.get("stage_7_4_experiment_executed") is not False
        or audit.get("freeze_effect", {}).get("exact_candidate_bytes_frozen") is not True
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "formal cross-audit")
    bindings = audit.get("artifact_bindings", {})
    actual_bindings = {
        "protocol_v2": (protocol_path, protocol_sha, "docs/risk-proxy-protocol-v2.md"),
        "config_v2": (config_path, config_sha, "configs/risk-proxy-config-v2.json"),
        "preflight_v9": (preflight_path, preflight_sha, "evidence/preflight-manifest-v9.json"),
        "executor_v1": (
            Path(__file__).resolve(),
            sha256_file(Path(__file__).resolve()),
            "scripts/run_risk_proxy_v1.py",
        ),
        "tests_v1": (
            SCRIPT_DIR / "tests/test_risk_proxy_v1.py",
            sha256_file(SCRIPT_DIR / "tests/test_risk_proxy_v1.py"),
            "scripts/tests/test_risk_proxy_v1.py",
        ),
    }
    for name, (_path, digest, relative_path) in actual_bindings.items():
        record = bindings.get(name, {})
        if record.get("sha256") != digest or record.get("relative_path") != relative_path:
            raise ProtocolStop("identity_or_hash_mismatch", f"audit binding {name}")
    implementation = preflight.get("implementation_candidate", {})
    if (
        implementation.get("executor", {}).get("sha256")
        != actual_bindings["executor_v1"][1]
        or implementation.get("synthetic_tests", {}).get("sha256")
        != actual_bindings["tests_v1"][1]
        or implementation.get("synthetic_test_result", {}).get("status") != "pass"
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "v9 implementation binding")
    authority = config.get("authority", {})
    if (
        authority.get("preflight_v9", {}).get("sha256") != preflight_sha
        or authority.get("protocol", {}).get("relative_path")
        != "docs/risk-proxy-protocol-v2.md"
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "config authority")
    if config["tie_policy"]["numeric_equal_bit_distinct_action"] != R1_UNREACHABLE_REASON:
        raise ProtocolStop("identity_or_hash_mismatch", "R1 reason")
    if config["coverage"]["zero_denominators"]["T_zero"] != "zero_core_total_pixel_count":
        raise ProtocolStop("identity_or_hash_mismatch", "T zero reason")
    reasons = config["protocol_error"]["reason_closed_set"]
    if set(reasons) != PROTOCOL_ERROR_REASONS or len(reasons) != len(PROTOCOL_ERROR_REASONS):
        raise ProtocolStop("identity_or_hash_mismatch", "protocol reasons")
    checks = verify_upstream_hashes(config)
    outputs = {}
    for name, record in config["outputs"].items():
        if not isinstance(record, dict) or "relative_path" not in record:
            continue
        path = resolve_bound_path(record)
        if require_outputs_absent and path.exists():
            raise ProtocolStop("output_reconciliation_failure", str(path))
        outputs[name] = str(path)
    return {
        "status": "verified_result_blind",
        "upstream_binding_count": len(checks),
        "outputs": outputs,
        "formal_cross_audit_sha256": audit_sha,
        "protected_result_content_parsed": False,
    }


def classify_strata(
    cos_i: np.ndarray, check_domain: np.ndarray | None = None
) -> dict[str, np.ndarray]:
    values = np.asarray(cos_i)
    finite = np.isfinite(values)
    domain = finite if check_domain is None else finite & np.asarray(check_domain, dtype=bool)
    outside = (values < -1.0) | (values > 1.0)
    if np.any(domain & outside):
        raise ProtocolStop("base_valid_land_cos_i_outside_minus1_plus1")
    partition_domain = finite & ~outside
    masks = {
        "self_shadow": partition_domain & (values <= 0.0),
        "near_zero": partition_domain & (values > 0.0) & (values <= 0.1),
        "mu_band_low": partition_domain & (values > 0.1) & (values <= 0.4),
        "mu_band_mid": partition_domain & (values > 0.4) & (values <= 0.7),
        "mu_band_high": partition_domain & (values > 0.7) & (values <= 1.0),
    }
    total = sum(mask.astype("uint8") for mask in masks.values())
    if np.any(partition_domain & (total != 1)) or np.any(~partition_domain & (total != 0)):
        raise ProtocolStop("strata_partition_failure")
    return masks


def risk_proxy_from_cos_i(cos_i: np.ndarray) -> np.ndarray:
    values = np.asarray(cos_i, dtype="float32")
    return np.subtract(np.float32(1.0), values, dtype=np.float32)


def _bit_keys(values: np.ndarray) -> np.ndarray:
    array = np.ascontiguousarray(values)
    if array.dtype == np.float32:
        return array.view(np.uint32)
    if array.dtype == np.float64:
        return array.view(np.uint64)
    raise TypeError("score dtype must be float32 or float64")


def exact_risk_points(
    scores: np.ndarray, residuals: np.ndarray, denominator: int
) -> list[dict[str, Any]]:
    scores, residuals = np.asarray(scores), np.asarray(residuals, dtype="float64")
    if scores.ndim != 1 or residuals.ndim != 1 or scores.size != residuals.size:
        raise ValueError("unaligned scores and residuals")
    if np.any(~np.isfinite(scores)):
        raise ProtocolStop("base_valid_land_cos_i_nonfinite")
    if np.any(~np.isfinite(residuals)):
        raise ProtocolStop("supported_residual_nonfinite")
    if denominator <= 0:
        return []
    order = np.argsort(scores, kind="stable")
    values, absolute = scores[order], np.abs(residuals[order])
    keys, points, accepted_sum, accepted_n, start = _bit_keys(values), [], 0.0, 0, 0
    while start < values.size:
        end = start + 1
        while end < values.size and keys[end] == keys[start]:
            end += 1
        accepted_sum += float(absolute[start:end].sum(dtype="float64"))
        accepted_n += end - start
        points.append({
            "exact_point_index": len(points) + 1,
            "score_threshold": float(values[start]),
            "score_bit_pattern": f"0x{int(keys[start]):0{8 if scores.dtype == np.float32 else 16}x}",
            "accepted_pixel_count": int(accepted_n),
            "selective_prediction_coverage": accepted_n / denominator,
            "accepted_set_MAE": accepted_sum / accepted_n,
        })
        start = end
    return points


def map_fixed_grid(
    points: Sequence[dict[str, Any]], denominator: int, target_denominator: int = 20
) -> list[dict[str, Any]]:
    if denominator <= 0:
        return []
    rows, first_q = [], {}
    for k in range(1, target_denominator + 1):
        candidates = [
            point for point in points
            if target_denominator * int(point["accepted_pixel_count"]) <= k * denominator
        ]
        if not candidates:
            rows.append({"target_q": k / target_denominator, "status": "unreachable",
                         "exact_point_index": None, "selective_prediction_coverage": None,
                         "reason": "below_min_accepted_support", "canonical_target_q": None})
            continue
        point = candidates[-1]
        if k * denominator > target_denominator * int(points[-1]["accepted_pixel_count"]):
            rows.append({"target_q": k / target_denominator, "status": "unreachable",
                         "exact_point_index": None, "selective_prediction_coverage": None,
                         "reason": "above_max_reachable_coverage", "canonical_target_q": None})
            continue
        index = int(point["exact_point_index"])
        if index not in first_q:
            first_q[index], status, reason = k, "reachable", None
        else:
            status, reason = "duplicate", "duplicate_exact_point"
        rows.append({"target_q": k / target_denominator, "status": status,
                     "exact_point_index": index,
                     "selective_prediction_coverage": point["selective_prediction_coverage"],
                     "reason": reason, "canonical_target_q": first_q[index] / target_denominator})
    return rows


def verify_fixed_grid(
    points: Sequence[dict[str, Any]],
    rows: Sequence[dict[str, Any]],
    denominator: int,
    target_denominator: int,
) -> None:
    if len(rows) != target_denominator or denominator <= 0:
        raise ProtocolStop("fixed_grid_invariant_failure", "row count or denominator")
    by_index = {int(point["exact_point_index"]): point for point in points}
    first_target_by_index: dict[int, int] = {}
    for k, row in enumerate(rows, start=1):
        if float(row["target_q"]) != k / target_denominator:
            raise ProtocolStop("fixed_grid_invariant_failure", f"target q {k}")
        candidates = [
            point for point in points
            if target_denominator * int(point["accepted_pixel_count"]) <= k * denominator
        ]
        above_max = bool(points) and (
            k * denominator > target_denominator * int(points[-1]["accepted_pixel_count"])
        )
        if not candidates or above_max:
            expected_reason = (
                "below_min_accepted_support" if not candidates
                else "above_max_reachable_coverage"
            )
            if (
                row["status"] != "unreachable"
                or row["reason"] != expected_reason
                or row["exact_point_index"] is not None
                or row["selective_prediction_coverage"] is not None
                or row["canonical_target_q"] is not None
            ):
                raise ProtocolStop("fixed_grid_invariant_failure", f"unreachable row {k}")
            continue
        expected = candidates[-1]
        index = int(expected["exact_point_index"])
        first = first_target_by_index.setdefault(index, k)
        expected_status = "reachable" if first == k else "duplicate"
        expected_reason = None if first == k else "duplicate_exact_point"
        if (
            row["status"] != expected_status
            or row["reason"] != expected_reason
            or int(row["exact_point_index"]) != index
            or float(row["selective_prediction_coverage"])
            != int(expected["accepted_pixel_count"]) / denominator
            or float(row["canonical_target_q"]) != first / target_denominator
            or index not in by_index
        ):
            raise ProtocolStop("fixed_grid_invariant_failure", f"mapped row {k}")


def staircase_aurc(points: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if len(points) < 2:
        return {"area": None, "span": None, "normalized": None}
    area = sum(
        float(left["accepted_set_MAE"]) * (
            float(right["selective_prediction_coverage"])
            - float(left["selective_prediction_coverage"])
        )
        for left, right in zip(points, points[1:])
    )
    span = (
        float(points[-1]["selective_prediction_coverage"])
        - float(points[0]["selective_prediction_coverage"])
    )
    return {"area": area, "span": span, "normalized": area / span if span > 0 else None}


def curve_shape(points: Sequence[dict[str, Any]], tau_abs: float, tau_rel: float) -> str:
    signs = set()
    for left, right in zip(points, points[1:]):
        a, b = float(left["accepted_set_MAE"]), float(right["accepted_set_MAE"])
        delta, tau = b - a, tau_abs + tau_rel * max(abs(a), abs(b))
        signs.add(1 if delta > tau else -1 if delta < -tau else 0)
    nonzero = signs - {0}
    if not nonzero:
        return "flat"
    if nonzero == {1}:
        return "order_consistent"
    if nonzero == {-1}:
        return "order_inverted"
    return "mixed"


def coverage_values(total: int, base_valid: int, scored: int, accepted: int = 0) -> dict[str, Any]:
    if total == 0:
        raise ProtocolStop("zero_core_total_pixel_count")
    if not 0 <= accepted <= scored <= base_valid <= total:
        raise ProtocolStop("count_order_violation")
    if base_valid == 0:
        return {"evidence_support_coverage": 0.0, "scoring_coverage": None,
                "selective_prediction_coverage": None, "acceptance_given_scored": None,
                "reason": "zero_base_valid_land_denominator"}
    evidence = Fraction(base_valid, total)
    scoring = Fraction(scored, base_valid)
    selective = Fraction(accepted, base_valid)
    if evidence * scoring != Fraction(scored, total):
        raise ProtocolStop("coverage_identity_failure", "evidence x scoring")
    if evidence * selective != Fraction(accepted, total):
        raise ProtocolStop("coverage_identity_failure", "evidence x selective")
    if scored and selective != scoring * Fraction(accepted, scored):
        raise ProtocolStop("coverage_identity_failure", "selective factorization")
    return {
        "evidence_support_coverage": float(evidence),
        "scoring_coverage": float(scoring),
        "selective_prediction_coverage": float(selective),
        "acceptance_given_scored": float(Fraction(accepted, scored)) if scored else None,
        "reason": "zero_scored_denominator" if scored == 0 else None,
    }


def evaluate_scope(
    scores: np.ndarray,
    residuals: np.ndarray,
    total: int,
    base_valid: int,
    config: dict[str, Any],
    unit_gate_scored: bool = True,
) -> dict[str, Any]:
    scored = int(np.asarray(scores).size)
    coverage_values(total, base_valid, scored)
    empty = {"s_min": None, "s_max": None, "score_range": None, "exact_points": [],
             "admissible_points": [], "grid": [],
             "AURC": {"area": None, "span": None, "normalized": None}, "curve_shape": None}
    def stop(verdict: str, reason: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        return {**empty, **(extra or {}), "scope_gate": "not_evaluable",
                "risk_proxy_verdict": verdict, "not_evaluable_reason": reason}
    if not unit_gate_scored:
        return stop("not_evaluable_insufficient_scored_support", "unit_gate_not_scored")
    if base_valid == 0:
        return stop("not_evaluable_insufficient_scored_support",
                    "zero_base_valid_land_denominator")
    if scored == 0:
        return stop("not_evaluable_insufficient_scored_support", "zero_scored_denominator")
    scores, residuals = np.asarray(scores), np.asarray(residuals, dtype="float64")
    s_min, s_max = float(scores.min()), float(scores.max())
    common = {"s_min": s_min, "s_max": s_max, "score_range": s_max - s_min}
    guards, tolerances = config["M2_guards"], config["tolerances"]
    if scored < int(guards["N_scored_min_per_scope"]):
        return stop("not_evaluable_insufficient_scored_support", "N_scored_below_271", common)
    tau_score = (
        float(tolerances["tau_score"]["absolute"])
        + float(tolerances["tau_score"]["relative"]) * max(abs(s_min), abs(s_max))
    )
    if common["score_range"] <= tau_score:
        return stop("not_evaluable_score_degenerate", "score_range_at_or_below_tau_score", common)
    exact = exact_risk_points(scores, residuals, base_valid)
    for point in exact:
        coverage_values(total, base_valid, scored, int(point["accepted_pixel_count"]))
    common["exact_points"] = exact
    if len(exact) < int(guards["unique_proxy_values_min_per_scope"]):
        return stop("not_evaluable_score_degenerate", "unique_proxy_values_below_3", common)
    admissible = [
        point for point in exact
        if point["accepted_pixel_count"] >= guards["accepted_n_min_per_admissible_exact_point"]
    ]
    common["admissible_points"] = admissible
    if len(admissible) < int(guards["admissible_exact_points_min_per_scope"]):
        return stop("not_evaluable_score_degenerate", "admissible_exact_points_below_3", common)
    grid = map_fixed_grid(admissible, base_valid, config["fixed_grid"]["target_denominator"])
    verify_fixed_grid(
        admissible, grid, base_valid, config["fixed_grid"]["target_denominator"]
    )
    common["grid"] = grid
    by_index = {point["exact_point_index"]: point for point in admissible}
    canonical = [
        {**row, "accepted_set_MAE": by_index[row["exact_point_index"]]["accepted_set_MAE"]}
        for row in grid if row["status"] == "reachable"
    ]
    if len(canonical) < guards["canonical_reachable_grid_points_min_per_scope"]:
        return stop("not_evaluable_score_degenerate",
                    "canonical_reachable_grid_points_below_3", common)
    aurc = staircase_aurc(admissible)
    common["AURC"] = aurc
    if aurc["span"] is None or aurc["span"] <= 0:
        return stop("not_evaluable_score_degenerate", "AURC_nonpositive_span", common)
    shape = curve_shape(canonical, tolerances["tau_outcome"]["absolute"],
                        tolerances["tau_outcome"]["relative"])
    return {**empty, **common, "scope_gate": "evaluated", "curve_shape": shape,
            "risk_proxy_verdict": config["verdict"]["mapping"][shape],
            "not_evaluable_reason": None}


def describe(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype="float64")
    if array.size == 0:
        return {"count": 0, "median": None, "min": None, "max": None}
    return {"count": int(array.size), "median": float(np.median(array)),
            "min": float(array.min()), "max": float(array.max())}


def aggregate_scope_summaries(
    rows: Sequence[dict[str, Any]],
    verdict_closed_set: Sequence[str],
    reason_closed_set: Sequence[str],
) -> list[dict[str, Any]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["band"], row["curve_scope"])].append(row)
    output = []
    for (band, scope), subset in sorted(grouped.items()):
        per_acquisition = []
        for acquisition in sorted({row["acquisition"] for row in subset}):
            local = [row for row in subset if row["acquisition"] == acquisition]
            per_acquisition.append({
                "acquisition": acquisition,
                "fold_median_range": {
                    key: describe(row[key] for row in local if row.get(key) is not None)
                    for key in CONTINUOUS_SCOPE_FIELDS
                },
            })
        verdicts = Counter(row["risk_proxy_verdict"] for row in subset)
        reasons = Counter(row["not_evaluable_reason"] for row in subset
                          if row["not_evaluable_reason"] is not None)
        across = {
            key: describe(
                row["fold_median_range"][key]["median"]
                for row in per_acquisition
                if row["fold_median_range"][key]["median"] is not None
            )
            for key in CONTINUOUS_SCOPE_FIELDS
        }
        output.append({
            "band": band, "curve_scope": scope,
            "continuous_median_range": {
                "within_acquisition_fold_median_range": per_acquisition,
                "across_acquisition_equal_weight_median_range": across,
            },
            "risk_proxy_verdict_counts": {
                verdict: int(verdicts.get(verdict, 0)) for verdict in verdict_closed_set
            },
            "not_evaluable_reason_counts": {
                reason: int(reasons.get(reason, 0)) for reason in reason_closed_set
            },
            "acquisition_equal_weight_statement":
                "fold medians within acquisition, then equal weight across acquisitions",
        })
    return output


def read_terrain_valid(
    support_audit: dict[str, Any], target_grid: dict[str, Any]
) -> np.ndarray:
    valid = None
    for name, record in sorted(support_audit["terrain_geometry"].items()):
        path = REPOSITORY_ROOT / record["relative_path"]
        ensure_hash(path, record["sha256"])
        with rasterio.open(path) as dataset:
            ensure_grid(dataset, target_grid, path)
            if dataset.count != 1:
                raise ProtocolStop("identity_or_hash_mismatch", f"terrain bands: {path}")
            if dataset.nodata != record["nodata"]:
                raise ProtocolStop("identity_or_hash_mismatch", f"terrain nodata: {path}")
            values, nodata = dataset.read(1), dataset.nodata
        finite = np.isfinite(values)
        if nodata is not None:
            finite &= values != nodata
        if int(finite.sum()) != int(record["finite_count"]):
            raise ProtocolStop("identity_or_hash_mismatch", f"terrain count: {path}")
        valid = finite if valid is None else valid & finite
    if valid is None:
        raise ProtocolStop("identity_or_hash_mismatch", "no terrain components")
    return valid


def build_folds(topology: dict[str, Any]) -> list[dict[str, Any]]:
    grid = topology["target_grid"]
    xs = grid["bounds"][0] + (np.arange(grid["width"]) + 0.5) * grid["resolution"]
    ys = grid["bounds"][3] - (np.arange(grid["height"]) + 0.5) * grid["resolution"]
    x, y = np.meshgrid(xs, ys)
    folds = []
    for record in topology["folds"]:
        path = STAGE_7_3 / record["geometric_calibration_domain"]["relative_path"]
        ensure_hash(path, record["geometric_calibration_domain"]["sha256"])
        with rasterio.open(path) as dataset:
            ensure_grid(dataset, grid, path)
            if dataset.count != 1:
                raise ProtocolStop("identity_or_hash_mismatch", f"domain bands: {path}")
            raw_domain = dataset.read(1)
        if np.any(~np.isin(raw_domain, (0, 1))):
            raise ProtocolStop("identity_or_hash_mismatch", f"domain values: {path}")
        domain = raw_domain.astype(bool)
        if int(domain.sum()) != int(record["geometric_calibration_domain"]["pixel_count"]):
            raise ProtocolStop("identity_or_hash_mismatch", f"domain count: {path}")
        left, bottom, right, top = record["core_projected_bounds"]
        core = (x >= left) & (x <= right) & (y >= bottom) & (y <= top)
        if int(core.sum()) != int(record["core_pixel_count"]):
            raise ProtocolStop("identity_or_hash_mismatch", f"core count: {record['fold_index']}")
        if np.any(core & domain):
            raise ProtocolStop("identity_or_hash_mismatch", f"fold {record['fold_index']}")
        folds.append({"record": record, "core": core})
    partition = sum(fold["core"].astype("uint8") for fold in folds)
    if np.any(partition > 1):
        raise ProtocolStop("identity_or_hash_mismatch", "core overlap")
    return folds


def scope_mask(name: str, scored: np.ndarray, strata: dict[str, np.ndarray]) -> np.ndarray:
    return scored if name == "unit_all_scored" else scored & strata[name]


def curve_records(
    identity: dict[str, Any], scope: str, role: str, result: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    common = {
        **identity,
        "curve_scope": scope,
        "scope_role": role,
        "scope_gate": result["scope_gate"],
        "s_min": result["s_min"],
        "s_max": result["s_max"],
        "score_range": result["score_range"],
        "AURC_area": result["AURC"]["area"],
        "AURC_span": result["AURC"]["span"],
        "AURC_normalized": result["AURC"]["normalized"],
        "curve_shape": result["curve_shape"],
        "risk_proxy_verdict": result["risk_proxy_verdict"],
        "not_evaluable_reason": result["not_evaluable_reason"],
    }
    by_index = {point["exact_point_index"]: point for point in result["exact_points"]}
    admissible_indexes = {point["exact_point_index"] for point in result["admissible_points"]}
    admissible = result["admissible_points"]
    rows = [{
        **common,
        "point_record_index": 1,
        "point_kind": "scope_summary",
        "exact_point_index": None,
        "admissible": False,
        "target_q": None,
        "grid_status": None,
        "accepted_pixel_count": None,
        "selective_prediction_coverage": None,
        "accepted_set_MAE": None,
        "exact_point_count": len(result["exact_points"]),
        "admissible_exact_point_count": len(admissible),
        "first_admissible_exact_point_index": (
            admissible[0]["exact_point_index"] if admissible else None
        ),
        "last_admissible_exact_point_index": (
            admissible[-1]["exact_point_index"] if admissible else None
        ),
        "exact_point_sequence_materialized": False,
        "exact_point_replay_authority": "frozen inputs plus audited executor",
    }]
    for grid in result["grid"]:
        point = by_index.get(grid["exact_point_index"])
        rows.append({
            **common,
            "point_record_index": len(rows) + 1,
            "point_kind": "fixed_grid",
            "exact_point_index": grid["exact_point_index"],
            "admissible": point is not None,
            "target_q": grid["target_q"],
            "grid_status": grid["status"],
            "grid_reason": grid["reason"],
            "canonical_target_q": grid["canonical_target_q"],
            "accepted_pixel_count": point["accepted_pixel_count"] if point else None,
            "selective_prediction_coverage": grid["selective_prediction_coverage"],
            "accepted_set_MAE": point["accepted_set_MAE"] if point else None,
        })
    summary = {
        **identity,
        "curve_scope": scope,
        "AURC_normalized": result["AURC"]["normalized"],
        "score_range": result["score_range"],
        "s_min": result["s_min"],
        "s_max": result["s_max"],
        "AURC_area": result["AURC"]["area"],
        "AURC_span": result["AURC"]["span"],
        "risk_proxy_verdict": result["risk_proxy_verdict"],
        "not_evaluable_reason": result["not_evaluable_reason"],
    }
    return rows, summary


def ensure_finite_json(value: Any, label: str) -> None:
    if isinstance(value, float) and not np.isfinite(value):
        raise ProtocolStop("output_reconciliation_failure", f"nonfinite {label}")
    if isinstance(value, dict):
        for key, child in value.items():
            ensure_finite_json(child, f"{label}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            ensure_finite_json(child, f"{label}[{index}]")


def validate_generated_tables(
    config: dict[str, Any], logical: dict[str, dict[str, Any]]
) -> dict[str, int]:
    for name, payload in logical.items():
        spec = config["outputs"][name]
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise ProtocolStop("output_reconciliation_failure", f"rows {name}")
        keys: set[tuple[Any, ...]] = set()
        for row in rows:
            if not set(spec["required_fields"]) <= set(row):
                raise ProtocolStop("output_reconciliation_failure", f"required fields {name}")
            key = tuple(row.get(field) for field in spec["row_key"])
            if any(value is None for value in key) or key in keys:
                raise ProtocolStop("output_reconciliation_failure", f"row key {name}")
            keys.add(key)
        ensure_finite_json(payload, name)

    unit_rows = logical["unit_status_ledger"]["rows"]
    stratum_rows = logical["stratum_table"]["rows"]
    risk_rows = logical["risk_curve_table"]["rows"]
    aggregate_rows = logical["aggregation_table"]["rows"]
    units = {
        (row["acquisition"], row["band"], int(row["fold"])): row for row in unit_rows
    }
    if len(units) != len(unit_rows):
        raise ProtocolStop("output_reconciliation_failure", "unit identities")
    for row in unit_rows:
        if row["unit_gate_state"] == "scored":
            if (
                row["unit_terminal_category"] != "scored"
                or row["top_level_reason"] is not None
                or row["detail_reason"] is not None
                or row["fallback_receipt"] is not None
            ):
                raise ProtocolStop("output_reconciliation_failure", "scored terminal")
        elif row["unit_gate_state"] == "not_scored":
            if row["unit_terminal_category"] not in {
                "unsupported_calibration", "not_scored_no_supported_pixel"
            } or row["fallback_receipt"] is None or row["fallback_receipt"].get(
                "fallback_used"
            ) is not False:
                raise ProtocolStop("output_reconciliation_failure", "not-scored terminal")
        else:
            raise ProtocolStop("output_reconciliation_failure", "unit gate state")

    strata_by_unit: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in stratum_rows:
        strata_by_unit[(row["acquisition"], row["band"], int(row["fold"]))].append(row)
    if set(strata_by_unit) != set(units):
        raise ProtocolStop("output_reconciliation_failure", "stratum unit identities")
    for key, rows in strata_by_unit.items():
        unit = units[key]
        if {row["stratum"] for row in rows} != set(STRATA):
            raise ProtocolStop("output_reconciliation_failure", "stratum closed set")
        if sum(int(row["stratum_base_valid_count"]) for row in rows) != int(
            unit["base_valid_land_count"]
        ):
            raise ProtocolStop("coverage_identity_failure", "stratum base partition")
        scored_sum = sum(
            int(row["stratum_scored_count"])
            for row in rows if row["stratum"] in {"mu_band_low", "mu_band_mid", "mu_band_high"}
        )
        if scored_sum != int(unit["scope_scored_pixel_counts"]["unit_all_scored"]):
            raise ProtocolStop("coverage_identity_failure", "stratum scored partition")
        total, base = int(unit["core_total_pixel_count"]), int(unit["base_valid_land_count"])
        for row in rows:
            count = int(row["stratum_scored_count"])
            if row["evidence_support_coverage"] != base / total:
                raise ProtocolStop("coverage_identity_failure", "evidence support ratio")
            expected_scoring = count / base if base else None
            expected_selective = (
                count / base
                if base
                and row["status"] == "scored"
                and count
                >= int(config["M2_guards"]["accepted_n_min_per_admissible_exact_point"])
                else 0.0
                if base and count == 0
                else None
            )
            if (
                row["scoring_coverage"] != expected_scoring
                or row["selective_prediction_coverage"] != expected_selective
            ):
                raise ProtocolStop("coverage_identity_failure", "stratum coverage ratio")

    verdicts = set(config["verdict"]["risk_proxy_verdict_closed_set"])
    shapes = set(config["verdict"]["curve_shape_closed_set"])
    reason_owner = {
        reason: verdict
        for verdict, reasons in config["verdict"]["not_evaluable_reason_closed_set"].items()
        for reason in reasons
    }
    risk_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in risk_rows:
        unit_key = (row["acquisition"], row["band"], int(row["fold"]))
        if unit_key not in units or row["risk_proxy_verdict"] not in verdicts:
            raise ProtocolStop("output_reconciliation_failure", "risk identity or verdict")
        if row["scope_gate"] == "evaluated":
            if (
                row["curve_shape"] not in shapes
                or config["verdict"]["mapping"][row["curve_shape"]]
                != row["risk_proxy_verdict"]
                or row["not_evaluable_reason"] is not None
            ):
                raise ProtocolStop("output_reconciliation_failure", "evaluated verdict")
        elif (
            row["scope_gate"] != "not_evaluable"
            or reason_owner.get(row["not_evaluable_reason"]) != row["risk_proxy_verdict"]
            or row["curve_shape"] is not None
        ):
            raise ProtocolStop("output_reconciliation_failure", "not-evaluable verdict")
        if row["accepted_pixel_count"] is not None:
            base = int(units[unit_key]["base_valid_land_count"])
            accepted = int(row["accepted_pixel_count"])
            if base <= 0 or row["selective_prediction_coverage"] != accepted / base:
                raise ProtocolStop("coverage_identity_failure", "risk coverage ratio")
        risk_groups[unit_key + (row["curve_scope"],)].append(row)

    expected_risk_groups = {
        unit_key + (scope,) for unit_key in units for scope in SCOPES
    }
    if set(risk_groups) != expected_risk_groups:
        raise ProtocolStop("output_reconciliation_failure", "risk scope identities")
    for rows in risk_groups.values():
        indexes = [int(row["point_record_index"]) for row in rows]
        if indexes != list(range(1, len(rows) + 1)):
            raise ProtocolStop("output_reconciliation_failure", "risk point sequence")

    aggregate_keys = {(row["band"], row["curve_scope"]) for row in aggregate_rows}
    if aggregate_keys != {(band, scope) for band in BANDS for scope in SCOPES}:
        raise ProtocolStop("output_reconciliation_failure", "aggregation identities")
    for aggregate in aggregate_rows:
        subset = [
            rows[0] for key, rows in risk_groups.items()
            if key[1] == aggregate["band"] and key[3] == aggregate["curve_scope"]
        ]
        if sum(aggregate["risk_proxy_verdict_counts"].values()) != len(subset):
            raise ProtocolStop("output_reconciliation_failure", "verdict counts")
        if sum(aggregate["not_evaluable_reason_counts"].values()) != sum(
            row["not_evaluable_reason"] is not None for row in subset
        ):
            raise ProtocolStop("output_reconciliation_failure", "reason counts")
    return {
        "unit_rows": len(unit_rows),
        "stratum_rows": len(stratum_rows),
        "curve_rows": len(risk_rows),
        "aggregation_rows": len(aggregate_rows),
    }


def compute_outputs(
    config: dict[str, Any], freeze_receipt_id: str, freeze_after_revision: int
) -> dict[str, bytes]:
    topology = load_json(STAGE_7_3 / "evidence/topology-manifest-v1.json")
    if topology.get("status") != "frozen":
        raise ProtocolStop("identity_or_hash_mismatch", "topology not frozen")
    alpha_ledger = load_json(STAGE_7_3 / "evidence/fold-alpha-and-leakage-ledger-v1.json")
    input_view = load_json(STAGE_7_1 / "evidence/stage-7.2-direct-only-input-view-v1.json")
    support_audit = load_json(STAGE_7_1 / "evidence/observation-support-ledger-v1.json")
    evidence_manifest = load_json(
        STAGE_7_1 / "evidence/observation-evidence-manifest-v1.json"
    )
    frozen_inputs = {
        record["role"]: record for record in evidence_manifest["provenance"]["frozen_inputs"]
    }
    export_record = frozen_inputs.get("export_manifest_v3")
    if export_record is None:
        raise ProtocolStop("identity_or_hash_mismatch", "export manifest authority")
    export_path = STAGE_7_1 / export_record["relative_path"]
    ensure_hash(export_path, export_record["sha256"])
    export_manifest = load_json(export_path)
    cos_registry = load_json(STAGE_7_2 / "evidence/cos-i-registry-v1.json")
    mconf_registry = load_json(STAGE_7_2 / "evidence/mconf-registry-v1.json")

    target_grid = topology["target_grid"]
    terrain_valid, folds = read_terrain_valid(support_audit, target_grid), build_folds(topology)
    eligible = {row["acquisition_id"]: row for row in input_view["eligible_candidates"]}
    alpha_by_key = {
        (row["acquisition_id"], row["band"], int(row["fold_index"])): row
        for row in alpha_ledger["units"]
    }
    expected_alpha_keys = {
        (acquisition, band, int(fold["record"]["fold_index"]))
        for acquisition in eligible
        for band in BANDS
        for fold in folds
    }
    if len(alpha_by_key) != len(alpha_ledger["units"]) or set(alpha_by_key) != expected_alpha_keys:
        raise ProtocolStop("identity_or_hash_mismatch", "fold alpha unit identity set")
    stack_root = STAGE_7_1 / export_manifest["path_policy"]["root_relative_path"]
    stack_bands = export_manifest["execution"]["bands"]
    if tuple(stack_bands) != (
        "SR_B4", "SR_B5", "QA_PIXEL", "SR_B4_VALID", "SR_B5_VALID", "QA_PIXEL_VALID"
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "observation stack band order")
    locator = {
        row["acquisition_id"]: row["target_relative_to_alias"]
        for row in export_manifest["acquisitions"]
    }
    member_hash = {
        row["acquisition_id"]: row["member_sha256"]
        for row in evidence_manifest["members"]
    }
    cos_by_id = {row["acquisition_id"]: row for row in cos_registry["members"]}
    mconf_by_id = {row["acquisition_id"]: row for row in mconf_registry["members"]}
    if (
        len(locator) != len(export_manifest["acquisitions"])
        or len(member_hash) != len(evidence_manifest["members"])
        or len(cos_by_id) != len(cos_registry["members"])
        or len(mconf_by_id) != len(mconf_registry["members"])
        or not set(eligible) <= set(locator)
        or not set(eligible) <= set(member_hash)
        or not set(eligible) <= set(cos_by_id)
        or not set(eligible) <= set(mconf_by_id)
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "acquisition registry identity set")
    unit_rows, stratum_rows, risk_rows, scope_summaries = [], [], [], []

    for entry in sorted(export_manifest["acquisitions"], key=lambda row: row["order"]):
        acquisition = entry["acquisition_id"]
        if acquisition not in eligible:
            continue
        stack_path = stack_root / locator[acquisition]
        ensure_hash(stack_path, member_hash[acquisition])
        with rasterio.open(stack_path) as dataset:
            ensure_grid(dataset, target_grid, stack_path)
            if dataset.count != len(stack_bands):
                raise ProtocolStop("identity_or_hash_mismatch", f"stack bands: {acquisition}")
            data = {name: dataset.read(i + 1) for i, name in enumerate(stack_bands)}
        cos_record = cos_by_id[acquisition]
        cos_path = STAGE_7_2 / cos_record["output"]["relative_path"]
        ensure_hash(cos_path, cos_record["output"]["sha256"])
        with rasterio.open(cos_path) as dataset:
            ensure_grid(dataset, target_grid, cos_path)
            if (
                dataset.count != 1
                or dataset.dtypes[0] != cos_record["output"]["dtype"]
                or dataset.nodata != cos_record["output"]["nodata"]
            ):
                raise ProtocolStop("identity_or_hash_mismatch", f"cos_i bands: {acquisition}")
            cos_i = dataset.read(1)
        cos_missing = cos_i == FLOAT_NODATA
        cos_nonfinite = ~np.isfinite(cos_i)
        cos_valid = ~cos_missing & ~cos_nonfinite
        mconf_record = mconf_by_id[acquisition]
        mconf_path = STAGE_7_2 / mconf_record["relative_path"]
        ensure_hash(mconf_path, mconf_record["sha256"])
        with rasterio.open(mconf_path) as dataset:
            ensure_grid(dataset, target_grid, mconf_path)
            if dataset.count != 1 or dataset.dtypes[0] != "uint8" or dataset.nodata != 255:
                raise ProtocolStop("identity_or_hash_mismatch", f"Mconf bands: {acquisition}")
            mconf_raw = dataset.read(1)
        mconf = mconf_raw == 1
        expected_mconf = cos_valid & (cos_i > MCONF_THRESHOLD)
        if (
            np.any(~np.isin(mconf_raw, (0, 1, 255)))
            or np.any(mconf != expected_mconf)
            or np.any((mconf_raw == 255) != ~cos_valid)
        ):
            raise ProtocolStop("mconf_cos_i_inconsistency", acquisition)

        msource = (
            (data["SR_B4_VALID"] == 1)
            & (data["SR_B5_VALID"] == 1)
            & (data["QA_PIXEL_VALID"] == 1)
        )
        rho = {
            band: data[band].astype("float64") * SR_SCALE + SR_OFFSET
            for band in BANDS
        }
        in_range = np.ones_like(msource, dtype=bool)
        for band in BANDS:
            in_range &= (
                np.isfinite(rho[band]) & (rho[band] >= SR_MIN) & (rho[band] <= SR_MAX)
            )
        qa = data["QA_PIXEL"]
        qa_clear = (qa & QA_CLEAR_MASK) == 0
        water = ((qa >> QA_WATER_BIT) & 1) == 1
        base_valid_land = msource & qa_clear & in_range & terrain_valid & ~water
        if int(base_valid_land.sum()) != int(eligible[acquisition]["base_valid_land_count"]):
            raise ProtocolStop("coverage_identity_failure", f"base-valid count: {acquisition}")
        if np.any(base_valid_land & cos_missing):
            raise ProtocolStop("base_valid_land_cos_i_missing", acquisition)
        if np.any(base_valid_land & cos_nonfinite):
            raise ProtocolStop("base_valid_land_cos_i_nonfinite", acquisition)
        if np.any(base_valid_land & ((cos_i < -1.0) | (cos_i > 1.0))):
            raise ProtocolStop("base_valid_land_cos_i_outside_minus1_plus1", acquisition)
        strata = classify_strata(cos_i, check_domain=base_valid_land)
        mu = np.maximum(cos_i.astype("float64"), 0.0)
        proxy = risk_proxy_from_cos_i(cos_i)

        for fold in folds:
            fold_index, core = int(fold["record"]["fold_index"]), fold["core"]
            total = int(core.sum())
            base_core = base_valid_land & core
            scored = base_core & mconf
            base_count, scored_count = int(base_core.sum()), int(scored.sum())
            coverage_values(total, base_count, scored_count)
            scored_partition_count = sum(
                int((scored & strata[name]).sum())
                for name in ("mu_band_low", "mu_band_mid", "mu_band_high")
            )
            if scored_partition_count != scored_count:
                raise ProtocolStop("coverage_identity_failure", f"scored partition: {acquisition}")
            for band in BANDS:
                alpha_row = alpha_by_key[(acquisition, band, fold_index)]
                if alpha_row.get("state") not in {"fitted", "unsupported_calibration"}:
                    raise ProtocolStop(
                        "identity_or_hash_mismatch", f"alpha state: {acquisition}|{band}|{fold_index}"
                    )
                if (
                    alpha_row.get("split") != eligible[acquisition]["split"]
                    or alpha_row.get("core_id") != fold["record"]["core_id"]
                ):
                    raise ProtocolStop(
                        "identity_or_hash_mismatch", f"alpha identity: {acquisition}|{band}|{fold_index}"
                    )
                fitted = alpha_row["state"] == "fitted"
                accounting = alpha_row["holdout_core_accounting"]
                expected_accounting = {
                    "core_total_pixels": total,
                    "upstream_valid_pixels": base_count,
                    "scored_pixels": scored_count,
                    "unsupported_by_direct_only_pixels": base_count - scored_count,
                }
                if any(accounting.get(key) != value for key, value in expected_accounting.items()):
                    raise ProtocolStop(
                        "coverage_identity_failure", f"fold ledger counts: {acquisition}|{band}|{fold_index}"
                    )
                if fitted:
                    alpha_value = alpha_row.get("alpha_fold_safe")
                    if (
                        alpha_value is None
                        or not np.isfinite(alpha_value)
                        or not 0.0 <= float(alpha_value) <= 1.0
                        or alpha_row.get("fallback_receipt") is not None
                    ):
                        raise ProtocolStop(
                            "identity_or_hash_mismatch", f"fitted alpha: {acquisition}|{band}|{fold_index}"
                        )
                elif (
                    alpha_row.get("alpha_fold_safe") is not None
                    or alpha_row.get("fallback_receipt") is None
                ):
                    raise ProtocolStop(
                        "identity_or_hash_mismatch", f"unsupported alpha: {acquisition}|{band}|{fold_index}"
                    )
                gate_scored = fitted and scored_count > 0
                terminal = (
                    "scored"
                    if gate_scored
                    else "unsupported_calibration"
                    if not fitted
                    else "not_scored_no_supported_pixel"
                )
                top_reason = (
                    None
                    if gate_scored
                    else "unsupported_calibration"
                    if not fitted
                    else "no_supported_pixel_in_core"
                )
                alpha_fallback = alpha_row.get("fallback_receipt")
                fallback = None
                if not gate_scored:
                    fallback = (
                        {**alpha_fallback, "fallback_used": False}
                        if alpha_fallback is not None
                        else {
                            "reason_code": "no_supported_pixel_in_core",
                            "fallback_used": False,
                            "imputed": False,
                            "default_alpha_written": False,
                            "reference_alpha_fallback": False,
                        }
                    )
                identity = {
                    "acquisition": acquisition,
                    "split": eligible[acquisition]["split"],
                    "band": band,
                    "fold": fold_index,
                }
                unit_rows.append({
                    **identity,
                    "unit_gate_state": "scored" if gate_scored else "not_scored",
                    "unit_terminal_category": terminal,
                    "top_level_reason": top_reason,
                    "detail_reason": (
                        alpha_fallback.get("reason_code") if alpha_fallback else None
                    ),
                    "core_total_pixel_count": total,
                    "base_valid_land_count": base_count,
                    "scope_scored_pixel_counts": {
                        scope: int(scope_mask(scope, scored, strata).sum())
                        for scope in SCOPES
                    },
                    "fallback_receipt": fallback,
                    "upstream_identity": {
                        "fold_alpha_ledger_sha256":
                            config["upstream_bindings"]["stage_7_3_fold_alpha_leakage_ledger"]["sha256"],
                        "observation_member_sha256": member_hash[acquisition],
                        "cos_i_sha256": cos_record["output"]["sha256"],
                        "mconf_sha256": mconf_record["sha256"],
                    },
                })
                residual = np.full(cos_i.shape, np.nan, dtype="float64")
                if gate_scored:
                    residual[scored] = (
                        float(alpha_row["alpha_fold_safe"]) * mu[scored] - rho[band][scored]
                    )
                    if np.any(~np.isfinite(residual[scored])):
                        raise ProtocolStop(
                            "supported_residual_nonfinite", f"{acquisition}|{band}|{fold_index}"
                        )
                for stratum in STRATA:
                    footprint = core & strata[stratum]
                    local_base, local_scored = base_core & strata[stratum], scored & strata[stratum]
                    count, metrics = int(local_scored.sum()), None
                    if gate_scored and count:
                        values = residual[local_scored]
                        metrics = {
                            "signed_bias": float(values.mean()),
                            "MAE": float(np.abs(values).mean()),
                            "P90_absolute_residual":
                                float(np.percentile(np.abs(values), 90)),
                        }
                    terminal_admissible = (
                        gate_scored
                        and count >= int(
                            config["M2_guards"]["accepted_n_min_per_admissible_exact_point"]
                        )
                    )
                    stratum_rows.append({
                        **identity,
                        "stratum": stratum,
                        "core_total_pixel_count": total,
                        "base_valid_land_count": base_count,
                        "evidence_support_coverage": base_count / total,
                        "stratum_footprint_count": int(footprint.sum()),
                        "stratum_base_valid_count": int(local_base.sum()),
                        "stratum_scored_count": count,
                        "scoring_coverage": count / base_count if base_count else None,
                        "selective_prediction_coverage":
                            (
                                count / base_count
                                if base_count and terminal_admissible
                                else 0.0
                                if base_count and count == 0
                                else None
                            ),
                        "status": (
                            "scored"
                            if stratum in config["strata"]["scored"] and gate_scored and count
                            else "by_design_unsupported"
                            if stratum in config["strata"]["by_design_unsupported"]
                            else "not_scored"
                        ),
                        "supported_residual_metrics": metrics,
                    })
                for scope in SCOPES:
                    mask = scope_mask(scope, scored, strata)
                    result = evaluate_scope(
                        proxy[mask] if gate_scored else np.array([], dtype="float32"),
                        residual[mask] if gate_scored else np.array([], dtype="float64"),
                        total,
                        base_count,
                        config,
                        unit_gate_scored=gate_scored,
                    )
                    rows, summary = curve_records(
                        identity, scope, config["curve_scopes"]["roles"][scope], result
                    )
                    risk_rows.extend(rows)
                    scope_summaries.append(summary)

    expected_units = len(eligible) * len(BANDS) * len(folds)
    if len(unit_rows) != expected_units:
        raise ProtocolStop("output_reconciliation_failure", "unit count")
    reason_closed_set = [
        reason
        for reasons in config["verdict"]["not_evaluable_reason_closed_set"].values()
        for reason in reasons
    ]
    aggregate_rows = aggregate_scope_summaries(
        scope_summaries,
        config["verdict"]["risk_proxy_verdict_closed_set"],
        reason_closed_set,
    )
    common = {
        "method_pack": "M2_guarded_5pct_v3",
        "protocol": "docs/risk-proxy-protocol-v2.md",
        "config": "configs/risk-proxy-config-v2.json",
        "freeze_receipt_id": freeze_receipt_id,
        "freeze_after_route_revision": freeze_after_revision,
    }
    logical = {
        "unit_status_ledger": {
            "schema": config["outputs"]["unit_status_ledger"]["schema"],
            **common,
            "rows": unit_rows,
        },
        "stratum_table": {
            "schema": config["outputs"]["stratum_table"]["schema"],
            **common,
            "rows": stratum_rows,
        },
        "risk_curve_table": {
            "schema": config["outputs"]["risk_curve_table"]["schema"],
            **common,
            "rows": risk_rows,
        },
        "aggregation_table": {
            "schema": config["outputs"]["aggregation_table"]["schema"],
            **common,
            "rows": aggregate_rows,
        },
    }
    reconciliation_counts = validate_generated_tables(config, logical)
    encoded = {name: json_bytes(value) for name, value in logical.items()}
    report_counts = [
        {"band": row["band"], "scope": row["curve_scope"],
         "counts": row["risk_proxy_verdict_counts"]}
        for row in aggregate_rows
    ]
    encoded["scientific_report"] = (
        "# Stage 7.4 residual reliability report\n\n"
        "## single_roi_non_independent_boundary\n\n"
        "仅为单 ROI、共享标定支持且 fold 非独立的描述性 model-adequacy 基线。\n\n"
        "## residual_exposure_boundary\n\n"
        f"冻结回执 {freeze_receipt_id}（route {freeze_after_revision}）读回后首次读取结果。\n\n"
        "## primary_and_secondary_curves\n\n"
        "unit_all_scored 为 primary；三个 mu band 为 secondary。\n\n"
        "## permanent_abstention_ledger\n\n"
        "self_shadow 与 near_zero 永久 abstention，仍留在 base_valid_land 分母。\n\n"
        "## five_state_verdict_counts\n\n"
        + json.dumps(report_counts, ensure_ascii=False, sort_keys=True)
        + "\n\n## not_evaluated_claims\n\n"
        "不声称概率、校准置信度、统计显著性、跨域泛化或独立确认。\n\n"
        "## output_hash_reconciliation\n\n"
        "完成字节哈希见 reconciliation manifest。\n"
    ).encode("utf-8")
    report_text = encoded["scientific_report"].decode("utf-8")
    for section in config["outputs"]["scientific_report"]["required_sections"]:
        if f"## {section}" not in report_text:
            raise ProtocolStop("output_reconciliation_failure", f"report section {section}")
    completed_hashes = {
        name: sha256_bytes(payload) for name, payload in sorted(encoded.items())
    }
    encoded["reconciliation_manifest"] = json_bytes({
        "schema": config["outputs"]["reconciliation_manifest"]["schema"],
        **common,
        "member_hash_reconciliation": "pass",
        "mask_reconciliation": "pass",
        "unit_terminal_state_reconciliation": "pass",
        "coverage_denominator_reconciliation": "pass",
        "fold_ledger_reconciliation": "pass",
        "verdict_reconciliation": "pass",
        "completed_output_hashes": completed_hashes,
        "completed_output_hash_scope": "all five non-self members; manifest self hash is reported by the executor and PF3 asset receipt",
        "counts": reconciliation_counts,
    })
    return encoded


def publish_outputs(config: dict[str, Any], payloads: dict[str, bytes]) -> dict[str, str]:
    targets = {
        name: resolve_bound_path(record)
        for name, record in config["outputs"].items()
        if isinstance(record, dict) and "relative_path" in record
    }
    if set(targets) != set(payloads):
        raise ProtocolStop("output_reconciliation_failure", "logical output set")
    if any(path.exists() for path in targets.values()):
        raise ProtocolStop("output_reconciliation_failure", "output exists")
    with tempfile.TemporaryDirectory(prefix="stage7.4-risk-proxy-") as tmp:
        staged = {}
        for name, payload in payloads.items():
            path = Path(tmp) / name
            path.write_bytes(payload)
            staged[name] = path
        for target in targets.values():
            target.parent.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []
        try:
            for name, target in targets.items():
                os.link(staged[name], target)
                created.append(target)
        except OSError as exc:
            rollback_failures = []
            for target in reversed(created):
                try:
                    target.unlink()
                except OSError as rollback_exc:
                    rollback_failures.append(f"{target}: {rollback_exc}")
            detail = f"atomic publication failed: {exc}"
            if rollback_failures:
                detail += "; rollback failures: " + " | ".join(rollback_failures)
            raise ProtocolStop("output_reconciliation_failure", detail) from exc
    return {name: sha256_file(path) for name, path in targets.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "execute"):
        command = subparsers.add_parser(name)
        command.add_argument("--protocol", type=Path, required=True)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--preflight", type=Path, required=True)
        command.add_argument("--audit", type=Path, required=True)
        command.add_argument("--protocol-sha256", required=True)
        command.add_argument("--config-sha256", required=True)
        command.add_argument("--preflight-sha256", required=True)
        command.add_argument("--audit-sha256", required=True)
    execute = subparsers.choices["execute"]
    execute.add_argument("--freeze-receipt-id", required=True)
    execute.add_argument("--freeze-after-revision", type=int, required=True)
    execute.add_argument("--confirm-freeze-readback", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    check = verify_contract(
        args.protocol.resolve(),
        args.config.resolve(),
        args.preflight.resolve(),
        args.audit.resolve(),
        args.protocol_sha256,
        args.config_sha256,
        args.preflight_sha256,
        args.audit_sha256,
        require_outputs_absent=True,
    )
    if args.command == "verify":
        print(json.dumps(check, ensure_ascii=False, sort_keys=True))
        return 0
    if not args.confirm_freeze_readback:
        raise SystemExit("stop: --confirm-freeze-readback required after real PF3 readback")
    preflight = load_json(args.preflight.resolve())
    prefreeze_revision = int(preflight["pf3_snapshot_binding"]["live_route_revision"])
    if (
        args.freeze_after_revision <= prefreeze_revision
        or not args.freeze_receipt_id.startswith("rc_")
    ):
        raise ProtocolStop("identity_or_hash_mismatch", "PF3 freeze readback identity")
    config = load_json(args.config.resolve())
    payloads = compute_outputs(config, args.freeze_receipt_id, args.freeze_after_revision)
    hashes = publish_outputs(config, payloads)
    print(json.dumps({"status": "completed", "output_sha256": hashes},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProtocolStop as exc:
        print(json.dumps({"status": "protocol_error", "reason": exc.reason,
                          "detail": exc.detail}, ensure_ascii=False, sort_keys=True))
        raise SystemExit(2)
