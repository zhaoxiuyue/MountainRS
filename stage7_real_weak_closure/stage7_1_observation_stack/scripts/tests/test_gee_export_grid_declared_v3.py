"""Safety checks for the v3 declared-grid executor.

These tests never authenticate, never submit and never touch Earth Engine.
They inspect the source text and drive build_declared_grid_task with a stub.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack"
SCRIPT_PATH = STAGE_ROOT / "scripts/gee_export_grid_declared_v3.py"
MANIFEST_PATH = STAGE_ROOT / "evidence/export-manifest-v3.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXECUTOR = load_module("stage7_1_declared_grid_executor_under_test", SCRIPT_PATH)
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


class StubExport:
    def __init__(self, sink):
        self.image = self
        self._sink = sink

    def toDrive(self, **kwargs):  # noqa: N802 - Earth Engine API name
        self._sink.update(kwargs)
        return object()


class StubBatch:
    def __init__(self, sink):
        self.Export = StubExport(sink)


class StubEE:
    def __init__(self, sink):
        self.batch = StubBatch(sink)


class StubBase:
    @staticmethod
    def build_mask_preserving_image(ee: Any, acquisition_id: str) -> str:
        return f"image:{acquisition_id}"


class DeclaredGridTaskTest(unittest.TestCase):
    def build(self, manifest=None):
        sink: dict[str, Any] = {}
        manifest = manifest or MANIFEST
        EXECUTOR.build_declared_grid_task(StubEE(sink), StubBase, manifest, manifest["acquisitions"][0])
        return sink

    def test_passes_dimensions_and_never_passes_region(self):
        sink = self.build()
        self.assertEqual(sink["dimensions"], "650x752")
        self.assertNotIn("region", sink)

    def test_passes_frozen_crs_and_crs_transform(self):
        sink = self.build()
        grid = MANIFEST["target_grid"]
        self.assertEqual(sink["crs"], grid["crs"])
        self.assertEqual(sink["crsTransform"], grid["transform"])

    def test_max_pixels_equals_frozen_pixel_count(self):
        self.assertEqual(self.build()["maxPixels"], MANIFEST["target_grid"]["pixel_count"])

    def test_task_description_is_v3_scoped(self):
        self.assertTrue(self.build()["description"].startswith("MountainRS_Stage7_1_V3_"))

    def test_drive_prefix_isolates_v3_from_earlier_attempts(self):
        self.assertIn("V3", self.build()["fileNamePrefix"])

    def test_refuses_dimensions_that_disagree_with_frozen_shape(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["grid_specification"]["dimensions_width"] = 651
        with self.assertRaises(RuntimeError):
            self.build(manifest)

    def test_refuses_a_reintroduced_region_parameter(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["execution"]["region_parameter"] = "rectangle"
        with self.assertRaises(RuntimeError):
            self.build(manifest)

    def test_refuses_inflated_max_pixels(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["execution"]["max_pixels"] = 489552
        with self.assertRaises(RuntimeError):
            self.build(manifest)

    def test_source_never_creates_assets_or_downloads(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        for forbidden in ("toAsset", "getDownloadURL", "getThumbURL", "ee.data.createAsset"):
            self.assertNotIn(forbidden, source)

    def test_source_never_reintroduces_geometry_derived_grid(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("Geometry.Rectangle", source)
        self.assertNotIn("region=", source)

    def test_selects_the_requested_canonical_order(self):
        for order in (1, 2, 3):
            entry = EXECUTOR.select_entry(MANIFEST, order)
            self.assertEqual(entry["order"], order)
        with self.assertRaises(RuntimeError):
            EXECUTOR.select_entry(MANIFEST, 99)

    def test_refuses_to_skip_ahead_in_canonical_order(self):
        empty_journal: list = []
        EXECUTOR.assert_canonical_order_respected(MANIFEST, empty_journal, 1)
        with self.assertRaises(RuntimeError) as caught:
            EXECUTOR.assert_canonical_order_respected(MANIFEST, empty_journal, 2)
        self.assertIn("canonical order violated", str(caught.exception))

    def test_refuses_to_resubmit_a_succeeded_order(self):
        journal = [
            {"event_type": "task_status", "task_id": "T1", "order": 1, "lifecycle_state": "submitted"},
            {"event_type": "task_status", "task_id": "T1", "lifecycle_state": "succeeded"},
        ]
        with self.assertRaises(RuntimeError) as caught:
            EXECUTOR.assert_canonical_order_respected(MANIFEST, journal, 1)
        self.assertIn("already succeeded", str(caught.exception))

    def test_allows_next_order_once_predecessor_succeeded(self):
        journal = [
            {"event_type": "task_status", "task_id": "T1", "order": 1, "lifecycle_state": "submitted"},
            {"event_type": "task_status", "task_id": "T1", "lifecycle_state": "succeeded"},
        ]
        EXECUTOR.assert_canonical_order_respected(MANIFEST, journal, 2)

    def test_poll_mode_never_submits(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        poll_body = source.split("def poll(")[1].split("\ndef ")[0]
        self.assertNotIn("task.start()", poll_body)
        self.assertNotIn("toDrive", poll_body)


if __name__ == "__main__":
    unittest.main()
