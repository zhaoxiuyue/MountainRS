# Stage 7.8｜多域 L0 证据与独立参考的结果盲冻结

## 本容器做什么

为 3–5 个相对基准 ROI 存在**真实断裂**的 domain 建立并冻结 L0 证据栈、独立参考登记与评估设计。本节点**只建设和冻结证据，不训练、运行或比较任何候选模型**——`qualified` 只表示证据可用于评估，`deferred` 不等于模型跨域失败。

这是 Stage 7 后半段的转折点：Stage 7.6 判定三个光学 L2 加性项全部 unsupported、Stage 7.7 因此 `activated_count = 0`，而那个负结果的主要嫌疑成因之一就是单 ROI 的数据限制（fold 内 v_sky 的 IQR 中位仅 0.062，26% 的 train 单元变化不足）。本节点补的正是这一块。

**本节点也是迄今数据获取量最大的节点。** Stage 7.5/7.6/7.7 均以既有数据为主，本节点要从零建 3–5 个 domain 的完整证据栈——项目当前有零个其他 domain、零个地面测量。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `configs/` | 结果盲冻结件。`domain-candidate-universe-v1`（候选全集、真断裂判据、准入条件、确定性排序与替补规则）、`requalification-gate-criteria-v1`（重新资格化 Gate 判据） |
| `evidence/` | `activation-preflight-manifest-v1`（只读预检）、`freeze-manifest-v1`（冻结件唯一 hash 权威）。后续：逐域证据栈 manifest、Reference Registry、reconciliation report、Gate 判定 |
| `outputs/` | 待产出（依 `.gitignore` 不入 git，字节身份由 evidence 中的 manifest 承担） |
| `scripts/` | 待产出：分域获取、准入核验、支持审计 |
| `reports/` | 待产出 |

## 依赖哪些兄弟容器与冻结件

- `../stage7_1_observation_stack/` — **L0 schema 与质量因子体系直接复用**：`validity-support-schema-v1`、`observation-schema.yaml`、`target-grid.yaml`、支持审计体系。passCriteria 2 要求所有 domain 复用同一套定义，不得为单域临场修改
- `../stage7_6_optical_operator/` — v_sky 的计算参数（N=36、D=10 km、含曲率）为重新资格化 Gate 的 G1 判据所引用，计算参数不得因新域调整，否则两组数字不可比
- `../stage7_5_identity_gauge/` — G2 判据所指的 `deferred_missing_anchor` 判定来源
- `.cache/earthengine/venv` — 数据获取通道（Stage 7.6 已验证其可复现性）

## 终态

`qualified_multidomain_evidence_frozen`。五个 domain：天山中段、太白山秦岭、祁连山中段、高黎贡山（以上 evaluation）、阿尔泰山中段（calibration）；基准岷山为 train。独立参考为 Sentinel-2，判 `reference_observation` 并通过 I1–I4 与 L1–L4 全部审计，五域 ±3 天匹配 603 对。

**重新资格化 Gate 判 `requalification_not_warranted`** —— Stage 7.6 的负结果与 Stage 7.7 的空集保持不变。其中 G1 有一个推翻默认假设的结果：同尺度对照下，五个断裂域中只有太白山的 v_sky 变化范围超过基准，天山甚至低一个数量级。

## 三件容易读错的事

**其一，「结果值」在本节点包含几何与支持统计量。** 本节点不产生 residual，但重新资格化 Gate 要判断新域有没有补足「变化范围」，那就得看 v_sky 的分布与 IQR。所以 Gate 判据与 domain 候选全集是**同一个 change set**，在碰任何新域数据之前一起冻结——不能等核验完再定判据。

**其二，`deferred` 不阻断 7.9，但 7.9 仍然开不了工。** passCriteria 7 说「deferred 不阻断 Stage 7.9 单 ROI 主线」，这只声明本节点的 deferred 不构成阻断，它无权声明 7.9 没有别的阻断源。`nc_8fe5b4709440` 因 `activated_count = 0` 而阻断 7.9，当前生效，本节点无论判什么都不解除它。

**其三，独立参考的可得性是终态的主要不确定源。** 项目无任何地面测量。本节点有权允许 `reference observation` 充当独立参考（只要不称其为真值，且独立性与时间匹配容差一并冻结），但若连独立的 reference observation 也不可得，须如实判 `deferred`。**为拿到 qualified 而放宽参考类别，是本节点最直接的自欺路径。**
