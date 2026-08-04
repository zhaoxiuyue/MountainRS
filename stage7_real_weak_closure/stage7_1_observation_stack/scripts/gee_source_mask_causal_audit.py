#!/usr/bin/env python3
"""C7.1-D3B-M1 read-only causal audit for Stage 7.1 source masks.

The audit examines the complete frozen 21-acquisition universe.  It never
creates Export tasks or assets, downloads imagery, alters stack eligibility, or
rewrites the frozen Export Manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REQUIRED_BANDS = ("SR_B4", "SR_B5", "QA_PIXEL")
AUDIT_ID = "C7.1-D3B-M1"
EVIDENCE_SCHEMA = "mountainrs-stage7.1-source-mask-causal-audit-v1"
REPORT_TITLE = "C7.1-D3B-M1｜SR_B4 source-mask 因果审计"
MAX_PIXELS = 10_000_000


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_sibling_module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive_mask_counts(target_pixel_count: int, mask_one_count: Any) -> dict[str, Any]:
    if not isinstance(mask_one_count, (int, float)) or isinstance(mask_one_count, bool):
        raise ValueError("mask=1 count is missing or non-numeric")
    if mask_one_count < 0 or mask_one_count > target_pixel_count:
        raise ValueError("mask=1 count is outside the target-grid total")
    mask_zero_count = target_pixel_count - int(mask_one_count)
    return {
        "target_pixel_count": target_pixel_count,
        "mask_one_count": int(mask_one_count),
        "mask_zero_count": mask_zero_count,
        "mask_zero_ratio": mask_zero_count / target_pixel_count,
    }


def classify_b4(
    *,
    target_zero_count: int,
    native_zero_count: int,
    edge_zero_count: int,
    qa_explained_count: int,
) -> dict[str, Any]:
    if target_zero_count == 0:
        return {"primary": "no_b4_mask_zero", "flags": []}
    flags: list[str] = []
    if native_zero_count == 0:
        flags.append("target_grid_reprojection_introduced")
    else:
        flags.append("source_native_missing")
    if edge_zero_count == target_zero_count:
        flags.append("edge_only")
    if qa_explained_count == target_zero_count:
        flags.append("qa_explained")

    if "target_grid_reprojection_introduced" in flags:
        primary = "target_grid_reprojection_introduced"
    elif "edge_only" in flags:
        primary = "edge_only"
    elif "qa_explained" in flags:
        primary = "qa_explained"
    elif "source_native_missing" in flags:
        primary = "source_native_missing"
    else:
        primary = "unresolved"
    return {"primary": primary, "flags": flags}


def reduction_kwargs(region: Any, grid: dict[str, Any]) -> dict[str, Any]:
    return {
        "geometry": region,
        "crs": grid["crs"],
        "crsTransform": grid["transform"],
        "maxPixels": MAX_PIXELS,
        "bestEffort": False,
        "tileScale": 4,
    }


def require_numeric(value: Any, description: str) -> int:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RuntimeError(f"{description} is missing or non-numeric")
    return int(value)


def target_mask_counts(ee: Any, image: Any, region: Any, grid: dict[str, Any]) -> dict[str, Any]:
    mask_values = image.select(list(REQUIRED_BANDS)).mask()
    sums = mask_values.reduceRegion(ee.Reducer.sum(), **reduction_kwargs(region, grid)).getInfo()
    if not isinstance(sums, dict):
        raise RuntimeError("target-grid mask sum did not return a dictionary")
    return {
        band: derive_mask_counts(grid["pixel_count"], sums.get(band))
        for band in REQUIRED_BANDS
    }


def native_mask_counts(ee: Any, image: Any, band: str, region: Any) -> dict[str, Any]:
    projection = image.select(band).projection().getInfo()
    if not isinstance(projection, dict) or not projection.get("crs") or not projection.get("transform"):
        raise RuntimeError(f"native projection is incomplete for {band}")
    mask = image.select(band).mask().rename("mask_one_count")
    total = ee.Image.constant(1).rename("target_pixel_count")
    result = ee.Image.cat([total, mask]).reduceRegion(
        ee.Reducer.sum(),
        geometry=region,
        crs=projection["crs"],
        crsTransform=projection["transform"],
        maxPixels=MAX_PIXELS,
        bestEffort=False,
        tileScale=4,
    ).getInfo()
    if not isinstance(result, dict):
        raise RuntimeError(f"native mask reduction did not return a dictionary for {band}")
    counts = derive_mask_counts(
        require_numeric(result.get("target_pixel_count"), "native target-pixel total"),
        result.get("mask_one_count"),
    )
    return {"projection": projection, **counts}


def b4_zero_spatial_summary(ee: Any, image: Any, region: Any, grid: dict[str, Any]) -> dict[str, Any]:
    b4_zero = image.select("SR_B4").mask().eq(0).rename("b4_mask_zero")
    coordinates = ee.Image.pixelCoordinates(grid["crs"])
    envelope = coordinates.updateMask(b4_zero).reduceRegion(
        ee.Reducer.minMax(), **reduction_kwargs(region, grid)
    ).getInfo()
    if not isinstance(envelope, dict):
        raise RuntimeError("B4 zero-mask envelope did not return a dictionary")

    bounds = grid["bounds"]
    x = coordinates.select("x")
    y = coordinates.select("y")
    resolution_x, resolution_y = grid["resolution"]
    left = bounds[0] + resolution_x / 2
    right = bounds[2] - resolution_x / 2
    bottom = bounds[1] + resolution_y / 2
    top = bounds[3] - resolution_y / 2
    edges = ee.Image.cat(
        [
            b4_zero.And(x.eq(left)).rename("left"),
            b4_zero.And(x.eq(right)).rename("right"),
            b4_zero.And(y.eq(bottom)).rename("bottom"),
            b4_zero.And(y.eq(top)).rename("top"),
            b4_zero.And(x.eq(left).Or(x.eq(right)).Or(y.eq(bottom)).Or(y.eq(top))).rename("any_edge"),
        ]
    ).reduceRegion(ee.Reducer.sum(), **reduction_kwargs(region, grid)).getInfo()
    if not isinstance(edges, dict):
        raise RuntimeError("B4 zero-mask edge reduction did not return a dictionary")

    # connectedComponents cannot represent components larger than 1,024 pixels.
    # Vectorizing the binary zero mask preserves exact 8-connected components and
    # attaches a countEvery pixel total to each resulting component feature.
    components = b4_zero.selfMask().toInt().reduceToVectors(
        reducer=ee.Reducer.countEvery(),
        geometry=region,
        crs=grid["crs"],
        crsTransform=grid["transform"],
        geometryType="polygon",
        eightConnected=True,
        labelProperty="mask_zero_value",
        maxPixels=MAX_PIXELS,
        bestEffort=False,
        tileScale=4,
    )
    component_sizes_raw = components.aggregate_array("count").getInfo()
    if not isinstance(component_sizes_raw, list):
        raise RuntimeError("B4 zero-mask component counts are invalid")
    component_sizes = [int(value) for value in component_sizes_raw]
    return {
        "mask_zero_envelope_projected": {
            "x_min": envelope.get("x_min"),
            "x_max": envelope.get("x_max"),
            "y_min": envelope.get("y_min"),
            "y_max": envelope.get("y_max"),
        },
        "edge_zero_counts": {name: int(edges.get(name, 0)) for name in ("left", "right", "bottom", "top", "any_edge")},
        "connectivity": "8_connected",
        "connected_region_count": len(component_sizes),
        "largest_connected_region_pixel_count": max(component_sizes, default=0),
    }


def b4_qa_crosscheck(ee: Any, image: Any, region: Any, grid: dict[str, Any]) -> dict[str, int]:
    b4_zero = image.select("SR_B4").mask().eq(0)
    qa_pixel = image.select("QA_PIXEL")
    qa_radsat = image.select("QA_RADSAT")
    qa_fill = qa_pixel.bitwiseAnd(1 << 0).neq(0)
    b4_saturation = qa_radsat.bitwiseAnd(1 << 3).neq(0)
    qa_explained = qa_fill.Or(b4_saturation)
    values = ee.Image.cat(
        [
            qa_fill.updateMask(b4_zero).rename("qa_fill_count"),
            b4_saturation.updateMask(b4_zero).rename("qa_radsat_b4_saturation_count"),
            qa_explained.updateMask(b4_zero).rename("qa_explained_union_count"),
            image.select("SR_B5").mask().updateMask(b4_zero).rename("b5_mask_one_at_b4_zero_count"),
            qa_pixel.mask().updateMask(b4_zero).rename("qa_pixel_mask_one_at_b4_zero_count"),
        ]
    ).reduceRegion(ee.Reducer.sum(), **reduction_kwargs(region, grid)).getInfo()
    if not isinstance(values, dict):
        raise RuntimeError("B4 QA crosscheck did not return a dictionary")
    return {name: int(values.get(name, 0)) for name in (
        "qa_fill_count",
        "qa_radsat_b4_saturation_count",
        "qa_explained_union_count",
        "b5_mask_one_at_b4_zero_count",
        "qa_pixel_mask_one_at_b4_zero_count",
    )}


def audit_acquisition(ee: Any, entry: dict[str, Any], region: Any, grid: dict[str, Any]) -> dict[str, Any]:
    image = ee.Image(entry["acquisition_id"])
    target = target_mask_counts(ee, image, region, grid)
    record: dict[str, Any] = {
        "order": entry["order"],
        "acquisition_id": entry["acquisition_id"],
        "short_product_id": entry["short_product_id"],
        "target_grid": target,
    }
    if target["SR_B4"]["mask_zero_count"] == 0:
        record["b4_causal_audit"] = {"classification": classify_b4(target_zero_count=0, native_zero_count=0, edge_zero_count=0, qa_explained_count=0)}
        return record

    native = native_mask_counts(ee, image, "SR_B4", region)
    spatial = b4_zero_spatial_summary(ee, image, region, grid)
    qa = b4_qa_crosscheck(ee, image, region, grid)
    record["b4_causal_audit"] = {
        "native_grid": native,
        "target_grid": target["SR_B4"],
        "spatial": spatial,
        "qa_crosscheck": qa,
        "classification": classify_b4(
            target_zero_count=target["SR_B4"]["mask_zero_count"],
            native_zero_count=native["mask_zero_count"],
            edge_zero_count=spatial["edge_zero_counts"]["any_edge"],
            qa_explained_count=qa["qa_explained_union_count"],
        ),
    }
    return record


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    b4_failures = [item for item in records if item["target_grid"]["SR_B4"]["mask_zero_count"] > 0]
    classifications: dict[str, int] = {}
    for item in b4_failures:
        key = item["b4_causal_audit"]["classification"]["primary"]
        classifications[key] = classifications.get(key, 0) + 1
    return {
        "acquisition_count": len(records),
        "b4_zero_acquisition_count": len(b4_failures),
        "b4_zero_acquisitions": [item["short_product_id"] for item in b4_failures],
        "b4_primary_classifications": classifications,
        "all_b5_mask_one": all(item["target_grid"]["SR_B5"]["mask_zero_count"] == 0 for item in records),
        "all_qa_pixel_mask_one": all(item["target_grid"]["QA_PIXEL"]["mask_zero_count"] == 0 for item in records),
    }


def route_comparison() -> list[dict[str, str]]:
    return [
        {
            "route": "A. 排除 10 景",
            "candidate_universe": "改变 complete_v5_universe_all_21；会引入按掩膜结果排除的选择偏差。",
            "evidence_fidelity": "不保存被排除景的原始观测证据，无法再现其缺失语义。",
            "model_input": "仅剩 11 景，任何后续 split/模型输入都不再对应冻结 universe。",
        },
        {
            "route": "B. 原始 DN + 显式逐波段 valid-mask",
            "candidate_universe": "可保留 21 景，但需要新的版本化存储合同，不能改写 v1。",
            "evidence_fidelity": "可逆地保留 raw DN、每 band mask 与 QA 的不同语义，最低信息损失。",
            "model_input": "本地派生时可按 band-aware 有效域构建输入；必须重新定义 stack gate 与报告分母。",
        },
        {
            "route": "C. 全部保留，按冻结支持域本地判定 eligibility",
            "candidate_universe": "保留 21 景，但仅在现有 v1 约束被正式替换后才可执行。",
            "evidence_fidelity": "若仍只存三 band 且不存 source mask，会丢失 B4 无效位置，不能满足保真要求。",
            "model_input": "可避免整景排除偏差，但不能把缺失 B4 冒充为可用于支持域或模型输入。",
        },
    ]


def render_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"# {REPORT_TITLE}",
        "",
        "## 结论边界",
        "",
        "本报告是只读因果审计；未修改 Export 合同、stack eligibility、任务、资产或影像。它不选择新的存储路线。",
        "",
        "## 计数口径复核",
        "",
        "旧预检使用 `image.mask().reduceRegion(Reducer.count())`。这计数派生 mask 影像自身未遮蔽的像元，并不等于 `mask == 1` 的像元数。",
        "本审计将有效数定义为 `sum(image.mask())`，零数定义为 `target_pixel_count - mask_one_count`。",
        "",
        "## 审计摘要",
        "",
        f"- acquisition 总数：{summary['acquisition_count']}",
        f"- SR_B4 存在 mask=0 的景数：{summary['b4_zero_acquisition_count']}",
        f"- B5 全部 mask=1：{summary['all_b5_mask_one']}",
        f"- QA_PIXEL 全部 mask=1：{summary['all_qa_pixel_mask_one']}",
        f"- B4 首要分类：`{canonical_json(summary['b4_primary_classifications'])}`",
        "",
        "## B4 异常景",
        "",
        "| 景 | target mask=0 | native mask=0 | 边界 mask=0 | QA fill | B4 saturation | 分类 |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in result["records"]:
        causal = item.get("b4_causal_audit", {})
        if item["target_grid"]["SR_B4"]["mask_zero_count"] == 0:
            continue
        native = causal["native_grid"]
        spatial = causal["spatial"]
        qa = causal["qa_crosscheck"]
        lines.append(
            f"| `{item['short_product_id']}` | {item['target_grid']['SR_B4']['mask_zero_count']} | {native['mask_zero_count']} | {spatial['edge_zero_counts']['any_edge']} | {qa['qa_fill_count']} | {qa['qa_radsat_b4_saturation_count']} | `{causal['classification']['primary']}` |"
        )
    lines.extend(["", "## 路线影响比较", "", "| 路线 | 候选宇宙 | 证据保真 | 后续模型输入 |", "|---|---|---|---|"])
    for route in result["route_comparison"]:
        lines.append(f"| {route['route']} | {route['candidate_universe']} | {route['evidence_fidelity']} | {route['model_input']} |")
    lines.extend(["", "## 停止条件", "", "本轮不选择 A/B/C，也不修改任何冻结合同；等待 Elara 裁决正式存储路线。"])
    return "\n".join(lines) + "\n"


def atomic_create(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--project-config", required=True)
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-report", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    catalog_path = Path(args.catalog)
    manifest = load_json(manifest_path)
    catalog = load_json(catalog_path)
    auditor = load_sibling_module("stage7_1_export_manifest_auditor", "audit_export_manifest.py")
    executor = load_sibling_module("stage7_1_catalog_executor", "gee_catalog_audit.py")
    manifest_audit = auditor.validate_manifest(manifest, catalog, catalog_path)
    project_id = executor.read_project_id(Path(args.project_config))
    attestation, live_probe = executor.verify_authenticated_session(Path(args.attestation), project_id)

    import ee

    grid = manifest["target_grid"]
    region = ee.Geometry.Rectangle(grid["bounds"], grid["crs"], False)
    records = [audit_acquisition(ee, entry, region, grid) for entry in manifest["acquisitions"]]
    result = {
        "schema": EVIDENCE_SCHEMA,
        "audit_id": AUDIT_ID,
        "operation_boundary": {
            "read_only_earth_engine_queries": True,
            "export_tasks_created": 0,
            "assets_created": 0,
            "imagery_downloaded": 0,
            "export_manifest_rewritten": False,
            "stack_eligibility_changed": False,
        },
        "measurement_semantics": {
            "old_preflight_count": "image.mask().reduceRegion(Reducer.count()) counts non-masked pixels of the derived mask image, not mask==1 values.",
            "current_valid_count": "sum(image.mask()) on the exact target grid; mask values are 0/1.",
            "current_invalid_count": "target_pixel_count - mask_one_count.",
        },
        "source_evidence": {
            "export_manifest_sha256": sha256_file(manifest_path),
            "catalog_sha256": sha256_file(catalog_path),
            "manifest_audit": manifest_audit,
            "auth_attestation_sha256": sha256_file(Path(args.attestation)),
            "attestation_verified_at_utc": attestation["verified_at"],
            "attestation_valid_until_utc": attestation["valid_until"],
            "live_health_verified_at_utc": live_probe["verified_at"],
        },
        "target_grid": grid,
        "records": records,
        "summary": summarize(records),
        "route_comparison": route_comparison(),
    }
    atomic_create(Path(args.output_json), canonical_json(result) + "\n")
    atomic_create(Path(args.output_report), render_report(result))
    print(canonical_json({"audit_id": AUDIT_ID, "status": "completed", **result["summary"], "export_tasks_created": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
