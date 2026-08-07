"""Stage 7.2 ②④⑤⑥⑦ 的不变量。

守的是「支持不足必须变成一条有原因的记录，而不是一个看起来正常的 alpha」，
以及「几何许可、观测有效性、标定支持三者不得互相冒充」。
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_2_baseline_fit"
STAGE_7_1 = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack"
FITTER_PATH = STAGE_ROOT / "scripts/fit_baseline_v1.py"

MCONF_PATH = STAGE_ROOT / "evidence/mconf-registry-v1.json"
ALPHA_PATH = STAGE_ROOT / "evidence/alpha-reference-full-support-v1.json"
LEDGER_PATH = STAGE_ROOT / "evidence/support-loss-ledger-v1.json"
FOLD_RULE_PATH = STAGE_ROOT / "evidence/fold-safe-alpha-rule-v1.json"
SCHEMA_V2_PATH = STAGE_ROOT / "configs/validity-support-schema-v2.json"

UNIVERSE_SIZE = 21
ELIGIBLE = 18
MIN_SUPPORT = 271


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FITTER = load_module("stage7_2_fitter_under_test", FITTER_PATH)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class MconfFactorIdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = read(MCONF_PATH)

    def test_mconf_is_a_single_architecture_factor_not_composite_confidence(self):
        identity = self.registry["factor_identity"]
        self.assertEqual(identity["architecture_factor"], "geometry_visibility")
        self.assertFalse(identity["is_composite_confidence"])
        self.assertEqual(identity["may_merge_with"], [])

    def test_threshold_is_inherited_from_stage_7_0(self):
        identity = self.registry["factor_identity"]
        self.assertEqual(identity["threshold"], 0.1)
        self.assertFalse(identity["thresholds_invented"])
        self.assertIn("baseline_spec", identity["threshold_source"])

    def test_coverage_gap_is_declared_not_hidden(self):
        identity = self.registry["factor_identity"]
        self.assertEqual(identity["coverage"], "self_shadow_only")
        for gap in ("cast_shadow", "horizon_occlusion", "disocclusion_boundary"):
            self.assertIn(gap, identity["not_covered"])

    def test_mconf_generated_for_all_21_members_not_just_eligible(self):
        self.assertEqual(len(self.registry["members"]), UNIVERSE_SIZE)
        for member in self.registry["members"]:
            with self.subTest(order=member["order"]):
                self.assertEqual(member["evidence_membership"], "included")
                self.assertGreater(member["mconf_one_count"], 0)


class AlphaEstimationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = read(ALPHA_PATH)
        cls.units = cls.registry["units"]

    def test_every_unit_is_exactly_fitted_or_unsupported(self):
        self.assertEqual(len(self.units), ELIGIBLE * 2)
        for unit in self.units:
            with self.subTest(unit=(unit["order"], unit["band"])):
                self.assertIn(unit["state"], {"fitted", "unsupported_calibration"})
                if unit["state"] == "fitted":
                    self.assertIsNotNone(unit["alpha_reference_full_support"])
                    self.assertIsNone(unit["fallback_receipt"])
                else:
                    self.assertIsNone(unit["alpha_reference_full_support"])
                    self.assertIsNotNone(unit["fallback_receipt"])

    def test_unsupported_units_carry_a_closed_set_reason_and_no_default_alpha(self):
        allowed = {"calibration_support_below_minimum", "nonpositive_mu_squared_denominator"}
        unsupported = [u for u in self.units if u["state"] != "fitted"]
        self.assertTrue(unsupported, "本轮应存在 unsupported 单元，否则阈值形同虚设")
        for unit in unsupported:
            with self.subTest(product=unit["short_product_id"], band=unit["band"]):
                receipt = unit["fallback_receipt"]
                self.assertIn(receipt["reason_code"], allowed)
                self.assertFalse(receipt["default_alpha_written"])
                self.assertFalse(receipt["imputed"])
                self.assertIn("raw_counts", receipt)

    def test_threshold_is_enforced_exactly_as_frozen(self):
        threshold = self.registry["minimum_support_threshold"]
        self.assertEqual(threshold["value"], MIN_SUPPORT)
        self.assertEqual(threshold["unit"], "calibration_lit_pixels")
        for unit in self.units:
            with self.subTest(unit=(unit["order"], unit["band"])):
                if unit["sample_count"] < MIN_SUPPORT:
                    self.assertEqual(unit["state"], "unsupported_calibration")
                elif unit["denominator_sum_mu_squared"] > 0:
                    self.assertEqual(unit["state"], "fitted")

    def test_alpha_is_recomputable_from_recorded_numerator_and_denominator(self):
        for unit in (u for u in self.units if u["state"] == "fitted"):
            with self.subTest(unit=(unit["order"], unit["band"])):
                expected = unit["numerator_sum_mu_rho"] / unit["denominator_sum_mu_squared"]
                self.assertAlmostEqual(unit["alpha_raw_before_clip"], expected, places=12)
                self.assertGreaterEqual(unit["alpha_reference_full_support"], 0.0)
                self.assertLessEqual(unit["alpha_reference_full_support"], 1.0)

    def test_alpha_carries_its_architecture_state_class(self):
        for unit in self.units:
            self.assertEqual(unit["parameter_role"], "scene_local_calibration_nuisance")
            self.assertEqual(unit["evaluation_role"], "non_evaluative")
            self.assertEqual(unit["architecture_state_class"], "N_t")

    def test_no_stratum_dimension_was_introduced(self):
        estimator = self.registry["estimator"]
        self.assertFalse(estimator["stratum_dimension_added"])
        self.assertFalse(estimator["intercept_or_diffuse_added"])
        self.assertEqual(estimator["fitting_key"], "acquisition x band")

    def test_bands_are_estimated_independently(self):
        by_order = {}
        for unit in self.units:
            by_order.setdefault(unit["order"], {})[unit["band"]] = unit
        for order, bands in by_order.items():
            with self.subTest(order=order):
                self.assertEqual(set(bands), {"SR_B4", "SR_B5"})
                if bands["SR_B4"]["state"] == "fitted":
                    self.assertNotEqual(
                        bands["SR_B4"]["numerator_sum_mu_rho"],
                        bands["SR_B5"]["numerator_sum_mu_rho"],
                    )
                    self.assertEqual(
                        bands["SR_B4"]["denominator_sum_mu_squared"],
                        bands["SR_B5"]["denominator_sum_mu_squared"],
                    )


class SupportLossLedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = read(LEDGER_PATH)
        cls.schema_v2 = read(SCHEMA_V2_PATH)

    def test_ledger_closes_arithmetically_per_acquisition(self):
        """base_valid_land 减去几何机制拒绝必须精确等于 calibration_lit。"""
        for record in self.ledger["per_acquisition"]:
            with self.subTest(order=record["order"]):
                self.assertEqual(
                    record["base_valid_land"] - record["mconf_mechanism_zero"]["total"],
                    record["calibration_lit"],
                )

    def test_mconf_zero_subclasses_are_mutually_exclusive_and_exhaustive(self):
        for record in self.ledger["per_acquisition"]:
            with self.subTest(order=record["order"]):
                mconf_zero = record["mconf_mechanism_zero"]
                self.assertEqual(
                    mconf_zero["near_zero"] + mconf_zero["self_shadow"], mconf_zero["total"]
                )

    def test_no_parallel_label_system_was_created(self):
        authority = self.ledger["taxonomy_authority"]
        self.assertFalse(authority["parallel_label_system_created"])
        self.assertIn("v2_delta_amendment", authority)

    def test_schema_v2_amends_v1_without_editing_it(self):
        amends = self.schema_v2["amends"]
        self.assertEqual(amends["schema_id"], "mountainrs-stage7.1r-validity-support-schema-v1")
        self.assertFalse(amends["predecessor_edited"])
        v1_path = STAGE_7_1 / "configs/validity-support-schema-v1.json"
        self.assertEqual(FITTER.sha256_file(v1_path), amends["sha256"])

    def test_mconf_mechanism_zero_is_registered_under_the_active_bucket(self):
        kind = self.schema_v2["added_deprivation_kinds"]["mconf_mechanism_zero"]
        self.assertEqual(kind["parent"], "active")
        self.assertEqual(kind["provenance_class"], "unsupported")
        self.assertEqual(kind["factor"], "geometry_visibility")
        self.assertIn("mconf_mechanism_zero", self.schema_v2["exclusivity_after_amendment"]["active_kinds"])
        self.assertFalse(self.schema_v2["exclusivity_after_amendment"]["kinds_additive"])

    def test_upstream_exclusion_maps_to_v1_rather_than_replacing_it(self):
        mapping = self.schema_v2["label_mappings"]["observation_or_upstream_validity_exclusion"]
        self.assertFalse(mapping["is_new_category"])
        self.assertIn("passive", mapping["maps_to_v1"])
        self.assertIn("active", mapping["maps_to_v1"])


class FoldSafeRuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rule = read(FOLD_RULE_PATH)

    def test_rule_is_frozen_but_not_instantiated(self):
        self.assertEqual(self.rule["status"], "frozen")
        boundary = self.rule["boundary"]
        self.assertFalse(boundary["block_topology_instantiated"])
        self.assertFalse(boundary["fold_membership_defined"])
        self.assertFalse(boundary["fold_specific_alpha_computed"])

    def test_reference_alpha_may_never_score_its_own_block(self):
        rule = self.rule["rules"]["R1_reference_alpha_is_non_evaluative"]
        self.assertIn("禁止用于任何 held-out block 的正式成绩", rule["statement"])
        self.assertIn("non_evaluative", rule["statement"])
        self.assertIn("alpha-reference-full-support-v1.json", rule["applies_to"])

    def test_fallbacks_are_explicitly_forbidden(self):
        forbidden = self.rule["rules"]["R3_insufficient_support_is_typed_not_repaired"]["forbidden_fallbacks"]
        self.assertIn("默认 alpha", forbidden)
        self.assertIn("插补", forbidden)

    def test_threshold_and_buffer_are_locked_against_stage_7_3(self):
        params = self.rule["frozen_parameters"]
        self.assertEqual(params["minimum_calibration_lit_pixels"], MIN_SUPPORT)
        self.assertEqual(params["buffer_width_pixels"], MIN_SUPPORT)
        self.assertFalse(params["threshold_may_be_relaxed_by_stage_7_3"])

    def test_known_risk_is_transferred_with_numbers_not_vaguely(self):
        risk = self.rule["known_risk_transferred_to_stage_7_3"]
        self.assertEqual(risk["roi_independent_scale_capacity"]["roi_pixels"], [650, 752])
        self.assertGreater(risk["per_scene_headroom"]["lowest_fitted_calibration_lit"], 0)
        self.assertEqual(len(risk["per_scene_headroom"]["already_unsupported_at_full_support"]), 2)


class OperationBoundaryTest(unittest.TestCase):
    def test_no_scoring_or_residual_anywhere(self):
        for path in (MCONF_PATH, ALPHA_PATH, LEDGER_PATH):
            with self.subTest(artifact=path.name):
                boundary = read(path)["boundary"]
                self.assertFalse(boundary["scored"])
                self.assertFalse(boundary["residual_computed"])
                self.assertFalse(boundary["confidence_computed"])
                self.assertFalse(boundary["block_or_fold_instantiated"])

    def test_frozen_contracts_are_bound_by_hash(self):
        registry = read(ALPHA_PATH)
        for key in ("mconf_subprotocol", "calibration_contract"):
            with self.subTest(contract=key):
                record = registry["frozen_inputs"][key]
                path = STAGE_ROOT / record["relative_path"]
                self.assertEqual(FITTER.sha256_file(path), record["sha256"])

    def test_upstream_freeze_untouched(self):
        for path in (MCONF_PATH, ALPHA_PATH, LEDGER_PATH):
            boundary = read(path)["boundary"]
            self.assertFalse(boundary["earth_engine_called"])
            self.assertFalse(boundary["frozen_evidence_rewritten"])
            self.assertFalse(boundary["membership_changed"])
            self.assertFalse(boundary["split_reassigned"])


if __name__ == "__main__":
    unittest.main()
