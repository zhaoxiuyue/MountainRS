"""Stage 7.3 空间阻断的不变量。

守两件最容易在评分压力下失守的事：拓扑不能被结果反向影响，
以及共享标定的 fold 不能被当成独立重复。
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_3_spatial_blocking"
FITTER_PATH = STAGE_ROOT / "scripts/fit_fold_alpha_and_score_v1.py"

SUBPROTOCOL = STAGE_ROOT / "docs/core-topology-subprotocol-v1.md"
PREFLIGHT = STAGE_ROOT / "evidence/preflight-manifest-v1.json"
FEASIBILITY = STAGE_ROOT / "evidence/geometric-feasibility-audit-v1.json"
TOPOLOGY = STAGE_ROOT / "evidence/topology-manifest-v1.json"
LEDGER = STAGE_ROOT / "evidence/fold-alpha-and-leakage-ledger-v1.json"
RESIDUAL = STAGE_ROOT / "evidence/descriptive-residual-summary-v1.json"

ROI_PIXELS = 488800
ISOLATION_M = 8130.0
MIN_SUPPORT = 271
EXPECTED_FOLDS = 5
EXPECTED_ACQUISITIONS = 18


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FITTER = load_module("stage7_3_fitter_under_test", FITTER_PATH)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class PreflightGateTest(unittest.TestCase):
    def test_preflight_completed_in_planned_state(self):
        manifest = read(PREFLIGHT)
        self.assertEqual(manifest["node_state_at_preflight"], "planned")
        self.assertTrue(manifest["verdict"]["activation_admitted"])
        self.assertTrue(manifest["verdict"]["core_topology_definition_uniquely_executable"])
        self.assertTrue(manifest["verdict"]["scoring_protocol_uniquely_executable"])

    def test_preflight_did_not_read_per_acquisition_data(self):
        scope = read(PREFLIGHT)["read_scope_compliance"]
        self.assertTrue(scope["compliant"])
        self.assertFalse(scope["opened_any_raster"])
        for forbidden in ("逐景 radiance", "QA/validity 支持量", "alpha", "residual", "分数"):
            self.assertIn(forbidden, scope["not_read"])

    def test_subprotocol_is_frozen_and_bound_by_hash(self):
        self.assertIn("**状态：** `frozen`", SUBPROTOCOL.read_text(encoding="utf-8"))
        recorded = read(PREFLIGHT)["approved_subprotocol"]["sha256"]
        self.assertEqual(FITTER.sha256_file(SUBPROTOCOL), recorded)


class TopologyLayeringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.topology = read(TOPOLOGY)

    def test_topology_is_frozen(self):
        self.assertEqual(self.topology["status"], "frozen")

    def test_topology_layer_did_not_read_per_acquisition_data(self):
        """合同⑤：拓扑冻结时不得读取逐景 calibration_lit、QA/validity 或 alpha。"""
        boundary = self.topology["layering_boundary"]
        self.assertFalse(boundary["opened_any_raster_for_reading"])
        self.assertFalse(boundary["read_per_acquisition_data"])
        self.assertFalse(boundary["read_alpha_or_residual"])

    def test_core_buffer_domain_partition_is_exhaustive_and_exclusive(self):
        for fold in self.topology["folds"]:
            with self.subTest(fold=fold["fold_index"]):
                total = (
                    fold["core_pixel_count"]
                    + fold["buffer_pixel_count"]
                    + fold["geometric_calibration_domain"]["pixel_count"]
                )
                self.assertEqual(total, ROI_PIXELS)
                self.assertTrue(fold["partition_exhaustive_and_exclusive"])

    def test_every_fold_meets_the_isolation_predicate(self):
        self.assertEqual(len(self.topology["folds"]), EXPECTED_FOLDS)
        for fold in self.topology["folds"]:
            with self.subTest(fold=fold["fold_index"]):
                self.assertTrue(fold["isolation_admitted"])
                self.assertGreaterEqual(fold["min_distance_core_to_own_domain_m"], ISOLATION_M)

    def test_cores_do_not_overlap(self):
        for pair in self.topology["pairwise_cores"]:
            with self.subTest(pair=pair["pair"]):
                self.assertFalse(pair["cores_overlap"])

    def test_topology_is_shared_across_all_acquisitions_and_bands(self):
        shared = self.topology["shared_topology"]
        self.assertTrue(shared["applies_to_all_18_acquisitions"])
        self.assertTrue(shared["applies_to_both_bands"])


class FoldSafeAlphaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = read(LEDGER)
        cls.units = cls.ledger["units"]

    def test_unit_count_matches_acquisitions_times_bands_times_folds(self):
        self.assertEqual(len(self.units), EXPECTED_ACQUISITIONS * 2 * EXPECTED_FOLDS)

    def test_reference_alpha_never_used_for_any_score(self):
        """合同⑥的铁律：全支持 reference alpha 禁止用于任何 fold 的成绩。"""
        self.assertFalse(self.ledger["boundary"]["reference_alpha_used_for_any_score"])
        for unit in self.units:
            with self.subTest(unit=(unit["order"], unit["band"], unit["fold_index"])):
                self.assertFalse(unit["reference_alpha_used"])
                self.assertEqual(
                    unit["alpha_source"],
                    "within_acquisition_calibration_excluding_own_core_and_buffer",
                )
                if unit["fallback_receipt"]:
                    self.assertFalse(unit["fallback_receipt"]["reference_alpha_fallback"])

    def test_threshold_enforced_exactly_and_never_relaxed(self):
        self.assertEqual(self.ledger["estimator"]["minimum_support_threshold"], MIN_SUPPORT)
        self.assertFalse(self.ledger["estimator"]["threshold_relaxed"])
        for unit in self.units:
            with self.subTest(unit=(unit["order"], unit["band"], unit["fold_index"])):
                n = unit["calibration"]["actual_calibration_lit_pixels"]
                if n < MIN_SUPPORT:
                    self.assertEqual(unit["state"], "unsupported_calibration")
                elif unit["calibration"]["denominator_sum_mu_squared"] > 0:
                    self.assertEqual(unit["state"], "fitted")

    def test_unsupported_units_carry_closed_set_reason_and_no_repair(self):
        allowed = {"calibration_support_below_minimum", "nonpositive_mu_squared_denominator"}
        unsupported = [u for u in self.units if u["state"] != "fitted"]
        self.assertTrue(unsupported, "本轮应存在 unsupported 单元，否则阈值形同虚设")
        for unit in unsupported:
            with self.subTest(unit=(unit["short_product_id"], unit["fold_index"], unit["band"])):
                receipt = unit["fallback_receipt"]
                self.assertIn(receipt["reason_code"], allowed)
                self.assertFalse(receipt["default_alpha_written"])
                self.assertFalse(receipt["imputed"])
                self.assertIsNone(unit["alpha_fold_safe"])

    def test_alpha_is_recomputable_and_bounded(self):
        for unit in (u for u in self.units if u["state"] == "fitted"):
            with self.subTest(unit=(unit["order"], unit["band"], unit["fold_index"])):
                expected = (
                    unit["calibration"]["numerator_sum_mu_rho"]
                    / unit["calibration"]["denominator_sum_mu_squared"]
                )
                self.assertAlmostEqual(unit["alpha_fold_safe"], max(0.0, min(1.0, expected)), places=12)


class LeakageAndIndependenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = read(LEDGER)

    def test_actual_calibration_never_touches_core_or_buffer(self):
        for check in self.ledger["leakage_checks"]:
            with self.subTest(fold=check["fold_index"]):
                self.assertFalse(check["actual_calibration_intersects_core_or_buffer"])
                self.assertEqual(check["violations"], [])

    def test_shared_calibration_is_reported_pairwise_not_hidden(self):
        pairs = self.ledger["fold_pairwise_shared_actual_calibration"]
        self.assertEqual(len(pairs), EXPECTED_FOLDS * (EXPECTED_FOLDS - 1) // 2)
        for pair in pairs:
            self.assertIn("shares_actual_calibration", pair)
            self.assertIn("shared_pixel_count_range", pair)

    def test_folds_are_declared_non_independent(self):
        statement = self.ledger["independence_statement"]
        self.assertIn("不是统计独立重复", statement)
        self.assertIn("effective n", statement)
        self.assertFalse(self.ledger["boundary"]["effective_n_or_p_value_computed"])


class DescriptiveScoringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = read(RESIDUAL)
        cls.ledger = read(LEDGER)

    def test_residual_definition_and_denominator_come_from_stage_7_0(self):
        protocol = self.summary["scoring_protocol"]
        self.assertEqual(protocol["residual_definition"], "residual = rho_hat - rho_obs")
        self.assertIn("base_valid_land", protocol["coverage_denominator"])
        self.assertEqual(protocol["minimum_reporting_unit"], "acquisition × band × fold")
        self.assertIn("evaluation_protocol.md", protocol["source"])

    def test_four_accounting_columns_reported_for_every_unit(self):
        for unit in self.ledger["units"]:
            with self.subTest(unit=(unit["order"], unit["band"], unit["fold_index"])):
                accounting = unit["holdout_core_accounting"]
                for field in (
                    "core_total_pixels",
                    "upstream_valid_pixels",
                    "geometry_proxy_supported_pixels",
                    "scored_pixels",
                ):
                    self.assertIn(field, accounting)
                self.assertLessEqual(accounting["scored_pixels"], accounting["upstream_valid_pixels"])
                self.assertLessEqual(accounting["upstream_valid_pixels"], accounting["core_total_pixels"])

    def test_unsupported_units_are_not_scored_as_zero_error(self):
        for unit in self.ledger["units"]:
            if unit["state"] != "fitted":
                with self.subTest(unit=(unit["short_product_id"], unit["fold_index"])):
                    self.assertEqual(unit["residual"]["state"], "not_scored")
                    self.assertNotIn("signed_bias", unit["residual"])

    def test_no_pooled_statistics_beyond_median_and_range(self):
        for key, block in self.summary["by_band_and_fold"].items():
            with self.subTest(cell=key):
                if block["scored_unit_count"]:
                    for metric in ("signed_bias", "mae", "p90_absolute_residual"):
                        self.assertEqual(
                            set(block[metric]) - {"count"}, {"median", "min", "max"}
                        )

    def test_semantic_boundary_is_declared(self):
        boundary = self.summary["semantic_boundary"]
        self.assertTrue(boundary["single_roi_same_domain_diagnostic"])
        self.assertFalse(boundary["replaces_cross_domain_isolated_validation"])
        self.assertIn("Cross-Domain Isolated Validation", boundary["statement"])
        self.assertIn("combined_risk_stress", boundary["sampling_bias"])
        self.assertIn("不构成独立样本", boundary["independence"])

    def test_input_members_verified_fail_closed_before_read(self):
        """执行器直接读 observation stack 的字节，读之前必须先验明身份，否则生成链不自证。"""
        for payload in (self.ledger, self.summary):
            with self.subTest(artifact=payload["schema"]):
                verification = payload["input_member_verification"]
                self.assertEqual(verification["policy"], "fail_closed_before_read")
                self.assertEqual(verification["verified_member_count"], EXPECTED_ACQUISITIONS)
                self.assertEqual(len(verification["members"]), EXPECTED_ACQUISITIONS)
                self.assertEqual(
                    verification["authority"]["field"], "members[].member_sha256"
                )
                for member in verification["members"]:
                    self.assertRegex(member["sha256"], r"^[0-9a-f]{64}$")

    def test_report_core_gap_count_matches_manifest(self):
        """报告里「距离为 0 的 core 对数」必须与 topology manifest 一致（曾出现事实漂移）。"""
        topology = read(TOPOLOGY)
        zero_pairs = [p for p in topology["pairwise_cores"] if p["core_to_core_distance_m"] == 0.0]
        zero_folds = [f for f in topology["folds"] if f["nearest_other_core_distance_m"] == 0.0]
        self.assertEqual(len(zero_pairs), 1)
        self.assertEqual(len(zero_folds), 2)
        report = (STAGE_ROOT / "reports/spatial-blocking-report-v1.md").read_text(encoding="utf-8")
        self.assertIn("恰有一对", report)
        self.assertNotIn("其中两对 core 距离为 0", report)

    def test_upstream_freeze_untouched(self):
        for payload in (self.ledger, self.summary):
            boundary = payload["boundary"]
            self.assertFalse(boundary["earth_engine_called"])
            self.assertFalse(boundary["frozen_evidence_rewritten"])
            self.assertFalse(boundary["membership_changed"])
            self.assertFalse(boundary["split_reassigned"])
            self.assertFalse(boundary["topology_changed_after_freeze"])
            self.assertFalse(boundary["mechanism_compared_or_ranked"])


if __name__ == "__main__":
    unittest.main()
