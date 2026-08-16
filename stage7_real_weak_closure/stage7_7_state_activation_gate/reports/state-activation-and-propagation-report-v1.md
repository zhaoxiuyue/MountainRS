# Stage 7.7 报告｜L1 状态激活 Gate 与几何失效传播首验

**记录日期** 2026-08-16

本节点的两半必须分开读。状态激活 Gate 的通过条件在空集上**空真**，几何失效传播 fixture 是**实质验收**。把两者合并成一句「本节点通过」会让读者以为状态都判过了。

---

## 一、L1 状态激活 Gate：候选 universe 为空集

### 结论

`activated_count = 0`。候选状态 universe 为空集，passCriteria 1–3 全部空真。

### 推导（不含裁量项）

| | 内容 | 地位 |
|---|---|---|
| P1 | 本节点 passCriteria 1：「候选状态只能依赖 Stage 7.6 的 qualified 算子」 | 在 7.6 首次结果值产出前冻结，**preregistered** |
| P2 | Stage 7.6 产出零个 qualified 算子 | 已公开的判定结果 |
| ⇒ | 不存在满足 P1 的候选状态，universe = ∅ | 唯一推出 |

任何执行手在 P1 与 P2 之下都会得到同一结果。

### 暴露地位：两句话必须同时说

- **这个冻结标记 post-result exploratory**，不得声称 preregistered。`nc_e3a7a30f1aaa` 要求它早于 7.6 首次结果值产出，实际晚了（偏差登记于 `../stage7_6_optical_operator/evidence/cross-node-timing-deviation-v1.json`）。
- **该标记是关于时点的，不是关于内容的。** 空集由结果前即冻结的依赖约束唯一推出，执行手没有挑选空间。

只说前者会让人以为清单可能被结果污染；只说后者会掩盖真实发生的时序偏差。

### 空集不等于没想过

架构 v3.3 §2.1 对 X(t) 的举例已逐一登记排除理由（见 `evidence/candidate-state-universe-v1.json`）。其中一条值得单列：

**`terrain_adjacency_surface_state` 与 Stage 7.6 的严格邻接项互为前提**——邻接算子需要周围坡面的地表状态才能成立，而该状态又需要一个 qualified 的邻接算子才能被观测约束。这是循环依赖，不是疏漏，在当前证据下无法从任一端解开。

---

## 二、几何失效传播：本节点的实质工作

### 为什么这一半有独立价值

该机制在项目中此前**不存在**：仓库内 `invalidated`/`quarantined` 的全部命中只有架构规范条款与 Stage 7.4 的事故记录，无任何实现。架构第 212 行本身把它登记为待验证的未决问题：

> 如何区分持续几何变化与随机残差，如何界定包含可见性与辐射传播的影响范围，以及如何审查和回滚，仍需小样区经验与专项验证。

本节点是该验证，不是该问题的关闭。

### 核心设计决策：几何版本按什么定义

两个直觉方案各被一个真实反例否决：

**方案 A：按 artifact 字节身份（文件 sha256）。**
Stage 7.6 引入的外扩 DEM 是全新 artifact，但其 ROI 窗口内与冻结 DEM 逐位相同（488,800 像元，max|d| = 0.0000 m）。按 hash 定义会令 cos_i、slope、aspect 及全部后代失效，而它们的输入一个比特都没变。这是**假阳性失效**。

**方案 B：按几何值在自身存储范围内是否变化。**
v_sky 的地平线搜索半径是 10 km，ROI 之外 10 km 内的地形变化会改变 ROI 内的 v_sky，而 ROI 内高程可以一字未动。这是**假阴性失效**——让已失效的派生量继续被当作有效，比假阳性严重得多。

**采用：几何版本按「值 + 消费者影响半径」定义，artifact 身份只是载体。**

对消费者 c，两次几何状态同版本当且仅当在 c 的**影响域**内逐元素相等。影响域 = c 的计算范围向外扩张其影响半径。

| 消费者 | 影响半径 | 依据 |
|---|---|---|
| slope / aspect / cos_i | 30 m | 有限差分只用相邻像元 |
| v_sky | 10 km | Stage 7.6 几何 Gate 冻结的搜索距离 D* |

**同一次几何变更对不同消费者可以得出相反结论，这是设计意图而非不一致。** 未登记的消费者一律 fail closed，不许默认半径 0——默认 0 会系统性产生假阴性。

### 三类变更与传播

| 变更类别 | 判据 | 传播 |
|---|---|---|
| `artifact_only` | 影响域内值逐元素相等 | 不传播，但**必须留痕** |
| `value_change_in_scope` | 影响域内存在值变化 | 直接依赖 → `invalidated`；后代 → `quarantined` |
| `scope_extension` | 覆盖扩大，原覆盖内值不变 | 视该消费者此前是否有产出而定 |

两级标记不合并：`invalidated` 是**已知失效**，`quarantined` 是**待确认**。合并会丢失「哪些被直接推翻、哪些只是受牵连」这一信息，使重算无法按拓扑序推进。

无依赖路径的 artifact 保持有效——空间范围重叠不构成依赖关系（架构第 156 行禁止包围盒内无条件全删）。

