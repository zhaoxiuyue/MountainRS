# Stage 6.5｜真实 Landsat 观测压力测试

## 本容器做什么

Stage 6 的 toy 闭环通关后，用**真实** Landsat 单景 L2SR 数据压一遍：QA 掩膜怎么定、
真实太阳角下的 `cos_i` 怎么算、规范分区完不完整、以及——最关键的——**单景能不能切出
空间独立的 holdout**。

这是项目第一次碰真实观测数据，也是第一次被真实数据挡回来。

## 终态：`BLOCKED`

`6.5.3-B` 的确定性预检判 **BLOCKED**，原因是**独立候选 blocks 不足**：
两个场景都是 `calibration=1, holdout=0`，最小要求 2。

空间相关范围（reliable range）实测：clean_a 的 cos_i 806 m、b4 2016 m、b5 1613 m；
shadow_risk_b 的 cos_i 2438 m、b4 8125 m、b5 7719 m。**在单景 ROI 内，一个 block 都留不出来。**

**这个 BLOCKED 是 Stage 7.1 存在的理由**——多 acquisition 观测栈就是为了解决它。
引用本容器结论时，不要读成「方法失败」，要读成「单景这个证据形态不够」。

预检边界：未拟合三种机制、未评分 holdout、未计算 residual / risk–coverage、未形成最终实验结论。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `configs/` | `stage6_5_3_b.yaml`（冻结口径：`base_valid`、三分区、water bit 7 处理） |
| `data/` | 两个单景数据包 `clean_a`（干净景）与 `shadow_risk_b`（阴影风险景），各含 B4/B5/QA_PIXEL/metadata |
| `outputs/` | 两套网格上的 dem/slope/aspect/cos_i/qa_valid_mask/confidence/shadow_mask/near_zero_mask，及 `stage6_5_3_b/` |
| `evidence/` | `stage6_5_3_b/` — 预检证据 |
| `scripts/` | 三个 GEE 导出/审计 `.js`、两个本地检查 `.py`、`stage6_5_3_b_executor.py` 与 `_experiment.py` |
| `reports/` | 导出计划、本地检查、方法合同提案、实验报告；另有 `xiaohongshu/post_03*` 科研图卡 |

两个 `.py` 本地检查脚本的 shebang 指向 `miniforge3/bin/python`——那是解释器，不是定位根目录，
不违反规则第二条；但换机器时需要改。

## 依赖哪些兄弟容器与冻结件

- `../stage2_dem_terrain/` — DEM 与地形因子
- `../stage4_terrain_radiation_toy/` — `cos_i` 与 shadow/near_zero 的三分区口径
- `../stage5_gradient_friendly_model/` — `soft_weight` 的 `k=30` 经验基线（本容器明确它只是继承值）
- `../stage3_image_dem_alignment/` — **只作为被审计对象**，见 `reports/stage3_landsat_source_audit.md`；
  本容器起不再使用旧 composite

本容器的多数产物已登记进 `.pf/resource-registry.yaml`（alias 前缀 `clean_a_*`、`shadow_risk_b_*`、
`stage_6_5_*`），跨容器引用走 alias，不写死路径。

## 三条死路与一条暂停线（记录在 PF3 主线上）

- `Stage 6.5.0-X` 复杂 GEE shadow-risk 预筛审计 — 死路
- `Stage 6.5.1-X` 大 ROI + 0.95 单景 full-cover 强约束 — 死路
- `Stage 6.5.1-D` 缩小 ROI 的快速调试路线 — 已暂停

它们留在路线上不删，是为了让后来者知道这几条路走过且不通。
