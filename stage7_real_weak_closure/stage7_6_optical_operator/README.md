# Stage 7.6｜光学 L2 算子资格化：漫射、邻接与大气边界

## 本容器做什么

对天空漫射、地形邻接反射与加性大气路径辐射三类候选逐项资格化，判定它们能否进入冻结 L2 栈。**结论是三个候选全部未获支持**，L2 光学算子在本节点结束时仍为 direct-only（`rho_hat = alpha·mu`）。

结论范围 evidence_scope = local：单 ROI、非独立 fold、post-result exploratory。不得读作「天空漫射项无用」或「地形调制不存在」——未获支持的是该假设在本数据上的可检测性。

先读 `reports/optical-operator-report-v1.md`，它是本容器的入口。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `configs/` | 两份结果前冻结件：`svf-geometry-gate-v1`（几何精度选择协议）、`optical-operator-config-v1`（候选集、判定规则、support gate） |
| `evidence/` | 冻结与结果的可复算证据。`freeze-manifest-v1` 是结果读取前冻结件的唯一 hash 权威；`result-freeze-manifest-v1` 登记结果件字节身份；`optical-operator-contract-v1` 是下游引用光学算子的唯一权威 |
| `outputs/` | 程序产物（依仓库 `.gitignore` 不入 git，字节身份由 `result-freeze-manifest-v1` 承担）：v_sky 栅格、消融单元表、判定表、审计报告 |
| `scripts/` | v_sky 计算与几何 Gate、消融执行、终态判定、两套 fail-closed auditor、收据生成 |
| `reports/` | 人读报告 |
| `docs/` | 执行期间产生的裁决请求 |

## 依赖哪些兄弟容器与冻结件

- `../stage7_1_observation_stack/` — 观测栈成员、支持审计、evidence manifest、direct-only input view
- `../stage7_2_baseline_fit/` — cos_i registry、mconf registry
- `../stage7_3_spatial_blocking/` — fold 拓扑与几何标定域。**消融的数据装载层逐字沿用其 `fit_fold_alpha_and_score_v1.py`**，口径若自行发明则跨节点不可比
- `../stage7_5_identity_gauge/` — 身份闭集与可辨识性工具箱；本容器复用其 schema 与 rtol=1e-10，引用而不修改
- `../../stages/stage2_dem_terrain/data/dem_roi_plus_20km_utm48n.tif` — 为 v_sky 引入的外扩 DEM，来源与可复现性见 `evidence/dem-extension-provenance-v1.json`（本体不入 git）

## 两件必须一并读到的事

- `evidence/cross-node-timing-deviation-v1.json` 登记了一次跨节点时序偏差：Stage 7.7 的候选状态 universe 本应在本节点首次结果值产出前冻结，实际未做。
- 本节点的负结果使 Stage 7.7 的 activated_count = 0，进而使 Stage 7.9 无法激活（见节点约束 `nc_8fe5b4709440`）。补数据后的重新资格化路径见 `nc_b6d6ef3e44f2`。