### fixture 结果：22/22

每个用例都指明它能杀死哪个错误实现。杀不死任何实现的用例等于没有用例。

| 用例 | 验的是 | 杀死的错误实现 |
|---|---|---|
| F1 | artifact 变而影响域内值不变（**真实素材**） | 只比对文件 hash |
| F2 | 影响域外变化，小半径消费者 | 按整 artifact 比值 |
| F3 | 影响域外变化，大半径消费者 | 按自身存储范围比值（假阴性） |
| F4 | 无依赖 artifact 保持有效 | 按空间包围盒失效 |
| F5 | 两级标记区分与传播路径 | 合并成一个标记 |
| F6 | 旧 cache 不得静默载入 | 不匹配即静默重算 |
| F7 | 未登记消费者 fail closed | 默认半径 0 |
| F8 | 按 receipt 回滚 | — |
| F9 | ROI 边界接缝落在两消费者影响域的不同侧 | 回避边界案例 |

### 两处对冻结用例设定的调整

冻结规则先于 fixture 运行，执行中发现两处必须如实调整：

**F1 的 compute_rect 内缩一个像元。** 冻结 DEM 的覆盖恰好等于 ROI 且无余量，因此 **ROI 最外一圈像元的 cos_i，其影响域已伸出 DEM 之外**。这是既有事实，不是本用例引入的。fixture 保留了这一点并单独断言：不内缩时该判定为 `scope_extension`。

**F9 是半合成的。** Stage 7.6 的替换前 DEM 版本未归档，无法取得纯真实的接缝前后对照。该用例采用真实接缝的统计量级（std 7.792 m）但构造扰动位置。如实标注，不冒充真实素材。

### 对一次真实变更的传播审计

审计对象是 Stage 7.6 实际发生过的几何 artifact 变更（冻结 DEM → 外扩 DEM），不是为产出证据而编造的场景。

结果：**invalidated 0、quarantined 0、valid 8**。slope/aspect/cos_i 判 `artifact_only`（影响域内 488,800 像元逐位相同）；v_sky 判 `scope_extension` 且此前无产出，属新增能力而非失效。

**不传播也留了全量痕迹。** 若只记录发生了传播的事件，「规则判定不传播」与「规则漏检」在事后无法区分。

---

## 三、未关闭的问题

- **架构第 212 行只被部分处置。** 本节点给出了「影响范围如何界定」的可执行答案（按消费者影响半径），但**「如何区分持续几何变化与随机残差」未处理**——变更判据是逐元素精确比对，不含噪声容差，无法区分微小真实变化与数值噪声。该问题保持开放。
- **只覆盖光学链路。** SAR 斜距几何的消费者及其影响半径属 Stage 8.0，未登记。遇到时会按 `UnregisteredConsumer` 停机，这是预期行为。
- **fixture 首验不等于 v3.1 §7H 几何变化检测已解决**（本节点 explicitExclusions）。
- **影响半径不是消费者的固有属性，而是其配置的函数。** v_sky 的 10 km 来自 Stage 7.6 冻结的 D*；若 D 改变，登记表必须同步更新。

---

## 四、下游

`activated_count = 0` 使 Stage 7.9 无法激活——其 objective 要求「只使用 Stage 7.7 已激活状态与 Stage 7.6 已资格化算子……状态经 L2 重建观测」，无状态即无闭环。该停止条件已固定为节点约束 `nc_8fe5b4709440`，不依赖记忆或口头交接。

补数据后的重新资格化路径固定为 `nc_b6d6ef3e44f2`：Stage 7.8 关闭前须判定新增 domain/reference 是否补足了当前缺失的变化范围、锚点或状态约束，**判据须在读取新域结果值之前冻结**——否则「是否值得 reopen」会变成一个可按期望结果调节的问题。

空集是诚实的中间状态，不是路线终点。

---

## 五、产物

| 文件 | 角色 |
|---|---|
| `configs/geometry-version-and-propagation-v1.json` | 版本定义、变更分类、传播规则、F1–F9 用例（**fixture 运行前冻结**） |
| `evidence/activation-preflight-manifest-v1.json` | 只读预检，含所有者路线计划 |
| `evidence/candidate-state-universe-v1.json` | 空集冻结与逐项排除理由 |
| `evidence/activation-registry-v1.json` | 激活登记表（activated_count = 0） |
| `evidence/state-observation-matrix-v1.json` | 状态-观测矩阵（无行，有列） |
| `evidence/dependency-graph-v1.json` | artifact 依赖图与影响半径 |
| `evidence/propagation-audit-v1.json` | 真实变更的传播审计（含 no-op 留痕） |
| `evidence/propagation-receipt-v1.json` | fail-closed receipt 与回滚契约 |
| `evidence/fixture-manifest-v1.json` | fixture/实现/规则的字节身份与运行结果 |
| `scripts/geometry_propagation_v1.py` | 传播实现 |
| `scripts/tests/test_geometry_propagation_v1.py` | F1–F9 |
| `scripts/emit_propagation_evidence_v1.py` | 证据集生成 |
