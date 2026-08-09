#!/usr/bin/env python3
"""Synthetic, result-blind tests for the Stage 7.4 M2 executor."""

from __future__ import annotations

import importlib.util
import math
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "run_risk_proxy_v1.py"
SPEC = importlib.util.spec_from_file_location("risk_proxy_v1", SCRIPT)
assert SPEC and SPEC.loader
rp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rp)


def synthetic_config() -> dict:
    return {
        "M2_guards": {
            "N_scored_min_per_scope": 271,
            "accepted_n_min_per_admissible_exact_point": 271,
            "unique_proxy_values_min_per_scope": 3,
            "admissible_exact_points_min_per_scope": 3,
            "canonical_reachable_grid_points_min_per_scope": 3,
        },
        "fixed_grid": {"target_denominator": 20},
        "tolerances": {
            "tau_score": {"absolute": 1e-12, "relative": 1e-12},
            "tau_outcome": {"absolute": 1e-12, "relative": 1e-12},
        },
        "verdict": {
            "mapping": {
                "order_consistent": "descriptive_ordering_signal",
                "order_inverted": "directionally_adverse",
                "flat": "descriptive_non_discriminative",
                "mixed": "descriptive_non_discriminative",
            }
        },
    }


class StrataAndR1Test(unittest.TestCase):
    def test_strata_boundaries_are_exclusive_and_exhaustive(self) -> None:
        values = np.array([-1.0, 0.0, 0.1, 0.10001, 0.4, 0.40001, 0.7, 0.70001, 1.0])
        masks = rp.classify_strata(values)
        self.assertEqual([int(m.sum()) for m in masks.values()], [2, 1, 2, 2, 2])
        self.assertTrue(np.all(sum(mask.astype("uint8") for mask in masks.values()) == 1))

    def test_out_of_range_stops(self) -> None:
        with self.assertRaises(rp.ProtocolStop) as caught:
            rp.classify_strata(np.array([1.0001]))
        self.assertEqual(caught.exception.reason, "base_valid_land_cos_i_outside_minus1_plus1")

    def test_nodata_and_out_of_domain_values_do_not_expand_error_domain(self) -> None:
        values = np.array([-9999.0, 1.5, 0.2], dtype="float32")
        domain = np.array([False, False, True])
        masks = rp.classify_strata(values, check_domain=domain)
        self.assertEqual(sum(int(mask.sum()) for mask in masks.values()), 1)
        with self.assertRaises(rp.ProtocolStop):
            rp.classify_strata(values, check_domain=np.array([False, True, True]))

    def test_r1_signed_zero_branch_needs_no_detector(self) -> None:
        score = rp.risk_proxy_from_cos_i(np.array([np.float32(1.0)], dtype="float32"))
        self.assertEqual(float(score[0]), 0.0)
        self.assertFalse(bool(np.signbit(score[0])))
        self.assertEqual(rp.R1_UNREACHABLE_REASON,
                         "numeric_equal_bit_distinct_proxy_order_undefined")
        self.assertFalse(any(name.startswith("detect_numeric_equal") for name in dir(rp)))


