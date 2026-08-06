"""Semantic invariants of the Stage 7.1-R L0 evidence layer.

这些用例守的是语义而不是数字：证据成员资格不可被操作资格撤销、剥夺归因的
passive/active 二分互斥且穷尽、细分类不可相加、unsupported 不得被读成零值目标。
数字只在能证明语义的地方出现。
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack"
BUILDER_PATH = STAGE_ROOT / "scripts/build_observation_evidence_v1.py"

SCHEMA_PATH = STAGE_ROOT / "configs/validity-support-schema-v1.json"
LEDGER_PATH = STAGE_ROOT / "evidence/observation-support-ledger-v1.json"
MANIFEST_PATH = STAGE_ROOT / "evidence/observation-evidence-manifest-v1.json"
VIEW_PATH = STAGE_ROOT / "evidence/stage-7.2-direct-only-input-view-v1.json"
RECONCILIATION_PATH = STAGE_ROOT / "evidence/evidence-reconciliation-audit-v1.json"
STACK_MANIFEST_PATH = STAGE_ROOT / "evidence/stack_manifest.json"
OBSERVATION_SCHEMA_PATH = STAGE_ROOT / "configs/observation-schema.yaml"

UNIVERSE_SIZE = 21
ELIGIBLE = 18
UNSUPPORTED = 3


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("stage7_1r_evidence_builder_under_test", BUILDER_PATH)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class EvidenceMembershipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = read(SCHEMA_PATH)
        cls.ledger = read(LEDGER_PATH)
        cls.manifest = read(MANIFEST_PATH)
        cls.view = read(VIEW_PATH)

    def test_all_acquisitions_are_irrevocable_evidence_members(self):
        members = self.manifest["members"]
        self.assertEqual(len(members), UNIVERSE_SIZE)
        self.assertTrue(all(m["evidence_membership"] == "included" for m in members))
        self.assertTrue(all(m["acquisition_status"] == "acquired" for m in members))
        self.assertFalse(self.manifest["state_boundary"]["membership_revocable"])

    def test_membership_survives_operation_level_unsupported(self):
        """3 景在 direct-only 下无支持，但它们仍然是证据成员——这是本节点存在的理由。"""
        unsupported = self.view["unsupported_records"]
        self.assertEqual(len(unsupported), UNSUPPORTED)
        self.assertTrue(all(r["evidence_membership"] == "included" for r in unsupported))
        self.assertTrue(
            self.manifest["state_boundary"]["operation_level_unsupported_may_not_revoke_membership"]
        )
        self.assertFalse(self.view["state_boundary"]["changes_evidence_membership"])

    def test_membership_may_not_depend_on_quality_or_model_signals(self):
        forbidden = self.schema["fields"]["evidence_membership"]["must_not_depend_on"]
        for signal in ("cloud", "qa", "source_mask", "residual", "fit", "split", "model_result"):
            self.assertIn(signal, forbidden)

    def test_universe_version_scopes_irrevocability(self):
        universe = self.manifest["evidence_universe"]
        self.assertEqual(universe["member_count"], UNIVERSE_SIZE)
        self.assertEqual(
            universe["membership_irrevocability"]["scope"], "within_this_universe_version_only"
        )
        for axis in ("temporal_scope", "sensor_product", "spatial_scope", "grid_identity"):
            self.assertIn(axis, universe["membership_irrevocability"]["new_universe_required_on"])


class DeprivationTaxonomyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = read(SCHEMA_PATH)
        cls.ledger = read(LEDGER_PATH)

    def test_top_level_split_is_exclusive_and_exhaustive_per_acquisition(self):
        for member in self.ledger["per_acquisition"]:
            with self.subTest(order=member["order"]):
                self.assertTrue(member["deprivation"]["partition_check"]["exhaustive_and_exclusive"])

    def test_passive_and_active_are_additive_but_kinds_are_not(self):
        totals = self.ledger["deprivation_totals"]
        self.assertTrue(totals["additive"])
        self.assertFalse(totals["kind_totals_additive"])
        self.assertFalse(self.schema["deprivation_taxonomy"]["exclusivity"]["kinds_additive"])
        self.assertTrue(
            self.schema["deprivation_taxonomy"]["exclusivity"]["top_level_mutually_exclusive"]
        )

    def test_kind_overlap_accounts_for_the_gap_against_the_active_bucket(self):
        """细分类之和减去重叠必须精确回到 active 桶——这正是「不可相加」的量化证明。"""
        totals = self.ledger["deprivation_totals"]
        kinds = totals["kind_totals_not_additive"]
        active_kinds_sum = (
            kinds["qa_rejected"] + kinds["reflectance_out_of_range"] + kinds["terrain_nodata"]
        )
        overlap = totals["overlap_evidence"]["active_kind_overlap_pixel_events"]
        self.assertGreater(overlap, 0, "重叠为零则本项目无法证明细分类确实会重叠")
        self.assertEqual(
            active_kinds_sum - overlap, totals["top_level_mutually_exclusive"]["active"]
        )

    def test_passive_and_active_are_reported_separately(self):
        totals = self.ledger["deprivation_totals"]
        self.assertIn("passive", totals["top_level_mutually_exclusive"])
        self.assertIn("active", totals["top_level_mutually_exclusive"])
        self.assertNotIn("total", totals["top_level_mutually_exclusive"])

    def test_water_is_not_a_deprivation(self):
        self.assertIn("water 不属于 deprivation", self.schema["deprivation_taxonomy"]["reporting_rule"])
        self.assertGreater(self.ledger["deprivation_totals"]["water_excluded_from_land_total"], 0)

    def test_no_acquisition_kind_is_empty_under_full_cover(self):
        taxonomy = self.schema["deprivation_taxonomy"]["kinds"]["no_acquisition"]
        self.assertEqual(taxonomy["parent"], "passive")
        self.assertEqual(taxonomy["expected_count_in_this_universe"], 0)

    def test_three_unsupported_acquisitions_are_actively_rejected_not_unobserved(self):
        view = read(VIEW_PATH)
        for record in view["unsupported_records"]:
            with self.subTest(acquisition=record["short_product_id"]):
                self.assertEqual(record["deprivation_kind"], "active")
                self.assertEqual(record["deprivation_detail"], "qa_rejected")
                self.assertEqual(record["qa_clear_support_count"], 0)


class ProvenanceAndTrainingSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = read(SCHEMA_PATH)
        cls.manifest = read(MANIFEST_PATH)
        cls.view = read(VIEW_PATH)

    def test_l0_may_not_emit_observed_inferred(self):
        classes = self.schema["provenance_classes"]["classes"]
        self.assertFalse(classes["observed_inferred"]["producible_at_l0"])
        self.assertFalse(classes["prior_only"]["producible_at_l0"])
        self.assertTrue(classes["unsupported"]["producible_at_l0"])
        self.assertTrue(classes["support_ready"]["producible_at_l0"])
        emitted = {m["provenance_class"] for m in self.manifest["members"]}
        self.assertTrue(emitted <= {"support_ready", "unsupported"})

    def test_support_ready_is_not_an_architecture_class(self):
        self.assertFalse(
            self.schema["provenance_classes"]["classes"]["support_ready"]["is_architecture_class"]
        )

    def test_downstream_may_not_fork_the_label_system(self):
        binding = self.schema["provenance_classes"]["downstream_binding"]
        self.assertEqual(binding["parallel_label_systems"], "prohibited")
        for stage in ("stage_7_4_residual_reliability", "stage_7_8_l3_encoding", "stage_7_11_calibration_ood"):
            self.assertIn(stage, binding["inherited_by"])

    def test_training_semantics_are_frozen_against_negative_sampling(self):
        for payload in (
            self.schema["training_semantics"],
            self.manifest["training_semantics"],
            self.view["state_boundary"]["training_semantics"],
        ):
            self.assertEqual(payload["unsupported_as_target"], "forbidden")
            self.assertEqual(payload["unsupported_as_negative_sample"], "forbidden")
            self.assertEqual(payload["loss_participation"], "excluded")
            self.assertEqual(payload["loss_value"], "not_computed")
            self.assertEqual(payload["unsupported_encoded_as_zero_state"], "forbidden")

    def test_confidence_is_not_projected_here(self):
        self.assertEqual(self.schema["confidence_projection_status"], "not_computed")
        self.assertEqual(self.manifest["confidence_projection_status"], "not_computed")


class GeometrySupportHandoffTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = read(MANIFEST_PATH)
        cls.view = read(VIEW_PATH)

    def test_solar_geometry_is_transcribed_for_every_acquisition(self):
        members = self.manifest["members"]
        self.assertEqual(len(members), UNIVERSE_SIZE)
        for member in members:
            with self.subTest(order=member["order"]):
                solar = member["solar_geometry"]
                self.assertIsNotNone(solar["sun_azimuth_deg"])
                self.assertIsNotNone(solar["sun_elevation_deg"])
                self.assertEqual(solar["azimuth_source_field"], "SUN_AZIMUTH")
                self.assertEqual(solar["elevation_source_field"], "SUN_ELEVATION")
                self.assertTrue(solar["transcribed_not_computed"])

    def test_geometry_support_is_declared_not_computed_with_inputs_ready(self):
        for member in self.manifest["members"]:
            self.assertEqual(member["geometry_support_status"], "not_computed")
        handoff = self.view["handoff_to_stage_7_2"]
        self.assertTrue(handoff["geometry_support_inputs_ready"])
        self.assertEqual(handoff["geometry_support_status"], "not_computed")
        self.assertEqual(handoff["geometry_support_evaluation_scope"], "all_21_acquisitions")

    def test_mask_identities_stay_separate(self):
        masks = self.manifest["mask_identities"]
        self.assertTrue(masks["Msource"]["delivered_by_this_node"])
        self.assertTrue(masks["Mqa"]["delivered_by_this_node"])
        self.assertFalse(masks["Mgeom_support"]["delivered_by_this_node"])
        self.assertFalse(masks["Mloss_support"]["delivered_by_this_node"])
        self.assertEqual(masks["Mgeom_support"]["owner"], "stage_7_2")


class SupportProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = read(LEDGER_PATH)
        cls.view = read(VIEW_PATH)

    def test_observation_opportunity_is_a_declared_constant_field(self):
        opportunity = self.ledger["per_world_position"]["observation_opportunity_count"]
        self.assertTrue(opportunity["constant_field"])
        self.assertEqual(opportunity["value"], UNIVERSE_SIZE)
        self.assertIn("full-cover", opportunity["justification"])
        self.assertNotIn(
            "observation_opportunity_count", self.ledger["per_world_position"]["count_rasters"]
        )

    def test_per_world_position_rasters_exist_and_match_recorded_hashes(self):
        for name, record in self.ledger["per_world_position"]["count_rasters"].items():
            with self.subTest(raster=name):
                path = STAGE_ROOT / record["relative_path"]
                self.assertTrue(path.is_file())
                self.assertEqual(BUILDER.sha256_file(path), record["sha256"])
                self.assertEqual(record["granularity"], "world_position")
                self.assertLessEqual(record["value_range"][1], UNIVERSE_SIZE)

    def test_support_gap_is_stated_as_absence_not_as_low_confidence(self):
        gap = self.ledger["per_world_position"]["support_gap"]
        self.assertGreater(gap["pixel_count"], 0)
        self.assertIn("不是低置信度", gap["note"])
        self.assertEqual(
            gap["raster_reference"],
            self.ledger["per_world_position"]["count_rasters"]["base_valid_land_count"][
                "relative_path"
            ],
        )

    def test_operation_view_preserves_the_frozen_split_and_its_scope(self):
        split = self.view["split"]
        self.assertEqual(split["split_scope"], "stage_7_2_direct_only_eligible_subset")
        self.assertEqual(split["counts"], {"train": 10, "validation": 3, "test": 5})
        self.assertFalse(split["reassigned_by_this_node"])
        self.assertEqual(split["members_outside_split_remain_evidence_members"], UNSUPPORTED)

    def test_operation_view_counts_agree_with_history(self):
        counts = self.view["counts"]
        self.assertEqual(counts["universe"], UNIVERSE_SIZE)
        self.assertEqual(counts["eligible_candidate"], ELIGIBLE)
        self.assertEqual(counts["operation_scoped_unsupported"], UNSUPPORTED)
        self.assertFalse(self.view["frozen_predicate"]["re_adjudicated_by_this_node"])
        self.assertFalse(self.view["frozen_predicate"]["thresholds_invented"])


class SupersessionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = read(SCHEMA_PATH)
        cls.manifest = read(MANIFEST_PATH)
        cls.view = read(VIEW_PATH)
        cls.reconciliation = read(RECONCILIATION_PATH)

    def test_successors_bind_uniquely_to_the_superseded_evidence(self):
        supersession = self.manifest["supersession"]
        self.assertEqual(supersession["semantic_successor_of"], "mountainrs-stage7.1-stack-manifest-v1")
        self.assertEqual(
            supersession["supersession_scope"], "validity_semantics_and_support_projection"
        )
        self.assertEqual(
            supersession["predecessor_sha256"],
            self.reconciliation["reconciled_evidence"]["stack_manifest"]["sha256"],
        )
        self.assertFalse(supersession["predecessor_edited"])

    def test_schema_supersedes_without_editing_the_old_schema(self):
        supersession = self.schema["supersession"]
        self.assertEqual(
            supersession["supersession_scope"], "validity_semantics_and_support_projection"
        )
        self.assertFalse(supersession["predecessor_edited"])
        self.assertEqual(
            BUILDER.sha256_file(OBSERVATION_SCHEMA_PATH), supersession["predecessor_sha256"]
        )

    def test_predecessor_files_are_untouched_on_disk(self):
        """旧 stack_manifest 必须仍是对账时的那一份字节，不得被后继覆盖或改名。"""
        self.assertTrue(STACK_MANIFEST_PATH.is_file())
        self.assertEqual(
            BUILDER.sha256_file(STACK_MANIFEST_PATH),
            self.reconciliation["reconciled_evidence"]["stack_manifest"]["sha256"],
        )

    def test_input_view_binds_to_the_evidence_manifest_by_hash(self):
        source = self.view["source_evidence_manifest"]
        self.assertEqual(source["manifest_id"], self.manifest["manifest_id"])
        self.assertEqual(BUILDER.sha256_file(MANIFEST_PATH), source["sha256"])
        self.assertEqual(source["universe_id"], self.manifest["evidence_universe"]["universe_id"])


class FailClosedTest(unittest.TestCase):
    def test_builder_refuses_to_run_on_a_failed_reconciliation(self):
        """地基没验过就不许动工：对账未通过时构建器必须拒绝启动。"""
        reconciliation = read(RECONCILIATION_PATH)
        reconciliation["status"] = "failed_reconciliation"
        reconciliation["failed_checks"] = ["C4"]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            broken = tmp_path / "reconciliation.json"
            broken.write_text(json.dumps(reconciliation), encoding="utf-8")
            argv = [
                "build_observation_evidence_v1.py",
                "--reconciliation", str(broken),
                "--schema", str(SCHEMA_PATH),
                "--ledger", str(tmp_path / "ledger.json"),
                "--evidence-manifest", str(tmp_path / "manifest.json"),
                "--input-view", str(tmp_path / "view.json"),
                "--raster-dir", str(tmp_path / "rasters"),
            ]
            with mock.patch("sys.argv", argv):
                with self.assertRaises(SystemExit) as caught:
                    BUILDER.main()
            self.assertIn("reconciliation", str(caught.exception))
            self.assertFalse((tmp_path / "ledger.json").exists())

    def test_terrain_hash_drift_stops_the_build(self):
        support_audit = read(STAGE_ROOT / "evidence/local-support-audit-v1.json")
        support_audit["terrain_geometry"]["dem"]["sha256"] = "0" * 64
        with self.assertRaises(SystemExit) as caught:
            BUILDER.read_terrain(support_audit)
        self.assertIn("drifted", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
