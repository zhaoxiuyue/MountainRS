#!/usr/bin/env python3
"""Execute only the audited v3 declared-grid export manifest.

The image, band order, mask-before-fill semantics, journal discipline and
lifecycle gates are inherited verbatim from the v2 executor.  The single
difference is how the output grid reaches Earth Engine: v2 passed a `region`
polygon and let Earth Engine derive the grid, which added a one-pixel skirt;
v3 passes `dimensions` so the frozen grid is declared, never derived.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DESCRIPTION_PREFIX = "MountainRS_Stage7_1_V3_"


def load_sibling_module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_declared_grid_task(ee: Any, base: Any, manifest: dict[str, Any], entry: dict[str, Any]) -> Any:
    """Declare the frozen grid; never let Earth Engine derive it from geometry."""
    grid = manifest["target_grid"]
    spec = manifest["grid_specification"]
    execution = manifest["execution"]
    if spec["dimensions_width"] != grid["shape"]["width"] or spec["dimensions_height"] != grid["shape"]["height"]:
        raise RuntimeError("declared dimensions do not equal the frozen target-grid shape")
    if execution.get("region_parameter") != "omitted":
        raise RuntimeError("v3 must not pass a region parameter")
    if execution["max_pixels"] != grid["pixel_count"]:
        raise RuntimeError("maxPixels must equal the frozen pixel count so grid inflation fails closed")
    return ee.batch.Export.image.toDrive(
        image=base.build_mask_preserving_image(ee, entry["acquisition_id"]),
        description=f"{TASK_DESCRIPTION_PREFIX}{entry['short_product_id']}",
        folder=execution["external_destination"]["folder_name"],
        fileNamePrefix=f"{entry['short_product_id']}__SR_B4_SR_B5_QA_PIXEL__VALID__V3",
        crs=grid["crs"],
        crsTransform=grid["transform"],
        dimensions=spec["dimensions"],
        maxPixels=execution["max_pixels"],
        fileFormat=execution["file_format"],
        skipEmptyTiles=execution["skip_empty_tiles"],
    )


def select_entry(manifest: dict[str, Any], order: int) -> dict[str, Any]:
    matches = [entry for entry in manifest["acquisitions"] if entry.get("order") == order]
    if len(matches) != 1:
        raise RuntimeError(f"manifest has no unique acquisition at order {order}")
    return matches[0]


def assert_canonical_order_respected(
    manifest: dict[str, Any], journal: list[dict[str, Any]], order: int
) -> None:
    """Refuse to skip ahead: every earlier order must already have succeeded."""
    succeeded = {
        event.get("order")
        for event in journal
        if event.get("lifecycle_state") == "succeeded" and event.get("order") is not None
    }
    # A terminal receipt carries no `order`; recover it from the submission intent
    # that shares the same task id.
    order_by_task = {
        event["task_id"]: event.get("order")
        for event in journal
        if event.get("task_id") and event.get("order") is not None
    }
    for event in journal:
        if event.get("lifecycle_state") == "succeeded" and event.get("task_id") in order_by_task:
            succeeded.add(order_by_task[event["task_id"]])
    missing = [earlier for earlier in range(1, order) if earlier not in succeeded]
    if missing:
        raise RuntimeError(f"canonical order violated: orders {missing} have not succeeded yet")
    if order in succeeded:
        raise RuntimeError(f"order {order} already succeeded; resubmission is prohibited")


def active_v3_tasks(ee: Any) -> list[dict[str, Any]]:
    active = []
    for task in ee.batch.Task.list():
        status = task.status()
        description = status.get("description")
        if isinstance(description, str) and description.startswith(TASK_DESCRIPTION_PREFIX):
            if status.get("state") in ("READY", "RUNNING", "SUBMITTED"):
                active.append(status)
    return active


def preflight(args: argparse.Namespace) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, int]]:
    auditor = load_sibling_module("stage7_1_export_manifest_v3_auditor", "audit_export_manifest_v3.py")
    base = load_sibling_module("stage7_1_mask_preserving_exporter", "gee_export_mask_preserving_v2.py")
    catalog_executor = load_sibling_module("stage7_1_catalog_executor", "gee_catalog_audit.py")

    manifest_path = Path(args.manifest)
    catalog_path = Path(args.catalog)
    causal_path = Path(args.causal_audit)
    journal_path = Path(args.journal)

    manifest = base.load_json(manifest_path)
    auditor.validate_manifest(
        manifest,
        base.load_json(catalog_path),
        catalog_path,
        base.load_json(causal_path),
        causal_path,
    )

    journal = base.load_journal(journal_path) if journal_path.exists() else []
    base.assert_journal_safe_for_submission(journal)

    entry = select_entry(manifest, args.order)
    assert_canonical_order_respected(manifest, journal, args.order)
    base.assert_local_target_absent(catalog_path.parents[2], manifest, entry)

    project_id = catalog_executor.read_project_id(Path(args.project_config))
    catalog_executor.verify_authenticated_session(Path(args.attestation), project_id)

    import ee

    actual = base.query_source_mask_counts(ee, entry["acquisition_id"], manifest["target_grid"])
    expected = base.expected_m1_mask_counts(base.load_json(causal_path), entry["acquisition_id"])
    if actual != expected:
        raise RuntimeError(f"v3 source-mask preflight differs from M1: expected={expected}, actual={actual}")
    if active_v3_tasks(ee) or base.active_v2_tasks(ee):
        raise RuntimeError("Earth Engine reports an active Stage 7.1 task; submission is prohibited")
    return base, manifest, entry, actual


def submit(args: argparse.Namespace) -> dict[str, Any]:
    base, manifest, entry, actual = preflight(args)
    journal_path = Path(args.journal)
    intent = {
        "schema": "mountainrs-stage7.1-export-attempt-event-v3",
        "event_type": "submission_intent",
        "recorded_at_utc": base.utc_now(),
        "manifest_request_id": manifest["request_id"],
        "manifest_sha256": base.sha256_file(Path(args.manifest)),
        "order": entry["order"],
        "acquisition_id": entry["acquisition_id"],
        "short_product_id": entry["short_product_id"],
        "attempt_number": 1,
        "idempotency_identity": entry["first_attempt_idempotency_seed"],
        "task_description": f"{TASK_DESCRIPTION_PREFIX}{entry['short_product_id']}",
        "target_relative_to_alias": entry["target_relative_to_alias"],
        "source_mask_one_counts_verified_against_m1": actual,
        "grid_specification": {
            "method": manifest["grid_specification"]["method"],
            "dimensions": manifest["grid_specification"]["dimensions"],
            "region_parameter": "omitted",
            "max_pixels": manifest["execution"]["max_pixels"],
        },
    }
    base.append_journal_event(journal_path, intent)

    import ee

    task = build_declared_grid_task(ee, base, manifest, entry)
    client_task_id = getattr(task, "id", None)
    try:
        task.start()
    except Exception as error:
        base.append_journal_event(journal_path, {
            **intent,
            "event_type": "external_outcome_unknown",
            "recorded_at_utc": base.utc_now(),
            "lifecycle_state": "unknown",
            "client_task_id": client_task_id,
            "external_error_class": type(error).__name__,
            "external_error_message": str(error),
        })
        raise RuntimeError("v3 start outcome is unknown; do not retry") from error
    try:
        status = task.status()
        task_id = status.get("id")
        earth_engine_state = status.get("state")
        if not isinstance(task_id, str) or not isinstance(earth_engine_state, str):
            raise RuntimeError("v3 task status lacks a real id or state")
        state = base.lifecycle_state(earth_engine_state)
    except Exception as error:
        base.append_journal_event(journal_path, {
            **intent,
            "event_type": "external_outcome_unknown",
            "recorded_at_utc": base.utc_now(),
            "lifecycle_state": "unknown",
            "client_task_id": client_task_id,
            "external_error_class": type(error).__name__,
            "external_error_message": str(error),
        })
        raise RuntimeError("v3 task started but status is unknown; do not retry") from error

    base.append_journal_event(journal_path, {
        **intent,
        "event_type": "task_status",
        "recorded_at_utc": base.utc_now(),
        "task_id": task_id,
        "earth_engine_state": earth_engine_state,
        "lifecycle_state": state,
    })
    return {
        "status": "submitted" if state == "submitted" else state,
        "order": entry["order"],
        "acquisition_id": entry["acquisition_id"],
        "task_id": task_id,
        "earth_engine_state": earth_engine_state,
        "declared_dimensions": manifest["grid_specification"]["dimensions"],
        "max_pixels": manifest["execution"]["max_pixels"],
        "source_mask_one_counts_verified_against_m1": actual,
    }


def poll(args: argparse.Namespace) -> dict[str, Any]:
    """Read the terminal state of the recorded v3 task; never submits."""
    base = load_sibling_module("stage7_1_mask_preserving_exporter", "gee_export_mask_preserving_v2.py")
    catalog_executor = load_sibling_module("stage7_1_catalog_executor", "gee_catalog_audit.py")
    journal_path = Path(args.journal)
    journal = base.load_journal(journal_path)
    task_ids = [event["task_id"] for event in journal if event.get("task_id")]
    if not task_ids:
        raise RuntimeError("v3 journal records no task id")
    task_id = task_ids[-1]
    project_id = catalog_executor.read_project_id(Path(args.project_config))
    catalog_executor.verify_authenticated_session(Path(args.attestation), project_id)

    import ee

    status = ee.data.getTaskStatus(task_id)[0]
    earth_engine_state = status.get("state")
    event = {
        "schema": "mountainrs-stage7.1-export-attempt-event-v3",
        "event_type": "task_status",
        "recorded_at_utc": base.utc_now(),
        "task_id": task_id,
        "earth_engine_state": earth_engine_state,
        "lifecycle_state": base.lifecycle_state(earth_engine_state),
        "error_message": status.get("error_message"),
        "destination_uris": status.get("destination_uris"),
    }
    base.append_journal_event(journal_path, event)
    return event


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "submit", "poll"), required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--causal-audit", required=True)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--project-config", required=True)
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--order", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = load_sibling_module("stage7_1_mask_preserving_exporter", "gee_export_mask_preserving_v2.py")
    if args.mode == "preflight":
        _base, manifest, entry, actual = preflight(args)
        print(base.canonical_json({
            "status": "passed",
            "mode": "preflight",
            "order": entry["order"],
            "acquisition_id": entry["acquisition_id"],
            "declared_dimensions": manifest["grid_specification"]["dimensions"],
            "max_pixels": manifest["execution"]["max_pixels"],
            "source_mask_one_counts_verified_against_m1": actual,
            "export_tasks_created": 0,
        }))
        return 0
    if args.mode == "poll":
        print(base.canonical_json(poll(args)))
        return 0
    print(base.canonical_json(submit(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