class CurveMechanicsTest(unittest.TestCase):
    def test_bit_exact_ties_are_atomic(self) -> None:
        scores = np.array([0.1, 0.1, 0.2, 0.3], dtype="float32")
        residuals = np.array([1.0, -3.0, 2.0, 4.0])
        points = rp.exact_risk_points(scores, residuals, denominator=5)
        self.assertEqual([p["accepted_pixel_count"] for p in points], [2, 3, 4])
        self.assertAlmostEqual(points[0]["accepted_set_MAE"], 2.0)

    def test_fixed_grid_integer_mapping_and_dedup(self) -> None:
        points = [
            {"exact_point_index": 1, "accepted_pixel_count": 10,
             "selective_prediction_coverage": 0.25, "accepted_set_MAE": 1.0},
            {"exact_point_index": 2, "accepted_pixel_count": 20,
             "selective_prediction_coverage": 0.50, "accepted_set_MAE": 2.0},
            {"exact_point_index": 3, "accepted_pixel_count": 30,
             "selective_prediction_coverage": 0.75, "accepted_set_MAE": 3.0},
            {"exact_point_index": 4, "accepted_pixel_count": 40,
             "selective_prediction_coverage": 1.00, "accepted_set_MAE": 4.0},
        ]
        rows = rp.map_fixed_grid(points, denominator=40, target_denominator=4)
        self.assertEqual([row["status"] for row in rows],
                         ["reachable", "reachable", "reachable", "reachable"])
        self.assertEqual([row["exact_point_index"] for row in rows], [1, 2, 3, 4])
        rp.verify_fixed_grid(points, rows, denominator=40, target_denominator=4)

    def test_fixed_grid_unreachable_duplicate_and_tamper_stop(self) -> None:
        points = [
            {"exact_point_index": 1, "accepted_pixel_count": 30,
             "selective_prediction_coverage": 0.3, "accepted_set_MAE": 1.0},
            {"exact_point_index": 2, "accepted_pixel_count": 60,
             "selective_prediction_coverage": 0.6, "accepted_set_MAE": 2.0},
        ]
        rows = rp.map_fixed_grid(points, denominator=100, target_denominator=10)
        self.assertEqual(rows[0]["reason"], "below_min_accepted_support")
        self.assertEqual(rows[3]["status"], "duplicate")
        self.assertEqual(rows[-1]["reason"], "above_max_reachable_coverage")
        rp.verify_fixed_grid(points, rows, denominator=100, target_denominator=10)
        rows[2]["canonical_target_q"] = 0.4
        with self.assertRaises(rp.ProtocolStop) as caught:
            rp.verify_fixed_grid(points, rows, denominator=100, target_denominator=10)
        self.assertEqual(caught.exception.reason, "fixed_grid_invariant_failure")

    def test_staircase_aurc(self) -> None:
        points = [
            {"selective_prediction_coverage": 0.2, "accepted_set_MAE": 1.0},
            {"selective_prediction_coverage": 0.5, "accepted_set_MAE": 2.0},
            {"selective_prediction_coverage": 0.9, "accepted_set_MAE": 4.0},
        ]
        result = rp.staircase_aurc(points)
        self.assertAlmostEqual(result["area"], 1.1)
        self.assertAlmostEqual(result["span"], 0.7)
        self.assertAlmostEqual(result["normalized"], 1.1 / 0.7)

    def test_curve_shapes(self) -> None:
        def rows(values):
            return [{"accepted_set_MAE": value} for value in values]
        self.assertEqual(rp.curve_shape(rows([1, 2, 3]), 1e-12, 1e-12),
                         "order_consistent")
        self.assertEqual(rp.curve_shape(rows([3, 2, 1]), 1e-12, 1e-12),
                         "order_inverted")
        self.assertEqual(rp.curve_shape(rows([1, 1, 1]), 1e-12, 1e-12), "flat")
        self.assertEqual(rp.curve_shape(rows([1, 2, 1]), 1e-12, 1e-12), "mixed")

    def test_T_zero_uses_bare_closed_set_reason(self) -> None:
        with self.assertRaises(rp.ProtocolStop) as caught:
            rp.coverage_values(0, 0, 0)
        self.assertEqual(caught.exception.reason, "zero_core_total_pixel_count")

    def test_zero_D_and_zero_S_coverage_are_typed(self) -> None:
        self.assertEqual(
            rp.coverage_values(10, 0, 0)["reason"],
            "zero_base_valid_land_denominator",
        )
        result = rp.coverage_values(10, 5, 0)
        self.assertEqual(result["scoring_coverage"], 0.0)
        self.assertEqual(result["selective_prediction_coverage"], 0.0)
        self.assertIsNone(result["acceptance_given_scored"])
        self.assertEqual(result["reason"], "zero_scored_denominator")

    def test_M2_full_scope_is_evaluable(self) -> None:
        scores = np.linspace(0.0, 1.0, 1000, dtype="float32")
        residuals = np.linspace(0.0, 2.0, 1000, dtype="float64")
        result = rp.evaluate_scope(scores, residuals, 1000, 1000, synthetic_config())
        self.assertEqual(result["scope_gate"], "evaluated")
        self.assertEqual(result["risk_proxy_verdict"], "descriptive_ordering_signal")
        self.assertGreaterEqual(
            sum(row["status"] == "reachable" for row in result["grid"]), 3
        )
        self.assertTrue(math.isfinite(result["AURC"]["normalized"]))

    def test_curve_output_materializes_summary_and_fixed_grid_only(self) -> None:
        scores = np.linspace(0.0, 1.0, 1000, dtype="float32")
        residuals = np.linspace(0.0, 2.0, 1000, dtype="float64")
        result = rp.evaluate_scope(scores, residuals, 1000, 1000, synthetic_config())
        rows, _summary = rp.curve_records(
            {"acquisition": "A", "split": "train", "band": "SR_B4", "fold": 1},
            "unit_all_scored",
            "primary",
            result,
        )
        self.assertEqual(rows[0]["point_kind"], "scope_summary")
        self.assertEqual(rows[0]["exact_point_count"], 1000)
        self.assertFalse(rows[0]["exact_point_sequence_materialized"])
        self.assertEqual(len(rows), 21)
        self.assertTrue(all(row["point_kind"] == "fixed_grid" for row in rows[1:]))

    def test_support_precedence(self) -> None:
        result = rp.evaluate_scope(
            np.arange(10, dtype="float32"), np.arange(10, dtype="float64"),
            100, 100, synthetic_config(),
        )
        self.assertEqual(result["risk_proxy_verdict"],
                         "not_evaluable_insufficient_scored_support")
        self.assertEqual(result["not_evaluable_reason"], "N_scored_below_271")


