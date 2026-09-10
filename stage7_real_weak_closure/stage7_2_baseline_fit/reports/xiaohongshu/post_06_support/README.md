# MountainRS 小红书科研图卡 · Post 06

本目录把冻结的 Stage 7.2 几何许可边界与支持损失账本渲染为 4 张 1080 × 1350 PNG 图卡。它只读取既有 evidence、冻结子协议与简报，不执行模型、不重新拟合、不调用 Earth Engine，也不修改 `evidence/`、`configs/`、`docs/`、`scripts/` 或 PF3 状态。

## 输出

- `../post_06/01_cover.png`：0.92%“是下界，不是答案”的反直觉数字封面。
- `../post_06/02_half_the_shadow.png`：自阴影与未计算投射阴影的机制示意。
- `../post_06/03_two_problems.png`：当前已识别下界与重复性两个问题。
- `../post_06/04_frozen_contract.png`：冻结合同原文、乐观上界与落点。
- `../post_06/contact_sheet.png`：四张缩略总览。
- `figure_sources.json`：逐图来源、字段、读取值与派生值；输出目录另存一份同内容副本。

## 复现

从本目录运行：

```sh
NODE_PATH=/Users/zhaoxiuyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
  /Users/zhaoxiuyue/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node render_post_06.js
```

脚本出图前会校验：18 × 488,800 = 8,798,400；81,005 / 8,798,400 = 0.92%；35,525 + 45,480 = 81,005；最低太阳角与最低 lit 比例均对应 order 1、21；Mconf 只覆盖自阴影、五类未覆盖项、唯一禁令和“乐观上界”冻结原文；同时拒绝把 v1 的 76.26% 对比或“云雪”桶简称渲染进任何图卡。
