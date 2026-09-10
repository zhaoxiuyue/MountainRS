# MountainRS 小红书科研图卡 · Post 05

本目录把冻结的 Stage 7.1 观测证据账本渲染为 4 张 1080 × 1350 PNG 图卡。它只读取既有 evidence、源码与本地 SR_B4 栅格，不执行模型、不重新拟合、不调用 Earth Engine，也不修改 `evidence/`、`configs/`、`docs/`、`data/`、`scripts/` 或 PF3 状态。

## 输出

- `../post_05/01_cover.png`：Post 04 中三份无支持观测放大为黄框三联画。
- `../post_05/02_same_18_different_dataset.png`：相同的 18 景有效证据，不同的证据账本。
- `../post_05/03_two_kinds_of_unseen.png`：passive 与 active 缺失事件的线性比例。
- `../post_05/04_falsifiable_attribution.png`：可证伪归因、半个答案与落点。
- `../post_05/contact_sheet.png`：四张缩略总览。
- `figure_sources.json`：逐图来源、字段、读取值与派生值；输出目录另存一份同内容副本。

## 复现

从本目录运行：

```sh
NODE_PATH=~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
  ~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node render_post_05.js
```

脚本出图前会校验：21＝18＋3、21 个 evidence membership 全部 included、三景 canonical order 为 3/10/12 且 QA-clear 均为 0、passive/active 为 5,980/7,905,703、派生比例 1,322 与 99.92%、18/21＝85.7%，以及 unsupported 记录不得作为 target、negative sample 或参与 loss。
