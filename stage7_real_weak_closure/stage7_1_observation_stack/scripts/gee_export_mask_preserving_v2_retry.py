#!/usr/bin/env python3
"""Execute only the audited order-1, attempt-2 maxPixels retry amendment."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


def canonical_json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(path: Path) -> dict[str, Any]:
    import json

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


def build_retry_task(ee: Any, base: Any, manifest: dict[str, Any], amendment: dict[str, Any]) -> Any:
    retry = amendment["retry_attempt"]
    grid = manifest["target_grid"]
    return ee.batch.Export.image.toDrive(
        image=base.build_mask_preserving_image(ee, retry["acquisition_id"]),
        description=retry["task_description"],
        folder=retry["external_destination"]["folder_name"],
        fileNamePrefix=retry["external_destination"]["file_name_prefix"],
        region=ee.Geometry.Rectangle(grid["bounds"], grid["crs"], False),
        crs=grid["crs"],
        crsTransform=grid["transform"],
        maxPixels=amendment["sole_execution_amendment"]["to"],
        fileFormat=manifest["execution"]["file_format"],
        skipEmptyTiles=manifest["execution"]["skip_empty_tiles"],
    )


def preflight(args: argparse.Namespace) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, int]]:
    amendment_auditor = load_sibling_module("stage7_1_retry_amendment_auditor", "audit_export_retry_amendment_v2.py")
    base = load_sibling_module("stage7_1_mask_preserving_exporter", "gee_export_mask_preserving_v2.py")
    catalog_executor = load_sibling_module("stage7_1_catalog_executor", "gee_catalog_audit.py")
    amendment_path = Path(args.amendment)
    manifest_path = Path(args.base_manifest)
    catalog_path = Path(args.catalog)
    causal_path = Path(args.causal_audit)
    journal_path = Path(args.journal)
    amendment = load_json(amendment_path)
    amendment_auditor.validate_amendment(amendment, manifest_path, catalog_path, causal_path, journal_path)
    manifest = load_json(manifest_path)
    journal = base.load_journal(journal_path)
    base.assert_journal_safe_for_submission(journal)
    entry = manifest["acquisitions"][0]
    base.assert_local_target_absent(catalog_path.parents[2], manifest, entry)
    project_id = catalog_executor.read_project_id(Path(args.project_config))
    catalog_executor.verify_authenticated_session(Path(args.attestation), project_id)

    import ee

    actual = base.query_source_mask_counts(ee, entry["acquisition_id"], manifest["target_grid"])
    expected = base.expected_m1_mask_counts(load_json(causal_path), entry["acquisition_id"])
    if actual != expected:
        raise RuntimeError(f"retry source-mask preflight differs from M1: expected={expected}, actual={actual}")
    if base.active_v2_tasks(ee):
        raise RuntimeError("Earth Engine reports an active v2 task; retry is prohibited")
    return base, manifest, amendment, actual


def submit(args: argparse.Namespace) -> dict[str, Any]:
    base, manifest, amendment, actual = preflight(args)
    journal_path = Path(args.journal)
    retry = amendment["retry_attempt"]
    intent = {
        "schema": "mountainrs-stage7.1-export-attempt-event-v2",
        "event_type": "retry_submission_intent",
        "recorded_at_utc": base.utc_now(),
        "manifest_request_id": manifest["request_id"],
        "retry_amendment_request_id": amendment["request_id"],
        "retry_amendment_sha256": base.sha256_file(Path(args.amendment)),
        "order": retry["order"],
        "acquisition_id": retry["acquisition_id"],
        "short_product_id": retry["short_product_id"] if "short_product_id" in retry else manifest["acquisitions"][0]["short_product_id"],
        "attempt_number": retry["attempt_number"],
        "idempotency_identity": retry["idempotency_identity"],
        "task_description": retry["task_description"],
        "target_relative_to_alias": retry["local_target_relative_to_alias"],
        "source_mask_one_counts_verified_against_m1": actual,
        "sole_execution_amendment": amendment["sole_execution_amendment"],
    }
    base.append_journal_event(journal_path, intent)

    import ee

    task = build_retry_task(ee, base, manifest, amendment)
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
        raise RuntimeError("retry start outcome is unknown; do not retry again") from error
    try:
        status = task.status()
        task_id = status.get("id")
        earth_engine_state = status.get("state")
        if not isinstance(task_id, str) or not isinstance(earth_engine_state, str):
            raise RuntimeError("retry task status lacks a real id or state")
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
        raise RuntimeError("retry task started but status is unknown; do not retry again") from error
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
        "order": retry["order"],
        "acquisition_id": retry["acquisition_id"],
        "task_id": task_id,
        "earth_engine_state": earth_engine_state,
        "max_pixels": amendment["sole_execution_amendment"]["to"],
        "source_mask_one_counts_verified_against_m1": actual,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "submit"), required=True)
    parser.add_argument("--amendment", required=True)
    parser.add_argument("--base-manifest", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--causal-audit", required=True)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--project-config", required=True)
    parser.add_argument("--attestation", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "preflight":
        _base, _manifest, amendment, actual = preflight(args)
        print(canonical_json({
            "status": "passed",
            "mode": "preflight",
            "order": amendment["retry_attempt"]["order"],
            "acquisition_id": amendment["retry_attempt"]["acquisition_id"],
            "max_pixels": amendment["sole_execution_amendment"]["to"],
            "source_mask_one_counts_verified_against_m1": actual,
            "export_tasks_created": 0,
        }))
        return 0
    print(canonical_json(submit(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
