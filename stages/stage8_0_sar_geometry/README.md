# Stage 8.0｜SAR L0 证据与斜距几何算子

> **当前状态：`planned`，未激活。** 容器内目前只有一份只读的激活预检裁决。
> 本 README 是预检产出的一部分，写在激活之前，用于让下一个窗口只读它即可开工。

## 本容器做什么

建立 SAR observation schema、世界坐标到斜距观测的几何映射，以及 SAR 专属的可见性/失效域，
为后续 Stage 8.1 的辐射算子提供**已资格化的 L0/L2 几何入口**。

核心工作是**纯几何**：输入是轨道状态矢量、成像时刻与 DEM，输出是斜距映射与三类失效域
（layover、foreshortening、radar shadow）。这部分**不需要任何 SAR 像素**。SAR 像素只在
passCriteria 4 的对齐验证环节被用到——这个区分是 B1 能判 ready 而非 blocked 的全部理由。

**本节点不做**：后向散射状态反演、粗糙度激活、InSAR 形变、未经物理约束的光学-SAR 翻译。

## 产物落在哪个槽

| 槽 | 内容 |
|---|---|
| `evidence/` | `activation-preflight-manifest-v1.json`（**已有**，只读预检裁决，outcome = `activation_preflight_ready`）。后续：结果盲声明、冻结 manifest、对齐验证证据 |
| `configs/` | 待产出：observation schema、几何映射参数、失效域判据与阈值 |
| `data/` | 待产出：S1 GRD 原始输入（若最终取像素） |
| `outputs/` | 待产出：斜距映射栅格、三类失效域掩膜、visibility factors |
| `scripts/` | 待产出：几何算子实现、fail-closed 测试 |
| `reports/` | 待产出：alignment report |
| `docs/` | 待产出：人读协议 |

容器内代码定位根目录只许用「从自己往上数 N 层」，不写仓库名、容器名或绝对路径（项目规则第二条）。

## 依赖哪些兄弟容器与冻结件

**本容器有一处跨区引用，须显式登记为例外。** 按项目规则第二条，工作包区 `stages/<stage>/`
的容器「跨 stage 只引用兄弟容器，不跳出工作包区」。但本节点必须引用历史证据区
`stage7_real_weak_closure/` 内的冻结件——该区是 Stage 7.x 的容器所在地，冻结不迁。

**该例外按规则第三条走唯一的间接层解析：`.pf/resource-registry.yaml`。**
下列 alias 已登记；**代码中一律用 alias，不得写死路径**。hash 是执行手在 2026-09-10 的主张，
用前自行复验：

| alias | 提供什么 | sha256 |
|---|---|---|
| `stage_7_6_svf_geometry_gate` | v_sky 的算法与冻结参数：N\* = 36 方位、D\* = 10000 m、含地球曲率 | `b6155cf4034cf2…` |
| `stage_7_6_v_sky_roi_grid` | 冻结的单 ROI v_sky 栅格 | `8444955a0dc40e…` |
| `stage_7_6_dem_extension_provenance` | 外扩 DEM 的获取参数与可复现性凭据 | `5042df8be408d3…` |
| `stage_7_7_geometry_propagation` | 几何失效传播机制与 `consumer_registry` | `b5bcfb7bf14488…` |
| `stage_7_8_domain_split_manifest` | 五域 + 基准的 domain/split 冻结 manifest | `6a54eb0b6c3c18…` |
| `stage_7_8_reference_registry` | Sentinel-2 判 `reference_observation` 的独立性与泄漏审计 | `e85eb8007bd571…` |
| `stage_7_8_domain_dem_cache` | 五域外扩 10 km DEM 缓存（本机派生物，不入 git） | 目录，逐文件复验 |

## 激活时必须处置的三件事

预检判 ready，但 ready 以下述三项**被显式承接**为条件。它们必须在激活时即被接住，
不能等写验证报告时才发现。完整论证见 `evidence/activation-preflight-manifest-v1.json`。

**B1｜GRD 已被 SRTM 正射校正，与本项目共享同一 DEM——这构成对 passCriteria 4 的循环性。**
GEE 的 `COPERNICUS/S1_GRD` 元数据含 `S1TBX_SAR_Processing_vers = 7.0.2` 与
`SNAP_Graph_Processing_Framework_GPF_vers = 7.0.3`，即已经 SNAP 流水线的
Range-Doppler terrain correction，所用 DEM 为 SRTM 30。用它验证我们自己用同一 SRTM 建的
几何映射，两者共享 DEM 与相近的几何模型，一致性会系统性偏高、边界误差被低估。
这与 Stage 7.8 的 I3/I4 是同一类问题：用一个未经本项目验证的地形假设去验证另一个。

处置要求：① 执行时显式声明该循环性，**不得把与 GRD 的对齐一致性报告为独立验证**；
② 边界误差须标注为「共享 DEM 条件下的**下界估计**」，不是绝对精度；
③ 若需独立验证须取未经地形校正的 SLC——GEE 不提供，可得途径为 ASF DAAC 或
Copernicus Data Space Ecosystem。**该获取属 `external_dependency`，须另行裁决，本预检未授权。**

**B2｜SAR 失效机制不得复用光学的 shadow/mask 名称或语义。**
radar shadow 由视线方向的地形遮挡决定并与入射角强相关，光学自阴影由太阳方向决定；
layover 与 foreshortening 在光学中无对应概念。沿用光学名称会使两套失效域在下游被误当作
同一事物合并。须在 observation schema 中为三类 SAR 失效建立**独立命名与独立 reason code**。

并且须在 `stage_7_7_geometry_propagation` 的 `consumer_registry` 中**登记为新的消费者**并声明
影响半径。该 registry 目前只有光学链路的四个消费者（slope 30 m、aspect 30 m、cos_i 30 m、
v_sky 10000 m）。遇到未登记的消费者会按 `UnregisteredConsumer` 停机，且未声明半径者
一律按 unbounded 处理并 fail closed——**这是预期行为，不是故障**。

**B3｜「G 默认锁定」这一前提须逐条复核。**
SAR 几何算子以 DEM 为输入但**不得反过来调整它**。若执行中出现「调整 DEM 可改善对齐」的
情形，须停机登记而非调整——那属于联合更新 G 与观测算子，被架构 §1.4 拒绝律禁止。
交叉引用：Stage 7.5 已将 `cos_i` 归 E 类，其归类以「G 保持锁定」为条件；本节点若动摇该前提，
须触发 `cos_i` 的重分类，而不是默默继续。

## 两件容易读错的事

**其一，本容器落在 `stages/` 而不是 `stage7_real_weak_closure/`，是规则结论不是偏好。**
历史证据区冻结不迁（规则第一条）。Stage 7.x 的容器留在其中，是因为它们被区内的冻结合同与
审计器**按路径引用**。Stage 8 是新阶段，无此约束，故按规则第二条落于工作包区。

**其二，SAR 覆盖零缺失不等于 passCriteria 1 已满足。**
预检核到六个 domain（含基准）的 Sentinel-1 场景数为 499–895，全部 IW 模式、升降轨齐备、
极化含 VV 与 VV+VH，`missing_domains = []`。但这只是**资源层面**已满足；passCriteria 1 还要求
逐一登记并冻结身份/hash，那要等激活后执行。另外 S1_GRD 的 `angle` 波段是**正射校正后的
椭球入射角，不是局部入射角**——后者须由 DEM 与轨道几何自行计算，正是 passCriteria 3 的
工作内容，不可直接取用该波段代替。
