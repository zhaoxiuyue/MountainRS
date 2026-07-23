#!/usr/bin/env python3
"""Stage 7.1 query-only Earth Engine catalog auditor.

This is the Python execution channel for the frozen JavaScript semantics in
gee_catalog_audit.js. It performs metadata and QA summary queries only. It does
not create exports, assets, downloads, fitted models, scores, or scene ranking.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import ee


COLLECTION_ID = "LANDSAT/LC08/C02/T1_L2"
START_UTC = "2023-01-01T00:00:00Z"
END_UTC = "2024-01-01T00:00:00Z"
WRS_PATH = 130
WRS_ROW = 38
TARGET_CRS = "EPSG:32648"
TARGET_TRANSFORM = [30, 0, 292230, 0, -30, 3473790]
TARGET_BOUNDS = [292230, 3451230, 311730, 3473790]
TARGET_SHAPE = {"height": 752, "width": 650}
TARGET_RESOLUTION = [30, 30]
TARGET_PIXEL_COUNT = 488800
TARGET_GRID_ID = "shadow-risk-b-b4-grid-v1"
MIN_FOOTPRINT_COVERAGE = 0.999999
OUTPUT_SCHEMA = "mountainrs-stage7.1-acquisition-catalog-v1"
OBSERVATION_SCHEMA = "mountainrs-stage7.1-observation-record-v1"
REQUIRED_EXPORTABLE_PROPERTIES = [
    "system:index",
    "system:time_start",
    "SPACECRAFT_ID",
    "SENSOR_ID",
    "PROCESSING_LEVEL",
    "WRS_PATH",
    "WRS_ROW",
    "SUN_AZIMUTH",
    "SUN_ELEVATION",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def read_project_id(path: Path) -> str:
    """Read only the non-secret top-level project_id from the tracked YAML."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("project_id:"):
            project_id = line.split(":", 1)[1].strip().strip("\"'")
            if project_id:
                return project_id
    raise ValueError(f"project_id is missing from {path}")


def validate_request_manifest(path: Path) -> dict[str, Any]:
    request = json.loads(path.read_text(encoding="utf-8"))
    boundary = request["operation_boundary"]
    scope = request["query_scope"]
    grid = request["target_roi_grid"]
    if boundary["query_only"] is not True:
        raise ValueError("request manifest must set query_only=true")
    if boundary["exports_allowed"] is not False:
        raise ValueError("request manifest must set exports_allowed=false")
    expected_scope = {
        "collection": COLLECTION_ID,
        "wrs_path": WRS_PATH,
        "wrs_row": WRS_ROW,
    }
    for key, expected in expected_scope.items():
        if scope.get(key) != expected:
            raise ValueError(f"request scope drift for {key}")
    window = scope["time_window"]
    if (
        window.get("start_utc") != START_UTC
        or window.get("start_inclusive") is not True
        or window.get("end_utc") != END_UTC
        or window.get("end_inclusive") is not False
    ):
        raise ValueError("request time window drift")
    if scope.get("minimum_target_roi_footprint_coverage") != MIN_FOOTPRINT_COVERAGE:
        raise ValueError("request footprint threshold drift")
    if (
        grid.get("grid_id") != TARGET_GRID_ID
        or grid.get("crs") != TARGET_CRS
        or grid.get("transform") != TARGET_TRANSFORM
        or grid.get("bounds") != TARGET_BOUNDS
        or grid.get("shape") != TARGET_SHAPE
        or grid.get("resolution") != TARGET_RESOLUTION
        or grid.get("target_pixel_count") != TARGET_PIXEL_COUNT
    ):
        raise ValueError("request target grid drift")
    return request


