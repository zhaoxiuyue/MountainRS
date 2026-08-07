# Mconf 子协议 v1｜草案（待所有者批准）

- **状态：** `draft_pending_owner_approval` —— 未获批准前不得据此计算任何逐单元支持量或 alpha
- **合同依据：** Stage 7.2 合同 ②
- **建立日期：** 2026-08-07
- **批准后动作：** 状态改为 `frozen`，登记 registry 别名，方可执行合同 ③ 及其后

## 0. 为什么需要这份子协议

合同 ② 给了两条路：证明上游协议已唯一给出光学 Mconf，或者冻结一份经你批准的子协议。

**上游没有给。** 我把 Stage 7.0 的四份冻结文档（`baseline_spec.md`、`evaluation_protocol.md`、
`data_gap_report.md`、`leakage_audit.md`）逐份检查过，`Mconf` 一词一次都没有出现。
7.0 冻结的是一个二值支持代理：

```
supported                  := cos_i > 0.1
unsupported_by_direct_only := cos_i <= 0.1
```

所以走子协议路径。本子协议**不发明新阈值**，只把 7.0 已冻结的谓词提升为一个具名的、
有明确架构归属和明确覆盖边界的质量因子。

## 1. 架构归属（这条决定它将来怎么被用）

`Mconf` 是架构 v3 §3 六类可追溯质量因子中的 **`geometry_visibility` 单因子**。

它**不是** §9 已撤销的那个合成 confidence。v2 架构里 Mconf 是「总置信度」，v3 明确
「以六类可追溯质量因子取代单一 Mconf」。本子协议沿用 `Mconf` 这个名字只是为了与
Stage 7.2 合同文本对齐，其语义已经收窄为六因子之一。

**禁止**：与 `support_mask`、`sensor_quality`、`reconstruction_quality`、
`model_adequacy`、`output_uncertainty` 中任何一个合并，或被下游读作总置信度。
Stage 7.1-R 已交付的 `Msource`、`Mqa` 是独立因子，与本因子并列，不得互相冒充。

## 2. 定义

| 项 | 值 |
|---|---|
| 因子名 | `Mconf`（= `geometry_visibility`） |
| 粒度 | acquisition × world position（冻结 ROI 上逐像元） |
| 值域 | `{1, 0}` |
| 判定 | `Mconf = 1` 当且仅当 `cos_i > 0.1`；否则 `Mconf = 0` |
| 阈值来源 | Stage 7.0 `baseline_spec.md` 冻结的 `supported := cos_i > 0.1`，**非本节点新增** |
| 输入 | `evidence/cos-i-registry-v1.json` 登记的 21 个 cos_i 栅格（逐景 sha256 已记录） |
| 结果无关性 | 拟合前确定，不依赖任何 residual、alpha、split 或模型结果 |

`cos_i` 的公式、角度约定与地形身份见 `evidence/cos-i-registry-v1.json`，其中 order 1
的复算已位级复现 Stage 6.5 冻结栅格（`afb0728e…`，max_abs_difference = 0.0）。

### 原因标签（闭集）

| 标签 | 谓词 | 顶层归属 |
|---|---|---|
| `mconf_lit` | `cos_i > 0.1` | 不是剥夺 |
| `mconf_zero_near_zero` | `0 < cos_i <= 0.1` | `active` |
| `mconf_zero_self_shadow` | `cos_i <= 0` | `active` |

三分区口径沿用 Stage 7.0 `data_gap_report.md`，非本节点新增。

按 Stage 7.2 合同 ⑦，`Mconf = 0` 统一构成 `mconf_mechanism_zero`，须登记为
Stage 7.1-R `validity-support-schema-v1.json` 中 **`active` 桶下的新细分类**
（几何机制拒绝），走该 schema 自身规定的修订流程，**不另立平行标签体系**。
映射到架构 v3 §3 的来源类别为 `unsupported`。

## 3. 覆盖边界（这一节是本子协议最重要的部分）

`cos_i > 0.1` **只覆盖自阴影**（self-shadowing，由局部入射角决定：坡面背向太阳）。

**以下全部未覆盖**，本子协议不量化、不近似、不以任何方式声称已处理：

| 未覆盖项 | 说明 | 归属 |
|---|---|---|
| 地形投射阴影 | 山脊在远处坡面上投下的阴影。该处 `cos_i` 可以远大于 0.1，却完全照不到直射光 | Stage 7.5 / 7.6 |
| 地平线遮挡 | 同上的一般形式，需要沿太阳方位角做地平线角计算 | Stage 7.5 / 7.6 |
| 去遮挡边界 | 几何变化导致的可见性翻转区域 | Stage 7.6，架构 §7 H |
| 几何不稳定边界 | 陡崖、断崖处 DEM 本身的几何不确定性 | Stage 7.6，架构 §7 F |
| 观测视角遮挡 | Landsat 8 近天底观测（视角 < 7.5°），本版按近天底处理，不做视角遮挡 | 多角度传感器接入时再议 |

**因此，结论中不得出现「几何可见性已覆盖」「遮挡已处理」一类表述。**
本因子只能被称为「自阴影许可量」。架构 §7 A（遮挡边界的信息缺口）在本阶段仍然完全打开。

这个缺口有实际后果：低太阳角的景（order 1 仰角 31.14°、order 21 仰角 31.32°）投射阴影
最严重，而它们恰好是 `cos_i` 判定 lit 比例最低的景（73.5%、73.8%）——真实的可用区域
只会比这更小，**不会更大**。本子协议因此在几何上是**乐观**的，任何基于它的支持计数
都应理解为上界。

## 4. 可复算方法

```
输入：evidence/cos-i-registry-v1.json 中该 acquisition 的 cos_i 栅格（按 sha256 验明）
输出：uint8 栅格，1 = Mconf 许可，0 = 拒绝；地形无效处为 nodata
判定：Mconf = (cos_i > 0.1) 且 cos_i 有效
```

本 ROI 上地形有效像元为全部 488,800，故不存在 `Mconf = undefined` 的位置。

逐景生成 Mconf 身份与 sha256，登记入 `evidence/mconf-registry-v1.json`。

## 5. 与 calibration-lit 的关系

**二者不是一回事，即使当前数值可由前者推出后者。**

- `Mconf`：纯几何许可，与观测有效性无关。同一像元在阴天和晴天的 Mconf 完全相同。
- `calibration-lit`：标定支持集，引用 Mconf **并叠加**观测有效性（`base_valid_land`）。

`calibration-lit` 的正式定义属于合同 ③ 的 calibration contract，不在本子协议内。
本子协议只声明：calibration-lit 必须引用 Mconf，且**不得反过来用 calibration-lit 的
规模去调整 Mconf 的阈值**。

## 6. 本子协议不做的事

不计算 cos_i 之外的任何几何量；不引入投射阴影或地平线算法；不改变 `0.1` 这个阈值；
不定义 calibration-lit、alpha、置信度、reliability 或 risk–coverage；不裁决任何景的
model_eligible；不改变 evidence membership、split、ROI 或网格。

---

## 待你批准的事项

**只有一项：确认 Mconf v1 = `cos_i > 0.1`，且接受它只覆盖自阴影这一边界。**

批准即意味着接受：本阶段的几何支持是**乐观上界**，投射阴影造成的高估留到 Stage 7.5 / 7.6
才会被量化和修正，其间所有基于 Mconf 的支持计数都带这个已知偏差。

如果你认为投射阴影必须在本阶段就处理，那是另一条路——需要新增地平线计算，
超出 Stage 7.2 合同 boundaries「不加自由度」的范围，应当作为独立节点插入。
