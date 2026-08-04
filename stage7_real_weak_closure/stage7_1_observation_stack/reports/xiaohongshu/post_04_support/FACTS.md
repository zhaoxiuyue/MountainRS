# Post 04 事实卡与雷区清单

给写正文的人（小克 / 阿澈）。**本文不规定怎么写，只规定什么是真的、什么不能说。**
文笔、结构、节奏由你们定。写完由执行手只审事实层。

主题：《还没训练 AI，数据已经可能被挑偏了》
论点：**先冻结完整候选宇宙与预注册标准，再做资格审计，避免实验结果反过来参与选数据。**

---

## 一、可以直接用的事实（每条都注了出处，可自行核）

### 1. 候选宇宙

| 事实 | 数值 | 出处 |
|---|---|---|
| 2023 年 Path 130 / Row 38 全部过境 | **21 景** | Earth Engine 只读查询，2026-08-04 |
| 其中与目标 ROI 有交集 | 21 景 | 同上 |
| 完整覆盖 ROI（覆盖率 ≥ 0.999999） | **21 景，全部** | `data/raw/acquisition-catalog.json` → 逐景 `target_roi_footprint_coverage` 全为 1.0 |
| 被几何规则挡在宇宙之外 | **0 景** | 由上两行相减 |
| 宇宙身份哈希 | `15d5522991f9…` | `evidence/export-manifest-v3.json` → `source_evidence.universe_sha256` |
| 枚举方式 | `complete_without_cloud_or_quality_truncation` | `acquisition-catalog.json` → `query_scope` |

**所以「21 景一景没挑」成立，无需限定。** 全年就 21 次过境，21 次全部完整覆盖，21 景全部进入宇宙。

### 2. 冻结的先后顺序（本文命门）

| 事实 | 出处 |
|---|---|
| 选景协议状态：`frozen before any Stage 7.1 GEE catalog query` | `docs/selection-protocol.md` 文首 Status |
| 目标网格：`The choice is fixed before any new acquisition catalog is viewed`，冻结日 2026-07-23 | `configs/target-grid.yaml` → `frozen_date`、`selection_rationale` |
| 禁止条款：不得用 cloud / QA / residual / fit / validation / test / model 任一准则移除、替换或重排导出集成员 | `docs/selection-protocol.md` §9.1 |
| `CLOUD_COVER` 只可作元数据报告，不得用于 top-N、排序或静默移除困难观测 | `docs/selection-protocol.md` §1 |

### 3. 资格审计漏斗

```
2023 年全部过境                 21
完整覆盖 ROI（几何层）           21   ← 有权淘汰，实际淘汰 0
成功获取                        21
身份与语义完整                   21
精确网格通过                     21
stack_eligible                  18   ← 唯一实际发生淘汰的一层
划分            train 10 / validation 3 / test 5
```

出处：`evidence/stack_manifest.json` → `counts`、`split`、`members[]`

### 4. 被判不合格的三景

| 日期 | canonical 位次 | QA-clear 像元 | 判据 |
|---|---|---|---|
| 2023-02-02 | 3 | **0** | `base_valid_land > 0` 不成立 |
| 2023-06-10 | 10 | **0** | 同上 |
| 2023-07-12 | 12 | **0** | 同上 |

出处：`evidence/local-support-audit-v1.json` → `members[].qa_clear_count`

冬雪与雨季，整景**没有一个** QA-clear 像元。判据是预注册的 `base_valid_land > 0`。

### 5. 划分

`N=18` → `n_train = max(1, floor(0.6×18)) = 10`、`n_validation = max(1, floor(0.2×18)) = 3`、
`n_test = 18−10−3 = 5`。按 `system:time_start` 升序连续切段：
train `2023-01-01 → 07-28`、validation `08-13 → 09-30`、test `10-16 → 12-19`。
规则原文见 `docs/selection-protocol.md` §5。**纯算术，无人为阈值。**

### 6. 一个可用的细节

第 3 景（2023-02-02）在很早就暴露了不合格，但后面 18 景**照样一景不落地导完**——
因为 §9.1 禁止用 QA 准则跳过成员。**省事和守规矩冲突时守规矩**，这是"避免结果反向参与选数"最生动的实证。

---

## 二、雷区（写错任何一条，全文说服力归零）

1. **「不合格」≠「质量差被剔除」。**
   判据是预注册标准判定"没有可用观测"，不是主观取舍。这个区别是全文的地基。
   ✅ 「预注册标准判定它没有可用观测」 ❌ 「我把质量差的剔除了」

2. **几何层淘汰的是 0，不是"筛掉了一些"。**
   别写成"先用几何规则筛一遍"。准确说法：几何层**有权**淘汰，实际淘汰 0 景；
   唯一实际发生的淘汰在 `stack_eligible`，淘汰 3 景。

3. **不得暗示任何模型结论。**
   这个节点只建观测证据栈，**没有拟合、没有评分、没有比较机制**，
   `model_eligible` 明确为 `not_adjudicated_stage_7_2`。任何"效果如何/谁更好"的话都是越界。

4. **`stack_eligible` 不等于"数据好"。**
   它只表示：本地成员与哈希存在、精确网格完整性通过、`base_valid_land > 0`。
   18 景合格不代表 18 景好用，只代表它们有可用观测、可以进入下一步评估。

5. **别把 split 说成"我分的"。**
   split 是 §5 的算术在 N=18 上的唯一解，先冻结规则再代入数字。

6. **数字必须与图一致。**
   图卡的数字来自同一批冻结文件；正文若与图不符，以冻结文件为准并回头改图。

---

## 三、目前无法宣称的

- 无法宣称"这些数据足以训练/验证某个模型"——样本量是否够是 Stage 7.2 的通过条件之一，本节点未评估。
- 无法宣称这个 ROI 代表龙门山或任何更大区域——`target-grid.yaml`
  的 `geographic_scope_statement` 明确写它只是几何压力测试 ROI。
- 无法宣称逐景的 shadow / near-zero 支持量——唯一冻结的 `cos_i` 只对
  `LC08_130038_20230101` 的太阳几何有效，逐景分类属 Stage 7.2。

---

## 四、结尾问题（本篇落点，建议保留）

> 剔除低质量影像，什么时候是在去噪，什么时候是在删掉最难的真实世界？

可回扣第一篇《背阴坡不是黑，是模型少了一项物理》：**最难的像元恰恰是背阴坡**——
删掉难的，等于删掉你要研究的对象。四篇由此成环。
