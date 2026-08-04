from __future__ import annotations

import ast
import copy
import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage7_real_weak_closure/stage7_1_observation_stack"
SCRIPT_PATH = STAGE_ROOT / "scripts/audit_export_retry_amendment_v2.py"
AMENDMENT_PATH = STAGE_ROOT / "evidence/export-retry-amendment-v2-order1-attempt2.json"
MANIFEST_PATH = STAGE_ROOT / "evidence/export-manifest-v2.json"
CATALOG_PATH = STAGE_ROOT / "data/raw/acquisition-catalog.json"
CAUSAL_AUDIT_PATH = STAGE_ROOT / "evidence/source-mask-causal-audit-v1.json"
JOURNAL_PATH = STAGE_ROOT / "evidence/export-attempts-v2.jsonl"


def load_auditor():
    spec = importlib.util.spec_from_file_location("stage7_1_retry_auditor", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load retry amendment auditor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDITOR = load_auditor()


class RetryAmendmentAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.amendment = AUDITOR.load_json(AMENDMENT_PATH)

    def audit(self, amendment: dict[str, object]) -> dict[str, object]:
        return AUDITOR.validate_amendment(
            amendment,
            MANIFEST_PATH,
            CATALOG_PATH,
            CAUSAL_AUDIT_PATH,
            JOURNAL_PATH,
        )

    def assert_rejected(self, amendment: dict[str, object], pattern: str) -> None:
        with self.assertRaisesRegex(AUDITOR.RetryAmendmentError, pattern):
            self.audit(amendment)

    def test_exact_technical_amendment_passes(self) -> None:
        result = self.audit(copy.deepcopy(self.amendment))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["max_pixels"], 489552)
        self.assertFalse(result["semantic_change"])

    def test_any_grid_band_or_eligibility_change_fails(self) -> None:
        grid = copy.deepcopy(self.amendment)
        grid["unchanged_semantic_anchors"]["transform"][2] += 15
        self.assert_rejected(grid, "semantic anchor drift")
        bands = copy.deepcopy(self.amendment)
        bands["unchanged_semantic_anchors"]["bands"].pop()
        self.assert_rejected(bands, "band semantics")
        eligibility = copy.deepcopy(self.amendment)
        eligibility["unchanged_semantic_anchors"]["stack_eligible"] = True
        self.assert_rejected(eligibility, "semantic anchor drift")

    def test_only_service_reported_maxpixels_value_is_permitted(self) -> None:
        arbitrary = copy.deepcopy(self.amendment)
        arbitrary["sole_execution_amendment"]["to"] = 500000
        self.assert_rejected(arbitrary, "only the service-reported")
        missing_failure = copy.deepcopy(self.amendment)
        missing_failure["prior_attempt"]["task_id"] = "fake"
        self.assert_rejected(missing_failure, "prior task lineage")

    def test_auditor_is_local_only(self) -> None:
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("ee", imports)
        for forbidden in ("ee.batch", "toDrive(", "toAsset(", "getDownloadURL(", "requests.", "urllib."):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
