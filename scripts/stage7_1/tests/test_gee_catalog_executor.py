from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
PYTHON_EXECUTOR = SCRIPT_DIR / "gee_catalog_audit.py"
JAVASCRIPT_REFERENCE = SCRIPT_DIR / "gee_catalog_audit.js"


def python_constants() -> dict[str, object]:
    tree = ast.parse(PYTHON_EXECUTOR.read_text(encoding="utf-8"))
    values: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            try:
                values[target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return values


def javascript_scalar(source: str, name: str) -> object:
    match = re.search(rf"var {re.escape(name)} = ([^;]+);", source)
    if not match:
        raise AssertionError(f"JavaScript constant {name} is missing")
    value = match.group(1).strip()
    if value.startswith("'") or value.startswith('"'):
        return value[1:-1]
    if value.startswith("["):
        return ast.literal_eval(value)
    if "." in value:
        return float(value)
    return int(value)


class FrozenSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.python_source = PYTHON_EXECUTOR.read_text(encoding="utf-8")
        cls.javascript_source = JAVASCRIPT_REFERENCE.read_text(encoding="utf-8")
        cls.python_values = python_constants()

    def test_frozen_constants_match_javascript(self) -> None:
        for name in (
            "COLLECTION_ID",
            "START_UTC",
            "END_UTC",
            "WRS_PATH",
            "WRS_ROW",
            "TARGET_CRS",
            "TARGET_TRANSFORM",
            "TARGET_PIXEL_COUNT",
            "MIN_FOOTPRINT_COVERAGE",
        ):
            self.assertEqual(
                self.python_values[name],
                javascript_scalar(self.javascript_source, name),
                name,
            )
        self.assertIn(
            "ee.Geometry.Rectangle(\n  [292230, 3451230, 311730, 3473790]",
            self.javascript_source,
        )
        self.assertEqual(
            self.python_values["TARGET_BOUNDS"],
            [292230, 3451230, 311730, 3473790],
        )

    def test_exportable_fields_match_javascript(self) -> None:
        match = re.search(
            r"var requiredExportableProperties = \[(.*?)\];",
            self.javascript_source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        javascript_fields = re.findall(r"'([^']+)'", match.group(1))
        self.assertEqual(
            self.python_values["REQUIRED_EXPORTABLE_PROPERTIES"],
            javascript_fields,
        )

    def test_scope_is_exhaustive_and_not_ranked(self) -> None:
        for source in (self.python_source, self.javascript_source):
            self.assertNotRegex(source, r"\.limit\s*\(")
            self.assertNotRegex(
                source,
                r"\.sort\s*\(\s*[\"']CLOUD_COVER",
            )
        self.assertIn(".toList(cataloged.size())", self.javascript_source)
        self.assertIn(".toList(cataloged.size())", self.python_source)
        self.assertIn("duplicate acquisition_id", self.python_source)

    def test_output_schema_and_state_boundaries(self) -> None:
        for required in (
            "mountainrs-stage7.1-acquisition-catalog-v1",
            '"stack_eligible": "not_yet_evaluated"',
            '"formal_split": None',
            '"model_eligible": "not_adjudicated_stage_7_2"',
            '"query_only": True',
            '"exports_allowed": False',
        ):
            self.assertIn(required, self.python_source)

    def test_forbidden_actions_absent(self) -> None:
        forbidden = (
            r"\bExport\.",
            r"ee\.batch\.Export",
            r"ee\.data\.createAsset",
            r"ee\.data\.startIngestion",
            r"getDownloadURL",
            r"getThumbURL",
            r"\bfit\s*\(",
            r"\bscore\s*\(",
            r"\bresidual\b",
        )
        for pattern in forbidden:
            self.assertNotRegex(self.python_source, pattern)
            self.assertNotRegex(self.javascript_source, pattern)


if __name__ == "__main__":
    unittest.main()
