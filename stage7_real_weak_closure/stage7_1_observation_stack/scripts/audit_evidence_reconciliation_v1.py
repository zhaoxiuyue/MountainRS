#!/usr/bin/env python3
"""Stage 7.1-R 冻结证据对账审计：fail-closed，只读，不改任何冻结件。

本程序只证明一件事——Stage 7.1-R 要建立的 L0 证据语义层，长在与 Stage 7.1
完全同一份证据上，而不是长在一份漂移过的副本上。语义补全本身不在这里，
这里只负责在补之前把地基验一遍；地基不实就停机，不得发布就绪结论。

对账口径全部取自既有冻结证据，本程序不引入新阈值、不重判资格、不改成员集合：
- acquisition-catalog：21 景候选宇宙、逐景太阳几何、QA 摘要、footprint 覆盖率
- export-manifest v3 与 append-only attempts journal：身份、canonical order、任务谱系
- 21 份 local-mask-audit-v3：逐波段无损重建证据与传输零值语义
- local-support-audit-v1：逐景支持计数与地形几何身份
- stack_manifest v1 与 readiness report：18/3 历史操作资格与 10/3/5 split
- relocation-manifest-v2：preserve_bytes 冻结条目的字节完好性

合同⑨：任一检查不通过即停止并以非零码退出。

不调用 Earth Engine，不认证，不下载，不写任何既有文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

# scripts/ → stage7_1_observation_stack/ → stage7_real_weak_closure/ → 仓库根
SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SCRIPT_DIR.parents[2]

EXPECTED_UNIVERSE_SIZE = 21
EXPECTED_ELIGIBLE = 18
EXPECTED_SPLIT = {"train": 10, "validation": 3, "test": 5}
JOURNAL_EVENTS_PER_ACQUISITION = 3  # intent / READY / COMPLETED
FOOTPRINT_MINIMUM_RATIO = 0.999999  # target-grid.yaml canonical_stack_constraints
VALID_BANDS = {"SR_B4": "SR_B4_VALID", "SR_B5": "SR_B5_VALID", "QA_PIXEL": "QA_PIXEL_VALID"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(check_id: str, description: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"check_id": check_id, "description": description, "passed": bool(passed), **detail}


class Evidence:
    """一次性加载全部冻结证据，之后所有检查都只读这份内存副本。"""

    def __init__(self) -> None:
        self.catalog_path = STAGE_ROOT / "data/raw/acquisition-catalog.json"
        self.manifest_path = STAGE_ROOT / "evidence/export-manifest-v3.json"
        self.journal_path = STAGE_ROOT / "evidence/export-attempts-v3.jsonl"
        self.stack_manifest_path = STAGE_ROOT / "evidence/stack_manifest.json"
        self.support_audit_path = STAGE_ROOT / "evidence/local-support-audit-v1.json"
        self.amendment_path = STAGE_ROOT / "evidence/grid-declaration-amendment-v1.json"
        self.relocation_path = STAGE_ROOT / "evidence/relocation-manifest-v2.json"
        self.readiness_path = STAGE_ROOT / "reports/readiness_report.md"
        self.target_grid_path = STAGE_ROOT / "configs/target-grid.yaml"
        self.selection_protocol_path = STAGE_ROOT / "docs/selection-protocol.md"

        self.catalog = load_json(self.catalog_path)
        self.manifest = load_json(self.manifest_path)
        self.stack_manifest = load_json(self.stack_manifest_path)
        self.support_audit = load_json(self.support_audit_path)
        self.relocation = load_json(self.relocation_path)
        self.readiness_text = self.readiness_path.read_text(encoding="utf-8")
        self.journal = [
            json.loads(line)
            for line in self.journal_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        self.stack_root = STAGE_ROOT / self.manifest["path_policy"]["root_relative_path"]
        self.mask_audits = {
            entry["order"]: load_json(
                STAGE_ROOT / f"evidence/local-mask-audit-v3-order{entry['order']}.json"
            )
            for entry in self.manifest["acquisitions"]
        }

    def member_tif(self, entry: dict[str, Any]) -> Path:
        return self.stack_root / entry["target_relative_to_alias"]


def check_universe_identity(ev: Evidence) -> dict[str, Any]:
    """C1：四处证据的 21 景身份集合必须完全相同，一个都不能多、不能少、不能改名。"""
    sources = {
        "acquisition_catalog": {c["acquisition_id"] for c in ev.catalog["candidates"]},
        "export_manifest_v3": {a["acquisition_id"] for a in ev.manifest["acquisitions"]},
        "stack_manifest": {m["acquisition_id"] for m in ev.stack_manifest["members"]},
        "local_support_audit": {m["acquisition_id"] for m in ev.support_audit["members"]},
    }
    reference = sources["acquisition_catalog"]
    agree = all(ids == reference for ids in sources.values())
    return check(
        "C1",
        "21 景 acquisition 身份集合在 catalog / export manifest / stack manifest / support audit 四处一致",
        agree and len(reference) == EXPECTED_UNIVERSE_SIZE,
        member_count={name: len(ids) for name, ids in sources.items()},
        symmetric_differences={
            name: sorted(ids ^ reference) for name, ids in sources.items() if ids != reference
        },
    )


def check_canonical_order(ev: Evidence) -> dict[str, Any]:
    """C2：canonical order 是 1..21 的连续整数，且与 (system_time_start, acquisition_id) 升序一致。"""
    entries = sorted(ev.manifest["acquisitions"], key=lambda e: e["order"])
    orders = [e["order"] for e in entries]
    contiguous = orders == list(range(1, EXPECTED_UNIVERSE_SIZE + 1))

    time_sorted = sorted(entries, key=lambda e: (e["system_time_start_utc"], e["acquisition_id"]))
    order_matches_time = [e["acquisition_id"] for e in entries] == [
        e["acquisition_id"] for e in time_sorted
    ]

    manifest_by_order = {e["order"]: e["acquisition_id"] for e in entries}
    stack_by_order = {m["order"]: m["acquisition_id"] for m in ev.stack_manifest["members"]}
    support_by_order = {m["order"]: m["acquisition_id"] for m in ev.support_audit["members"]}
    mapping_agrees = manifest_by_order == stack_by_order == support_by_order

    return check(
        "C2",
        "canonical order 连续为 1..21，与时间升序一致，且 order↔身份映射在三处证据一致",
        contiguous and order_matches_time and mapping_agrees,
        order_contiguous=contiguous,
        order_matches_time_ascending=order_matches_time,
        order_identity_mapping_agrees=mapping_agrees,
    )


def check_grid_identity(ev: Evidence, rasters: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """C3：21 景栅格的 CRS / transform / 形状必须精确等于冻结网格，禁止任何重采样容差。"""
    grid = ev.stack_manifest["target_grid"]
    mismatched = []
    for order, raster in sorted(rasters.items()):
        exact = (
            raster["crs"] == grid["crs"]
            and raster["transform"] == grid["transform"]
            and raster["height"] == grid["shape"]["height"]
            and raster["width"] == grid["shape"]["width"]
        )
        if not exact:
            mismatched.append({"order": order, "observed": raster})
    return check(
        "C3",
        f"21 景精确匹配冻结网格 {grid['grid_id']}（CRS / transform / 形状零容差）",
        not mismatched,
        grid_id=grid["grid_id"],
        pixel_count=grid["pixel_count"],
        mismatched=mismatched,
    )


def check_content_hashes(ev: Evidence, rasters: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """C4：每景磁盘字节的 SHA-256 必须同时等于 stack manifest、support audit 与 mask audit 三处记录。"""
    drifted = []
    for entry in ev.manifest["acquisitions"]:
        order = entry["order"]
        observed = rasters[order]["sha256"]
        recorded = {
            "stack_manifest": next(
                m["member_sha256"] for m in ev.stack_manifest["members"] if m["order"] == order
            ),
            "local_support_audit": next(
                m["member_sha256"] for m in ev.support_audit["members"] if m["order"] == order
            ),
            "local_mask_audit": ev.mask_audits[order]["local_file"]["sha256"],
        }
        if any(value != observed for value in recorded.values()):
            drifted.append({"order": order, "on_disk": observed, "recorded": recorded})
    return check(
        "C4",
        "21 景磁盘 SHA-256 与 stack manifest / support audit / mask audit 三处记录逐一相同",
        not drifted,
        drifted=drifted,
    )


def check_lossless_mask_reconstruction(
    ev: Evidence, rasters: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """C5：逐波段 VALID 可无损重建源掩膜，且被掩膜像元的传输值恒为记录的 masked_transfer_value。

    这条同时是合同③「masked、nodata 与为传输序列化写入的零值必须可区分」的证据：
    被掩膜位置在数据波段上写的是传输零值，只有 VALID 波段能把它和真实 0 值分开。
    """
    failures = []
    for entry in ev.manifest["acquisitions"]:
        order = entry["order"]
        audit = ev.mask_audits[order]
        if audit["status"] != "passed_lossless_mask_reconstruction":
            failures.append({"order": order, "reason": "audit_status", "status": audit["status"]})
            continue
        for band, recorded in audit["reconstructed_source_masks"].items():
            observed = rasters[order]["masks"][band]
            if observed["mask_one_count"] != recorded["mask_one_count"]:
                failures.append({
                    "order": order,
                    "band": band,
                    "reason": "mask_one_count",
                    "recorded": recorded["mask_one_count"],
                    "recomputed": observed["mask_one_count"],
                })
            if not observed["masked_pixels_all_carry_transfer_value"]:
                failures.append({
                    "order": order,
                    "band": band,
                    "reason": "masked_transfer_value_not_uniform",
                    "expected": recorded["masked_transfer_value"],
                })
    return check(
        "C5",
        "21 景逐波段 VALID 无损重建复现既有掩膜计数，且被掩膜像元一律携带传输零值",
        not failures,
        bands=sorted(VALID_BANDS),
        failures=failures,
    )


def check_operation_eligibility(ev: Evidence) -> dict[str, Any]:
    """C6：历史操作资格 18/3 与三景不合格身份固定，本节点不重新判定，只复读。"""
    members = ev.stack_manifest["members"]
    eligible = [m for m in members if m["stack_eligible"] == "eligible"]
    not_eligible = sorted(m["short_product_id"] for m in members if m["stack_eligible"] != "eligible")
    zero_base_valid = sorted(
        m["short_product_id"] for m in members if m["base_valid_land"] == 0
    )
    in_report = all(pid in ev.readiness_text for pid in not_eligible)
    return check(
        "C6",
        f"历史操作资格固定为 {EXPECTED_ELIGIBLE} eligible / {EXPECTED_UNIVERSE_SIZE - EXPECTED_ELIGIBLE} not_eligible，"
        "且不合格三景恰为 base_valid_land = 0 的三景",
        len(eligible) == EXPECTED_ELIGIBLE
        and not_eligible == zero_base_valid
        and len(not_eligible) == EXPECTED_UNIVERSE_SIZE - EXPECTED_ELIGIBLE
        and in_report,
        eligible_count=len(eligible),
        not_eligible=not_eligible,
        zero_base_valid_land=zero_base_valid,
        present_in_readiness_report=in_report,
    )


def check_split_arithmetic(ev: Evidence) -> dict[str, Any]:
    """C7：10/3/5 split 按 selection-protocol §5 唯一算术复算一致，且只落在 eligible 子集上。"""
    members = ev.stack_manifest["members"]
    counts = {name: sum(1 for m in members if m["split"] == name) for name in EXPECTED_SPLIT}
    n = sum(1 for m in members if m["stack_eligible"] == "eligible")
    recomputed = {
        "train": max(1, math.floor(0.6 * n)),
        "validation": max(1, math.floor(0.2 * n)),
    }
    recomputed["test"] = n - recomputed["train"] - recomputed["validation"]

    ordered = sorted(
        (m for m in members if m["stack_eligible"] == "eligible"),
        key=lambda m: (m["system_time_start_utc"], m["acquisition_id"]),
    )
    contiguous = True
    for index, member in enumerate(ordered):
        expected = (
            "train" if index < recomputed["train"]
            else "validation" if index < recomputed["train"] + recomputed["validation"]
            else "test"
        )
        if member["split"] != expected:
            contiguous = False
    unassigned_are_not_eligible = all(
        m["stack_eligible"] != "eligible" for m in members if m["split"] not in EXPECTED_SPLIT
    )
    return check(
        "C7",
        "split 复算等于既有 10/3/5，按时间连续切段，且只分配给 eligible 子集",
        counts == EXPECTED_SPLIT == recomputed and contiguous and unassigned_are_not_eligible,
        recorded=counts,
        recomputed=recomputed,
        contiguous_time_segments=contiguous,
        unassigned_are_not_eligible=unassigned_are_not_eligible,
    )


def check_journal_completeness(ev: Evidence) -> dict[str, Any]:
    """C8：append-only journal 的任务谱系逐景闭合。

    每景三条事件：submission_intent → task_status(READY) → task_status(COMPLETED)。
    终态事件只带 task_id，不带 acquisition 身份，所以身份必须靠 READY 事件登记的
    task_id 回链——链断了就等于无法证明某景真的完成过，此时停机。
    """
    universe = {a["acquisition_id"] for a in ev.manifest["acquisitions"]}
    intents: dict[str, int] = {}
    ready_task_owner: dict[str, str] = {}
    completed_tasks: dict[str, dict[str, Any]] = {}

    for event in ev.journal:
        if event.get("event_type") == "submission_intent":
            acquisition_id = event.get("acquisition_id")
            intents[acquisition_id] = intents.get(acquisition_id, 0) + 1
        elif event.get("event_type") == "task_status":
            state = event.get("earth_engine_state")
            if state == "READY":
                ready_task_owner[event.get("task_id")] = event.get("acquisition_id")
            elif state == "COMPLETED":
                completed_tasks[event.get("task_id")] = event

    completed_owners = {
        ready_task_owner[task_id] for task_id in completed_tasks if task_id in ready_task_owner
    }
    all_succeeded = all(
        event.get("lifecycle_state") == "succeeded" for event in completed_tasks.values()
    )
    expected_total = EXPECTED_UNIVERSE_SIZE * JOURNAL_EVENTS_PER_ACQUISITION
    complete = (
        len(ev.journal) == expected_total
        and set(intents) == universe
        and all(count == 1 for count in intents.values())
        and set(ready_task_owner.values()) == universe
        and len(ready_task_owner) == EXPECTED_UNIVERSE_SIZE
        and set(completed_tasks) == set(ready_task_owner)
        and completed_owners == universe
        and all_succeeded
    )
    return check(
        "C8",
        f"append-only journal 共 {expected_total} 条事件；21 景各一条 submission_intent 与 READY，"
        "终态 COMPLETED 经 task_id 唯一回链到同一景且全部 succeeded",
        complete,
        event_count=len(ev.journal),
        submission_intents=len(intents),
        ready_tasks=len(ready_task_owner),
        completed_tasks=len(completed_tasks),
        unlinked_completed_tasks=sorted(set(completed_tasks) - set(ready_task_owner)),
        acquisitions_without_completion=sorted(universe - completed_owners),
        all_completed_lifecycle_succeeded=all_succeeded,
    )


def check_solar_geometry_available(ev: Evidence) -> dict[str, Any]:
    """C9（合同⑩）：21 景太阳几何在本地 catalog 中全覆盖，缺一即停——不得以缺省值或邻景插值补齐。"""
    missing = []
    for candidate in ev.catalog["candidates"]:
        azimuth = candidate.get("sun_azimuth_deg")
        elevation = candidate.get("sun_elevation_deg")
        declared_missing = candidate.get("solar_geometry_missing_fields") or []
        if azimuth is None or elevation is None or declared_missing:
            missing.append({
                "acquisition_id": candidate["acquisition_id"],
                "sun_azimuth_deg": azimuth,
                "sun_elevation_deg": elevation,
                "solar_geometry_missing_fields": declared_missing,
            })
    elevations = [c["sun_elevation_deg"] for c in ev.catalog["candidates"] if c.get("sun_elevation_deg") is not None]
    return check(
        "C9",
        "21 景太阳几何（SUN_AZIMUTH / SUN_ELEVATION）在本地 catalog 中全覆盖，可作 Stage 7.2 几何支持输入",
        not missing and len(elevations) == EXPECTED_UNIVERSE_SIZE,
        covered=len(elevations),
        sun_elevation_deg_range=[min(elevations), max(elevations)] if elevations else None,
        missing=missing,
    )


def check_footprint_full_cover(ev: Evidence) -> dict[str, Any]:
    """C10（合同④）：21 景对冻结 ROI 均为 full cover——这是 observation_opportunity 为常数场的唯一依据。"""
    ratios = {c["acquisition_id"]: c["target_roi_footprint_coverage"] for c in ev.catalog["candidates"]}
    below = {k: v for k, v in ratios.items() if v < FOOTPRINT_MINIMUM_RATIO}
    return check(
        "C10",
        f"21 景 target_roi_footprint_coverage 均 ≥ {FOOTPRINT_MINIMUM_RATIO}，"
        "故逐世界位置 observation_opportunity_count 为常数场 21",
        not below and len(ratios) == EXPECTED_UNIVERSE_SIZE,
        minimum_observed=min(ratios.values()) if ratios else None,
        constant_field_value=EXPECTED_UNIVERSE_SIZE if not below else None,
        below_threshold=below,
    )


def check_frozen_bytes_intact(ev: Evidence) -> dict[str, Any]:
    """C11：relocation-manifest-v2 声明为 preserve_bytes 的冻结条目，磁盘字节必须仍与记录一致。"""
    checked = []
    drifted = []
    missing = []
    for operation in ev.relocation["operations"]:
        if operation.get("contentEditPolicy") != "preserve_bytes":
            continue
        after = operation.get("after") or {}
        locator = after.get("locator")
        recorded_hash = after.get("sha256")
        if not locator or not recorded_hash:
            continue
        path = REPO_ROOT / locator
        if not path.is_file():
            missing.append(locator)
            continue
        observed = sha256_file(path)
        checked.append(locator)
        if observed != recorded_hash:
            drifted.append({"locator": locator, "recorded": recorded_hash, "on_disk": observed})
    return check(
        "C11",
        "relocation-manifest-v2 的 preserve_bytes 冻结条目字节完好",
        not drifted and not missing and bool(checked),
        preserve_bytes_entries=len(checked),
        missing=missing,
        drifted=drifted,
    )


def scan_rasters(ev: Evidence) -> dict[int, dict[str, Any]]:
    """读一遍 21 景：只提取对账所需的网格身份、内容哈希与逐波段掩膜事实。"""
    bands = ev.manifest["execution"]["bands"]
    rasters: dict[int, dict[str, Any]] = {}
    for entry in ev.manifest["acquisitions"]:
        tif = ev.member_tif(entry)
        if not tif.is_file():
            raise SystemExit(f"C0 stop: member raster missing on disk: {tif}")
        with rasterio.open(tif) as dataset:
            data = {name: dataset.read(index + 1) for index, name in enumerate(bands)}
            crs = dataset.crs.to_string()
            transform = list(dataset.transform)[:6]
            height, width = dataset.height, dataset.width

        masks = {}
        for band, valid_band in VALID_BANDS.items():
            valid = data[valid_band] == 1
            masked_values = data[band][~valid]
            masks[band] = {
                "mask_one_count": int(valid.sum()),
                "mask_zero_count": int((~valid).sum()),
                # 被掩膜像元必须全部是传输零值：这正是「masked 与真实 0 不可混淆」的可验证形式
                "masked_pixels_all_carry_transfer_value": bool(
                    masked_values.size == 0 or np.all(masked_values == 0)
                ),
            }

        rasters[entry["order"]] = {
            "crs": crs,
            "transform": transform,
            "height": height,
            "width": width,
            "sha256": sha256_file(tif),
            "masks": masks,
        }
    return rasters


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="对账结论落点（JSON）")
    args = parser.parse_args()

    ev = Evidence()
    rasters = scan_rasters(ev)

    checks = [
        check_universe_identity(ev),
        check_canonical_order(ev),
        check_grid_identity(ev, rasters),
        check_content_hashes(ev, rasters),
        check_lossless_mask_reconstruction(ev, rasters),
        check_operation_eligibility(ev),
        check_split_arithmetic(ev),
        check_journal_completeness(ev),
        check_solar_geometry_available(ev),
        check_footprint_full_cover(ev),
        check_frozen_bytes_intact(ev),
    ]
    failed = [c["check_id"] for c in checks if not c["passed"]]

    payload = {
        "schema": "mountainrs-stage7.1r-evidence-reconciliation-audit-v1",
        "status": "failed_reconciliation" if failed else "passed_reconciliation",
        "failed_checks": failed,
        "universe_size": EXPECTED_UNIVERSE_SIZE,
        "reconciled_evidence": {
            "acquisition_catalog": {
                "relative_path": "data/raw/acquisition-catalog.json",
                "sha256": sha256_file(ev.catalog_path),
            },
            "export_manifest_v3": {
                "relative_path": "evidence/export-manifest-v3.json",
                "sha256": sha256_file(ev.manifest_path),
            },
            "export_attempts_journal_v3": {
                "relative_path": "evidence/export-attempts-v3.jsonl",
                "sha256": sha256_file(ev.journal_path),
            },
            "stack_manifest": {
                "relative_path": "evidence/stack_manifest.json",
                "sha256": sha256_file(ev.stack_manifest_path),
            },
            "local_support_audit_v1": {
                "relative_path": "evidence/local-support-audit-v1.json",
                "sha256": sha256_file(ev.support_audit_path),
            },
            "grid_declaration_amendment_v1": {
                "relative_path": "evidence/grid-declaration-amendment-v1.json",
                "sha256": sha256_file(ev.amendment_path),
            },
            "target_grid_spec": {
                "relative_path": "configs/target-grid.yaml",
                "sha256": sha256_file(ev.target_grid_path),
            },
            "selection_protocol": {
                "relative_path": "docs/selection-protocol.md",
                "sha256": sha256_file(ev.selection_protocol_path),
            },
            "readiness_report": {
                "relative_path": "reports/readiness_report.md",
                "sha256": sha256_file(ev.readiness_path),
            },
            "local_mask_audits_v3": {
                "relative_path_pattern": "evidence/local-mask-audit-v3-order{1..21}.json",
                "count": len(ev.mask_audits),
                "sha256": {
                    str(order): sha256_file(
                        STAGE_ROOT / f"evidence/local-mask-audit-v3-order{order}.json"
                    )
                    for order in sorted(ev.mask_audits)
                },
            },
        },
        "checks": checks,
        "boundary": {
            "read_only": True,
            "earth_engine_called": False,
            "frozen_evidence_rewritten": False,
            "eligibility_re_adjudicated": False,
            "split_reassigned": False,
            "membership_changed": False,
        },
    }

    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(
        {"status": payload["status"], "checks": len(checks), "failed": failed},
        ensure_ascii=False,
    ))
    if failed:
        # 合同⑨ fail-closed：证据漂移时不得继续发布任何就绪结论
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
