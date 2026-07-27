from __future__ import annotations

import ast
import copy
import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
AUDITOR_PATH = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack/scripts/audit_export_manifest.py"
CATALOG_PATH = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack/data/raw/acquisition-catalog.json"
PROTOCOL_PATH = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack/docs/selection-protocol.md"


def load_auditor():
    spec = importlib.util.spec_from_file_location("stage7_1_export_manifest_auditor", AUDITOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Export Manifest auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = load_auditor()


def valid_manifest() -> dict[str, object]:
    catalog = AUDITOR.load_json(CATALOG_PATH)
    entries = []
    for order, candidate in enumerate(catalog["candidates"], start=1):
        short_id = candidate["system_index"]
        acquisition_id = candidate["acquisition_id"]
        entries.append(
            {
                "order": order,
                "acquisition_id": acquisition_id,
                "short_product_id": short_id,
                "system_time_start_utc": candidate["system_time_start_utc"],
                "target_relative_to_alias": (
                    f"{short_id}/{short_id}__SR_B4_SR_B5_QA_PIXEL.tif"
                ),
                "first_attempt_idempotency_seed": (
                    f"{AUDITOR.REQUEST_ID}:{acquisition_id}:attempt-1"
                ),
                "state": "not_requested",
                "attempts": [],
                "source_mask_preflight": "not_yet_evaluated",
                "stack_eligible": "not_yet_evaluated",
                "split": "not_yet_assigned",
            }
        )
    return {
        "schema": AUDITOR.MANIFEST_SCHEMA,
        "request_id": AUDITOR.REQUEST_ID,
        "manifest_version": 1,
        "status": "preregistered",
        "source_evidence": {
            "v5_request_sha256": AUDITOR.V5_REQUEST_SHA256,
            "universe_sha256": AUDITOR.UNIVERSE_SHA256,
            "catalog_sha256": AUDITOR.CATALOG_SHA256,
            "export_set_policy": "complete_v5_universe_all_21",
        },
        "authorization": {
            "exports_allowed": True,
            "task_creation_authorized_this_run": False,
            "tasks_created": 0,
            "assets_created": 0,
        },
        "execution": {
            "operation": "Export.image.toDrive",
            "task_granularity": "one_acquisition_one_task_one_three_band_geotiff",
            "maximum_active_exports": 1,
            "file_format": "GeoTIFF",
            "bands": ["SR_B4", "SR_B5", "QA_PIXEL"],
            "apply_scale_offset": False,
            "best_effort": False,
            "resampling": "nearest_neighbor_default",
            "explicit_resample_call": False,
            "unmask": False,
            "format_options_no_data": "omitted",
            "skip_empty_tiles": False,
        },
        "target_grid": copy.deepcopy(AUDITOR.EXPECTED_GRID),
        "raw_encoding": {
            "dtype": "uint16",
            "qa_zero_is_valid": True,
            "qa_fill_bit": 0,
            "source_mask_preflight_required": True,
            "source_masks_must_be_all_valid": True,
            "mask_failure_action": "stop_before_task_no_split_or_extra_band",
            "local_nodata_expected": None,
        },
        "path_policy": {
            "root_alias": "stage_7_1_observation_stack",
            "root_relative_path": "stage7_real_weak_closure/stage7_1_observation_stack/data/raw/observation_stack",
            "absolute_paths_allowed": False,
            "overwrite_existing_target": False,
        },
        "lifecycle": {
            "unknown_allows_resubmit": False,
            "retry_only_after_terminal_failed": True,
            "preserve_all_task_id_lineage": True,
            "active_or_submitted_is_success": False,
            "succeeded_requires_local_hash_and_reconciliation": True,
        },
        "attempt_backfill_schema": {
            "task_id": "required_real_value",
            "asset_id": "not_applicable_for_drive_export",
            "output_sha256": "required_after_local_file",
            "status_history": "append_only",
            "allowed_states": [
                "submitted",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                "unknown",
            ],
        },
        "acquisitions": entries,
    }


class ExportManifestAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = AUDITOR.load_json(CATALOG_PATH)

    def audit(self, manifest: dict[str, object]) -> dict[str, object]:
        return AUDITOR.validate_manifest(manifest, self.catalog, CATALOG_PATH)

    def assert_rejected(self, manifest: dict[str, object], pattern: str) -> None:
        with self.assertRaisesRegex(AUDITOR.ManifestError, pattern):
            self.audit(manifest)

    def test_complete_frozen_manifest_passes(self) -> None:
        result = self.audit(valid_manifest())
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["acquisition_count"], 21)
        self.assertEqual(result["universe_sha256"], AUDITOR.UNIVERSE_SHA256)
        self.assertEqual(result["unique_output_paths"], 21)
        self.assertEqual(result["unique_idempotency_seeds"], 21)
        self.assertEqual(result["tasks_created"], 0)
        self.assertEqual(result["assets_created"], 0)

    def test_missing_or_duplicate_acquisition_fails_closed(self) -> None:
        missing = valid_manifest()
        missing["acquisitions"].pop()
        self.assert_rejected(missing, "21 acquisitions")
        duplicate = valid_manifest()
        duplicate["acquisitions"][-1] = copy.deepcopy(duplicate["acquisitions"][0])
        self.assert_rejected(duplicate, "set or order drift")

    def test_order_and_timestamp_are_frozen(self) -> None:
        reordered = valid_manifest()
        reordered["acquisitions"][0], reordered["acquisitions"][1] = (
            reordered["acquisitions"][1],
            reordered["acquisitions"][0],
        )
        self.assert_rejected(reordered, "set or order drift")
        changed_time = valid_manifest()
        changed_time["acquisitions"][0]["system_time_start_utc"] = "2023-01-01T00:00:00Z"
        self.assert_rejected(changed_time, "timestamp drift")

    def test_raw_dn_qa_and_mask_semantics_are_fail_closed(self) -> None:
        for key, value, pattern in (
            ("apply_scale_offset", True, "raw DN"),
            ("unmask", True, "unmask"),
            ("format_options_no_data", 0, "nodata"),
            ("resampling", "bilinear", "resampling"),
            ("best_effort", True, "bestEffort"),
        ):
            manifest = valid_manifest()
            manifest["execution"][key] = value
            self.assert_rejected(manifest, pattern)
        mask_drift = valid_manifest()
        mask_drift["raw_encoding"]["source_masks_must_be_all_valid"] = False
        self.assert_rejected(mask_drift, "mask gate")

    def test_grid_and_three_band_transaction_are_exact(self) -> None:
        grid = valid_manifest()
        grid["target_grid"]["transform"][2] += 15
        self.assert_rejected(grid, "target grid drift")
        bands = valid_manifest()
        bands["execution"]["bands"] = ["SR_B4", "QA_PIXEL"]
        self.assert_rejected(bands, "band order")
        concurrency = valid_manifest()
        concurrency["execution"]["maximum_active_exports"] = 2
        self.assert_rejected(concurrency, "must be one")

    def test_paths_are_relative_unique_and_never_overwritten(self) -> None:
        absolute = valid_manifest()
        absolute["acquisitions"][0]["target_relative_to_alias"] = "/tmp/output.tif"
        self.assert_rejected(absolute, "absolute path")
        changed = valid_manifest()
        changed["path_policy"]["overwrite_existing_target"] = True
        self.assert_rejected(changed, "overwrite")
        alias = valid_manifest()
        alias["path_policy"]["root_alias"] = "unregistered_output"
        self.assert_rejected(alias, "Alias drift")

    def test_preregistration_contains_no_task_or_split_result(self) -> None:
        task = valid_manifest()
        task["acquisitions"][0]["attempts"] = [{"task_id": "fabricated"}]
        self.assert_rejected(task, "lineage must be empty")
        stack = valid_manifest()
        stack["acquisitions"][0]["stack_eligible"] = True
        self.assert_rejected(stack, "stack eligibility changed")
        split = valid_manifest()
        split["acquisitions"][0]["split"] = "train"
        self.assert_rejected(split, "split assigned")

    def test_unknown_retry_and_receipt_lineage_boundaries(self) -> None:
        unknown = valid_manifest()
        unknown["lifecycle"]["unknown_allows_resubmit"] = True
        self.assert_rejected(unknown, "unknown outcome")
        retry = valid_manifest()
        retry["lifecycle"]["retry_only_after_terminal_failed"] = False
        self.assert_rejected(retry, "retry gate")
        lineage = valid_manifest()
        lineage["lifecycle"]["preserve_all_task_id_lineage"] = False
        self.assert_rejected(lineage, "lineage")

    def test_auditor_is_local_read_only(self) -> None:
        tree = ast.parse(AUDITOR_PATH.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertNotIn("ee", imported)
        source = AUDITOR_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "ee.batch",
            "toCloudStorage(",
            "toAsset(",
            "getDownloadURL(",
            "requests.",
            "urllib.",
        ):
            self.assertNotIn(forbidden, source)

    def test_protocol_contains_all_user_decisions(self) -> None:
        protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
        for required in (
            AUDITOR.UNIVERSE_SHA256,
            "raw `SR_B4` DN",
            "raw `SR_B5` DN",
            "raw `QA_PIXEL`",
            "default nearest-neighbor",
            "At most one Export task may be active",
            "stage_7_1_observation_stack",
            "QA_PIXEL = 0",
            "unknown` is not retryable",
            "exports_allowed=true",
        ):
            self.assertIn(required, protocol)


if __name__ == "__main__":
    unittest.main()
