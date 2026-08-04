from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "gee_export_mask_preserving_v2.py"
CAUSAL_AUDIT_PATH = SCRIPT_PATH.parents[1] / "evidence/source-mask-causal-audit-v1.json"


def load_executor():
    spec = importlib.util.spec_from_file_location("stage7_1_mask_preserving_executor", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load mask-preserving export executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXECUTOR = load_executor()


class FakeBand:
    def __init__(self, label: str, trace: list[str]) -> None:
        self.label = label
        self.trace = trace

    def mask(self):
        self.trace.append(f"{self.label}.mask")
        return FakeBand(f"{self.label}.mask", self.trace)

    def unmask(self, value: int):
        self.trace.append(f"{self.label}.unmask:{value}")
        return FakeBand(f"{self.label}.unmask", self.trace)

    def toUint16(self):
        self.trace.append(f"{self.label}.toUint16")
        return FakeBand(f"{self.label}.toUint16", self.trace)

    def rename(self, value: str):
        self.trace.append(f"{self.label}.rename:{value}")
        return value


class FakeImage:
    def __init__(self, trace: list[str]) -> None:
        self.trace = trace

    def select(self, band: str):
        self.trace.append(f"select:{band}")
        return FakeBand(band, self.trace)


class FakeEEImageNamespace:
    @staticmethod
    def cat(bands):
        return list(bands)


class FakeEE:
    Image = FakeEEImageNamespace

    @staticmethod
    def Image(_acquisition_id: str):
        raise AssertionError("shadowed by instance in test")


class MaskPreservingExportExecutorTest(unittest.TestCase):
    def test_m1_counts_are_loaded_per_band(self) -> None:
        audit = EXECUTOR.load_json(CAUSAL_AUDIT_PATH)
        counts = EXECUTOR.expected_m1_mask_counts(
            audit, "LANDSAT/LC08/C02/T1_L2/LC08_130038_20230101"
        )
        self.assertEqual(counts, {"SR_B4": 488288, "SR_B5": 488800, "QA_PIXEL": 488800})

    def test_canonical_order_cannot_skip_the_first_untouched_acquisition(self) -> None:
        manifest = {
            "acquisitions": [
                {"order": 1, "acquisition_id": "a"},
                {"order": 2, "acquisition_id": "b"},
            ]
        }
        with self.assertRaisesRegex(RuntimeError, "requires 1"):
            EXECUTOR.next_canonical_entry(manifest, [], 2)
        first = EXECUTOR.next_canonical_entry(manifest, [], 1)
        self.assertEqual(first["acquisition_id"], "a")
        second = EXECUTOR.next_canonical_entry(
            manifest, [{"acquisition_id": "a", "event_type": "task_status"}], 2
        )
        self.assertEqual(second["acquisition_id"], "b")

    def test_unknown_or_active_lineage_blocks_submission(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unknown external outcome"):
            EXECUTOR.assert_journal_safe_for_submission([
                {"event_type": "external_outcome_unknown", "lifecycle_state": "unknown"}
            ])
        with self.assertRaisesRegex(RuntimeError, "active v2 task"):
            EXECUTOR.assert_journal_safe_for_submission([
                {"event_type": "task_status", "task_id": "active", "earth_engine_state": "RUNNING"}
            ])
        EXECUTOR.assert_journal_safe_for_submission([
            {"event_type": "task_status", "task_id": "old", "earth_engine_state": "READY"},
            {"event_type": "task_status", "task_id": "old", "earth_engine_state": "FAILED"},
        ])

    def test_lifecycle_mapping_is_explicit_and_rejects_unknown_state(self) -> None:
        self.assertEqual(EXECUTOR.lifecycle_state("READY"), "submitted")
        self.assertEqual(EXECUTOR.lifecycle_state("COMPLETED"), "succeeded")
        with self.assertRaisesRegex(RuntimeError, "unrecognized"):
            EXECUTOR.lifecycle_state("MYSTERY")

    def test_source_mask_is_extracted_before_each_data_fill(self) -> None:
        trace: list[str] = []

        class LocalEE:
            class Image:
                @staticmethod
                def cat(bands):
                    return list(bands)

            @staticmethod
            def Image(_acquisition_id: str):
                return FakeImage(trace)

        # The production function accesses ee.Image as a callable and ee.Image.cat.
        class ImageCallable:
            def __call__(self, _acquisition_id: str):
                return FakeImage(trace)

            @staticmethod
            def cat(bands):
                return list(bands)

        class CallableEE:
            Image = ImageCallable()

        bands = EXECUTOR.build_mask_preserving_image(CallableEE(), "asset")
        self.assertEqual(bands, [
            "SR_B4", "SR_B5", "QA_PIXEL",
            "SR_B4_VALID", "SR_B5_VALID", "QA_PIXEL_VALID",
        ])
        for band in EXECUTOR.RAW_BANDS:
            self.assertLess(
                trace.index(f"{band}.mask"),
                trace.index(f"{band}.unmask:0"),
            )

    def test_executor_exposes_no_download_or_asset_path(self) -> None:
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
        for forbidden in ("toAsset(", "getDownloadURL(", "toCloudStorage(", "requests.", "urllib."):
            self.assertNotIn(forbidden, source)
        self.assertIn("toDrive(", source)
        self.assertIn("captured before serialization fill", source)


if __name__ == "__main__":
    unittest.main()
