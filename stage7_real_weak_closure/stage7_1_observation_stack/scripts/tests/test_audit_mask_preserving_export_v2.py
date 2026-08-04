from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "audit_mask_preserving_export_v2.py"
CAUSAL_AUDIT_PATH = SCRIPT_PATH.parents[1] / "evidence/source-mask-causal-audit-v1.json"


def load_auditor():
    spec = importlib.util.spec_from_file_location("stage7_1_local_mask_auditor", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load local mask reconciler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = load_auditor()


class LocalMaskReconciliationTest(unittest.TestCase):
    def test_m1_counts_include_the_b4_source_missingness(self) -> None:
        audit = AUDITOR.load_json(CAUSAL_AUDIT_PATH)
        counts = AUDITOR.expected_m1_mask_counts(
            audit, "LANDSAT/LC08/C02/T1_L2/LC08_130038_20230101"
        )
        self.assertEqual(
            counts["SR_B4"],
            {"mask_one_count": 488288, "mask_zero_count": 512, "target_pixel_count": 488800},
        )
        self.assertEqual(counts["SR_B5"]["mask_zero_count"], 0)
        self.assertEqual(counts["QA_PIXEL"]["mask_zero_count"], 0)

    def test_manifest_entry_is_unique(self) -> None:
        manifest = {
            "acquisitions": [
                {"acquisition_id": "one", "short_product_id": "one"},
                {"acquisition_id": "two", "short_product_id": "two"},
            ]
        }
        self.assertEqual(AUDITOR.entry_for_acquisition(manifest, "two")["short_product_id"], "two")
        with self.assertRaisesRegex(RuntimeError, "no unique"):
            AUDITOR.entry_for_acquisition(manifest, "missing")

    def test_raster_dependency_is_runtime_only_and_no_remote_api_exists(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        top_level_imports = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("rasterio", top_level_imports)
        self.assertNotIn("numpy", top_level_imports)
        self.assertNotIn("ee", top_level_imports)
        for forbidden in ("ee.batch", "toDrive(", "toAsset(", "getDownloadURL(", "requests.", "urllib."):
            self.assertNotIn(forbidden, source)
        self.assertIn("source.read_masks()", source)
        self.assertIn("valid_array == 0", source)


if __name__ == "__main__":
    unittest.main()
