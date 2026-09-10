# 山地遥感物理基座

在山地做遥感推断，标准假设会失效：坡面朝向决定它接收多少直射光，山峰会把阴影投到几公里外，
同一片地表在不同入射角下亮度可以差好几倍。这个仓库尝试为这种条件下的地表状态推断建立一个
**物理上说得通、可迁移、带不确定性**的基座。

不过，你在这里看到的多数结论是**否定的**。

---

## 这个仓库不寻常的地方

大部分研究仓库只留下走通了的那条路。这里留下的是全部——**包括三条死路、一个把自己判定为
无法开工的节点，和一份撤回了自己两条结论的审计**。

之所以能这样，是因为整个项目跑在一套预注册纪律上：判据在看结果之前冻结并绑定 SHA-256，
协议冻结的回执必须早于第一次读取结果，事后修订即使合法也照标「post-result」。这套东西的
代价是慢，好处是——**报告里的每个数字都能被追回到一份冻结件，包括那些难看的数字**。

如果你只有五分钟，看这三个文件就够了：

| 看什么 | 为什么值得看 |
|---|---|
| [`stage7_8_multidomain_evidence/evidence/screening-findings-v1.json`](stage7_real_weak_closure/stage7_8_multidomain_evidence/evidence/screening-findings-v1.json) 和 [`-v2.json`](stage7_real_weak_closure/stage7_8_multidomain_evidence/evidence/screening-findings-v2.json) | **两份都在。** v1 写了两条结论，v2 把它们全部撤回——一个 Earth Engine 的 reducer 在重采样后对离散类别失效，导致基准区被判成占比 1.1% 的「稀树草原」，而真实主导地类是占 46.1% 的草地。错误的发现不靠任何自动检查，只因为在准备裁决材料时坚持补可核查的事实底座。v1 没有被覆盖，因为覆盖等于抹掉证据 |
| [`stage7_8_multidomain_evidence/reports/multidomain-evidence-report-v1.md`](stage7_real_weak_closure/stage7_8_multidomain_evidence/reports/multidomain-evidence-report-v1.md) 第 6 节 | 一次**合法但仍被标记为污染**的修订。所有者在看到结果后新增了一条准入条件，裁决权属所有者、程序无瑕疵，执行记录照样标 `post_result`：「冻结时序约束的是『规则不得在看过结果后改动』，与改动方向无关，允许事后收紧等于允许事后按结果挑选。」更彻底的是下一句——七个候选的相关占比全在 0.0–0.1%，所以任何阈值都只淘汰同一个候选，**这次修订根本不影响结果。知道不影响，还是标了** |
| [`stage7_9_l3_closed_loop/evidence/activation-preflight-manifest-v1.json`](stage7_real_weak_closure/stage7_9_l3_closed_loop/evidence/activation-preflight-manifest-v1.json) | 一个节点判定**自己无法开工**。它拒绝把责任推给上游（「上游没有失效，它准确地完成了工作」），拒绝把既成事实包装成待决选项（「用 decision_required 会把一个客观事实伪装成待决事项」），并逐条堵死两条本可以蒙混过去的退路 |

---

## 主线走到哪了

物理链路自下而上：地形几何 → 光照与可见性 → 观测算子 → 状态反演。目前止步于**第三层**。

几个可以自己去核的结果：

- **加性天空漫射项没能通过检验。** 教科书写法，直觉上背阴坡的光就该来自天空散射。三个候选在
  180 个单元上跑完，中位改善 **+0.06%**，冻结门槛是 5%——差了近两个数量级。算子至今仍是最简
  形式 `rho_hat = alpha · mu`。→ [Stage 7.6 报告](stage7_real_weak_closure/stage7_6_optical_operator/reports/optical-operator-report-v1.md)

- **几何可见性判据只认一半的阴影。** `cos_i > 0.1` 只看坡面朝向，看不见邻峰投来的阴影。所以它
  给出的 0.92% 几何拒绝率是**下界，不是答案**。这个缺口是判据冻结那天一起写进合同的，不是后来
  被发现的。→ [Stage 7.2](stage7_real_weak_closure/stage7_2_baseline_fit/)

- **一个自建的风险排序代理，指反了。** 用 `1−cos_i` 给像元打危险分，先拒最危险的，看误差降不降。
  720 个判定里「有序」19 个，「方向相反」204 个。判定的五类闭集在读残差之前就冻结了，所以
  「方向相反」是合法结果，不许事后改分数。→ [Stage 7.4 报告](stage7_real_weak_closure/stage7_4_residual_reliability/reports/residual-reliability-report-v1.md)

- **跨域证据已备好，但还没有模型可以拿去测。** 五个相对基准存在真实断裂的山区、891 个合格观测、
  一套通过独立性与泄漏审计的 Sentinel-2 参考（603 对时间匹配）。→ [Stage 7.8 报告](stage7_real_weak_closure/stage7_8_multidomain_evidence/reports/multidomain-evidence-report-v1.md)

**当前状态：暂停。** 下一关需要的两样东西——已资格化的观测算子、已激活的状态——上游各交出了
一个空集，且都是正常执行、通过审计后的**有效负结果**。解锁需要项目外的新证据。

---

## 目录怎么读

```
stages/                      科研工作包区。每个 stage 是自足容器，各自带 README
stage7_real_weak_closure/    历史证据区。冻结不迁，字节不改
docs/                        架构文档，含四个版本的 PDF 与 SHA-256 校验
_ops/                        一次性整理的操作记录，搬前搬后全量哈希清单
```

**关于 `stage7_real_weak_closure` 这个名字**——它看着像「没做完」，其实是字面意思：这一段做的就是
*weak closure*（弱闭环），即在真实数据上把链路走通但不声称跨域泛化。它没有被改名，因为区内的
冻结合同与审计器是**按路径**引用它的，改名会让一批证据失去可追溯性。这个约束本身也写在项目
规则里。

进任何一个 stage 容器，先读它的 `README.md`——判据是只读它就能开工，不用翻目录考古。

每个容器内部按职能分槽：`configs/` 冻结件、`data/` 原始输入、`evidence/` 可复算证据、
`outputs/` 程序产物、`reports/` 人读报告、`scripts/` 代码、`docs/` 协议。

---

## 需要知道的边界

- **Stage 1–6 是 toy model**，用真实地形但观测是合成的，结论不可外推到真实数据。真实观测从
  Stage 6.5 开始，那一关的终态是 `BLOCKED`——单景切不出空间独立的 holdout，这正是 Stage 7.1
  转向多时相观测栈的原因。
- **所有结论限于单 ROI**（岷山）除非另有说明。空间折不是独立样本。
- 大部分 `outputs/` 不入 git，字节身份由 `evidence/` 里的 manifest 承担。
- 数据来自 Landsat 8/9 C2 L2SR、Sentinel-1 GRD、Sentinel-2 SR、SRTM，均经 Google Earth Engine 获取。

---

## 相关

- 架构文档 v3.3（PDF，含 SHA-256）→ [`docs/releases/`](docs/releases/)
- 这个项目的过程被写成了一个七篇的图文系列「**桑榆非晚 · 修补前**」，讲的都是同一件事：
  *一个看似合理的做法，换个视角就塌了*。从「背阴坡不是黑，是模型少了一项物理」开始，到
  「连『哪里更危险』也不能靠直觉」收尾。

## 许可

本仓库以 [CC BY 4.0](LICENSE) 发布——**署名即可自由使用，包括商用**。

用到这里的方法、判据、数据编排或结论时，请注明来源。

---

想聊可以私信。
