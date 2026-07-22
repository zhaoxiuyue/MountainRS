# Stage 6.5.3-B｜已批准的方法与评价合同

- **状态：** `approved_for_stage_6_5_3_b`；本轮只冻结合同与校验接口，尚未运行任何拟合、holdout 评分、residual 或 risk–coverage 计算。
- **fold basis：**`evidence/stage6_5_3_b/proposed_fold_manifest.json` 的 approved content hash 为 `d0dc8cc339edef91ff2bf519d37af08549385de88eab4119ce0b882f30ff3b37`；其批准前 proposal source hash 为 `d45df2aceeeb3607b08ced88ca04d154bbe78015ff03af9ed3bcd82776ad4fdc`。五个 Clean A lit/control 与五个 Shadow-risk B combined-risk cores 的身份、坐标、计数和 8,130 m / 271 px buffer 均不变。
- **统计边界：**geographic cores 两两不重叠；不同 fold 的 calibration 可以重叠，故每折只作为描述性空间挑战，不能被当作独立统计重复。
- **适用范围：**只限 Stage 6.5.3-B 的机制压力测试。它不验证完整 L0–L5，不把 residual 称为反演真误差，也不推断真实 diffuse irradiance、sky-view、邻坡散射、BRDF 或大气辐射传输机制。

## 1. 共同输入、分区与训练边界

对 scene `s`、band `b∈{B4,B5}`、fold `f`、像元 `p`：

```text
rho_obs(s,b,p) = Landsat L2 SR B4 或 B5 的观测 surface reflectance
mu(p)          = max(cos_i(p), 0)
tau            = 0.1
```

每个 `(scene, band, fold)` 独立拟合，B4 与 B5 分开报告。canonical base-valid land 仍由 QA_PIXEL bits 0–5 clear、B4/B5/cos_i 有效、B4/B5 位于 `[-0.05,1.0]` 重建；QA water bit 7 单独统计且不进入 land 主指标。分区固定为 `shadow=cos_i<=0`、`near_zero=0<cos_i<=0.1`、`lit=cos_i>0.1`。

所有可拟合参数、NDVI/brightness 分位点与任何参数边界只可使用当前 fold 的 calibration 数据。holdout、buffer 和 holdout `rho_obs` 不得进入参数估计、阈值、fold 选择或模型选择。若 manifest hash 不匹配、任一训练像元至其 core 的最小距离低于 8,130 m，或输入/partition 与 manifest 支持量不一致，停止执行。

## 2. 三种冻结机制

### hard_mask

```text
rho_hat = alpha * mu
0 <= alpha <= 1
calibration support = calibration ∩ lit = {cos_i > 0.1}
objective = ordinary least squares
```

`alpha` 是 scene×band×fold 共享的直接光 gain/albedo-like scalar，不是已验证真 albedo 产品。holdout 中 `cos_i<=0.1` 固定标为 `unsupported_by_hard_mask`：不进入 hard_mask 评分成功集合，却仍保留在 coverage 分母中，绝不能因被排除而被称为低风险成功。

### soft_weight

```text
rho_hat = alpha * mu
0 <= alpha <= 1
w_k = sigmoid(k * (cos_i - 0.1))
calibration support = 全部 calibration base_valid_land
objective = sum(w_k * (rho_hat - rho_obs)^2)
```

主值为 `k=30`；`k=15` 和 `k=60` 仅属于同一机制的预注册敏感性分析，不能计作额外方法，也不能依据 holdout 表现选择。`w_30` 是 observability/reliability 排序分数，不是正确概率。主要风险始终使用未加权 absolute residual；低权重不是低误差成功。

### bounded_scene_constant_diffuse（D1，已采纳）

```text
rho_hat = alpha * (mu + delta)
0 <= alpha <= 1
0 <= delta <= 0.1
d = alpha * delta
calibration support = 全部 calibration base_valid_land
objective = ordinary least squares
```

