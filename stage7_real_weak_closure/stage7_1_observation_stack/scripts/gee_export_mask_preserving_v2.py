#!/usr/bin/env python3
"""Serial executor for the preregistered Stage 7.1 v2 transfer contract.

`preflight` performs only authenticated read-only Earth Engine queries.  The
`submit` mode is deliberately narrow: after the same checks it may create one
Drive Export task for the next canonical acquisition, records append-only task
lineage, and never downloads imagery, writes an Earth Engine asset, changes a
manifest, or adjudicates stack eligibility.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RAW_BANDS = ("SR_B4", "SR_B5", "QA_PIXEL")
ACTIVE_STATES = {"READY", "RUNNING"}
TASK_DESCRIPTION_PREFIX = "MountainRS_Stage7_1_V2_"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


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


def load_journal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"attempt journal line {line_number} is not an object")
        records.append(value)
    return records


def append_journal_event(path: Path, event: dict[str, Any]) -> None:
    """Append one durable JSON line; the immutable manifest is never changed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = canonical_json(event) + "\n"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(serialized)
        stream.flush()
        os.fsync(stream.fileno())


def expected_m1_mask_counts(causal_audit: dict[str, Any], acquisition_id: str) -> dict[str, int]:
    records = causal_audit.get("records")
    if not isinstance(records, list):
        raise RuntimeError("M1 causal audit records are missing")
    matches = [record for record in records if record.get("acquisition_id") == acquisition_id]
    if len(matches) != 1:
        raise RuntimeError(f"M1 causal audit has no unique record for {acquisition_id}")
    target = matches[0].get("target_grid")
    if not isinstance(target, dict):
        raise RuntimeError("M1 target-grid mask counts are missing")
    counts: dict[str, int] = {}
    for band in RAW_BANDS:
        value = target.get(band)
        if not isinstance(value, dict) or not isinstance(value.get("mask_one_count"), int):
            raise RuntimeError(f"M1 mask=1 count is missing for {band}")
        counts[band] = value["mask_one_count"]
    return counts


def query_source_mask_counts(ee: Any, acquisition_id: str, grid: dict[str, Any]) -> dict[str, int]:
    image = ee.Image(acquisition_id).select(list(RAW_BANDS))
    region = ee.Geometry.Rectangle(grid["bounds"], grid["crs"], False)
    # Make the derived validity image full-grid before summing it.  Reducer.sum
    # therefore measures mask value == 1; it is not Reducer.count over masked
    # pixels, the semantic error corrected by C7.1-D3B-M1.
    derived_validity = image.mask().unmask(0)
    result = derived_validity.reduceRegion(
        ee.Reducer.sum(),
        geometry=region,
        crs=grid["crs"],
        crsTransform=grid["transform"],
        maxPixels=10_000_000,
        bestEffort=False,
        tileScale=4,
    ).getInfo()
    if not isinstance(result, dict):
        raise RuntimeError("source-mask preflight returned invalid data")
    counts: dict[str, int] = {}
    for band in RAW_BANDS:
        value = result.get(band)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError(f"source-mask preflight count is missing for {band}")
        counts[band] = int(value)
    return counts


def build_mask_preserving_image(ee: Any, acquisition_id: str) -> Any:
    """Return six full-grid uint16 bands with masks extracted before data fill."""
    image = ee.Image(acquisition_id)
    raw_bands: list[Any] = []
    valid_bands: list[Any] = []
    for band in RAW_BANDS:
        source_band = image.select(band)
        # The original source mask is captured before serialization fill.  This
        # explicit 0/1 band, not a GeoTIFF nodata convention, is authoritative.
        valid_bands.append(source_band.mask().unmask(0).toUint16().rename(f"{band}_VALID"))
        raw_bands.append(source_band.unmask(0).toUint16().rename(band))
    return ee.Image.cat(raw_bands + valid_bands)


