#!/usr/bin/env python3
"""Local fail-closed auditor for the order-1 v2 Export retry amendment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
AMENDMENT_SCHEMA = "mountainrs-stage7.1-export-retry-amendment-v2-order1-attempt2"
AMENDMENT_ID = "mountainrs-stage7.1-export-retry-amendment-v2-order1-attempt2"
BASE_MANIFEST_SHA256 = "a4a68743cfa15f89557bdd6e4371c7bcd66f8961fb6e3565def4e6c0bb5718b7"
TASK_ID = "WDI4LVYAKCREQUJPII2JAFV2"
ACQUISITION_ID = "LANDSAT/LC08/C02/T1_L2/LC08_130038_20230101"
EXPECTED_ERROR = "Export too large: specified 489552 pixels (max: 488800). Specify higher maxPixels value if you intend to export a large area."
EXPECTED_RETRY_SEED = "mountainrs-stage7.1-export-retry-amendment-v2-order1-attempt2:LANDSAT/LC08/C02/T1_L2/LC08_130038_20230101:attempt-2"
EXPECTED_GRID = {
    "target_grid_id": "shadow-risk-b-b4-grid-v1",
    "crs": "EPSG:32648",
    "transform": [30.0, 0.0, 292230.0, 0.0, -30.0, 3473790.0],
    "shape": {"height": 752, "width": 650},
    "bounds": [292230.0, 3451230.0, 311730.0, 3473790.0],
}
EXPECTED_BANDS = ["SR_B4", "SR_B5", "QA_PIXEL", "SR_B4_VALID", "SR_B5_VALID", "QA_PIXEL_VALID"]


class RetryAmendmentError(ValueError):
    """The permitted technical retry has drifted beyond its one amendment."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RetryAmendmentError(message)


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        require(isinstance(value, dict), f"journal line {line_number} is not an object")
        result.append(value)
    return result


