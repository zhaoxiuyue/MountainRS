# Stage 7.0｜acquisition / ROI leakage audit

## Scope and result

This audit applies the Stage 7.0 Node Contract to the verified C5-D3 data and to the noncanonical candidate directory. It does not run a baseline, fit alpha, compare mechanisms, or create a continuous risk–coverage claim.

**Overall readiness:**

- `within-acquisition spatial holdout`: **conditionally_ready** as a future, per-acquisition, buffered regression protocol.
- `leave-acquisition-out`: **insufficient_evidence**.

The control variables are the verified acquisition identities and the formal C5-D3 core geometry. A pixel, a same-scene fold, a shared-calibration fold or an adjacent core is not an independent statistical replicate.

## Acquisition leakage

| check | finding | consequence |
|---|---|---|
| acquisition identity | Two verified Landsat 8 C2 T1 L2 products exist: Clean A (`LC08_130038_20230813`) and Shadow-risk B (`LC08_130038_20230101`). | They are two distinct acquisitions, not ten scenes. |
| sensing time | Formal metadata gives dates but no sensing timestamp. | Timestamp-level linkage is missing; it must be required in a future acquisition catalog. |
| runner behavior | `stage6_5_3_b_experiment.py` fits parameters independently for each `scene × band × fold`. | C5-D3 contains no leave-acquisition-out fitted/frozen-alpha result. |
| test-data isolation | C5-D3 keeps each fold’s holdout out of that fold’s fit, but it does not define a train-acquisition → validation-acquisition → test-acquisition alpha transfer. | A future test acquisition must never refit/select alpha; the missing transfer rule blocks a generalization claim. |
| composite substitution | `stage7_real_weak_closure/` explicitly discusses multi-date composites, while its directory contains no exported observation stack. | A composite must not be treated as a single-date physical observation; it supplies no acquisition identity for this audit. |

The two formal raster domains have a nearest-bounds separation of 66,670.152 m in EPSG:32648. That spatial separation does not manufacture a third acquisition or separate temporal from geographic/domain shift.

## ROI geometry and calibration overlap

The C5-D3 manifest defines five Clean A `lit_control` and five Shadow-risk B `combined_risk_stress` geographic cores. Within each scene, cores are pairwise non-overlapping. For every fold, calibration is at least 8,130 m from that fold’s complete square geographic core. The 8,130 m rule is therefore a **fold-internal train-to-own-holdout** guarantee, not a claim that all cores are mutually 8,130 m apart.

| acquisition / group | formal cores | core overlap | minimum core-to-core gap | pairs with core gap ≥ 8,130 m | pairwise shared calibration | shared-calibration range (pixels) | interpretation |
|---|---:|---|---:|---:|---:|---:|---|
| Clean A / `clean_a_lit_control` | 5 | none | 4,320 m | 7 / 10 | 10 / 10 | 23,743–285,696 | valid buffered holdout challenges; not five independent ROIs |
| Shadow-risk B / `shadow_risk_b_combined_risk` | 5 | none | 0 m (touching boundaries) | 3 / 10 | 10 / 10 | 9,702–41,003 | valid fold-internal buffers; cores and calibration are not independent repetitions |

The four required distinctions are therefore:

1. **Non-overlapping geographic cores:** true for the ten formal C5-D3 cores.
2. **Calibration overlap:** true for every within-scene pair. A shared-calibration pair must be reported separately or descriptively, never pooled as independent evidence.
3. **Same-acquisition spatial challenge:** all five cores within a group are this category. Their holdout pixels are spatially buffered from their own calibration set but arise from the same acquisition.
4. **Independent acquisition / independent ROI:** only two acquisition identities exist, and no formally admitted Stage 7 ROI set exists. Neither the ten C5-D3 folds nor the noncanonical candidate plans satisfy this category by themselves.

## Pixel pseudoreplication audit

- `base_valid_land`, shadow, near-zero and lit counts are per-pixel support measurements. They establish denominator and data availability, not sample size for inferential tests.
- C5-D3 itself limits results to fold-level descriptive summaries and forbids pixel-level p-values, confidence intervals or effective-sample-size inflation. The Stage 7.0 contract retains that prohibition.
- Clean A contributes 0 shadow pixels and 3 near-zero pixels in the verified full acquisition; it cannot be relabeled as a shadow-risk repeat.
- Shadow-risk B contains 4,063 shadow and 4,559 near-zero base-valid-land pixels, but those pixels remain measurements inside one acquisition, not thousands of independent acquisitions.
- The 10 C5-D3 folds may be used as regression-reference geometry only. They do not justify a pooled pixel p-value, an acquisition-level confidence interval, or a mechanism ranking.

## Regime readiness and stop conditions

| regime | status | conditions already evidenced | remaining blocker / boundary |
|---|---|---|---|
| within-acquisition spatial holdout | **conditionally_ready** | Verified B4/B5/QA_PIXEL/`cos_i` grids; base_valid_land partitions; five non-overlapping cores per acquisition; own-core 8,130 m buffer. | Freeze a Stage 7 ROI protocol before execution; use only same-acquisition calibration lit pixels for alpha and keep holdout ROI out of fit. Do not interpret shared-calibration folds as independent repeats. |
| leave-acquisition-out | **insufficient_evidence** | Two distinct verified dates/products. | Need an acquisition catalog with at least train/validation/test identities and a predeclared frozen alpha/transfer rule. No test reflectance may refit alpha; random-pixel or adjacent-block substitutes are prohibited. |

The noncanonical `stage7_real_weak_closure/` folder creates no additional readiness: it has no verified scene table, single-date metadata, exported B4/B5/QA_PIXEL rasters, terrain geometry, ROI vectors or split record. It is recorded only as a candidate source, not admitted as an input alias.

## Audit verdict

There is no evidence of a hidden acquisition leak in the two formal C5-D3 scene identities, but there is an unavoidable **independence gap** for Stage 7 generalization: only two acquisitions and shared-calibration spatial folds are available. The appropriate response is to retain the data-gap verdict, not to add random pixel splits, relax the 8.13 km rule, treat a composite as a date-specific observation, or rerun C5-D3 as if it were a Stage 7 comparison.
