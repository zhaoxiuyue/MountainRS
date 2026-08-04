#!/usr/bin/env python3
"""Fail-closed local auditor for the Stage 7.1 v3 declared-grid manifest.

v3 supersedes v2 on the output-grid specification route only.  The storage
semantics frozen by mask-preserving-observation-storage-protocol-v2.md are
inherited verbatim; only the way the output grid is expressed changes, from
`region` geometry derivation to `crs + crsTransform + dimensions` declaration.

The program reads local evidence only.  It cannot authenticate to Earth Engine,
submit an Export task, create an asset, or download imagery.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent

MANIFEST_SCHEMA = "mountainrs-stage7.1-export-manifest-v3"
REQUEST_ID = "mountainrs-stage7.1-export-manifest-v3"
V2_MANIFEST_SHA256 = "a4a68743cfa15f89557bdd6e4371c7bcd66f8961fb6e3565def4e6c0bb5718b7"
V1_MANIFEST_SHA256 = "596171933511530ff1ecc20f07e6fc4a0c3258f01c68cff57046749af991ca25"
STORAGE_PROTOCOL = "docs/mask-preserving-observation-storage-protocol-v2.md"
V2_JOURNAL = "evidence/export-attempts-v2.jsonl"
V3_JOURNAL = "evidence/export-attempts-v3.jsonl"
REJECTED_V2_ARTIFACT = (
    "data/raw/rejected_exports/"
    "LC08_130038_20230101__SR_B4_SR_B5_QA_PIXEL__VALID__v2_attempt2_651x752_rejected.tif"
)
REJECTED_V2_SHA256 = "95474954ae832f99c49bd80f8beb37169f09ffebf463ee8871c85f360861740f"

# 网格声明修正案 v1（所有者 2026-08-04 裁决，追溯范围 R）。
# 冻结协议 A/B 原文禁止设置 dimensions；本修正案在六项绑定条件下解禁该 token，
# 其余禁止项一字不动。审计器必须校验协议的「禁止清单正文」而不只是文件哈希。
AMENDMENT_DOC = "docs/grid-declaration-amendment-v1.md"
AMENDMENT_JSON = "evidence/grid-declaration-amendment-v1.json"
AMENDMENT_SCHEMA = "mountainrs-stage7.1-grid-declaration-amendment-v1"
# 协议原文按 frozen_contract 里的 sha256 校验；修正案自身的哈希钉在这里，
# 改动修正案会立刻使审计失败——这正是本常量存在的目的。
AMENDMENT_JSON_SHA256 = "d21d34295075b6f930ea2830f53564f15313d19cf15432edac4efdeac6b5c365"
# 协议 A/B 正文明令禁止、且不被本修正案解禁的执行项。
PROHIBITED_EXECUTION_TOKENS = {
    "scale_parameter": "omitted",
    "format_options_no_data": "omitted",
    "region_parameter": "omitted",
}


def load_sibling_module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V2 = load_sibling_module("stage7_1_export_manifest_v2_auditor", "audit_export_manifest_v2.py")

ManifestError = V2.ManifestError
require = V2.require
sha256_file = V2.sha256_file
load_json = V2.load_json
canonical_json = V2.canonical_json
EXPECTED_GRID = V2.EXPECTED_GRID
EXPECTED_BANDS = V2.EXPECTED_BANDS
RAW_BANDS = V2.RAW_BANDS
VALID_BANDS = V2.VALID_BANDS
SHORT_ID_RE = V2.SHORT_ID_RE


def validate_supersession(manifest: dict[str, Any], workspace_root: Path) -> None:
    supersession = manifest.get("supersession")
    require(isinstance(supersession, dict), "supersession record missing")
    require(
        supersession.get("supersedes_grid_specification_route_only") == "evidence/export-manifest-v2.json"
        or supersession.get("supersedes_grid_specification_route_only") == "export-manifest-v2.json",
        "v3 must declare which route it supersedes",
    )
    require(supersession.get("v2_manifest_sha256") == V2_MANIFEST_SHA256, "v2 historical anchor drift")
    require(supersession.get("v2_immutability") == "historical_anchor_do_not_rewrite", "v2 immutability boundary missing")
    require(supersession.get("v1_manifest_sha256") == V1_MANIFEST_SHA256, "v1 historical anchor drift")
    require(supersession.get("v1_immutability") == "historical_anchor_do_not_rewrite", "v1 immutability boundary missing")
    require(supersession.get("storage_protocol_unchanged") is True, "v3 must inherit the v2 storage protocol")
    require(supersession.get("storage_protocol_relative_path") == STORAGE_PROTOCOL, "storage protocol anchor drift")
    require(supersession.get("v2_attempt_lineage_frozen_in") == V2_JOURNAL, "v2 attempt lineage must stay frozen")

    for relative, expected in (
        ("evidence/export-manifest-v2.json", V2_MANIFEST_SHA256),
        ("evidence/export-manifest-v1.json", V1_MANIFEST_SHA256),
    ):
        path = workspace_root / relative
        require(path.is_file(), f"historical manifest is missing: {relative}")
        require(sha256_file(path) == expected, f"historical manifest was rewritten: {relative}")

    v2_journal = workspace_root / V2_JOURNAL
    require(v2_journal.is_file(), "v2 attempt journal is missing")


def validate_grid_specification(manifest: dict[str, Any]) -> None:
    grid = manifest.get("target_grid")
    require(grid == EXPECTED_GRID, "target grid drift")
    width = EXPECTED_GRID["shape"]["width"]
    height = EXPECTED_GRID["shape"]["height"]

    spec = manifest.get("grid_specification")
    require(isinstance(spec, dict), "grid specification is missing")
    require(spec.get("method") == "declared_crs_crs_transform_and_dimensions", "v3 grid method drift")
    require(
        spec.get("superseded_method") == "derived_from_region_polygon_and_crs_transform",
        "v3 must name the superseded grid method",
    )
    require(spec.get("dimensions") == f"{width}x{height}", "declared dimensions drift")
    require(spec.get("dimensions_width") == width, "declared width drift")
    require(spec.get("dimensions_height") == height, "declared height drift")
    require(spec.get("must_equal_target_grid_shape") is True, "dimensions must be bound to the frozen shape")
    require(spec.get("region_parameter_prohibited") is True, "v3 must prohibit the region parameter")
    require(
        spec.get("client_expression_outer_operator") == "Image.clipToBoundsAndScale",
        "declared-grid client expression drift",
    )
    require(
        spec.get("client_expression_rectangle_space") == "pixel_coordinates_of_reprojected_image",
        "declared-grid rectangle space drift",
    )
    require(spec.get("client_expression_rectangle") == [0, 0, width, height], "declared-grid rectangle drift")
    require(spec.get("superseded_expression_outer_operator") == "Image.clip", "superseded expression drift")
    require(spec.get("max_pixels_equals_target_pixel_count") is True, "maxPixels must equal the frozen pixel count")
    require(spec.get("max_pixels_acts_as_failclosed_grid_guard") is True, "maxPixels fail-closed role missing")


def validate_root_cause(manifest: dict[str, Any], workspace_root: Path) -> None:
    root = manifest.get("root_cause")
    require(isinstance(root, dict), "root cause record is missing")
    require(root.get("observed_probe_origin") == [-1, -1], "skirt origin evidence drift")
    require(root.get("observed_probe_dimensions") == [652, 754], "skirt dimension evidence drift")
    require(root.get("query_path_pixel_count") == EXPECTED_GRID["pixel_count"], "query-path count drift")
    require(root.get("v2_export_path_pixel_count") == 489552, "v2 export-path count drift")
    require(root.get("our_region_and_transform_were_exact") is True, "root cause must exonerate our inputs")
    require(root.get("region_bounds_offset_from_grid_origin_metres") == 0.0, "measured region offset drift")

    rejected = root.get("rejected_v2_attempt2_artifact")
    require(isinstance(rejected, dict), "rejected v2 artifact record is missing")
    require(rejected.get("relative_path") == REJECTED_V2_ARTIFACT, "rejected artifact path drift")
    require(rejected.get("sha256") == REJECTED_V2_SHA256, "rejected artifact hash drift")
    require(rejected.get("actual_shape") == {"height": 752, "width": 651}, "rejected artifact shape drift")
    require(
        rejected.get("retained_as") == "comparison_material_for_v3_acceptance_not_a_stack_member",
        "rejected artifact role drift",
    )
    path = workspace_root / REJECTED_V2_ARTIFACT
    require(path.is_file(), "rejected v2 artifact was not retained")
    require(sha256_file(path) == REJECTED_V2_SHA256, "retained rejected artifact was modified")


def validate_vacated_target(manifest: dict[str, Any], workspace_root: Path) -> None:
    policy = manifest.get("path_policy")
    require(isinstance(policy, dict), "path policy is missing")
    require(policy.get("root_alias") == "stage_7_1_observation_stack", "output Alias drift")
    require(policy.get("root_relative_path") == "data/raw/observation_stack", "output root drift")
    require(policy.get("absolute_paths_allowed") is False, "absolute paths must be prohibited")
    require(policy.get("overwrite_existing_target") is False, "overwrite must be prohibited")
    require(policy.get("existing_target_vacated_before_v3") is True, "v3 must record the vacate step")
    require(policy.get("vacated_target_relative_path") == REJECTED_V2_ARTIFACT, "vacated target path drift")

    # Emptiness of the canonical slot is a submission-time precondition, not a
    # manifest invariant: once the audited product legitimately lands, the slot
    # is occupied by design.  The gate lives in the executor preflight, which
    # calls assert_local_target_absent before every submission.
    entry = manifest["acquisitions"][0]
    target = workspace_root / policy["root_relative_path"] / entry["target_relative_to_alias"]
    if target.exists():
        require(
            sha256_file(target) != REJECTED_V2_SHA256,
            "the rejected 651x752 artifact is back in the canonical slot",
        )


def validate_protocol_prohibition_list(manifest: dict[str, Any], workspace_root: Path) -> None:
    """校验协议正文的禁止清单，而不只是协议文件的哈希。

    事故教训：只比对 frozen_contract 里协议文件的 sha256，等于验证「文件没被改写」，
    并不验证「文件被遵守」。哈希对得上、正文被违反，审计仍会全绿。
    """
    execution = manifest.get("execution")
    require(isinstance(execution, dict), "execution contract is missing")
    grid = manifest.get("target_grid")
    require(isinstance(grid, dict), "target grid is missing")

    # 1/4/6：协议禁止项必须逐条声明为 omitted
    for field, expected in PROHIBITED_EXECUTION_TOKENS.items():
        require(
            execution.get(field) == expected,
            f"protocol prohibition violated: execution.{field} must be {expected!r}",
        )
    # 2：bestEffort 禁止
    require(execution.get("best_effort") is False, "protocol prohibition violated: bestEffort")
    # 3：只允许默认最近邻，且不得显式调用重采样
    require(
        execution.get("resampling") == "nearest_neighbor_default",
        "protocol prohibition violated: non-nearest resampling",
    )
    require(
        execution.get("explicit_resample_call") is False,
        "protocol prohibition violated: explicit resample call",
    )
    # 5：禁止分片/部分输出
    require(
        execution.get("skip_empty_tiles") is False,
        "protocol prohibition violated: partial or sharded output",
    )
    # 7：dimensions 必须由冻结 shape 算出，不接受硬编码字面量
    shape = grid.get("shape")
    require(isinstance(shape, dict), "target-grid shape is missing")
    computed = f"{shape.get('width')}x{shape.get('height')}"
    require(
        execution.get("dimensions_parameter") == computed,
        "amendment condition c3 violated: dimensions must be computed from the frozen shape",
    )
    # 8：maxPixels 必须等于冻结像元数，使网格膨胀在服务端失败
    require(
        execution.get("max_pixels") == grid.get("pixel_count"),
        "amendment condition c5 violated: maxPixels must equal the frozen pixel count",
    )

    # 9：修正案必须在场、哈希吻合，并绑回本 manifest
    amendment_path = workspace_root / AMENDMENT_JSON
    require(amendment_path.is_file(), f"grid declaration amendment is missing: {AMENDMENT_JSON}")
    require(
        sha256_file(amendment_path) == AMENDMENT_JSON_SHA256,
        "grid declaration amendment was modified",
    )
    amendment = load_json(amendment_path)
    require(amendment.get("schema") == AMENDMENT_SCHEMA, "amendment schema drift")
    require(amendment.get("status") == "frozen", "amendment is not frozen")

    doc_path = workspace_root / AMENDMENT_DOC
    require(doc_path.is_file(), f"amendment normative text is missing: {AMENDMENT_DOC}")
    require(
        sha256_file(doc_path) == amendment.get("normative_text", {}).get("sha256"),
        "amendment normative text was modified",
    )

    # 修正案点名的两份协议必须仍与它记录的哈希一致（未被就地编辑）
    for amended in amendment.get("amends", []):
        path = workspace_root / amended["document"]
        require(path.is_file(), f"amended protocol is missing: {amended['document']}")
        require(
            sha256_file(path) == amended["sha256"],
            f"amended protocol was edited in place: {amended['document']}",
        )
        require(amended.get("edited_in_place") is False, "in-place protocol edit was recorded")

    bound = amendment.get("bound_manifest", {})
    require(bound.get("request_id") == manifest.get("request_id"), "amendment binds a different manifest")
    require(
        bound.get("relative_path") == "evidence/export-manifest-v3.json",
        "amendment manifest binding path drift",
    )
    manifest_path = workspace_root / bound["relative_path"]
    require(manifest_path.is_file(), "bound manifest is missing")
    require(sha256_file(manifest_path) == bound.get("sha256"), "bound manifest hash drift")

    # 解禁范围必须仅限 dimensions；其余禁止项不得出现在解禁清单里
    still = amendment.get("still_prohibited", [])
    for token in ("scale", "bestEffort", "non_nearest_resampling", "shared_nodata",
                  "partial_or_sharded_output", "region_passed_together_with_dimensions"):
        require(token in still, f"amendment silently unbanned {token}")
    for amended in amendment.get("amends", []):
        require(amended.get("amended_token") == "dimensions", "amendment touched more than dimensions")


def validate_execution(manifest: dict[str, Any]) -> None:
    execution = manifest.get("execution")
    require(isinstance(execution, dict), "execution contract is missing")
    require(execution.get("operation") == "Export.image.toDrive", "unexpected export channel")
    require(
        execution.get("task_granularity") == "one_acquisition_one_task_one_six_band_geotiff",
        "task granularity drift",
    )
    require(execution.get("maximum_active_exports") == 1, "active export limit must be one")
    require(execution.get("file_format") == "GeoTIFF", "file format drift")
    require(execution.get("expected_files_per_task") == 1, "file count per task drift")
    require(execution.get("bands") == EXPECTED_BANDS, "six-band order or membership drift")
    require(execution.get("apply_scale_offset") is False, "raw DN must not be scaled")
    require(execution.get("resampling") == "nearest_neighbor_default", "resampling drift")
    require(execution.get("explicit_resample_call") is False, "explicit resample call is prohibited")
    require(execution.get("scale_parameter") == "omitted", "scale is prohibited")
    require(execution.get("region_parameter") == "omitted", "v3 must omit region")
    width = EXPECTED_GRID["shape"]["width"]
    height = EXPECTED_GRID["shape"]["height"]
    require(execution.get("dimensions_parameter") == f"{width}x{height}", "v3 must declare dimensions")
    require(execution.get("best_effort") is False, "bestEffort is prohibited")
    require(execution.get("crs_and_crs_transform_required") is True, "crs and crsTransform remain required")
    require(
        execution.get("max_pixels") == EXPECTED_GRID["pixel_count"],
        "maxPixels must be restored to the frozen pixel count so grid inflation fails closed",
    )
    require(
        execution.get("source_mask_extraction_before_serialization_fill") is True,
        "source mask must precede fill",
    )
    require(
        execution.get("serialization_fill")
        == {
            "allowed": True,
            "value": 0,
            "scope": "only_after_source_mask_extraction_only_for_masked_data_pixels",
        },
        "serialization-fill scope drift",
    )
    require(execution.get("format_options_no_data") == "omitted", "shared nodata must be omitted")
    require(execution.get("skip_empty_tiles") is False, "complete output requirement drift")
    destination = execution.get("external_destination")
    require(isinstance(destination, dict), "external destination is missing")
    require(destination.get("folder_name_must_be_unique") is True, "transfer folder must be unique")
    require(destination.get("canonical_local_member") is False, "Drive output is not a canonical member")


def validate_manifest(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    catalog_path: Path,
    causal_audit: dict[str, Any],
    causal_audit_path: Path,
) -> dict[str, Any]:
    workspace_root = catalog_path.parents[2]
    candidates = V2.validate_catalog(catalog, catalog_path)
    V2.validate_causal_audit(causal_audit, causal_audit_path, candidates)
    V2.validate_frozen_files(manifest, workspace_root)
    V2.validate_historical_anchors(manifest, workspace_root)

    require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema drift")
    require(manifest.get("request_id") == REQUEST_ID, "manifest request identity drift")
    require(manifest.get("manifest_version") == 3, "manifest version drift")
    require(manifest.get("status") == "preregistered", "manifest is not preregistered")

    validate_supersession(manifest, workspace_root)
    validate_root_cause(manifest, workspace_root)
    validate_grid_specification(manifest)
    validate_protocol_prohibition_list(manifest, workspace_root)
    validate_execution(manifest)

    source = manifest.get("source_evidence")
    require(isinstance(source, dict), "source evidence missing")
    require(source.get("universe_sha256") == V2.UNIVERSE_SHA256, "universe anchor drift")
    require(source.get("catalog_sha256") == V2.CATALOG_SHA256, "catalog anchor drift")
    require(source.get("export_set_policy") == "complete_v5_universe_all_21", "export set is not the full universe")
    require(source.get("export_set_is_stack_eligibility_decision") is False, "export was confused with eligibility")

    authorization = manifest.get("authorization")
    require(isinstance(authorization, dict), "authorization is missing")
    require(authorization.get("exports_allowed") is True, "v3 execution marker missing")
    require(
        authorization.get("task_creation_authorized_when_preregistered") is False,
        "preregistration created task authority",
    )
    for field in ("tasks_created", "assets_created", "imagery_created_or_downloaded"):
        require(authorization.get(field) == 0, f"immutable manifest records {field}")

    encoding = manifest.get("raw_encoding")
    require(encoding == V2.load_json(workspace_root / "evidence/export-manifest-v2.json")["raw_encoding"],
            "v3 must inherit the v2 raw encoding verbatim")

    lifecycle = manifest.get("lifecycle")
    require(isinstance(lifecycle, dict), "lifecycle is missing")
    require(lifecycle.get("maximum_active_exports") == 1, "lifecycle active limit drift")
    require(lifecycle.get("unknown_allows_resubmit") is False, "unknown outcome must block resubmission")
    require(lifecycle.get("retry_only_after_terminal_failed") is True, "retry gate drift")
    require(lifecycle.get("maximum_attempts_per_acquisition") == 2, "v3 must not loosen the attempt cap")
    require(lifecycle.get("maximum_retries_after_terminal_failed") == 1, "v3 must not loosen the retry cap")
    require(lifecycle.get("preserve_all_task_id_lineage") is True, "task lineage must be preserved")
    require(lifecycle.get("status_history_is_append_only") is True, "status history must be append-only")
    require(lifecycle.get("active_or_submitted_is_success") is False, "submission was confused with success")
    require(
        lifecycle.get("succeeded_requires_local_hash_and_reconciliation") is True,
        "local reconciliation gate missing",
    )
    require(lifecycle.get("attempt_journal_relative_path") == V3_JOURNAL, "v3 must use its own attempt journal")

    validate_vacated_target(manifest, workspace_root)

    entries = manifest.get("acquisitions")
    require(isinstance(entries, list) and len(entries) == 21, "manifest must contain 21 acquisitions")
    expected_ids = [candidate["acquisition_id"] for candidate in candidates]
    actual_ids = [entry.get("acquisition_id") for entry in entries]
    require(actual_ids == expected_ids, "manifest acquisition set or order drift")

    output_paths: set[str] = set()
    seeds: set[str] = set()
    for order, (entry, candidate) in enumerate(zip(entries, candidates, strict=True), start=1):
        short_id = candidate["system_index"]
        require(SHORT_ID_RE.fullmatch(short_id) is not None, f"invalid short product ID: {short_id}")
        require(entry.get("order") == order, f"order drift for {short_id}")
        require(entry.get("short_product_id") == short_id, f"short product identity drift for {short_id}")
        relative = entry.get("target_relative_to_alias")
        expected_path = f"{short_id}/{short_id}__SR_B4_SR_B5_QA_PIXEL__VALID.tif"
        V2.validate_relative_path(relative, expected_path)
        require(relative not in output_paths, f"output path collision: {relative}")
        output_paths.add(relative)
        seed = f"{REQUEST_ID}:{candidate['acquisition_id']}:attempt-1"
        require(entry.get("first_attempt_idempotency_seed") == seed, f"idempotency seed drift for {short_id}")
        require(seed not in seeds, f"duplicate idempotency seed for {short_id}")
        seeds.add(seed)
        require(entry.get("state") == "not_requested", f"unexpected state for {short_id}")
        require(entry.get("attempts") == [], f"task lineage must be empty for {short_id}")
        require(entry.get("source_mask_preflight") == "m1_audited", f"M1 mask audit marker missing for {short_id}")
        require(entry.get("stack_eligible") == "not_yet_evaluated", f"eligibility changed for {short_id}")
        require(entry.get("split") == "not_yet_assigned", f"split changed for {short_id}")

    state = manifest.get("state_boundary")
    require(isinstance(state, dict), "state boundary is missing")
    require(state.get("stack_eligible") == "not_yet_evaluated", "global eligibility changed")
    require(state.get("eligibility_thresholds_added_by_v3") is False, "v3 invented an eligibility threshold")
    require(state.get("split") == "not_yet_assigned", "global split changed")
    require(state.get("model_eligible") == "not_adjudicated_stage_7_2", "model boundary drift")
    require(
        state.get("export_success_does_not_imply_stack_eligible") is True,
        "export success was confused with eligibility",
    )

    return {
        "status": "passed",
        "schema": MANIFEST_SCHEMA,
        "request_id": REQUEST_ID,
        "manifest_version": 3,
        "acquisition_count": len(entries),
        "universe_sha256": V2.universe_sha256(actual_ids),
        "unique_output_paths": len(output_paths),
        "unique_idempotency_seeds": len(seeds),
        "grid_specification_method": "declared_crs_crs_transform_and_dimensions",
        "declared_dimensions": manifest["grid_specification"]["dimensions"],
        "max_pixels": manifest["execution"]["max_pixels"],
        "canonical_target_vacated": True,
        "tasks_created": 0,
        "assets_created": 0,
        "stack_eligible": "not_yet_evaluated",
        "split": "not_yet_assigned",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--causal-audit", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = validate_manifest(
        load_json(args.manifest),
        load_json(args.catalog),
        args.catalog,
        load_json(args.causal_audit),
        args.causal_audit,
    )
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