def build_candidate_collection() -> ee.FeatureCollection:
    target_roi = ee.Geometry.Rectangle(TARGET_BOUNDS, TARGET_CRS, False)
    target_area_m2 = target_roi.area(1)

    def stable_sort_key(image: ee.Image) -> ee.String:
        image = ee.Image(image)
        timestamp = ee.Date(image.get("system:time_start")).format(
            "YYYY-MM-dd'T'HH:mm:ss.SSS'Z'", "UTC"
        )
        return timestamp.cat("|").cat(ee.String(image.get("system:index")))

    def with_footprint_coverage(image: ee.Image) -> ee.Image:
        image = ee.Image(image)
        footprint = image.geometry()
        intersection_area_m2 = footprint.intersection(target_roi, 1).area(1)
        coverage = intersection_area_m2.divide(target_area_m2)
        return image.set(
            {
                "target_roi_area_m2": target_area_m2,
                "target_roi_intersection_area_m2": intersection_area_m2,
                "target_roi_footprint_coverage": coverage,
                "stable_sort_key": stable_sort_key(image),
            }
        )

    def qa_and_coverage_summary(image: ee.Image) -> ee.Dictionary:
        image = ee.Image(image)
        qa = image.select("QA_PIXEL")
        scaled = image.select(["SR_B4", "SR_B5"]).multiply(0.0000275).add(-0.2)
        qa_clear = qa.bitwiseAnd(63).eq(0).rename("qa_clear_count")
        water = qa.bitwiseAnd(1 << 7).neq(0).rename("qa_water_count")
        source_mask_valid = scaled.mask().reduce(ee.Reducer.min())
        reflectance_in_range = (
            scaled.gte(-0.05).And(scaled.lte(1.0)).reduce(ee.Reducer.min())
        )
        numeric_valid = source_mask_valid.And(reflectance_in_range).rename(
            "reflectance_numeric_valid_count"
        )
        base_valid = qa_clear.And(numeric_valid).rename("base_valid_count")
        base_valid_land = base_valid.And(water.Not()).rename(
            "base_valid_land_count"
        )
        summary_image = ee.Image.cat(
            [
                ee.Image.constant(1).rename("target_pixel_count"),
                qa_clear,
                water,
                numeric_valid,
                base_valid,
                base_valid_land,
                qa.bitwiseAnd(1 << 0).neq(0).rename("qa_fill_count"),
                qa.bitwiseAnd(1 << 1)
                .neq(0)
                .rename("qa_dilated_cloud_count"),
                qa.bitwiseAnd(1 << 2).neq(0).rename("qa_cirrus_count"),
                qa.bitwiseAnd(1 << 3).neq(0).rename("qa_cloud_count"),
                qa.bitwiseAnd(1 << 4)
                .neq(0)
                .rename("qa_cloud_shadow_count"),
                qa.bitwiseAnd(1 << 5).neq(0).rename("qa_snow_count"),
            ]
        ).unmask(0)
        return summary_image.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=target_roi,
            crs=TARGET_CRS,
            crsTransform=TARGET_TRANSFORM,
            maxPixels=1_000_000,
            tileScale=4,
        )

    scoped = (
        ee.ImageCollection(COLLECTION_ID)
        .filterDate(START_UTC, END_UTC)
        .filter(ee.Filter.eq("WRS_PATH", WRS_PATH))
        .filter(ee.Filter.eq("WRS_ROW", WRS_ROW))
        .map(with_footprint_coverage)
    )
    cataloged = scoped.filter(
        ee.Filter.gte(
            "target_roi_footprint_coverage",
            MIN_FOOTPRINT_COVERAGE,
        )
    ).sort("stable_sort_key")
    exportable = cataloged.filter(
        ee.Filter.notNull(REQUIRED_EXPORTABLE_PROPERTIES)
    )
    exportable_ids = ee.List(exportable.aggregate_array("system:index"))
    cataloged_list = cataloged.toList(cataloged.size())

    def candidate_feature(item: Any) -> ee.Feature:
        image = ee.Image(item)
        is_exportable = exportable_ids.contains(image.get("system:index"))
        state = ee.String(
            ee.Algorithms.If(is_exportable, "exportable", "cataloged")
        )
        full_asset_id = (
            ee.String(COLLECTION_ID)
            .cat("/")
            .cat(ee.String(image.get("system:index")))
        )
        properties = ee.Dictionary(
            {
                "observation_schema": OBSERVATION_SCHEMA,
                "candidate_state": state,
                "acquisition_id": full_asset_id,
                "earth_engine_asset_id": full_asset_id,
                "system_index": image.get("system:index"),
                "system_time_start_ms": image.get("system:time_start"),
                "system_time_start_utc": ee.Date(
                    image.get("system:time_start")
                ).format("YYYY-MM-dd'T'HH:mm:ss.SSS'Z'", "UTC"),
                "platform": image.get("SPACECRAFT_ID"),
                "sensor": image.get("SENSOR_ID"),
                "collection": COLLECTION_ID,
                "tier": "T1",
                "processing_level": image.get("PROCESSING_LEVEL"),
                "wrs_path": image.get("WRS_PATH"),
                "wrs_row": image.get("WRS_ROW"),
                "sun_azimuth_deg": image.get("SUN_AZIMUTH"),
                "sun_elevation_deg": image.get("SUN_ELEVATION"),
                "sun_azimuth_source_field": "SUN_AZIMUTH",
                "sun_elevation_source_field": "SUN_ELEVATION",
                "cloud_cover_report_only": image.get("CLOUD_COVER"),
                "source_footprint_area_m2": image.geometry().area(1),
                "target_roi_area_m2": image.get("target_roi_area_m2"),
                "target_roi_intersection_area_m2": image.get(
                    "target_roi_intersection_area_m2"
                ),
                "target_roi_footprint_coverage": image.get(
                    "target_roi_footprint_coverage"
                ),
                "target_grid_id": TARGET_GRID_ID,
                "target_crs": TARGET_CRS,
                "target_transform": TARGET_TRANSFORM,
                "target_pixel_count_declared": TARGET_PIXEL_COUNT,
                "stable_sort_key": image.get("stable_sort_key"),
                "stack_eligible": "not_evaluated_local_only",
                "model_eligible": "not_adjudicated_stage_7_2",
            }
        ).combine(qa_and_coverage_summary(image), True)
        return ee.Feature(image.geometry(), properties)

    return ee.FeatureCollection(cataloged_list.map(candidate_feature)).sort(
        "stable_sort_key"
    )


