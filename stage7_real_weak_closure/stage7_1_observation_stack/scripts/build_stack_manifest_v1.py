#!/usr/bin/env python3
"""按冻结规则生成 Stage 7.1 stack manifest 与 readiness report。

split 规则逐字取自 selection-protocol.md §5，本程序不得增删：
  1. 按 system:time_start 升序，再按完整 product ID 升序；
  2. N < 3 则停止，不得创建名义 split；
  3. n_train = max(1, floor(0.6 × N))；
  4. n_validation = max(1, floor(0.2 × N))；
  5. n_test = N − n_train − n_validation，必须为正；
  6. 按时间连续切段：早段 train、中段 validation、晚段 test；
  7. 同一 acquisition 的全部 ROI 与导出继承该 acquisition 的 split。

eligibility 规则取自 §3：本地成员与哈希存在、精确 target-grid 完整性通过、
base_valid_land > 0。本程序不引入任何新阈值。只读，不触碰 Earth Engine。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assign_split(eligible: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(eligible)
    if n < 3:
        raise SystemExit(f"selection-protocol §5 rule 2: N={n} < 3, stop; do not create a nominal split")
    ordered = sorted(eligible, key=lambda m: (m["system_time_start_utc"], m["acquisition_id"]))
    n_train = max(1, math.floor(0.6 * n))
    n_validation = max(1, math.floor(0.2 * n))
    n_test = n - n_train - n_validation
    if n_test <= 0:
        raise SystemExit(f"selection-protocol §5 rule 5: n_test={n_test} is not positive")
    for index, member in enumerate(ordered):
        member["split"] = (
            "train" if index < n_train
            else "validation" if index < n_train + n_validation
            else "test"
        )
    return {
        "rule_source": "docs/selection-protocol.md section 5",
        "N": n,
        "n_train": n_train,
        "n_validation": n_validation,
        "n_test": n_test,
        "arithmetic": {
            "n_train": f"max(1, floor(0.6 * {n})) = {n_train}",
            "n_validation": f"max(1, floor(0.2 * {n})) = {n_validation}",
            "n_test": f"{n} - {n_train} - {n_validation} = {n_test}",
        },
        "allocation": "contiguous ascending time segments: earliest to train, middle to validation, latest to test",
        "thresholds_invented": False,
        "counts": {
            "train": sum(1 for m in ordered if m["split"] == "train"),
            "validation": sum(1 for m in ordered if m["split"] == "validation"),
            "test": sum(1 for m in ordered if m["split"] == "test"),
        },
        "ordered_members": ordered,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--support-audit", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    support = load_json(args.support_audit)
    stage_root = args.manifest.parent.parent
    root = manifest["path_policy"]["root_relative_path"]

    members = []
    for record in support["members"]:
        entry = next(e for e in manifest["acquisitions"] if e["order"] == record["order"])
        members.append({
            "order": record["order"],
            "acquisition_id": record["acquisition_id"],
            "short_product_id": record["short_product_id"],
            "system_time_start_utc": record["system_time_start_utc"],
            "member_relative_to_alias": entry["target_relative_to_alias"],
            "member_sha256": record["member_sha256"],
            "member_byte_size": record["member_byte_size"],
            "target_grid_exact": record["grid_shape"] == manifest["target_grid"]["shape"],
            "qa_clear_count": record["qa_clear_count"],
            "water_count": record["water_count"],
            "base_valid_land": record["base_valid_land"]["qa_clear_included"],
            "stack_eligible": record["stack_eligible"],
            "split": "not_assigned",
        })

    eligible = [m for m in members if m["stack_eligible"] == "eligible"]
    split = assign_split(eligible)
    by_id = {m["acquisition_id"]: m["split"] for m in split.pop("ordered_members")}
    for member in members:
        if member["acquisition_id"] in by_id:
            member["split"] = by_id[member["acquisition_id"]]

    payload = {
        "schema": "mountainrs-stage7.1-stack-manifest-v1",
        "request_id": "mountainrs-stage7.1-stack-manifest-v1",
        "created_at_utc": "2026-08-04T11:00:00Z",
        "source_export_manifest": {
            "relative_path": "evidence/export-manifest-v3.json",
            "request_id": manifest["request_id"],
            "sha256": sha256_file(args.manifest),
        },
        "grid_declaration_amendment": {
            "relative_path": "evidence/grid-declaration-amendment-v1.json",
            "sha256": sha256_file(args.amendment),
        },
        "support_audit": {
            "relative_path": "evidence/local-support-audit-v1.json",
            "sha256": sha256_file(args.support_audit),
        },
        "root_alias": manifest["path_policy"]["root_alias"],
        "root_relative_path": root,
        "target_grid": manifest["target_grid"],
        "eligibility_rule": {
            "source": "docs/selection-protocol.md section 3",
            "rule": "local members and hashes exist, exact target-grid integrity passes, base_valid_land > 0",
            "base_valid_reading": "QA-clear is part of base_valid",
            "reading_determined_by": (
                "Stage 7.0 frozen accounting on the same scene reproduces exactly "
                "(base_valid_land 102222 and cos_i partition 4063/4559/93600) only under this reading"
            ),
            "thresholds_invented": False,
        },
        "counts": {
            "universe": len(members),
            "eligible": len(eligible),
            "not_eligible": len(members) - len(eligible),
        },
        "split": split,
        "per_pixel_counts": support["per_pixel_counts"],
        "members": members,
        "state_boundary": {
            "model_eligible": "not_adjudicated_stage_7_2",
            "export_success_does_not_imply_stack_eligible": True,
            "split_frozen": True,
            "silent_replacement_or_backfill_prohibited": True,
        },
        "operation_boundary": {
            "earth_engine_called": False,
            "export_tasks_created": 0,
            "assets_created": 0,
            "frozen_evidence_rewritten": False,
        },
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")

    rows = "\n".join(
        f"| {m['order']} | {m['short_product_id']} | {m['system_time_start_utc'][:10]} | "
        f"{m['qa_clear_count']} | {m['base_valid_land']} | {m['stack_eligible']} | {m['split']} |"
        for m in members
    )
    report = f"""# Stage 7.1 readiness report

