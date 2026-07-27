#!/usr/bin/env python3
"""Fail-closed static auditor for the Stage 7.1 Export Manifest.

This program reads local JSON only. It cannot authenticate to Earth Engine,
create an Export task, write an asset, or download imagery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_SCHEMA = "mountainrs-stage7.1-export-manifest-v1"
CATALOG_SCHEMA = "mountainrs-stage7.1-acquisition-catalog-v1"
REQUEST_ID = "mountainrs-stage7.1-export-manifest-v1"
V5_REQUEST_SHA256 = (
    "980f11b36593ca5b7c8b0504cdec2584465ac77d09f43b273476dc4eb94fbd5d"
)
UNIVERSE_SHA256 = (
    "15d5522991f9ff7eddba2f6983603f19b906026cceb4954579a892e6bd1bfe60"
)
CATALOG_SHA256 = (
    "742275e25644c36da35a6ccf20e18a3e18703707b30d2ab55169cfe1579c8dda"
)
EXPECTED_BANDS = ["SR_B4", "SR_B5", "QA_PIXEL"]
EXPECTED_GRID = {
    "grid_id": "shadow-risk-b-b4-grid-v1",
    "crs": "EPSG:32648",
    "transform": [30.0, 0.0, 292230.0, 0.0, -30.0, 3473790.0],
    "shape": {"height": 752, "width": 650},
    "bounds": [292230.0, 3451230.0, 311730.0, 3473790.0],
    "resolution": [30.0, 30.0],
    "pixel_count": 488800,
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHORT_ID_RE = re.compile(r"^LC08_130038_2023[0-1][0-9][0-3][0-9]$")


class ManifestError(ValueError):
    """The preregistration violates a frozen Stage 7.1 boundary."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def universe_sha256(acquisition_ids: list[str]) -> str:
    return hashlib.sha256(canonical_json(acquisition_ids).encode("utf-8")).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def validate_relative_path(value: str, expected: str) -> None:
    path = PurePosixPath(value)
    require(not path.is_absolute(), f"absolute path is prohibited: {value}")
    require(".." not in path.parts, f"parent traversal is prohibited: {value}")
    require(value == expected, f"unexpected relative path: {value}")


def validate_catalog(catalog: dict[str, Any], catalog_path: Path) -> list[dict[str, Any]]:
    require(catalog.get("schema") == CATALOG_SCHEMA, "catalog schema drift")
    require(sha256_file(catalog_path) == CATALOG_SHA256, "catalog file hash drift")
    counts = catalog.get("counts")
    require(
        counts == {"cataloged": 21, "exportable": 21, "incomplete": 0},
        "catalog counts drift",
    )
    candidates = catalog.get("candidates")
    require(isinstance(candidates, list) and len(candidates) == 21, "catalog must contain 21 candidates")
    ordered = sorted(
        candidates,
        key=lambda item: (item["system_time_start_utc"], item["earth_engine_asset_id"]),
    )
    require(candidates == ordered, "catalog candidate order drift")
    ids = [item["acquisition_id"] for item in candidates]
    require(len(ids) == len(set(ids)), "duplicate catalog acquisition identity")
    require(universe_sha256(ids) == UNIVERSE_SHA256, "catalog universe hash drift")
    for item in candidates:
        require(item.get("cataloged") is True, "non-cataloged universe member")
        require(item.get("exportable") is True, "non-exportable universe member")
        require(item.get("stack_eligible") == "not_yet_evaluated", "stack eligibility was adjudicated")
        require(item.get("formal_split") is None, "formal split was assigned")
    return candidates


