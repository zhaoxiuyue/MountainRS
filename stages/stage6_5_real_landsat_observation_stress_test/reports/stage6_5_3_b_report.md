# Stage 6.5.3-B｜First Action：规范掩膜与空间隔离预检

- **预检结论：** `BLOCKED`
- **执行边界：** deterministic preflight only；未拟合三种机制、未评分 holdout、未计算 residual/risk–coverage、未形成最终实验结论。
- **Architecture basis：** docs/architecture.md V3。

## 冻结口径

- `base_valid`：QA_PIXEL bits 0–5 均为 0，B4/B5/cos_i 均 finite、非 nodata，且 B4/B5 都在 [-0.05, 1.0]。
- 分区：`shadow=cos_i<=0`、`near_zero=0<cos_i<=0.1`、`lit=cos_i>0.1`；完整性在 `base_valid` 上验证。
- water bit 7 单独统计，并从主要 land 指标和空间相关估计排除；更高 QA confidence bits 本轮明确不作为 hard exclusion。
- `soft_weight` k=30 只是继承的经验基线；k={15,30,60} 留给同一机制的后续敏感性检查。bounded diffuse 的数值界限尚未裁决，只能由 calibration-only 证据冻结。

## A/B 规范统计

| Scene | base_valid | base_valid_land | water in base_valid | shadow land | near_zero land | lit land | partition integrity |
|---|---:|---:|---:|---:|---:|---:|---|
| clean_a | 471670 (0.980256) | 469534 (0.975817) | 2136 | 0 (0.000000) | 3 (0.000006) | 469531 (0.999994) | PASS |
| shadow_risk_b | 240187 (0.491381) | 102222 (0.209128) | 137965 | 4063 (0.039747) | 4559 (0.044599) | 93600 (0.915654) | PASS |

## Grid / nodata 检查

- **clean_a**：CRS=EPSG:32648，shape=[746, 645]，resolution=[30.0, 30.0]，主输入 grid=PASS。
- **shadow_risk_b**：CRS=EPSG:32648，shape=[752, 650]，resolution=[30.0, 30.0]，主输入 grid=PASS。

## 空间相关范围与候选隔离

### clean_a
- cos_i: reliable range=806.250 m；tail sill=0.0025733258。
- b4: reliable range=2015.625 m；tail sill=0.0010808709。
- b5: reliable range=1612.500 m；tail sill=0.0039230642。
- candidate blocks: **BLOCKED** — 独立候选 blocks 不足：calibration=1, holdout=0, minimum=2。
### shadow_risk_b
- cos_i: reliable range=2437.500 m；tail sill=0.10595167。
- b4: reliable range=8125.000 m；tail sill=0.01680663。
- b5: reliable range=7718.750 m；tail sill=0.022000338。
- candidate blocks: **BLOCKED** — 独立候选 blocks 不足：calibration=1, holdout=0, minimum=2。

## Prior-result 差异核对

已有 QA/mask/confidence 仅作 cross-check，并未作为 canonical mask 真相源。旧 near-zero mask 的 `cos_i<=0.1` 口径包含 shadow；因此它与本轮严格 `0<cos_i<=0.1` 的差异是预期可解释差异，而非补写或拟合。

## Verdict / blockers

- **BLOCKER：** clean_a 独立 calibration/holdout candidate blocks 不足：独立候选 blocks 不足：calibration=1, holdout=0, minimum=2
- **BLOCKER：** shadow_risk_b 独立 calibration/holdout candidate blocks 不足：独立候选 blocks 不足：calibration=1, holdout=0, minimum=2

## 尚待裁决

- bounded_scene_constant_diffuse 的数值边界与依据必须在 calibration-only 条件下另行冻结；不得读取 holdout 后调整。
- 本报告不提供三种机制的拟合、残差、risk–coverage 或最终优劣结论。

<!-- stage6_5_3_b_buffered_leave_region_out_audit -->
## C5-D1A｜8.13 km Buffered Leave-Region-Out 几何可行性审查

