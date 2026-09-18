# MountainRS — A Physical Foundation for Mountain Remote Sensing

[中文](README.md) · [How three AI clients shared project state](docs/one-tree-three-clients.en.md)

## Start with one result

Compare three terrain-radiation treatments at each method's maximum pixel coverage. In band B4, `hard` has the largest error: **0.0768**. Compare them at the **same 80% coverage**, and the gap nearly disappears: **0.0770 / 0.0776 / 0.0775**.

![Original MountainRS result figure, with its English data table immediately below](stages/stage6_5_real_landsat_observation_stress_test/reports/xiaohongshu/post_03/04_coverage_comparison.png)

The original figure is in Chinese. Its recorded values, in English:

| Band | Comparison | hard | soft (k=30) | diffuse |
|---|---|---:|---:|---:|
| B4 | Each method at maximum coverage | 0.0768 | 0.0647 | 0.0647 |
| B4 | Common 80% coverage | 0.0770 | 0.0776 | 0.0775 |
| B5 | Each method at maximum coverage | 0.0675 | 0.0654 | 0.0622 |
| B5 | Common 80% coverage | 0.0703 | 0.0714 | 0.0690 |

Maximum coverage is 87.2% for `hard` and 100% for the other two methods. Values are median fold MAE over five spatial folds for acquisition `shadow_risk_b`; those folds are not independent statistical replicates. This table translates the [original Chinese figure](stages/stage6_5_real_landsat_observation_stress_test/reports/xiaohongshu/post_03/04_coverage_comparison.png), using the committed [result summary](stages/stage6_5_real_landsat_observation_stress_test/evidence/stage6_5_3_b/c5_d3_35789933202effad/result_summary.json) and [risk/coverage table](stages/stage6_5_real_landsat_observation_stress_test/evidence/stage6_5_3_b/c5_d3_35789933202effad/risk_coverage.csv).

A method can reduce its error by answering for fewer pixels. Error without coverage is not a like-for-like comparison.

This repository investigates surface-state inference in mountainous terrain, where slope orientation changes direct illumination, mountains cast distant shadows, and the same surface can have very different brightness under different incidence angles. The approach is to **fix the criteria for evidence first, then see which conclusions survive**.

Most conclusions are **negative results**.

## What you can reuse

| Material | Where to look |
|---|---|
| Negative-result cases: three additive optical terms rejected by preregistered thresholds, and a risk-ranking proxy with the wrong direction | [Stage 7.6](stage7_real_weak_closure/stage7_6_optical_operator/) · [Stage 7.4](stage7_real_weak_closure/stage7_4_residual_reliability/) |
| A way to separate observation validity and evaluation support from model accuracy | [Validity/support schema](stage7_real_weak_closure/stage7_1_observation_stack/configs/validity-support-schema-v1.json) |
| Identifiability checks, including their limits: three of six checks return `not_applicable` for the single-parameter model | [Stage 7.5 report — Chinese](stage7_real_weak_closure/stage7_5_identity_gauge/reports/identity-gauge-report-v1.md) |
| Data organization for cross-domain evaluation: five mountain domains that differ from the baseline, 891 eligible observations and 603 temporally matched Sentinel-2 references, with independence and leakage audit rules | [Stage 7.8](stage7_real_weak_closure/stage7_8_multidomain_evidence/) |
| A workflow that freezes criteria before inspecting results: SHA-256 identities, timestamped freeze receipts and explicit flags for post-result changes | [Stage 7.4 evidence](stage7_real_weak_closure/stage7_4_residual_reliability/evidence/) |
| Architecture documents v3.1–v3.3, with SHA-256 hashes | [PDF releases — Chinese](docs/releases/) |

Historical stage reports are mainly in Chinese. Structured artifacts retain their original keys, identifiers and verdicts; translating this entry page does not alter those artifacts.

## Three cases

### 1. I expected sky diffuse light to explain shaded slopes

**Initial idea.** Shaded slopes still receive diffuse skylight. Add a term such as `beta_v · v_sky` to the observation operator.

