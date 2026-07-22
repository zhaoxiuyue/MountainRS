# Stage 7.0｜baseline specification

## Status and scope

This file freezes the sole pre-repair weak-closure baseline for Stage 7.0. It is a specification, not an experiment result, fitted parameter set, mechanism comparison, or generalization claim.

- **Baseline identity:** `direct_only_hard_mask_v1`
- **Applicable bands:** B4 and B5, fitted and reported independently.
- **Current data boundary:** the only verified acquisitions are `LC08_130038_20230813` and `LC08_130038_20230101`. They are C5-D3 regression anchors, not sufficient Stage 7 acquisition-level generalization evidence.
- **Contract guard at freeze:** project revision `51`; route revision `2`; Stage 7.0 Node Contract revision `1`.

## Frozen forward model and support boundary

For every pixel in a permitted evaluation unit:

```text
mu      = max(cos_i, 0)
rho_hat = alpha × mu
0 <= alpha <= 1
```

The model contains no intercept, diffuse term, soft weight, pixelwise correction, or free residual term. `soft_weight_k30` remains a historical sensitivity reference only. `bounded_scene_constant_diffuse` remains a repair candidate only. Neither is a component of `direct_only_hard_mask_v1`.

The canonical support proxy is binary:

```text
supported                    := cos_i > 0.1
unsupported_by_direct_only   := cos_i <= 0.1
```

`unsupported_by_direct_only` remains in the complete `base_valid_land` coverage denominator and must never be counted as a low-error success. It is excluded from this baseline’s supported-residual success set. Reliability is only the binary label `supported` / `unsupported`; this baseline has no sigmoid confidence, continuous reliability score, or risk–coverage ranking/curve.

## Frozen alpha estimator

For each permitted calibration unit and band, use only calibration lit pixels (`cos_i > 0.1`) to compute:

```text
alpha_raw = sum(mu_i × rho_obs_i) / sum(mu_i²)
alpha     = clip(alpha_raw, 0, 1)
```

The calibration set must be nonempty, finite, and have a strictly positive denominator. A unit with a zero denominator, non-finite estimator, or insufficient approved calibration-lit support is labeled `unsupported_calibration`; it receives no default alpha, imputation, intercept, diffuse substitution, or holdout-derived repair. Before any future execution, its execution plan must state the minimum calibration-lit support threshold; absent such an approved threshold, the unit remains `unsupported_calibration` rather than being silently scored.

## Alpha regime A — within-acquisition spatial holdout

For each `acquisition × band`:

1. Use only pre-specified calibration ROIs from the same acquisition and only their calibration lit pixels to estimate alpha.
2. Exclude the complete holdout geographic core, its buffer, and all holdout observations from alpha fitting, threshold selection, model selection, and stop-condition selection.
3. Maintain a minimum calibration-to-complete-holdout-core distance of 8.13 km.
4. Report each spatial holdout as a same-acquisition challenge, not as an independent acquisition replicate.
5. Cores that share calibration support remain separate descriptive units; they must not be pooled as independent observations.

The current C5-D3 cores make this regime **conditionally_ready**: each own-core buffer is valid, but the cores are regression-reference geometry with shared calibration, and a formal Stage 7 ROI protocol must be used before execution.

## Alpha regime B — leave-acquisition-out

The test acquisition’s reflectance observations must not participate in alpha fitting, alpha selection, threshold selection, model selection, or stop-condition selection.

The frozen transfer policy is applied independently to each band:

1. For each `training acquisition × calibration ROI × band`, calculate constrained alpha using the estimator above.
2. Within an acquisition, take the unweighted median of its valid calibration-ROI alphas.
3. Take the unweighted median of those acquisition-level alphas across training acquisitions.
4. The result is the one frozen `transferred_alpha` for the band.
5. Apply that value unchanged to validation and test acquisitions.
6. Each acquisition has equal weight; neither pixel count nor ROI area may weight either median.
7. If the training set contains no valid acquisition-level alpha for a band, label that band `unsupported_transfer`.
8. Never re-fit alpha on a validation or test acquisition.

This is a transparent weak-baseline transfer policy. It does not assert that alpha is physically sufficient across dates, domains, illumination, terrain, land cover, or sensors.

## Current-evidence boundary

`LC08_130038_20230813` and `LC08_130038_20230101` are verified single-date product identities, share WRS path/row 130/38, and have missing sensing-time fields in the formal metadata. The 10 C5-D3 cores are same-acquisition buffered spatial challenges. They are not ten independent scenes or statistical repetitions.

Within-acquisition spatial holdout is conditionally ready. Leave-acquisition-out is `insufficient_evidence`: only two verified acquisitions exist, so train/validation/test cannot all be nonempty, and no C5-D3 result may be upgraded to Stage 7 generalization evidence. See `docs/stage7_0/data_gap_report.md` and `docs/stage7_0/leakage_audit.md` for the identity and leakage evidence.

## Prohibitions

- Do not treat a multi-date composite as a single-date acquisition.
- Do not use random pixel splits, adjacent unbuffered blocks, pixel-level p-values, pixel-level confidence intervals, or inflated effective sample sizes.
- Do not replace missing support with a default alpha or use an unsupported pixel as a supported residual success.
- Do not use this specification to rerun C5-D3, compare the three C5-D3 methods, or claim that direct-only illumination, diffuse light, or any other mechanism has been scientifically validated.
