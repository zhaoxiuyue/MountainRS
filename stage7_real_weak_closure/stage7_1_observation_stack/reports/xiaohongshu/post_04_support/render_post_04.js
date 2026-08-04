#!/usr/bin/env node
"use strict";

/* Deterministic renderer: 《还没训练 AI，数据已经可能被挑偏了》.
 * Read-only inputs: frozen Stage 7.1 evidence/config/data and this handoff.
 * Outputs only: reports/xiaohongshu/post_04*.
 */

const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const W = 1080;
const H = 1350;
const SCRIPT_DIR = __dirname;
const OUT = path.resolve(SCRIPT_DIR, "../post_04");
// post_04 is nested under the Stage 7.1 container; ../../../.. from OUT is
// not the repository root. Resolve directly to the container instead.
const CONTAINER = path.resolve(SCRIPT_DIR, "../../..");
const REL = (relative) => path.join(CONTAINER, relative);

const FILE = {
  brief: "reports/xiaohongshu/post_04_support/BRIEF.md",
  stack: "evidence/stack_manifest.json",
  support: "evidence/local-support-audit-v1.json",
  catalog: "data/raw/acquisition-catalog.json",
  attempts: "evidence/export-attempts-v3.jsonl",
  protocol: "docs/selection-protocol.md",
  grid: "configs/target-grid.yaml",
};
const C = { ink: "#111210", paper: "#FFF9E8", panel: "#FFFDF7", panel2: "#FFF3CF", yellow: "#F7D34E", orange: "#E54817", muted: "#5E605B", line: "#DDD3B9", green: "#23584C", greenSoft: "#D6E7DD", mountain1: "#F8E9B8", mountain2: "#F3DFA0" };

