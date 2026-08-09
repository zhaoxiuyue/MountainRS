#!/usr/bin/env node
"use strict";

/* Deterministic renderer: 《云挡了76%，地形只挡0.92%。但麻烦的是后者》.
 * Read-only inputs: frozen Stage 7.2 evidence, protocol, and this brief.
 * Outputs only: reports/xiaohongshu/post_06*.
 */

const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const W = 1080;
const H = 1350;
const SCRIPT_DIR = __dirname;
const OUT = path.resolve(SCRIPT_DIR, "../post_06");
const CONTAINER = path.resolve(SCRIPT_DIR, "../../..");
const REL = (relative) => path.join(CONTAINER, relative);

const FILE = {
  brief: "reports/xiaohongshu/post_06_support/BRIEF.md",
  ledger: "evidence/support-loss-ledger-v1.json",
  mconf: "evidence/mconf-registry-v1.json",
  cosi: "evidence/cos-i-registry-v1.json",
  protocol: "docs/mconf-subprotocol-v1.md",
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
  gray: "#A7A79F",
  graySoft: "#E8E5DC",
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
async function writeFigure(file, contents) { await sharp(svg(contents)).png().toFile(path.join(OUT, file)); }

function gather() {
  const brief = textFile(FILE.brief);
  const ledger = json(FILE.ledger);
  const mconf = json(FILE.mconf);
  const cosi = json(FILE.cosi);
  const protocol = textFile(FILE.protocol);

  const acquisitionCount = ledger.per_acquisition.length;
  const targetPixelCounts = [...new Set(ledger.per_acquisition.map((member) => member.target_pixel_count))];
  same(targetPixelCounts.length, 1, "Single target pixel count");
  const targetPixelCount = targetPixelCounts[0];
  const denominator = acquisitionCount * targetPixelCount;
  const qualityCount = ledger.totals.observation_or_upstream_validity_exclusion;
  const geometryCount = ledger.totals.mconf_mechanism_zero;
  const qualityPct = Number((qualityCount / denominator * 100).toFixed(2));
  const geometryPct = Number((geometryCount / denominator * 100).toFixed(2));
  const selfShadow = ledger.per_acquisition.reduce((sum, member) => sum + member.mconf_mechanism_zero.self_shadow, 0);
  const nearZero = ledger.per_acquisition.reduce((sum, member) => sum + member.mconf_mechanism_zero.near_zero, 0);
  const mechanismTotal = ledger.per_acquisition.reduce((sum, member) => sum + member.mconf_mechanism_zero.total, 0);

  const order1 = cosi.members.find((member) => member.order === 1);
  const order21 = cosi.members.find((member) => member.order === 21);
  const memberSummary = (member) => ({
    order: member.order,
    date: member.system_time_start_utc.slice(0, 10),
    sunElevation: member.solar_geometry.sun_elevation_deg,
    sunElevation2: Number(member.solar_geometry.sun_elevation_deg.toFixed(2)),
    litCount: member.descriptive_partition_not_a_support_decision.lit_cos_i_gt_0_1,
    litPct: Number((member.descriptive_partition_not_a_support_decision.lit_cos_i_gt_0_1 / member.output.valid_count * 100).toFixed(1)),
  });
  const low1 = memberSummary(order1);
  const low21 = memberSummary(order21);
  const lowestSunOrders = [...cosi.members].sort((a, b) => a.solar_geometry.sun_elevation_deg - b.solar_geometry.sun_elevation_deg).slice(0, 2).map((member) => member.order);
  const lowestLitOrders = [...cosi.members].sort((a, b) => a.descriptive_partition_not_a_support_decision.lit_cos_i_gt_0_1 - b.descriptive_partition_not_a_support_decision.lit_cos_i_gt_0_1).slice(0, 2).map((member) => member.order);

  deepSame([acquisitionCount, targetPixelCount, denominator], [18, 488800, 8798400], "Calibration denominator");
  deepSame([qualityCount, geometryCount, qualityPct, geometryPct], [6709508, 81005, 76.26, 0.92], "Support-loss headline values");
  deepSame([selfShadow, nearZero, mechanismTotal], [35525, 45480, 81005], "Mconf mechanism decomposition");
  same(selfShadow + nearZero, geometryCount, "Self-shadow plus near-zero equals mechanism total");
  same(qualityCount + geometryCount + ledger.totals.calibration_lit, denominator, "Calibration opportunity partition");
  same(ledger.per_acquisition.every((member) => member.mconf_mechanism_zero.self_shadow + member.mconf_mechanism_zero.near_zero === member.mconf_mechanism_zero.total), true, "Per-member geometry decomposition");
  same(mconf.factor_identity.coverage, "self_shadow_only", "Mconf coverage");
  deepSame(mconf.factor_identity.not_covered, ["cast_shadow", "horizon_occlusion", "disocclusion_boundary", "geometric_instability_boundary", "view_angle_occlusion"], "Mconf uncovered list");
  same(mconf.factor_identity.coverage_caveat.includes("乐观上界"), true, "Optimistic upper-bound caveat");
  deepSame(lowestSunOrders, [1, 21], "Lowest sun-elevation orders");
  deepSame(lowestLitOrders, [1, 21], "Lowest lit-count orders");
  deepSame([low1.sunElevation2, low21.sunElevation2, low1.litPct, low21.litPct], [31.14, 31.32, 73.5, 73.8], "Low-sun descriptive values");
  same(protocol.includes("`cos_i > 0.1` **只覆盖自阴影**（self-shadowing，由局部入射角决定：坡面背向太阳）。"), true, "Contract self-shadow boundary quote");
  same(protocol.includes("**以下全部未覆盖**，本子协议不量化、不近似、不以任何方式声称已处理："), true, "Contract no-coverage quote");
  same(protocol.includes("**因此，结论中不得出现「几何可见性已覆盖」「遮挡已处理」一类表述。**"), true, "Contract prohibited-wording quote");
  same(protocol.includes("本因子只能被称为「自阴影许可量」。"), true, "Contract allowed-name quote");
  same(/本子协议因此在几何上是\*\*乐观\*\*的，任何基于它的支持计数\s+都应理解为上界。/.test(protocol), true, "Contract optimistic-upper-bound quote");
  same(brief.includes("不得声称已经处理了投射阴影"), true, "Brief cast-shadow wording guard");

  return {
    ledger,
    mconf,
    cosi,
    acquisitionCount,
    targetPixelCount,
    denominator,
    qualityCount,
    geometryCount,
    qualityPct,
    geometryPct,
    selfShadow,
    nearZero,
    low1,
    low21,
  };
}

function schematic() {
  return [
    rr(60, 245, 960, 390, C.panel, 28, `stroke="${C.line}" stroke-width="3"`),
    rr(704, 260, 282, 38, C.panel, 19, `stroke="${C.line}" stroke-width="2"`),
    txt(845, 285, "SCHEMATIC · 机制示意 · 非结果图", 14, { fill: C.muted, weight: 700, anchor: "middle" }),
    `<circle cx="145" cy="340" r="43" fill="${C.yellow}"/>`,
    line(145, 274, 145, 247, C.yellow, 7, 'stroke-linecap="round"'),
    line(94, 289, 75, 270, C.yellow, 7, 'stroke-linecap="round"'),
    line(196, 289, 215, 270, C.yellow, 7, 'stroke-linecap="round"'),
    txt(145, 410, "太阳", 20, { weight: 800, anchor: "middle" }),
    line(190, 342, 410, 355, C.yellow, 8, 'stroke-linecap="round"'),
    `<path d="M 410 355 l -18 -11 l -2 20 Z" fill="${C.yellow}"/>`,
    line(190, 375, 375, 388, C.yellow, 5, 'stroke-linecap="round" opacity=".8"'),
    line(410, 355, 730, 447, C.yellow, 5, 'stroke-linecap="round" stroke-dasharray="14 13" opacity=".72"'),
    txt(455, 389, "被 A 截断", 17, { fill: C.orange, weight: 800 }),

    `<path d="M 90 605 L 260 545 L 410 355 L 548 598 L 710 468 L 850 322 L 1010 605 Z" fill="#D8D0BD" stroke="${C.ink}" stroke-width="5" stroke-linejoin="round"/>`,
    `<path d="M 410 355 L 548 598 L 657 510 L 590 430 Z" fill="#777871" opacity=".72"/>`,
    `<path d="M 410 355 L 850 322 L 548 598 Z" fill="#686A65" opacity=".55"/>`,
    `<path d="M 548 598 L 850 322" stroke="${C.orange}" stroke-width="14" stroke-linecap="round" opacity=".9"/>`,
    `<path d="M 548 598 L 850 322" stroke="#777871" stroke-width="9" stroke-linecap="round" opacity=".58"/>`,
    txt(360, 333, "山 A", 20, { weight: 800 }),
    txt(865, 318, "山 B", 20, { weight: 800 }),
    txt(505, 574, "A 投下的阴影", 20, { fill: "#FFF9E8", weight: 800, anchor: "middle" }),
    txt(810, 410, "这面朝着太阳", 20, { fill: C.orange, weight: 800 }),
    txt(810, 440, "cos_i 仍然很大", 18, { fill: C.orange, weight: 700 }),
    line(785, 420, 735, 456, C.orange, 4, 'stroke-linecap="round"'),
    `<path d="M 735 456 l 9 -18 l 9 12 Z" fill="${C.orange}"/>`,
  ].join("");
}

async function render(data) {
  const footer = "几何判据只覆盖自阴影 / 投射阴影未纳入 / 缺口已写入冻结合同";
  const figures = [];

  figures.push({
    file: "01_cover.png",
    claim: `地形机制拒绝占 18 景标定机会的 ${data.geometryPct}%，但其系统性缺口是本篇重点。`,
    sources: [
      sourceEntry(FILE.ledger, ["totals.mconf_mechanism_zero", "per_acquisition[].target_pixel_count"], { geometry_count: data.geometryCount, denominator: data.denominator, geometry_percent: data.geometryPct }),
      sourceEntry(FILE.brief, ["01 cover sequel signal and hook"], { sequel_signal: "上一篇：删掉3景，成功率100%。我没删" }),
    ],
    render: () => writeFigure("01_cover.png", [
      rect(0, 0, W, H, C.paper),
      rr(5, 5, 1070, 1340, "none", 28, 'stroke="#F0E5C3" stroke-width="7"'),
      txt(1018, 65, "上一篇：删掉3景，成功率100%。我没删", 17, { fill: C.muted, weight: 600, anchor: "end" }),
      txt(540, 590, `${data.geometryPct.toFixed(2)}%`, 270, { weight: 800, anchor: "middle" }),
      marker(185, 690, 710, 66),
      txt(540, 755, "地形只挡了这么点", 68, { weight: 800, anchor: "middle" }),
      txt(540, 945, `但麻烦的是它，不是那 ${Math.round(data.qualityPct)}%。`, 43, { fill: C.orange, weight: 800, anchor: "middle" }),
    ].join("")),
  });

  const qualityBarWidth = 820 * data.qualityCount / data.denominator;
  const geometryBarWidth = 820 * data.geometryCount / data.denominator;
  figures.push({
    file: "02_who_blocks_calibration.png",
    claim: `18×488,800=${data.denominator} 个像元级标定机会中，上游观测质量排除 ${data.qualityCount}（${data.qualityPct}%），几何判据排除 ${data.geometryCount}（${data.geometryPct}%）。`,
    sources: [
      sourceEntry(FILE.ledger, ["per_acquisition[].target_pixel_count", "totals.observation_or_upstream_validity_exclusion", "totals.mconf_mechanism_zero", "totals.calibration_lit"], {
        acquisition_count: data.acquisitionCount,
        target_pixel_count: data.targetPixelCount,
        denominator: data.denominator,
        observation_or_upstream_validity_exclusion: data.qualityCount,
        observation_or_upstream_validity_exclusion_percent: data.qualityPct,
        mconf_mechanism_zero: data.geometryCount,
        mconf_mechanism_zero_percent: data.geometryPct,
      }),
    ],
    render: () => writeFigure("02_who_blocks_calibration.png", [
      page("谁拦住了标定像元？", "量大的会变，量小的却固定", footer),
      rr(60, 245, 960, 92, C.panel2, 22),
      txt(90, 282, "本篇分母", 19, { fill: C.muted, weight: 800 }),
      txt(980, 302, `${data.acquisitionCount} 景 × ${data.targetPixelCount.toLocaleString("en-US")} = ${data.denominator.toLocaleString("en-US")} 个像元级标定机会`, 26, { weight: 800, anchor: "end" }),

      txt(90, 406, "云雪等观测质量不合格", 27, { weight: 800 }),
      txt(990, 406, `${data.qualityCount.toLocaleString("en-US")}  ·  ${data.qualityPct.toFixed(2)}%`, 29, { fill: C.green, weight: 800, anchor: "end" }),
      rr(90, 442, 820, 62, C.graySoft, 12),
      rr(90, 442, qualityBarWidth, 62, C.green, 12),

      txt(90, 585, "我的几何判据拒绝", 27, { weight: 800 }),
      txt(990, 585, `${data.geometryCount.toLocaleString("en-US")}  ·  ${data.geometryPct.toFixed(2)}%`, 29, { fill: C.ink, weight: 800, anchor: "end" }),
      rr(90, 621, 820, 62, C.graySoft, 12),
      rr(90, 621, geometryBarWidth, 62, C.ink, 4),
      txt(910, 716, "同一分母 · 线性比例", 18, { fill: C.muted, weight: 700, anchor: "end" }),

      rr(60, 760, 960, 366, C.ink, 28),
      txt(90, 808, "只看数量，几何像个小问题。", 26, { fill: "#FFF9E8", weight: 800 }),
      txt(90, 855, "但它不会自己消失。", 34, { fill: C.yellow, weight: 800 }),
      rr(90, 890, 420, 130, "#262724", 20),
      txt(120, 932, `${Math.round(data.qualityPct)}% · 观测质量`, 21, { fill: C.yellow, weight: 800 }),
      txt(120, 979, "云雪随日期变化。", 27, { fill: "#FFF9E8", weight: 800 }),
      rr(540, 890, 450, 130, "#262724", 20),
      txt(570, 932, `${data.geometryPct.toFixed(2)}% · 地形机制`, 21, { fill: C.yellow, weight: 800 }),
      txt(570, 979, "同一坡面会被反复拒绝。", 27, { fill: "#FFF9E8", weight: 800 }),
      txt(540, 1080, `${Math.round(data.qualityPct)}% 会自己变，${data.geometryPct.toFixed(2)}% 不会。`, 30, { fill: C.orange, weight: 800, anchor: "middle" }),
    ].join("")),
  });

  figures.push({
    file: "03_half_the_shadow.png",
    claim: `Mconf v1 只覆盖局部 cos_i 自阴影与近零拒绝（${data.selfShadow}+${data.nearZero}=${data.geometryCount}）；投射阴影未计算且规模未知。`,
    sources: [
      sourceEntry(FILE.ledger, ["per_acquisition[].mconf_mechanism_zero.self_shadow", "per_acquisition[].mconf_mechanism_zero.near_zero", "totals.mconf_mechanism_zero"], { self_shadow: data.selfShadow, near_zero: data.nearZero, total: data.geometryCount }),
      sourceEntry(FILE.mconf, ["factor_identity.coverage", "factor_identity.not_covered", "factor_identity.coverage_caveat", "factor_identity.threshold"], data.mconf.factor_identity),
      sourceEntry(FILE.cosi, ["members[order=1,21].solar_geometry.sun_elevation_deg", "members[order=1,21].descriptive_partition_not_a_support_decision.lit_cos_i_gt_0_1", "members[order=1,21].output.valid_count"], { order_1: data.low1, order_21: data.low21 }),
    ],
    render: () => writeFigure("03_half_the_shadow.png", [
      page("我的判据只认一半的阴影", "cos_i 只看坡面朝向，不看前方有没有山", footer, { titleSize: 46 }),
      schematic(),
      txt(540, 664, "局部坡向说“有光”，前方山体却把直射光挡住了。", 19, { weight: 800, anchor: "middle" }),
      rr(60, 685, 460, 190, C.greenSoft, 24),
      txt(90, 728, "自阴影 + 近零（我算了）", 23, { fill: C.green, weight: 800 }),
      txt(90, 771, "坡面背向太阳或接近掠射", 22, { weight: 700 }),
      txt(90, 815, "cos_i ≤ 0.1 能抓到", 23, { weight: 800 }),
      txt(90, 853, `${data.selfShadow.toLocaleString("en-US")} + ${data.nearZero.toLocaleString("en-US")} = ${data.geometryCount.toLocaleString("en-US")}`, 24, { fill: C.green, weight: 800 }),
      rr(560, 685, 460, 190, C.panel, 24, `stroke="${C.line}" stroke-width="3"`),
      txt(590, 728, "投射阴影（我没算）", 23, { fill: C.orange, weight: 800 }),
      txt(590, 771, "坡面朝阳，但被别的山挡住", 22, { weight: 700 }),
      txt(590, 815, "cos_i 仍可能很大", 23, { weight: 800 }),
      txt(590, 853, "不知道有多少——我没算", 24, { fill: C.orange, weight: 800 }),
      txt(540, 927, "我的几何判据只覆盖自阴影，另一半它根本看不见。", 27, { fill: C.orange, weight: 800, anchor: "middle" }),

      rr(60, 975, 960, 220, C.panel2, 25),
      txt(90, 1017, "偏差方向不是随机的：太阳角越低，投射阴影越重。", 23, { weight: 800 }),
      rr(90, 1042, 420, 95, C.panel, 18),
      txt(115, 1077, `${data.low1.date} · ${data.low1.sunElevation2.toFixed(2)}°`, 21, { weight: 800 }),
      txt(115, 1117, `lit ${data.low1.litPct.toFixed(1)}%`, 27, { fill: C.green, weight: 800 }),
      rr(540, 1042, 450, 95, C.panel, 18),
      txt(565, 1077, `${data.low21.date} · ${data.low21.sunElevation2.toFixed(2)}°`, 21, { weight: 800 }),
      txt(565, 1117, `lit ${data.low21.litPct.toFixed(1)}%`, 27, { fill: C.green, weight: 800 }),
      txt(540, 1173, "真实可用区域只会更少，不会更多。", 25, { fill: C.orange, weight: 800, anchor: "middle" }),
    ].join("")),
  });

  figures.push({
    file: "04_frozen_contract.png",
    claim: "冻结子协议§3逐字声明 cos_i>0.1 只覆盖自阴影，五类几何遮挡未覆盖，并禁止把几何可见性或遮挡表述为已覆盖；因此几何支持是乐观上界。",
    sources: [
      sourceEntry(FILE.protocol, ["§3 lines 71-89"], {
        quote_1: "cos_i > 0.1 只覆盖自阴影（self-shadowing，由局部入射角决定：坡面背向太阳）。",
        quote_2: "以下全部未覆盖，本子协议不量化、不近似、不以任何方式声称已处理：",
        quote_3: "本子协议因此在几何上是乐观的，任何基于它的支持计数都应理解为上界。",
        quote_4: "因此，结论中不得出现「几何可见性已覆盖」「遮挡已处理」一类表述。",
        quote_5: "本因子只能被称为「自阴影许可量」。",
      }),
      sourceEntry(FILE.mconf, ["factor_identity.coverage", "factor_identity.not_covered", "factor_identity.coverage_caveat"], {
        coverage: data.mconf.factor_identity.coverage,
        not_covered: data.mconf.factor_identity.not_covered,
        caveat: data.mconf.factor_identity.coverage_caveat,
      }),
    ],
    render: () => writeFigure("04_frozen_contract.png", [
      page("我把它写进了合同", "记录方法的缺口，而不是假装方法完整", footer),
      rr(60, 240, 960, 540, C.ink, 28),
      txt(90, 278, "冻结原文 · docs/mconf-subprotocol-v1.md §3", 18, { fill: C.yellow, weight: 800 }),
      multi(90, 325, [
        "cos_i > 0.1 只覆盖自阴影（self-shadowing，",
        "由局部入射角决定：坡面背向太阳）。",
      ], 22, 33, { fill: "#FFF9E8", weight: 700 }),
      multi(90, 405, [
        "以下全部未覆盖，本子协议不量化、不近似、",
        "不以任何方式声称已处理：",
      ], 22, 33, { fill: "#FFF9E8", weight: 700 }),
      multi(90, 485, [
        "地形投射阴影 / 地平线遮挡 / 去遮挡边界 /",
        "几何不稳定边界 / 观测视角遮挡",
      ], 20, 33, { fill: "#F6C5B4", weight: 800 }),
      multi(90, 565, [
        "因此，结论中不得出现「几何可见性已覆盖」",
        "「遮挡已处理」一类表述。",
        "本因子只能被称为「自阴影许可量」。",
      ], 21, 32, { fill: "#F6C5B4", weight: 800 }),
      multi(90, 685, [
        "本子协议因此在几何上是乐观的，",
        "任何基于它的支持计数都应理解为上界。",
      ], 22, 34, { fill: C.yellow, weight: 800 }),
      txt(60, 830, "这不是事后检讨，是判据冻结那天就一起写进去的。", 26, { fill: C.orange, weight: 800 }),

      marker(60, 890, 585, 58),
      multi(60, 948, [
        "我知道我的判据是错的。",
        "我把它写进了合同，",
        "而不是等以后被人发现。",
      ], 41, 58, { weight: 800 }),
      multi(60, 1170, [
        "第一篇我说：背阴坡不是黑，是模型少了一项物理。",
        "五篇之后我给它建了个判据——然后发现，它只认一半的阴影。",
      ], 19, 31, { fill: C.muted, weight: 600 }),
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
    schema: "mountainrs-xiaohongshu-post-06-figure-sources-v1",
    rendering: {
      renderer: "render_post_06.js",
      dimensions: "1080x1350",
      numeric_policy: "Every displayed value is read from frozen Stage 7.2 evidence or derived after exact validation; no model, refit, Earth Engine call, evidence mutation, or PF3 mutation occurs.",
      denominator_policy: "Post 06 uses the 18 eligible calibration acquisitions times the frozen 488,800-pixel target grid, not Post 05's 21-acquisition observation-opportunity denominator.",
      schematic_policy: "Card 03 is explicitly labeled SCHEMATIC and explains an unquantified coverage gap; it is not a computed cast-shadow result.",
      wording_guard: "Geometry rejection is small in count but systematic; cast shadow remains uncomputed and unquantified; Mconf support is an optimistic upper bound.",
      visual_system: "Post 03-05 warm-paper system with ink headlines, yellow narrative marker, orange annotations, pale panels, and mountain footer; the cover intentionally omits mountain imagery per brief.",
    },
    derived_values: {
      acquisition_count: data.acquisitionCount,
      target_pixel_count: data.targetPixelCount,
      calibration_opportunity_denominator: data.denominator,
      observation_or_upstream_validity_exclusion_percent: data.qualityPct,
      mconf_mechanism_zero_percent: data.geometryPct,
      self_shadow_plus_near_zero: data.geometryCount,
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
  process.stdout.write(`Rendered 4 evidence-led post_06 cards and contact sheet to ${OUT}\n`);
}

main().catch((error) => {
  process.stderr.write(`post_06 render failed: ${error.stack || error.message}\n`);
  process.exitCode = 1;
});
