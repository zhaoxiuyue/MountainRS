#!/usr/bin/env python3
"""Fail-closed local auditor for the Stage 7.1 v2 mask-preserving manifest.

The program reads local evidence only.  It cannot authenticate to Earth Engine,
submit an Export task, create an asset, or download imagery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_SCHEMA = "mountainrs-stage7.1-export-manifest-v2"
CATALOG_SCHEMA = "mountainrs-stage7.1-acquisition-catalog-v1"
CAUSAL_AUDIT_SCHEMA = "mountainrs-stage7.1-source-mask-causal-audit-v1"
REQUEST_ID = "mountainrs-stage7.1-export-manifest-v2"
UNIVERSE_SHA256 = "15d5522991f9ff7eddba2f6983603f19b906026cceb4954579a892e6bd1bfe60"
CATALOG_SHA256 = "742275e25644c36da35a6ccf20e18a3e18703707b30d2ab55169cfe1579c8dda"
V5_REQUEST_SHA256 = "980f11b36593ca5b7c8b0504cdec2584465ac77d09f43b273476dc4eb94fbd5d"
V1_MANIFEST_SHA256 = "596171933511530ff1ecc20f07e6fc4a0c3258f01c68cff57046749af991ca25"
CAUSAL_AUDIT_SHA256 = "450ba6d1f5e8d1aa31f2afbb3c2fcdab673a764c7a37716ff36903ac103328db"
EXPECTED_GRID = {
    "grid_id": "shadow-risk-b-b4-grid-v1",
    "crs": "EPSG:32648",
    "transform": [30.0, 0.0, 292230.0, 0.0, -30.0, 3473790.0],
    "shape": {"height": 752, "width": 650},
    "bounds": [292230.0, 3451230.0, 311730.0, 3473790.0],
    "resolution": [30.0, 30.0],
    "pixel_count": 488800,
}
RAW_BANDS = ["SR_B4", "SR_B5", "QA_PIXEL"]
VALID_BANDS = ["SR_B4_VALID", "SR_B5_VALID", "QA_PIXEL_VALID"]
EXPECTED_BANDS = RAW_BANDS + VALID_BANDS
SHORT_ID_RE = re.compile(r"^LC08_130038_2023[0-1][0-9][0-3][0-9]$")


class ManifestError(ValueError):
    """The v2 preregistration violates a frozen Stage 7.1 boundary."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def universe_sha256(acquisition_ids: list[str]) -> str:
    return hashlib.sha256(canonical_json(acquisition_ids).encode("utf-8")).hexdigest()


def validate_relative_path(value: Any, expected: str) -> None:
    require(isinstance(value, str), "required path is missing")
    path = PurePosixPath(value)
    require(not path.is_absolute(), f"absolute path is prohibited: {value}")
    require(".." not in path.parts, f"parent traversal is prohibited: {value}")
    require(value == expected, f"unexpected relative path: {value}")


def validate_catalog(catalog: dict[str, Any], catalog_path: Path) -> list[dict[str, Any]]:
    require(catalog.get("schema") == CATALOG_SCHEMA, "catalog schema drift")
    require(sha256_file(catalog_path) == CATALOG_SHA256, "catalog file hash drift")
    require(catalog.get("counts") == {"cataloged": 21, "exportable": 21, "incomplete": 0}, "catalog counts drift")
    candidates = catalog.get("candidates")
    require(isinstance(candidates, list) and len(candidates) == 21, "catalog must contain 21 candidates")
    ordered = sorted(candidates, key=lambda item: (item["system_time_start_utc"], item["earth_engine_asset_id"]))
    require(candidates == ordered, "catalog candidate order drift")
    ids = [item.get("acquisition_id") for item in candidates]
    require(all(isinstance(item, str) for item in ids), "catalog acquisition identity is missing")
    require(len(ids) == len(set(ids)), "duplicate catalog acquisition identity")
    require(universe_sha256(ids) == UNIVERSE_SHA256, "catalog universe hash drift")
    for candidate in candidates:
        require(candidate.get("cataloged") is True, "non-cataloged universe member")
        require(candidate.get("exportable") is True, "non-exportable universe member")
        require(candidate.get("stack_eligible") == "not_yet_evaluated", "catalog eligibility was adjudicated")
        require(candidate.get("formal_split") is None, "catalog split was assigned")
    return candidates


