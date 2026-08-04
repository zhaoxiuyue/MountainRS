# 网格声明修正案（提案 v1）

**状态：草案，待所有者裁决。本文本身不授权任何导出、不使任何 acquisition 成为 `stack_eligible`、不分配 split、不改变候选宇宙、ROI 或 target grid。**

提出者：执行手（Claude Code）
提出日期：2026-08-04
关联 PF3 节点：`nd_a5842cfa87de`（Stage 7.1）
关联进展：`ev_63829dc21a29`（根因诊断）、`ev_215a9d9c54cd`（违规自查）

---

## 1. 本修正案只改两句话

### 1.1 被修正条款 A

`docs/mask-preserving-observation-storage-protocol-v2.md` 第 3 节：

> The output must use the frozen `shadow-risk-b-b4-grid-v1` CRS, six-element
> affine transform, shape, bounds and pixel alignment. The task may not set
> `scale`, **`dimensions`**, `bestEffort`, a non-nearest resampling mode, a shared
> nodata value, or a partial/sharded-output option.

### 1.2 被修正条款 B

`docs/selection-protocol.md` 第 9.3 节：

> The Export must use the exact frozen CRS and six-element affine transform; it
> must not substitute `scale`, **`dimensions`**, `bestEffort` or a shifted grid.

**两条中被修正的只有 `dimensions` 一词。** `scale`、`bestEffort`、非最近邻重采样、共享 nodata、分片输出——全部维持禁止，一字不动。

---

## 2. 为什么必须改：两条冻结条款目前互斥

`configs/target-grid.yaml` 的 `canonical_stack_constraints` 要求
`exact_grid_match_required: true`、`silent_resampling: prohibited`、`mismatch_action: stop_and_report`。

只读诊断（0 任务 / 0 资产 / 0 下载）已证实，在**不设 `dimensions`** 的前提下，该要求无法满足：

| 探针 | 结果 |
|---|---|
| EE 回显 region 原始存储坐标 | `[292230, 3451230, 311730, 3473790]`，整数，`geodesic=false`，与冻结值逐位相同 |
| EE 自算的 region 外接框 | 西边距网格原点 **Δ = 0.0 m**，列索引恰为 **0.0**；东 650.0、南 752.0 |
| 同一影像 `clip(region).reproject(crs, crsTransform)` | `dimensions=[652, 754]`，**`origin=[-1, -1]`** |
| 同一 region + crsTransform 下 `reduceRegion` | **488800**（＝冻结像元数） |
| 同一 region + crsTransform 下 `Export` | **489552** ＝ 651 × 752 |

**根因**：Earth Engine 的栅格物化路径会在裁剪几何四周各加一圈 1 像元裙边。我方 region 与 crsTransform 无浮点漂移、无投影误差；差异 100% 产生在 EE 一侧。Export 路径表现为保留西侧那一列（原点 x 由 292230.0 变 292200.0，北/南/东边界不变）。

实证：attempt-1（task `WDI4LVYAKCREQUJPII2JAFV2`）以 `Export too large: specified 489552 pixels (max: 488800)` 终态 FAILED；attempt-2（task `VQLKW3N7RVXY4432QF3O2XSO`）仅抬高 maxPixels，终态 COMPLETED 但产物为 651×752，按 `exact_grid_match_required` 不可入栈。该产物保留于
`data/raw/rejected_exports/LC08_130038_20230101__SR_B4_SR_B5_QA_PIXEL__VALID__v2_attempt2_651x752_rejected.tif`（sha256 `95474954…`）。

**结论**：禁令写作时未预见 EE 的这一行为。禁 `dimensions` 的立法原意是「不得用 scale/dimensions 兑出一个被替换或近似的网格」，而在本例中，`dimensions` 恰恰是唯一能兑现该原意的手段。维持原文则条款 A、B 与 `exact_grid_match_required` 永久互斥，本节点无解。

---

## 3. 修正后的规则（比原禁令更严）

> 输出网格必须等于冻结的 `shadow-risk-b-b4-grid-v1`。任务**不得**设置 `scale`、
> `bestEffort`、非最近邻重采样模式、共享 nodata 值或分片输出选项。
>
> 任务**可以**设置 `dimensions`，**当且仅当**同时满足下列全部条件：
>
> 1. `crs` 逐字等于冻结值 `EPSG:32648`；
> 2. `crsTransform` 逐元素等于冻结的六元仿射
>    `[30.0, 0.0, 292230.0, 0.0, -30.0, 3473790.0]`；
> 3. `dimensions` 逐字等于 `"<width>x<height>"`，其中 width、height 取自冻结
>    `shape`，即 `"650x752"`；
> 4. 同一任务**不得**同时传入 `region`；输出网格只能被声明，不得由几何推导；
> 5. `maxPixels` 等于冻结 `pixel_count`（488800），使网格膨胀在服务端即失败；
> 6. 本地核对在**落位之前**执行：实际 GeoTIFF 的 crs、transform、width、
>    height、bounds、resolution、pixel alignment 逐项等于冻结值，任一不符即
>    停手且不得进入 alias 目录。
>
> 上述任一条件不成立，`dimensions` 仍然禁止。

