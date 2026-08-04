from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "gee_export_mask_preserving_v2_retry.py"


def load_executor():
    spec = importlib.util.spec_from_file_location("stage7_1_retry_executor", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load retry executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXECUTOR = load_executor()


class RetryExportExecutorTest(unittest.TestCase):
    def test_retry_task_uses_only_amended_maxpixels_and_isolated_destination(self) -> None:
        captured: dict[str, object] = {}

        class FakeImageExport:
            @staticmethod
            def toDrive(**kwargs):
                captured.update(kwargs)
                return "task"

        class FakeEE:
            class batch:
                class Export:
                    image = FakeImageExport

            class Geometry:
                @staticmethod
                def Rectangle(bounds, crs, geodesic):
                    return {"bounds": bounds, "crs": crs, "geodesic": geodesic}

        class FakeBase:
            @staticmethod
            def build_mask_preserving_image(_ee, acquisition_id):
                return f"six-band:{acquisition_id}"

        manifest = {
            "target_grid": {
                "bounds": [1, 2, 3, 4],
                "crs": "EPSG:32648",
                "transform": [30, 0, 1, 0, -30, 4],
            },
            "execution": {"file_format": "GeoTIFF", "skip_empty_tiles": False},
        }
        amendment = {
            "retry_attempt": {
                "acquisition_id": "asset",
                "task_description": "retry_task",
                "external_destination": {"folder_name": "isolated", "file_name_prefix": "retry_prefix"},
            },
            "sole_execution_amendment": {"to": 489552},
        }
        self.assertEqual(EXECUTOR.build_retry_task(FakeEE(), FakeBase(), manifest, amendment), "task")
        self.assertEqual(captured["image"], "six-band:asset")
        self.assertEqual(captured["folder"], "isolated")
        self.assertEqual(captured["fileNamePrefix"], "retry_prefix")
        self.assertEqual(captured["maxPixels"], 489552)
        self.assertNotIn("scale", captured)
        self.assertNotIn("dimensions", captured)
        self.assertNotIn("formatOptions", captured)

    def test_retry_executor_has_no_asset_or_download_path(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("ee", imports)
        for forbidden in ("toAsset(", "getDownloadURL(", "toCloudStorage(", "requests.", "urllib."):
            self.assertNotIn(forbidden, source)
        self.assertIn("toDrive(", source)
        self.assertIn("retry_submission_intent", source)
        self.assertIn("external_outcome_unknown", source)


if __name__ == "__main__":
    unittest.main()
