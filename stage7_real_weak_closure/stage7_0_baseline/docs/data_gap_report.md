# Stage 7.0｜scene / ROI inventory 与 data-gap report

## 结论

**data-gap verdict：insufficient evidence for leave-acquisition-out；within-acquisition spatial holdout 为 conditionally_ready。**

本报告只执行 Stage 7.0 的 First Action：盘点身份、几何和可执行性。它不拟合 `direct_only_hard_mask_v1`，不运行正式实验，不生成 `stage_7_0_baseline_spec` 或 `stage_7_0_evaluation_protocol`，也不把 C5-D3 的机制压力测试升级为泛化结论。

本次盘点对应的 PF2 guard 为 project revision `51`、route revision `2`、Stage 7.0 Node Contract revision `1`。所有位置均为项目内相对路径、稳定 acquisition identity 或投影坐标；未记录 Workspace Locator。

## 审计来源与身份边界

- `architecture_source`：`docs/architecture.md`。它要求各节点只声称实际检验的机制，且明确 Stage 6.5.3-B 不是完整 L0–L5 验证。
- `c5_d3_approved_contract`：`stage6_5_real_landsat_observation_stress_test/reports/stage6_5_3_b_method_contract_proposal.md`。
- `stage_6_5_3_b_config`：`stage6_5_real_landsat_observation_stress_test/configs/stage6_5_3_b.yaml`。
- `c5_d3_runner`：`stage6_5_real_landsat_observation_stress_test/scripts/stage6_5_3_b_experiment.py`。
- `c5_d3_experiment_report` 与 `c5_d3_evidence_manifest`：C5-D3 正式结果和 manifest。
- 现有 `clean_a_*` 与 `shadow_risk_b_*` aliases：唯一已核验的本地 B4、B5、QA_PIXEL、metadata 与 `cos_i` 来源。

`stage7_real_weak_closure/` 是未跟踪的 **noncanonical candidate**。其中只有 GEE 脚本、计划、草案和策略文档；没有导出的 raster、metadata CSV、候选场景表或 ROI 矢量。目录名、脚本中建议的日期/ROI，均不构成正式 Stage 7 acquisition 或 ROI identity。

## acquisition inventory

| acquisition key | stable product / scene identity | date / time | sensor / collection / level | WRS | solar geometry | identity status |
|---|---|---|---|---|---|---|
| Clean A | `LANDSAT/LC08/C02/T1_L2/LC08_130038_20230813` | 2023-08-13; sensing time **missing** from the formal CSV | Landsat 8 (`LC08`); Collection 2, Tier 1, Level 2 SR | 130 / 38 | azimuth 123.53706884°; elevation 62.94220054° | **verified** product, date, WRS and solar fields; time field missing |
| Shadow-risk B | `LANDSAT/LC08/C02/T1_L2/LC08_130038_20230101` | 2023-01-01; sensing time **missing** from the formal CSV | Landsat 8 (`LC08`); Collection 2, Tier 1, Level 2 SR | 130 / 38 | azimuth 155.66673554°; elevation 31.1368308° | **verified** product, date, WRS and solar fields; time field missing |

The product identities, dates, WRS and solar fields come from the two formal metadata CSVs, not from filenames. The two acquisitions share WRS path/row but have distinct product identities and dates. Their date separation is 224 days. Neither formal metadata CSV contains a sensing-time field, so time-level identity is explicitly incomplete rather than inferred.

### Raster/header and support inventory

| acquisition | B4/B5/QA_PIXEL/`cos_i` source aliases | header consistency | CRS / shape / resolution | projected raster bounds (m, EPSG:32648) | base_valid_land | shadow | near-zero | lit supported |
|---|---|---|---|---|---:|---:|---:|---:|
| Clean A | `clean_a_b4`, `clean_a_b5`, `clean_a_qa_pixel`, `clean_a_metadata`, `clean_a_cos_i` | CRS, bounds, shape, resolution and affine transform all match | EPSG:32648; 746 × 645; 30 m | [377670, 3419010, 397020, 3441390] | 469,534 | 0 | 3 | 469,531 |
| Shadow-risk B | `shadow_risk_b_b4`, `shadow_risk_b_b5`, `shadow_risk_b_qa_pixel`, `shadow_risk_b_metadata`, `shadow_risk_b_cos_i` | CRS, bounds, shape, resolution and affine transform all match | EPSG:32648; 752 × 650; 30 m | [292230, 3451230, 311730, 3473790] | 102,222 | 4,063 | 4,559 | 93,600 |

Counts were recomputed from the contract’s canonical rules: QA_PIXEL bits 0–5 clear, finite B4/B5/`cos_i`, B4/B5 in [-0.05, 1.0], and QA water bit 7 excluded from land metrics. Shadow is `cos_i <= 0`; near-zero is `0 < cos_i <= 0.1`; lit is `cos_i > 0.1`. The three partition counts sum to base_valid_land for both acquisitions. Clean A has 2,136 QA-water pixels within base-valid; Shadow-risk B has 137,965; neither water subset enters the land denominator.

## ROI / geographic-core inventory

The only formal spatial regions are the C5-D3 buffered geographic cores. They are **regression-reference cores**, not already-approved Stage 7 ROIs. Their WGS84 footprints below are transforms of the approved EPSG:32648 core bounds, not filenames or hand-drawn labels.