def normalize_candidate(feature: dict[str, Any]) -> dict[str, Any]:
    properties = feature["properties"]
    exportable = properties["candidate_state"] == "exportable"
    missing_solar = [
        name
        for name in ("SUN_AZIMUTH", "SUN_ELEVATION")
        if properties.get(
            "sun_azimuth_deg" if name == "SUN_AZIMUTH" else "sun_elevation_deg"
        )
        is None
    ]
    qa_summary = {
        key: properties.get(key)
        for key in (
            "qa_clear_count",
            "qa_water_count",
            "qa_fill_count",
            "qa_dilated_cloud_count",
            "qa_cirrus_count",
            "qa_cloud_count",
            "qa_cloud_shadow_count",
            "qa_snow_count",
        )
    }
    land_valid_support_summary = {
        key: properties.get(key)
        for key in (
            "target_pixel_count",
            "reflectance_numeric_valid_count",
            "base_valid_count",
            "base_valid_land_count",
        )
    }
    land_valid_support_summary.update(
        {
            "supported": "not_yet_evaluated_local_terrain_required",
            "unsupported": "not_yet_evaluated_local_terrain_required",
        }
    )
    reasons = (
        ["all_required_identity_time_solar_and_qa_fields_present"]
        if exportable
        else ["one_or_more_required_identity_time_solar_or_qa_fields_missing"]
    )
    return {
        "acquisition_id": properties["acquisition_id"],
        "earth_engine_asset_id": properties["earth_engine_asset_id"],
        "system_index": properties["system_index"],
        "system_time_start_ms": properties["system_time_start_ms"],
        "system_time_start_utc": properties["system_time_start_utc"],
        "platform": properties.get("platform"),
        "sensor": properties.get("sensor"),
        "collection": properties["collection"],
        "tier": properties["tier"],
        "processing_level": properties.get("processing_level"),
        "wrs_path": properties.get("wrs_path"),
        "wrs_row": properties.get("wrs_row"),
        "source_footprint": feature.get("geometry"),
        "source_footprint_area_m2": properties["source_footprint_area_m2"],
        "target_roi_area_m2": properties["target_roi_area_m2"],
        "target_roi_intersection_area_m2": properties[
            "target_roi_intersection_area_m2"
        ],
        "target_roi_footprint_coverage": properties[
            "target_roi_footprint_coverage"
        ],
        "sun_azimuth_deg": properties.get("sun_azimuth_deg"),
        "sun_elevation_deg": properties.get("sun_elevation_deg"),
        "sun_azimuth_source_field": properties["sun_azimuth_source_field"],
        "sun_elevation_source_field": properties[
            "sun_elevation_source_field"
        ],
        "solar_geometry_missing_fields": missing_solar,
        "cloud_cover_report_only": properties.get("cloud_cover_report_only"),
        "qa_summary": qa_summary,
        "land_valid_support_summary": land_valid_support_summary,
        "cataloged": True,
        "cataloged_reasons": [
            "matches_frozen_collection_time_wrs_and_target_roi_coverage"
        ],
        "exportable": exportable,
        "exportable_reasons": reasons,
        "stack_eligible": "not_yet_evaluated",
        "model_eligible": "not_adjudicated_stage_7_2",
        "formal_split": None,
        "stable_sort_key": properties["stable_sort_key"],
    }


