# Stage 7.1-R｜L0 观测证据成员与支持语义补全

生成时间：2026-08-06T00:00:00Z
语义契约：`configs/validity-support-schema-v1.json`（sha256 `d79f60a884cb81b1…`）
冻结证据对账：`evidence/evidence-reconciliation-audit-v1.json`（sha256 `53d120871791
7f42…`）
支持账本：`evidence/observation-support-ledger-v1.json`（sha256 `103278e1158746f8…`）
证据清单：`evidence/observation-evidence-manifest-v1.json`（sha256 `7ea5cf3da6aceed5…`）
操作视图：`evidence/stage-7.2-direct-only-input-view-v1.json`（sha256 `3c9adfd98d5f6dbd…`）

## 1. 结论

Stage 7.1 留下的结论是「18 景可用、3 景不合格」。本节点不推翻这个结论，而是把它
放回它真正的位置：**21 景全部是不可撤销的证据成员，18/3 只是 direct-only 这一个
操作下的资格投影**。缺失与拒绝的原因从此是可追溯的证据字段，不再在建模前消失。

冻结证据对账 11 项全通过，21 景身份、canonical order、网格、内容哈希、任务谱系与
25 条 preserve_bytes 冻结件字节全部未漂移。回归 151/151 全绿（既有 104 + 新增 47）。

本节点不计算 cos_i、不拟合、不评分、不产出任何置信度。

## 2. 语义上改了什么

| 语义 | Stage 7.1 | Stage 7.1-R |
|---|---|---|
| 成员资格 | 隐含在 `stack_eligible` 里，不合格即退出观测栈 | `evidence_membership = included`，21 景全部，本 universe version 内不可撤销 |
| 3 景的地位 | `not_eligible` | 证据成员，且在 direct-only 操作下 `operation_scoped_unsupported` |
| 支持 | 单一 `base_valid_land` 计数 | 四层可追溯：观测机会 → 逐波段源有效 → QA 支持 → 目标地表支持 |
| 缺失原因 | `zero_base_valid_land` 一句话 | `deprivation_kind` 顶层 passive / active 二分 + 五类细分 |
| 来源类别 | 无 | 显式映射到架构 v3 §3 的 `observed_inferred` / `prior_only` / `unsupported` |
| 太阳几何 | 只有一景冻结了 cos_i | 21 景原始角度全部登记为几何支持输入原语 |

一句话：`stack_eligible` 从「候选状态机的一个状态」降级为「历史操作资格映射」。
旧 `stack_manifest.json` 字节未改、未改名，只是被限定范围地后继。

## 3. 冻结证据对账（11 项，全通过）

| # | 检查 | 结果 |
|---|---|---|
| C1 | 21 景身份集合在 catalog / export manifest / stack manifest / support audit 四处一致 | 通过 |
| C2 | canonical order 连续 1..21，与时间升序一致，order↔身份映射三处一致 | 通过 |
| C3 | 21 景精确匹配冻结网格 `shadow-risk-b-b4-grid-v1`（零容差） | 通过 |
| C4 | 21 景磁盘 SHA-256 与三处记录逐一相同 | 通过 |
| C5 | 逐波段 VALID 无损重建复现既有掩膜计数，被掩膜像元一律携带传输零值 | 通过 |
| C6 | 历史操作资格固定 18/3，不合格三景恰为 `base_valid_land = 0` 的三景 | 通过 |
| C7 | split 复算等于既有 10/3/5，按时间连续切段，只分配给 eligible 子集 | 通过 |
| C8 | journal 63 事件，终态 COMPLETED 经 task_id 唯一回链且全部 succeeded | 通过 |
| C9 | 21 景太阳几何全覆盖（仰角 31.14°–68.81°） | 通过 |
| C10 | 21 景 footprint 覆盖率均为 1.0 | 通过 |
| C11 | relocation-manifest-v2 的 25 条 preserve_bytes 冻结条目字节完好 | 通过 |

## 4. 核心发现：这个 ROI 的缺失几乎全是主动清零

21 景 × 488,800 像元 = 10,264,800 个像元级观测事件。按冻结谓词分层：

