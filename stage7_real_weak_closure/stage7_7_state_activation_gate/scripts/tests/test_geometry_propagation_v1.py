#!/usr/bin/env python3
"""Stage 7.7 fixture F1–F9：几何失效传播的版本化首验。

用例在 configs/geometry-version-and-propagation-v1.json 中于运行前冻结。
每个用例都指明它能杀死哪个错误实现——杀不死任何实现的用例等于没有用例。

两处对冻结用例设定的如实调整，理由随用例记录：
  F1 的 compute_rect 内缩一个像元（见用例内说明）。
  F9 使用真实接缝的统计量级但构造扰动位置（替换前版本未归档）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rasterio  # noqa: E402

from geometry_propagation_v1 import (  # noqa: E402
    ARTIFACT_ONLY, INVALIDATED, QUARANTINED, SCOPE_EXTENSION, VALID,
    VALUE_CHANGE_IN_SCOPE, Artifact, CacheVersionMismatch, ConsumerRegistry,
    DependencyGraph, Geometry, Grid, UnregisteredConsumer, classify_change,
    geometry_version_digest, load_cache_or_fail, load_rules, propagate, rollback,
)

REPO = Path(__file__).resolve().parents[4]
FROZEN_DEM = REPO / "stages/stage6_5_real_landsat_observation_stress_test/outputs/dem_on_shadowrisk_grid.tif"
EXTENDED_DEM = REPO / "stages/stage2_dem_terrain/data/dem_roi_plus_20km_utm48n.tif"
ROI = (292230.0, 3451230.0, 311730.0, 3473790.0)

RESULTS: list[tuple[str, bool, str]] = []


def check(case: str, condition: bool, detail: str) -> None:
    RESULTS.append((case, bool(condition), detail))
    print(f"  [{'✓' if condition else '✗'}] {case}  {detail}")


def open_geometry(path: Path, artifact_id: str) -> Geometry:
    with rasterio.open(path) as dataset:
        values = dataset.read(1).astype("float64")
        transform = dataset.transform
        grid = Grid(origin_x=transform.c, origin_y=transform.f,
                    resolution=transform.a, width=dataset.width, height=dataset.height)
    return Geometry(artifact_id=artifact_id, values=values, grid=grid)


def synthetic(artifact_id: str, origin_x: float, origin_y: float, res: float,
              width: int, height: int, fill: float = 100.0) -> Geometry:
    grid = Grid(origin_x, origin_y, res, width, height)
    return Geometry(artifact_id, np.full((height, width), fill, dtype="float64"), grid)


def standard_graph() -> DependencyGraph:
    """光学链路的最小依赖图。"""
    return DependencyGraph([
        Artifact("dem", "geometry"),
        Artifact("slope", "geometry_consumer", ["dem"], consumer_name="slope"),
        Artifact("aspect", "geometry_consumer", ["dem"], consumer_name="aspect"),
        Artifact("cos_i", "geometry_consumer", ["dem"], consumer_name="cos_i"),
        Artifact("v_sky", "geometry_consumer", ["dem"], consumer_name="v_sky"),
        Artifact("alpha_fit", "derived", ["cos_i"]),
        Artifact("ablation_table", "derived", ["alpha_fit", "v_sky"]),
        Artifact("qa_mask", "observation"),          # 与几何无依赖路径
    ])


def main() -> int:
    rules = load_rules()
    registry = ConsumerRegistry(rules)
    print(f"规则来源 {rules['schema']}，登记消费者 {registry.known()}\n")

    # ---- F1：artifact 变而影响域内值不变（真实素材）----
    print("F1 artifact 变而影响域内值不变 —— 杀死「只比对文件 hash」的实现")
    if not (FROZEN_DEM.exists() and EXTENDED_DEM.exists()):
        check("F1", False, "真实 DEM 缺失，用例无法执行")
    else:
        old = open_geometry(FROZEN_DEM, "dem@frozen")
        new = open_geometry(EXTENDED_DEM, "dem@extended")
        # 冻结 DEM 的覆盖恰好等于 ROI，无余量，故 ROI 最外一圈像元的 cos_i
        # 其影响域（±30 m）已伸出 DEM 之外。这是既有事实，不是本用例引入的。
        # 用例取内缩一个像元的 compute_rect，使比较落在影响域完整可比的区域。
        res = old.grid.resolution
        inset = (ROI[0] + res, ROI[1] + res, ROI[2] - res, ROI[3] - res)
        verdict = classify_change(old, new, "cos_i", inset, registry)
        check("F1 cos_i 判 artifact_only", verdict["change_class"] == ARTIFACT_ONLY,
              f"{verdict['pixels_compared']} 像元比对，差异 {verdict['pixels_differing']}")
        check("F1 artifact hash 确实不同",
              verdict["old_artifact_hash"] != verdict["new_artifact_hash"],
              f"{verdict['old_artifact_hash']}… vs {verdict['new_artifact_hash']}…")
        graph = standard_graph()
        manifest = propagate(graph, "dem", [verdict])
        check("F1 不传播，全图保持 valid", manifest["counts"][INVALIDATED] == 0
              and manifest["counts"][QUARANTINED] == 0,
              f"marks: invalidated={manifest['counts'][INVALIDATED]} "
              f"quarantined={manifest['counts'][QUARANTINED]}")
        # 边界事实登记：不内缩时 cos_i 的影响域伸出冻结 DEM
        full = classify_change(old, new, "cos_i", ROI, registry)
        check("F1 附带事实：不内缩时判 scope_extension",
              full["change_class"] == SCOPE_EXTENSION,
              "ROI 最外一圈的 cos_i 依赖超出冻结 DEM 覆盖——既有事实，本用例只是使其显形")

    # ---- F2 / F3：同一变更，不同半径的消费者结论相反 ----
    print("\nF2/F3 影响域外的值变化 —— 杀死「按整 artifact 比值」与「按自身范围比值」")
    # 栅格必须容纳 v_sky 的影响域（ROI ± 10 km = x 282230–321730, y 3441230–3483790），
    # 否则会判 scope_extension 而非值变化——用例就测不到它要测的东西。
    base = synthetic("dem@base", 280000.0, 3486000.0, 30.0, 1500, 1550, fill=2000.0)
    changed_values = base.values.copy()
    # 在距 ROI 边界约 5 km 处改动高程
    far_x, far_y = ROI[0] - 5000.0, (ROI[1] + ROI[3]) / 2
    rows, cols = base.grid.window_for(far_x - 200, far_y - 200, far_x + 200, far_y + 200)
    changed_values[rows, cols] += 50.0
    changed = Geometry("dem@changed", changed_values, base.grid)

    v_cos = classify_change(base, changed, "cos_i", ROI, registry)
    check("F2 cos_i（半径 30 m）判 artifact_only", v_cos["change_class"] == ARTIFACT_ONLY,
          f"影响域内差异像元 {v_cos.get('pixels_differing')}")
    v_sky = classify_change(base, changed, "v_sky", ROI, registry)
    check("F3 v_sky（半径 10 km）判 value_change_in_scope",
          v_sky["change_class"] == VALUE_CHANGE_IN_SCOPE,
          f"影响域内差异像元 {v_sky.get('pixels_differing')}，"
          f"max|Δ| {v_sky.get('max_abs_difference')}")

    graph = standard_graph()
    manifest = propagate(graph, "dem", [v_cos, v_sky])
    check("F3 v_sky 得 invalidated", manifest["marks"]["v_sky"] == INVALIDATED,
          manifest["reason_codes"].get("v_sky", "")[:60])
    check("F3 cos_i 保持 valid", manifest["marks"]["cos_i"] == VALID,
          "同一次变更对不同半径消费者结论相反，这是设计意图")

    # ---- F4：无依赖 artifact 保持有效 ----
    print("\nF4 无依赖 artifact —— 杀死「按空间包围盒失效」的实现")
    check("F4 qa_mask 保持 valid", manifest["marks"]["qa_mask"] == VALID,
          "与几何无依赖路径；空间范围重叠不构成依赖（架构 §156）")
    check("F4 unaffected 被显式列出", "qa_mask" in manifest["unaffected_artifacts"],
          f"unaffected: {manifest['unaffected_artifacts']}")

    # ---- F5：直接依赖与后代的标记区分 ----
    print("\nF5 两级标记区分 —— 杀死「合并成一个标记」的实现")
    check("F5 ablation_table 得 quarantined",
          manifest["marks"]["ablation_table"] == QUARANTINED,
          "消费了 invalidated 的 v_sky，其值是否改变尚未确定")
    check("F5 两级标记不混用",
          manifest["marks"]["v_sky"] == INVALIDATED
          and manifest["marks"]["ablation_table"] == QUARANTINED,
          "invalidated=已知失效，quarantined=待确认")
    check("F5 传播路径被记录",
          manifest["propagation_path"].get("ablation_table") == ["v_sky", "ablation_table"],
          f"{manifest['propagation_path'].get('ablation_table')}")

    # ---- F6：旧 cache 不得静默载入 ----
    print("\nF6 cache 版本 —— 杀死「不匹配即静默重算」的实现")
    digest_old = geometry_version_digest(base, "v_sky", ROI, registry)
    digest_new = geometry_version_digest(changed, "v_sky", ROI, registry)
    check("F6 变更后摘要不同", digest_old != digest_new,
          f"{digest_old[:12]}… → {digest_new[:12]}…")
    entry = {"id": "v_sky_cache", "geometry_version_digest": digest_old, "payload": "stale"}
    try:
        load_cache_or_fail(entry, digest_new)
        check("F6 版本不符时 fail closed", False, "未抛出异常 ← 静默载入了旧 cache")
    except CacheVersionMismatch as exc:
        check("F6 版本不符时 fail closed", True, str(exc)[:70])
    check("F6 版本相符时正常载入",
          load_cache_or_fail(entry, digest_old) == "stale", "同版本不阻断")

    # ---- F7：未登记消费者 fail closed ----
    print("\nF7 未登记消费者 —— 杀死「默认半径 0」的实现")
    try:
        registry.radius("backscatter_geometry")
        check("F7 未登记消费者停机", False, "未抛出异常 ← 默认了半径")
    except UnregisteredConsumer as exc:
        check("F7 未登记消费者停机", True, str(exc)[:70])

    # ---- F8：回滚可达 ----
    print("\nF8 回滚")
    before = {aid: VALID for aid in standard_graph().nodes}
    receipt = {"marks_before": before, "marks_after": manifest["marks"]}
    restored = rollback(before, receipt)
    check("F8 标记回到传播前", restored == before,
          f"{len(restored)} 个 artifact 全部回到 valid")
    try:
        rollback({"dem": INVALIDATED}, receipt)
        check("F8 状态不符时拒绝回滚", False, "未抛出异常")
    except ValueError:
        check("F8 状态不符时拒绝回滚", True, "receipt 与给定状态不符即拒绝")

    # ---- F9：ROI 边界接缝落在两个消费者影响域的不同侧 ----
    print("\nF9 接缝边界案例")
    print("  设定调整：Stage 7.6 的替换前版本未归档，故本用例采用真实接缝的统计量级")
    print("  （std 7.792 m）但构造扰动位置。这不是纯真实素材，如实标注。")
    seam_values = base.values.copy()
    # 在 ROI 边界外侧 100–200 m 的环带上施加接缝量级的扰动
    outer = base.grid.window_for(ROI[0] - 200, ROI[1] - 200, ROI[2] + 200, ROI[3] + 200)
    inner = base.grid.window_for(ROI[0] - 100, ROI[1] - 100, ROI[2] + 100, ROI[3] + 100)
    ring = np.zeros_like(seam_values, dtype=bool)
    ring[outer] = True
    ring[inner] = False
    seam_values[ring] += 7.792
    seam = Geometry("dem@seam", seam_values, base.grid)

    seam_cos = classify_change(base, seam, "cos_i", ROI, registry)
    seam_vsky = classify_change(base, seam, "v_sky", ROI, registry)
    check("F9 cos_i（半径 30 m）不受接缝影响",
          seam_cos["change_class"] == ARTIFACT_ONLY,
          "接缝在 ROI 外 100–200 m，超出 cos_i 的 30 m 影响域")
    check("F9 v_sky（半径 10 km）受接缝影响",
          seam_vsky["change_class"] == VALUE_CHANGE_IN_SCOPE,
          f"影响域内差异像元 {seam_vsky.get('pixels_differing')}")
    seam_manifest = propagate(standard_graph(), "dem", [seam_cos, seam_vsky])
    check("F9 规则给出确定答案而非回避",
          seam_manifest["marks"]["v_sky"] == INVALIDATED
          and seam_manifest["marks"]["cos_i"] == VALID,
          "同一接缝，两个消费者结论相反且各有依据")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} 通过")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
