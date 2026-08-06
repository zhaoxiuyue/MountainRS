"""Fail-closed checks for the Stage 7.1-R evidence reconciliation auditor.

每个 check 都必须在证据漂移时翻红。这些用例的作用不是证明当前证据是好的
（那由审计器自己跑出来的结论承担），而是证明审计器不会在证据变坏时保持沉默。
"""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack"
SCRIPT_PATH = STAGE_ROOT / "scripts/audit_evidence_reconciliation_v1.py"
AUDIT_RESULT_PATH = STAGE_ROOT / "evidence/evidence-reconciliation-audit-v1.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = load_module("stage7_1r_reconciliation_auditor_under_test", SCRIPT_PATH)


def synthetic_rasters(evidence) -> dict[int, dict]:
    """按既有记录合成 21 景的栅格事实，免去逐景重读——本套用例只测判定逻辑。"""
    grid = evidence.stack_manifest["target_grid"]
    rasters = {}
    for entry in evidence.manifest["acquisitions"]:
        order = entry["order"]
        audit = evidence.mask_audits[order]
        rasters[order] = {
            "crs": grid["crs"],
            "transform": grid["transform"],
            "height": grid["shape"]["height"],
            "width": grid["shape"]["width"],
            "sha256": audit["local_file"]["sha256"],
            "masks": {
                band: {
                    "mask_one_count": recorded["mask_one_count"],
                    "mask_zero_count": recorded["mask_zero_count"],
                    "masked_pixels_all_carry_transfer_value": True,
                }
                for band, recorded in audit["reconstructed_source_masks"].items()
            },
        }
    return rasters


class ReconciliationAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = AUDITOR.Evidence()
        cls.rasters = synthetic_rasters(cls.evidence)

    def fresh(self):
        return copy.deepcopy(self.evidence)

    def test_recorded_audit_result_is_passing(self):
        """当前落盘的对账结论必须是全过的——它是后续构建的前置条件。"""
        result = json.loads(AUDIT_RESULT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "passed_reconciliation")
        self.assertEqual(result["failed_checks"], [])
        self.assertTrue(all(c["passed"] for c in result["checks"]))

    def test_baseline_all_checks_pass(self):
        for func in (
            AUDITOR.check_universe_identity,
            AUDITOR.check_canonical_order,
            AUDITOR.check_operation_eligibility,
            AUDITOR.check_split_arithmetic,
            AUDITOR.check_journal_completeness,
            AUDITOR.check_solar_geometry_available,
            AUDITOR.check_footprint_full_cover,
        ):
            with self.subTest(check=func.__name__):
                self.assertTrue(func(self.evidence)["passed"])
        self.assertTrue(AUDITOR.check_grid_identity(self.evidence, self.rasters)["passed"])
        self.assertTrue(AUDITOR.check_content_hashes(self.evidence, self.rasters)["passed"])
        self.assertTrue(
            AUDITOR.check_lossless_mask_reconstruction(self.evidence, self.rasters)["passed"]
        )

    def test_dropped_member_fails_universe_identity(self):
        evidence = self.fresh()
        evidence.stack_manifest["members"].pop()
        self.assertFalse(AUDITOR.check_universe_identity(evidence)["passed"])

    def test_renamed_member_fails_universe_identity(self):
        evidence = self.fresh()
        evidence.support_audit["members"][0]["acquisition_id"] = "LANDSAT/LC08/C02/T1_L2/FORGED"
        self.assertFalse(AUDITOR.check_universe_identity(evidence)["passed"])

    def test_reordered_canonical_order_fails(self):
        evidence = self.fresh()
        first, second = evidence.manifest["acquisitions"][0], evidence.manifest["acquisitions"][1]
        first["order"], second["order"] = second["order"], first["order"]
        self.assertFalse(AUDITOR.check_canonical_order(evidence)["passed"])

    def test_grid_drift_fails(self):
        rasters = copy.deepcopy(self.rasters)
        rasters[1]["width"] += 1
        self.assertFalse(AUDITOR.check_grid_identity(self.evidence, rasters)["passed"])

    def test_content_hash_drift_fails(self):
        rasters = copy.deepcopy(self.rasters)
        rasters[3]["sha256"] = "0" * 64
        self.assertFalse(AUDITOR.check_content_hashes(self.evidence, rasters)["passed"])

    def test_mask_count_drift_fails(self):
        rasters = copy.deepcopy(self.rasters)
        rasters[1]["masks"]["SR_B4"]["mask_one_count"] += 1
        self.assertFalse(
            AUDITOR.check_lossless_mask_reconstruction(self.evidence, rasters)["passed"]
        )

    def test_masked_pixel_carrying_non_transfer_value_fails(self):
        """被掩膜像元若不是传输零值，masked 与观测零值就不再可区分，必须翻红。"""
        rasters = copy.deepcopy(self.rasters)
        rasters[2]["masks"]["SR_B4"]["masked_pixels_all_carry_transfer_value"] = False
        self.assertFalse(
            AUDITOR.check_lossless_mask_reconstruction(self.evidence, rasters)["passed"]
        )

    def test_eligibility_flip_fails(self):
        evidence = self.fresh()
        for member in evidence.stack_manifest["members"]:
            if member["stack_eligible"] != "eligible":
                member["stack_eligible"] = "eligible"
                break
        self.assertFalse(AUDITOR.check_operation_eligibility(evidence)["passed"])

    def test_split_reassignment_fails(self):
        evidence = self.fresh()
        for member in evidence.stack_manifest["members"]:
            if member["split"] == "train":
                member["split"] = "test"
                break
        self.assertFalse(AUDITOR.check_split_arithmetic(evidence)["passed"])

    def test_split_given_to_ineligible_member_fails(self):
        evidence = self.fresh()
        for member in evidence.stack_manifest["members"]:
            if member["stack_eligible"] != "eligible":
                member["split"] = "train"
                break
        self.assertFalse(AUDITOR.check_split_arithmetic(evidence)["passed"])

    def test_broken_task_lineage_fails(self):
        """终态事件失去 task_id 回链即无法证明该景完成过。"""
        evidence = self.fresh()
        for event in evidence.journal:
            if event.get("earth_engine_state") == "COMPLETED":
                event["task_id"] = "UNLINKED-TASK-ID"
                break
        self.assertFalse(AUDITOR.check_journal_completeness(evidence)["passed"])

    def test_truncated_journal_fails(self):
        evidence = self.fresh()
        evidence.journal.pop()
        self.assertFalse(AUDITOR.check_journal_completeness(evidence)["passed"])

    def test_missing_solar_geometry_fails(self):
        evidence = self.fresh()
        evidence.catalog["candidates"][0]["sun_elevation_deg"] = None
        self.assertFalse(AUDITOR.check_solar_geometry_available(evidence)["passed"])

    def test_declared_missing_solar_field_fails(self):
        evidence = self.fresh()
        evidence.catalog["candidates"][5]["solar_geometry_missing_fields"] = ["SUN_AZIMUTH"]
        self.assertFalse(AUDITOR.check_solar_geometry_available(evidence)["passed"])

    def test_partial_footprint_coverage_fails(self):
        """coverage 掉出 full cover，observation_opportunity 就不再是常数场，必须停机。"""
        evidence = self.fresh()
        evidence.catalog["candidates"][2]["target_roi_footprint_coverage"] = 0.87
        result = AUDITOR.check_footprint_full_cover(evidence)
        self.assertFalse(result["passed"])
        self.assertIsNone(result["constant_field_value"])


if __name__ == "__main__":
    unittest.main()
