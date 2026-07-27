from __future__ import annotations

import ast
import datetime as dt
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1]
PYTHON_EXECUTOR = SCRIPT_DIR / "gee_catalog_audit.py"
JAVASCRIPT_REFERENCE = SCRIPT_DIR / "gee_catalog_audit.js"


def load_executor_module():
    spec = importlib.util.spec_from_file_location(
        "stage7_1_gee_catalog_audit",
        PYTHON_EXECUTOR,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Python executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def python_summary_band_count(source: str) -> int:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "summary_image"
            for target in node.targets
        ):
            continue
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "unmask"
            and isinstance(call.func.value, ast.Call)
            and call.func.value.args
            and isinstance(call.func.value.args[0], ast.List)
        ):
            return len(call.func.value.args[0].elts)
    raise AssertionError("Python summary_image band list is missing")


def javascript_summary_band_count(source: str) -> int:
    match = re.search(
        r"var summaryImage = ee\.Image\.cat\(\[(.*?)\]\)\.unmask\(0\);",
        source,
        re.DOTALL,
    )
    if not match:
        raise AssertionError("JavaScript summaryImage band list is missing")
    return len(
        re.findall(
            r"^    (?:ee\.Image|qaClear|water|numericValid|baseValid|baseValidLand|qa\.bitwiseAnd)",
            match.group(1),
            re.MULTILINE,
        )
    )


class FrozenSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.python_source = PYTHON_EXECUTOR.read_text(encoding="utf-8")
        cls.javascript_source = JAVASCRIPT_REFERENCE.read_text(encoding="utf-8")
        cls.python_values = python_constants()
        cls.executor = load_executor_module()

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
            "SUMMARY_REDUCTION_BAND_COUNT",
            "SUMMARY_REDUCTION_MAX_PIXELS",
            "SUMMARY_BATCH_SIZE",
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

    def test_frozen_summary_reduction_budget(self) -> None:
        target_pixels = self.python_values["TARGET_PIXEL_COUNT"]
        reduction_bands = self.python_values["SUMMARY_REDUCTION_BAND_COUNT"]
        max_pixels = self.python_values["SUMMARY_REDUCTION_MAX_PIXELS"]
        pixel_demand = target_pixels * reduction_bands
        self.assertEqual(target_pixels, 650 * 752)
        self.assertEqual(reduction_bands, 12)
        self.assertEqual(
            python_summary_band_count(self.python_source),
            reduction_bands,
        )
        self.assertEqual(
            javascript_summary_band_count(self.javascript_source),
            reduction_bands,
        )
        self.assertEqual(pixel_demand, 5_865_600)
        self.assertLess(pixel_demand, max_pixels)
        self.assertEqual(max_pixels, 10_000_000)
        self.assertEqual(self.python_values["SUMMARY_BATCH_SIZE"], 1)
        self.assertEqual(
            self.executor.validate_reduction_budget(),
            pixel_demand,
        )
        with self.assertRaisesRegex(ValueError, "exceeds maxPixels budget"):
            self.executor.validate_reduction_budget(
                max_pixels=pixel_demand - 1,
            )
        self.assertIn(
            "SUMMARY_REDUCTION_PIXEL_DEMAND > SUMMARY_REDUCTION_MAX_PIXELS",
            self.javascript_source,
        )
        for source in (self.python_source, self.javascript_source):
            self.assertNotIn("bestEffort", source)

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

    def test_candidate_universe_contains_no_summary_aggregation(self) -> None:
        tree = ast.parse(self.python_source)
        universe = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "build_candidate_universe"
        )
        universe_source = ast.get_source_segment(self.python_source, universe)
        self.assertIsNotNone(universe_source)
        self.assertNotIn("reduceRegion", universe_source)
        self.assertNotIn("qa_and_coverage_summary", universe_source)
        javascript_universe = re.search(
            r"function buildCandidateUniverse\(\) \{(.*?)\n\}",
            self.javascript_source,
            re.DOTALL,
        )
        self.assertIsNotNone(javascript_universe)
        self.assertNotIn("reduceRegion", javascript_universe.group(1))
        self.assertNotIn("qaAndCoverageSummary", javascript_universe.group(1))

    def test_summary_execution_is_strictly_serial_batch_size_one(self) -> None:
        self.assertEqual(self.python_values["SUMMARY_BATCH_SIZE"], 1)
        self.assertEqual(
            javascript_scalar(self.javascript_source, "SUMMARY_BATCH_SIZE"),
            1,
        )
        self.assertEqual(
            javascript_scalar(
                self.javascript_source,
                "MAXIMUM_IN_FLIGHT_SUMMARY_AGGREGATIONS",
            ),
            1,
        )
        self.assertIn(
            "for asset_id in ordered_asset_ids:",
            self.python_source,
        )
        self.assertIn(
            "buildSingleSummary(assetIds[index]).getInfo(",
            self.javascript_source,
        )
        self.assertIn(
            "runNext(index + SUMMARY_BATCH_SIZE)",
            self.javascript_source,
        )
        for forbidden_parallelism in (
            "ThreadPool",
            "ProcessPool",
            "concurrent.futures",
            "asyncio.gather",
            "Promise.all",
        ):
            self.assertNotIn(forbidden_parallelism, self.python_source)
            self.assertNotIn(forbidden_parallelism, self.javascript_source)

    def test_staging_reuse_is_idempotent_and_not_a_formal_result(self) -> None:
        asset_id = (
            "LANDSAT/LC08/C02/T1_L2/LC08_130038_20230101"
        )
        response = {
            "schema": self.executor.SUMMARY_RESPONSE_SCHEMA,
            "earth_engine_asset_id": asset_id,
            "summary": {
                field: index
                for index, field in enumerate(self.executor.SUMMARY_FIELDS)
            },
        }
        fetch = mock.Mock(return_value=response)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            first = self.executor.load_or_fetch_single_summary(
                directory,
                request_sha256="a" * 64,
                executor_sha256="b" * 64,
                asset_id=asset_id,
                fetch_summary=fetch,
            )
            second = self.executor.load_or_fetch_single_summary(
                directory,
                request_sha256="a" * 64,
                executor_sha256="b" * 64,
                asset_id=asset_id,
                fetch_summary=fetch,
            )
            record_path = self.executor.summary_staging_path(
                directory,
                asset_id,
            )
            record = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(first, second)
        fetch.assert_called_once_with(asset_id)
        self.assertEqual(record["schema"], self.executor.STAGING_RECORD_SCHEMA)
        self.assertNotEqual(record["schema"], self.executor.OUTPUT_SCHEMA)
        self.assertTrue(
            str(self.executor.STAGING_ROOT).startswith(
                ".cache/earthengine/catalog-audit-v5"
            )
        )

    def test_atomic_assembly_fails_when_any_candidate_is_missing(self) -> None:
        asset_id = (
            "LANDSAT/LC08/C02/T1_L2/LC08_130038_20230101"
        )
        universe = [
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "earth_engine_asset_id": asset_id,
                },
            }
        ]
        with self.assertRaisesRegex(
            RuntimeError,
            "requires one summary per candidate",
        ):
            self.executor.assemble_raw_features(universe, {})

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

    def test_attestation_has_exact_non_secret_fields_and_30_minute_ttl(
        self,
    ) -> None:
        verified_at = dt.datetime(2026, 7, 23, 15, 0, tzinfo=dt.timezone.utc)
        probe = {
            "verified_at": self.executor.format_utc(verified_at),
            "health_probe_input_sha256": self.executor.sha256_text(
                self.executor.HEALTH_PROBE_INPUT
            ),
            "health_probe_response_sha256": self.executor.sha256_text(
                self.executor.HEALTH_PROBE_INPUT
            ),
        }
        attestation = self.executor.build_attestation(
            "gee-et-playground",
            probe,
        )
        self.assertEqual(set(attestation), self.executor.ATTESTATION_FIELDS)
        self.assertFalse(attestation["credential_body_read"])
        self.assertEqual(
            self.executor.parse_utc(attestation["valid_until"])
            - self.executor.parse_utc(attestation["verified_at"]),
            dt.timedelta(minutes=30),
        )
        serialized = json.dumps(attestation).lower()
        for forbidden_secret_field in (
            "email",
            "token",
            "refresh_token",
            "authorization_code",
            "credential_path",
        ):
            self.assertNotIn(forbidden_secret_field, serialized)

    def test_attestation_project_and_expiry_fail_closed(self) -> None:
        verified_at = dt.datetime(2026, 7, 23, 15, 0, tzinfo=dt.timezone.utc)
        probe = {
            "verified_at": self.executor.format_utc(verified_at),
            "health_probe_input_sha256": self.executor.sha256_text(
                self.executor.HEALTH_PROBE_INPUT
            ),
            "health_probe_response_sha256": self.executor.sha256_text(
                self.executor.HEALTH_PROBE_INPUT
            ),
        }
        attestation = self.executor.build_attestation(
            "gee-et-playground",
            probe,
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "auth-attestation.json"
            path.write_text(json.dumps(attestation), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "project mismatch"):
                self.executor.validate_session_attestation(
                    path,
                    "wrong-project",
                    now=verified_at + dt.timedelta(minutes=1),
                )
            with self.assertRaisesRegex(ValueError, "expired"):
                self.executor.validate_session_attestation(
                    path,
                    "gee-et-playground",
                    now=verified_at + dt.timedelta(minutes=30),
                )

    def test_catalog_requires_fresh_attestation_and_live_reverification(
        self,
    ) -> None:
        verified_at = dt.datetime(2026, 7, 23, 15, 0, tzinfo=dt.timezone.utc)
        probe = {
            "verified_at": self.executor.format_utc(verified_at),
            "health_probe_input_sha256": self.executor.sha256_text(
                self.executor.HEALTH_PROBE_INPUT
            ),
            "health_probe_response_sha256": self.executor.sha256_text(
                self.executor.HEALTH_PROBE_INPUT
            ),
        }
        attestation = self.executor.build_attestation(
            "gee-et-playground",
            probe,
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "auth-attestation.json"
            path.write_text(json.dumps(attestation), encoding="utf-8")
            with mock.patch.object(
                self.executor,
                "run_live_health_probe",
                return_value=probe,
            ) as live_probe:
                resolved, resolved_probe = (
                    self.executor.verify_authenticated_session(
                        path,
                        "gee-et-playground",
                        now=verified_at + dt.timedelta(minutes=1),
                    )
                )
            self.assertEqual(resolved, attestation)
            self.assertEqual(resolved_probe, probe)
            live_probe.assert_called_once_with(
                "gee-et-playground",
                now=verified_at + dt.timedelta(minutes=1),
            )
            with mock.patch.object(
                self.executor,
                "run_live_health_probe",
                side_effect=RuntimeError("live probe failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "live probe failed"):
                    self.executor.verify_authenticated_session(
                        path,
                        "gee-et-playground",
                        now=verified_at + dt.timedelta(minutes=1),
                    )

    def test_live_probe_initializes_exact_project_and_rejects_bad_echo(
        self,
    ) -> None:
        fixed_now = dt.datetime(2026, 7, 23, 15, 0, tzinfo=dt.timezone.utc)
        with (
            mock.patch.object(self.executor.ee, "Initialize") as initialize,
            mock.patch.object(self.executor.ee, "String") as ee_string,
        ):
            ee_string.return_value.getInfo.return_value = "unexpected"
            with self.assertRaisesRegex(RuntimeError, "unexpected response"):
                self.executor.run_live_health_probe(
                    "gee-et-playground",
                    now=fixed_now,
                )
        initialize.assert_called_once_with(project="gee-et-playground")
        ee_string.assert_called_once_with(self.executor.HEALTH_PROBE_INPUT)

    def test_audit_verifies_session_before_building_catalog(self) -> None:
        tree = ast.parse(self.python_source)
        run_audit = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_audit"
        )
        calls = [
            node.func.id
            for node in ast.walk(run_audit)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        self.assertLess(
            calls.index("verify_authenticated_session"),
            calls.index("build_candidate_universe"),
        )


if __name__ == "__main__":
    unittest.main()
