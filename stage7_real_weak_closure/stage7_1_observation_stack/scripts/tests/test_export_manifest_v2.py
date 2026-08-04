from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack"
AUDITOR_PATH = STAGE_ROOT / "scripts/audit_export_manifest_v2.py"
MANIFEST_PATH = STAGE_ROOT / "evidence/export-manifest-v2.json"
CATALOG_PATH = STAGE_ROOT / "data/raw/acquisition-catalog.json"
CAUSAL_AUDIT_PATH = STAGE_ROOT / "evidence/source-mask-causal-audit-v1.json"


def load_auditor():
    spec = importlib.util.spec_from_file_location("stage7_1_export_manifest_v2_auditor", AUDITOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v2 Export Manifest auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = load_auditor()


class ExportManifestV2AuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = AUDITOR.load_json(MANIFEST_PATH)
        cls.catalog = AUDITOR.load_json(CATALOG_PATH)
        cls.causal_audit = AUDITOR.load_json(CAUSAL_AUDIT_PATH)

    def audit(self, manifest: dict[str, object]) -> dict[str, object]:
        return AUDITOR.validate_manifest(
            manifest,
            self.catalog,
            CATALOG_PATH,
            self.causal_audit,
            CAUSAL_AUDIT_PATH,
        )

    def assert_rejected(self, manifest: dict[str, object], pattern: str) -> None:
        with self.assertRaisesRegex(AUDITOR.ManifestError, pattern):
            self.audit(manifest)

    def test_preregistered_manifest_passes_and_preserves_all_21_members(self) -> None:
        result = self.audit(copy.deepcopy(self.manifest))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["acquisition_count"], 21)
        self.assertEqual(result["unique_output_paths"], 21)
        self.assertEqual(result["unique_idempotency_seeds"], 21)
        self.assertEqual(result["stack_eligible"], "not_yet_evaluated")
        self.assertEqual(result["split"], "not_yet_assigned")

    def test_six_band_order_and_serialized_masks_are_immutable(self) -> None:
        wrong_bands = copy.deepcopy(self.manifest)
        wrong_bands["execution"]["bands"].pop()
        self.assert_rejected(wrong_bands, "six-band order")
        wrong_mask_order = copy.deepcopy(self.manifest)
        wrong_mask_order["raw_encoding"]["valid_band_order"][0] = "QA_PIXEL_VALID"
        self.assert_rejected(wrong_mask_order, "valid band order")
        missing_pre_fill = copy.deepcopy(self.manifest)
        missing_pre_fill["execution"]["source_mask_extraction_before_serialization_fill"] = False
        self.assert_rejected(missing_pre_fill, "source mask")
        scaled = copy.deepcopy(self.manifest)
        scaled["execution"]["apply_scale_offset"] = True
        self.assert_rejected(scaled, "raw DN")

    def test_grid_universe_paths_and_concurrency_fail_closed(self) -> None:
        grid = copy.deepcopy(self.manifest)
        grid["target_grid"]["transform"][2] += 15
        self.assert_rejected(grid, "target grid")
        removed = copy.deepcopy(self.manifest)
        removed["acquisitions"].pop()
        self.assert_rejected(removed, "21 acquisitions")
        absolute = copy.deepcopy(self.manifest)
        absolute["acquisitions"][0]["target_relative_to_alias"] = "/tmp/invalid.tif"
        self.assert_rejected(absolute, "absolute path")
        concurrent = copy.deepcopy(self.manifest)
        concurrent["execution"]["maximum_active_exports"] = 2
        self.assert_rejected(concurrent, "active export limit")

    def test_no_implicit_eligibility_or_unknown_retry(self) -> None:
        eligible = copy.deepcopy(self.manifest)
        eligible["acquisitions"][0]["stack_eligible"] = True
        self.assert_rejected(eligible, "eligibility changed")
        threshold = copy.deepcopy(self.manifest)
        threshold["state_boundary"]["eligibility_thresholds_added_by_v2"] = True
        self.assert_rejected(threshold, "invented")
        retry = copy.deepcopy(self.manifest)
        retry["lifecycle"]["unknown_allows_resubmit"] = True
        self.assert_rejected(retry, "unknown outcome")

    def test_auditor_is_local_only(self) -> None:
        source = AUDITOR_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("ee", imported)
        for forbidden in ("ee.batch", "toDrive(", "toAsset(", "getDownloadURL(", "requests.", "urllib."):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
