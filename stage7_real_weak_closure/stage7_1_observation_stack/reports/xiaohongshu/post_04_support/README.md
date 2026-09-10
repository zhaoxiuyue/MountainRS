# MountainRS 小红书科研图卡 · Post 04

本目录将冻结的 Stage 7.1 预注册选景与资格审计渲染为 4 张 1080 × 1350 PNG 图卡。它不会执行 Earth Engine、重新拟合、计算新结果，或修改 `evidence/`、`configs/`、`data/`、`docs/`。

## 输出

- `../post_04/01_cover.png`：封面。
- `../post_04/02_rules.png`：标准先冻结。
- `../post_04/03_funnel.png`：唯一允许淘汰的一层。
- `../post_04/04_cost_and_question.png`：三景的代价与拷问。
- `../post_04/contact_sheet.png`：4 张缩略总览。
- `figure_sources.json`：逐图来源、字段与读取值。

## 复现

从本目录运行：

```sh
NODE_PATH=~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
  ~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node render_post_04.js
```

脚本从 `stage7_1_observation_stack` 容器根解析证据路径；没有复用 post 03 的 `../../../..` 根深度。出图前会校验：21 个完整候选/导出/完成任务、18 个 `stack_eligible` 成员的 10/3/5 划分、三景 QA-clear=0、协议的预查询冻结与完整导出条款，以及网格冻结日期。