def build_task(ee: Any, manifest: dict[str, Any], entry: dict[str, Any]) -> Any:
    grid = manifest["target_grid"]
    execution = manifest["execution"]
    destination = execution["external_destination"]
    short_id = entry["short_product_id"]
    description = f"{TASK_DESCRIPTION_PREFIX}{short_id}"
    return ee.batch.Export.image.toDrive(
        image=build_mask_preserving_image(ee, entry["acquisition_id"]),
        description=description,
        folder=destination["folder_name"],
        fileNamePrefix=f"{short_id}__SR_B4_SR_B5_QA_PIXEL__VALID",
        region=ee.Geometry.Rectangle(grid["bounds"], grid["crs"], False),
        crs=grid["crs"],
        crsTransform=grid["transform"],
        maxPixels=execution["max_pixels"],
        fileFormat=execution["file_format"],
        skipEmptyTiles=execution["skip_empty_tiles"],
    )


def active_v2_tasks(ee: Any) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for task in ee.batch.Task.list():
        status = task.status()
        description = status.get("description")
        if isinstance(description, str) and description.startswith(TASK_DESCRIPTION_PREFIX):
            if status.get("state") in ACTIVE_STATES:
                active.append(status)
    return active


def lifecycle_state(earth_engine_state: str) -> str:
    mapping = {
        "READY": "submitted",
        "RUNNING": "running",
        "COMPLETED": "succeeded",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
    }
    if earth_engine_state not in mapping:
        raise RuntimeError(f"unrecognized Earth Engine task state: {earth_engine_state}")
    return mapping[earth_engine_state]


def next_canonical_entry(
    manifest: dict[str, Any],
    journal: list[dict[str, Any]],
    requested_order: int,
) -> dict[str, Any]:
    touched_ids = {
        event.get("acquisition_id")
        for event in journal
        if isinstance(event.get("acquisition_id"), str)
    }
    next_entry = next(
        (entry for entry in manifest["acquisitions"] if entry["acquisition_id"] not in touched_ids),
        None,
    )
    if next_entry is None:
        raise RuntimeError("all canonical acquisitions already have lineage; reconcile before another action")
    if next_entry["order"] != requested_order:
        raise RuntimeError(
            f"canonical order requires {next_entry['order']}, not requested order {requested_order}"
        )
    return next_entry


def assert_journal_safe_for_submission(journal: list[dict[str, Any]]) -> None:
    latest_task_states: dict[str, Any] = {}
    for event in journal:
        if event.get("lifecycle_state") == "unknown" or event.get("event_type") == "external_outcome_unknown":
            raise RuntimeError("attempt journal contains an unknown external outcome; reconcile before submission")
        if event.get("event_type") == "task_status" and isinstance(event.get("task_id"), str):
            # The journal is chronological and append-only.  A prior READY is
            # historical once the same task later records FAILED/COMPLETED, so
            # concurrency must be judged from each task's latest receipt.
            latest_task_states[event["task_id"]] = event.get("earth_engine_state")
    if any(state in ACTIVE_STATES for state in latest_task_states.values()):
        raise RuntimeError("attempt journal records an active v2 task; reconcile before submission")


def assert_local_target_absent(stage_root: Path, manifest: dict[str, Any], entry: dict[str, Any]) -> None:
    relative = manifest["path_policy"]["root_relative_path"]
    target = stage_root / relative / entry["target_relative_to_alias"]
    if target.exists():
        raise RuntimeError(f"local target already exists and must not be overwritten: {target}")


def preflight(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, int], str]:
    auditor = load_sibling_module("stage7_1_export_manifest_v2_auditor", "audit_export_manifest_v2.py")
    catalog_executor = load_sibling_module("stage7_1_catalog_executor", "gee_catalog_audit.py")
    manifest_path = Path(args.manifest)
    catalog_path = Path(args.catalog)
    causal_path = Path(args.causal_audit)
    manifest = load_json(manifest_path)
    catalog = load_json(catalog_path)
    causal_audit = load_json(causal_path)
    manifest_audit = auditor.validate_manifest(manifest, catalog, catalog_path, causal_audit, causal_path)
    journal = load_journal(Path(args.attempt_journal))
    assert_journal_safe_for_submission(journal)
    entry = next_canonical_entry(manifest, journal, args.order)
    assert_local_target_absent(catalog_path.parents[2], manifest, entry)
    project_id = catalog_executor.read_project_id(Path(args.project_config))
    attestation, live_probe = catalog_executor.verify_authenticated_session(Path(args.attestation), project_id)

    import ee

    actual = query_source_mask_counts(ee, entry["acquisition_id"], manifest["target_grid"])
    expected = expected_m1_mask_counts(causal_audit, entry["acquisition_id"])
    if actual != expected:
        raise RuntimeError(
            "source-mask preflight differs from frozen M1 counts; stop before task "
            f"(expected={expected}, actual={actual})"
        )
    active = active_v2_tasks(ee)
    if active:
        raise RuntimeError("Earth Engine reports an active v2 task; reconcile before submission")
    return {
        "manifest": manifest,
        "entry": entry,
        "actual_mask_one_counts": actual,
        "manifest_audit": manifest_audit,
        "attestation": attestation,
        "live_probe": live_probe,
    }, causal_audit, actual, project_id