function fail(message) { throw new Error(message); }
function source(relative) { const full = REL(relative); if (!fs.existsSync(full)) fail(`Missing frozen source: ${relative}`); return full; }
function textFile(relative) { return fs.readFileSync(source(relative), "utf8"); }
function json(relative) { return JSON.parse(textFile(relative)); }
function jsonl(relative) { return textFile(relative).trim().split(/\r?\n/).filter(Boolean).map(JSON.parse); }
function same(actual, expected, label) { if (actual !== expected) fail(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`); }
function deepSame(actual, expected, label) { same(JSON.stringify(actual), JSON.stringify(expected), label); }
function esc(value) { return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function rect(x, y, w, h, fill, extra = "") { return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" ${extra}/>`; }
function rr(x, y, w, h, fill, r = 22, extra = "") { return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" ${extra}/>`; }
function line(x1, y1, x2, y2, stroke = C.line, width = 2) { return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${width}"/>`; }
function txt(x, y, value, size = 28, options = {}) { const { fill = C.ink, weight = 400, anchor = "start", family = "'PingFang SC','STHeiti','Arial Unicode MS',sans-serif", letter = 0, opacity = 1 } = options; return `<text x="${x}" y="${y}" font-family="${family}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}" letter-spacing="${letter}" opacity="${opacity}">${esc(value)}</text>`; }
function multi(x, y, values, size, h, options = {}) { return values.map((value, i) => txt(x, y + i * h, value, size, options)).join(""); }
function mono(x, y, value, size = 22, options = {}) { return txt(x, y, value, size, { family: "'Menlo','SF Mono','Courier New',monospace", ...options }); }
function marker(x, y, w, h = 50) { return `<path d="M ${x} ${y + 9} C ${x + w * .14} ${y - 1}, ${x + w * .32} ${y + 3}, ${x + w * .52} ${y + 7} C ${x + w * .72} ${y + 1}, ${x + w * .88} ${y + 4}, ${x + w} ${y + 8} L ${x + w - 8} ${y + h - 6} C ${x + w * .72} ${y + h + 2}, ${x + w * .34} ${y + h - 2}, ${x + 6} ${y + h - 4} Z" fill="${C.yellow}" opacity=".86"/>`; }
function underline(x, y, w) { return `<path d="M ${x} ${y} C ${x + w * .26} ${y - 5}, ${x + w * .57} ${y + 6}, ${x + w} ${y - 1}" fill="none" stroke="${C.yellow}" stroke-width="7" stroke-linecap="round"/>`; }
function mountain(y = 1170) { return `<path d="M 0 ${H} L 0 ${y + 145} C 120 ${y + 130},190 ${y + 79},284 ${y + 87} C 373 ${y + 94},452 ${y + 153},538 ${y + 138} C 625 ${y + 123},713 ${y + 56},795 ${y + 12} C 849 ${y - 18},883 ${y - 7},930 ${y + 29} C 985 ${y + 71},1030 ${y + 101},1080 ${y + 110} L 1080 ${H} Z" fill="${C.mountain1}" opacity=".72"/><path d="M 0 ${H} L 0 ${y + 167} C 136 ${y + 154},211 ${y + 116},290 ${y + 124} C 374 ${y + 133},454 ${y + 183},546 ${y + 162} C 637 ${y + 141},699 ${y + 112},765 ${y + 81} C 818 ${y + 56},863 ${y + 74},913 ${y + 105} C 972 ${y + 140},1029 ${y + 150},1080 ${y + 150} L 1080 ${H} Z" fill="${C.mountain2}" opacity=".64"/>`; }
function badge(x, y, label, fill = C.yellow, textFill = C.ink) { const w = Math.max(126, label.length * 19 + 40); return `${rr(x, y, w, 42, fill, 21)}${txt(x + 18, y + 29, label, 18, { fill: textFill, weight: 800 })}`; }
function page(title, subtitle, footer) { return `${rect(0, 0, W, H, C.paper)}${mountain()}${rr(5, 5, 1070, 1340, "none", 28, 'stroke="#F0E5C3" stroke-width="7"')}${txt(1018, 108, "“", 108, { fill: C.yellow, weight: 800, anchor: "end", opacity: .62 })}${txt(60, 144, title, 51, { weight: 800 })}${underline(60, 213, 144)}${txt(60, 193, subtitle, 24, { fill: C.muted, weight: 500 })}${txt(60, 1310, footer, 19, { fill: C.muted, weight: 500 })}`; }
function svg(contents) { return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><style>text { font-kerning: normal; }</style>${contents}</svg>`); }
function sourceEntry(sourceFile, fields, values = {}) { return { source_file: sourceFile, fields, values }; }
async function writeFigure(file, contents, composites = [], overlay = "") {
  const layers = [...composites];
  if (overlay) layers.push({ input: svg(overlay), left: 0, top: 0 });
  await sharp(svg(contents)).composite(layers).png().toFile(path.join(OUT, file));
}
async function scenePreview(relative, width, height, mode = "contrast") {
  const { data, info } = await sharp(source(relative)).raw().toBuffer({ resolveWithObject: true });
  const b4 = Buffer.alloc(info.width * info.height);
  for (let pixel = 0; pixel < b4.length; pixel += 1) b4[pixel] = data[pixel * info.channels];
  let image = sharp(b4, { raw: { width: info.width, height: info.height, channels: 1 } });
  image = mode === "weather" ? image.linear(1.25, -10).grayscale() : image.normalise().clahe({ width: 64, height: 64, maxSlope: 3 }).tint("#A6B19A");
  return image.resize(width, height, { fit: "cover", position: "centre" }).png().toBuffer();
}
function cellStrip(x, y, members, options = {}) {
  const { cell = 22, gap = 5, showEligibility = false } = options;
  return members.map((member, index) => {
    const cx = x + index * (cell + gap);
    const off = showEligibility && member.stack_eligible !== "eligible";
    const fill = off ? "#B8B8B1" : C.green;
    return `${rr(cx, y, cell, cell, fill, 4, `stroke="${off ? "#898B85" : C.green}" stroke-width="2"`)}${off ? `<path d="M ${cx + 5} ${y + 5} L ${cx + cell - 5} ${y + cell - 5} M ${cx + cell - 5} ${y + 5} L ${cx + 5} ${y + cell - 5}" stroke="#6C6E69" stroke-width="3" stroke-linecap="round"/>` : ""}`;
  }).join("");
}

function gather() {
  const brief = textFile(FILE.brief);
  const stack = json(FILE.stack);
  const support = json(FILE.support);
  const catalog = json(FILE.catalog);
  const attempts = jsonl(FILE.attempts);
  const protocol = textFile(FILE.protocol);
  const gridText = textFile(FILE.grid);
  const universe = stack.counts.universe;
  const eligible = stack.counts.eligible;
  const notEligible = stack.counts.not_eligible;
  const split = stack.split.counts;
  const stackBad = stack.members.filter((m) => m.stack_eligible === "not_eligible");
  const supportBad = support.members.filter((m) => m.stack_eligible === "not_eligible");
  const intents = attempts.filter((e) => e.event_type === "submission_intent");
  const ready = attempts.filter((e) => e.earth_engine_state === "READY");
  const completed = attempts.filter((e) => e.earth_engine_state === "COMPLETED");
  const frozenDate = (gridText.match(/frozen_date: "([^"]+)"/) || [])[1];
  const exportFreezeDate = (protocol.match(/frozen by user decision on (\d{4}-\d{2}-\d{2}) before any Stage 7\.1 Export task/) || [])[1];

  same(catalog.counts.cataloged, universe, "Cataloged count");
  same(catalog.counts.exportable, universe, "Exportable count");
  same(catalog.counts.incomplete, 0, "Incomplete catalog count");
  same(stack.members.length, universe, "Stack member count");
  same(stack.per_pixel_counts.observation_count, universe, "Per-pixel observation count");
  same(stack.members.filter((m) => m.stack_eligible === "eligible").length, eligible, "Eligible count");
  same(stackBad.length, notEligible, "Not-eligible count");
  same(split.train + split.validation + split.test, eligible, "Split sum");
  deepSame([split.train, split.validation, split.test], [10, 3, 5], "Split values");
  same(intents.length, universe, "Export intents");
  same(ready.length, universe, "READY events");
  same(completed.length, universe, "COMPLETED events");
  same(new Set(intents.map((e) => e.short_product_id)).size, universe, "Unique export intent products");
  same(new Set(ready.map((e) => e.task_id)).size, universe, "Unique READY task ids");
  same(new Set(completed.map((e) => e.task_id)).size, universe, "Unique COMPLETED task ids");
  same(stack.members.every((m) => m.target_grid_exact === true && typeof m.member_sha256 === "string"), true, "Exact-grid stack provenance");
  same(stackBad.every((m) => m.qa_clear_count === 0 && m.base_valid_land === 0), true, "Stack preregistered gate result");
  same(supportBad.every((m) => m.qa_clear_count === 0 && m.base_valid_land.qa_clear_included === 0), true, "Support-audit QA clear zeros");
  deepSame(stackBad.map((m) => m.system_time_start_utc.slice(0, 10)), ["2023-02-02", "2023-06-10", "2023-07-12"], "Stack not-eligible dates");
  deepSame(supportBad.map((m) => m.system_time_start_utc.slice(0, 10)), ["2023-02-02", "2023-06-10", "2023-07-12"], "Support-audit not-eligible dates");
  same(frozenDate, "2026-07-23", "Frozen grid date");
  same(exportFreezeDate, "2026-07-24", "Export-set protocol freeze date");
  if (!/^Status: \*\*frozen before any Stage 7\.1 GEE catalog query\*\*/m.test(protocol)) fail("Pre-query protocol freeze missing.");
  if (!protocol.includes("The choice is fixed before any new acquisition catalog is viewed.")) fail("Pre-inspection grid freeze missing.");
  if (!/No cloud, QA, residual, fit, validation, test or model-result criterion may remove,\s+replace or reorder a member\./.test(protocol)) fail("Complete export prohibition missing.");
  if (!brief.includes('不是"我嫌它质量差"') || !brief.includes("质量差被剔除")) fail("Brief wording guard missing.");

  const scenes = stack.members.map((m) => ({ ...m, relative: `data/raw/observation_stack/${m.member_relative_to_alias}` }));
  same(scenes.every((m) => fs.existsSync(source(m.relative))), true, "All 21 local observation rasters exist");
  return { universe, eligible, notEligible, split, stack, catalog, frozenDate, exportFreezeDate, scenes, bad: supportBad.map((m) => ({ date: m.system_time_start_utc.slice(0, 10), qaClear: m.qa_clear_count, baseValidLand: m.base_valid_land.qa_clear_included, id: m.short_product_id, relative: `data/raw/observation_stack/${m.member_relative_to_alias}` })) };
}

async function renderTextVersion(data) {
  const footer = `${data.universe} 景候选宇宙 / ${data.eligible} 景合格 / 标准冻结在看见第一景之前`;
  const figures = [];
  figures.push({
    file: "01_cover.png",
    claim: "21 个候选一景未挑；其中 3 景在导出前即可由预注册标准预见为不合格。",
    sources: [sourceEntry(FILE.catalog, ["counts.cataloged", "counts.exportable", "counts.incomplete"], { cataloged: data.catalog.counts.cataloged, exportable: data.catalog.counts.exportable, incomplete: data.catalog.counts.incomplete }), sourceEntry(FILE.stack, ["counts.universe", "counts.not_eligible"], { universe: data.universe, not_eligible: data.notEligible })],
    render: () => writeFigure("01_cover.png", `${rect(0, 0, W, H, C.paper)}${mountain()}${rr(5, 5, 1070, 1340, "none", 28, 'stroke="#F0E5C3" stroke-width="7"')}${txt(540, 650, String(data.universe), 620, { weight: 800, anchor: "middle" })}${txt(540, 840, "一景没挑", 82, { weight: 800, anchor: "middle" })}${txt(540, 968, `其中 ${data.notEligible} 景，我导之前就知道不合格。`, 37, { weight: 700, anchor: "middle", fill: C.orange })}`),
  });
  figures.push({
    file: "02_rules.png",
    claim: "目标网格在 2026-07-23 冻结，协议在任何 Stage 7.1 GEE catalog query 前冻结；完整导出集禁止以云、QA、残差、拟合、验证、测试或模型结果删除、替换、重排成员。",
    sources: [sourceEntry(FILE.protocol, ["Status pre-query freeze", "section 2 pre-inspection grid choice", "section 9.1 complete export-set prohibition"], { protocol_status: "frozen before any Stage 7.1 GEE catalog query" }), sourceEntry(FILE.grid, ["frozen_date", "selection_rationale.allowed[2]"], { frozen_date: data.frozenDate }), sourceEntry(FILE.catalog, ["counts.cataloged", "counts.exportable"], { cataloged: data.universe, exportable: data.universe })],
    render: () => writeFigure("02_rules.png", `${page("规矩：我为什么不能挑", "标准冻结在看见任何一景之前", footer)}${rr(60, 267, 276, 180, C.panel2, 25)}${txt(88, 320, "① 网格先冻结", 23, { weight: 800 })}${txt(88, 379, data.frozenDate, 34, { weight: 800, fill: C.orange })}${txt(88, 420, "还没看新目录", 20, { fill: C.muted, weight: 700 })}${txt(374, 365, "→", 38, { fill: C.orange, weight: 800, anchor: "middle" })}${rr(412, 267, 276, 180, C.panel, 25, `stroke="${C.line}" stroke-width="3"`)}${txt(440, 320, "② 协议冻结", 23, { weight: 800 })}${multi(440, 368, ["before any", "GEE catalog query"], 22, 31, { family: "'Menlo','SF Mono',monospace", weight: 800 })}${txt(726, 365, "→", 38, { fill: C.orange, weight: 800, anchor: "middle" })}${rr(764, 267, 256, 180, C.greenSoft, 25)}${txt(792, 320, "③ 再看目录", 23, { weight: 800 })}${txt(792, 382, `${data.universe} 景`, 46, { weight: 800, fill: C.green })}${txt(792, 420, "完整候选宇宙", 20, { fill: C.muted, weight: 700 })}${rr(60, 498, 960, 308, C.ink, 28)}${txt(92, 555, "完整导出集的铁律", 22, { fill: C.yellow, weight: 800, letter: 1 })}${multi(92, 618, ["禁止用 cloud / QA / residual / fit / validation", "/ test / model 移除、替换或重排", "任何一个导出集成员。"], 24, 39, { fill: "#FFF9E8", weight: 700, family: "'Menlo','SF Mono',monospace" })}${rr(60, 862, 960, 180, C.panel, 28, `stroke="${C.line}" stroke-width="3"`)}${marker(90, 891, 80)}${txt(108, 934, "所以", 27, { weight: 800 })}${multi(90, 989, [`那 ${data.notEligible} 景，即使预注册标准判定不合格，`, "也必须一景不落地导完。"], 32, 45, { weight: 800 })}`),
  });
  figures.push({
    file: "03_funnel.png",
    claim: "候选宇宙、成功获取、身份与语义完整、精确网格通过均为 21；仅 stack_eligible 根据预注册标准收窄为 18，并按 10/3/5 划分。",
    sources: [sourceEntry(FILE.stack, ["counts", "members[].target_grid_exact", "per_pixel_counts.observation_count", "split.counts", "split.N"], { universe: data.universe, eligible: data.eligible, not_eligible: data.notEligible, observation_count: data.stack.per_pixel_counts.observation_count, split: data.split }), sourceEntry(FILE.attempts, ["21 submission_intent / 21 READY / 21 COMPLETED task-status records"], { submitted: data.universe, ready: data.universe, completed: data.universe }), sourceEntry(FILE.catalog, ["counts.cataloged", "counts.exportable", "counts.incomplete"], { cataloged: data.universe, exportable: data.universe, incomplete: data.catalog.counts.incomplete })],
    render: () => writeFigure("03_funnel.png", `${page("这个漏斗，前四层不收窄", "不收窄本身就是结论：其余环节不淘汰成员", footer)}${badge(60, 265, "identity hash 已冻结")}${rr(120, 330, 840, 85, C.panel, 18, `stroke="${C.line}" stroke-width="3"`)}${txt(154, 385, "候选宇宙", 28, { weight: 800 })}${txt(926, 385, String(data.universe), 43, { weight: 800, anchor: "end" })}${rr(120, 430, 840, 85, C.panel, 18, `stroke="${C.line}" stroke-width="3"`)}${txt(154, 485, "成功获取", 28, { weight: 800 })}${txt(926, 485, String(data.universe), 43, { weight: 800, anchor: "end" })}${rr(120, 530, 840, 85, C.panel, 18, `stroke="${C.line}" stroke-width="3"`)}${txt(154, 585, "身份与语义完整", 28, { weight: 800 })}${txt(926, 585, String(data.universe), 43, { weight: 800, anchor: "end" })}${rr(120, 630, 840, 85, C.panel, 18, `stroke="${C.line}" stroke-width="3"`)}${txt(154, 685, "精确网格通过", 28, { weight: 800 })}${txt(926, 685, String(data.universe), 43, { weight: 800, anchor: "end" })}<path d="M 120 730 L 960 730 L 870 855 L 210 855 Z" fill="${C.panel2}" stroke="${C.orange}" stroke-width="5"/>${txt(250, 805, "stack_eligible", 31, { weight: 800 })}${txt(830, 805, String(data.eligible), 49, { weight: 800, fill: C.orange, anchor: "end" })}${multi(984, 755, ["只有一处", "允许淘汰"], 21, 31, { fill: C.orange, weight: 800 })}<path d="M 968 803 L 899 806" stroke="${C.orange}" stroke-width="4"/><path d="M 900 806 l 16 -10 M 900 806 l 16 10" stroke="${C.orange}" stroke-width="4" fill="none"/>${rr(210, 897, 660, 121, C.ink, 24)}${txt(320, 945, "train", 19, { fill: C.yellow, weight: 800, anchor: "middle" })}${txt(320, 989, String(data.split.train), 42, { fill: "#FFF9E8", weight: 800, anchor: "middle" })}${line(430, 920, 430, 995, "#484A45", 2)}${txt(540, 945, "validation", 19, { fill: C.yellow, weight: 800, anchor: "middle" })}${txt(540, 989, String(data.split.validation), 42, { fill: "#FFF9E8", weight: 800, anchor: "middle" })}${line(650, 920, 650, 995, "#484A45", 2)}${txt(760, 945, "test", 19, { fill: C.yellow, weight: 800, anchor: "middle" })}${txt(760, 989, String(data.split.test), 42, { fill: "#FFF9E8", weight: 800, anchor: "middle" })}${txt(540, 1080, `${data.universe} → ${data.universe} → ${data.universe} → ${data.universe} → ${data.eligible}`, 29, { weight: 800, anchor: "middle", fill: C.orange })}`),
  });
  figures.push({
    file: "04_cost_and_question.png",
    claim: "2023-02-02、2023-06-10、2023-07-12 三景 QA-clear 均为 0，并由预注册标准判定为不合格；结尾追问不要把难的真实世界当作应被主观去掉的低质量影像。",
    sources: [sourceEntry(FILE.support, ["members[].system_time_start_utc", "members[].qa_clear_count", "members[].base_valid_land.qa_clear_included", "members[].stack_eligible"], { not_eligible_members: data.bad }), sourceEntry(FILE.stack, ["counts.not_eligible", "members[].stack_eligible", "members[].base_valid_land"], { not_eligible: data.notEligible, eligibility_basis: "base_valid_land > 0" }), sourceEntry(FILE.protocol, ["section 3: stack_eligible requires base_valid_land > 0", "section 4 QA/support semantics"], { preregistered_gate: "base_valid_land > 0" })],
    render: () => writeFigure("04_cost_and_question.png", `${page("代价：三景完整地做完", "不是“质量差被剔除”，是预注册标准判定不合格", footer)}${rr(60, 260, 960, 318, C.panel, 28, `stroke="${C.line}" stroke-width="3"`)}${txt(96, 317, "它们是谁？", 25, { fill: C.muted, weight: 700 })}${rr(92, 346, 896, 60, C.panel2, 15)}${txt(122, 385, "日期", 21, { weight: 800 })}${txt(570, 385, "QA-clear 像元", 21, { weight: 800 })}${txt(936, 385, "判定", 21, { weight: 800, anchor: "end" })}${line(92, 431, 988, 431)}${txt(122, 471, data.bad[0].date, 27, { weight: 800, family: "'Menlo','SF Mono',monospace" })}${txt(570, 471, String(data.bad[0].qaClear), 32, { weight: 800, fill: C.orange })}${txt(936, 471, "预注册不合格", 23, { weight: 800, fill: C.orange, anchor: "end" })}${line(92, 492, 988, 492)}${txt(122, 532, data.bad[1].date, 27, { weight: 800, family: "'Menlo','SF Mono',monospace" })}${txt(570, 532, String(data.bad[1].qaClear), 32, { weight: 800, fill: C.orange })}${txt(936, 532, "预注册不合格", 23, { weight: 800, fill: C.orange, anchor: "end" })}${line(92, 553, 988, 553)}${txt(122, 593, data.bad[2].date, 27, { weight: 800, family: "'Menlo','SF Mono',monospace" })}${txt(570, 593, String(data.bad[2].qaClear), 32, { weight: 800, fill: C.orange })}${txt(936, 593, "预注册不合格", 23, { weight: 800, fill: C.orange, anchor: "end" })}${rr(60, 633, 960, 126, C.ink, 26)}${txt(92, 685, "不是“我嫌它质量差”。", 27, { fill: C.yellow, weight: 800 })}${txt(92, 730, "是预注册标准告诉我：它没有可用观测。", 25, { fill: "#FFF9E8", weight: 700 })}${marker(60, 819, 430)}${txt(78, 864, "真正该问的不是“要不要剔除”。", 33, { weight: 800 })}${multi(60, 946, ["剔除低质量影像，什么时候是在去噪，", "什么时候是在删掉最难的真实世界？"], 43, 61, { weight: 800 })}${txt(60, 1084, "最难的像元，恰恰可能是你要研究的对象。", 25, { fill: C.orange, weight: 800 })}`),
  });

  for (const figure of figures) await figure.render();
  const thumbs = await Promise.all(figures.map(async (figure, index) => ({ input: await sharp(path.join(OUT, figure.file)).resize(492, 615).png().toBuffer(), left: 24 + (index % 2) * 540, top: 24 + Math.floor(index / 2) * 639 })));
  await sharp({ create: { width: W, height: 1302, channels: 3, background: C.paper } }).composite(thumbs).png().toFile(path.join(OUT, "contact_sheet.png"));
  fs.writeFileSync(path.join(SCRIPT_DIR, "figure_sources.json"), `${JSON.stringify({ schema: "mountainrs-xiaohongshu-post-04-figure-sources-v3", rendering: { renderer: "render_post_04.js", dimensions: "1080x1350", numeric_policy: "Every displayed number is read from frozen Stage 7.1 evidence/config/data and checked before rendering. The script runs no model, Earth Engine operation, refit, or source mutation.", visual_system: "Warm paper, ink-black Chinese headlines, yellow narrative marker strokes, orange-red annotations, pale cards, and layered mountain silhouettes, continuing post 03.", funnel_rule: "The first four levels deliberately keep the same width. Only the preregistered stack_eligible gate narrows from 21 to 18.", wording_guard: "The three scenes are described as preregistered-standard not eligible, never as subjective low-quality removals." }, figures: figures.map(({ file, claim, sources }) => ({ file, claim, sources })) }, null, 2)}\n`);
}

async function render(data) {
  const footer = `${data.universe} 景候选宇宙 / ${data.eligible} 景合格 / 标准冻结在看见第一景之前`;
  const figures = [];

  const coverCell = 142;
  const coverGap = 6;
  const coverX = 25;
  const coverY = 435;
  const coverComposites = [];
  let coverOverlay = "";
  for (let index = 0; index < data.scenes.length; index += 1) {
    const scene = data.scenes[index];
    const x = coverX + (index % 7) * (coverCell + coverGap);
    const y = coverY + Math.floor(index / 7) * (coverCell + coverGap);
    let preview = await scenePreview(scene.relative, coverCell, coverCell, "contrast");
    if (scene.stack_eligible !== "eligible") preview = await sharp(preview).grayscale().modulate({ brightness: 0.62 }).blur(0.35).png().toBuffer();
    coverComposites.push({ input: preview, left: x, top: y });
    coverOverlay += rr(x, y, coverCell, coverCell, "none", 12, `stroke="${scene.stack_eligible === "eligible" ? "#F3E5BB" : "#666862"}" stroke-width="4"`);
    if (scene.stack_eligible !== "eligible") coverOverlay += `<path d="M ${x + 27} ${y + 27} L ${x + coverCell - 27} ${y + coverCell - 27} M ${x + coverCell - 27} ${y + 27} L ${x + 27} ${y + coverCell - 27}" stroke="#FFF9E8" stroke-width="10" stroke-linecap="round"/><circle cx="${x + coverCell / 2}" cy="${y + coverCell / 2}" r="46" fill="none" stroke="#FFF9E8" stroke-width="5" opacity=".88"/>`;
  }
  figures.push({
    file: "01_cover.png",
    claim: "21 份真实 SR_B4 观测构成全年矩阵，一景未挑；三份预注册不合格观测在其真实位置灰显并打叉。",
    sources: [
      sourceEntry(FILE.stack, ["counts.universe", "counts.not_eligible", "members[].member_relative_to_alias", "members[].stack_eligible", "members[].order"], { universe: data.universe, not_eligible: data.notEligible, actual_scene_files: data.scenes.map((scene) => scene.relative) }),
      sourceEntry(FILE.catalog, ["counts.cataloged", "counts.exportable", "candidates canonical order"], { cataloged: data.universe, exportable: data.universe }),
    ],
    render: () => writeFigure("01_cover.png", `${rect(0, 0, W, H, C.paper)}${mountain(1100)}${rr(5, 5, 1070, 1340, "none", 28, 'stroke="#F0E5C3" stroke-width="7"')}${txt(60, 330, String(data.universe), 350, { weight: 800 })}${txt(480, 218, "一景没挑", 70, { weight: 800 })}${txt(484, 272, "一整年 · 一景不落", 26, { fill: C.muted, weight: 700 })}${txt(540, 970, `其中 ${data.notEligible} 景，我导之前就知道不合格。`, 38, { fill: C.orange, weight: 800, anchor: "middle" })}${txt(540, 1030, "真实 SR_B4 观测 · 灰叉为预注册标准不合格", 19, { fill: C.muted, weight: 600, anchor: "middle" })}`, coverComposites, coverOverlay),
  });

  const timelineY = 535;
  figures.push({
    file: "02_rules.png",
    claim: "横向时间轴表达网格与查询协议先于看见数据；协议 §9 的完整导出集规则另于任何导出之前冻结。",
    sources: [
      sourceEntry(FILE.grid, ["frozen_date", "selection_rationale.allowed[2]"], { frozen_date: data.frozenDate }),
      sourceEntry(FILE.protocol, ["Status pre-query freeze", "section 2 pre-inspection grid choice", "section 9 amendment status", "section 9.1 complete export-set prohibition"], { protocol_status: "frozen before any Stage 7.1 GEE catalog query", export_set_frozen_date: data.exportFreezeDate }),
      sourceEntry(FILE.catalog, ["counts.cataloged", "counts.exportable"], { cataloged: data.universe, exportable: data.universe }),
    ],
    render: () => writeFigure("02_rules.png", `${page("规矩不是一句话，是先后顺序", "标准先冻结，数据后出现", footer)}${line(105, timelineY, 970, timelineY, C.ink, 5)}<path d="M 970 ${timelineY} l -18 -11 v22 Z" fill="${C.ink}"/>${line(190, 430, 190, 620, C.orange, 5)}${line(385, 455, 385, 595, C.orange, 5)}${line(650, 445, 650, 605, C.ink, 5)}${line(900, 455, 900, 595, C.green, 5)}${rr(90, 292, 200, 110, C.panel2, 22)}${txt(190, 329, "网格冻结", 24, { weight: 800, anchor: "middle" })}${txt(190, 372, data.frozenDate, 26, { fill: C.orange, weight: 800, anchor: "middle" })}${rr(300, 315, 210, 88, C.panel, 22, `stroke="${C.line}" stroke-width="3"`)}${txt(405, 350, "协议冻结", 24, { weight: 800, anchor: "middle" })}${txt(405, 380, "before query", 18, { fill: C.muted, weight: 700, anchor: "middle" })}<path d="M 580 ${timelineY} Q 650 470 720 ${timelineY} Q 650 600 580 ${timelineY} Z" fill="${C.panel}" stroke="${C.ink}" stroke-width="4"/><circle cx="650" cy="${timelineY}" r="22" fill="${C.ink}"/>${txt(650, 660, "看见数据", 30, { weight: 800, anchor: "middle" })}${rr(805, 315, 190, 88, C.greenSoft, 22)}${txt(900, 350, "首次查询目录", 23, { fill: C.green, weight: 800, anchor: "middle" })}${txt(900, 380, `${data.universe} 景全部出现`, 18, { fill: C.muted, weight: 700, anchor: "middle" })}${txt(190, 676, "都在左边", 19, { fill: C.orange, weight: 800, anchor: "middle" })}${txt(900, 676, "才在右边", 19, { fill: C.green, weight: 800, anchor: "middle" })}${rr(60, 746, 960, 228, C.ink, 28)}${txt(90, 790, `协议 §9 · ${data.exportFreezeDate}`, 21, { fill: C.yellow, weight: 800 })}${txt(382, 790, "冻结于任何导出之前", 21, { fill: "#FFF9E8", weight: 800 })}<circle cx="972" cy="785" r="22" fill="none" stroke="${C.orange}" stroke-width="4"/><path d="M 961 774 L 983 796 M 983 774 L 961 796" stroke="${C.orange}" stroke-width="4" stroke-linecap="round"/>${txt(90, 830, "这些字段可以记录，但不能决定谁被导出：", 22, { fill: "#FFF9E8", weight: 700 })}${rr(90, 850, 120, 50, "#F6C5B4", 25, `stroke="#FFF9E8" stroke-width="2"`)}${txt(150, 883, "cloud", 18, { weight: 800, anchor: "middle" })}${rr(228, 850, 94, 50, "#F6C5B4", 25, `stroke="#FFF9E8" stroke-width="2"`)}${txt(275, 883, "QA", 18, { weight: 800, anchor: "middle" })}${rr(340, 850, 200, 50, "#F6C5B4", 25, `stroke="#FFF9E8" stroke-width="2"`)}${txt(440, 883, "residual / fit", 18, { weight: 800, anchor: "middle" })}${rr(558, 850, 240, 50, "#F6C5B4", 25, `stroke="#FFF9E8" stroke-width="2"`)}${txt(678, 883, "validation / test", 18, { weight: 800, anchor: "middle" })}${rr(816, 850, 130, 50, "#F6C5B4", 25, `stroke="#FFF9E8" stroke-width="2"`)}${txt(881, 883, "model", 18, { weight: 800, anchor: "middle" })}${txt(540, 946, "不得决定导出集", 21, { fill: C.orange, weight: 800, anchor: "middle", letter: 2 })}${rr(60, 1000, 960, 104, C.panel2, 24)}${cellStrip(84, 1038, data.scenes, { cell: 24, gap: 5 })}${txt(840, 1060, `那 ${data.notEligible} 景，也在里面。`, 24, { fill: C.orange, weight: 800 })}`),
  });

  const row = (y, label, eligibleMode = false) => `${rr(50, y, 980, 74, eligibleMode ? C.panel2 : C.panel, 18, `stroke="${eligibleMode ? C.orange : C.line}" stroke-width="${eligibleMode ? 4 : 2}"`)}${txt(78, y + 46, label, 23, { weight: 800 })}${cellStrip(392, y + 25, data.scenes, { cell: 22, gap: 5, showEligibility: eligibleMode })}`;
  figures.push({
    file: "03_funnel.png",
    claim: `完整 ROI 几何层有权淘汰成员，但实际淘汰 ${data.catalog.counts.incomplete} 景；真正的淘汰发生在预注册 stack_eligible 标准，按真实成员位置熄灭 ${data.notEligible} 格。`,
    sources: [
      sourceEntry(FILE.protocol, ["section 1 complete target-ROI footprint rules", "section 9.1 complete export set"], { geometric_filter_is_catalog_admission: true }),
      sourceEntry(FILE.catalog, ["counts.cataloged", "counts.exportable", "counts.incomplete", "candidates canonical order"], { roi_complete: data.universe, exportable: data.universe, incomplete: data.catalog.counts.incomplete }),
      sourceEntry(FILE.attempts, ["21 submission_intent / READY / COMPLETED"], { completed: data.universe }),
      sourceEntry(FILE.stack, ["members[].target_grid_exact", "members[].stack_eligible", "split.counts"], { grid_exact: data.universe, eligible: data.eligible, split: data.split }),
    ],
    render: () => writeFigure("03_funnel.png", `${page("筛选发生在哪一层？", `几何层淘汰 ${data.catalog.counts.incomplete}；预注册标准淘汰 ${data.notEligible}`, footer)}${rr(60, 242, 315, 116, C.panel, 22, `stroke="${C.line}" stroke-width="3"`)}${txt(217, 276, "2023 年全部过境", 24, { weight: 800, anchor: "middle" })}${txt(217, 317, `${data.universe} 景`, 31, { fill: C.orange, weight: 800, anchor: "middle" })}${txt(217, 344, "Path 130 / Row 38", 15, { fill: C.muted, weight: 700, anchor: "middle" })}${line(375, 300, 685, 300, C.ink, 4)}<path d="M 685 300 l -16 -10 v20 Z" fill="${C.ink}"/>${rr(418, 245, 214, 40, C.panel2, 20)}${txt(525, 272, "这一层有权淘汰", 18, { fill: C.orange, weight: 800, anchor: "middle" })}${txt(525, 342, `实际淘汰 ${data.catalog.counts.incomplete} 景`, 21, { fill: C.orange, weight: 800, anchor: "middle" })}${rr(685, 242, 335, 116, C.greenSoft, 22)}${txt(852, 276, "完整覆盖 ROI", 24, { fill: C.green, weight: 800, anchor: "middle" })}${txt(852, 317, `${data.universe} 景`, 31, { fill: C.green, weight: 800, anchor: "middle" })}${txt(852, 344, "进入候选宇宙", 15, { fill: C.muted, weight: 700, anchor: "middle" })}${row(390, "完整覆盖 ROI")}${row(479, "成功获取")}${row(568, "身份与语义完整")}${row(657, "精确网格通过")}${row(760, "stack_eligible", true)}${txt(540, 880, `真正淘汰发生在 stack_eligible：${data.notEligible} 景`, 25, { fill: C.orange, weight: 800, anchor: "middle" })}${rr(210, 928, 660, 112, C.ink, 23)}${txt(320, 970, "train", 18, { fill: C.yellow, weight: 800, anchor: "middle" })}${txt(320, 1015, String(data.split.train), 38, { fill: "#FFF9E8", weight: 800, anchor: "middle" })}${line(430, 950, 430, 1020, "#484A45", 2)}${txt(540, 970, "validation", 18, { fill: C.yellow, weight: 800, anchor: "middle" })}${txt(540, 1015, String(data.split.validation), 38, { fill: "#FFF9E8", weight: 800, anchor: "middle" })}${line(650, 950, 650, 1020, "#484A45", 2)}${txt(760, 970, "test", 18, { fill: C.yellow, weight: 800, anchor: "middle" })}${txt(760, 1015, String(data.split.test), 38, { fill: "#FFF9E8", weight: 800, anchor: "middle" })}${txt(540, 1114, `${data.universe} → ${data.universe} → ${data.universe} → ${data.universe} → ${data.universe} → ${data.eligible}`, 31, { fill: C.muted, weight: 800, anchor: "middle" })}`),
  });

  const costComposites = [];
  for (let index = 0; index < data.bad.length; index += 1) costComposites.push({ input: await scenePreview(data.bad[index].relative, 286, 330, "weather"), left: 67 + index * 323, top: 307 });
  const costOverlay = data.bad.map((scene, index) => {
    const x = 67 + index * 323;
    return `${rr(x, 307, 286, 330, "none", 16, `stroke="#FFF9E8" stroke-width="4"`)}${rr(x + 12, 319, 112, 32, "#111210B8", 16)}${txt(x + 68, 342, "actual SR_B4", 14, { fill: "#FFF9E8", weight: 700, anchor: "middle" })}`;
  }).join("");
  figures.push({
    file: "04_cost_and_question.png",
    claim: "三份预注册不合格景以真实 SR_B4 影像并排展示；各自 QA-clear 像元均为 0，读者可直接看到冬雪与雨季云遮蔽。",
    sources: [
      sourceEntry(FILE.support, ["members[].system_time_start_utc", "members[].qa_clear_count", "members[].stack_eligible", "members[].member_relative_to_alias"], { not_eligible_members: data.bad }),
      ...data.bad.map((scene) => sourceEntry(scene.relative, ["actual SR_B4 raster displayed with one fixed stretch"], { date: scene.date, qa_clear_count: scene.qaClear })),
      sourceEntry(FILE.protocol, ["section 3 stack_eligible requires base_valid_land > 0", "section 4 QA/support semantics"], { preregistered_gate: "base_valid_land > 0" }),
    ],
    render: () => writeFigure("04_cost_and_question.png", `${page("代价：三景真的没法用", "先看真实观测，再看预注册判据", footer)}${rr(50, 272, 980, 468, C.panel, 28, `stroke="${C.line}" stroke-width="3"`)}${txt(210, 680, `${data.bad[0].date} · 冬雪`, 22, { weight: 800, anchor: "middle" })}${txt(533, 680, `${data.bad[1].date} · 雨季`, 22, { weight: 800, anchor: "middle" })}${txt(856, 680, `${data.bad[2].date} · 雨季`, 22, { weight: 800, anchor: "middle" })}${txt(210, 720, `QA-clear = ${data.bad[0].qaClear}`, 24, { fill: C.orange, weight: 800, anchor: "middle" })}${txt(533, 720, `QA-clear = ${data.bad[1].qaClear}`, 24, { fill: C.orange, weight: 800, anchor: "middle" })}${txt(856, 720, `QA-clear = ${data.bad[2].qaClear}`, 24, { fill: C.orange, weight: 800, anchor: "middle" })}${rr(60, 790, 960, 82, C.ink, 22)}${txt(90, 842, "预注册判据：base_valid_land > 0", 23, { fill: C.yellow, weight: 800 })}${txt(765, 842, "这三景都等于 0", 23, { fill: "#FFF9E8", weight: 700 })}${marker(60, 924, 420)}${txt(78, 968, "真正的拷问", 31, { weight: 800 })}${multi(60, 1035, ["剔除低质量影像，什么时候是在去噪，", "什么时候是在删掉最难的真实世界？"], 39, 57, { weight: 800 })}${txt(60, 1176, "最难的像元，恰恰可能是你要研究的对象。", 24, { fill: C.orange, weight: 800 })}`, costComposites, costOverlay),
  });

  for (const figure of figures) await figure.render();
  const thumbs = await Promise.all(figures.map(async (figure, index) => ({ input: await sharp(path.join(OUT, figure.file)).resize(492, 615).png().toBuffer(), left: 24 + (index % 2) * 540, top: 24 + Math.floor(index / 2) * 639 })));
  await sharp({ create: { width: W, height: 1302, channels: 3, background: C.paper } }).composite(thumbs).png().toFile(path.join(OUT, "contact_sheet.png"));
  fs.writeFileSync(path.join(SCRIPT_DIR, "figure_sources.json"), `${JSON.stringify({ schema: "mountainrs-xiaohongshu-post-04-figure-sources-v4", rendering: { renderer: "render_post_04.js", dimensions: "1080x1350", numeric_policy: "Every displayed number is read from frozen Stage 7.1 evidence/config/data and checked before rendering.", raster_policy: "Cover and cost cards display actual local SR_B4 rasters with deterministic display-only contrast stretches; no scientific values are recomputed.", visual_system: "Post 03 warm-paper system, with image-first evidence and restrained explanatory text.", funnel_rule: "The geometry layer is allowed to remove members but removes zero; all 21-cell rows stay the same width until the preregistered stack_eligible row extinguishes the three actual not-eligible positions." }, figures: figures.map(({ file, claim, sources }) => ({ file, claim, sources })) }, null, 2)}\n`);
}

async function main() { fs.mkdirSync(OUT, { recursive: true }); await render(gather()); process.stdout.write(`Rendered 4 visual-evidence post_04 cards and contact sheet to ${OUT}\n`); }
main().catch((error) => { process.stderr.write(`post_04 render failed: ${error.stack || error.message}\n`); process.exitCode = 1; });
