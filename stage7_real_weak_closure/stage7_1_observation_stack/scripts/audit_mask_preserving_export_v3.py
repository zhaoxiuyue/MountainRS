#!/usr/bin/env python3
"""Local reversibility audit for a v3 declared-grid GeoTIFF.

The storage semantics of v3 are inherited verbatim from v2, so the raster audit
itself is the very same `audit_geotiff` function, imported rather than copied.
Only the manifest validation differs: v3 manifests are validated by the v3
auditor, which additionally proves the grid was declared and not derived.

Read-only with respect to Earth Engine: no authentication, no task, no asset,
no download.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def load_sibling_module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOCAL = load_sibling_module("stage7_1_local_mask_auditor", "audit_mask_preserving_export_v2.py")
V3 = load_sibling_module("stage7_1_export_manifest_v3_auditor", "audit_export_manifest_v3.py")


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
    manifest_path = Path(args.manifest)
    catalog_path = Path(args.catalog)
    causal_path = Path(args.causal_audit)

    manifest = LOCAL.load_json(manifest_path)
    causal_audit = LOCAL.load_json(causal_path)
    V3.validate_manifest(
        manifest,
        LOCAL.load_json(catalog_path),
        catalog_path,
        causal_audit,
        causal_path,
    )
    result = LOCAL.audit_geotiff(Path(args.tif), manifest, causal_audit, args.acquisition_id)
    result["manifest_version"] = manifest["manifest_version"]
    result["grid_specification_method"] = manifest["grid_specification"]["method"]
    LOCAL.atomic_create_json(Path(args.output), result)
    print(LOCAL.canonical_json({
        "status": result["status"],
        "acquisition_id": result["acquisition_id"],
        "manifest_version": result["manifest_version"],
        "grid_specification_method": result["grid_specification_method"],
        "output_sha256": result["local_file"]["sha256"],
        "stack_eligible": result["state_boundary"]["stack_eligible"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