class AggregationTest(unittest.TestCase):
    def test_acquisitions_receive_equal_weight(self) -> None:
        rows = [
            {"acquisition": "A", "band": "SR_B4", "curve_scope": "unit_all_scored",
             "AURC_normalized": 1.0, "score_range": 0.5,
             "risk_proxy_verdict": "descriptive_ordering_signal",
             "not_evaluable_reason": None},
            {"acquisition": "A", "band": "SR_B4", "curve_scope": "unit_all_scored",
             "AURC_normalized": 3.0, "score_range": 0.7,
             "risk_proxy_verdict": "descriptive_ordering_signal",
             "not_evaluable_reason": None},
            {"acquisition": "B", "band": "SR_B4", "curve_scope": "unit_all_scored",
             "AURC_normalized": 10.0, "score_range": 0.9,
             "risk_proxy_verdict": "directionally_adverse",
             "not_evaluable_reason": None},
        ]
        verdicts = [
            "not_evaluable_insufficient_scored_support",
            "not_evaluable_score_degenerate",
            "descriptive_ordering_signal",
            "directionally_adverse",
            "descriptive_non_discriminative",
        ]
        output = rp.aggregate_scope_summaries(rows, verdicts, ["N_scored_below_271"])[0]
        self.assertAlmostEqual(
            output["continuous_median_range"]
            ["across_acquisition_equal_weight_median_range"]
            ["AURC_normalized"]["median"],
            6.0,
        )
        self.assertEqual(output["risk_proxy_verdict_counts"]["descriptive_ordering_signal"], 2)
        self.assertEqual(output["risk_proxy_verdict_counts"]["directionally_adverse"], 1)
        self.assertEqual(output["risk_proxy_verdict_counts"]["descriptive_non_discriminative"], 0)
        within = output["continuous_median_range"]["within_acquisition_fold_median_range"]
        self.assertEqual(within[0]["fold_median_range"]["AURC_normalized"]["min"], 1.0)
        self.assertEqual(within[0]["fold_median_range"]["AURC_normalized"]["max"], 3.0)


class PublicationTest(unittest.TestCase):
    def test_verify_and_execute_require_cross_audit_binding(self) -> None:
        parser = rp.build_parser()
        common = [
            "--protocol", "p", "--config", "c", "--preflight", "f",
            "--audit", "a", "--protocol-sha256", "0", "--config-sha256", "0",
            "--preflight-sha256", "0", "--audit-sha256", "0",
        ]
        self.assertEqual(parser.parse_args(["verify", *common]).audit, Path("a"))
        self.assertEqual(parser.parse_args(["execute", *common,
                                            "--freeze-receipt-id", "rc_x",
                                            "--freeze-after-revision", "72"]).audit, Path("a"))

    def test_partial_publication_is_rolled_back_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {
                "outputs": {
                    "a": {"path_base": "node_container_root", "relative_path": "a.json"},
                    "b": {"path_base": "node_container_root", "relative_path": "b.json"},
                }
            }
            real_link = rp.os.link
            calls = 0

            def fail_second(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("synthetic link failure")
                return real_link(source, target)

            with mock.patch.object(rp, "NODE_ROOT", root), mock.patch.object(
                rp.os, "link", side_effect=fail_second
            ):
                with self.assertRaises(rp.ProtocolStop):
                    rp.publish_outputs(config, {"a": b"a", "b": b"b"})
            self.assertFalse((root / "a.json").exists())
            self.assertFalse((root / "b.json").exists())


if __name__ == "__main__":
    unittest.main()
