#!/usr/bin/env python3
"""为五个选定 domain 取外扩 DEM（供 v_sky 计算）。

外扩 334 像元 = 10020 m ≥ Stage 7.6 冻结的搜索距离 D* = 10000 m。
DEM 本体不入 git，依赖本脚本的可复现获取（参数全部写死在此）。
"""
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path
import ee

CONTAINER = Path(__file__).resolve().parents[1]
EE_PROJECT, SRTM = "gee-et-playground", "USGS/SRTMGL1_003"
BUFFER_PIXELS, RES = 334, 30.0
CACHE = CONTAINER / "outputs/dem_cache"


def main() -> int:
    ee.Initialize(project=EE_PROJECT)
    manifest = json.loads((CONTAINER / "evidence/dataset-domain-split-manifest-v1.json")
                          .read_text(encoding="utf-8"))
    CACHE.mkdir(parents=True, exist_ok=True)
    for domain in manifest["domains"]:
        did, roi = domain["domain_id"], domain["roi"]
        out = CACHE / f"{did}_dem_plus10km.tif"
        if out.exists():
            print(f"  {did:<26} 已存在 {out.stat().st_size/1e6:.1f} MB")
            continue
        left, bottom, right, top = roi["bounds"]
        b = BUFFER_PIXELS * RES
        url = ee.Image(SRTM).select("elevation").getDownloadURL({
            "format": "GEO_TIFF", "crs": f"EPSG:{roi['epsg']}",
            "crs_transform": [RES, 0, left - b, 0, -RES, top + b],
            "dimensions": [int(round((right - left + 2*b)/RES)),
                           int(round((top - bottom + 2*b)/RES))]})
        urllib.request.urlretrieve(url, out)
        print(f"  {did:<26} 取得 {out.stat().st_size/1e6:.1f} MB  外扩 {b:.0f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
