# Stage 7.0｜evaluation protocol

## Status and evaluation unit

This protocol freezes the evaluation and reporting rules for `direct_only_hard_mask_v1`. It does not authorize fitting, scoring, an experiment, a PF2 result writeback, or node completion.

The minimum evaluation unit is:

```text
acquisition × non-overlapping ROI × band
```

Pixels are measurements inside that unit, not independent samples. All reporting must retain acquisition ID, ROI/domain identity, split identity, and band identity.

## Acquisition and split rules

1. Acquisition ID is the outer grouping key.
2. All ROIs from one acquisition belong to the same outer train, validation, or test collection; an acquisition must not span those collections in leave-acquisition-out evaluation.
3. Within-acquisition spatial holdout is a secondary spatial diagnostic only, not a substitute for acquisition-level generalization.
4. Calibration buffers never enter fitting or scoring.
5. A multi-date composite is not a single-date acquisition and cannot fill a missing acquisition role.
6. Missing formal metadata remains `missing`; no date, sensing time, solar geometry, CRS, QA linkage, terrain geometry, product identity, ROI boundary, or split identity may be inferred from a filename.
7. Train, validation, and test must all be nonempty. Thus the structural lower bound is three distinct acquisitions. Three is only an executable minimum, not evidence of stable generalization.
8. Every report must state the number of test acquisitions and the number of `acquisition × ROI × band` units.

For leave-acquisition-out, test-acquisition reflectance must not re-fit alpha, select alpha, choose thresholds, choose a model, or determine stopping. The transferred alpha is exactly the unweighted-median training policy in `docs/stage7_0/baseline_spec.md`.

## Current-data status

- `LC08_130038_20230813` and `LC08_130038_20230101` are the two verified acquisitions. Both are Landsat 8 Collection 2 Tier 1 Level 2 SR products with WRS path/row 130/38; sensing time is currently missing from formal metadata.
- The existing 10 C5-D3 geographic cores are same-acquisition spatial challenges with within-scene shared calibration. They are regression anchors, not ten independent scenes or Stage 7 generalization evidence.
- Within-acquisition spatial holdout is **conditionally_ready** when it uses the frozen 8.13 km own-core buffer and same-acquisition calibration lit pixels.
- Leave-acquisition-out is **insufficient_evidence**: two acquisitions cannot form nonempty train/validation/test collections. No random pixel split, nearby unbuffered block, or composite may fill the missing role.

## Residual, support, and unit-level metrics

The only residual name and definition are:

```text
residual = rho_hat - rho_obs
```

It is a specified-baseline **model–observation residual**, not a true inversion error, albedo error, or proof of a physical illumination mechanism.

For every `acquisition × ROI × band` unit, report at least:

- `supported_pixel_count`;
- `base_valid_land_count`;
- `support_coverage = supported_pixel_count / base_valid_land_count`;
- signed bias;
- MAE;
- P90 absolute residual;
- `unsupported_by_direct_only_count`;
- QA and geometry validity status;
- alpha source: `within_acquisition_calibration` or `transferred_training_only`.

Coverage’s denominator is all `base_valid_land` pixels. `unsupported_by_direct_only` remains in that denominator and does not become a low-error success. Only supported pixels contribute to supported-residual metrics for this direct-only baseline. No continuous confidence curve, sigmoid ranking, soft-weight order, or risk–coverage curve is defined here.

## Aggregation and statistical boundary

1. Compute metrics inside each evaluation unit first.
2. Summarize unit metrics descriptively without pixel pooling as a replacement for unit-level results.
3. Give acquisitions equal weight in acquisition-level summaries.
4. Use only medians, ranges, and unit-level tables at the current sample size.
5. Do not report pixel-level p-values, pixel-level confidence intervals, effective sample sizes, or statistical-significance claims.
6. Same-acquisition folds, shared-calibration folds, and adjacent ROIs must not be called independent replicates.

## Readiness gates before future execution

### Within-acquisition spatial holdout

Status: **conditionally_ready**.

Required before an execution is admitted:

- a formal Stage 7 ROI protocol with projected/geographic boundaries and non-overlap checks;
- designated calibration and holdout ROIs;
- a recorded 8.13 km calibration-to-complete-holdout-core buffer;
- an approved minimum calibration-lit support threshold;
- unit-level reporting with the support boundary in this protocol.

### Leave-acquisition-out

Status: **insufficient_evidence**.

Required before an execution is admitted:

- at least three verified, single-date acquisitions occupying nonempty train, validation, and test groups;
- product ID, sensing timestamp, WRS, sensor/collection/processing level, sun geometry, CRS/grid, QA, terrain geometry, observation date, and ROI/split provenance linked per acquisition;
- the frozen transferred-alpha policy applied without test-acquisition refitting;
- reporting of acquisition count, independent unit count, and remaining domain limitations.

## C5-D3 boundary and consistency

C5-D3 remains a regression anchor. Its `WARNING` result, its three-method comparison, its 10 folds, its shared calibration, and its incomplete residual spatial diagnostics cannot be promoted to a Stage 7 generalization conclusion. This protocol is consistent with `docs/stage7_0/data_gap_report.md` and `docs/stage7_0/leakage_audit.md`: no evidence gap is hidden by a pixel split or a composite, and data insufficiency is a reportable result rather than a reason to lower the protocol.
