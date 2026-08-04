from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "gee_source_mask_causal_audit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage7_1_source_mask_causal_audit", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load causal source-mask auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = load_module()


class CausalSourceMaskAuditTest(unittest.TestCase):
    def test_mask_one_sum_is_not_derived_mask_pixel_count(self) -> None:
        self.assertEqual(
            AUDITOR.derive_mask_counts(488800, 488700),
            {"target_pixel_count": 488800, "mask_one_count": 488700, "mask_zero_count": 100, "mask_zero_ratio": 100 / 488800},
        )

    def test_rejects_impossible_mask_one_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside"):
            AUDITOR.derive_mask_counts(10, 11)

    def test_causal_categories_preserve_reasons(self) -> None:
        reprojection = AUDITOR.classify_b4(target_zero_count=8, native_zero_count=0, edge_zero_count=0, qa_explained_count=0)
        self.assertEqual(reprojection["primary"], "target_grid_reprojection_introduced")
        edge = AUDITOR.classify_b4(target_zero_count=8, native_zero_count=8, edge_zero_count=8, qa_explained_count=0)
        self.assertEqual(edge["primary"], "edge_only")
        qa = AUDITOR.classify_b4(target_zero_count=8, native_zero_count=8, edge_zero_count=0, qa_explained_count=8)
        self.assertEqual(qa["primary"], "qa_explained")
        native = AUDITOR.classify_b4(target_zero_count=8, native_zero_count=8, edge_zero_count=0, qa_explained_count=0)
        self.assertEqual(native["primary"], "source_native_missing")

    def test_audit_has_no_export_asset_or_download_api(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("requests", imports)
        self.assertNotIn("urllib", imports)
        for forbidden in ("ee.batch", "toDrive(", "toAsset(", "getDownloadURL(", ".start("):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("connectedComponents(", source)
        self.assertIn("reduceToVectors(", source)


if __name__ == "__main__":
    unittest.main()