def submit(args: argparse.Namespace) -> dict[str, Any]:
    result, _causal_audit, actual_counts, _project_id = preflight(args)
    manifest = result["manifest"]
    entry = result["entry"]
    journal_path = Path(args.attempt_journal)
    manifest_path = Path(args.manifest)
    description = f"{TASK_DESCRIPTION_PREFIX}{entry['short_product_id']}"
    intent = {
        "schema": "mountainrs-stage7.1-export-attempt-event-v2",
        "event_type": "submission_intent",
        "recorded_at_utc": utc_now(),
        "manifest_request_id": manifest["request_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "order": entry["order"],
        "acquisition_id": entry["acquisition_id"],
        "short_product_id": entry["short_product_id"],
        "attempt_number": 1,
        "idempotency_identity": entry["first_attempt_idempotency_seed"],
        "task_description": description,
        "target_relative_to_alias": entry["target_relative_to_alias"],
        "source_mask_one_counts_verified_against_m1": actual_counts,
    }
    append_journal_event(journal_path, intent)

    import ee

    task = build_task(ee, manifest, entry)
    client_task_id = getattr(task, "id", None)
    try:
        task.start()
    except Exception as error:
        append_journal_event(
            journal_path,
            {
                **intent,
                "event_type": "external_outcome_unknown",
                "recorded_at_utc": utc_now(),
                "lifecycle_state": "unknown",
                "client_task_id": client_task_id,
                "external_error_class": type(error).__name__,
                "external_error_message": str(error),
            },
        )
        raise RuntimeError("task start outcome is unknown; do not retry or submit another task") from error
    try:
        status = task.status()
        task_id = status.get("id")
        earth_engine_state = status.get("state")
        if not isinstance(task_id, str) or not isinstance(earth_engine_state, str):
            raise RuntimeError("task status lacks a real id or state")
        state = lifecycle_state(earth_engine_state)
    except Exception as error:
        append_journal_event(
            journal_path,
            {
                **intent,
                "event_type": "external_outcome_unknown",
                "recorded_at_utc": utc_now(),
                "lifecycle_state": "unknown",
                "client_task_id": client_task_id,
                "external_error_class": type(error).__name__,
                "external_error_message": str(error),
            },
        )
        raise RuntimeError("task was started but status is unknown; do not retry or submit another task") from error
    receipt = {
        **intent,
        "event_type": "task_status",
        "recorded_at_utc": utc_now(),
        "task_id": task_id,
        "earth_engine_state": earth_engine_state,
        "lifecycle_state": state,
    }
    append_journal_event(journal_path, receipt)
    return {
        "status": "submitted" if state == "submitted" else state,
        "order": entry["order"],
        "acquisition_id": entry["acquisition_id"],
        "task_id": task_id,
        "earth_engine_state": earth_engine_state,
        "manifest_sha256": intent["manifest_sha256"],
        "source_mask_one_counts_verified_against_m1": actual_counts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "submit"), required=True)
    parser.add_argument("--order", type=int, required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--causal-audit", required=True)
    parser.add_argument("--project-config", required=True)
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--attempt-journal", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "preflight":
        result, _causal_audit, actual_counts, _project_id = preflight(args)
        print(canonical_json({
            "status": "passed",
            "mode": "preflight",
            "order": result["entry"]["order"],
            "acquisition_id": result["entry"]["acquisition_id"],
            "source_mask_one_counts_verified_against_m1": actual_counts,
            "export_tasks_created": 0,
            "assets_created": 0,
            "imagery_downloaded": 0,
        }))
        return 0
    print(canonical_json(submit(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