def load_sibling_module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_amendment(
    amendment: dict[str, Any],
    base_manifest_path: Path,
    base_catalog_path: Path,
    causal_audit_path: Path,
    journal_path: Path,
) -> dict[str, Any]:
    base_auditor = load_sibling_module("stage7_1_export_manifest_v2_auditor", "audit_export_manifest_v2.py")
    base_manifest = load_json(base_manifest_path)
    base_auditor.validate_manifest(
        base_manifest,
        load_json(base_catalog_path),
        base_catalog_path,
        load_json(causal_audit_path),
        causal_audit_path,
    )
    require(amendment.get("schema") == AMENDMENT_SCHEMA, "retry amendment schema drift")
    require(amendment.get("request_id") == AMENDMENT_ID, "retry amendment identity drift")
    require(amendment.get("status") == "preregistered", "retry amendment is not preregistered")
    require(amendment.get("classification") == "ordinary_recoverable_execution_budget_repair_no_scientific_semantic_change", "retry classification drift")
    base = amendment.get("base_manifest")
    require(isinstance(base, dict), "base manifest anchor missing")
    require(base.get("request_id") == base_manifest["request_id"], "base manifest request mismatch")
    require(base.get("sha256") == BASE_MANIFEST_SHA256, "base manifest hash anchor drift")
    require(sha256_file(base_manifest_path) == BASE_MANIFEST_SHA256, "base manifest file hash drift")

    prior = amendment.get("prior_attempt")
    require(isinstance(prior, dict), "prior attempt record missing")
    require(prior.get("order") == 1 and prior.get("acquisition_id") == ACQUISITION_ID, "prior attempt identity drift")
    require(prior.get("attempt_number") == 1 and prior.get("task_id") == TASK_ID, "prior task lineage drift")
    require(prior.get("earth_engine_state") == "FAILED", "prior task is not terminal failed")
    require(prior.get("error_message") == EXPECTED_ERROR, "prior task error drift")
    require(prior.get("prior_drive_output_status") == "not_used_as_canonical_and_not_assumed_absent", "prior Drive boundary drift")
    journal = load_jsonl(journal_path)
    failed_events = [
        event for event in journal
        if event.get("task_id") == TASK_ID and event.get("earth_engine_state") == "FAILED"
    ]
    require(len(failed_events) == 1, "append-only journal lacks the one terminal failure receipt")
    receipt = failed_events[0]
    require(receipt.get("acquisition_id") == ACQUISITION_ID, "failed receipt acquisition drift")
    require(receipt.get("lifecycle_state") == "failed", "failed receipt lifecycle drift")
    require(receipt.get("external_error_message") == EXPECTED_ERROR, "failed receipt error drift")
    require(not any(event.get("event_type") == "external_outcome_unknown" for event in journal), "journal contains unknown external state")

    retry = amendment.get("retry_attempt")
    require(isinstance(retry, dict), "retry attempt record missing")
    require(retry.get("order") == 1 and retry.get("acquisition_id") == ACQUISITION_ID, "retry acquisition drift")
    require(retry.get("attempt_number") == 2, "retry must be attempt 2")
    require(retry.get("idempotency_identity") == EXPECTED_RETRY_SEED, "retry idempotency drift")
    require(retry.get("local_target_relative_to_alias") == base_manifest["acquisitions"][0]["target_relative_to_alias"], "retry local target drift")
    destination = retry.get("external_destination")
    require(isinstance(destination, dict), "retry destination missing")
    require(destination.get("folder_name") == "MountainRS_Stage7_1_V2_R2_15d5522991f9", "retry folder drift")
    require(destination.get("file_name_prefix") == "LC08_130038_20230101__SR_B4_SR_B5_QA_PIXEL__VALID__R2", "retry prefix drift")
    require(destination.get("canonical_local_member") is False, "Drive transfer was confused with local canonical member")

    change = amendment.get("sole_execution_amendment")
    require(change == {
        "parameter": "maxPixels",
        "from": 488800,
        "to": 489552,
        "service_reported_required_pixel_budget": 489552,
        "derivation": "Earth Engine terminal error from prior attempt; 489552 = 651 x 752",
        "meaning": "export safety cap only; it does not set output CRS, affine transform, ROI, dimensions, source data, masks or eligibility",
    }, "retry must amend only the service-reported maxPixels cap")

    anchors = amendment.get("unchanged_semantic_anchors")
    require(isinstance(anchors, dict), "unchanged semantic anchors missing")
    for key, expected in EXPECTED_GRID.items():
        require(anchors.get(key) == expected, f"semantic anchor drift: {key}")
    require(anchors.get("candidate_universe_sha256") == base_manifest["source_evidence"]["universe_sha256"], "candidate universe drift")
    require(anchors.get("bands") == EXPECTED_BANDS, "band semantics drift")
    for key, expected in (
        ("raw_dn_unscaled", True),
        ("source_mask_extracted_before_serialization_fill", True),
        ("serialization_fill_value", 0),
        ("explicit_valid_mask_authoritative", True),
        ("shared_nodata", None),
        ("source_native_missing_remains_in_candidate_universe", True),
        ("stack_eligible", "not_yet_evaluated"),
        ("split", "not_yet_assigned"),
    ):
        require(anchors.get(key) == expected, f"semantic anchor drift: {key}")
    boundary = amendment.get("operation_boundary")
    require(isinstance(boundary, dict), "operation boundary missing")
    for key in ("base_manifest_rewritten", "candidate_universe_changed", "roi_changed", "target_grid_changed", "stack_eligibility_changed", "split_changed"):
        require(boundary.get(key) is False, f"retry crossed boundary: {key}")
    require(boundary.get("assets_created") == 0 and boundary.get("imagery_downloaded") == 0, "retry preregistration created external data")
    return {
        "status": "passed",
        "request_id": AMENDMENT_ID,
        "base_manifest_sha256": BASE_MANIFEST_SHA256,
        "prior_task_id": TASK_ID,
        "retry_order": 1,
        "retry_attempt_number": 2,
        "max_pixels": 489552,
        "semantic_change": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--base-manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--causal-audit", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = validate_amendment(
        load_json(args.amendment),
        args.base_manifest,
        args.catalog,
        args.causal_audit,
        args.journal,
    )
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
