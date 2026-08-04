#!/usr/bin/env python3
"""Local lossless-mask reconciler for a downloaded Stage 7.1 v2 GeoTIFF.

This tool reads a local GeoTIFF and local frozen evidence only.  It never calls
Earth Engine, creates an Export task or asset, downloads imagery, rewrites a
manifest, assigns a split, or sets stack eligibility.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RAW_BANDS = ("SR_B4", "SR_B5", "QA_PIXEL")
VALID_BANDS = ("SR_B4_VALID", "SR_B5_VALID", "QA_PIXEL_VALID")


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


def expected_m1_mask_counts(causal_audit: dict[str, Any], acquisition_id: str) -> dict[str, dict[str, int]]:
    records = causal_audit.get("records")
    if not isinstance(records, list):
        raise RuntimeError("M1 causal audit records are missing")
    matched = [record for record in records if record.get("acquisition_id") == acquisition_id]
    if len(matched) != 1:
        raise RuntimeError(f"M1 causal audit has no unique record for {acquisition_id}")
    target = matched[0].get("target_grid")
    if not isinstance(target, dict):
        raise RuntimeError("M1 target-grid record is missing")
    result: dict[str, dict[str, int]] = {}
    for band in RAW_BANDS:
        counts = target.get(band)
        if not isinstance(counts, dict):
            raise RuntimeError(f"M1 counts missing for {band}")
        one = counts.get("mask_one_count")
        zero = counts.get("mask_zero_count")
        total = counts.get("target_pixel_count")
        if not all(isinstance(value, int) for value in (one, zero, total)) or one + zero != total:
            raise RuntimeError(f"M1 counts inconsistent for {band}")
        result[band] = {"mask_one_count": one, "mask_zero_count": zero, "target_pixel_count": total}
    return result


def entry_for_acquisition(manifest: dict[str, Any], acquisition_id: str) -> dict[str, Any]:
    entries = manifest.get("acquisitions")
    if not isinstance(entries, list):
        raise RuntimeError("manifest acquisitions are missing")
    matched = [entry for entry in entries if entry.get("acquisition_id") == acquisition_id]
    if len(matched) != 1:
        raise RuntimeError(f"manifest has no unique entry for {acquisition_id}")
    return matched[0]


def require_raster_dependencies() -> tuple[Any, Any]:
    try:
        import numpy as np
        import rasterio
    except ImportError as error:
        raise RuntimeError(
            "local GeoTIFF reconciliation requires rasterio and numpy in the approved local runtime"
        ) from error
    return np, rasterio


def require_exact_grid(source: Any, grid: dict[str, Any]) -> None:
    if source.crs is None or source.crs.to_string() != grid["crs"]:
        raise RuntimeError("local CRS does not match the frozen target grid")
    transform = [source.transform.a, source.transform.b, source.transform.c, source.transform.d, source.transform.e, source.transform.f]
    if transform != grid["transform"]:
        raise RuntimeError("local affine transform does not match the frozen target grid")
    if source.height != grid["shape"]["height"] or source.width != grid["shape"]["width"]:
        raise RuntimeError("local shape does not match the frozen target grid")
    bounds = [source.bounds.left, source.bounds.bottom, source.bounds.right, source.bounds.top]
    if bounds != grid["bounds"]:
        raise RuntimeError("local bounds do not match the frozen target grid")


def audit_geotiff(
    tif_path: Path,
    manifest: dict[str, Any],
    causal_audit: dict[str, Any],
    acquisition_id: str,
) -> dict[str, Any]:
    np, rasterio = require_raster_dependencies()
    entry = entry_for_acquisition(manifest, acquisition_id)
    expected = expected_m1_mask_counts(causal_audit, acquisition_id)
    grid = manifest["target_grid"]
    with rasterio.open(tif_path) as source:
        if source.driver != "GTiff":
            raise RuntimeError("local output is not a GeoTIFF")
        if source.count != 6:
            raise RuntimeError("local output must contain exactly six bands")
        if tuple(source.dtypes) != ("uint16",) * 6:
            raise RuntimeError("local output must contain six uint16 bands")
        if source.nodata is not None or any(value is not None for value in source.nodatavals):
            raise RuntimeError("local output must not declare dataset or band nodata")
        require_exact_grid(source, grid)
        arrays = source.read()
        dataset_masks = source.read_masks()
        if not np.all(dataset_masks == 255):
            raise RuntimeError("transfer GeoTIFF has an implicit masked pixel; explicit VALID bands are required")
        valid_arrays = arrays[3:6]
        raw_arrays = arrays[0:3]
        reconstructed: dict[str, dict[str, int]] = {}
        for raw_name, valid_name, raw_array, valid_array in zip(
            RAW_BANDS, VALID_BANDS, raw_arrays, valid_arrays, strict=True
        ):
            if not np.all((valid_array == 0) | (valid_array == 1)):
                raise RuntimeError(f"{valid_name} contains a value other than 0 or 1")
            invalid = valid_array == 0
            if not np.all(raw_array[invalid] == 0):
                raise RuntimeError(f"{raw_name} is nonzero where {valid_name}=0")
            one = int(np.count_nonzero(valid_array == 1))
            zero = int(np.count_nonzero(invalid))
            counts = {"mask_one_count": one, "mask_zero_count": zero, "target_pixel_count": one + zero}
            if counts != expected[raw_name]:
                raise RuntimeError(
                    f"{raw_name} reconstructed mask counts differ from frozen M1 evidence: "
                    f"expected={expected[raw_name]}, actual={counts}"
                )
            reconstructed[raw_name] = {
                **counts,
                "valid_band": valid_name,
                "masked_transfer_value": 0,
            }
        descriptions = list(source.descriptions)
    return {
        "schema": "mountainrs-stage7.1-mask-preserving-local-audit-v2",
        "status": "passed_lossless_mask_reconstruction",
        "operation_boundary": {
            "earth_engine_called": False,
            "export_tasks_created": 0,
            "assets_created": 0,
            "imagery_downloaded": 0,
            "manifest_rewritten": False,
            "stack_eligibility_changed": False,
            "split_changed": False,
        },
        "manifest_request_id": manifest["request_id"],
        "acquisition_id": acquisition_id,
        "short_product_id": entry["short_product_id"],
        "output_relative_to_alias": entry["target_relative_to_alias"],
        "local_file": {
            "sha256": sha256_file(tif_path),
            "byte_size": tif_path.stat().st_size,
            "driver": "GTiff",
            "band_count": 6,
            "band_order_authority": list(RAW_BANDS + VALID_BANDS),
            "band_descriptions_report_only": descriptions,
            "dtype": "uint16",
            "nodata": None,
        },
        "target_grid": grid,
        "reconstructed_source_masks": reconstructed,
        "state_boundary": {
            "stack_eligible": "not_yet_evaluated",
            "split": "not_yet_assigned",
            "reason": "mask reversibility and file integrity are necessary but local terrain/support audit is still separate",
        },
    }


def atomic_create_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing local-audit evidence: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(canonical_json(value) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--causal-audit", required=True)
    parser.add_argument("--acquisition-id", required=True)
    parser.add_argument("--tif", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    auditor = load_sibling_module("stage7_1_export_manifest_v2_auditor", "audit_export_manifest_v2.py")
    manifest_path = Path(args.manifest)
    catalog_path = Path(args.catalog)
    causal_path = Path(args.causal_audit)
    manifest = load_json(manifest_path)
    causal_audit = load_json(causal_path)
    auditor.validate_manifest(
        manifest,
        load_json(catalog_path),
        catalog_path,
        causal_audit,
        causal_path,
    )
    result = audit_geotiff(Path(args.tif), manifest, causal_audit, args.acquisition_id)
    atomic_create_json(Path(args.output), result)
    print(canonical_json({
        "status": result["status"],
        "acquisition_id": result["acquisition_id"],
        "output_sha256": result["local_file"]["sha256"],
        "stack_eligible": result["state_boundary"]["stack_eligible"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
