# MountainRS 小红书科研图卡

本目录只包含基于已冻结 C5-D3 结果生成的传播图。它不执行模型、不重新拟合、不修改实验报告、scalar results、evidence 或任何 PF2 状态。

## 文件

- `01_cover.png` 至 `06_conclusion.png`：6 张 1080 × 1350（4:5）PNG 图卡。
- `contact_sheet.png`：6 张图的缩略图总览。
- `figure_sources.json`：每张图使用的相对 source file、字段与数值。
- `render_post_03.js`：确定性渲染脚本。

## 视觉约定

- 延续前两篇：暖米白 `#FFF9E8` 纸张、墨黑 `#111210` 标题、黄色 `#F7D34E` 荧光笔、橙红 `#E54817` 批注与浅黄色山形。
- 图表仍使用克制的灰、橙、橙红方法色；黄笔刷只承担叙事强调，不编码实验数值。
- 图 01–02 的底图明确为 **actual observation**：已存在的 Landsat L2 SR B4 GeoTIFF，叠加 C5-D3 canonical masks。
- 图 03 标为 **SCHEMATIC**；图 04–06 是冻结 scalar results 的描述性传播图，不是新实验。
- 中文使用 Arial Unicode / STHeiti 的可嵌入 Unicode 字体族进行光栅化；最终 PNG 不依赖阅读设备字体。
- 所有图统一页脚：`2 acquisitions / 10 spatial challenges；空间折不是独立统计重复`。

## 复现

在具备 Node.js 18+ 与 `sharp` 0.34+ 的环境中、从本目录运行：

```sh
NODE_PATH=<sharp 所在 node_modules> node render_post_03.js
```

脚本会先校验 run ID、WARNING verdict、六个 80% coverage 中位数、四个局部 B5 MAE 与三类诊断总数，再写出 PNG、contact sheet 与 source 清单。它只读取相对路径下的正式 C5-D3 文件，不会写入实验目录、evidence 或 PF2。