**净效果比原禁令更强**：原文只是一句禁止，无机器强制；新条款是「禁止 + 六项绑定 + 落位前核对」，且下节要求把它写成审计断言。

---

## 4. 审计器义务（修补「校验哈希 ≠ 校验遵守」）

本次事故的技术成因之一是：`audit_export_manifest_v3.py` 校验了 `frozen_contract`
中协议文件的 sha256，却从不校验协议**正文**的禁止清单。哈希对得上、正文被违反，
审计仍然全绿。

本修正案生效后，manifest 审计器**必须**新增下列断言，缺一不可：

1. `execution.scale_parameter == "omitted"`；
2. `execution.best_effort is False`；
3. `execution.resampling == "nearest_neighbor_default"` 且 `explicit_resample_call is False`；
4. `execution.format_options_no_data == "omitted"`；
5. `execution.skip_empty_tiles is False`；
6. `execution.region_parameter == "omitted"`；
7. `execution.dimensions_parameter` 等于由 `target_grid.shape` 计算出的 `"650x752"`——**不得**接受任何硬编码字面量；
8. `execution.max_pixels == target_grid.pixel_count`；
9. manifest 引用的协议文件 sha256 必须同时命中「协议原文」与「本修正案」两份，缺任一即失败。

并补充回归测试：逐条构造违反上述断言的变异 manifest，断言审计器拒绝。

---

## 5. 追溯范围（需所有者明确选择）

三景已在修正案冻结**之前**按本形态导出完毕：

| order | acquisition | task | sha256 | 网格 | 无损重建 |
|---|---|---|---|---|---|
| 1 | `LC08_130038_20230101` | `HTBLVMKOD7MLLEDHJXBOHAFC` | `69530d52…` | 650×752 ✅ | ✅（mask=0 512） |
| 2 | `LC08_130038_20230117` | `7G7C37XHKPCNJUD6PUIHTWRZ` | `dfafc16c…` | 650×752 ✅ | ✅（mask=0 1339） |
| 3 | `LC08_130038_20230202` | `OT3EPS2CNRDFQ5GHGTT5F7LF` | `35a11988…` | 650×752 ✅ | ✅（mask=0 0） |

**选项 R（追溯适用）**：三景逐一复核第 3 节六项条件后予以承认。理据是这六项条件**可从产物本身独立验证**，不依赖执行时的意图声明——三景均已通过。

**选项 P（仅向后适用）**：三景判为不可入栈，按修正后的合同重新导出。成本约 15 分钟，manifest-v3 生命周期允许每景 2 次尝试、当前各用 1 次，预算充足。

**须诚实指出**：重导出很可能产出字节相同的文件（同一确定性表达式），但 EE 侧压缩与分块不保证逐字节可复现，故不能预先断言 hash 相同。因此选项 P 的实际收益是**程序上的洁净**，而非产物质量上的改善——两者产物质量已被同一套审计独立验证为相同。

执行手建议 **R**，但这是所有者的合同判断。

---

## 6. 本修正案明确不做的事

- 不改变候选宇宙（21 景，identity hash `15d5522991f9…`）、canonical order、ROI 或 target grid 任一数值；
- 不使任何 acquisition 成为 `stack_eligible`，不分配 split；
- 不引入任何数值阈值，不改变 QA、反射率、支持域或 `base_valid_land` 语义；
- 不改写 `export-manifest-v1.json`、`export-manifest-v2.json` 或任何 `preserve_bytes` 冻结证据；
- 不放宽 attempt / retry 上限，不放宽 `maximum_active_exports = 1`。

---

## 7. 冻结方式（技术约束）

`selection-protocol.md` 与 `mask-preserving-observation-storage-protocol-v2.md`
的 sha256 已被 manifest-v2 与 manifest-v3 的 `frozen_contract` 钉死。**就地编辑
这两份文件会使已冻结的 manifest 审计失败**，因此本修正案不得就地修改原文，只能作为
**独立文档 supersede 被点名的那一句**——与 protocol-v2 当初 supersede v1 存储路线
的方式完全一致。

裁决通过后建议落为两件：

- `docs/grid-declaration-amendment-v1.md`——规范正文（本文定稿）；
- `evidence/grid-declaration-amendment-v1.json`——机器可审版本，绑定
  `export-manifest-v3.json` 的 sha256 `2ee2b57a…`，供审计器强制校验。

随后由审计器实现第 4 节九条断言并补齐回归测试。

---

## 8. 待裁决事项清单

1. 是否采纳本修正案（是 / 否 / 修改后采纳）；
2. 追溯范围选 **R** 还是 **P**；
3. 是否同意第 4 节的审计器义务清单，是否需要增删条目；
4. 定稿后的文档命名与落点是否按第 7 节执行。
