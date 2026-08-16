#!/usr/bin/env python3
"""执行重新资格化 Gate（节点约束 nc_b6d6ef3e44f2）。

判据取自 configs/requalification-gate-criteria-v1.json，冻结于任何新域统计
可见之前。本程序只执行不选择。

G1 的可执行性说明：冻结判据要求「逐 domain 逐 fold 在其训练支持区内取 IQR」，
但本节点不产出 fold 结构（fold 是 Stage 7.3 针对单 ROI 的构造）。本程序改测
domain 级 IQR，二者关系是单向的——fold 训练区是 domain 支持区的子集，子集的
四分位距不大于全集，故：
    domain 级 IQR < 0.10  ⇒  fold 级必然 < 0.10  ⇒  可确定判 not_warranted
    domain 级 IQR ≥ 0.10  ⇒  fold 级未定        ⇒  不足以判 warranted
该单向性使本次测量在「不满足」方向上是严格的，在「满足」方向上不充分。
如实登记，不以 domain 级数值冒充判据所要求的 fold 级数值。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

CONTAINER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
# 用本容器的 numpy 实现——当前环境无 scipy。该实现已与 Stage 7.6 冻结的
# v_sky 栅格逐点比对，max|Δ| = 2.98e-08（float32 存储精度量级）。
from svf_numpy_v1 import svf_at_points, verify_against_stage76  # noqa: E402

N_AZIMUTH, D_SEARCH_M, CURVATURE = 36, 10000.0, True     # Stage 7.6 冻结参数
BUFFER_PIXELS = 334                                      # 334 × 30 = 10020 m ≥ D
RES = 30.0
N_SAMPLE = 4000
CACHE = CONTAINER / "outputs/dem_cache"


def main() -> int:
    criteria = json.loads((CONTAINER / "configs/requalification-gate-criteria-v1.json")
                          .read_text(encoding="utf-8"))
    manifest = json.loads((CONTAINER / "evidence/dataset-domain-split-manifest-v1.json")
                          .read_text(encoding="utf-8"))
    g1 = next(c for c in criteria["criteria"]["categories"] if c["id"] == "G1")
    threshold = 0.10
    assert "0.10" in g1["criterion"], "G1 阈值须与冻结判据一致"

    consistency = verify_against_stage76()
    print(f"实现一致性核验：与 Stage 7.6 冻结 v_sky 比对 {consistency['n_compared']} 点，"
          f"max|Δ| {consistency['max_abs_difference']:.2e}\n")
    rng = np.random.default_rng(20260816)
    per_domain = []
    for domain in manifest["domains"]:
        did, roi = domain["domain_id"], domain["roi"]
        path = CACHE / f"{did}_dem_plus10km.tif"
        if not path.exists():
            raise SystemExit(f"stop: {path} 不存在，请先运行 fetch_domain_dems_v1.py")
        with rasterio.open(path) as ds:
            Z = ds.read(1).astype("float64")
            Z = np.where(Z <= -1000, np.nan, Z)
            transform = ds.transform
        left, bottom, right, top = roi["bounds"]
        xs = rng.uniform(left, right, N_SAMPLE)
        ys = rng.uniform(bottom, top, N_SAMPLE)
        v = svf_at_points(Z, transform, xs, ys, N_AZIMUTH, D_SEARCH_M, CURVATURE, RES)
        v = v[np.isfinite(v)]
        q25, q75 = np.percentile(v, [25, 75])
        iqr = float(q75 - q25)
        rec = {"domain_id": did, "split_role": domain["split_role"],
               "n_sample": int(v.size), "v_sky_min": float(v.min()),
               "v_sky_median": float(np.median(v)), "v_sky_max": float(v.max()),
               "iqr": iqr,
               "fraction_below_stage76_support_gate": float(np.mean(v < 0.05)),
               "dem_sha256_note": "DEM 为按 manifest 参数从 GEE 重取，缓存于 outputs/dem_cache（不入 git）"}
        per_domain.append(rec)
        print(f"  {did:<26} [{domain['split_role']:<11}] "
              f"v_sky {v.min():.3f}–{v.max():.3f} 中位 {np.median(v):.4f}  IQR {iqr:.4f}")

    iqrs = sorted(r["iqr"] for r in per_domain)
    median_iqr = float(np.median(iqrs))
    g1_satisfied_at_domain_level = median_iqr >= threshold

    baseline_iqr_median = 0.062      # Stage 7.6 的 train 单元 fold 级 IQR 中位
    report = {
        "schema": "mountainrs-stage7.8-requalification-gate-result-v1",
        "constraint": "nc_b6d6ef3e44f2",
        "criteria_source": "configs/requalification-gate-criteria-v1.json（冻结于任何新域统计可见之前）",
        "executed_on": "2026-08-16",
        "G1_variation_range": {
            "threshold": threshold,
            "measured_median_iqr_domain_level": median_iqr,
            "per_domain": per_domain,
            "baseline_reference": {
                "value": baseline_iqr_median,
                "level": "fold（Stage 7.6 的 train 单元）",
                "comparability_caveat": "基准值是 fold 级，本次测量是 domain 级，二者不同尺度，"
                                        "不可直接相减比较大小差。列出仅供量级参照。"},
            "measurement_level": "domain（非判据要求的 fold 级）",
            "one_way_validity": {
                "reason": "fold 训练区是 domain 支持区的子集，子集的 IQR 不大于全集。",
                "if_below_threshold": "可确定判 G1 不满足",
                "if_at_or_above_threshold": "不足以判 G1 满足——须有 fold 结构方能严格执行判据",
            },
            "verdict": ("not_satisfied" if not g1_satisfied_at_domain_level
                        else "indeterminate_at_this_measurement_level"),
            "implementation_consistency": consistency,
            "v_sky_parameters": {"N_azimuth": N_AZIMUTH, "D_search_m": D_SEARCH_M,
                                 "earth_curvature": CURVATURE,
                                 "source": "Stage 7.6 svf-geometry-gate 冻结值，未因新域调整"},
        },
        "G2_independent_anchor": {
            "verdict": "not_satisfied",
            "basis": "Reference Registry 中 ground_truth 类为 0 项。唯一的 reference_observation "
                     "（Sentinel-2）其 unverifiable_scope 明确包含『不可用于验证绝对辐射定标』与"
                     "『不可用于验证 DEM 几何本身』，故不能解除 Stage 7.5 的任何 "
                     "deferred_missing_anchor 判定，也不能独立约束 alpha 所折叠的透过率、"
                     "辐照度与平均反照率中的任何一个。",
            "what_would_change_it": "取得落于选定 domain 内、时间与 Landsat acquisition 有交集的"
                                    "地面原位测量（见 Reference Registry 的 recovery_condition）。",
        },
        "G3_state_constraint": {
            "verdict": "not_satisfied",
            "basis": "判据要求指明具体状态、具体新证据与不依赖任何未 qualified 算子的具体信息通路。"
                     "本节点新增的证据是同一类 Landsat 光学观测的更多区域样本，以及一个独立的光学"
                     "参考观测；二者都须经由 L2 算子才能连到任何 L1 状态，而 Stage 7.6 的 qualified "
                     "算子集合为空。故不存在绕开未资格化算子的信息通路。",
            "explicitly_rejected_reasoning": "『新域数据更多，或许有助于状态激活』属判据明确排除的笼统表述。",
        },
    }
    satisfied = [k for k in ("G1_variation_range", "G2_independent_anchor", "G3_state_constraint")
                 if report[k]["verdict"] == "satisfied"]
    report["verdict"] = ("requalification_warranted" if satisfied
                         else "requalification_not_warranted")
    report["satisfied_categories"] = satisfied
    report["consequence"] = (
        "保持 Stage 7.6 的负结果与 Stage 7.7 的空集不变。禁止凭空增加状态，"
        "禁止放宽 Stage 7.6 的判定阈值，禁止以『方向为正但未达标』作部分翻案依据——"
        "本 Gate 判据二值化，无部分满足档位。"
        if not satisfied else f"据此可 reopen：{satisfied}")
    report["does_not_affect"] = [
        "不解除 nc_8fe5b4709440——Stage 7.9 因 activated_count = 0 被独立阻断，与本 Gate 结论无关。",
        "不改变本节点的 domain 证据与 Reference Registry——它们独立于本 Gate 结论而有效。",
    ]

    out = CONTAINER / "evidence/requalification-gate-result-v1.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nG1 domain 级 IQR 中位 {median_iqr:.4f}（阈值 {threshold}）→ "
          f"{report['G1_variation_range']['verdict']}")
    print(f"G2 独立锚点 → {report['G2_independent_anchor']['verdict']}")
    print(f"G3 状态约束 → {report['G3_state_constraint']['verdict']}")
    print(f"\n判定：{report['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