- **审查状态：** `COMPLETED_GEOMETRY_ONLY`（几何设计审查，不是正式实验）。
- **隔离定义：**完整方形 geographic core 以像元中心欧氏距离缓冲 271 px / 8,130 m；scoreable holdout 仅为 core 内 base_valid_land。此 envelope 比只对 scoreable 像元缓冲更严格，因此不会降低隔离。
- **方法边界：**未拟合 hard_mask、soft_weight、bounded diffuse；未评分 holdout、未计算 residual、risk–coverage 或方法排名。
- **候选选择：**只用 canonical land/shadow/near_zero/lit 计数；不使用 B4/B5 residual、任何拟合或方法表现。不同 fold 的 calibration 可重叠，不能被当作统计重复。

### Raster 空间范围

- **clean_a**：shape=[746, 645]，CRS=EPSG:32648，resolution=[30.0, 30.0] m，bounds=(377670.000, 3419010.000)–(397020.000, 3441390.000)；扫描 16910 cores。
- **shadow_risk_b**：shape=[752, 650]，CRS=EPSG:32648，resolution=[30.0, 30.0] m，bounds=(292230.000, 3451230.000)–(311730.000, 3473790.000)；扫描 16910 cores。

### 可行性矩阵

| cal min | holdout min | risk/class min | A folds / non-overlap | B shadow folds / non-overlap | B near-zero folds / non-overlap | B combined folds / non-overlap |
|---:|---:|---:|---:|---:|---:|---:|
| 5000 | 500 | 50 | 16910 / 460 | 8648 / 48 | 8621 / 49 | 7818 / 37 |
| 5000 | 500 | 100 | 16910 / 460 | 6224 / 26 | 6528 / 28 | 5276 / 23 |
| 5000 | 500 | 250 | 16910 / 460 | 2636 / 9 | 2994 / 11 | 2082 / 8 |
| 5000 | 1000 | 50 | 16644 / 406 | 8090 / 41 | 8124 / 39 | 7530 / 34 |
| 5000 | 1000 | 100 | 16644 / 406 | 6013 / 26 | 6334 / 27 | 5253 / 22 |
| 5000 | 1000 | 250 | 16644 / 406 | 2555 / 9 | 2994 / 11 | 2082 / 8 |
| 5000 | 2500 | 50 | 13315 / 110 | 6123 / 28 | 6179 / 24 | 5965 / 24 |
| 5000 | 2500 | 100 | 13315 / 110 | 5083 / 19 | 5348 / 19 | 4768 / 18 |
| 5000 | 2500 | 250 | 13315 / 110 | 2305 / 10 | 2874 / 11 | 2073 / 8 |
| 10000 | 500 | 50 | 16910 / 460 | 8648 / 48 | 8621 / 49 | 7818 / 37 |
| 10000 | 500 | 100 | 16910 / 460 | 6224 / 26 | 6528 / 28 | 5276 / 23 |
| 10000 | 500 | 250 | 16910 / 460 | 2636 / 9 | 2994 / 11 | 2082 / 8 |
| 10000 | 1000 | 50 | 16644 / 406 | 8090 / 41 | 8124 / 39 | 7530 / 34 |
| 10000 | 1000 | 100 | 16644 / 406 | 6013 / 26 | 6334 / 27 | 5253 / 22 |
| 10000 | 1000 | 250 | 16644 / 406 | 2555 / 9 | 2994 / 11 | 2082 / 8 |
| 10000 | 2500 | 50 | 13315 / 110 | 6123 / 28 | 6179 / 24 | 5965 / 24 |
| 10000 | 2500 | 100 | 13315 / 110 | 5083 / 19 | 5348 / 19 | 4768 / 18 |
| 10000 | 2500 | 250 | 13315 / 110 | 2305 / 10 | 2874 / 11 | 2073 / 8 |
| 20000 | 500 | 50 | 16910 / 460 | 8468 / 48 | 8441 / 49 | 7638 / 37 |
| 20000 | 500 | 100 | 16910 / 460 | 6047 / 26 | 6348 / 28 | 5099 / 23 |
| 20000 | 500 | 250 | 16910 / 460 | 2512 / 9 | 2834 / 11 | 1959 / 8 |
| 20000 | 1000 | 50 | 16644 / 406 | 7910 / 41 | 7944 / 39 | 7350 / 34 |
| 20000 | 1000 | 100 | 16644 / 406 | 5836 / 26 | 6154 / 27 | 5076 / 22 |
| 20000 | 1000 | 250 | 16644 / 406 | 2431 / 9 | 2834 / 11 | 1959 / 8 |
| 20000 | 2500 | 50 | 13315 / 110 | 5943 / 28 | 5999 / 24 | 5785 / 24 |
| 20000 | 2500 | 100 | 13315 / 110 | 4906 / 19 | 5168 / 19 | 4591 / 18 |
| 20000 | 2500 | 250 | 13315 / 110 | 2181 / 10 | 2714 / 11 | 1950 / 8 |