| 层 | 计数 | 占比 |
|---|---|---|
| 观测机会（常数场） | 10,264,800 | 100% |
| 逐波段源有效（Msource） | 10,258,820 | 99.94% |
| QA-clear（Mqa） | 2,366,524 | 23.05% |
| base_valid | 2,353,117 | 22.92% |
| base_valid_land | 2,088,892 | 20.35% |

剥夺归因（顶层二分互斥且穷尽，`passive + active = 7,911,683 = 非 base_valid`）：

| 顶层 | 含义 | 计数 | 占剥夺 |
|---|---|---|---|
| **passive** | 观测不可获得 | **5,980** | 0.076% |
| **active** | 观测存在但被主动拒绝 | **7,905,703** | 99.924% |

**主动清零是被动无观测的 1,322 倍。** 架构 v3 §3 要求这两类分别量化、
「不得混成一个『低置信度』总体数字」，未决问题 I 也点名这条。本 ROI 上这个要求
不是形式主义：如果按老办法合成一个「低支持」数，这 1,322 倍的量级差会完全消失，
而它恰恰说明这里的信息缺口来自云雪遮挡（可通过补观测缓解），不是来自数据不可得。

细分类计数**不可相加**，因为同一像元可同时命中多类：

| 细分类 | 顶层 | 计数 |
|---|---|---|
| `qa_rejected` | active | 7,893,358 |
| `reflectance_out_of_range` | active | 432,012 |
| `terrain_nodata` | active | 0 |
| `source_band_missing` | passive | 5,980 |
| `no_acquisition` | passive | 0（full cover 下恒空） |

三个 active 细分类之和 8,325,370，重叠 419,667，**8,325,370 − 419,667 = 7,905,703
= active 顶层桶**，精确闭合。这条算术就是「细分类不可相加为互斥分解」的量化证明，
也被写成了测试。`water` 不属于剥夺，它是被单独计数的地表类型（264,225 像元事件）。

## 5. 三景被重新解释成了什么

`LC08_130038_20230202`、`LC08_130038_20230610`、`LC08_130038_20230712`：

- `evidence_membership = included` —— 仍是证据成员，永久保留
- `acquisition_status = acquired` —— 采集事实成立，任务谱系完整闭合
- `target_surface_support_status = zero_base_valid_land`
- `deprivation_kind = active`，细分 `qa_rejected`，证据是 `qa_clear_support_count = 0`
- `stage_7_2_direct_only_input_eligibility = operation_scoped_unsupported`
- `provenance_class = unsupported`

归因来自实测计数而非断言：构建器在归因前会校验 `qa_clear = 0`，不成立就停机。

这三景不是「没有数据」，是**全景云雪、观测被 QA 全部拒绝**。它们在 split 之外，
但仍在证据宇宙之内。`training_semantics` 冻结了它们的用法：不得作目标、不得作
负样本、不参与损失、不编码为地表状态零值。

## 6. 逐世界位置计数层

| 栅格 | 取值范围 | 说明 |
|---|---|---|
| `outputs/support/source_valid_count_SR_B4.tif` | 19 – 21 | 唯一有源缺失的波段 |
| `outputs/support/source_valid_count_SR_B5.tif` | 21 – 21 | 全域源有效 |
| `outputs/support/source_valid_count_QA_PIXEL.tif` | 21 – 21 | 全域源有效 |
| `outputs/support/qa_clear_support_count.tif` | 0 – 12 | |
| `outputs/support/base_valid_land_count.tif` | 0 – 12 | |

`observation_opportunity_count` **不写栅格**：21 景 footprint 覆盖率均为 1.0，
该量在冻结 ROI 上是常数场 21。它由 full-cover 事实导出，不是逐像元重算结果，
写成栅格会伪装成有空间变化的独立层。若将来引入部分覆盖的 acquisition，
该字段必须退回逐像元重算——这一条写在 schema 里。

**support gap**：64,480 个世界位置（占 ROI 13.19%）在 21 次观测机会中一次也没有
形成目标地表支持；全支持像元为 0。support gap 是「缺少支持」这个事实本身，
不是地表状态结论，也不是低置信度。

## 7. 太阳几何登记（本次补充）

