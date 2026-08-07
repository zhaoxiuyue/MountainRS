"""Stage 7.2 ① cos_i 复算的不变量。

守两件事：几何这一层不许让 3 景再消失一次；以及公式没有被本节点改动过——
后者由「位级复现 Stage 6.5 冻结栅格」这一条硬门槛承担。
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_2_baseline_fit"
STAGE_7_1 = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack"
SCRIPT_PATH = STAGE_ROOT / "scripts/compute_cos_i_v1.py"
REGISTRY_PATH = STAGE_ROOT / "evidence/cos-i-registry-v1.json"

UNIVERSE_SIZE = 21
ELIGIBLE = 18
UNSUPPORTED = 3


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPUTER = load_module("stage7_2_cos_i_under_test", SCRIPT_PATH)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class FormulaFidelityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = read(REGISTRY_PATH)

    def test_order_one_reproduces_frozen_raster_bitwise(self):
        """公式自检：复现不了冻结 cos_i 就说明角度约定或地形身份有出入。"""
        verification = self.registry["formula_verification"]
        self.assertTrue(verification["passed"])
        self.assertTrue(verification["bitwise_identical"])
        self.assertTrue(verification["valid_mask_agrees"])
        self.assertEqual(verification["max_abs_difference_on_valid"], 0.0)
        self.assertEqual(
            verification["frozen_sha256"],
            "afb0728e1cf627beb91ca4071177b554176e8c7080c61f94ebcb6b03328d9b1a",
        )

    def test_formula_is_inherited_not_authored_here(self):
        self.assertFalse(self.registry["formula_modified_by_this_node"])
        self.assertFalse(self.registry["thresholds_invented"])
        self.assertIn("stage6_5_2b_shadowrisk_local_check.py", self.registry["formula_source"])

    def test_terrain_identity_is_verified_by_hash(self):
        terrain = self.registry["inputs"]["terrain_geometry"]
        for component in ("dem", "slope", "aspect"):
            with self.subTest(component=component):
                self.assertRegex(terrain[component]["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(terrain["combined_valid_count"], 488800)


class GeometrySupportCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = read(REGISTRY_PATH)
        cls.members = cls.registry["members"]

    def test_all_21_evidence_members_have_cos_i(self):
        """Stage 7.1-R 合同⑧：全部 21 景进入几何支持评估，不是 18 景。"""
        self.assertEqual(len(self.members), UNIVERSE_SIZE)
        self.assertEqual(self.registry["coverage"]["evidence_members_computed"], UNIVERSE_SIZE)
        for member in self.members:
            with self.subTest(order=member["order"]):
                self.assertEqual(member["evidence_membership"], "included")
                self.assertEqual(member["geometry_support_status"], "cos_i_computed")

    def test_operation_scoped_unsupported_scenes_still_get_geometry(self):
        """3 景在 direct-only 下无支持，但几何这一层不能让它们再消失一次。"""
        unsupported = [
            m for m in self.members
            if m["stage_7_2_direct_only_input_eligibility"] == "operation_scoped_unsupported"
        ]
        self.assertEqual(len(unsupported), UNSUPPORTED)
        for member in unsupported:
            with self.subTest(product=member["short_product_id"]):
                self.assertEqual(member["geometry_support_status"], "cos_i_computed")
                self.assertGreater(member["output"]["valid_count"], 0)
                self.assertEqual(member["evidence_membership"], "included")

    def test_eligibility_counts_match_the_input_view(self):
        view = read(STAGE_7_1 / "evidence/stage-7.2-direct-only-input-view-v1.json")
        self.assertEqual(self.registry["coverage"]["eligible_candidate"], ELIGIBLE)
        self.assertEqual(
            self.registry["coverage"]["operation_scoped_unsupported"], UNSUPPORTED
        )
        self.assertEqual(view["counts"]["eligible_candidate"], ELIGIBLE)
        self.assertEqual(view["counts"]["operation_scoped_unsupported"], UNSUPPORTED)

    def test_every_scene_uses_its_own_solar_geometry(self):
        """cos_i 逐景不同的唯一来源是太阳几何；共用一景的角度即为违约。"""
        azimuths = {m["solar_geometry"]["sun_azimuth_deg"] for m in self.members}
        elevations = {m["solar_geometry"]["sun_elevation_deg"] for m in self.members}
        self.assertEqual(len(azimuths), UNIVERSE_SIZE)
        self.assertEqual(len(elevations), UNIVERSE_SIZE)
        for member in self.members:
            solar = member["solar_geometry"]
            self.assertAlmostEqual(
                solar["solar_zenith_deg"], 90.0 - solar["sun_elevation_deg"], places=9
            )
            self.assertEqual(solar["azimuth_source_field"], "SUN_AZIMUTH")
            self.assertEqual(solar["elevation_source_field"], "SUN_ELEVATION")

    def test_rasters_exist_and_match_recorded_hashes(self):
        for member in self.members:
            with self.subTest(order=member["order"]):
                path = STAGE_ROOT / member["output"]["relative_path"]
                self.assertTrue(path.is_file())
                self.assertEqual(COMPUTER.sha256_file(path), member["output"]["sha256"])
                self.assertEqual(member["output"]["nodata"], -9999.0)


class SupportDecisionBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = read(REGISTRY_PATH)

    def test_partition_is_declared_descriptive_not_a_support_decision(self):
        """合同 ②③ 未获批前，三分区只能是描述统计，不得充当 Mconf 或 calibration-lit。"""
        boundary = self.registry["descriptive_partition_boundary"]
        self.assertIn("不构成本节点的 Mconf 或 calibration-lit 判定", boundary["statement"])
        self.assertIn("data_gap_report", boundary["source"])
        for member in self.registry["members"]:
            self.assertIn("descriptive_partition_not_a_support_decision", member)

    def test_no_support_quantity_or_alpha_was_produced(self):
        boundary = self.registry["boundary"]
        self.assertFalse(boundary["mconf_computed"])
        self.assertFalse(boundary["calibration_lit_decided"])
        self.assertFalse(boundary["alpha_estimated"])
        self.assertFalse(boundary["scored"])

    def test_upstream_freeze_untouched(self):
        boundary = self.registry["boundary"]
        self.assertFalse(boundary["earth_engine_called"])
        self.assertFalse(boundary["frozen_evidence_rewritten"])
        self.assertFalse(boundary["membership_changed"])
        self.assertFalse(boundary["split_reassigned"])

    def test_partition_counts_sum_to_valid_pixels(self):
        for member in self.registry["members"]:
            with self.subTest(order=member["order"]):
                partition = member["descriptive_partition_not_a_support_decision"]
                total = (
                    partition["shadow_cos_i_le_0"]
                    + partition["near_zero_0_lt_cos_i_le_0_1"]
                    + partition["lit_cos_i_gt_0_1"]
                )
                self.assertEqual(total, member["output"]["valid_count"])


if __name__ == "__main__":
    unittest.main()
