# Stage 7.1 readiness report

生成时间：2026-08-04T11:00:00Z
来源导出合同：`evidence/export-manifest-v3.json`（sha256 `2ee2b57a040ff647…`）
网格声明修正案：`evidence/grid-declaration-amendment-v1.json`（sha256 `d21d34295075b6f9…`）
支持域审计：`evidence/local-support-audit-v1.json`（sha256 `682ecd0d0e0efb66…`）

## 1. 结论

完整 21 景候选宇宙已全部导出并通过本地无损掩膜重建审计；按冻结 selection-protocol
§3 判定，其中 **18 景** `stack_eligible`，**3 景**不合格。
按 §5 唯一算术规则分配 acquisition 级 split：train 10、
validation 3、test 5，三者均非空。

## 2. 网格与存储

全部 21 个成员精确匹配冻结网格 `shadow-risk-b-b4-grid-v1`：
`EPSG:32648`、650×752、
transform `[30.0, 0.0, 292230.0, 0.0, -30.0, 3473790.0]`、488800 像元、
6×uint16 波段、无共享 nodata。掩膜由显式 `*_VALID` 波段重建，逐景与
`source-mask-causal-audit-v1.json` 的 M1 计数吻合。

## 3. eligibility 判据

`base_valid_land > 0`，其中 base_valid 包含 QA-clear。该读法**不是本节点选定的**：
冻结文本可作两读，两读在部分景上给出相反判定，故改用 Stage 7.0 对同一景
（shadow-risk B ＝ `LC08_130038_20230101`）冻结的账目反解——`base_valid_land = 102222`
与 cos_i 分区 `4063 / 4559 / 93600` 四数同时精确复现，当且仅当 QA-clear 属于
base_valid；另一读法差 +177821。未引入任何新阈值。

## 4. 成员一览

| order | short product ID | 日期 | QA-clear 像元 | base_valid_land | eligible | split |
|---|---|---|---|---|---|---|
| 1 | LC08_130038_20230101 | 2023-01-01 | 255793 | 107215 | eligible | train |
| 2 | LC08_130038_20230117 | 2023-01-17 | 41866 | 32900 | eligible | train |
| 3 | LC08_130038_20230202 | 2023-02-02 | 0 | 0 | not_eligible | not_assigned |
| 4 | LC08_130038_20230218 | 2023-02-18 | 241037 | 218404 | eligible | train |
| 5 | LC08_130038_20230306 | 2023-03-06 | 56447 | 46908 | eligible | train |
| 6 | LC08_130038_20230322 | 2023-03-22 | 257 | 226 | eligible | train |
| 7 | LC08_130038_20230407 | 2023-04-07 | 9319 | 7447 | eligible | train |
| 8 | LC08_130038_20230509 | 2023-05-09 | 72970 | 72751 | eligible | train |
| 9 | LC08_130038_20230525 | 2023-05-25 | 156663 | 156085 | eligible | train |
| 10 | LC08_130038_20230610 | 2023-06-10 | 0 | 0 | not_eligible | not_assigned |
| 11 | LC08_130038_20230626 | 2023-06-26 | 320638 | 316797 | eligible | train |
| 12 | LC08_130038_20230712 | 2023-07-12 | 0 | 0 | not_eligible | not_assigned |
| 13 | LC08_130038_20230728 | 2023-07-28 | 22439 | 22353 | eligible | train |
| 14 | LC08_130038_20230813 | 2023-08-13 | 287235 | 278254 | eligible | validation |
| 15 | LC08_130038_20230914 | 2023-09-14 | 300299 | 290373 | eligible | validation |
| 16 | LC08_130038_20230930 | 2023-09-30 | 133998 | 119296 | eligible | validation |
| 17 | LC08_130038_20231016 | 2023-10-16 | 203429 | 190519 | eligible | test |
| 18 | LC08_130038_20231101 | 2023-11-01 | 145538 | 129242 | eligible | test |
| 19 | LC08_130038_20231117 | 2023-11-17 | 94289 | 79524 | eligible | test |
| 20 | LC08_130038_20231203 | 2023-12-03 | 100 | 71 | eligible | test |
| 21 | LC08_130038_20231219 | 2023-12-19 | 24207 | 20527 | eligible | test |

## 5. 逐像元支持

- `observation_count` = 21
- `valid_count` 范围 = 0 – 12
- 全支持像元 = 0
- 零支持像元 = 64480

## 6. 边界与移交事项

- `model_eligible` 未裁决，属 Stage 7.2；本报告不拟合、不评分、不比较机制。
- split 一经冻结不得因模型表现重排；成员若日后未通过完整性检查，须显式修订协议与
  catalog，禁止静默替换或回填。
- **cos_i 边界**：唯一冻结的 cos_i 栅格是为 `LC08_130038_20230101` 的太阳几何所算，
  不得套用于其他 acquisition。`base_valid_land` 只依赖地形几何故不受影响，但逐景
  supported / unsupported 分类需要逐景太阳几何，属 Stage 7.2 范围。
- **待办**：registry 别名 `stage_7_1_terrain_stack` 指向 `data/terrain_stack`，目前为空。
  地形几何当前通过 `target-grid.yaml` 中按 sha256 钉住的 stage6.5 别名解析
  （dem / slope / aspect / cos_i，均 `exact_match: true`）。Stage 7.2 若需要独立地形栈，
  应在该节点显式建立，不应由本节点静默复制。