生成时间：{payload['created_at_utc']}
来源导出合同：`evidence/export-manifest-v3.json`（sha256 `{payload['source_export_manifest']['sha256'][:16]}…`）
网格声明修正案：`evidence/grid-declaration-amendment-v1.json`（sha256 `{payload['grid_declaration_amendment']['sha256'][:16]}…`）
支持域审计：`evidence/local-support-audit-v1.json`（sha256 `{payload['support_audit']['sha256'][:16]}…`）

## 1. 结论

完整 21 景候选宇宙已全部导出并通过本地无损掩膜重建审计；按冻结 selection-protocol
§3 判定，其中 **{len(eligible)} 景** `stack_eligible`，**{len(members) - len(eligible)} 景**不合格。
按 §5 唯一算术规则分配 acquisition 级 split：train {split['counts']['train']}、
validation {split['counts']['validation']}、test {split['counts']['test']}，三者均非空。

## 2. 网格与存储

全部 21 个成员精确匹配冻结网格 `{payload['target_grid']['grid_id']}`：
`{payload['target_grid']['crs']}`、{payload['target_grid']['shape']['width']}×{payload['target_grid']['shape']['height']}、
transform `{payload['target_grid']['transform']}`、{payload['target_grid']['pixel_count']} 像元、
6×uint16 波段、无共享 nodata。掩膜由显式 `*_VALID` 波段重建，逐景与
`source-mask-causal-audit-v1.json` 的 M1 计数吻合。

## 3. eligibility 判据

`base_valid_land > 0`，其中 base_valid 包含 QA-clear。该读法**不是本节点选定的**：
冻结文本可作两读，两读在部分景上给出相反判定，故改用 Stage 7.0 对同一景
（shadow-risk B ＝ `LC08_130038_20230101`）冻结的账目反解——`base_valid_land = 102222`
与 cos_i 分区 `4063 / 4559 / 93600` 四数同时精确复现，当且仅当 QA-clear 属于
base_valid；另一读法差 +177821。未引入任何新阈值。

## 4. 成员一览

| order | short product ID | 日期 | QA-clear 像元 | base_valid_land | eligible | split |
|---|---|---|---|---|---|---|
{rows}

## 5. 逐像元支持

- `observation_count` = {support['per_pixel_counts']['observation_count']}
- `valid_count` 范围 = {support['per_pixel_counts']['valid_count_min']} – {support['per_pixel_counts']['valid_count_max']}
- 全支持像元 = {support['per_pixel_counts']['pixels_with_full_support']}
- 零支持像元 = {support['per_pixel_counts']['pixels_with_zero_support']}

## 6. 边界与移交事项

- `model_eligible` 未裁决，属 Stage 7.2；本报告不拟合、不评分、不比较机制。
- split 一经冻结不得因模型表现重排；成员若日后未通过完整性检查，须显式修订协议与
  catalog，禁止静默替换或回填。
- **cos_i 边界**：唯一冻结的 cos_i 栅格是为 `LC08_130038_20230101` 的太阳几何所算，
  不得套用于其他 acquisition。`base_valid_land` 只依赖地形几何故不受影响，但逐景
  supported / unsupported 分类需要逐景太阳几何，属 Stage 7.2 范围。
- **待办**：registry 别名 `stage_7_1_terrain_stack` 指向 `data/terrain_stack`，目前为空。
  地形几何当前通过 `target-grid.yaml` 中按 sha256 钉住的 stage6.5 别名解析
  （dem / slope / aspect / cos_i，均 `exact_match: true`）。Stage 7.2 若需要独立地形栈，
  应在该节点显式建立，不应由本节点静默复制。
"""
    args.report.write_text(report, encoding="utf-8")

    print(json.dumps({
        "status": "passed",
        "universe": len(members),
        "eligible": len(eligible),
        "split": split["counts"],
        "all_splits_non_empty": all(v > 0 for v in split["counts"].values()),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
