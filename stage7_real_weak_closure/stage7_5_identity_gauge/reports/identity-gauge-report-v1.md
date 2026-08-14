# Stage 7.5｜G/X/Z/N/E 身份边界、Gauge 与可辨识性工具箱

生成时间：2026-08-14
冻结件：架构 v3.3 §2.1（`sha256:cb514ea9…`）、`configs/identity-registry-schema-v1.json`
产物：`identity-registry-v1.json`、`gauge-equivalence-matrix-v1.json`、`disposition-ledger-v1.json`、`toolbox-fixture-results-v1.json`

> **这不是一次可辨识性审计的成功报告。** 当前正向模型只有一个自由参数，任何针对已存在对象的可辨识性结论都必然平凡。本节点的实质产出是身份体系、工具箱能力验证与对 Stage 7.6 的前置约束——见第 1 节。

## 0. 必须先读：结论的平凡性

当前正向模型为

```
rho_hat = alpha × mu        自由参数 1 个（alpha）；mu 由 cos_i 决定，属 E 类
```

**单参数模型的可辨识性问题是平凡的**：Jacobian 为 N×1，条件数恒为 1，不存在联合扰动，不存在等价替代。工具箱对该模型的 6 项检查中有 3 项返回 `not_applicable`，理由均为数学性的（单参数下奇异值谱不携带信息、等价替代至少需要两个参数、未提供多起点）。

因此，**「alpha 可辨识」这个结论不构成任何成绩**。它是模型形式的直接推论，一行式子就能看出来，不需要跑任何工具。

本节点真正做了三件事：

1. 冻结身份体系，使后续节点无法靠重定义类别来安放无处安放的对象；
2. 在合成 fixture 上验证工具箱确有能力，并**测出它的原理性局限**（第 4 节）；
3. 为 Stage 7.6 立下前置约束：三个对象被挡在门外（第 3 节）。

## 1. 身份登记

主表 20 个对象 + deferred 段 2 个。

| identity_class | 数量 | 对象 |
|---|---:|---|
| `G` | 3 | terrain_elevation、slope、aspect |
| `E` | 5 | sun_elevation、sun_azimuth、acquisition_datetime、cos_i、mu |
| `N_t` | 2 | alpha、atmospheric_scale_term（未实例化） |
| `X_t` / `Z_t` | 0 | 当前模型不含目标时变状态或独立结构约束 |
| `not_applicable` | 10 | 观测数据、残差、6 类质量因子、风险代理、证据成员身份 |

**`not_applicable` 是正确终态，不是缺失。** 架构 v3.3 §3 末段已声明质量因子不属于 G/X/Z/N/E；把 `support_mask` 或 `sensor_quality` 写进 `identity_class` 会把两套正交的本体混成一套，auditor 的 I1 直接拒收。这 10 个对象中有 6 个额外携带 `quality_phase`（4 个 pre_inference、2 个 post_inference），仅作标注，不构成第二套身份体系。

### 两处需要特别说明的判定

**cos_i 归入 E，但带前提。** 它由 slope、aspect（G 的确定性变换）与太阳几何（E）共同决定，本身完全已知、不占推断自由度，行为上是 E。但归类前提是**G 在常态训练中锁定**——若未来 G 参与更新（如局部几何重建），cos_i 将继承 G 的不确定性，必须重新分类。该前提已写入登记的 `classification_precondition` 字段，并给出触发重分类的具体条件。

**alpha 的粒度是 `acquisition × band`，不是 per-scene。** 依据 Stage 7.2 冻结件的 `estimator.fitting_key = "acquisition x band"`：18 景 × 2 波段 = 36 个独立实例。**自由度计数必须按此粒度展开。** 若按景聚合成 18，后续判断大气项与 alpha 的等价关系时自由度个数会错一半。

## 2. alpha 的 gauge：这个参数不是一个物理量

alpha 被判为 `identity_qualified_with_fixed_gauge`，而不是 `identity_qualified`。区别是实质的。

当前模型里没有独立的大气透过率项、没有辐照度常数项、没有场景平均反照率项——**它们全被合并进了 alpha**。这等价于把其余各因素隐式固定为 1，是一次**没有明说的 gauge fixing**。

后果：

```
alpha 的数值是「透过率 × 辐照度尺度 × 平均反照率 × …」这个合成量的估计，
不是其中任何一项的测量。
```

所以 registry 的 `forbidden_paths` 里写死两条：不得被报告为地表反照率的独立估计，不得被报告为大气透过率的独立估计。

`evidence_scope` 判为 `global`，依据是 `analytic_proof`：模型对 alpha 线性，Jacobian 各元素恒为 mu、不随参数点变化，故局部结论在整个参数域成立。这是解析论证，不是多起点数值实验的升级——两者的区别由 schema 的 `global_justification_kind` 字段强制区分（见第 5 节）。

## 3. 三个对象被挡在 Stage 7.6 之外