**Test.** Freeze the candidate set, comparisons, ablation order, metrics, thresholds and tie rules before reading residuals. Run after cross-review: 180 units = 18 acquisitions × 2 bands × 5 folds.

**Finding.** All three candidates were `unsupported_by_evidence`. Median improvement was **+0.06%**, against a frozen threshold of **5%**. The median absolute `beta_v` was **0.82 times** the baseline MAE, while the main parameter alpha shifted by **19.9%**.

**Consequence.** The operator remains the minimal `rho_hat = alpha · mu`. The three additions moved from untested ideas to tested candidates without evidential support.

[Report — Chinese](stage7_real_weak_closure/stage7_6_optical_operator/reports/optical-operator-report-v1.md) · [Per-unit results](stage7_real_weak_closure/stage7_6_optical_operator/outputs/ablation-unit-table-v1.json) · [Verdicts](stage7_real_weak_closure/stage7_6_optical_operator/outputs/verdict-table-v1.json)

### 2. I expected MODIS land-cover labels to characterize candidate regions

**Initial idea.** Use `ee.Reducer.mode()` to identify each candidate region's dominant IGBP class. The baseline returned “savanna,” which looked implausible for a high mountain region. Two findings followed: MODIS was unreliable there, and another candidate was predominantly wetland.

**Test.** Query a frequency histogram to substantiate the second finding.

**Finding.** The histogram disagreed with the mode. In this workflow, the reducer after resampling did not correctly identify the dominant discrete class. “Savanna” accounted for only **1.1%** of the baseline; the actual dominant class was grassland at **46.1%**. Both findings rested on the faulty result.

**Consequence.** Both findings were withdrawn. The bytes of `v1` were retained, and `v2` recorded the withdrawal. Otherwise, the owner would have been asked to decide from two false factual premises, both pointing toward changing frozen criteria.

[v1 — retained erroneous findings](stage7_real_weak_closure/stage7_8_multidomain_evidence/evidence/screening-findings-v1.json) · [v2 — withdrawals](stage7_real_weak_closure/stage7_8_multidomain_evidence/evidence/screening-findings-v2.json)

### 3. I assumed a subset could not have a larger IQR than the full set

**Initial idea.** An admission criterion required the sky-view factor's interquartile range (IQR) within each fold, but that stage produced no fold structure. A region-level measurement was substituted. The argument was that a fold's training support is a subset of the region, so its IQR could not exceed the region's IQR. A region-level value of 0.0655 < 0.10 was then used to rule out the fold-level criterion.

**Test.** A separate review examined the argument line by line before publication.

**Finding.** The claimed monotonicity is false. With the usual inclusive, linearly interpolated quartiles, eight zeros and two ones have IQR 0; a subset of two zeros and two ones has IQR 1.

**Consequence.** The criterion changed from “not satisfied” to **“not established.”** The overall gate verdict weakened from `not_warranted` to `not_established`. The measurement was not the error; the inference from it was.

[Defect record](stage7_real_weak_closure/stage7_8_multidomain_evidence/evidence/requalification-gate-g1-defect-v1.json). The original report and script remain unchanged; a separate, append-only record withdraws the inference.

## Check a result yourself

The first case can be inspected without running Earth Engine. Under [`stage7_real_weak_closure/stage7_6_optical_operator/`](stage7_real_weak_closure/stage7_6_optical_operator/), read:

| File | Purpose |
|---|---|
| [Verdict table](stage7_real_weak_closure/stage7_6_optical_operator/outputs/verdict-table-v1.json) | Final status and reasons for four candidates, including the baseline |
| [Ablation unit table](stage7_real_weak_closure/stage7_6_optical_operator/outputs/ablation-unit-table-v1.json) | Fitted results for 180 evaluation units |
| [Frozen config](stage7_real_weak_closure/stage7_6_optical_operator/configs/optical-operator-config-v1.json) | Thresholds and `verdict_rules` |
| [Result audit](stage7_real_weak_closure/stage7_6_optical_operator/outputs/result-audit-v1.json) | Y1–Y11 checks and negative controls |

