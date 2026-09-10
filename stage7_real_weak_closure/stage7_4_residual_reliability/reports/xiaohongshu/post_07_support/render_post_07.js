#!/usr/bin/env node
"use strict";

/* Deterministic renderer: Post 07 「修补前」季终篇.
 * Reads frozen Stage 7.4 verdict counts and previously frozen Stage 7.1/7.2 ledgers.
 * Writes only reports/xiaohongshu/post_07*.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const sharp = require("sharp");

const W = 1080;
const H = 1350;
const SCRIPT_DIR = __dirname;
const OUT = path.resolve(SCRIPT_DIR, "../post_07");
const CONTAINER = path.resolve(SCRIPT_DIR, "../../..");
const REL = (relative) => path.resolve(CONTAINER, relative);

const FILE = {
  brief: "reports/xiaohongshu/post_07_support/BRIEF.md",
  aggregation: "outputs/risk-proxy-aggregation-table-v1.json",
  curveTable: "outputs/risk-proxy-risk-curve-table-v1.json",
  unitLedger: "evidence/risk-proxy-unit-status-ledger-v1.json",
  reconciliation: "evidence/risk-proxy-reconciliation-manifest-v1.json",
  config: "configs/risk-proxy-config-v2.json",
  protocol: "docs/risk-proxy-protocol-v2.md",
  resultBlind: "evidence/result-blind-declaration-v1.json",
  freezeAudit: "evidence/risk-proxy-runtime-freeze-audit-v2.json",
  post05Manifest: "../stage7_1_observation_stack/evidence/observation-evidence-manifest-v1.json",
  post06Ledger: "../stage7_2_baseline_fit/evidence/support-loss-ledger-v1.json",
  post06Mconf: "../stage7_2_baseline_fit/evidence/mconf-registry-v1.json",
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
  gray: "#CFD0CA",
  grayDark: "#7B7D77",
  beige: "#F0D99A",
  dark: "#5E605B",
  mountain1: "#F8E9B8",
  mountain2: "#F3DFA0",
};

const CATEGORY = {
  ordered: { key: "descriptive_ordering_signal", label: "有序", color: C.green, stroke: C.green },
  none: { key: "descriptive_non_discriminative", label: "无区分", color: C.gray, stroke: C.grayDark },
  adverse: { key: "directionally_adverse", label: "方向相反", color: C.orange, stroke: C.orange },
  insufficient: { key: "not_evaluable_insufficient_scored_support", label: "支持不足", color: C.beige, stroke: "#BDA869" },
  degenerate: { key: "not_evaluable_score_degenerate", label: "分数退化", color: C.dark, stroke: C.dark },
};
const CATEGORY_ORDER = ["ordered", "none", "adverse", "insufficient", "degenerate"];

function fail(message) { throw new Error(message); }
function source(relative) {
  const full = REL(relative);
  if (!fs.existsSync(full)) fail(`Missing frozen source: ${relative}`);
  return full;
}
function textFile(relative) { return fs.readFileSync(source(relative), "utf8"); }
function json(relative) { return JSON.parse(textFile(relative)); }
function sha256(relative) { return crypto.createHash("sha256").update(fs.readFileSync(source(relative))).digest("hex"); }
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
function marker(x, y, w, h = 52) {
  return `<path d="M ${x} ${y + 9} C ${x + w * 0.14} ${y - 1}, ${x + w * 0.32} ${y + 3}, ${x + w * 0.52} ${y + 7} C ${x + w * 0.72} ${y + 1}, ${x + w * 0.88} ${y + 4}, ${x + w} ${y + 8} L ${x + w - 8} ${y + h - 6} C ${x + w * 0.72} ${y + h + 2}, ${x + w * 0.34} ${y + h - 2}, ${x + 6} ${y + h - 4} Z" fill="${C.yellow}" opacity=".86"/>`;
}
function underline(x, y, w, color = C.yellow, width = 7) {
  return `<path d="M ${x} ${y} C ${x + w * 0.26} ${y - 5}, ${x + w * 0.57} ${y + 6}, ${x + w} ${y - 1}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round"/>`;
}
function mountain(y = 1180) {
  return `<path d="M 0 ${H} L 0 ${y + 145} C 120 ${y + 130},190 ${y + 79},284 ${y + 87} C 373 ${y + 94},452 ${y + 153},538 ${y + 138} C 625 ${y + 123},713 ${y + 56},795 ${y + 12} C 849 ${y - 18},883 ${y - 7},930 ${y + 29} C 985 ${y + 71},1030 ${y + 101},1080 ${y + 110} L 1080 ${H} Z" fill="${C.mountain1}" opacity=".72"/><path d="M 0 ${H} L 0 ${y + 167} C 136 ${y + 154},211 ${y + 116},290 ${y + 124} C 374 ${y + 133},454 ${y + 183},546 ${y + 162} C 637 ${y + 141},699 ${y + 112},765 ${y + 81} C 818 ${y + 56},863 ${y + 74},913 ${y + 105} C 972 ${y + 140},1029 ${y + 150},1080 ${y + 150} L 1080 ${H} Z" fill="${C.mountain2}" opacity=".64"/>`;
}
function seasonMark() {
  return [
    rr(790, 24, 230, 42, C.panel, 21, `stroke="${C.line}" stroke-width="2"`),
    txt(905, 53, "「修补前」· 收束篇", 17, { fill: C.muted, weight: 800, anchor: "middle" }),
    txt(1018, 126, "“", 108, { fill: C.yellow, weight: 800, anchor: "end", opacity: 0.62 }),
  ].join("");
}
function page(title, subtitle, footer, options = {}) {
  const { titleSize = 49, mountainY = 1180 } = options;
  return [
    rect(0, 0, W, H, C.paper),
    mountain(mountainY),
    rr(5, 5, 1070, 1340, "none", 28, 'stroke="#F0E5C3" stroke-width="7"'),
    seasonMark(),
    txt(60, 144, title, titleSize, { weight: 800 }),
    txt(60, 193, subtitle, 24, { fill: C.muted, weight: 500 }),
    underline(60, 213, 144),
    txt(60, 1310, footer, 17, { fill: C.muted, weight: 500 }),
  ].join("");
}
function svg(contents) {
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><style>text { font-kerning: normal; }</style>${contents}</svg>`);
}
function sourceEntry(sourceFile, fields, values = {}, metadata = {}) { return { source_file: sourceFile, ...metadata, fields, values }; }
async function writeFigure(file, contents) { await sharp(svg(contents)).png().toFile(path.join(OUT, file)); }

function verdictCounts(row) {
  const sourceCounts = row.risk_proxy_verdict_counts;
  return {
    ordered: sourceCounts[CATEGORY.ordered.key],
    none: sourceCounts[CATEGORY.none.key],
    adverse: sourceCounts[CATEGORY.adverse.key],
    insufficient: sourceCounts[CATEGORY.insufficient.key],
    degenerate: sourceCounts[CATEGORY.degenerate.key],
  };
}
function countSum(counts) { return CATEGORY_ORDER.reduce((sum, key) => sum + counts[key], 0); }
function addCounts(a, b) {
  return Object.fromEntries(CATEGORY_ORDER.map((key) => [key, a[key] + b[key]]));
}
function emptyCounts() { return Object.fromEntries(CATEGORY_ORDER.map((key) => [key, 0])); }
function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) fail("Cannot take median of an empty array");
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function gather() {
  const brief = textFile(FILE.brief);
  const aggregation = json(FILE.aggregation);
  const curveTable = json(FILE.curveTable);
  const unitLedger = json(FILE.unitLedger);
  const reconciliation = json(FILE.reconciliation);
  const config = json(FILE.config);
  const protocol = textFile(FILE.protocol);
  const resultBlind = json(FILE.resultBlind);
  const freezeAudit = json(FILE.freezeAudit);
  const post05Manifest = json(FILE.post05Manifest);
  const post06Ledger = json(FILE.post06Ledger);
  const post06Mconf = json(FILE.post06Mconf);

  same(aggregation.rows.length, 8, "Eight band-by-scope aggregation rows");
  const findRow = (band, scope) => {
    const row = aggregation.rows.find((candidate) => candidate.band === band && candidate.curve_scope === scope);
    if (!row) fail(`Missing aggregation row ${band}/${scope}`);
    return row;
  };
  const primaryB4 = verdictCounts(findRow("SR_B4", "unit_all_scored"));
  const primaryB5 = verdictCounts(findRow("SR_B5", "unit_all_scored"));
  deepSame(primaryB4, { ordered: 0, none: 25, adverse: 41, insufficient: 24, degenerate: 0 }, "B4 primary verdict counts");
  deepSame(primaryB5, { ordered: 1, none: 48, adverse: 17, insufficient: 24, degenerate: 0 }, "B5 primary verdict counts");
  same(countSum(primaryB4), 90, "B4 primary decision total");
  same(countSum(primaryB5), 90, "B5 primary decision total");
  same(aggregation.rows.every((row) => countSum(verdictCounts(row)) === 90), true, "Every band-by-scope row has 90 decisions");

  const totals = aggregation.rows.map(verdictCounts).reduce(addCounts, emptyCounts());
  deepSame(totals, { ordered: 19, none: 177, adverse: 204, insufficient: 248, degenerate: 72 }, "All 720 verdict totals");
  const totalDecisions = countSum(totals);
  same(totalDecisions, 720, "Total scope decisions");
  same(unitLedger.rows.length, 180, "Unit ledger rows");
  same(reconciliation.counts.unit_rows, 180, "Reconciled unit rows");
  same(reconciliation.counts.curve_rows, curveTable.rows.length, "Reconciled risk-curve rows");
  const curveTableSha256 = sha256(FILE.curveTable);
  same(curveTableSha256, reconciliation.completed_output_hashes.risk_curve_table, "Frozen risk-curve table hash");
  same(unitLedger.rows.filter((row) => row.band === "SR_B4").length, 90, "B4 units");
  same(unitLedger.rows.filter((row) => row.band === "SR_B5").length, 90, "B5 units");
  same(config.curve_scopes.roles.unit_all_scored, "primary", "Primary curve scope");
  deepSame(config.risk_proxy, { ...config.risk_proxy, expression: "1-cos_i", order: "ascending_low_first" }, "Risk proxy expression and order");
  deepSame(config.verdict.risk_proxy_verdict_closed_set, [
    "not_evaluable_insufficient_scored_support",
    "not_evaluable_score_degenerate",
    "descriptive_ordering_signal",
    "directionally_adverse",
    "descriptive_non_discriminative",
  ], "Frozen five-state verdict closed set");
  same(config.lifecycle_freeze.result_values_read_before_freeze, false, "No result read before freeze");
  same(config.lifecycle_freeze.cross_audit_gate, "unanimous_pass_exactly_one_round", "Cross-audit gate");
  same(protocol.includes("risk_proxy     = 1 - cos_i"), true, "Protocol risk proxy");
  same(protocol.includes("acceptance     = ascending risk_proxy, low first"), true, "Protocol acceptance order");
  same(resultBlind.declaration.stage_7_3_residual_alpha_or_score_values_read, false, "Result-blind declaration");

  deepSame(freezeAudit.formal_cross_audit.votes, { pass: 2, block: 1 }, "Original cross-audit votes");
  deepSame(freezeAudit.formal_cross_audit.effective_votes_after_owner_adjudication, { pass: 3, block: 0 }, "Effective votes after adjudication");
  same(freezeAudit.formal_cross_audit.second_audit_round_run, false, "No second audit round");
  same(freezeAudit.result_blind_compliance.operational_deviation.occurred, true, "Read-only search deviation occurred");
  same(freezeAudit.result_blind_compliance.operational_deviation.result_pollution, false, "Deviation did not pollute result");
  same(freezeAudit.result_blind_compliance.operational_deviation.information_gain_bits, 0, "Deviation information gain");

  same(freezeAudit.formal_cross_audit.unanimous_pass, true, "Effective cross-audit pass");
  same(freezeAudit.formal_cross_audit.overall_effect, "pass", "Cross-audit overall effect");
  same(freezeAudit.validation_evidence.synthetic_tests.status, "pass", "Synthetic tests status");
  same(freezeAudit.validation_evidence.synthetic_tests.tests_run, 17, "Synthetic tests run");
  const reconciliationFields = [
    "coverage_denominator_reconciliation",
    "fold_ledger_reconciliation",
    "mask_reconciliation",
    "member_hash_reconciliation",
    "unit_terminal_state_reconciliation",
    "verdict_reconciliation",
  ];
  same(reconciliationFields.every((field) => reconciliation[field] === "pass"), true, "All reconciliations pass");

  const quarterRows = curveTable.rows.filter((row) =>
    row.scope_role === "primary"
    && row.curve_scope === "unit_all_scored"
    && row.point_kind === "fixed_grid"
    && (row.target_q === 0.25 || row.target_q === 0.75)
    && row.grid_status === "reachable"
    && Number.isFinite(row.accepted_set_MAE));
  const quarterByCurve = new Map();
  same(quarterRows.every((row) => row.canonical_target_q === row.target_q), true, "Canonical target q matches fixed-grid target");
  same(quarterRows.every((row) => row.scope_gate === "evaluated"), true, "Reachable quarter points come from evaluated scopes");
  same(quarterRows.every((row) => Number.isInteger(row.exact_point_index) && Number.isFinite(row.selective_prediction_coverage)), true, "Reachable quarter points bind exact realized coverage");
  for (const row of quarterRows) {
    const key = JSON.stringify([row.acquisition, row.band, row.fold, row.curve_scope]);
    if (!quarterByCurve.has(key)) quarterByCurve.set(key, new Map());
    const points = quarterByCurve.get(key);
    if (points.has(row.target_q)) fail(`Duplicate fixed-grid point ${key} at ${row.target_q}`);
    points.set(row.target_q, row.accepted_set_MAE);
  }
  const pairedRelativeChanges = [...quarterByCurve.values()]
    .filter((points) => points.has(0.25) && points.has(0.75))
    .map((points) => points.get(0.25) / points.get(0.75) - 1);
  const pairedMedianRelativeMaePercentExact = median(pairedRelativeChanges) * 100;
  const coverageComparison = {
    from_percent: 75,
    to_percent: 25,
    comparable_primary_curves: pairedRelativeChanges.length,
    mae_rise: pairedRelativeChanges.filter((value) => value > 0).length,
    mae_fall: pairedRelativeChanges.filter((value) => value < 0).length,
    mae_equal: pairedRelativeChanges.filter((value) => value === 0).length,
    paired_median_relative_mae_percent_exact: pairedMedianRelativeMaePercentExact,
    paired_median_relative_mae_percent_displayed: Number(pairedMedianRelativeMaePercentExact.toFixed(1)),
  };
  deepSame(coverageComparison, {
    from_percent: 75,
    to_percent: 25,
    comparable_primary_curves: 114,
    mae_rise: 93,
    mae_fall: 21,
    mae_equal: 0,
    paired_median_relative_mae_percent_exact: 18.2733791182489,
    paired_median_relative_mae_percent_displayed: 18.3,
  }, "Primary 75-to-25 coverage comparison");

  same(post05Manifest.counts.target_surface_zero_base_valid_land, 3, "Post 05 retained failure records");
  const acquisitionCount = post06Ledger.per_acquisition.length;
  const targetPixelCounts = [...new Set(post06Ledger.per_acquisition.map((member) => member.target_pixel_count))];
  same(targetPixelCounts.length, 1, "Post 06 target pixel count");
  const geometryDenominator = acquisitionCount * targetPixelCounts[0];
  const geometryRejected = post06Ledger.totals.mconf_mechanism_zero;
  const geometryComponents = post06Ledger.per_acquisition.reduce((sum, member) => ({
    self_shadow: sum.self_shadow + member.mconf_mechanism_zero.self_shadow,
    near_zero: sum.near_zero + member.mconf_mechanism_zero.near_zero,
  }), { self_shadow: 0, near_zero: 0 });
  const geometryPct = Number((geometryRejected / geometryDenominator * 100).toFixed(2));
  deepSame([acquisitionCount, targetPixelCounts[0], geometryRejected, geometryDenominator, geometryPct], [18, 488800, 81005, 8798400, 0.92], "Post 06 lower-bound calculation");
  deepSame(geometryComponents, { self_shadow: 35525, near_zero: 45480 }, "Post 06 geometry rejection components");
  same(geometryComponents.self_shadow + geometryComponents.near_zero, geometryRejected, "Post 06 geometry components reconcile");
  same(post06Mconf.factor_identity.coverage, "self_shadow_only", "Post 06 factor boundary");
  deepSame(post06Mconf.factor_identity.not_covered, [
    "cast_shadow",
    "horizon_occlusion",
    "disocclusion_boundary",
    "geometric_instability_boundary",
    "view_angle_occlusion",
  ], "Post 06 uncovered geometry mechanisms");
  same(brief.includes("不绘制任何实测曲线"), true, "Post 07 curve boundary");

  return {
    aggregation,
    config,
    primaryB4,
    primaryB5,
    totals,
    totalDecisions,
    unitCount: unitLedger.rows.length,
    retainedFailureRecords: post05Manifest.counts.target_surface_zero_base_valid_land,
    geometryPct,
    geometryRejected,
    geometryComponents,
    post06NotCovered: post06Mconf.factor_identity.not_covered,
    originalAuditVotes: freezeAudit.formal_cross_audit.votes,
    effectiveAuditVotes: freezeAudit.formal_cross_audit.effective_votes_after_owner_adjudication,
    operationalDeviation: freezeAudit.result_blind_compliance.operational_deviation,
    testsRun: freezeAudit.validation_evidence.synthetic_tests.tests_run,
    reconciliationFields,
    coverageComparison,
    curveTableSha256,
  };
}

function gridBlocks(counts, x, y, options = {}) {
  const { cell = 35, gap = 6, highlightOrdered = false } = options;
  const categories = [];
  for (const key of CATEGORY_ORDER) {
    for (let index = 0; index < counts[key]; index += 1) categories.push(key);
  }
  same(categories.length, 90, "Rendered primary grid cell count");
  return categories.map((key, index) => {
    const col = index % 10;
    const row = Math.floor(index / 10);
    const meta = CATEGORY[key];
    const extra = highlightOrdered && key === "ordered"
      ? `stroke="${C.yellow}" stroke-width="5"`
      : `stroke="${meta.stroke}" stroke-width="2"`;
    return rr(x + col * (cell + gap), y + row * (cell + gap), cell, cell, meta.color, 5, extra);
  }).join("");
}

function legendItem(x, y, key, label) {
  const meta = CATEGORY[key];
  return [
    rr(x, y - 19, 24, 24, meta.color, 5, `stroke="${meta.stroke}" stroke-width="2"`),
    txt(x + 34, y, label || meta.label, 18, { fill: C.muted, weight: 700 }),
  ].join("");
}

function stackedBar(totals, x, y, width, height) {
  let cursor = x;
  const result = [rr(x, y, width, height, C.gray, height / 2)];
  for (const key of CATEGORY_ORDER) {
    const segmentWidth = width * totals[key] / 720;
    result.push(rect(cursor, y, segmentWidth, height, CATEGORY[key].color));
    cursor += segmentWidth;
  }
  result.push(rr(x, y, width, height, "none", height / 2, `stroke="${C.ink}" stroke-width="2"`));
  return result.join("");
}

async function render(data) {
  const footer = `${data.unitCount}单元 · ${data.totalDecisions}判定 / 有序${data.totals.ordered} · 方向相反${data.totals.adverse} / 判定闭集冻结在读残差之前`;
  const figures = [];

  figures.push({
    file: "01_cover.png",
    claim: `SR_B4 的 90 个 primary 判定中，有序为 ${data.primaryB4.ordered}，方向相反为 ${data.primaryB4.adverse}。`,
    sources: [
      sourceEntry(FILE.aggregation, ["rows[band=SR_B4,curve_scope=unit_all_scored].risk_proxy_verdict_counts"], data.primaryB4),
      sourceEntry(FILE.config, ["curve_scopes.roles.unit_all_scored"], { role: "primary" }),
    ],
    render: () => writeFigure("01_cover.png", [
      rect(0, 0, W, H, C.paper),
      mountain(1090),
      rr(5, 5, 1070, 1340, "none", 28, 'stroke="#F0E5C3" stroke-width="7"'),
      seasonMark(),
      txt(540, 210, "SR_B4 的 90 个主判定里，“有序”——", 31, { fill: C.muted, weight: 800, anchor: "middle" }),
      txt(470, 785, data.primaryB4.ordered, 690, { weight: 800, anchor: "middle" }),

      `<circle cx="835" cy="420" r="92" fill="${C.panel}" stroke="${C.ink}" stroke-width="7"/>`,
      `<circle cx="835" cy="420" r="10" fill="${C.ink}"/>`,
      line(835, 420, 906, 420, C.orange, 12, 'stroke-linecap="round"'),
      `<path d="M 914 420 L 884 402 L 884 438 Z" fill="${C.orange}"/>`,
      txt(766, 428, "危险", 19, { fill: C.ink, weight: 800, anchor: "middle" }),
      txt(835, 535, "针偏偏指向另一边", 18, { fill: C.orange, weight: 800, anchor: "middle" }),

      marker(135, 845, 810, 70),
      txt(540, 906, `而“方向相反”，有 ${data.primaryB4.adverse} 个。`, 47, { fill: C.orange, weight: 800, anchor: "middle" }),
      txt(540, 1038, "我造的风险指南针，指反了。", 49, { weight: 800, anchor: "middle" }),
      txt(60, 1310, footer, 17, { fill: C.muted, weight: 500 }),
    ].join("")),
  });

  figures.push({
    file: "02_exam_rules.png",
    claim: "结果盲冻结的 risk_proxy=1-cos_i 只在已有可评分支持的像元内按低风险优先接纳，并在读取受保护残差前冻结五态 verdict 闭集；曲线仅为机制示意。",
    sources: [
      sourceEntry(FILE.config, ["lifecycle_freeze", "risk_proxy", "verdict.risk_proxy_verdict_closed_set"], {
        freeze_phase: data.config.lifecycle_freeze.phase,
        result_values_read_before_freeze: data.config.lifecycle_freeze.result_values_read_before_freeze,
        risk_proxy: data.config.risk_proxy,
        verdict_closed_set: data.config.verdict.risk_proxy_verdict_closed_set,
      }),
      sourceEntry(FILE.protocol, ["§2 scoreable mask, support and permanent abstention", "§8 shape and verdict"], {
        expression: "risk_proxy = 1 - cos_i",
        acceptance: "ascending risk_proxy, low first",
      }),
    ],
    render: () => writeFigure("02_exam_rules.png", [
      page("考试规则，在看卷子之前就冻结了", "机制示意 · 不是结果图", footer, { titleSize: 44 }),
      rr(830, 174, 190, 38, C.yellow, 19),
      txt(925, 202, "SCHEMATIC", 24, { weight: 800, anchor: "middle" }),

      rr(60, 250, 280, 182, C.panel, 24, `stroke="${C.line}" stroke-width="3"`),
      `<circle cx="112" cy="303" r="27" fill="${C.yellow}"/>`,
      txt(112, 313, "1", 27, { weight: 800, anchor: "middle" }),
      txt(200, 302, "给危险分", 27, { weight: 800, anchor: "middle" }),
      txt(200, 351, "1 − cos_i", 33, { fill: C.orange, weight: 800, anchor: "middle" }),
      multi(200, 382, ["越不正对太阳，", "分越高"], 24, 30, { fill: C.muted, weight: 700, anchor: "middle" }),

      line(348, 340, 370, 340, C.ink, 5, 'stroke-linecap="round"'),
      `<path d="M 378 340 L 360 329 L 360 351 Z" fill="${C.ink}"/>`,
      rr(400, 250, 280, 182, C.panel, 24, `stroke="${C.line}" stroke-width="3"`),
      `<circle cx="452" cy="303" r="27" fill="${C.yellow}"/>`,
      txt(452, 313, "2", 27, { weight: 800, anchor: "middle" }),
      txt(540, 302, "先拒危险", 27, { weight: 800, anchor: "middle" }),
      rr(455, 340, 36, 36, C.orange, 6),
      rr(500, 340, 36, 36, C.orange, 6),
      rr(545, 340, 36, 36, C.gray, 6),
      rr(590, 340, 36, 36, C.gray, 6),
      txt(540, 408, "保留比例 从高到低", 24, { fill: C.muted, weight: 700, anchor: "middle" }),

      line(688, 340, 710, 340, C.ink, 5, 'stroke-linecap="round"'),
      `<path d="M 718 340 L 700 329 L 700 351 Z" fill="${C.ink}"/>`,
      rr(740, 250, 280, 182, C.panel, 24, `stroke="${C.line}" stroke-width="3"`),
      `<circle cx="792" cy="303" r="27" fill="${C.yellow}"/>`,
      txt(792, 313, "3", 27, { weight: 800, anchor: "middle" }),
      txt(880, 302, "再看误差", 27, { weight: 800, anchor: "middle" }),
      multi(880, 353, ["留下的像元", "误差降不降"], 24, 34, { weight: 700, anchor: "middle" }),

      rr(60, 470, 960, 250, C.panel2, 26),
      multi(90, 520, [
        "如果指南针有用，",
        "拒掉高风险后，",
        "留下的误差应该下降。",
      ], 24, 39, { weight: 800 }),
      txt(90, 640, "只在已有可评分支持的像元内排序。", 24, { fill: C.muted, weight: 800 }),
      txt(90, 676, "这里只画期望方向，不画结果。", 24, { fill: C.muted, weight: 700 }),
      line(500, 665, 965, 665, C.ink, 3, 'stroke-linecap="round"'),
      `<path d="M 972 665 L 954 655 L 954 675 Z" fill="${C.ink}"/>`,
      line(500, 665, 500, 515, C.ink, 3, 'stroke-linecap="round"'),
      `<path d="M 500 507 L 490 525 L 510 525 Z" fill="${C.ink}"/>`,
      txt(735, 699, "保留比例：100% → 更低", 24, { fill: C.muted, weight: 700, anchor: "middle" }),
      txt(483, 540, "MAE", 24, { fill: C.muted, weight: 700, anchor: "end" }),
      `<path d="M 535 540 C 650 550, 750 610, 930 638" fill="none" stroke="${C.orange}" stroke-width="6" stroke-linecap="round" stroke-dasharray="14 12"/>`,
      `<path d="M 930 638 L 903 623 L 907 648 Z" fill="${C.orange}"/>`,
      txt(748, 537, "如果指南针有用，应该长这样", 24, { fill: C.orange, weight: 800, anchor: "middle" }),
      txt(748, 576, "机制示意，非实测曲线", 24, { fill: C.muted, weight: 800, anchor: "middle" }),

      txt(60, 760, "冻结的五种判定", 24, { weight: 800 }),
      rr(60, 785, 293, 72, C.green, 18),
      txt(95, 832, "↗  有序", 25, { fill: C.paper, weight: 800 }),
      rr(394, 785, 293, 72, C.gray, 18, `stroke="${C.grayDark}" stroke-width="2"`),
      txt(429, 832, "≈  无区分", 25, { weight: 800 }),
      rr(728, 785, 292, 72, C.orange, 18),
      txt(763, 832, "↘  方向相反", 25, { fill: C.paper, weight: 800 }),
      rr(225, 875, 293, 72, C.beige, 18, 'stroke="#BDA869" stroke-width="2"'),
      txt(260, 922, "∅  支持不足", 25, { weight: 800 }),
      rr(563, 875, 293, 72, C.dark, 18),
      txt(598, 922, "—  分数退化", 25, { fill: C.paper, weight: 800 }),

      marker(145, 1000, 790, 62),
      multi(540, 1050, [
        "“方向相反”也是合法结果——",
        "不许事后改分数。",
      ], 34, 47, { fill: C.orange, weight: 800, anchor: "middle" }),
      underline(308, 1112, 464, C.orange, 6),
    ].join("")),
  });

  figures.push({
    file: "03_real_verdict_counts.png",
    claim: `B4/B5 primary 各 90 个判定严格按冻结五态计数绘制；全部 720 个 scope 判定为 ${JSON.stringify(data.totals)}。`,
    sources: [
      sourceEntry(FILE.aggregation, ["rows[].band", "rows[].curve_scope", "rows[].risk_proxy_verdict_counts"], {
        B4_unit_all_scored: data.primaryB4,
        B5_unit_all_scored: data.primaryB5,
        all_8_band_scope_rows: data.totals,
      }),
      sourceEntry(FILE.unitLedger, ["rows[].band"], { unit_count: data.unitCount, B4_units: 90, B5_units: 90 }),
      sourceEntry(FILE.config, ["curve_scopes.roles.unit_all_scored"], { unit_all_scored: "primary" }),
    ],
    render: () => writeFigure("03_real_verdict_counts.png", [
      page("180个主判定跑完，指针这样倒", "主判定（所有可评分像元）· B4/B5各90；每格＝1景×1空间折", footer, { titleSize: 44 }),
      rr(60, 230, 225, 38, C.ink, 19),
      txt(172, 256, "真实判定计数 · 非示意", 17, { fill: C.paper, weight: 800, anchor: "middle" }),
      legendItem(330, 255, "ordered"),
      legendItem(455, 255, "none"),
      legendItem(595, 255, "adverse"),
      legendItem(765, 255, "insufficient"),
      legendItem(930, 255, "degenerate", "退化"),

      rr(50, 290, 480, 530, C.panel, 26, `stroke="${C.line}" stroke-width="3"`),
      txt(80, 335, "SR_B4 · 90个主判定", 27, { weight: 800 }),
      rr(412, 310, 34, 34, "none", 5, `stroke="${C.green}" stroke-width="4"`),
      txt(458, 336, "有序 0个", 19, { fill: C.green, weight: 800 }),
      gridBlocks(data.primaryB4, 76, 385),
      multi(290, 770, [
        `方向相反 ${data.primaryB4.adverse} · 无区分 ${data.primaryB4.none}`,
        `支持不足 ${data.primaryB4.insufficient} · 有序 ${data.primaryB4.ordered}`,
      ], 18, 28, { fill: C.muted, weight: 800, anchor: "middle" }),

      rr(550, 290, 480, 530, C.panel, 26, `stroke="${C.line}" stroke-width="3"`),
      txt(580, 335, "SR_B5 · 90个主判定", 27, { weight: 800 }),
      txt(835, 365, "唯一的“有序”", 20, { fill: C.orange, weight: 800 }),
      line(810, 369, 612, 402, C.orange, 4, 'stroke-linecap="round"'),
      `<path d="M 612 402 L 629 388 L 634 410 Z" fill="${C.orange}"/>`,
      gridBlocks(data.primaryB5, 576, 385, { highlightOrdered: true }),
      multi(790, 770, [
        `无区分 ${data.primaryB5.none} · 方向相反 ${data.primaryB5.adverse}`,
        `支持不足 ${data.primaryB5.insufficient} · 有序 ${data.primaryB5.ordered}`,
      ], 18, 28, { fill: C.muted, weight: 800, anchor: "middle" }),

      txt(60, 858, `全部 ${data.totalDecisions} 个判定`, 22, { weight: 800 }),
      txt(1020, 858, "8组 band × scope · 每组90", 18, { fill: C.muted, weight: 700, anchor: "end" }),
      stackedBar(data.totals, 60, 875, 960, 34),
      txt(540, 947, `有序${data.totals.ordered} / 无区分${data.totals.none} / 方向相反${data.totals.adverse} / 支持不足${data.totals.insufficient} / 退化${data.totals.degenerate}`, 21, { weight: 800, anchor: "middle" }),
      txt(540, 1005, "在方向可判的结果里，", 31, { fill: C.orange, weight: 800, anchor: "middle" }),
      txt(540, 1052, "我标成最危险的地方，当前基线模型往往错得更少。", 36, { fill: C.orange, weight: 800, anchor: "middle" }),
      txt(540, 1105, "单ROI · 空间折不是独立样本 · 仅作描述，不解释为什么", 21, { fill: C.muted, weight: 700, anchor: "middle" }),
    ].join("")),
  });

  figures.push({
    file: "04_frozen_season_ledger.png",
    claim: `季终卡把 Post 05/06 的冻结缺口、程序验收结果与固定网格 q=75%→25% 的 ${data.coverageComparison.comparable_primary_curves} 条可比主曲线并列存档；配对 MAE 变化中位数为 +${data.coverageComparison.paired_median_relative_mae_percent_displayed.toFixed(1)}%。`,
    sources: [
      sourceEntry(FILE.post06Ledger, ["totals.mconf_mechanism_zero", "per_acquisition[].target_pixel_count", "per_acquisition[].mconf_mechanism_zero.self_shadow", "per_acquisition[].mconf_mechanism_zero.near_zero"], {
        geometry_rejection_count: data.geometryRejected,
        geometry_rejection_components: data.geometryComponents,
        lower_bound_percent: data.geometryPct,
      }),
      sourceEntry(FILE.post06Mconf, ["factor_identity.coverage", "factor_identity.not_covered", "factor_identity.coverage_caveat"], {
        coverage: "self_shadow_only",
        not_covered: data.post06NotCovered,
      }),
      sourceEntry(FILE.post05Manifest, ["counts.target_surface_zero_base_valid_land", "counts.evidence_membership_included"], {
        retained_failure_records: data.retainedFailureRecords,
        evidence_membership_included: 21,
      }),
      sourceEntry(FILE.freezeAudit, ["formal_cross_audit.votes", "formal_cross_audit.effective_votes_after_owner_adjudication", "formal_cross_audit.overall_effect", "validation_evidence.synthetic_tests"], {
        original_votes: data.originalAuditVotes,
        effective_votes_after_owner_adjudication: data.effectiveAuditVotes,
        overall_effect: "pass",
        synthetic_tests: { status: "pass", tests_run: data.testsRun },
      }),
      sourceEntry(FILE.reconciliation, data.reconciliationFields, Object.fromEntries(data.reconciliationFields.map((field) => [field, "pass"]))),
      sourceEntry(FILE.curveTable, [
        "rows[].point_kind",
        "rows[].scope_role",
        "rows[].curve_scope",
        "rows[].acquisition",
        "rows[].band",
        "rows[].fold",
        "rows[].target_q",
        "rows[].canonical_target_q",
        "rows[].grid_status",
        "rows[].scope_gate",
        "rows[].exact_point_index",
        "rows[].selective_prediction_coverage",
        "rows[].accepted_set_MAE",
      ], {
        filters: {
          point_kind: "fixed_grid",
          scope_role: "primary",
          curve_scope: "unit_all_scored",
          grid_status: "reachable",
          target_q: [0.25, 0.75],
          both_endpoints_required: true,
        },
        pairing_key: ["acquisition", "band", "fold", "curve_scope"],
        formula: "100 * (accepted_set_MAE[q=0.25] / accepted_set_MAE[q=0.75] - 1)",
        derived: data.coverageComparison,
      }, { source_sha256: data.curveTableSha256 }),
    ],
    render: () => writeFigure("04_frozen_season_ledger.png", [
      page("修补前的账本，到此全部冻结", "程序关卡通过，不替科学假设背书", footer, { titleSize: 46, mountainY: 1220 }),
      rr(60, 240, 960, 440, C.ink, 28),
      txt(90, 282, "FROZEN LEDGER · 修补前", 18, { fill: C.yellow, weight: 800 }),
      txt(90, 345, `${data.geometryPct.toFixed(2)}%`, 29, { fill: C.yellow, weight: 800, family: "'SFMono-Regular','Menlo',monospace" }),
      txt(340, 345, "几何拒绝的下界（第六篇）", 27, { fill: C.paper, weight: 700 }),
      line(90, 375, 990, 375, "#343532", 2),
      txt(90, 430, `${data.retainedFailureRecords} 景`, 29, { fill: C.yellow, weight: 800, family: "'SFMono-Regular','Menlo',monospace" }),
      txt(340, 430, "失败记录保留在案，未删（第五篇）", 27, { fill: C.paper, weight: 700 }),
      line(90, 460, 990, 460, "#343532", 2),
      txt(90, 515, "判据边界", 26, { fill: C.yellow, weight: 800, family: "'SFMono-Regular','Menlo',monospace" }),
      txt(340, 515, "仅覆盖自阴影/近零入射，不含投射阴影等", 27, { fill: C.paper, weight: 700 }),
      line(90, 545, 990, 545, "#343532", 2),
      txt(90, 600, "1 − cos_i", 27, { fill: C.yellow, weight: 800, family: "'SFMono-Regular','Menlo',monospace" }),
      txt(340, 600, "本ROI：不构成可靠的风险排序代理", 27, { fill: C.paper, weight: 700 }),
      txt(990, 651, `方向相反${data.totals.adverse} > 有序${data.totals.ordered} · 描述性`, 19, { fill: "#F6C5B4", weight: 800, anchor: "end" }),

      rr(60, 700, 960, 345, C.panel2, 26),
      txt(90, 746, "程序关卡全过，排序假设没过", 34, { weight: 800 }),
      rr(90, 770, 420, 50, C.greenSoft, 15, `stroke="${C.green}" stroke-width="2"`),
      txt(300, 804, "✓ 规则先冻结 · 交叉审计通过", 21, { fill: C.green, weight: 800, anchor: "middle" }),
      rr(530, 770, 460, 50, C.greenSoft, 15, `stroke="${C.green}" stroke-width="2"`),
      txt(760, 804, `✓ 六项 reconciliation PASS · 测试 ${data.testsRun}/${data.testsRun}`, 20, { fill: C.green, weight: 800, anchor: "middle" }),

      rr(80, 845, 210, 150, C.yellow, 20),
      txt(185, 910, `${data.coverageComparison.from_percent}% → ${data.coverageComparison.to_percent}%`, 34, { weight: 800, anchor: "middle" }),
      txt(185, 958, "固定网格 q", 23, { fill: C.muted, weight: 800, anchor: "middle" }),

      rr(305, 845, 210, 150, C.panel, 20, `stroke="${C.line}" stroke-width="3"`),
      txt(410, 918, data.coverageComparison.comparable_primary_curves, 56, { weight: 800, anchor: "middle" }),
      txt(410, 958, "可比主曲线", 23, { fill: C.muted, weight: 800, anchor: "middle" }),

      rr(530, 845, 210, 150, C.panel, 20, `stroke="${C.line}" stroke-width="3"`),
      txt(585, 914, `${data.coverageComparison.mae_rise}↑`, 39, { fill: C.orange, weight: 800, anchor: "middle" }),
      txt(688, 914, `${data.coverageComparison.mae_fall}↓`, 39, { fill: C.green, weight: 800, anchor: "middle" }),
      txt(635, 958, "MAE上升 / 下降", 21, { fill: C.muted, weight: 800, anchor: "middle" }),

      rr(755, 845, 245, 150, C.ink, 20),
      txt(877, 916, `+${data.coverageComparison.paired_median_relative_mae_percent_displayed.toFixed(1)}%`, 48, { fill: C.yellow, weight: 800, anchor: "middle" }),
      txt(877, 958, "配对MAE相对变化中位数", 20, { fill: C.paper, weight: 800, anchor: "middle" }),

      marker(105, 1070, 870, 62),
      txt(540, 1117, "回答要有证据，拒答也要有证据。", 34, { weight: 800, anchor: "middle" }),
      multi(540, 1182, [
        "第一篇：背阴坡不是黑。",
        "第七篇：连“哪里更危险”也不能靠直觉。",
      ], 25, 40, { fill: C.muted, weight: 800, anchor: "middle" }),
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
    schema: "mountainrs-xiaohongshu-post-07-figure-sources-v1",
    rendering: {
      renderer: "render_post_07.js",
      dimensions: "1080x1350",
      source_base: "stage7_real_weak_closure/stage7_4_residual_reliability",
      numeric_policy: "Every displayed result count is read from frozen Stage 7.4 aggregation/ledger/curve artifacts or derived after exact equality checks. Post 05/06 callbacks are read from their frozen Stage 7.1/7.2 ledgers.",
      curve_policy: "No measured curve is drawn. Card 02 contains one fixed SVG mechanism sketch labeled non-measured. Card 04 reads only frozen fixed-grid MAE rows to derive paired counts and a median; it does not plot any measured curve.",
      grid_policy: "Card 03 renders exactly two 10x9 primary grids. Each square is one verdict count; squares are grouped by verdict category and encode no temporal or spatial ordering.",
      paired_curve_policy: "Card 04 pairs only primary unit_all_scored curves with reachable fixed-grid q=0.75 and q=0.25 endpoints by acquisition, band, fold, and curve_scope. Relative MAE change is 100*(MAE_q025/MAE_q075-1); the displayed +18.3% is the median of 114 per-curve changes.",
      visual_system: "Warm-paper series system with ink headlines, yellow marker, orange annotations, mountain footer, quote mark, and a season-final badge.",
    },
    derived_values: {
      unit_count: data.unitCount,
      scope_decision_count: data.totalDecisions,
      all_verdict_counts: data.totals,
      B4_primary_counts: data.primaryB4,
      B5_primary_counts: data.primaryB5,
      post06_geometry_rejection_lower_bound_percent: data.geometryPct,
      post05_retained_failure_records: data.retainedFailureRecords,
      primary_fixed_grid_75_to_25: data.coverageComparison,
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
  process.stdout.write(`Rendered 4 evidence-led post_07 cards and contact sheet to ${OUT}\n`);
}

main().catch((error) => {
  process.stderr.write(`post_07 render failed: ${error.stack || error.message}\n`);
  process.exitCode = 1;
});
