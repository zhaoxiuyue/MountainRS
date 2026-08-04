"""Fail-closed checks for the v3 declared-grid manifest and its auditor."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack"
SCRIPT_PATH = STAGE_ROOT / "scripts/audit_export_manifest_v3.py"
MANIFEST_PATH = STAGE_ROOT / "evidence/export-manifest-v3.json"
V2_MANIFEST_PATH = STAGE_ROOT / "evidence/export-manifest-v2.json"
CATALOG_PATH = STAGE_ROOT / "data/raw/acquisition-catalog.json"
CAUSAL_AUDIT_PATH = STAGE_ROOT / "evidence/source-mask-causal-audit-v1.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = load_module("stage7_1_export_manifest_v3_auditor_under_test", SCRIPT_PATH)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit(manifest):
    return AUDITOR.validate_manifest(
        manifest, read(CATALOG_PATH), CATALOG_PATH, read(CAUSAL_AUDIT_PATH), CAUSAL_AUDIT_PATH
    )


class DeclaredGridManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = read(MANIFEST_PATH)

    def test_frozen_manifest_passes(self):
        summary = audit(self.manifest)
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["manifest_version"], 3)
        self.assertEqual(summary["acquisition_count"], 21)
        self.assertEqual(summary["unique_output_paths"], 21)
        self.assertEqual(summary["unique_idempotency_seeds"], 21)
        self.assertEqual(summary["tasks_created"], 0)
        self.assertEqual(summary["assets_created"], 0)

    def test_target_grid_is_the_frozen_grid_verbatim(self):
        self.assertEqual(self.manifest["target_grid"], read(V2_MANIFEST_PATH)["target_grid"])

    def test_declared_dimensions_equal_frozen_shape(self):
        shape = self.manifest["target_grid"]["shape"]
        spec = self.manifest["grid_specification"]
        self.assertEqual(spec["dimensions"], f"{shape['width']}x{shape['height']}")
        self.assertEqual(spec["dimensions_width"], shape["width"])
        self.assertEqual(spec["dimensions_height"], shape["height"])

    def test_region_parameter_is_omitted(self):
        self.assertEqual(self.manifest["execution"]["region_parameter"], "omitted")
        self.assertTrue(self.manifest["grid_specification"]["region_parameter_prohibited"])

    def test_max_pixels_equals_frozen_pixel_count_as_guard(self):
        self.assertEqual(
            self.manifest["execution"]["max_pixels"], self.manifest["target_grid"]["pixel_count"]
        )

    def test_storage_semantics_inherited_from_v2_verbatim(self):
        v2 = read(V2_MANIFEST_PATH)
        self.assertEqual(self.manifest["raw_encoding"], v2["raw_encoding"])
        self.assertEqual(self.manifest["execution"]["bands"], v2["execution"]["bands"])
        self.assertEqual(self.manifest["frozen_contract"], v2["frozen_contract"])
        self.assertEqual(self.manifest["source_evidence"], v2["source_evidence"])

    def test_v1_and_v2_remain_immutable_anchors(self):
        supersession = self.manifest["supersession"]
        self.assertEqual(supersession["v2_immutability"], "historical_anchor_do_not_rewrite")
        self.assertEqual(supersession["v1_immutability"], "historical_anchor_do_not_rewrite")
        self.assertEqual(supersession["v2_attempt_lineage_frozen_in"], "evidence/export-attempts-v2.jsonl")

    def test_attempt_and_retry_caps_are_not_loosened(self):
        v2 = read(V2_MANIFEST_PATH)["lifecycle"]
        lifecycle = self.manifest["lifecycle"]
        self.assertEqual(
            lifecycle["maximum_attempts_per_acquisition"], v2["maximum_attempts_per_acquisition"]
        )
        self.assertEqual(
            lifecycle["maximum_retries_after_terminal_failed"], v2["maximum_retries_after_terminal_failed"]
        )
        self.assertTrue(lifecycle["retry_only_after_terminal_failed"])

    def test_v3_uses_its_own_journal(self):
        self.assertEqual(
            self.manifest["lifecycle"]["attempt_journal_relative_path"], "evidence/export-attempts-v3.jsonl"
        )

    def test_vacate_is_recorded_and_rejected_artifact_retained(self):
        policy = self.manifest["path_policy"]
        self.assertTrue(policy["existing_target_vacated_before_v3"])
        rejected = STAGE_ROOT / self.manifest["root_cause"]["rejected_v2_attempt2_artifact"]["relative_path"]
        self.assertTrue(rejected.is_file())
        self.assertEqual(
            AUDITOR.sha256_file(rejected),
            self.manifest["root_cause"]["rejected_v2_attempt2_artifact"]["sha256"],
        )

    def test_rejected_artifact_may_never_reoccupy_the_canonical_slot(self):
        # Slot emptiness is a submission-time precondition enforced by the
        # executor preflight, not a manifest invariant.  What the manifest
        # auditor must guarantee is weaker and permanent: whatever occupies the
        # canonical slot is never the rejected 651x752 product.
        policy = self.manifest["path_policy"]
        target = (
            STAGE_ROOT
            / policy["root_relative_path"]
            / self.manifest["acquisitions"][0]["target_relative_to_alias"]
        )
        if target.exists():
            self.assertNotEqual(
                AUDITOR.sha256_file(target),
                self.manifest["root_cause"]["rejected_v2_attempt2_artifact"]["sha256"],
            )

    def test_eligibility_and_split_untouched(self):
        self.assertEqual(self.manifest["state_boundary"]["stack_eligible"], "not_yet_evaluated")
        self.assertEqual(self.manifest["state_boundary"]["split"], "not_yet_assigned")
        for entry in self.manifest["acquisitions"]:
            self.assertEqual(entry["stack_eligible"], "not_yet_evaluated")
            self.assertEqual(entry["split"], "not_yet_assigned")

    def test_seeds_are_v3_scoped_and_unique(self):
        seeds = [e["first_attempt_idempotency_seed"] for e in self.manifest["acquisitions"]]
        self.assertEqual(len(set(seeds)), 21)
        for seed in seeds:
            self.assertTrue(seed.startswith("mountainrs-stage7.1-export-manifest-v3:"))
            self.assertNotIn("export-manifest-v2", seed)

    def _rejects(self, mutate, fragment):
        manifest = copy.deepcopy(self.manifest)
        mutate(manifest)
        with self.assertRaises(AUDITOR.ManifestError) as caught:
            audit(manifest)
        self.assertIn(fragment, str(caught.exception))

    def test_rejects_region_reintroduction(self):
        self._rejects(lambda m: m["execution"].__setitem__("region_parameter", "rectangle"), "execution.region_parameter")

    def test_rejects_dimensions_not_matching_frozen_shape(self):
        self._rejects(lambda m: m["execution"].__setitem__("dimensions_parameter", "651x752"), "computed from the frozen shape")

    def test_rejects_inflated_max_pixels(self):
        self._rejects(lambda m: m["execution"].__setitem__("max_pixels", 489552), "maxPixels must equal the frozen pixel count")

    def test_rejects_target_grid_drift(self):
        self._rejects(lambda m: m["target_grid"]["shape"].__setitem__("width", 651), "target grid drift")

    def test_rejects_loosened_attempt_cap(self):
        self._rejects(
            lambda m: m["lifecycle"].__setitem__("maximum_attempts_per_acquisition", 5),
            "must not loosen the attempt cap",
        )

    def test_rejects_rewriting_history(self):
        self._rejects(
            lambda m: m["supersession"].__setitem__("v2_immutability", "rewritable"),
            "v2 immutability boundary missing",
        )

    def test_rejects_recorded_task_creation(self):
        self._rejects(lambda m: m["authorization"].__setitem__("tasks_created", 1), "records tasks_created")

    def test_rejects_eligibility_adjudication(self):
        self._rejects(
            lambda m: m["acquisitions"][0].__setitem__("stack_eligible", "eligible"), "eligibility changed"
        )


class ProtocolProhibitionListTest(unittest.TestCase):
    """协议正文的禁止清单必须被逐条强制，而不只是校验协议文件哈希。"""

    def setUp(self):
        self.manifest = read(MANIFEST_PATH)

    def _rejects(self, mutate, fragment):
        manifest = copy.deepcopy(self.manifest)
        mutate(manifest)
        with self.assertRaises(AUDITOR.ManifestError) as caught:
            audit(manifest)
        self.assertIn(fragment, str(caught.exception))

    def test_a1_rejects_scale_parameter(self):
        self._rejects(lambda m: m["execution"].__setitem__("scale_parameter", 30),
                      "execution.scale_parameter")

    def test_a2_rejects_best_effort(self):
        self._rejects(lambda m: m["execution"].__setitem__("best_effort", True), "bestEffort")

    def test_a3_rejects_non_nearest_resampling(self):
        self._rejects(lambda m: m["execution"].__setitem__("resampling", "bilinear"),
                      "non-nearest resampling")

    def test_a3b_rejects_explicit_resample_call(self):
        self._rejects(lambda m: m["execution"].__setitem__("explicit_resample_call", True),
                      "explicit resample call")

    def test_a4_rejects_shared_nodata(self):
        self._rejects(lambda m: m["execution"].__setitem__("format_options_no_data", 0),
                      "execution.format_options_no_data")

    def test_a5_rejects_partial_or_sharded_output(self):
        self._rejects(lambda m: m["execution"].__setitem__("skip_empty_tiles", True),
                      "partial or sharded output")

    def test_a6_rejects_region_alongside_dimensions(self):
        self._rejects(lambda m: m["execution"].__setitem__("region_parameter", "rectangle"),
                      "execution.region_parameter")

    def test_a7_rejects_hardcoded_dimensions_not_derived_from_shape(self):
        # 网格 shape 与 dimensions 同时被改成自洽的另一组值也必须拒绝，
        # 因为 target_grid 本身已被冻结。
        self._rejects(lambda m: m["execution"].__setitem__("dimensions_parameter", "651x752"),
                      "computed from the frozen shape")

    def test_a8_rejects_max_pixels_not_equal_to_pixel_count(self):
        self._rejects(lambda m: m["execution"].__setitem__("max_pixels", 489552),
                      "maxPixels must equal the frozen pixel count")

    def test_a9_amendment_must_be_present_and_bind_this_manifest(self):
        path = STAGE_ROOT / AUDITOR.AMENDMENT_JSON
        self.assertTrue(path.is_file())
        self.assertEqual(AUDITOR.sha256_file(path), AUDITOR.AMENDMENT_JSON_SHA256)
        amendment = read(path)
        self.assertEqual(amendment["status"], "frozen")
        self.assertEqual(amendment["bound_manifest"]["request_id"], self.manifest["request_id"])
        self.assertEqual(
            amendment["bound_manifest"]["sha256"], AUDITOR.sha256_file(MANIFEST_PATH)
        )

    def test_amendment_unbans_only_dimensions(self):
        amendment = read(STAGE_ROOT / AUDITOR.AMENDMENT_JSON)
        for token in ("scale", "bestEffort", "non_nearest_resampling", "shared_nodata",
                      "partial_or_sharded_output", "region_passed_together_with_dimensions"):
            self.assertIn(token, amendment["still_prohibited"])
        for amended in amendment["amends"]:
            self.assertEqual(amended["amended_token"], "dimensions")
            self.assertFalse(amended["edited_in_place"])

    def test_amended_protocols_were_not_edited_in_place(self):
        amendment = read(STAGE_ROOT / AUDITOR.AMENDMENT_JSON)
        for amended in amendment["amends"]:
            path = STAGE_ROOT / amended["document"]
            self.assertEqual(AUDITOR.sha256_file(path), amended["sha256"])

    def test_retroactive_admission_is_measured_not_asserted(self):
        amendment = read(STAGE_ROOT / AUDITOR.AMENDMENT_JSON)
        admission = amendment["retroactive_admission"]
        self.assertEqual(admission["mode"], "R")
        self.assertTrue(admission["all_products_admitted"])
        self.assertEqual(len(admission["verified_products"]), 3)
        for product in admission["verified_products"]:
            self.assertTrue(all(product["conditions"].values()))
            tif = STAGE_ROOT / self.manifest["path_policy"]["root_relative_path"] / product["product_relative_to_alias"]
            self.assertTrue(tif.is_file())
            self.assertEqual(AUDITOR.sha256_file(tif), product["product_sha256"])

    def test_admission_does_not_confer_eligibility(self):
        amendment = read(STAGE_ROOT / AUDITOR.AMENDMENT_JSON)
        self.assertIn("stack_eligible", amendment["retroactive_admission"]["meaning"])
        for entry in self.manifest["acquisitions"]:
            self.assertEqual(entry["stack_eligible"], "not_yet_evaluated")
            self.assertEqual(entry["split"], "not_yet_assigned")


if __name__ == "__main__":
    unittest.main()