def validate_causal_audit(audit: dict[str, Any], audit_path: Path, candidates: list[dict[str, Any]]) -> None:
    require(sha256_file(audit_path) == CAUSAL_AUDIT_SHA256, "causal audit hash drift")
    require(audit.get("schema") == CAUSAL_AUDIT_SCHEMA, "causal audit schema drift")
    boundary = audit.get("operation_boundary")
    require(isinstance(boundary, dict), "causal audit operation boundary missing")
    for field in ("export_tasks_created", "assets_created", "imagery_downloaded"):
        require(boundary.get(field) == 0, "causal audit was not read-only")
    require(boundary.get("stack_eligibility_changed") is False, "causal audit changed eligibility")
    records = audit.get("records")
    require(isinstance(records, list) and len(records) == 21, "causal audit must contain 21 records")
    expected_ids = [candidate["acquisition_id"] for candidate in candidates]
    require([record.get("acquisition_id") for record in records] == expected_ids, "causal audit universe or order drift")
    for record in records:
        target = record.get("target_grid")
        require(isinstance(target, dict), "causal audit target-grid record missing")
        for band in RAW_BANDS:
            counts = target.get(band)
            require(isinstance(counts, dict), f"causal audit missing {band} counts")
            total = counts.get("target_pixel_count")
            one = counts.get("mask_one_count")
            zero = counts.get("mask_zero_count")
            require(total == EXPECTED_GRID["pixel_count"], "causal audit target-pixel total drift")
            require(isinstance(one, int) and isinstance(zero, int) and one + zero == total, "causal audit mask counts are inconsistent")


def validate_frozen_files(manifest: dict[str, Any], workspace_root: Path) -> None:
    frozen = manifest.get("frozen_contract")
    require(isinstance(frozen, dict), "frozen contract is missing")
    required = (
        ("selection_protocol_relative_path", "selection_protocol_sha256"),
        ("observation_schema_relative_path", "observation_schema_sha256"),
        ("target_grid_relative_path", "target_grid_sha256"),
        ("mask_preserving_protocol_relative_path", "mask_preserving_protocol_sha256"),
    )
    for relative_key, hash_key in required:
        relative = frozen.get(relative_key)
        expected_hash = frozen.get(hash_key)
        require(isinstance(relative, str) and isinstance(expected_hash, str), "frozen file anchor missing")
        validate_relative_path(relative, relative)
        path = workspace_root / relative
        require(path.is_file(), f"frozen file is missing: {relative}")
        require(sha256_file(path) == expected_hash, f"frozen file hash drift: {relative}")


def validate_historical_anchors(manifest: dict[str, Any], workspace_root: Path) -> None:
    source = manifest["source_evidence"]
    expected = (
        ("v5_request_relative_path", V5_REQUEST_SHA256),
        ("source_mask_causal_audit_relative_path", CAUSAL_AUDIT_SHA256),
    )
    for relative_key, expected_hash in expected:
        relative = source.get(relative_key)
        require(isinstance(relative, str), f"historical anchor path missing: {relative_key}")
        validate_relative_path(relative, relative)
        path = workspace_root / relative
        require(path.is_file(), f"historical anchor is missing: {relative}")
        require(sha256_file(path) == expected_hash, f"historical anchor hash drift: {relative}")
    v1_path = workspace_root / "evidence/export-manifest-v1.json"
    require(v1_path.is_file(), "v1 historical manifest is missing")
    require(sha256_file(v1_path) == V1_MANIFEST_SHA256, "v1 historical manifest hash drift")