### Top candidates

#### clean_a_lit_control
- edge=208 px, row=[384,592), col=[416,624), holdout land=43262, calibration land=176924, buffer-excluded land=249348, holdout shadow/near_zero/lit=0/0/43262, min geometry distance=8130.000 m。
- edge=208 px, row=[352,560), col=[432,640), holdout land=43262, calibration land=173368, buffer-excluded land=252904, holdout shadow/near_zero/lit=0/0/43262, min geometry distance=8130.000 m。
- edge=208 px, row=[368,576), col=[416,624), holdout land=43262, calibration land=169773, buffer-excluded land=256499, holdout shadow/near_zero/lit=0/0/43262, min geometry distance=8130.000 m。
- edge=208 px, row=[336,544), col=[432,640), holdout land=43262, calibration land=167004, buffer-excluded land=259268, holdout shadow/near_zero/lit=0/0/43262, min geometry distance=8130.000 m。
- edge=208 px, row=[384,592), col=[400,608), holdout land=43262, calibration land=166927, buffer-excluded land=259345, holdout shadow/near_zero/lit=0/0/43262, min geometry distance=8130.000 m。
#### shadow_risk_b_shadow_supported
- edge=208 px, row=[0,208), col=[96,304), holdout land=14225, calibration land=44141, buffer-excluded land=43856, holdout shadow/near_zero/lit=852/1344/12029, min geometry distance=8130.000 m。
- edge=208 px, row=[16,224), col=[352,560), holdout land=18190, calibration land=43905, buffer-excluded land=40127, holdout shadow/near_zero/lit=834/662/16694, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[112,320), holdout land=14338, calibration land=43320, buffer-excluded land=44564, holdout shadow/near_zero/lit=832/1343/12163, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[80,288), holdout land=14351, calibration land=44670, buffer-excluded land=43201, holdout shadow/near_zero/lit=818/1298/12235, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[352,560), holdout land=17224, calibration land=44940, buffer-excluded land=40058, holdout shadow/near_zero/lit=816/612/15796, min geometry distance=8130.000 m。
#### shadow_risk_b_near_zero_supported
- edge=208 px, row=[0,208), col=[96,304), holdout land=14225, calibration land=44141, buffer-excluded land=43856, holdout shadow/near_zero/lit=852/1344/12029, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[112,320), holdout land=14338, calibration land=43320, buffer-excluded land=44564, holdout shadow/near_zero/lit=832/1343/12163, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[48,256), holdout land=14084, calibration land=46003, buffer-excluded land=42135, holdout shadow/near_zero/lit=800/1305/11979, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[80,288), holdout land=14351, calibration land=44670, buffer-excluded land=43201, holdout shadow/near_zero/lit=818/1298/12235, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[64,272), holdout land=14180, calibration land=45127, buffer-excluded land=42915, holdout shadow/near_zero/lit=768/1265/12147, min geometry distance=8130.000 m。
#### shadow_risk_b_combined_risk
- edge=208 px, row=[0,208), col=[96,304), holdout land=14225, calibration land=44141, buffer-excluded land=43856, holdout shadow/near_zero/lit=852/1344/12029, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[112,320), holdout land=14338, calibration land=43320, buffer-excluded land=44564, holdout shadow/near_zero/lit=832/1343/12163, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[80,288), holdout land=14351, calibration land=44670, buffer-excluded land=43201, holdout shadow/near_zero/lit=818/1298/12235, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[48,256), holdout land=14084, calibration land=46003, buffer-excluded land=42135, holdout shadow/near_zero/lit=800/1305/11979, min geometry distance=8130.000 m。
- edge=208 px, row=[0,208), col=[128,336), holdout land=14159, calibration land=42673, buffer-excluded land=45390, holdout shadow/near_zero/lit=770/1265/12124, min geometry distance=8130.000 m。