def validate_manifest(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    catalog_path: Path,
) -> dict[str, Any]:
    candidates = validate_catalog(catalog, catalog_path)
    require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema drift")
    require(manifest.get("request_id") == REQUEST_ID, "request identity drift")
    require(manifest.get("manifest_version") == 1, "manifest version drift")
    require(manifest.get("status") == "preregistered", "manifest is not preregistered")

    source = manifest.get("source_evidence", {})
    require(source.get("v5_request_sha256") == V5_REQUEST_SHA256, "V5 request hash drift")
    require(source.get("universe_sha256") == UNIVERSE_SHA256, "universe anchor drift")
    require(source.get("catalog_sha256") == CATALOG_SHA256, "catalog anchor drift")
    require(source.get("export_set_policy") == "complete_v5_universe_all_21", "export set is not the full universe")

    authorization = manifest.get("authorization", {})
    require(authorization.get("exports_allowed") is True, "future export permission marker missing")
    require(authorization.get("task_creation_authorized_this_run") is False, "preregistration run cannot create tasks")
    require(authorization.get("tasks_created") == 0, "manifest records an Export task")
    require(authorization.get("assets_created") == 0, "manifest records an asset")

    execution = manifest.get("execution", {})
    require(execution.get("operation") == "Export.image.toDrive", "unexpected export channel")
    require(execution.get("task_granularity") == "one_acquisition_one_task_one_three_band_geotiff", "task granularity drift")
    require(execution.get("maximum_active_exports") == 1, "active Export limit must be one")
    require(execution.get("file_format") == "GeoTIFF", "file format drift")
    require(execution.get("bands") == EXPECTED_BANDS, "band order or membership drift")
    require(execution.get("apply_scale_offset") is False, "raw DN must not be scaled during export")
    require(execution.get("best_effort") is False, "bestEffort is prohibited")
    require(execution.get("resampling") == "nearest_neighbor_default", "resampling drift")
    require(execution.get("explicit_resample_call") is False, "resample call is prohibited")
    require(execution.get("unmask") is False, "unmask is prohibited")
    require(execution.get("format_options_no_data") == "omitted", "shared nodata must be omitted")
    require(execution.get("skip_empty_tiles") is False, "one task must produce one complete file")

    require(manifest.get("target_grid") == EXPECTED_GRID, "target grid drift")
    encoding = manifest.get("raw_encoding", {})
    require(encoding.get("dtype") == "uint16", "all raw bands must remain uint16")
    require(encoding.get("qa_zero_is_valid") is True, "legal QA zero was not preserved")
    require(encoding.get("qa_fill_bit") == 0, "QA fill bit drift")
    require(encoding.get("source_mask_preflight_required") is True, "source-mask preflight is missing")
    require(encoding.get("source_masks_must_be_all_valid") is True, "single-file lossless mask gate is missing")
    require(encoding.get("mask_failure_action") == "stop_before_task_no_split_or_extra_band", "mask failure is not fail-closed")
    require(encoding.get("local_nodata_expected") is None, "local nodata must remain unset")

    path_policy = manifest.get("path_policy", {})
    require(path_policy.get("root_alias") == "stage_7_1_observation_stack", "output Alias drift")
    require(path_policy.get("root_relative_path") == "stage7_real_weak_closure/stage7_1_observation_stack/data/raw/observation_stack", "registry-resolved root drift")
    require(path_policy.get("absolute_paths_allowed") is False, "absolute paths must be prohibited")
    require(path_policy.get("overwrite_existing_target") is False, "overwrite must be prohibited")

    lifecycle = manifest.get("lifecycle", {})
    require(lifecycle.get("unknown_allows_resubmit") is False, "unknown outcome must block resubmission")
    require(lifecycle.get("retry_only_after_terminal_failed") is True, "retry gate drift")
    require(lifecycle.get("preserve_all_task_id_lineage") is True, "task lineage must be preserved")
    require(lifecycle.get("active_or_submitted_is_success") is False, "submission was confused with success")
    require(lifecycle.get("succeeded_requires_local_hash_and_reconciliation") is True, "success reconciliation gate missing")

    entries = manifest.get("acquisitions")
    require(isinstance(entries, list) and len(entries) == 21, "manifest must contain 21 acquisitions")
    expected_ids = [item["acquisition_id"] for item in candidates]
    actual_ids = [item.get("acquisition_id") for item in entries]
    require(actual_ids == expected_ids, "manifest acquisition set or order drift")
    require(len(actual_ids) == len(set(actual_ids)), "duplicate manifest acquisition")

    output_paths: set[str] = set()
    idempotency_seeds: set[str] = set()
    for order, (entry, candidate) in enumerate(zip(entries, candidates, strict=True), start=1):
        short_id = candidate["system_index"]
        require(SHORT_ID_RE.fullmatch(short_id) is not None, f"invalid short product ID: {short_id}")
        require(entry.get("order") == order, f"order drift for {short_id}")
        require(entry.get("short_product_id") == short_id, f"short product ID drift for {short_id}")
        require(entry.get("system_time_start_utc") == candidate["system_time_start_utc"], f"timestamp drift for {short_id}")
        expected_path = f"{short_id}/{short_id}__SR_B4_SR_B5_QA_PIXEL.tif"
        relative_path = entry.get("target_relative_to_alias")
        require(isinstance(relative_path, str), f"missing target path for {short_id}")
        validate_relative_path(relative_path, expected_path)
        require(relative_path not in output_paths, f"output path collision: {relative_path}")
        output_paths.add(relative_path)
        seed = f"{REQUEST_ID}:{entry['acquisition_id']}:attempt-1"
        require(entry.get("first_attempt_idempotency_seed") == seed, f"idempotency seed drift for {short_id}")
        require(seed not in idempotency_seeds, f"duplicate idempotency seed for {short_id}")
        idempotency_seeds.add(seed)
        require(entry.get("state") == "not_requested", f"unexpected task state for {short_id}")
        require(entry.get("attempts") == [], f"task lineage must be empty at preregistration for {short_id}")
        require(entry.get("source_mask_preflight") == "not_yet_evaluated", f"mask preflight was adjudicated for {short_id}")
        require(entry.get("stack_eligible") == "not_yet_evaluated", f"stack eligibility changed for {short_id}")
        require(entry.get("split") == "not_yet_assigned", f"split assigned for {short_id}")

    backfill = manifest.get("attempt_backfill_schema", {})
    require(backfill.get("task_id") == "required_real_value", "real task ID backfill is not required")
    require(backfill.get("asset_id") == "not_applicable_for_drive_export", "asset boundary drift")
    require(backfill.get("output_sha256") == "required_after_local_file", "output hash backfill is not required")
    require(backfill.get("status_history") == "append_only", "status history must be append-only")
    require(backfill.get("allowed_states") == ["submitted", "running", "succeeded", "failed", "cancelled", "unknown"], "attempt states drift")

    return {
        "status": "passed",
        "schema": MANIFEST_SCHEMA,
        "request_id": REQUEST_ID,
        "acquisition_count": len(entries),
        "universe_sha256": universe_sha256(actual_ids),
        "unique_output_paths": len(output_paths),
        "unique_idempotency_seeds": len(idempotency_seeds),
        "tasks_created": 0,
        "assets_created": 0,
        "stack_eligible": "not_yet_evaluated",
        "split": "not_yet_assigned",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = validate_manifest(
        load_json(args.manifest),
        load_json(args.catalog),
        args.catalog,
    )
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
