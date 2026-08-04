from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "gee_export_preflight.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage7_1_export_preflight", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load source-mask preflight")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREFLIGHT = load_module()


class SourceMaskPreflightTest(unittest.TestCase):
    def test_mask_reduction_budget_covers_each_frozen_band(self) -> None:
        self.assertEqual(PREFLIGHT.mask_reduction_max_pixels(488800), 1466400)

    def test_all_bands_require_full_count_and_unit_minimum(self) -> None:
        counts = {band: 488800 for band in PREFLIGHT.REQUIRED_BANDS}
        minimums = {band: 1 for band in PREFLIGHT.REQUIRED_BANDS}
        result = PREFLIGHT.evaluate_mask_measurements(counts, minimums, 488800)
        self.assertTrue(result["source_masks_all_valid"])
        self.assertTrue(all(item["all_valid"] for item in result["bands"].values()))

    def test_missing_or_masked_pixels_fail_closed(self) -> None:
        counts = {band: 488800 for band in PREFLIGHT.REQUIRED_BANDS}
        minimums = {band: 1 for band in PREFLIGHT.REQUIRED_BANDS}
        counts["SR_B5"] = 488799
        minimums["QA_PIXEL"] = 0
        result = PREFLIGHT.evaluate_mask_measurements(counts, minimums, 488800)
        self.assertFalse(result["source_masks_all_valid"])
        self.assertFalse(result["bands"]["SR_B5"]["all_valid"])
        self.assertFalse(result["bands"]["QA_PIXEL"]["all_valid"])

    def test_preflight_has_no_export_or_download_api(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("requests", imported)
        self.assertNotIn("urllib", imported)
        for forbidden in ("ee.batch", "toDrive(", "toAsset(", "getDownloadURL(", ".start("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
