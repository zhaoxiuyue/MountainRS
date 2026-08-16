# Stage 7.7｜L1 状态激活 Gate 与几何失效传播首验

## 本容器做什么

合同的两半可执行性截然不同，**必须分开读**：

**其一，L1 状态激活 Gate（passCriteria 1–3）—— 候选 universe 为空集。**
passCriteria 1 规定候选状态只能依赖 Stage 7.6 的 qualified 算子；Stage 7.6 产出零个 qualified 算子，故候选集合被唯一推出为空集，activated_count = 0。这一半的通过条件全部**空真**——关闭时不得表述为「状态激活 Gate 已通过」，空真的通过不是验收。

空集的冻结时点晚于 Stage 7.6 首次结果值产出（偏差登记于 `../stage7_6_optical_operator/evidence/cross-node-timing-deviation-v1.json`），故标记 **post-result exploratory**；但空集这一结论由结果前即冻结的依赖约束唯一推出，不含执行手的挑选空间。

**其二，几何失效传播 fixture（passCriteria 4–6）—— 本节点的实质工作。**
不依赖任何 qualified 算子。要建立的机制在项目中尚不存在：仓库内 `invalidated`/`quarantined` 的命中仅有架构规范条款与 Stage 7.4 的事故记录，无任何实现。架构 `docs/architecture.md` 第 156–161 行给出规范，第 212 行明确将其登记为「仍需小样区经验与专项验证」的未决问题——本节点即该验证。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `evidence/` | `activation-preflight-manifest-v1` 已就位（只读预检，outcome = ready，含所有者裁决的路线计划）。后续：候选 universe 冻结件、geometry version 定义、传播审计、fail-closed receipt |
| `configs/` | 待产出：几何失效传播规则、fixture 规格 |
| `outputs/` | 待产出：fixture 运行结果（依 `.gitignore` 不入 git，字节身份由 evidence 中的 manifest 承担） |
| `scripts/` | 待产出：传播实现与 fixture/oracle |
| `reports/` | 待产出：节点报告 |

## 依赖哪些兄弟容器与冻结件

- `../stage7_6_optical_operator/` — 零 qualified 算子这一事实的证据来源；其 `optical-operator-contract-v1.json` 含局部 dependency_graph，是本节点汇聚全局依赖图的素材之一
- `../stage7_5_identity_gauge/` — 身份闭集；「光学有效粗糙度与 SAR 尺度粗糙度保持不同身份」这一要求的依据
- `../stage7_1_observation_stack/` — 原始观测永久保留与 evidence_membership 不可撤销的上游保证（passCriteria 4 末项的基础）
- `../../docs/architecture.md` §156–161 与第 212 行 — 传播规则的规范来源与未决问题登记

## fixture 的现实素材

Stage 7.6 期间引入了外扩 DEM `dem_roi_plus_20km_utm48n.tif`——新 artifact，但 ROI 窗口内与冻结 DEM 逐位相同（488,800 像元，max|d| = 0.0000 m）。正确的传播结果是 cos_i、slope、aspect 及其后代**不应**被 invalidated。

这个用例恰好落在两种错误实现的交叉点上：只比对文件 hash 的规则会错误地令整条链失效，只看几何值的规则会漏掉真正的版本漂移。其 ROI 边界的接缝（std 7.792 m / max 103.6 m）另构成「影响范围如何界定」的真实边界案例。真实素材不替代合成 fixture——多条传播路径仍需合成用例覆盖。

## 下游

本节点的 activated_count = 0 使 Stage 7.9 无法激活，该停止条件已固定为节点约束 `nc_8fe5b4709440`。补数据后的重新资格化路径见 `nc_b6d6ef3e44f2`（指向 Stage 7.8）。
