# Stage 6.5.3-B｜C5-D3 正式机制实验报告

- **run ID：** `c5_d3_35789933202effad`
- **合同 manifest：** `stage6_5_real_landsat_observation_stress_test/evidence/stage6_5_3_b/proposed_fold_manifest.json`，content hash `d0dc8cc339edef91ff2bf519d37af08549385de88eab4119ce0b882f30ff3b37`。
- **范围：**Clean A lit/control 与 Shadow-risk B shadow/near-zero stress；每折为描述性 buffered leave-region-out 挑战，不是独立统计重复。
- **不做的推断：**residual 是指定 forward baseline 的 model–observation residual，不是真值反演误差；D1 diffuse 是受 tau=0.1 约束的场景常数探针，不是真实 diffuse irradiance。

## 运行 Gate

- contract anchors：config `dc6224964aca5ca910dc38952aebaae6a0429597137286ffc1d5add3057d5d59`；approved method contract `0662e61b78fb110e19eb40243848d5a07589cca56a9b774e8bd70621edb1c910`；D2 executor contract `2c91e41c77aa4ab5dbb69c27979f59a4b0d2978f20cdc0c1bd785853934e9ee3`。
- 所有 10 folds 均复核 calibration/holdout/buffer 计数与 manifest 一致；最小隔离距离均不低于 8,130 m。
- scalar results hash：`5dac993df75fb513978b7b17fd08ee97201575846a27aedcaf567e79c4d5faa6`。

## 各场景 / 波段 / 方法的 fold-level 描述性摘要

| scene | band | method | median fold MAE | median fold P90 | median maximum coverage |
|---|---|---|---:|---:|---:|
| clean_a | B4 | hard_mask | 0.023309684185704112 | 0.03953916539998264 | 1.0 |
| clean_a | B4 | soft_weight_k30 | 0.023309683961343915 | 0.03953916511976907 | 1.0 |
| clean_a | B4 | bounded_scene_constant_diffuse | 0.023309685032140426 | 0.0395391653999826 | 1.0 |
| clean_a | B5 | hard_mask | 0.05201700084211928 | 0.10212538302777835 | 1.0 |
| clean_a | B5 | soft_weight_k30 | 0.052017005229932904 | 0.10212541044434499 | 1.0 |
| clean_a | B5 | bounded_scene_constant_diffuse | 0.05204412445091575 | 0.10206141391920362 | 1.0 |
| shadow_risk_b | B4 | hard_mask | 0.0767866514904577 | 0.14062727575685388 | 0.8722982351774737 |
| shadow_risk_b | B4 | soft_weight_k30 | 0.06470929762885462 | 0.1351246581240032 | 1.0 |
| shadow_risk_b | B4 | bounded_scene_constant_diffuse | 0.06467703854124379 | 0.135052048529724 | 1.0 |
| shadow_risk_b | B5 | hard_mask | 0.06752696864935426 | 0.1262908219720924 | 0.8722982351774737 |
| shadow_risk_b | B5 | soft_weight_k30 | 0.06541714921553188 | 0.1233511136622637 | 1.0 |
| shadow_risk_b | B5 | bounded_scene_constant_diffuse | 0.06221783882199424 | 0.12053242476703302 | 1.0 |

## 反证与空间诊断

- `surface_heterogeneity_sensitive`：20 / 40 个 scene×fold×band×stratification 诊断被标记。被标记的单元不得宣称稳定光照机制优势。
- residual spatial diagnostics：warning=0，no-warning=0，inconclusive=60。inconclusive 是 holdout core 尺度或 lag 支持不足，不是空间独立性的证明。

## 合同范围内 verdict

- **hard_mask：WARNING** — 硬掩膜的最大 coverage 中位数为 0.9700697870292383；cos_i<=0.1 保留为 unsupported，不能把排除当作低风险成功。
- **soft_weight_k30：INCONCLUSIVE** — 只在当前样本、当前 shared-fold 设计下描述 residual 与 coverage；w30 不是正确概率。
- **bounded_scene_constant_diffuse：WARNING** — D1 边界命中 17 / 20 个 scene×fold×band 拟合；只检验当前场景级常数参数化。
- **Stage 6.5.3-B：WARNING** — 当前结果受表面异质性敏感或 residual 空间诊断限制；不得宣称稳定机制优势。

## 产物与边界

- 紧凑表、evidence manifest 与本报告均可追溯；大体量 residual GeoTIFF 与图像只在 approved outputs 路径生成，遵循 Git ignore。
- Evidence manifest：`stage6_5_real_landsat_observation_stress_test/evidence/stage6_5_3_b/c5_d3_35789933202effad/experiment_manifest.json`。
- 本轮没有写回 PF2 结论、没有完成节点，也没有清除 current-task。
