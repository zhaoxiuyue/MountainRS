# Grid declaration amendment v1

Status: **frozen by owner ruling on 2026-08-04**, after proposal review.
Scope: this amendment supersedes exactly one token in two named clauses. It does
not authorize an Export task, does not make any acquisition `stack_eligible`,
does not assign a split, and does not change the candidate universe, canonical
order, ROI or target grid.

PF3 node `nd_a5842cfa87de` (Stage 7.1). Diagnosis `ev_63829dc21a29`;
self-reported violation `ev_215a9d9c54cd`; proposal
`reports/grid-declaration-amendment-proposal-v1.md`.

## 1. Clauses amended

**A.** `docs/mask-preserving-observation-storage-protocol-v2.md` section 3:
> The task may not set `scale`, **`dimensions`**, `bestEffort`, a non-nearest
> resampling mode, a shared nodata value, or a partial/sharded-output option.

**B.** `docs/selection-protocol.md` section 9.3:
> it must not substitute `scale`, **`dimensions`**, `bestEffort` or a shifted grid.

Only the token `dimensions` is amended. `scale`, `bestEffort`, non-nearest
resampling, shared nodata and partial/sharded output remain prohibited without
change. Neither source document is edited in place: their SHA-256 values are
pinned by the frozen `frozen_contract` of manifest v2 and v3, so this amendment
supersedes the named clause as a separate document, exactly as protocol v2
superseded the v1 storage route.

## 2. Why the amendment is necessary

`configs/target-grid.yaml` requires `exact_grid_match_required: true` with
`silent_resampling: prohibited`. Read-only probing (0 tasks, 0 assets,
0 downloads) established that this requirement is unsatisfiable while
`dimensions` is prohibited:

- Earth Engine echoes the region back as the exact integers
  `[292230, 3451230, 311730, 3473790]`, `geodesic=false`, EPSG:32648;
- Earth Engine's own bounds computation puts the western edge **0.0 m** from the
  grid origin, at column index exactly `0.0`;
- yet `clip(region).reproject(crs, crsTransform)` reports `dimensions=[652, 754]`
  with `origin=[-1, -1]` — the raster materialisation path adds a one-pixel
  skirt around the clip geometry;
- the same region and transform give `488800` through `reduceRegion` and
  `489552` through `Export`.

Evidence in the field: task `WDI4LVYAKCREQUJPII2JAFV2` terminal FAILED with
`Export too large: specified 489552 pixels (max: 488800)`; task
`VQLKW3N7RVXY4432QF3O2XSO` terminal COMPLETED but produced 651×752, retained
un-admitted at
`data/raw/rejected_exports/LC08_130038_20230101__SR_B4_SR_B5_QA_PIXEL__VALID__v2_attempt2_651x752_rejected.tif`.

The prohibition was written to forbid a **substituted or approximated** grid.
Here `dimensions` is the only means of honouring that intent. Left unamended,
clauses A and B are permanently mutually exclusive with
`exact_grid_match_required`, and this node has no solution.

## 3. Amended rule

The output grid must equal the frozen `shadow-risk-b-b4-grid-v1`. The task must
not set `scale`, `bestEffort`, a non-nearest resampling mode, a shared nodata
value, or a partial/sharded-output option.

The task **may** set `dimensions` **if and only if all** of the following hold:

1. `crs` equals the frozen `EPSG:32648` verbatim;
2. `crsTransform` equals the frozen six-element affine
   `[30.0, 0.0, 292230.0, 0.0, -30.0, 3473790.0]` element by element;
3. `dimensions` equals `"<width>x<height>"` **computed from the frozen
   `target_grid.shape`** — `"650x752"`. A hard-coded literal that is not derived
   from the frozen shape does not satisfy this condition;
4. the same task does **not** also pass `region`. The output grid may be
   declared, never derived from geometry;
5. `maxPixels` equals the frozen `pixel_count` (488800), so that any grid
   inflation fails server-side rather than producing an over-wide file;
6. local verification runs **before** the product is placed: the actual
   GeoTIFF's crs, transform, width, height, bounds, resolution and pixel
   alignment each equal the frozen values. Any mismatch stops the run and the
   product must not enter the alias directory.

If any condition fails, `dimensions` remains prohibited.

This is strictly stronger than the original prohibition: the original was a
sentence with no machine enforcement; this is a prohibition plus six bindings
plus a pre-placement check, and section 4 requires all of it to be asserted by
the auditor.

## 4. Auditor obligations

A contributing cause of the incident was that `audit_export_manifest_v3.py`
verified the SHA-256 of the protocol documents but never the **prohibition list
written inside them**. Hashes matched while the text was violated, and the audit
still passed green. Verifying that a document was not rewritten is not the same
as verifying that it was obeyed.

The manifest auditor must assert all of the following:

1. `execution.scale_parameter == "omitted"`;
2. `execution.best_effort is False`;
3. `execution.resampling == "nearest_neighbor_default"` and
   `execution.explicit_resample_call is False`;
4. `execution.format_options_no_data == "omitted"`;
5. `execution.skip_empty_tiles is False`;
6. `execution.region_parameter == "omitted"`;
7. `execution.dimensions_parameter` equals the value **computed from
   `target_grid.shape`**, never a hard-coded literal;
8. `execution.max_pixels == target_grid.pixel_count`;
9. both the protocol documents **and this amendment** are present with matching
   SHA-256, and the amendment binds back to the manifest under audit.

Regression tests must construct a mutated manifest violating each assertion and
prove the auditor rejects it.

## 5. Retroactive scope: R

The owner ruled **R — retroactive admission** on 2026-08-04.

Three acquisitions were exported under this form before the amendment was
frozen. They are admitted because the six conditions of section 3 are
**independently verifiable from the recorded request and the product itself**,
without relying on any statement of intent at execution time, and all three
were verified to satisfy every condition:

| order | acquisition | task | sha256 |
|---|---|---|---|
| 1 | `LC08_130038_20230101` | `HTBLVMKOD7MLLEDHJXBOHAFC` | `69530d52…` |
| 2 | `LC08_130038_20230117` | `7G7C37XHKPCNJUD6PUIHTWRZ` | `dfafc16c…` |
| 3 | `LC08_130038_20230202` | `OT3EPS2CNRDFQ5GHGTT5F7LF` | `35a11988…` |

The per-condition verification is recorded in
`evidence/grid-declaration-amendment-v1.json`. Admission here means only that
the production method is contract-compliant; it does **not** make any of the
three `stack_eligible`, which still requires the frozen local terrain and
support-domain audit with `base_valid_land > 0`.

## 6. What this amendment does not do

- does not change the 21-acquisition candidate universe
  (`15d5522991f9…`), canonical order, ROI or any target-grid value;
- does not make any acquisition `stack_eligible` and does not assign a split;
- introduces no numerical threshold and does not change QA, reflectance,
  support-domain or `base_valid_land` semantics;
- does not rewrite `export-manifest-v1.json`, `export-manifest-v2.json` or any
  `preserve_bytes` frozen evidence;
- does not relax attempt or retry caps, and does not relax
  `maximum_active_exports = 1`.