| ROI / core identity | acquisition | domain label | projected bounds [left,bottom,right,top] m | WGS84 bbox (SW → NE) | holdout land | calibration land | shadow / near-zero / lit in holdout |
|---|---|---|---|---|---:|---:|---|
| `stage_6_5_3_b_clean_a_lit_control_01` | Clean A | lit_control | [390150,3423630,396390,3429870] | 103.85007,30.94100 → 103.91475,30.99786 | 43,262 | 176,924 | 0 / 0 / 43,262 |
| `stage_6_5_3_b_clean_a_lit_control_02` | Clean A | lit_control | [377670,3439470,379590,3441390] | 103.71754,31.08266 → 103.73744,31.10018 | 3,600 | 376,431 | 0 / 0 / 3,600 |
| `stage_6_5_3_b_clean_a_lit_control_03` | Clean A | lit_control | [377670,3419010,379590,3420930] | 103.72001,30.89809 → 103.73987,30.91561 | 3,702 | 375,702 | 0 / 0 / 3,702 |
| `stage_6_5_3_b_clean_a_lit_control_04` | Clean A | lit_control | [395100,3439470,397020,3441390] | 103.90024,31.08435 → 103.92017,31.10184 | 3,694 | 376,137 | 0 / 0 / 3,694 |
| `stage_6_5_3_b_clean_a_lit_control_05` | Clean A | lit_control | [379590,3426990,385830,3433230] | 103.73915,30.97028 → 103.80378,31.02719 | 42,994 | 102,509 | 0 / 0 / 42,994 |
| `stage_6_5_3_b_shadow_risk_b_combined_risk_01` | Shadow-risk B | combined_risk_stress | [295110,3467550,301350,3473790] | 102.84670,31.32434 → 102.91100,31.38169 | 14,225 | 44,141 | 852 / 1,344 / 12,029 |
| `stage_6_5_3_b_shadow_risk_b_combined_risk_02` | Shadow-risk B | combined_risk_stress | [307890,3451230,311730,3455070] | 102.98407,31.17936 → 103.02363,31.21461 | 8,205 | 69,005 | 265 / 413 / 7,527 |
| `stage_6_5_3_b_shadow_risk_b_combined_risk_03` | Shadow-risk B | combined_risk_stress | [308370,3470430,311730,3473790] | 102.98543,31.35257 → 103.02010,31.38342 | 3,148 | 66,967 | 280 / 318 / 2,550 |
| `stage_6_5_3_b_shadow_risk_b_combined_risk_04` | Shadow-risk B | combined_risk_stress | [302790,3460350,307590,3465150] | 102.92879,31.26075 → 102.97825,31.30483 | 5,043 | 22,479 | 263 / 381 / 4,399 |
| `stage_6_5_3_b_shadow_risk_b_combined_risk_05` | Shadow-risk B | combined_risk_stress | [301350,3466110,307590,3472350] | 102.91253,31.31244 → 102.97686,31.36975 | 16,622 | 38,397 | 500 / 495 / 15,627 |

Every core passes its own frozen calibration-to-complete-core buffer of 8,130 m (271 pixels). This is not equivalent to pairwise independent ROIs: all five cores within each acquisition share calibration support. See `docs/stage7_0/leakage_audit.md` for pairwise overlap and distance results.

## Assessment of the two evaluation regimes

| regime | status | evidence | exact limitation |
|---|---|---|---|
| within-acquisition spatial holdout | **conditionally_ready** | Both verified acquisitions have five non-overlapping C5-D3 cores; each has base_valid_land in calibration and holdout and passes its own 8,130 m calibration-to-core buffer. Clean A supplies lit control only; Shadow-risk B supplies shadow and near-zero support. | These are C5-D3 regression-reference cores with shared calibration, not independent replicates; Stage 7 has no frozen ROI protocol yet. A later Stage 7 execution must fit alpha only on the same acquisition’s calibration lit pixels and must not bring holdout pixels into fitting. |
| leave-acquisition-out | **insufficient_evidence** | Two verified single-date acquisitions exist and have distinct product identities/dates. | Two acquisitions cannot form train/validation/test; the C5-D3 runner fits per scene×band×fold and provides no frozen cross-acquisition alpha transfer rule. The acquisitions also occupy separated raster domains (nearest raster-bound distance 66,670.152 m), so temporal and spatial/domain shifts cannot be disentangled. Testing cannot yet demonstrate acquisition-level generalization. |

No status is upgraded by pixels, the ten cores, or the C5-D3 fold count. Pixels are measurements inside an acquisition × ROI × band unit; the five folds in a scene share calibration support and must not become five statistically independent regions.

## Minimum data and protocol gaps

1. Supply a verified single-date acquisition catalog with product ID, sensing timestamp, WRS, collection/level, solar geometry, CRS/grid and B4/B5/QA_PIXEL/terrain-geometry provenance for additional acquisitions. A minimal leave-acquisition-out design requires separately identified training, validation and test acquisitions; two scenes do not provide those roles.
2. Define a formal Stage 7 ROI protocol: non-overlapping projected and geographic polygons, domain labels, ownership of calibration versus holdout pixels, 8.13 km buffer rule, and an explicit statement of which ROIs are merely descriptive challenges.
3. Predeclare the leave-acquisition-out alpha transfer rule. A test acquisition’s reflectance must not refit or choose alpha; no such transfer rule exists in the C5-D3 materials.
4. Retain `base_valid_land`, support/unsupported accounting and QA/solar/terrain/CRS/date linkage per acquisition. Do not substitute random pixels, adjacent unbuffered blocks, or a multi-date composite for these missing identities.
5. The noncanonical `stage7_real_weak_closure/` materials may inform a future acquisition schema, but exported data and a reviewed admission decision are required before any planned alias is created or any candidate becomes a formal Stage 7 input.

Data insufficiency is a result of this First Action, not a failure of the Stage 7.0 node. C5-D3 remains a regression anchor only; its WARNING conclusion and its mechanism comparison are not reused as Stage 7 generalization evidence.