21 景的 `sun_azimuth_deg` / `sun_elevation_deg` 全部登记进证据清单，来源字段
`SUN_AZIMUTH` / `SUN_ELEVATION`，标 `transcribed_not_computed = true`。

`geometry_support_status = not_computed`，`geometry_support_inputs_ready = true`。

Stage 7.1 移交时的边界仍然成立：唯一冻结的 cos_i 栅格只对 `LC08_130038_20230101`
的太阳几何有效，不得套用于其他 acquisition。本节点没有计算任何 cos_i，只是把
Stage 7.2 冻结几何支持公式时所需的输入原语提前钉住，省掉一次回头取数。

## 8. 两个 successor 与 supersession 边界

**`observation-evidence-manifest-v1`** —— 21 景证据清单
`semantic_successor_of: mountainrs-stage7.1-stack-manifest-v1`，
`supersession_scope: validity_semantics_and_support_projection`，
以 sha256 唯一绑定旧清单，`predecessor_edited = false`。

**`stage-7.2-direct-only-input-view-v1`** —— 操作视图
以 sha256 绑定来源证据清单；18 eligible_candidate / 3 operation_scoped_unsupported；
split 10/3/5 原样复读，`split_scope = stage_7_2_direct_only_eligible_subset`；
显式声明本视图不改变 evidence membership。

旧 protocol、manifest、journal、stack_manifest、readiness report 与
observation-schema.yaml 全部字节未改、未改名、未覆盖。

## 9. 边界与移交 Stage 7.2

- **全部 21 景**进入逐景几何支持评估范围；能算则登记 cos_i / geometry support，
  不能算则产出有原因的 typed unsupported。**18 景**进入 direct-only calibration
  Gate，**3 景不拟合**。
- `Msource` 与 `Mqa` 由本节点交付；`Mgeom_support` 与 `Mloss_support` 的精确公式
  由 Stage 7.2 在拟合前冻结，四者保持独立身份，不得合成为单一权重后丢弃因子。
- 任何后续 operation-level unsupported 都不得撤销 `evidence_membership = included`。
- `confidence_projection_status = not_computed`；本节点只生成 confidence inputs
  与 support primitives。
- 来源类别标签体系（`observed_inferred` / `prior_only` / `unsupported` /
  `support_ready`）由 Stage 7.4、7.8、7.11 直接继承，下游另立平行标签体系视为违约。
- **仍待办**：registry 别名 `stage_7_1_terrain_stack` 指向 `data/terrain_stack`
  依然为空。地形几何目前通过 `local-support-audit-v1.json` 中按 sha256 钉住的
  stage6.5 产物解析（dem / slope / aspect，构建时逐条校验哈希，不符即停）。
  Stage 7.2 若需要独立地形栈，应在该节点显式建立，不由本节点静默复制。

## 10. 产物清单

| 产物 | sha256 |
|---|---|
| `configs/validity-support-schema-v1.json` | `d79f60a884cb81b15c0ebcd2d2959108ea050f3c4a1a2b60c4893539a92133a9` |
| `evidence/evidence-reconciliation-audit-v1.json` | `53d1208717917f42c17dd1ea84a8448c6a97016f04b0e210a1107beca0249454` |
| `evidence/observation-support-ledger-v1.json` | `103278e1158746f80a7c0dd325a354046677a8c39b34c5eef37cf6300d50977d` |
| `evidence/observation-evidence-manifest-v1.json` | `7ea5cf3da6aceed55c1a2525fb958d44863cea5e243192c2ae56383f547197ea` |
| `evidence/stage-7.2-direct-only-input-view-v1.json` | `3c9adfd98d5f6dbd9767bc42ac3590d5b1bf3905f92f0a5e891dba8daf2251da` |

配套程序：`scripts/audit_evidence_reconciliation_v1.py`、
`scripts/build_observation_evidence_v1.py`；
测试：`scripts/tests/test_evidence_reconciliation_v1.py`（17）、
`scripts/tests/test_observation_evidence_v1.py`（30）。

操作边界：未调用 Earth Engine，未认证，未创建任务或资产，未下载影像，
未改写任何冻结证据，未改变成员集合、资格谓词或 split。
