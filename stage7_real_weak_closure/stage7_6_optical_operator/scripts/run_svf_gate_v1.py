#!/usr/bin/env python3
"""执行 svf-geometry-gate：纯几何地选定 (N*, D*)。

只读 DEM。不读取任何 residual、alpha、score 或本节点的实验输出。

收敛测试全程纳入地球曲率。Gate 允许 D ≤ 15 km 时省略曲率，但省略会使
D 从 10 km 到 20 km 的比较同时改变两个量（距离与曲率），破坏单变量对照。
始终纳入是更严格的一侧，不违反 Gate，并使每一步都是干净的单变量比较。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compute_svf_v1 import (  # noqa: E402
    criteria_pass, load_gate, open_dem, sample_points, svf_at_points,
)

N_SAMPLE = 3000
CURVATURE = True


def main() -> int:
    ds, Z, gate, prov = open_dem()
    res = ds.res[0]
    xs, ys = sample_points(N_SAMPLE, 0.0)
    N_CANDS = gate["frozen_parameters_pending_gate"]["azimuth_count_N"]["candidates"]
    D_CANDS = gate["frozen_parameters_pending_gate"]["search_distance_D_m"]["candidates"]
    D_MAX = max(D_CANDS)
    record = {"n_sample": N_SAMPLE, "curvature_in_tests": CURVATURE,
              "step_1_azimuth": [], "step_2_distance": [], "step_3_cross_check": None}

    print(f"DEM {ds.width}×{ds.height}  抽样 {N_SAMPLE}  曲率 {'纳入' if CURVATURE else '省略'}\n")

    # ---- Step 1：固定 D = D_max，测方位收敛 ----
    print(f"Step 1 方位收敛（D 固定 {D_MAX} m）")
    cache = {}
    prev_n, prev_v, n_star = None, None, None
    for n in N_CANDS:
        v = svf_at_points(Z, ds.transform, xs, ys, n, D_MAX, CURVATURE, res)
        cache[(n, D_MAX)] = v
        if prev_v is None:
            print(f"  N={n:>3}  v_sky 均值 {v.mean():.4f}  （基准）")
            record["step_1_azimuth"].append({"N": n, "v_sky_mean": float(v.mean()), "verdict": "baseline"})
        else:
            ok, got = criteria_pass(v, prev_v, gate)
            print(f"  N={n:>3}  v_sky 均值 {v.mean():.4f}  max|Δ| {got['max_abs_delta_v_sky']:.5f}"
                  f"  P99 {got['p99_abs_delta_v_sky']:.5f}  ρ {got['spearman_rho_of_pixel_ranking']:.6f}"
                  f"  → {'收敛' if ok else '未收敛'}")
            record["step_1_azimuth"].append({"N": n, "compared_to": prev_n,
                                             "v_sky_mean": float(v.mean()),
                                             "metrics": got, "converged": ok})
            if ok and n_star is None:
                n_star = prev_n     # 低一档即已足够
        prev_n, prev_v = n, v
    if n_star is None:
        print("\n方位维度未收敛：全部候选均未达阈值")
        record["outcome"] = "fail"; record["reason_code"] = "svf_geometry_not_converged"
        Path("outputs").mkdir(exist_ok=True)
        Path("outputs/svf-gate-run-v1.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1
    print(f"  → N* = {n_star}\n")
    record["n_star"] = n_star

    # ---- Step 2：固定 N*，测距离收敛 ----
    print(f"Step 2 距离收敛（N 固定 {n_star}）")
    prev_d, prev_v, d_star = None, None, None
    for d in D_CANDS:
        v = cache.get((n_star, d))
        if v is None:
            v = svf_at_points(Z, ds.transform, xs, ys, n_star, d, CURVATURE, res)
            cache[(n_star, d)] = v
        if prev_v is None:
            print(f"  D={d:>6}  v_sky 均值 {v.mean():.4f}  （基准）")
            record["step_2_distance"].append({"D_m": d, "v_sky_mean": float(v.mean()), "verdict": "baseline"})
        else:
            ok, got = criteria_pass(v, prev_v, gate)
            print(f"  D={d:>6}  v_sky 均值 {v.mean():.4f}  max|Δ| {got['max_abs_delta_v_sky']:.5f}"
                  f"  P99 {got['p99_abs_delta_v_sky']:.5f}  ρ {got['spearman_rho_of_pixel_ranking']:.6f}"
                  f"  → {'收敛' if ok else '未收敛'}")
            record["step_2_distance"].append({"D_m": d, "compared_to": prev_d,
                                              "v_sky_mean": float(v.mean()),
                                              "metrics": got, "converged": ok})
            if ok and d_star is None:
                d_star = prev_d
        prev_d, prev_v = d, v
    if d_star is None:
        print("\n距离维度未收敛：全部候选均未达阈值（受 DEM 外扩上限 20 km 限制）")
        record["outcome"] = "fail"; record["reason_code"] = "svf_geometry_not_converged"
        Path("outputs").mkdir(exist_ok=True)
        Path("outputs/svf-gate-run-v1.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1
    print(f"  → D* = {d_star} m\n")
    record["d_star"] = d_star

    # ---- Step 3：交叉复核 (N*,D*) vs (2N*,2D*) ----
    n2, d2 = n_star * 2, min(d_star * 2, 20000)
    print(f"Step 3 交叉复核 (N={n_star}, D={d_star}) vs (N={n2}, D={d2})")
    v1 = cache.get((n_star, d_star))
    if v1 is None:
        v1 = svf_at_points(Z, ds.transform, xs, ys, n_star, d_star, CURVATURE, res)
    v2 = svf_at_points(Z, ds.transform, xs, ys, n2, d2, CURVATURE, res)
    ok, got = criteria_pass(v2, v1, gate)
    print(f"  max|Δ| {got['max_abs_delta_v_sky']:.5f}  P99 {got['p99_abs_delta_v_sky']:.5f}"
          f"  ρ {got['spearman_rho_of_pixel_ranking']:.6f}  → {'通过' if ok else '未通过'}")
    record["step_3_cross_check"] = {"pair": [[n_star, d_star], [n2, d2]],
                                    "metrics": got, "passed": ok}

    record["outcome"] = "pass" if ok else "fail"
    if not ok:
        record["reason_code"] = "svf_geometry_not_converged"
        record["note"] = "两维各自收敛但联合未收敛——交叉复核正是为捕捉这种耦合而设。"
    else:
        record["selected"] = {"azimuth_count_N": n_star, "search_distance_D_m": d_star,
                              "earth_curvature": CURVATURE}
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/svf-gate-run-v1.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n结果: {record['outcome']}"
          + (f"  → N*={n_star}, D*={d_star} m, 曲率纳入" if ok else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
