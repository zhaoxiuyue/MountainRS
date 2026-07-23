# Stage 7.1 prospective acquisition selection protocol

Status: **frozen before any Stage 7.1 GEE catalog query**
Scope: Stage 7.1 First Action only. This protocol does not authorize a GEE run,
an outbound request, a data export, alpha fitting, scoring, or an experiment.

## 1. Frozen product scope

- Platform and sensor: Landsat 8 OLI/TIRS.
- Collection: `LANDSAT/LC08/C02/T1_L2`.
- WRS: Path 130 / Row 38.
- Time window: `[2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z)`.
- The start is inclusive and the end is exclusive.
- The candidate catalog must enumerate every acquisition in this range that
  satisfies the product, WRS, time and complete target-ROI footprint rules.
- `CLOUD_COVER` may be reported as metadata, but must not be used to retain only
  a top-N list, rank the catalog, or silently remove difficult observations.

The complete Earth Engine asset/product identity is the acquisition key.
`system:index` remains a required source field but is not sufficient on its own.
Repeated exports, renamed files, different crops and different ROIs from the same
product remain one acquisition. A composite, mosaic or derived raster is not an
acquisition.

## 2. Target ROI and grid frozen before candidate inspection

The prospective common grid is `shadow-risk-b-b4-grid-v1`, read from the real
local Shadow-risk B B4 raster. Its normative machine-readable definition is
`configs/stage7_1/target-grid.yaml`.

The choice is justified only because:

1. B4, B5, QA_PIXEL, DEM, slope, aspect and cos_i have already passed exact CRS
   and grid-alignment checks.
2. The frozen Stage 7.0 accounting finds nonzero lit, near-zero and shadow land
   support on this ROI.
3. The choice is fixed before any new acquisition catalog is viewed.
4. It is a geometry pressure-test ROI for the prototype stack.

It does not represent the whole Longmenshan region. Residuals, fitted performance,
future validation results and future test results are prohibited reasons for
choosing or changing this ROI.

The footprint admission threshold is `coverage_ratio >= 0.999999`, where the
ratio is source-footprint intersection area divided by frozen target-ROI area.
This tolerance exists only for geometry arithmetic; it does not permit a missing
strip of the canonical grid.

## 3. Candidate state layers

The states are ordered, but each has a different evidence authority:

- `cataloged`: the product, time, WRS and complete common-ROI footprint rules pass.
- `exportable`: `cataloged`, with full asset identity, complete
  `system:time_start`, solar geometry and QA fields present.
- `stack_eligible`: local B4/B5/QA members and hashes exist, exact target-grid
  integrity passes, and `base_valid_land > 0`.
- `model_eligible`: not decided in Stage 7.1. Stage 7.2 must freeze its fitting
  thresholds before model work.

Stage 7.1 records actual lit counts but does not use a minimum calibration-lit
count to accept or reject an acquisition. No threshold may be inferred from the
two existing products.

## 4. QA, reflectance and support semantics

The prospective catalog and later local stack use the frozen definitions:

- QA_PIXEL bits 0–5—fill, dilated cloud, cirrus, cloud, cloud shadow and snow—must
  all equal zero for QA-clear support.
- QA_PIXEL water bit 7 is counted separately and excluded from
  `base_valid_land`.
- Surface reflectance is `DN × 0.0000275 − 0.2` for `SR_B4` and `SR_B5`.
- B4 and B5 must be finite, source-mask-valid, nodata-valid and inside the
  inclusive analysis range `[-0.05, 1.0]`.
- `base_valid` additionally requires finite, nodata-valid terrain geometry.
- `base_valid_land = base_valid AND NOT water`.
- `cos_i > 0.1` is direct-only `supported`.
- `cos_i <= 0.1` is `unsupported_by_direct_only`.
- Unsupported land remains in the coverage denominator and is never counted as
  a low-error success.

Per-pixel `observation_count`, `valid_count` and `valid_ratio` must be derived
from per-acquisition records. A composite cannot replace those records.

## 5. Acquisition-level split

The split is assigned only after the complete `stack_eligible` set is frozen.
Let `N` be the number of distinct stack-eligible acquisition identities.

1. Sort by `system:time_start` ascending, then full product ID ascending.
2. If `N < 3`, stop; do not create a nominal split.
3. `n_train = max(1, floor(0.6 × N))`.
4. `n_validation = max(1, floor(0.2 × N))`.
5. `n_test = N − n_train − n_validation`; it must be positive.
6. Allocate contiguous time segments: earlier acquisitions to train, middle to
   validation, later to test.
7. Every ROI and export belonging to one acquisition inherits that acquisition's
   split.

After the split is frozen, model behavior cannot reorder it. If an assigned
member later fails integrity checks, the protocol and catalog must be explicitly
revised; silent replacement or backfilling is prohibited.

## 6. Grid and resampling boundary

Canonical stack members must exactly match the frozen CRS, affine transform,
shape, bounds, resolution and pixel alignment. A mismatch stops admission and is
reported. A silently resampled member must not be presented as an original
observation. QA_PIXEL must never use continuous interpolation.

## 7. Prospective catalog auditor boundary

`scripts/stage7_1/gee_catalog_audit.js` is a reviewable, not-yet-authorized query.
When separately authorized, it may only:

- query the complete frozen collection/time/WRS range;
- calculate source-footprint coverage and QA/coverage summaries;
- return the complete structured candidate `FeatureCollection`.

It may not submit outbound jobs, fit parameters, score candidates, inspect model
outputs, truncate to low-cloud scenes or select a “best” acquisition. Its output
does not make a candidate stack-eligible; local file, hash and grid verification
remain mandatory.

Before any later outbound action, a local request manifest with a frozen hash is
required. A submitted request is not success. Success requires real task/asset
identity, terminal status and local output hashes reconciled to that manifest.

## 8. Assumptions still requiring GEE verification

- The complete number of 2023 Path 130 / Row 38 acquisitions covering the ROI.
- Whether every cataloged acquisition contains full sensing time, solar and QA
  metadata required for `exportable`.
- Whether at least three acquisitions can later pass local `stack_eligible`
  checks on the exact frozen grid.
- Whether the frozen footprint tolerance behaves as expected for every source
  footprint without admitting incomplete grid coverage.

None of these assumptions has been verified in this First Action.
