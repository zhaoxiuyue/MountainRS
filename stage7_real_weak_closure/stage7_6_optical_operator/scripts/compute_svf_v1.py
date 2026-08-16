#!/usr/bin/env python3
"""天空可视因子 v_sky 的计算与几何收敛 Gate。

全程只读 DEM。不读取任何 residual、alpha、score 或本节点的实验输出——精度
选择必须是纯几何过程（见 configs/svf-geometry-gate-v1.json）。

算法：对每个目标像元，沿 N 个等间隔方位向外搜索至距离 D，取各方位的最大
地平线仰角 h(φ)，在各向同性天空假设下
    v_sky = (1/N) · Σ_φ cos²(h(φ))

距离采样按递增步长：远处地形的角分辨率随距离下降，等间距采样是浪费。
近场 (≤1 km) 用原生栅格步长，中场 (1–5 km) 2 倍，远场 (>5 km) 4 倍。
该采样方案是冻结参数的一部分，不得依据结果调整。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import map_coordinates

CONTAINER = Path(__file__).resolve().parents[1]
GATE_PATH = CONTAINER / "configs" / "svf-geometry-gate-v1.json"

R_EARTH = 6371000.0


def distance_samples(D_m: float, res: float) -> np.ndarray:
    """递增步长的距离采样点。"""
    out, x = [], res
    while x <= D_m:
        out.append(x)
        step = res if x <= 1000 else (2 * res if x <= 5000 else 4 * res)
        x += step
    return np.asarray(out, dtype="float64")


def svf_at_points(Z, transform, xs, ys, n_az, D_m, curvature, res, block=4000):
    """对给定世界坐标点批量计算 v_sky。"""
    ox, oy = transform.c, transform.f
    d = distance_samples(D_m, res)
    drop = (d ** 2) / (2 * R_EARTH) if curvature else np.zeros_like(d)
    az = np.arange(n_az) * 2 * np.pi / n_az
    out = np.empty(len(xs), dtype="float64")

    for s in range(0, len(xs), block):
        bx = xs[s:s + block]
        by = ys[s:s + block]
        r0 = (oy - by) / res
        c0 = (bx - ox) / res
        z0 = map_coordinates(Z, [r0, c0], order=1, mode="nearest")
        acc = np.zeros(len(bx), dtype="float64")
        for a in az:
            sa, ca = np.sin(a), np.cos(a)
            # (n_pts, n_dist)
            rr = (oy - (by[:, None] + d[None, :] * ca)) / res
            cc = ((bx[:, None] + d[None, :] * sa) - ox) / res
            zz = map_coordinates(Z, [rr.ravel(), cc.ravel()], order=1,
                                 mode="nearest").reshape(rr.shape)
            # 曲率：远处地面下沉，视线相对高度随之降低
            rel = zz - z0[:, None] - drop[None, :]
            ang = np.arctan(rel / d[None, :])
            h = np.maximum(ang.max(axis=1), 0.0)
            acc += np.cos(h) ** 2
        out[s:s + block] = acc / n_az
    return out


def load_gate() -> dict:
    return json.loads(GATE_PATH.read_text(encoding="utf-8"))


def open_dem():
    gate = load_gate()
    # DEM 路径由 provenance 证据给出
    prov = json.loads((CONTAINER / "evidence" /
                       "dem-extension-provenance-v1.json").read_text(encoding="utf-8"))
    p = (CONTAINER / "evidence" / prov["artifact"]["relative_path"]).resolve()
    ds = rasterio.open(p)
    Z = ds.read(1).astype("float64")
    Z = np.where(Z <= -1000, np.nan, Z)
    return ds, Z, gate, prov


def roi_bounds():
    """Stage 7.1 冻结 ROI。"""
    return (292230.0, 3451230.0, 311730.0, 3473790.0)


def sample_points(n, margin_m, seed=20260815):
    rng = np.random.default_rng(seed)
    x0, y0, x1, y1 = roi_bounds()
    return (rng.uniform(x0 + margin_m, x1 - margin_m, n),
            rng.uniform(y0 + margin_m, y1 - margin_m, n))


def criteria_pass(v_new, v_old, gate):
    from scipy.stats import spearmanr
    c = {m["name"]: m["threshold"] for m in gate["convergence_criteria"]["metrics"]}
    d = np.abs(v_new - v_old)
    got = {
        "max_abs_delta_v_sky": float(d.max()),
        "p99_abs_delta_v_sky": float(np.percentile(d, 99)),
        "spearman_rho_of_pixel_ranking": float(spearmanr(v_new, v_old).statistic),
    }
    ok = (got["max_abs_delta_v_sky"] <= c["max_abs_delta_v_sky"]
          and got["p99_abs_delta_v_sky"] <= c["p99_abs_delta_v_sky"]
          and got["spearman_rho_of_pixel_ranking"] >= c["spearman_rho_of_pixel_ranking"])
    return ok, got


def curvature_required(D_m, gate):
    return D_m > gate["curvature_rule"]["threshold_m"]


if __name__ == "__main__":
    ds, Z, gate, prov = open_dem()
    print(f"DEM {ds.width}×{ds.height} res {ds.res[0]:.1f} m  "
          f"sha256 {prov['artifact']['sha256'][:16]}…")
    xs, ys = sample_points(int(sys.argv[1]) if len(sys.argv) > 1 else 2000, 0.0)
    v = svf_at_points(Z, ds.transform, xs, ys, 36, 5000.0, False, ds.res[0])
    print(f"自检 N=36 D=5km: v_sky {v.min():.3f}–{v.max():.3f} 均值 {v.mean():.4f}")