def preview_split(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    exportable = [item for item in candidates if item["exportable"]]
    count = len(exportable)
    if count < 3:
        return {
            "status": "not_available",
            "reason": "fewer_than_three_exportable_acquisitions",
            "formal": False,
        }
    n_train = max(1, int(0.6 * count))
    n_validation = max(1, int(0.2 * count))
    n_test = count - n_train - n_validation
    if n_test < 1:
        raise RuntimeError("frozen split formula produced an empty test preview")
    ids = [item["acquisition_id"] for item in exportable]
    return {
        "status": "hypothetical_if_all_exportable_pass_local_stack_gate",
        "formal": False,
        "n_train": n_train,
        "n_validation": n_validation,
        "n_test": n_test,
        "train": ids[:n_train],
        "validation": ids[n_train : n_train + n_validation],
        "test": ids[n_train + n_validation :],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    project_config = Path(args.project_config)
    request_path = Path(args.request_manifest)
    output_path = Path(args.output)
    project_id = read_project_id(project_config)
    request = validate_request_manifest(request_path)
    ee.Initialize(project=project_id)
    raw = build_candidate_collection().getInfo()
    raw_features = raw.get("features", [])
    candidates = sorted(
        (normalize_candidate(feature) for feature in raw_features),
        key=lambda item: (item["system_time_start_ms"], item["acquisition_id"]),
    )
    acquisition_ids = [item["acquisition_id"] for item in candidates]
    if len(acquisition_ids) != len(set(acquisition_ids)):
        raise RuntimeError("duplicate acquisition_id returned by frozen query")
    cataloged_count = len(candidates)
    exportable_count = sum(item["exportable"] for item in candidates)
    executed_at = dt.datetime.now(dt.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    result = {
        "schema": OUTPUT_SCHEMA,
        "request_manifest_sha256": sha256_file(request_path),
        "operation": {
            "operation_type": "metadata_query",
            "channel": "official_earthengine_python_api",
            "query_only": True,
            "exports_allowed": False,
            "task_id": "not_applicable",
            "asset_id": "not_applicable",
            "cloud_project_id": project_id,
            "earthengine_api_version": ee.__version__,
            "executed_at_utc": executed_at,
            "gee_request_identity": "not_exposed_by_python_client",
            "raw_result_sha256": hashlib.sha256(
                canonical_json(raw).encode("utf-8")
            ).hexdigest(),
        },
        "query_scope": request["query_scope"],
        "target_roi_grid": request["target_roi_grid"],
        "counts": {
            "cataloged": cataloged_count,
            "exportable": exportable_count,
            "incomplete": cataloged_count - exportable_count,
        },
        "candidates": candidates,
        "split_preview": preview_split(candidates),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json(result) + "\n"
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(output_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen Stage 7.1 query-only GEE catalog audit."
    )
    parser.add_argument("--project-config", required=True)
    parser.add_argument("--request-manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    result = run(parse_args())
    print(
        canonical_json(
            {
                "status": "succeeded",
                "cataloged": result["counts"]["cataloged"],
                "exportable": result["counts"]["exportable"],
                "incomplete": result["counts"]["incomplete"],
                "output_schema": result["schema"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
