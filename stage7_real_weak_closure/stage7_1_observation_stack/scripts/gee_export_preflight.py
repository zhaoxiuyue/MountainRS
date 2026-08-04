#!/usr/bin/env python3
"""Read-only Stage 7.1 source-mask preflight for the frozen export universe.

This program authenticates only through the official Earth Engine client, runs
per-acquisition mask reductions, and writes one new evidence file.  It never
creates an Earth Engine task or asset, downloads imagery, or rewrites the
immutable Export Manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REQUIRED_BANDS = ("SR_B4", "SR_B5", "QA_PIXEL")
MASK_REDUCTION_BAND_COUNT = len(REQUIRED_BANDS)
EVIDENCE_SCHEMA = "mountainrs-stage7.1-source-mask-preflight-v1"


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
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_sibling_module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_mask_measurements(
    counts: dict[str, Any],
    minimums: dict[str, Any],
    pixel_count: int,
) -> dict[str, Any]:
    bands: dict[str, dict[str, Any]] = {}
    for band in REQUIRED_BANDS:
        count = counts.get(band)
        minimum = minimums.get(band)
        bands[band] = {
            "valid_source_mask_pixel_count": count,
            "source_mask_minimum": minimum,
            "all_valid": count == pixel_count and minimum == 1,
        }
    return {
        "bands": bands,
        "source_masks_all_valid": all(item["all_valid"] for item in bands.values()),
    }


def mask_reduction_max_pixels(pixel_count: int) -> int:
    return pixel_count * MASK_REDUCTION_BAND_COUNT


def query_source_masks(ee: Any, acquisition_id: str, grid: dict[str, Any]) -> dict[str, Any]:
    image = ee.Image(acquisition_id).select(list(REQUIRED_BANDS))
    region = ee.Geometry.Rectangle(grid["bounds"], grid["crs"], False)
    masks = image.mask()
    reduction = {
        "geometry": region,
        "crs": grid["crs"],
        "crsTransform": grid["transform"],
        # reduceRegion counts pixels across all three source-mask bands.  This
        # is a read-only accounting limit, not an Export scale change.
        "maxPixels": mask_reduction_max_pixels(grid["pixel_count"]),
        "bestEffort": False,
    }
    counts = masks.reduceRegion(ee.Reducer.count(), **reduction).getInfo()
    minimums = masks.reduceRegion(ee.Reducer.min(), **reduction).getInfo()
    if not isinstance(counts, dict) or not isinstance(minimums, dict):
        raise RuntimeError(f"source-mask reduction returned invalid data for {acquisition_id}")
    return evaluate_mask_measurements(counts, minimums, grid["pixel_count"])


def atomic_create_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(canonical_json(value) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run_preflight(args: argparse.Namespace) -> dict[str, Any]:
    auditor = load_sibling_module("stage7_1_export_manifest_auditor", "audit_export_manifest.py")
    executor = load_sibling_module("stage7_1_catalog_executor", "gee_catalog_audit.py")
    manifest_path = Path(args.manifest)
    catalog_path = Path(args.catalog)
    manifest = load_json(manifest_path)
    catalog = load_json(catalog_path)
    audit = auditor.validate_manifest(manifest, catalog, catalog_path)
    project_id = executor.read_project_id(Path(args.project_config))
    attestation, live_probe = executor.verify_authenticated_session(
        Path(args.attestation), project_id
    )

    import ee

    grid = manifest["target_grid"]
    records = []
    for entry in manifest["acquisitions"]:
        records.append(
            {
                "order": entry["order"],
                "acquisition_id": entry["acquisition_id"],
                "short_product_id": entry["short_product_id"],
                **query_source_masks(ee, entry["acquisition_id"], grid),
            }
        )

    passed = all(record["source_masks_all_valid"] for record in records)
    return {
        "schema": EVIDENCE_SCHEMA,
        "status": "passed" if passed else "failed_source_mask_gate",
        "operation_boundary": {
            "read_only_earth_engine_queries": True,
            "export_tasks_created": 0,
            "assets_created": 0,
            "imagery_downloaded": 0,
            "manifest_rewritten": False,
        },
        "source_evidence": {
            "export_manifest_sha256": sha256_file(manifest_path),
            "catalog_sha256": sha256_file(catalog_path),
            "manifest_audit": audit,
            "auth_attestation_sha256": sha256_file(Path(args.attestation)),
            "attestation_verified_at_utc": attestation["verified_at"],
            "attestation_valid_until_utc": attestation["valid_until"],
            "live_health_verified_at_utc": live_probe["verified_at"],
        },
        "target_grid": grid,
        "acquisition_count": len(records),
        "mask_reduction_max_pixels": mask_reduction_max_pixels(grid["pixel_count"]),
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--project-config", required=True)
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_preflight(args)
    atomic_create_json(Path(args.output), result)
    print(
        canonical_json(
            {
                "status": result["status"],
                "acquisition_count": result["acquisition_count"],
                "export_tasks_created": result["operation_boundary"]["export_tasks_created"],
            }
        )
    )
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
