#!/usr/bin/env python3
"""只依赖 numpy 的 v_sky 实现，算法与 Stage 7.6 的 compute_svf_v1.py 逐条相同。

为何重写：Stage 7.6 的实现依赖 scipy.ndimage.map_coordinates，而当前环境已无
scipy。改依赖比改算法风险小，但改依赖需要动环境；本文件改用 numpy 直接实现
双线性插值（等价于 map_coordinates 的 order=1, mode="nearest"），使计算不依赖
环境变更。

正确性不靠断言而靠比对：verify_against_stage76() 在基准 ROI 上用本实现算 v_sky，
与 Stage 7.6 冻结的 v_sky_roi_grid_v1.tif 逐像元比对。冻结栅格的 sha256 为
8444955a0dc40e47…，由 Stage 7.6 的 freeze-manifest 登记。
"""
from __future__ import annotations

import numpy as np

R_EARTH = 6371000.0


def bilinear_nearest(Z: np.ndarray, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    """双线性插值，越界坐标钳制到边界——等价于 map_coordinates(order=1, mode='nearest')。"""
    h, w = Z.shape
    r = np.clip(rows, 0.0, h - 1.0)
    c = np.clip(cols, 0.0, w - 1.0)
    r0 = np.floor(r).astype(np.intp)
    c0 = np.floor(c).astype(np.intp)
    r1 = np.minimum(r0 + 1, h - 1)
    c1 = np.minimum(c0 + 1, w - 1)
    fr = r - r0
    fc = c - c0
    return (Z[r0, c0] * (1 - fr) * (1 - fc) + Z[r1, c0] * fr * (1 - fc)
            + Z[r0, c1] * (1 - fr) * fc + Z[r1, c1] * fr * fc)


def distance_samples(D_m: float, res: float) -> np.ndarray:
    """递增步长的距离采样点，与 Stage 7.6 逐字相同。"""
    out, x = [], res
    while x <= D_m:
        out.append(x)
        step = res if x <= 1000 else (2 * res if x <= 5000 else 4 * res)
        x += step
    return np.asarray(out, dtype="float64")


def svf_at_points(Z, transform, xs, ys, n_az, D_m, curvature, res, block=4000):
    """对给定世界坐标点批量计算 v_sky。算法与 Stage 7.6 相同，仅插值实现不同。"""
    ox, oy = transform.c, transform.f
    d = distance_samples(D_m, res)
    drop = (d ** 2) / (2 * R_EARTH) if curvature else np.zeros_like(d)
    az = np.arange(n_az) * 2 * np.pi / n_az
    out = np.empty(len(xs), dtype="float64")

    for s in range(0, len(xs), block):
        bx, by = xs[s:s + block], ys[s:s + block]
        r0 = (oy - by) / res
        c0 = (bx - ox) / res
        z0 = bilinear_nearest(Z, r0, c0)
        acc = np.zeros(len(bx), dtype="float64")
        for a in az:
            sa, ca = np.sin(a), np.cos(a)
            rr = (oy - (by[:, None] + d[None, :] * ca)) / res
            cc = ((bx[:, None] + d[None, :] * sa) - ox) / res
            zz = bilinear_nearest(Z, rr.ravel(), cc.ravel()).reshape(rr.shape)
            rel = zz - z0[:, None] - drop[None, :]
            ang = np.arctan(rel / d[None, :])
            h = np.maximum(ang.max(axis=1), 0.0)
            acc += np.cos(h) ** 2
        out[s:s + block] = acc / n_az
    return out


def verify_against_stage76(n_sample: int = 2000) -> dict:
    """在基准 ROI 上比对本实现与 Stage 7.6 冻结栅格。"""
    import hashlib
    import json
    from pathlib import Path
    import rasterio

    container = Path(__file__).resolve().parents[1]
    s76 = container.parent / "stage7_6_optical_operator"
    freeze = json.loads((s76 / "evidence/freeze-manifest-v1.json").read_text(encoding="utf-8"))
    vs_rec = freeze["artifacts"]["v_sky_roi_grid_v1"]
    vs_path = (s76 / "evidence" / vs_rec["relative_path"]).resolve()
    digest = hashlib.sha256()
    with vs_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != vs_rec["sha256"]:
        raise SystemExit("stop: Stage 7.6 的 v_sky 栅格 hash 漂移，无法用作参照")

    prov = json.loads((s76 / "evidence/dem-extension-provenance-v1.json").read_text(encoding="utf-8"))
    dem_path = (s76 / "evidence" / prov["artifact"]["relative_path"]).resolve()
    with rasterio.open(dem_path) as ds:
        Z = np.where(ds.read(1) <= -1000, np.nan, ds.read(1).astype("float64"))
        dem_transform, res = ds.transform, ds.res[0]
    with rasterio.open(vs_path) as ds:
        frozen = ds.read(1).astype("float64")
        vs_transform = ds.transform
        height, width = ds.height, ds.width

    rng = np.random.default_rng(20260816)
    rows = rng.integers(0, height, n_sample)
    cols = rng.integers(0, width, n_sample)
    xs = vs_transform.c + (cols + 0.5) * res
    ys = vs_transform.f - (rows + 0.5) * res

    mine = svf_at_points(Z, dem_transform, xs, ys, 36, 10000.0, True, res)
    theirs = frozen[rows, cols]
    finite = np.isfinite(mine) & np.isfinite(theirs)
    diff = np.abs(mine[finite] - theirs[finite])
    return {"n_compared": int(finite.sum()),
            "max_abs_difference": float(diff.max()),
            "mean_abs_difference": float(diff.mean()),
            "frozen_sha256": vs_rec["sha256"]}


if __name__ == "__main__":
    result = verify_against_stage76()
    print(f"与 Stage 7.6 冻结 v_sky 比对：{result['n_compared']} 点  "
          f"max|Δ| {result['max_abs_difference']:.2e}  "
          f"mean|Δ| {result['mean_abs_difference']:.2e}")
