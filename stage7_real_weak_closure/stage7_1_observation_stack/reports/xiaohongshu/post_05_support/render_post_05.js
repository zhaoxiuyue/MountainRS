#!/usr/bin/env node
"use strict";

/* Deterministic renderer: 《那3景，我最后还是留下了》.
 * Read-only inputs: frozen Stage 7.1 evidence, source code, and local rasters.
 * Outputs only: reports/xiaohongshu/post_05*.
 */

const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const W = 1080;
const H = 1350;
const SCRIPT_DIR = __dirname;
const OUT = path.resolve(SCRIPT_DIR, "../post_05");
const CONTAINER = path.resolve(SCRIPT_DIR, "../../..");
const REL = (relative) => path.join(CONTAINER, relative);

const FILE = {
  brief: "reports/xiaohongshu/post_05_support/BRIEF.md",
  manifest: "evidence/observation-evidence-manifest-v1.json",
  ledger: "evidence/observation-support-ledger-v1.json",
  directView: "evidence/stage-7.2-direct-only-input-view-v1.json",
  builder: "scripts/build_observation_evidence_v1.py",
};

const C = {
  ink: "#111210",
  paper: "#FFF9E8",
  panel: "#FFFDF7",
  panel2: "#FFF3CF",
  yellow: "#F7D34E",
  orange: "#E54817",
  muted: "#5E605B",
  line: "#DDD3B9",
  green: "#23584C",
  greenSoft: "#D6E7DD",
  pink: "#F6C5B4",
  mountain1: "#F8E9B8",
  mountain2: "#F3DFA0",
};

