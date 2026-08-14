# Stage 7.5｜G/X/Z/N/E 身份边界、Gauge 与可辨识性工具箱

## 本容器做什么

在往模型里增加任何自由度**之前**，先回答三个问题：

1. **谁是谁**——每个进入推断图的对象属于 G / X(t) / Z(t) / N(t) / E 中的哪一类。
2. **谁可以动**——哪些接受梯度、哪些锁定、哪些是已知条件量。
3. **谁和谁其实是同一个自由度**——哪些参数只以固定组合影响预测，因而分不开。

本节点**不跑真实算子消融、不看 residual、不激活任何状态**。它产出的是一张身份表和一套审计工具，供 Stage 7.6 在加算子时校验。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `configs/` | registry schema、闭集定义、auditor 配置 |
| `evidence/` | identity registry 本体、gauge/等价矩阵、disposition ledger、preflight 与 hash 绑定 |
| `scripts/` | 可辨识性工具箱与 auditor |
| `scripts/tests/` | 固定 fixture（合成的、已知答案的测试案例） |
| `outputs/` | 工具箱在 fixture 上的运行结果表 |
| `reports/` | 人读报告 |
| `docs/` | 需所有者裁决时的一页式请求 |

## 依赖哪些兄弟容器与冻结件

- **架构 v3.3 §2.1**（`../../docs/architecture.md`）——五类身份的**唯一**定义来源。本节点不得重定义任一类别。
- **架构 v3.3 §3**——质量因子与三类来源类别；与本节点的身份体系**正交**，不得合并。
- **架构 v3.3 §7-F**——本节点关闭其中属于身份层的部分。
- `../stage7_2_baseline_fit/evidence/alpha-reference-full-support-v1.json`——alpha 的估计式、粒度（`acquisition x band`）与正向模型形式。
- `../stage7_2_baseline_fit/evidence/cos-i-registry-v1.json`——cos_i 与 mu 的定义链。
- `../stage7_1_observation_stack/configs/validity-support-schema-v1.json`——support 与 provenance 的既有 taxonomy。

## 两条容易踩的边界

**① 身份体系只适用于进入推断图的对象。** 质量因子、诊断量、算子、residual、provenance、治理元数据一律登记 `identity_class = not_applicable`，**不得强行归入五类**，也不得因它们装不下而停机。若某个 not_applicable 对象恰属架构 §3 的质量因子，只加一个轻量字段 `quality_phase`，**不建第二套身份 registry**。

**② 当前正向模型只有一个自由参数。** `rho_hat = alpha × mu`，其中 mu 由 cos_i 决定、属 E 类。因此对**已存在对象**的可辨识性审计结论必然是平凡的——单参数、Jacobian 为 N×1、无联合扰动可做、无等价替代可查。

**这个平凡性必须写进报告，不得包装成「审计通过」。** 本节点的实质产出在另外三处：身份体系冻结、工具箱在 fixture 上的能力验证、以及对 Stage 7.6 的前置约束（例如显式大气尺度项一旦引入，默认判 `non_identifiable_equivalent`）。