### 风险区域结论

- **shadow**：在最低 matrix 门槛下有 48 个贪心空间不重叠 core；至少两个空间不同的 risk-supported holdout regions。。
- **near_zero**：在最低 matrix 门槛下有 49 个贪心空间不重叠 core；至少两个空间不同的 risk-supported holdout regions。。
- **combined_risk**：在最低 matrix 门槛下有 37 个贪心空间不重叠 core；至少两个空间不同的 risk-supported holdout regions。。


审查没有改变 C5-D1 原有严格固定 block 设计的 `BLOCKED` 结论；这里只报告另一种仍保持 8.13 km 隔离的 leave-region-out 几何候选。后续正式拟合仍需单独授权。

<!-- stage6_5_3_b_fold_proposal -->
## C5-D1B｜Buffered Leave-Region-Out Fold 提案

- **状态：** `proposal_pending_user_confirmation`；未获用户确认前，executor 不得将其作为正式实验输入。
- **隔离：**每个 calibration 像元到完整 geographic holdout core 的最小距离均为至少 8,130 m；buffer 像元不进入拟合或评分。
- **统计边界：**各 fold 是描述性挑战，calibration 可重叠；不是独立统计重复，不得由此输出像元级 p-value 或把五折视为五个独立区域。

| Fold | Scene / role | core row,col / edge px | holdout land | calibration land | excluded buffer | holdout shadow / near-zero / lit | min distance m |
|---|---|---|---:|---:|---:|---:|---:|
| stage_6_5_3_b_clean_a_lit_control_01 | clean_a / lit_control | [384,592), [416,624) / 208 | 43262 | 176924 | 249348 | 0 / 0 / 43262 | 8130.000 |
| stage_6_5_3_b_clean_a_lit_control_02 | clean_a / lit_control | [0,64), [0,64) / 64 | 3600 | 376431 | 89503 | 0 / 0 / 3600 | 8130.000 |
| stage_6_5_3_b_clean_a_lit_control_03 | clean_a / lit_control | [682,746), [0,64) / 64 | 3702 | 375702 | 90130 | 0 / 0 / 3702 | 8130.000 |
| stage_6_5_3_b_clean_a_lit_control_04 | clean_a / lit_control | [0,64), [581,645) / 64 | 3694 | 376137 | 89703 | 0 / 0 / 3694 | 8130.000 |
| stage_6_5_3_b_clean_a_lit_control_05 | clean_a / lit_control | [272,480), [64,272) / 208 | 42994 | 102509 | 324031 | 0 / 0 / 42994 | 8130.000 |
| stage_6_5_3_b_shadow_risk_b_combined_risk_01 | shadow_risk_b / combined_risk_stress | [0,208), [96,304) / 208 | 14225 | 44141 | 43856 | 852 / 1344 / 12029 | 8130.000 |
| stage_6_5_3_b_shadow_risk_b_combined_risk_02 | shadow_risk_b / combined_risk_stress | [624,752), [522,650) / 128 | 8205 | 69005 | 25012 | 265 / 413 / 7527 | 8130.000 |
| stage_6_5_3_b_shadow_risk_b_combined_risk_03 | shadow_risk_b / combined_risk_stress | [0,112), [538,650) / 112 | 3148 | 66967 | 32107 | 280 / 318 / 2550 | 8130.000 |
| stage_6_5_3_b_shadow_risk_b_combined_risk_04 | shadow_risk_b / combined_risk_stress | [288,448), [352,512) / 160 | 5043 | 22479 | 74700 | 263 / 381 / 4399 | 8130.000 |
| stage_6_5_3_b_shadow_risk_b_combined_risk_05 | shadow_risk_b / combined_risk_stress | [48,256), [304,512) / 208 | 16622 | 38397 | 47203 | 500 / 495 / 15627 | 8130.000 |

- **manifest SHA-256：** `d45df2aceeeb3607b08ced88ca04d154bbe78015ff03af9ed3bcd82776ad4fdc`。