function fail(message) { throw new Error(message); }
function source(relative) {
  const full = REL(relative);
  if (!fs.existsSync(full)) fail(`Missing frozen source: ${relative}`);
  return full;
}
function textFile(relative) { return fs.readFileSync(source(relative), "utf8"); }
function json(relative) { return JSON.parse(textFile(relative)); }
function same(actual, expected, label) {
  if (actual !== expected) fail(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
}
function deepSame(actual, expected, label) { same(JSON.stringify(actual), JSON.stringify(expected), label); }
function esc(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;");
}
function rect(x, y, w, h, fill, extra = "") { return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" ${extra}/>`; }
function rr(x, y, w, h, fill, r = 22, extra = "") { return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" ${extra}/>`; }
function line(x1, y1, x2, y2, stroke = C.line, width = 2, extra = "") { return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${width}" ${extra}/>`; }
function txt(x, y, value, size = 28, options = {}) {
  const {
    fill = C.ink,
    weight = 400,
    anchor = "start",
    family = "'PingFang SC','STHeiti','Arial Unicode MS',sans-serif",
    letter = 0,
    opacity = 1,
  } = options;
  return `<text x="${x}" y="${y}" font-family="${family}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}" letter-spacing="${letter}" opacity="${opacity}">${esc(value)}</text>`;
}
function multi(x, y, values, size, h, options = {}) { return values.map((value, index) => txt(x, y + index * h, value, size, options)).join(""); }
function mono(x, y, value, size = 20, options = {}) { return txt(x, y, value, size, { family: "'Menlo','SF Mono','Courier New',monospace", ...options }); }
function marker(x, y, w, h = 48) {
  return `<path d="M ${x} ${y + 9} C ${x + w * 0.14} ${y - 1}, ${x + w * 0.32} ${y + 3}, ${x + w * 0.52} ${y + 7} C ${x + w * 0.72} ${y + 1}, ${x + w * 0.88} ${y + 4}, ${x + w} ${y + 8} L ${x + w - 8} ${y + h - 6} C ${x + w * 0.72} ${y + h + 2}, ${x + w * 0.34} ${y + h - 2}, ${x + 6} ${y + h - 4} Z" fill="${C.yellow}" opacity=".86"/>`;
}
function underline(x, y, w) {
  return `<path d="M ${x} ${y} C ${x + w * 0.26} ${y - 5}, ${x + w * 0.57} ${y + 6}, ${x + w} ${y - 1}" fill="none" stroke="${C.yellow}" stroke-width="7" stroke-linecap="round"/>`;
}
function mountain(y = 1180) {
  return `<path d="M 0 ${H} L 0 ${y + 145} C 120 ${y + 130},190 ${y + 79},284 ${y + 87} C 373 ${y + 94},452 ${y + 153},538 ${y + 138} C 625 ${y + 123},713 ${y + 56},795 ${y + 12} C 849 ${y - 18},883 ${y - 7},930 ${y + 29} C 985 ${y + 71},1030 ${y + 101},1080 ${y + 110} L 1080 ${H} Z" fill="${C.mountain1}" opacity=".72"/><path d="M 0 ${H} L 0 ${y + 167} C 136 ${y + 154},211 ${y + 116},290 ${y + 124} C 374 ${y + 133},454 ${y + 183},546 ${y + 162} C 637 ${y + 141},699 ${y + 112},765 ${y + 81} C 818 ${y + 56},863 ${y + 74},913 ${y + 105} C 972 ${y + 140},1029 ${y + 150},1080 ${y + 150} L 1080 ${H} Z" fill="${C.mountain2}" opacity=".64"/>`;
}
function page(title, subtitle, footer, options = {}) {
  const { titleSize = 49 } = options;
  return [
    rect(0, 0, W, H, C.paper),
    mountain(),
    rr(5, 5, 1070, 1340, "none", 28, 'stroke="#F0E5C3" stroke-width="7"'),
    txt(1018, 108, "“", 108, { fill: C.yellow, weight: 800, anchor: "end", opacity: 0.62 }),
    txt(60, 144, title, titleSize, { weight: 800 }),
    txt(60, 193, subtitle, 24, { fill: C.muted, weight: 500 }),
    underline(60, 213, 144),
    txt(60, 1310, footer, 18, { fill: C.muted, weight: 500 }),
  ].join("");
}
function svg(contents) {
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><style>text { font-kerning: normal; }</style>${contents}</svg>`);
}
function sourceEntry(sourceFile, fields, values = {}) { return { source_file: sourceFile, fields, values }; }
async function writeFigure(file, contents, composites = [], overlay = "") {
  const layers = [...composites];
  if (overlay) layers.push({ input: svg(overlay), left: 0, top: 0 });
  await sharp(svg(contents)).composite(layers).png().toFile(path.join(OUT, file));
}
async function scenePreview(relative, width, height) {
  const { data, info } = await sharp(source(relative)).raw().toBuffer({ resolveWithObject: true });
  const b4 = Buffer.alloc(info.width * info.height);
  for (let pixel = 0; pixel < b4.length; pixel += 1) b4[pixel] = data[pixel * info.channels];
  return sharp(b4, { raw: { width: info.width, height: info.height, channels: 1 } })
    .normalise()
    .clahe({ width: 64, height: 64, maxSlope: 3 })
    .tint("#A6B19A")
    .resize(width, height, { fit: "cover", position: "centre" })
    .png()
    .toBuffer();
}

function evidenceGrid(x, y, members, options = {}) {
  const { columns = 7, cell = 34, gap = 8, highlightUnsupported = false } = options;
  return members.map((member, index) => {
    const cx = x + (index % columns) * (cell + gap);
    const cy = y + Math.floor(index / columns) * (cell + gap);
    const unsupported = member.target_surface_support_status === "zero_base_valid_land";
    if (highlightUnsupported && unsupported) {
      return rr(cx, cy, cell, cell, C.panel, 6, `stroke="${C.yellow}" stroke-width="5"`);
    }
    return rr(cx, cy, cell, cell, C.green, 6, `stroke="${C.green}" stroke-width="2"`);
  }).join("");
}

function gather() {
  const brief = textFile(FILE.brief);
  const manifest = json(FILE.manifest);
  const ledger = json(FILE.ledger);
  const directView = json(FILE.directView);
  const builderText = textFile(FILE.builder);
  const counts = manifest.counts;
  const universe = counts.member_count;
  const supported = counts.target_surface_supported_somewhere;
  const unsupported = counts.target_surface_zero_base_valid_land;
  const included = counts.evidence_membership_included;
  const passive = ledger.deprivation_totals.top_level_mutually_exclusive.passive;
  const active = ledger.deprivation_totals.top_level_mutually_exclusive.active;
  const deprivationTotal = passive + active;
  const ratio = Math.round(active / passive);
  const keptSuccess = Number((supported / universe * 100).toFixed(1));
  const activeShare = Number((active / deprivationTotal * 100).toFixed(2));
  const members = [...manifest.members].sort((a, b) => a.order - b.order);
  const unsupportedMembers = members.filter((member) => member.target_surface_support_status === "zero_base_valid_land");
  const supportedMembers = members.filter((member) => member.target_surface_support_status === "supported_somewhere");
  const unsupportedRecords = [...directView.unsupported_records].sort((a, b) => a.order - b.order);
  const training = manifest.training_semantics;
  const codeLines = builderText.split(/\r?\n/).slice(467, 472);

  deepSame([universe, included, supported, unsupported], [21, 21, 18, 3], "Manifest counts");
  same(supported + unsupported, universe, "21 = 18 + 3");
  same(members.length, universe, "Manifest member length");
  same(members.every((member) => member.evidence_membership === "included"), true, "All evidence members included");
  deepSame(unsupportedMembers.map((member) => member.order), [3, 10, 12], "Unsupported canonical positions");
  deepSame(unsupportedRecords.map((member) => member.order), [3, 10, 12], "Direct-view unsupported positions");
  deepSame(unsupportedRecords.map((member) => member.system_time_start_utc.slice(0, 10)), ["2023-02-02", "2023-06-10", "2023-07-12"], "Unsupported dates");
  same(unsupportedRecords.every((member) => member.qa_clear_support_count === 0), true, "Unsupported QA-clear counts");
  same(unsupportedRecords.every((member) => member.deprivation_kind === "active" && member.deprivation_detail === "qa_rejected"), true, "Unsupported deprivation attribution");
  same(ledger.deprivation_totals.additive, true, "Top-level deprivation additivity");
  deepSame([passive, active, ratio, keptSuccess, activeShare], [5980, 7905703, 1322, 85.7, 99.92], "Derived deprivation values");
  const perAcquisitionNonvalid = ledger.per_acquisition.reduce((sum, member) => sum + member.deprivation.top_level_mutually_exclusive_counts.passive + member.deprivation.top_level_mutually_exclusive_counts.active, 0);
  same(deprivationTotal, perAcquisitionNonvalid, "Passive plus active exhausts non-base-valid events");
  same(training.unsupported_as_target, "forbidden", "Unsupported-as-target semantics");
  same(training.unsupported_as_negative_sample, "forbidden", "Unsupported-as-negative semantics");
  same(training.loss_participation, "excluded", "Unsupported loss participation");
  deepSame(directView.state_boundary.training_semantics, training, "Direct-view training semantics");
  same(codeLines[0].includes('if dominant == "qa_rejected"') && codeLines[0].includes('qa_clear_support_count"] != 0'), true, "Attribution guard condition");
  same(codeLines.some((value) => value.includes("raise SystemExit")), true, "Attribution guard stop");
  same(brief.includes("留下只指保留为证据成员") || brief.includes("保留为证据成员并进入观测机会的分母"), true, "Brief keep-not-train guard");

  const scenes = members.map((member) => ({
    ...member,
    relative: `data/raw/observation_stack/${member.member_relative_to_alias}`,
  }));
  same(scenes.every((scene) => fs.existsSync(source(scene.relative))), true, "All 21 local observation rasters exist");

  return {
    manifest,
    ledger,
    directView,
    universe,
    included,
    supported,
    unsupported,
    passive,
    active,
    deprivationTotal,
    ratio,
    keptSuccess,
    activeShare,
    members,
    supportedMembers,
    unsupportedMembers,
    unsupportedRecords,
    training,
    codeLines,
    scenes,
  };
}

async function render(data) {
  const footer = `${data.universe} 次观测机会 / ${data.supported} 次有效证据 / ${data.unsupported} 次失败原因可追溯`;
  const figures = [];

  // 01 · The three unsupported observations become a full-width evidence triptych.
  const coverWidth = 300;
  const coverHeight = 410;
  const coverY = 405;
  const coverX = [45, 390, 735];
  const coverScenes = data.scenes.filter((scene) => scene.target_surface_support_status === "zero_base_valid_land");
  const coverComposites = [];
  let coverOverlay = "";
  for (let index = 0; index < coverScenes.length; index += 1) {
    const scene = coverScenes[index];
    const x = coverX[index];
    coverComposites.push({ input: await scenePreview(scene.relative, coverWidth, coverHeight), left: x, top: coverY });
    coverOverlay += rr(x, coverY, coverWidth, coverHeight, "none", 18, `stroke="${C.yellow}" stroke-width="10"`);
    coverOverlay += `<path d="M ${x + 16} ${coverY + 48} V ${coverY + 16} H ${x + 48} M ${x + coverWidth - 48} ${coverY + 16} H ${x + coverWidth - 16} V ${coverY + 48} M ${x + 16} ${coverY + coverHeight - 48} V ${coverY + coverHeight - 16} H ${x + 48} M ${x + coverWidth - 48} ${coverY + coverHeight - 16} H ${x + coverWidth - 16} V ${coverY + coverHeight - 48}" fill="none" stroke="#FFF9E8" stroke-width="5" stroke-linecap="round"/>`;
  }
  figures.push({
    file: "01_cover.png",
    claim: "第 3、10、12 景真实 SR_B4 观测以三联画放大，并由黄框表示保留为证据成员而非用于训练。",
    sources: [
      sourceEntry(FILE.manifest, ["counts", "members[].order", "members[].member_relative_to_alias", "members[].evidence_membership", "members[].target_surface_support_status"], {
        included: data.included,
        unsupported_positions: data.unsupportedMembers.map((member) => member.order),
        actual_scene_files: coverScenes.map((scene) => scene.relative),
      }),
      sourceEntry(FILE.brief, ["01 cover continuation and wording guard"], { sequel_signal: "上一篇：21景，一景没挑" }),
    ],
    render: () => writeFigure("01_cover.png", [
      rect(0, 0, W, H, C.paper),
      mountain(1100),
      rr(5, 5, 1070, 1340, "none", 28, 'stroke="#F0E5C3" stroke-width="7"'),
      txt(1018, 62, "上一篇：21景，一景没挑", 17, { fill: C.muted, weight: 600, anchor: "end" }),
      txt(60, 92, "那", 30, { fill: C.muted, weight: 800 }),
      txt(52, 350, String(data.unsupported), 350, { weight: 800 }),
      txt(350, 190, "景，", 61, { weight: 800 }),
      txt(350, 292, "我留下了", 82, { weight: 800 }),
      txt(540, 870, `这 ${data.unsupported} 景：观测事件 ✓ ／ 当前拟合支持 = 0`, 19, { fill: C.muted, weight: 700, anchor: "middle" }),
      multi(540, 950, ["它们不进入拟合，", "却留下了模型以后该少自信的理由。"], 38, 52, { fill: C.orange, weight: 800, anchor: "middle" }),
    ].join(""), coverComposites, coverOverlay),
  });

  // 02 · Same effective model input; different evidence accounting.
  figures.push({
    file: "02_same_18_different_dataset.png",
    claim: "删除三次失败记录与保留三次失败记录都只有 18 景具备当前拟合资格，但前者呈现 18/18=100%，后者保留 21 个证据成员并呈现 18/21=85.7%。",
    sources: [
      sourceEntry(FILE.manifest, ["counts", "members[].evidence_membership", "members[].target_surface_support_status"], {
        universe: data.universe,
        effective_members: data.supported,
        unsupported_members: data.unsupported,
        deleted_record_success_rate: 100,
        evidence_ledger_success_rate: data.keptSuccess,
      }),
      sourceEntry(FILE.manifest, ["training_semantics.unsupported_as_target", "training_semantics.unsupported_as_negative_sample", "training_semantics.loss_participation"], data.training),
      sourceEntry(FILE.brief, ["Post 04 closing promise"], { quote: "不能入栈，不等于可以从证据记录中消失。" }),
    ],
    render: () => writeFigure("02_same_18_different_dataset.png", [
      page("一样的 18 景，不一样的数据集", "删掉失败记录，成功率就变成满分", footer, { titleSize: 47 }),
      rr(60, 238, 960, 92, C.panel, 22, `stroke="${C.line}" stroke-width="3"`),
      txt(90, 279, "“不能入栈，不等于可以从证据记录中消失。”", 24, { weight: 700 }),
      txt(980, 310, "上一篇文末", 17, { fill: C.muted, weight: 700, anchor: "end" }),

      rr(50, 365, 470, 490, C.greenSoft, 28),
      txt(285, 414, `删掉 ${data.unsupported} 景`, 28, { weight: 800, anchor: "middle" }),
      txt(285, 535, "100%", 102, { fill: C.green, weight: 800, anchor: "middle" }),
      txt(285, 579, `${data.supported}/${data.supported} 具备当前拟合资格`, 22, { fill: C.muted, weight: 700, anchor: "middle" }),
      evidenceGrid(161, 620, data.supportedMembers, { columns: 6, cell: 34, gap: 8 }),
      marker(95, 749, 380),
      txt(285, 791, "一个看起来从不失败的全年", 26, { weight: 800, anchor: "middle" }),
      txt(285, 832, `全年观测 ${data.supported} 次`, 21, { fill: C.muted, weight: 700, anchor: "middle" }),

      rr(560, 365, 470, 490, C.panel, 28, `stroke="${C.line}" stroke-width="3"`),
      txt(795, 414, `留下 ${data.unsupported} 景`, 28, { weight: 800, anchor: "middle" }),
      txt(795, 535, `${data.keptSuccess}%`, 82, { fill: C.ink, weight: 800, anchor: "middle" }),
      txt(795, 579, `${data.supported}/${data.universe} 具备当前拟合资格`, 22, { fill: C.muted, weight: 700, anchor: "middle" }),
      evidenceGrid(655, 620, data.members, { columns: 7, cell: 34, gap: 7, highlightUnsupported: true }),
      marker(606, 749, 378),
      txt(795, 791, "一个知道自己错过了什么的全年", 25, { weight: 800, anchor: "middle" }),
      txt(795, 832, `全年 ${data.universe} 次机会`, 21, { fill: C.muted, weight: 700, anchor: "middle" }),

      rr(60, 885, 960, 72, C.ink, 22),
      txt(540, 931, "两边进入当前拟合的有效支持相同", 25, { fill: C.yellow, weight: 800, anchor: "middle" }),
      rr(60, 985, 450, 174, C.ink, 25),
      txt(90, 1030, "它只知道", 21, { fill: C.yellow, weight: 800 }),
      multi(90, 1080, ["自己看见了什么。"], 31, 42, { fill: "#FFF9E8", weight: 800 }),
      rr(570, 985, 450, 174, C.ink, 25),
      txt(600, 1030, "它还知道", 21, { fill: C.yellow, weight: 800 }),
      multi(600, 1078, ["自己错过了什么，", "以及为什么。"], 29, 39, { fill: "#FFF9E8", weight: 800 }),
    ].join("")),
  });

  // 03 · Linear scale, no break and no logarithm.
  const activeBarWidth = 820;
  const passiveBarWidth = activeBarWidth * data.passive / data.active;
  figures.push({
    file: "03_two_kinds_of_unseen.png",
    claim: `顶层互斥缺失事件中 passive=${data.passive}、active=${data.active}，线性比例约 ${data.ratio} 倍；不使用断轴或对数。`,
    sources: [
      sourceEntry(FILE.ledger, ["deprivation_totals.additive", "deprivation_totals.top_level_mutually_exclusive.passive", "deprivation_totals.top_level_mutually_exclusive.active", "per_acquisition[].deprivation.top_level_mutually_exclusive_counts"], {
        passive: data.passive,
        active: data.active,
        passive_plus_active: data.deprivationTotal,
        active_div_passive_rounded: data.ratio,
      }),
    ],
    render: () => writeFigure("03_two_kinds_of_unseen.png", [
      page("「看不见」也分两种", `同样没有信号，规模差了 ${data.ratio} 倍`, footer),
      txt(90, 304, "被动 · 源数据没有形成所需值", 26, { weight: 800 }),
      txt(990, 304, data.passive.toLocaleString("en-US"), 32, { fill: C.muted, weight: 800, anchor: "end" }),
      rect(90, 340, passiveBarWidth, 54, C.ink),
      line(260, 435, 96, 372, C.orange, 4, 'stroke-linecap="round"'),
      `<path d="M 96 372 l 18 -4 l -8 16 Z" fill="${C.orange}"/>`,
      txt(275, 445, "这条不是画漏了。", 25, { fill: C.orange, weight: 800 }),

      txt(90, 552, "主动 · 观测存在，但被冻结规则拒绝", 26, { weight: 800 }),
      txt(990, 552, data.active.toLocaleString("en-US"), 32, { fill: C.green, weight: 800, anchor: "end" }),
      rr(90, 590, activeBarWidth, 76, C.green, 12),
      txt(910, 708, "线性比例 · 不断轴 · 不取对数", 18, { fill: C.muted, weight: 700, anchor: "end" }),

      txt(60, 785, "同样是「看不见」，但——", 31, { weight: 800 }),
      rr(60, 820, 460, 132, C.panel2, 24),
      txt(90, 864, "主动拒绝不只一种原因", 22, { fill: C.orange, weight: 800 }),
      txt(90, 914, "QA / 反射率 / 地形有效性可重叠。", 23, { weight: 800 }),
      rr(560, 820, 460, 132, C.panel, 24, `stroke="${C.line}" stroke-width="3"`),
      txt(590, 864, "被动缺失", 22, { fill: C.muted, weight: 800 }),
      txt(590, 914, "源数据没有形成所需值。", 25, { weight: 800 }),

      rr(60, 1000, 960, 126, C.panel2, 25),
      marker(78, 1016, 410, 52),
      txt(96, 1058, "压成一个「低支持」数字，", 29, { weight: 800 }),
      txt(96, 1101, `这 ${data.ratio} 倍当场消失。`, 31, { fill: C.orange, weight: 800 }),
      txt(60, 1182, "口径：像元级观测事件；passive / active 互斥、穷尽且可相加。", 18, { fill: C.muted, weight: 600 }),
    ].join("")),
  });

  // 04 · The attribution statement is guarded by executable fail-closed code.
  figures.push({
    file: "04_falsifiable_attribution.png",
    claim: "qa_rejected 归因受源码硬校验约束：必要证据 QA-clear 必须为 0，否则审计失败并停止发布；保留失败原因标注证据边界，但不让无支持记录参与当前拟合。",
    sources: [
      sourceEntry(FILE.builder, ["lines 468-472"], { exact_lines: data.codeLines }),
      sourceEntry(FILE.directView, ["unsupported_records[].qa_clear_support_count", "unsupported_records[].deprivation_kind", "unsupported_records[].deprivation_detail"], {
        records: data.unsupportedRecords.map((member) => ({
          order: member.order,
          date: member.system_time_start_utc.slice(0, 10),
          qa_clear_support_count: member.qa_clear_support_count,
          deprivation_kind: member.deprivation_kind,
          deprivation_detail: member.deprivation_detail,
        })),
      }),
      sourceEntry(FILE.ledger, ["deprivation_totals.top_level_mutually_exclusive"], { active_share_of_top_level_deprivation_percent: data.activeShare }),
      sourceEntry(FILE.manifest, ["training_semantics"], data.training),
      sourceEntry(FILE.brief, ["04 half-answer and mandatory rigor note"], { answers_only_half: true }),
    ],
    render: () => writeFigure("04_falsifiable_attribution.png", [
      page("归因必须可证伪", "能被自己的程序否定，才配叫结论", footer),
      rr(60, 238, 960, 266, C.ink, 26),
      txt(88, 278, "把硬校验翻译成人话 · 原码 468–472 行", 17, { fill: C.yellow, weight: 800 }),
      txt(90, 342, "候选归因：质量拒绝", 27, { fill: "#FFF9E8", weight: 800 }),
      txt(90, 400, "必要证据：QA-clear = 0", 27, { fill: "#FFF9E8", weight: 800 }),
      txt(90, 458, "若不等于 0 → 审计失败，停止发布", 27, { fill: "#F6C5B4", weight: 800 }),
      txt(60, 550, "不是解释性备注，是发布闸门。", 25, { fill: C.orange, weight: 800 }),
      txt(425, 550, "结论必须能被自己的程序否定，才配当结论。", 24, { weight: 800 }),

      rr(60, 590, 960, 348, C.panel2, 27),
      txt(90, 630, "回答上一篇最后的问题 · 只答一半", 20, { fill: C.orange, weight: 800 }),
      txt(90, 683, "半个答案：看你删的时候，留不留下「为什么删」。", 29, { weight: 800 }),
      rr(90, 718, 420, 92, C.panel, 20),
      txt(120, 755, `只留 ${data.supported} 景`, 20, { fill: C.muted, weight: 800 }),
      txt(120, 792, `${data.supported}/${data.supported} 具备当前资格`, 27, { weight: 800 }),
      rr(540, 718, 450, 92, C.greenSoft, 20),
      txt(570, 755, `保留 ${data.universe} 景`, 20, { fill: C.green, weight: 800 }),
      txt(570, 792, `${data.unsupported} 次目标支持为 0，原因可追溯`, 24, { weight: 800 }),
      txt(90, 852, `缺失事件中 ${data.activeShare}% 属主动剥夺：拍到了，但被规则拒绝。`, 24, { weight: 700 }),
      txt(90, 895, "操作层排除信号，是质量控制；证据层保留原因，是标注边界。", 24, { fill: C.orange, weight: 800 }),

      marker(60, 973, 565, 55),
      multi(60, 1025, [
        "我不是要让模型吃下所有坏数据，",
        "而是不允许它在只吃到少量好数据后，",
        "忘记自己曾经看不见。",
      ], 34, 50, { weight: 800 }),
      multi(60, 1196, [
        "差别不是传统方法算不了有效观测数，",
        "而是原因账本是否从 L0 开始就被原生保存。",
      ], 18, 28, { fill: C.muted, weight: 600 }),
    ].join("")),
  });

  for (const figure of figures) await figure.render();
  const thumbs = await Promise.all(figures.map(async (figure, index) => ({
    input: await sharp(path.join(OUT, figure.file)).resize(492, 615).png().toBuffer(),
    left: 24 + (index % 2) * 540,
    top: 24 + Math.floor(index / 2) * 639,
  })));
  await sharp({ create: { width: W, height: 1302, channels: 3, background: C.paper } })
    .composite(thumbs)
    .png()
    .toFile(path.join(OUT, "contact_sheet.png"));

  const figureSources = {
    schema: "mountainrs-xiaohongshu-post-05-figure-sources-v1",
    rendering: {
      renderer: "render_post_05.js",
      dimensions: "1080x1350",
      numeric_policy: "Every displayed result is read from frozen Stage 7.1 evidence or derived after exact validation; no model, refit, Earth Engine call, evidence mutation, or PF3 mutation occurs.",
      raster_policy: "The cover enlarges the same canonical order-3, order-10, and order-12 local SR_B4 rasters shown in Post 04, using the same deterministic display stretch; annotation changes from gray cross to yellow frame.",
      semantics_guard: "The three unsupported records remain evidence members and observation opportunities but are forbidden as targets, forbidden as negative samples, and excluded from loss participation.",
      visual_system: "Post 03/04 warm-paper system with image-first evidence, yellow narrative marker, orange annotations, green support encoding, and restrained text.",
    },
    derived_values: {
      success_rate_with_deleted_records_percent: 100,
      success_rate_with_evidence_ledger_percent: data.keptSuccess,
      active_div_passive_rounded: data.ratio,
      active_share_of_top_level_deprivation_percent: data.activeShare,
    },
    figures: figures.map(({ file, claim, sources }) => ({ file, claim, sources })),
  };
  const serializedSources = `${JSON.stringify(figureSources, null, 2)}\n`;
  fs.writeFileSync(path.join(SCRIPT_DIR, "figure_sources.json"), serializedSources);
  fs.writeFileSync(path.join(OUT, "figure_sources.json"), serializedSources);
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  await render(gather());
  process.stdout.write(`Rendered 4 evidence-led post_05 cards and contact sheet to ${OUT}\n`);
}

main().catch((error) => {
  process.stderr.write(`post_05 render failed: ${error.stack || error.message}\n`);
  process.exitCode = 1;
});
