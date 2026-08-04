# C7.1-D3B-M1｜SR_B4 source-mask 因果审计

## 结论边界

本报告是只读因果审计；未修改 Export 合同、stack eligibility、任务、资产或影像。它不选择新的存储路线。

## 计数口径复核

旧预检使用 `image.mask().reduceRegion(Reducer.count())`。这计数派生 mask 影像自身未遮蔽的像元，并不等于 `mask == 1` 的像元数。
本审计将有效数定义为 `sum(image.mask())`，零数定义为 `target_pixel_count - mask_one_count`。

## 审计摘要

- acquisition 总数：21
- SR_B4 存在 mask=0 的景数：10
- B5 全部 mask=1：True
- QA_PIXEL 全部 mask=1：True
- B4 首要分类：`{"source_native_missing":10}`

## B4 异常景

| 景 | target mask=0 | native mask=0 | 边界 mask=0 | QA fill | B4 saturation | 分类 |
|---|---:|---:|---:|---:|---:|---|
| `LC08_130038_20230101` | 512 | 513 | 3 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20230117` | 1339 | 1364 | 52 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20230218` | 9 | 9 | 0 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20230306` | 22 | 22 | 0 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20230914` | 2 | 2 | 0 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20230930` | 23 | 23 | 0 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20231016` | 75 | 75 | 0 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20231101` | 857 | 859 | 5 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20231117` | 292 | 288 | 7 | 0 | 0 | `source_native_missing` |
| `LC08_130038_20231219` | 2849 | 2847 | 4 | 0 | 0 | `source_native_missing` |

## 路线影响比较

| 路线 | 候选宇宙 | 证据保真 | 后续模型输入 |
|---|---|---|---|
| A. 排除 10 景 | 改变 complete_v5_universe_all_21；会引入按掩膜结果排除的选择偏差。 | 不保存被排除景的原始观测证据，无法再现其缺失语义。 | 仅剩 11 景，任何后续 split/模型输入都不再对应冻结 universe。 |
| B. 原始 DN + 显式逐波段 valid-mask | 可保留 21 景，但需要新的版本化存储合同，不能改写 v1。 | 可逆地保留 raw DN、每 band mask 与 QA 的不同语义，最低信息损失。 | 本地派生时可按 band-aware 有效域构建输入；必须重新定义 stack gate 与报告分母。 |
| C. 全部保留，按冻结支持域本地判定 eligibility | 保留 21 景，但仅在现有 v1 约束被正式替换后才可执行。 | 若仍只存三 band 且不存 source mask，会丢失 B4 无效位置，不能满足保真要求。 | 可避免整景排除偏差，但不能把缺失 B4 冒充为可用于支持域或模型输入。 |

## 停止条件

本轮不选择 A/B/C，也不修改任何冻结合同；等待 Elara 裁决正式存储路线。