The verdict follows the config's rules. The reporting unit is `acquisition × band × fold`, with `equal_per_acquisition_band` weighting, **not pixel-count weighting**, so scenes with larger support do not dominate the result. Qualification requires all five conditions:

1. Median relative MAE improvement over baseline ≥ **0.05**.
2. Consistent direction in at least **4 of 5** folds.
3. Parameter-boundary hits in no more than **0.10** of units.
4. Gradient and numerical stability checks pass.
5. The candidate passes `support_gate`. Two-parameter models additionally require `v_sky` IQR ≥ **0.05** within fold training support; otherwise the result is `unsupported`, rather than forcing a fit in a practically unidentifiable setting.

Coverage must also be comparable within **0.001**. A unit outside that tolerance is excluded from the comparison set and registered as `coverage_mismatch`. The frozen config is authoritative; this is a reading guide.

Most other stages' large `outputs/`, mainly GeoTIFFs, are not in Git. Early generated note drafts under `obsidian_drafts/` are also excluded. Historical references to those paths remain in reports; manifests and SHA-256 hashes in `evidence/` identify the artifacts. **The public repository supports inspection of selected evidence, but not a complete end-to-end rerun.**

## Where the work stopped

The physical chain is terrain geometry → illumination and visibility → observation operator → state inversion. The main line currently stops at the **third layer**.

**The owner deliberately stopped work on September 10, 2026.** The PF3 project lifecycle is `abandoned`. The next stage requires both a qualified observation operator and an activated state; upstream stages returned empty sets after normal execution and their respective fail-closed audits. Those are valid negative results, not workflow failures.

The downstream stage therefore found that it could not begin. It did not relabel the upstream work as failed merely because the required inputs were absent. [Activation preflight](stage7_real_weak_closure/stage7_9_l3_closed_loop/evidence/activation-preflight-manifest-v1.json).

## How the project was coordinated

Project state, routes, nodes, rules and criteria were maintained in **PF3**, an MCP server I built for multiple AI clients working against shared project state. [PF3 Showcase](https://github.com/zhaoxiuyue/pf3-showcase) provides the design notes, selected real records and an independent protocol example. The complete implementation remains private.

The [retrospective](docs/one-tree-three-clients.en.md) records three client labels—`claude-code`, `oauth:chatgpt` and `codex`—writing to one project tree. Version checks rejected stale writes; receipts recorded changes and reversals. Its **80 days and 93 commits** describe the period from June 22 through the September 10 stopping point, not the repository's current totals.

The same records preserve the IQR correction: withdrawing the inference did **not** remove a separate downstream block. Node and receipt IDs in the retrospective refer to the private PF3 service. Public research files and selected tree extracts can be inspected; the full receipt history cannot be queried publicly.

## Repository map and research scope

```text
stages/                    Self-contained research work packages
stage7_real_weak_closure/   Frozen historical evidence; corrections are append-only
docs/                      Architecture PDFs, English entry pages and retrospective
_ops/                      One-time organization records and before/after hash inventories
```

“Weak closure” describes running a chain on real observations without claiming cross-domain generalization. The directory name is retained because frozen contracts and auditors refer to its paths.

- **Stages 1–6 use toy models:** real terrain with synthetic observations. Their conclusions do not transfer directly to real observations.
- Real observations begin at Stage 6.5, whose final status is `BLOCKED`: the single-scene setup could not provide a spatially independent holdout.
- Conclusions concern one region of interest, Minshan, unless stated otherwise. Spatial folds are not independent samples.
- Source datasets are Landsat 8/9 C2 L2SR, Sentinel-1 GRD, Sentinel-2 SR and SRTM, accessed through Google Earth Engine.
- “Owner,” “executor” and “audit” describe roles within this single-author project, not a human research team.

## Author and license

I am Elara. I proposed, designed and directed this project: defining the questions, what counts as evidence, the criteria and stopping conditions, and when insufficient evidence should stop further work. The recorded rules also expose my own post-result changes. Questions about any conclusion are welcome; author/contact details are in the [Chinese README](README.md#关于作者).

[CC BY 4.0](LICENSE). Attribute this repository when reusing its methods, criteria, data organization or conclusions.