| 对象 | 终态 | 解封条件 |
|---|---|---|
| `atmospheric_scale_term` | `non_identifiable_equivalent` | 取得独立锚点（如 AOD 产品）钉住 T；或显式固定 gauge 并声明 alpha 为 gauge-relative；或与 alpha 互斥比较 |
| `optical_effective_roughness` | `deferred_missing_anchor` | 取得能独立约束它的证据，且其进入正向模型的形式被独立合同冻结 |
| `sar_scale_roughness` | `deferred_missing_anchor` | SAR L0 证据进入项目 |

`atmospheric_scale_term` 的等价性是**解析结论，不依赖任何数据**：若模型写作 `rho_hat = T · alpha' · mu`，则 `(T, alpha')` 与 `(kT, alpha'/k)` 对任意 k>0 产生逐点相同的预测。观测只能约束乘积。

**互斥比较那条解封路径附带一条限制**：胜出方只取得 gauge-fixed 的参数化身份，**不得记为该物理机制已获独立证据**。拟合优度差异不是机制证据（架构 §1.3）。

两个粗糙度对象进入 deferred 段而非主表，因为**它们的类别归属本身就是 §7-F 的未决内容**。在主表里给它们填一个 `identity_class`，等于替 §7-F 关闭一个它没关闭的问题。deferred 段只冻结一件事：**二者不是同一个对象**，后续节点不得复用同一身份、同一符号或同一参数实例。

## 4. 工具箱：能力已验证，局限也已测出

26 项 fixture 断言全部通过。六个 fixture 覆盖单参数、乘性共线、加性可分、缩放仿射、条件量排除、以及数据变化不足六种情形。

**但最重要的产出是一条负面结论：**

> **F2（真的乘性共线）与 F6（结构可分但因子几乎是常数）的数值秩与秩亏完全相同。**

这两种情形的正确处置是相反的：

- F2 是**结构不可辨识**——加再多数据也没用，必须改模型或固定 gauge；
- F6 是**实际不可辨识**——补充在关键维度上有新变化的数据即可解决。

而工具箱看到的东西一模一样。这不是实现缺陷，是**数值方法的原理性局限**：奇异值谱只知道「这批数据里两列共线」，不知道「它们是不是在式子里就绑死了」。要分辨只能回到模型式子做符号分析或给出解析证明。

据此，工具箱内部做了两处硬约束：

1. 原函数名 `check_structural_rank` 改为 `check_numerical_rank`，返回值携带 `caveat` 字段，随每个结论一起传播；
2. 全部数值检查的 `evidence_scope` 上限为 `local` 或 `profile`。**`global` 不由工具箱签发。**

顺带测出的第三件事：乘性共线的零空间方向 ∝ (T, −a)，**随参数点变化**。因此「多起点下零空间方向稳定」不能作为不可辨识的判据——稳定的是秩，不是方向。

## 5. auditor：不变量可执行，且抓得住

registry 的 8 条不变量已实现为可执行 auditor，fail-closed。负例自检 6/6 全部抓到（把质量因子名写进 identity_class、给 not_applicable 对象加 disposition、用数值实验冒充 global 依据、gauge.fixed 却判成普通 qualified、篡改上游 hash、给 deferred 对象强行定类别）。

**其中 I5 经历过一次重写。** 初版用关键词匹配散文 justification，结果把「**不是**多起点数值实验的升级」判成了「是数值实验」——同一套判据也会放过只写「解析」二字却不给证明的条目。**关键词匹配同时产生误报与漏报，不能作为可判定的准入条件。** 改为结构化枚举 `global_justification_kind ∈ {analytic_proof, structural_argument, domain_covering_evidence}` 后，散文仍保留供人读，但不参与判定。

## 6. §7-F 的关闭边界

**已关闭（身份层）**：光学有效粗糙度与 SAR 尺度粗糙度已分别登记独立身份，「二者不是同一对象」这一断言已冻结，堵死后续节点复用同一身份的路径。

**未关闭**：两类粗糙度各自的定义与类别归属、冠层/地物高度约束的可辨识性、X(t) 状态的刷新节奏、跨模态可辨识性。

**本节点不关闭 §7-F。** 上列各项已在 disposition ledger 中显式登记为未关闭，不得因本节点完成而被视作已解决。

## 7. 操作边界

未运行真实算子消融；未读取任何 residual、alpha 或 score 结果值；未激活任何状态；未改写任何冻结件；未新增第二套身份 registry；未为满足五分类而重定义任一类别；未把观测支持谱或置信度计算引入本节点。

本节点不消费既有结果值，故项目规则 `pr_d4a37fa568df` 第 1–4 条的结果盲冻结时序整体不适用；第 5 条（跨节点冻结时序）仍适用于 Stage 7.6。

上游回归：7.1 通过 136 项（另 15 项因本机未安装 Earth Engine 库而在 setup 阶段跳过，与本节点无关）、7.2 通过 37 项、7.3 通过 25 项、7.4 通过 17 项。本节点 fixture 26 项、registry auditor 不变量 11 条全部通过。