`alpha`、`delta` 和 `d` 都是 scene×band×fold 共享常数；同一 fold 内的所有 calibration 和 holdout 像元共享它们。`delta` 是受 `tau=0.1` 限制的无量纲 illumination-equivalent 常数；`d` 使用 surface-reflectance 标度。严禁逐像元 diffuse、分区专属参数或逐像元自由 residual 项。

每个 `(scene,band,fold)` 必须报告 `alpha`、`delta`、`d`、拟合状态与边界状态。优化器把 `delta` 约束在 `0` 或 `0.1` 时，必须标记 `boundary_hit`；不得根据 holdout 放宽、移动或替换边界。该探针不代表真实 diffuse irradiance 或物理反演值。允许的负面结论严格是：

> 当前场景级常数化 diffuse 参数化未带来可验证改善。

## 3. Residual、reliability 与 risk–coverage

```text
residual      = rho_hat - rho_obs
absolute_error = abs(residual)
```

residual 的单位为无量纲 surface reflectance；正值表示指定 forward baseline 过预测，负值表示低预测。它不是反演真误差、地表真 albedo error 或真实光学机制的证明。

每个 `band × scene × fold × canonical partition` 都必须报告：bias、MAE、median absolute error、P90 absolute error、supported 数和 unsupported 数。reliability 固定为：hard_mask 的 lit=`1`、其余 `unsupported`；soft_weight 的 `w_30`；bounded diffuse 的 `w_30`（只表示观测支持度，不表示 diffuse 成功概率）。

coverage 分母是 geographic core 内**全部** base-valid land；water 不在分母。像元按 reliability 降序、同分按固定 row-major 顺序形成 coverage 前缀。方法比较只在三种方法共同可达的 coverage 上进行，并同时报告每种方法最大可达 coverage。unsupported 不得从分母消失。

每折结果是主结果；仅允许 fold-level median、min、max 等描述性汇总。禁止像元级 p-value、置信区间，或把共享/重叠 calibration 的五折称为五个独立区域。

## 4. 表面异质性反证检查

此检查只诊断“全局 alpha 的残差是否主要来自植被/土壤表面异质性”，不增加任何拟合参数，也不按分层重新拟合 `alpha` 或 `delta`。

```text
NDVI       = (B5 - B4) / (B5 + B4)
brightness = (B4 + B5) / 2
```

NDVI 只在 B4/B5 finite 且 `abs(B5+B4)>=1e-6` 时计算；不满足安全分母规则的像元只从本诊断分层排除，不改变 canonical domain 或主要评价。每 fold 只用 calibration 计算 NDVI 和 brightness 的 25%、50%、75% 分位点，并把同一分界应用到 holdout。

每个有效表面分层分别报告三种方法的 MAE 与 P90 absolute error。任一分层的 holdout 像元少于 `100`，标记 `insufficient_support`。对同一 scene/band/fold，global 方法排序定义为共同可达 coverage 上的全 core MAE 升序；若该排序在至少两个充分支持分层中反转，或某方法优势只存在于单一充分支持表面分层，标记 `surface_heterogeneity_sensitive`，不得宣称稳定的光照机制优势。

## 5. 拟合后只读空间检查

正式 holdout 评分结束后，使用冻结的经验半变异函数口径对 holdout residual 做事后诊断。它不重新选 fold、不调参、不修改 mask 或方法合同。若在 `>=8,130 m` 的至少两个有效 lag bins 中 residual semivariance 持续低于 tail-sill 的 `95%`，标记 `spatial_dependence_warning`，并进一步限制泛化结论。

## 6. 失败边界与依据

停止条件包括：manifest/hash 不匹配；calibration–holdout 最小距离不足 8,130 m；holdout 信息进入参数、阈值或 fold 选择；alpha/delta 越界或优化不可复现；required fold/partition 支持量与 manifest 不一致；current-task stale；或输出越过 Workspace Contract。

合同依据为 `docs/architecture.md` V3、Stage 5/6 的 hard/soft forward toy、Stage 6.5.2-A/B 本地检查、C5-D1 canonical preflight，以及 C5-D1A buffered leave-region-out geometry audit。此轮未运行三种机制、未计算 residual/risk–coverage、未生成方法排名，也没有节点完成或 PF2 结果写回。