def validate_manifest(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    catalog_path: Path,
    causal_audit: dict[str, Any],
    causal_audit_path: Path,
) -> dict[str, Any]:
    candidates = validate_catalog(catalog, catalog_path)
    validate_causal_audit(causal_audit, causal_audit_path, candidates)
    validate_frozen_files(manifest, catalog_path.parents[2])
    require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema drift")
    require(manifest.get("request_id") == REQUEST_ID, "manifest request identity drift")
    require(manifest.get("manifest_version") == 2, "manifest version drift")
    require(manifest.get("status") == "preregistered", "manifest is not preregistered")

    supersession = manifest.get("supersession")
    require(isinstance(supersession, dict), "supersession record missing")
    require(supersession.get("v1_manifest_sha256") == V1_MANIFEST_SHA256, "v1 historical anchor drift")
    require(supersession.get("v1_immutability") == "historical_anchor_do_not_rewrite", "v1 immutability boundary missing")
    source = manifest.get("source_evidence")
    require(isinstance(source, dict), "source evidence missing")
    require(source.get("v5_request_sha256") == V5_REQUEST_SHA256, "V5 request hash drift")
    require(source.get("catalog_sha256") == CATALOG_SHA256, "catalog anchor drift")
    require(source.get("universe_sha256") == UNIVERSE_SHA256, "universe anchor drift")
    require(source.get("export_set_policy") == "complete_v5_universe_all_21", "export set is not the full universe")
    require(source.get("export_set_is_stack_eligibility_decision") is False, "export was confused with eligibility")
    require(source.get("source_mask_causal_audit_sha256") == CAUSAL_AUDIT_SHA256, "M1 source-mask anchor drift")
    validate_historical_anchors(manifest, catalog_path.parents[2])

    authorization = manifest.get("authorization")
    require(isinstance(authorization, dict), "authorization is missing")
    require(authorization.get("exports_allowed") is True, "v2 execution marker missing")
    require(authorization.get("task_creation_authorized_when_preregistered") is False, "preregistration created task authority")
    require(authorization.get("tasks_created") == 0, "immutable manifest records a task")
    require(authorization.get("assets_created") == 0, "immutable manifest records an asset")
    require(authorization.get("imagery_created_or_downloaded") == 0, "immutable manifest records imagery")

    execution = manifest.get("execution")
    require(isinstance(execution, dict), "execution contract is missing")
    require(execution.get("operation") == "Export.image.toDrive", "unexpected export channel")
    require(execution.get("task_granularity") == "one_acquisition_one_task_one_six_band_geotiff", "task granularity drift")
    require(execution.get("maximum_active_exports") == 1, "active export limit must be one")
    require(execution.get("file_format") == "GeoTIFF", "file format drift")
    require(execution.get("expected_files_per_task") == 1, "file count per task drift")
    require(execution.get("bands") == EXPECTED_BANDS, "six-band order or membership drift")
    require(execution.get("apply_scale_offset") is False, "raw DN must not be scaled")
    require(execution.get("resampling") == "nearest_neighbor_default", "resampling drift")
    require(execution.get("explicit_resample_call") is False, "explicit resample call is prohibited")
    require(execution.get("scale_parameter") == "omitted", "scale is prohibited")
    require(execution.get("dimensions_parameter") == "omitted", "dimensions are prohibited")
    require(execution.get("best_effort") is False, "bestEffort is prohibited")
    require(execution.get("source_mask_extraction_before_serialization_fill") is True, "source mask must precede fill")
    require(execution.get("serialization_fill") == {"allowed": True, "value": 0, "scope": "only_after_source_mask_extraction_only_for_masked_data_pixels"}, "serialization-fill scope drift")
    require(execution.get("format_options_no_data") == "omitted", "shared nodata must be omitted")
    require(execution.get("skip_empty_tiles") is False, "complete output requirement drift")
    require(manifest.get("target_grid") == EXPECTED_GRID, "target grid drift")

    encoding = manifest.get("raw_encoding")
    require(isinstance(encoding, dict), "raw encoding is missing")
    require(encoding.get("dtype") == "uint16", "output dtype drift")
    require(encoding.get("raw_band_order") == RAW_BANDS, "raw band order drift")
    require(encoding.get("valid_band_order") == VALID_BANDS, "valid band order drift")
    require(encoding.get("valid_values") == [0, 1], "valid mask values drift")
    require(encoding.get("qa_zero_is_valid") is True, "legal QA zero was not preserved")
    require(encoding.get("qa_fill_bit") == 0, "QA fill bit drift")
    require(encoding.get("source_masks_must_be_explicitly_serialized") is True, "explicit source masks are required")
    require(encoding.get("local_nodata_expected") is None, "nodata must remain unset")

    path_policy = manifest.get("path_policy")
    require(isinstance(path_policy, dict), "path policy is missing")
    require(path_policy.get("root_alias") == "stage_7_1_observation_stack", "output Alias drift")
    require(path_policy.get("root_relative_path") == "data/raw/observation_stack", "output root drift")
    require(path_policy.get("absolute_paths_allowed") is False, "absolute paths must be prohibited")
    require(path_policy.get("overwrite_existing_target") is False, "overwrite must be prohibited")

    lifecycle = manifest.get("lifecycle")
    require(isinstance(lifecycle, dict), "lifecycle is missing")
    require(lifecycle.get("maximum_active_exports") == 1, "lifecycle active limit drift")
    require(lifecycle.get("unknown_allows_resubmit") is False, "unknown outcome must block resubmission")
    require(lifecycle.get("retry_only_after_terminal_failed") is True, "retry gate drift")
    require(lifecycle.get("preserve_all_task_id_lineage") is True, "task lineage must be preserved")
    require(lifecycle.get("status_history_is_append_only") is True, "status history must be append-only")
    require(lifecycle.get("active_or_submitted_is_success") is False, "submission was confused with success")
    require(lifecycle.get("succeeded_requires_local_hash_and_reconciliation") is True, "local reconciliation gate missing")

    entries = manifest.get("acquisitions")
    require(isinstance(entries, list) and len(entries) == 21, "manifest must contain 21 acquisitions")
    expected_ids = [candidate["acquisition_id"] for candidate in candidates]
    actual_ids = [entry.get("acquisition_id") for entry in entries]
    require(actual_ids == expected_ids, "manifest acquisition set or order drift")
    output_paths: set[str] = set()
    seeds: set[str] = set()
    for order, (entry, candidate) in enumerate(zip(entries, candidates, strict=True), start=1):
        short_id = candidate["system_index"]
        require(SHORT_ID_RE.fullmatch(short_id) is not None, f"invalid short product ID: {short_id}")
        require(entry.get("order") == order, f"order drift for {short_id}")
        require(entry.get("short_product_id") == short_id, f"short product identity drift for {short_id}")
        require(entry.get("system_time_start_utc") == candidate["system_time_start_utc"], f"timestamp drift for {short_id}")
        relative = entry.get("target_relative_to_alias")
        expected_path = f"{short_id}/{short_id}__SR_B4_SR_B5_QA_PIXEL__VALID.tif"
        validate_relative_path(relative, expected_path)
        require(relative not in output_paths, f"output path collision: {relative}")
        output_paths.add(relative)
        seed = f"{REQUEST_ID}:{candidate['acquisition_id']}:attempt-1"
        require(entry.get("first_attempt_idempotency_seed") == seed, f"idempotency seed drift for {short_id}")
        require(seed not in seeds, f"duplicate idempotency seed for {short_id}")
        seeds.add(seed)
        require(entry.get("state") == "not_requested", f"unexpected state for {short_id}")
        require(entry.get("attempts") == [], f"task lineage must be empty for {short_id}")
        require(entry.get("source_mask_preflight") == "m1_audited", f"M1 mask audit marker missing for {short_id}")
        require(entry.get("stack_eligible") == "not_yet_evaluated", f"eligibility changed for {short_id}")
        require(entry.get("split") == "not_yet_assigned", f"split changed for {short_id}")

    state = manifest.get("state_boundary")
    require(isinstance(state, dict), "state boundary is missing")
    require(state.get("stack_eligible") == "not_yet_evaluated", "global eligibility changed")
    require(state.get("eligibility_thresholds_added_by_v2") is False, "v2 invented an eligibility threshold")
    require(state.get("split") == "not_yet_assigned", "global split changed")
    require(state.get("model_eligible") == "not_adjudicated_stage_7_2", "model boundary drift")
    return {
        "status": "passed",
        "schema": MANIFEST_SCHEMA,
        "request_id": REQUEST_ID,
        "acquisition_count": len(entries),
        "universe_sha256": universe_sha256(actual_ids),
        "unique_output_paths": len(output_paths),
        "unique_idempotency_seeds": len(seeds),
        "tasks_created": 0,
        "assets_created": 0,
        "stack_eligible": "not_yet_evaluated",
        "split": "not_yet_assigned",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--causal-audit", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = validate_manifest(
        load_json(args.manifest),
        load_json(args.catalog),
        args.catalog,
        load_json(args.causal_audit),
        args.causal_audit,
    )
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
