# MountainRS 小红书科研图卡 · Post 07

本目录把冻结的 Stage 7.4 风险代理判定账本渲染为 4 张 1080 × 1350 PNG 图卡。它只读取既有 evidence、configs、docs、outputs 与前篇冻结证据，不重新拟合、不重算残差、不调用 Earth Engine，也不修改任何冻结证据区或 PF3 状态。

## 输出

- `../post_07/01_cover.png`：SR_B4 的 90 个主判定中，“有序”0、“方向相反”41 的大数字封面。
- `../post_07/02_exam_rules.png`：结果盲冻结的考试规则与唯一一条机制示意曲线。
- `../post_07/03_real_verdict_counts.png`：B4、B5 各 90 格的主判定计数，以及全部 720 个判定总账。
- `../post_07/04_frozen_season_ledger.png`：前篇边界、程序验收关卡与固定网格 75%→25% 配对结果的冻结账本。
- `../post_07/contact_sheet.png`：四张缩略总览。
- `figure_sources.json`：逐图来源、字段、读取值、派生值与视觉编码策略；输出目录另存一份同内容副本。

## 复现

从本目录运行：

```sh
NODE_PATH=~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
  ~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node render_post_07.js
```

脚本出图前会校验：180 个单元由 B4/B5 各 90 个组成；B4 主判定为 0/25/41/24/0，B5 主判定为 1/48/17/24/0，且每组严格合计 90；全部 720 个判定为 19/177/204/248/72；风险代理为 `1-cos_i`、按低分优先读取，五类 verdict 构成冻结闭集，并且残差结果没有在冻结前读取。

图 2 只画预注册机制，不画实测曲线；横轴明确标成保留比例从 100% 向更低，确保“先拒掉最危险的”与示意方向一致。图 3 的方格按类别聚合排布，不编码时间或空间顺序。

图 4 的 `114 / 93 / 21 / +18.3%` 不手填：脚本先核对冻结 risk-curve table 的 SHA-256，再只取 `unit_all_scored` 主曲线中 q=0.75 与 q=0.25 两个固定网格点均可达的配对。逐曲线计算 `100 × (MAE_q025 / MAE_q075 − 1)`，得到 114 条可比曲线、93 条上升、21 条下降；原始变化中位数为 18.2733791182489%，图面四舍五入为 +18.3%。程序侧同时校验审计裁决后的有效 3/0、17 项合成测试通过和六项 reconciliation PASS。
