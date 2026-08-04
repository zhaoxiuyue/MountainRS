#!/usr/bin/env node
"use strict";

/*
 * Deterministic renderer for MountainRS Xiaohongshu post 03.
 * It only reads frozen C5-D3 report/evidence files and existing GeoTIFFs.
 * It does not execute, fit, score, or modify the C5-D3 experiment.
 */

const fs = require("fs");
const path = require("path");
const sharp = require("sharp");

const W = 1080;
const H = 1350;
const SCRIPT_DIR = __dirname;
const OUT = path.basename(SCRIPT_DIR) === "post_03_support" ? path.resolve(SCRIPT_DIR, "../post_03") : SCRIPT_DIR;
const META_OUT = SCRIPT_DIR;
const ROOT = path.resolve(OUT, "../../../..");
const PREFIX = "stage6_5_real_landsat_observation_stress_test";
const RUN = `${PREFIX}/evidence/stage6_5_3_b/c5_d3_35789933202effad`;
const REL = (relative) => path.join(ROOT, relative);

const C = {
  ink: "#111210",
  deep: "#FFF9E8",
  panel: "#FFFDF7",
  panel2: "#FFF3CF",
  sage: "#D8DDCB",
  cream: "#111210",
  muted: "#5E605B",
  orange: "#E54817",
  orangeSoft: "#F7D34E",
  red: "#D83B13",
  purple: "#86679B",
  yellow: "#F7D34E",
  line: "#DDD3B9",
  hard: "#505A56",
  soft: "#E4A23D",
  diffuse: "#E54817",
  mountain1: "#F8E9B8",
  mountain2: "#F3DFA0",
};

const FOOTER = "2 acquisitions / 10 spatial challenges；空间折不是独立统计重复";

function fail(message) {
  throw new Error(message);
}
function exists(relative) {
  const full = REL(relative);
  if (!fs.existsSync(full)) fail(`Missing source: ${relative}`);
  return full;
}
function readJson(relative) {
  return JSON.parse(fs.readFileSync(exists(relative), "utf8"));
}
function readCsv(relative) {
  const lines = fs.readFileSync(exists(relative), "utf8").trim().split(/\r?\n/);
  const header = lines.shift().split(",");
  return lines.map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(header.map((key, index) => [key, cells[index] ?? ""]));
  });
}
function median(values) {
  const sorted = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) fail("Cannot calculate median of an empty value list.");
  return sorted[Math.floor(sorted.length / 2)];
}
function approx(actual, expected, label) {
  if (Math.abs(actual - expected) > 0.0000008) {
    fail(`${label}: expected ${expected}, got ${actual}`);
  }
}
function esc(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function rect(x, y, width, height, fill, extra = "") {
  return `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${extra.includes("rx=") ? "" : 0}" fill="${fill}" ${extra}/>`;
}
function roundRect(x, y, width, height, fill, radius = 22, extra = "") {
  return `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${radius}" fill="${fill}" ${extra}/>`;
}
function line(x1, y1, x2, y2, stroke = C.line, width = 2, extra = "") {
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${width}" ${extra}/>`;
}
function text(x, y, value, size = 30, options = {}) {
  const {
    fill = C.cream,
    weight = 400,
    anchor = "start",
    opacity = 1,
    letter = 0,
    family = "'PingFang SC','STHeiti','Arial Unicode MS',sans-serif",
  } = options;
  return `<text x="${x}" y="${y}" font-family="${family}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}" opacity="${opacity}" letter-spacing="${letter}">${esc(value)}</text>`;
}
function multiline(x, y, values, size, lineHeight, options = {}) {
  return values.map((value, index) => text(x, y + index * lineHeight, value, size, options)).join("");
}
function svg(content) {
  return Buffer.from(
    `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
      <style>text { font-kerning: normal; }</style>${content}
    </svg>`,
    "utf8",
  );
}
function badge(x, y, label, fill = C.orange, textFill = C.ink) {
  const width = Math.max(142, label.length * 17 + 36);
  return `${roundRect(x, y, width, 42, fill, 21)}${text(x + 18, y + 29, label, 18, { fill: textFill, weight: 700, letter: 0.4 })}`;
}
function quoteMark(x = 64, y = 126, anchor = "start") {
  return text(x, y, "“", 108, { fill: C.yellow, weight: 800, anchor, opacity: 0.62 });
}
function marker(x, y, width, height = 54, fill = C.yellow, opacity = 0.88) {
  const top = y + 7;
  const bottom = y + height - 7;
  return `<path d="M ${x} ${top + 5} C ${x + width * 0.12} ${y - 2}, ${x + width * 0.28} ${top + 2}, ${x + width * 0.43} ${top}
    C ${x + width * 0.62} ${top - 5}, ${x + width * 0.82} ${top + 2}, ${x + width} ${top + 5}
    L ${x + width - 9} ${bottom + 2} C ${x + width * 0.78} ${bottom + 8}, ${x + width * 0.57} ${bottom - 2}, ${x + width * 0.39} ${bottom + 4}
    C ${x + width * 0.24} ${bottom + 8}, ${x + width * 0.10} ${bottom - 3}, ${x + 6} ${bottom + 1} Z" fill="${fill}" opacity="${opacity}"/>`;
}
function handUnderline(x, y, width, color = C.orange, strokeWidth = 6) {
  return `<path d="M ${x} ${y} C ${x + width * 0.24} ${y - 6}, ${x + width * 0.53} ${y + 7}, ${x + width} ${y - 1}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" stroke-linecap="round"/>`;
}
function mountainMotif(y = 1160) {
  return `<path d="M 0 ${H} L 0 ${y + 142}
    C 92 ${y + 139}, 186 ${y + 74}, 276 ${y + 82}
    C 360 ${y + 90}, 438 ${y + 144}, 526 ${y + 137}
    C 632 ${y + 129}, 713 ${y + 70}, 787 ${y + 18}
    C 834 ${y - 15}, 865 ${y - 18}, 904 ${y + 12}
    C 951 ${y + 48}, 1008 ${y + 100}, 1080 ${y + 116}
    L 1080 ${H} Z" fill="${C.mountain1}" opacity="0.66"/>
    <path d="M 0 ${H} L 0 ${y + 164}
    C 126 ${y + 158}, 208 ${y + 111}, 284 ${y + 120}
    C 370 ${y + 130}, 449 ${y + 174}, 535 ${y + 164}
    C 633 ${y + 153}, 697 ${y + 118}, 751 ${y + 92}
    C 815 ${y + 62}, 858 ${y + 80}, 906 ${y + 107}
    C 969 ${y + 142}, 1023 ${y + 151}, 1080 ${y + 153}
    L 1080 ${H} Z" fill="${C.mountain2}" opacity="0.56"/>`;
}
function outerBorder() {
  return `<rect x="4" y="4" width="1072" height="1342" rx="30" fill="none" stroke="#F0E5C3" stroke-width="7"/>`;
}
function footer() {
  return text(60, 1310, FOOTER, 20, { fill: C.muted, weight: 500 });
}
function pageBase(section, title, subtitle = "") {
  return `${rect(0, 0, W, H, C.deep)}${mountainMotif(1172)}${outerBorder()}${quoteMark(1010, 106, "end")}
    ${text(60, 146, title, 52, { fill: C.cream, weight: 800 })}
    ${handUnderline(60, 213, 142, C.yellow, 7)}
    ${subtitle ? text(60, 192, subtitle, 25, { fill: C.muted, weight: 500 }) : ""}`;
}
function pageHeader(section, title, subtitle = "") {
  return `${mountainMotif(1172)}${outerBorder()}${quoteMark(1010, 106, "end")}
    ${text(60, 146, title, 52, { fill: C.cream, weight: 800 })}
    ${handUnderline(60, 213, 142, C.yellow, 7)}
    ${subtitle ? text(60, 192, subtitle, 25, { fill: C.muted, weight: 500 }) : ""}`;
}
function fmt(value, digits = 4) {
  return Number(value).toFixed(digits);
}
function prettyMethod(method) {
  return {
    hard_mask: "hard mask",
    soft_weight_k30: "soft weight",
    bounded_scene_constant_diffuse: "bounded diffuse",
  }[method] || method;
}

/*
 * C5-D3 canonical masks are uint8, LZW-compressed, tiled GeoTIFFs with
 * PlanarConfiguration=2. sharp/libvips deliberately does not decode tiled
 * separate planes, so this small reader handles only that frozen mask schema.
 * It is read-only and rejects any unexpected input rather than guessing.
 */
const canonicalMaskCache = new Map();
function tiffTypeSize(type) {
  return ({ 1: 1, 2: 1, 3: 2, 4: 4 })[type] || 0;
}
function readCanonicalMaskTiff(filename) {
  if (canonicalMaskCache.has(filename)) return canonicalMaskCache.get(filename);
  const bytes = fs.readFileSync(filename);
  const order = bytes.toString("ascii", 0, 2);
  if (order !== "II") fail(`Canonical mask must be little-endian TIFF: ${path.basename(filename)}`);
  const u16 = (offset) => bytes.readUInt16LE(offset);
  const u32 = (offset) => bytes.readUInt32LE(offset);
  if (u16(2) !== 42) fail(`Unsupported TIFF magic: ${path.basename(filename)}`);
  const firstIfd = u32(4);
  const entryCount = u16(firstIfd);
  const tags = new Map();
  for (let i = 0; i < entryCount; i += 1) {
    const at = firstIfd + 2 + i * 12;
    const tag = u16(at);
    const type = u16(at + 2);
    const count = u32(at + 4);
    const size = tiffTypeSize(type);
    if (!size) continue;
    const valueAt = count * size <= 4 ? at + 8 : u32(at + 8);
    const values = [];
    for (let j = 0; j < count; j += 1) {
      const p = valueAt + j * size;
      values.push(type === 3 ? u16(p) : type === 4 ? u32(p) : bytes[p]);
    }
    tags.set(tag, values);
  }
  const scalar = (tag, label) => {
    const values = tags.get(tag);
    if (!values || values.length !== 1) fail(`Canonical TIFF missing ${label}: ${path.basename(filename)}`);
    return values[0];
  };
  const width = scalar(256, "ImageWidth");
  const height = scalar(257, "ImageLength");
  const bits = tags.get(258);
  const compression = scalar(259, "Compression");
  const samples = scalar(277, "SamplesPerPixel");
  const planar = scalar(284, "PlanarConfiguration");
  const tileWidth = scalar(322, "TileWidth");
  const tileHeight = scalar(323, "TileLength");
  const predictor = (tags.get(317) || [1])[0];
  const offsets = tags.get(324);
  const byteCounts = tags.get(325);
  if (!bits || bits.length !== samples || !bits.every((value) => value === 8) || compression !== 5 || samples !== 5 || planar !== 2 || predictor !== 1 || !offsets || !byteCounts || offsets.length !== byteCounts.length) {
    fail(`Unexpected canonical TIFF schema: ${path.basename(filename)}`);
  }
  const tilesAcross = Math.ceil(width / tileWidth);
  const tilesDown = Math.ceil(height / tileHeight);
  const tilesPerBand = tilesAcross * tilesDown;
  if (offsets.length !== samples * tilesPerBand) fail(`Unexpected canonical tile count: ${path.basename(filename)}`);
  const bands = Array.from({ length: samples }, () => Buffer.alloc(width * height));
  for (let band = 0; band < samples; band += 1) {
    for (let tile = 0; tile < tilesPerBand; tile += 1) {
      const index = band * tilesPerBand + tile;
      const compressed = bytes.subarray(offsets[index], offsets[index] + byteCounts[index]);
      const decoded = decodeTiffLzw(compressed);
      const tx = (tile % tilesAcross) * tileWidth;
      const ty = Math.floor(tile / tilesAcross) * tileHeight;
      const copyW = Math.min(tileWidth, width - tx);
      const copyH = Math.min(tileHeight, height - ty);
      if (decoded.length < tileWidth * tileHeight) fail(`Truncated canonical tile: ${path.basename(filename)}`);
      for (let row = 0; row < copyH; row += 1) {
        decoded.copy(bands[band], (ty + row) * width + tx, row * tileWidth, row * tileWidth + copyW);
      }
    }
  }
  const unexpected = new Set();
  for (const band of bands) {
    for (const value of band) if (value !== 0 && value !== 1 && value !== 255) unexpected.add(value);
  }
  if (unexpected.size) fail(`Canonical mask has unexpected samples (${[...unexpected].slice(0, 12).join(",")}): ${path.basename(filename)}`);
  const decoded = { width, height, bands };
  canonicalMaskCache.set(filename, decoded);
  return decoded;
}
function decodeTiffLzw(input) {
  let bitPosition = 0;
  const getCode = (width) => {
    if (bitPosition + width > input.length * 8) return null;
    let code = 0;
    for (let bit = 0; bit < width; bit += 1) {
      const absolute = bitPosition + bit;
      code = (code << 1) | ((input[absolute >> 3] >> (7 - (absolute & 7))) & 1);
    }
    bitPosition += width;
    return code;
  };
  const reset = () => {
    const table = Array.from({ length: 258 }, (_, index) => Buffer.from([index]));
    return table;
  };
  let table = reset();
  let codeWidth = 9;
  let previous = null;
  const chunks = [];
  for (;;) {
    const code = getCode(codeWidth);
    if (code === null) break;
    if (code === 256) {
      table = reset();
      codeWidth = 9;
      previous = null;
      continue;
    }
    if (code === 257) break;
    let entry;
    if (code < table.length && table[code]) {
      entry = table[code];
    } else if (code === table.length && previous) {
      entry = Buffer.concat([previous, previous.subarray(0, 1)]);
    } else {
      fail("Invalid TIFF LZW stream.");
    }
    chunks.push(entry);
    if (previous && table.length < 4096) {
      table.push(Buffer.concat([previous, entry.subarray(0, 1)]));
      // TIFF LZW uses the EarlyChange=1 code-width transition.
      if (table.length === (1 << codeWidth) - 1 && codeWidth < 12) codeWidth += 1;
    }
    previous = entry;
  }
  return Buffer.concat(chunks);
}

async function actualScene(rawRelative, maskRelative, width, height, overlays) {
  const raw = exists(rawRelative);
  const masks = exists(maskRelative);
  const canonical = readCanonicalMaskTiff(masks);
  const base = await sharp(raw)
    .normalise()
    .linear(1.45, 12)
    .resize(width, height, { fit: "cover", position: "centre" })
    .tint(C.sage)
    .modulate({ brightness: 0.92, saturation: 0.60 })
    .png()
    .toBuffer();
  const layers = [];
  for (const overlay of overlays) {
    const source = canonical.bands[overlay.band];
    const alphaRaw = Buffer.alloc(source.length);
    for (let i = 0; i < source.length; i += 1) alphaRaw[i] = source[i] === 1 ? Math.round(255 * overlay.opacity) : 0;
    const alpha = await sharp(alphaRaw, { raw: { width: canonical.width, height: canonical.height, channels: 1 } })
      .resize(width, height, { fit: "cover", position: "centre" })
      .png()
      .toBuffer();
    const colored = await sharp({
      create: { width, height, channels: 3, background: overlay.color },
    }).joinChannel(alpha).png().toBuffer();
    layers.push({ input: colored });
  }
  return sharp(base).composite(layers).png().toBuffer();
}

async function actualB4Preview(previewRelative, width, height) {
  /*
   * These are the existing formal stage-6.5 local-check images. The crop is
   * the labelled B4 reflectance panel only; no values are recomputed here.
   */
  return sharp(exists(previewRelative))
    .flatten({ background: "#FFFFFF" })
    .extract({ left: 20, top: 70, width: 510, height: 600 })
    .resize(width, height, { fit: "cover", position: "centre" })
    .png()
    .toBuffer();
}

async function canonicalMaskMap(maskRelative, width, height) {
  const canonical = readCanonicalMaskTiff(exists(maskRelative));
  const output = Buffer.alloc(canonical.width * canonical.height * 3);
  const rgb = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
  const base = rgb("#0C241E");
  const lit = rgb(C.yellow);
  const nearZero = rgb(C.purple);
  const shadow = rgb(C.orange);
  for (let i = 0; i < canonical.width * canonical.height; i += 1) {
    let color = base;
    if (canonical.bands[4][i] === 1) color = lit;
    if (canonical.bands[3][i] === 1) color = nearZero;
    if (canonical.bands[2][i] === 1) color = shadow;
    output[i * 3] = color[0];
    output[i * 3 + 1] = color[1];
    output[i * 3 + 2] = color[2];
  }
  return sharp(output, { raw: { width: canonical.width, height: canonical.height, channels: 3 } })
    .resize(width, height, { fit: "cover", position: "centre" })
    .png()
    .toBuffer();
}

async function renderPng(filename, content, layers = []) {
  const destination = path.join(OUT, filename);
  await sharp({ create: { width: W, height: H, channels: 3, background: C.deep } })
    .composite([...layers, { input: svg(content) }])
    .png({ compressionLevel: 9, palette: false })
    .toFile(destination);
  const metadata = await sharp(destination).metadata();
  if (metadata.width !== W || metadata.height !== H || metadata.format !== "png") {
    fail(`Invalid final asset: ${filename}`);
  }
}

function groupedBars({ x, y, width, height, groups, maximum, yTicks, legendY, barLabelY = 23 }) {
  const methods = [
    { key: "hard_mask", label: "hard", color: C.hard },
    { key: "soft_weight_k30", label: "soft k=30", color: C.soft },
    { key: "bounded_scene_constant_diffuse", label: "diffuse", color: C.diffuse },
  ];
  let out = "";
  for (const tick of yTicks) {
    const py = y + height - (tick / maximum) * height;
    out += line(x, py, x + width, py, tick === 0 ? C.cream : C.line, tick === 0 ? 2 : 1);
    out += text(x - 16, py + 7, tick.toFixed(2), 18, { fill: C.muted, anchor: "end" });
  }
  const groupWidth = width / groups.length;
  const barWidth = 50;
  groups.forEach((group, groupIndex) => {
    const gx = x + groupIndex * groupWidth + groupWidth / 2;
    methods.forEach((method, methodIndex) => {
      const value = group.values[method.key];
      const bx = gx - 84 + methodIndex * 60;
      const bh = (value / maximum) * height;
      const by = y + height - bh;
      out += roundRect(bx, by, barWidth, bh, method.color, 10);
      // Close frozen values are vertically staggered so six-decimal labels
      // remain readable without changing the shared zero-based axis.
      out += text(bx + barWidth / 2, Math.max(y + 20, by - barLabelY - methodIndex * 22), fmt(value), 16, { fill: C.cream, weight: 700, anchor: "middle" });
    });
    out += text(gx, y + height + 44, group.label, 25, { fill: C.cream, weight: 700, anchor: "middle" });
  });
  methods.forEach((method, index) => {
    const lx = x + index * 218;
    out += roundRect(lx, legendY, 18, 18, method.color, 5);
    out += text(lx + 28, legendY + 16, method.label, 19, { fill: C.muted, weight: 600 });
  });
  return out;
}

function pairedBars({ x, y, width, height, groups, maximum, yTicks, legendY }) {
  const methods = [
    { key: "soft_weight_k30", label: "soft k=30", color: C.soft },
    { key: "bounded_scene_constant_diffuse", label: "diffuse", color: C.diffuse },
  ];
  let out = "";
  for (const tick of yTicks) {
    const py = y + height - (tick / maximum) * height;
    out += line(x, py, x + width, py, tick === 0 ? C.cream : C.line, tick === 0 ? 2 : 1);
    out += text(x - 16, py + 7, tick.toFixed(2), 16, { fill: C.muted, anchor: "end" });
  }
  const groupWidth = width / groups.length;
  groups.forEach((group, groupIndex) => {
    const gx = x + groupIndex * groupWidth + groupWidth / 2;
    methods.forEach((method, methodIndex) => {
      const value = group.values[method.key];
      const bx = gx - 48 + methodIndex * 58;
      const bh = (value / maximum) * height;
      const by = y + height - bh;
      out += roundRect(bx, by, 42, bh, method.color, 9);
      out += text(bx + 21, Math.max(y + 18, by - 18), fmt(value), 14, { fill: C.cream, weight: 700, anchor: "middle" });
    });
    out += text(gx, y + height + 40, group.label, 21, { fill: C.cream, weight: 700, anchor: "middle" });
  });
  methods.forEach((method, index) => {
    const lx = x + 92 + index * 164;
    out += roundRect(lx, legendY, 16, 16, method.color, 4);
    out += text(lx + 24, legendY + 14, method.label, 16, { fill: C.muted, weight: 600 });
  });
  return out;
}

function source(relativePath, fields, values = {}) {
  return { source_file: relativePath, fields, values };
}

async function main() {
  const reportPath = `${PREFIX}/reports/stage6_5_3_b_experiment_report.md`;
  const resultPath = `${RUN}/result_summary.json`;
  const manifestPath = `${RUN}/experiment_manifest.json`;
  const riskPath = `${RUN}/risk_coverage.csv`;
  const partitionPath = `${RUN}/partition_metrics.csv`;
  const fitPath = `${RUN}/fit_parameters.csv`;
  const heteroPath = `${RUN}/heterogeneity_verdicts.csv`;
  const spatialPath = `${RUN}/residual_spatial_diagnostics.csv`;
  const cleanB4 = `${PREFIX}/data/stage6_5_single_scene_l8_l2sr_b4_red.tif`;
  const shadowB4 = `${PREFIX}/data/stage6_5_shadowrisk_single_scene_l8_l2sr_b4_red.tif`;
  const cleanPreview = `${PREFIX}/outputs/stage6_5_2_single_scene_local_check_preview.png`;
  const shadowPreview = `${PREFIX}/outputs/stage6_5_2b_shadowrisk_local_check_preview.png`;
  const cleanMasks = `${PREFIX}/outputs/stage6_5_3_b/preflight_clean_a_canonical_masks.tif`;
  const shadowMasks = `${PREFIX}/outputs/stage6_5_3_b/preflight_shadow_risk_b_canonical_masks.tif`;
  [reportPath, resultPath, manifestPath, riskPath, partitionPath, fitPath, heteroPath, spatialPath, cleanB4, shadowB4, cleanPreview, shadowPreview, cleanMasks, shadowMasks].forEach(exists);

  const results = readJson(resultPath);
  const manifest = readJson(manifestPath);
  const risk = readCsv(riskPath);
  const partitions = readCsv(partitionPath);
  const fits = readCsv(fitPath);
  const heterogeneity = readCsv(heteroPath);
  const spatial = readCsv(spatialPath);
  if (results.run_id !== "c5_d3_35789933202effad" || manifest.run_id !== results.run_id) fail("C5-D3 run identity mismatch.");
  if (results.overall_verdict !== "WARNING") fail("Unexpected C5-D3 verdict.");

  const value = (band, method) => {
    const row = results.method_summary.find((item) => item.scene === "shadow_risk_b" && item.band === band && item.method === method);
    if (!row) fail(`Missing summary: ${band}/${method}`);
    return row;
  };
  const full = {
    B4: {
      hard_mask: value("B4", "hard_mask").median_fold_mae,
      soft_weight_k30: value("B4", "soft_weight_k30").median_fold_mae,
      bounded_scene_constant_diffuse: value("B4", "bounded_scene_constant_diffuse").median_fold_mae,
    },
    B5: {
      hard_mask: value("B5", "hard_mask").median_fold_mae,
      soft_weight_k30: value("B5", "soft_weight_k30").median_fold_mae,
      bounded_scene_constant_diffuse: value("B5", "bounded_scene_constant_diffuse").median_fold_mae,
    },
  };
  approx(full.B4.hard_mask, 0.076787, "full B4 hard");
  approx(full.B4.soft_weight_k30, 0.064709, "full B4 soft");
  approx(full.B4.bounded_scene_constant_diffuse, 0.064677, "full B4 diffuse");
  approx(full.B5.hard_mask, 0.067527, "full B5 hard");
  approx(full.B5.soft_weight_k30, 0.065417, "full B5 soft");
  approx(full.B5.bounded_scene_constant_diffuse, 0.062218, "full B5 diffuse");

  const commonValue = (band, method) => {
    const rows = risk.filter((row) =>
      row.scene === "shadow_risk_b" &&
      row.band === band &&
      row.method === method &&
      Number(row.target_coverage) === 0.8 &&
      row.comparison_scope === "common_reachable",
    );
    if (rows.length !== 5) fail(`Expected five common-coverage folds for ${band}/${method}`);
    return median(rows.map((row) => row.mae));
  };
  const common = {
    B4: {
      hard_mask: commonValue("B4", "hard_mask"),
      soft_weight_k30: commonValue("B4", "soft_weight_k30"),
      bounded_scene_constant_diffuse: commonValue("B4", "bounded_scene_constant_diffuse"),
    },
    B5: {
      hard_mask: commonValue("B5", "hard_mask"),
      soft_weight_k30: commonValue("B5", "soft_weight_k30"),
      bounded_scene_constant_diffuse: commonValue("B5", "bounded_scene_constant_diffuse"),
    },
  };
  approx(common.B4.hard_mask, 0.076961, "common B4 hard");
  approx(common.B4.soft_weight_k30, 0.077554, "common B4 soft");
  approx(common.B4.bounded_scene_constant_diffuse, 0.077514, "common B4 diffuse");
  approx(common.B5.hard_mask, 0.070315, "common B5 hard");
  approx(common.B5.soft_weight_k30, 0.071416, "common B5 soft");
  approx(common.B5.bounded_scene_constant_diffuse, 0.069041, "common B5 diffuse");

  const partitionValue = (partition, method) => {
    const rows = partitions.filter((row) =>
      row.scene === "shadow_risk_b" &&
      row.band === "B5" &&
      row.partition === partition &&
      row.method === method,
    );
    if (rows.length !== 5) fail(`Expected five partition folds for ${partition}/${method}`);
    return median(rows.map((row) => row.mae));
  };
  const local = {
    shadow: {
      soft_weight_k30: partitionValue("shadow", "soft_weight_k30"),
      bounded_scene_constant_diffuse: partitionValue("shadow", "bounded_scene_constant_diffuse"),
    },
    near_zero: {
      soft_weight_k30: partitionValue("near_zero", "soft_weight_k30"),
      bounded_scene_constant_diffuse: partitionValue("near_zero", "bounded_scene_constant_diffuse"),
    },
  };
  approx(local.shadow.soft_weight_k30, 0.049992, "shadow B5 soft");
  approx(local.shadow.bounded_scene_constant_diffuse, 0.023666, "shadow B5 diffuse");
  approx(local.near_zero.soft_weight_k30, 0.038113, "near-zero B5 soft");
  approx(local.near_zero.bounded_scene_constant_diffuse, 0.024586, "near-zero B5 diffuse");

  const diffuseFits = fits.filter((row) => row.method === "bounded_scene_constant_diffuse");
  const boundaryHits = diffuseFits.filter((row) => row.boundary_hit === "True").length;
  const sensitive = heterogeneity.filter((row) => row.surface_heterogeneity_sensitive === "True").length;
  const inconclusive = spatial.filter((row) => row.status.startsWith("inconclusive")).length;
  if (diffuseFits.length !== 20 || boundaryHits !== 17 || heterogeneity.length !== 40 || sensitive !== 20 || spatial.length !== 60 || inconclusive !== 60) {
    fail("C5-D3 diagnostic totals are not the frozen values expected by this post.");
  }

  const overlayAll = [
    { band: 4, color: C.yellow, opacity: 0.22 },
    { band: 3, color: C.purple, opacity: 0.58 },
    { band: 2, color: C.orange, opacity: 0.62 },
  ];
  const shadowBackground = await actualScene(shadowB4, shadowMasks, 960, 500, overlayAll);
  const cleanPanel = await actualB4Preview(cleanPreview, 420, 430);
  const shadowPanel = await actualB4Preview(shadowPreview, 420, 430);
  const cleanMaskInset = await canonicalMaskMap(cleanMasks, 124, 124);
  const shadowMaskInset = await canonicalMaskMap(shadowMasks, 124, 124);

  // 01 cover: real Shadow-risk B B4 scene with canonical-mask overlays.
  await renderPng(
    "01_cover.png",
    `${mountainMotif(1172)}${outerBorder()}${quoteMark(64, 122)}
      ${text(60, 264, "一换评测口径，", 82, { fill: C.ink, weight: 800 })}
      ${marker(54, 296, 720, 92)}
      ${text(60, 370, "‘赢家’消失了", 88, { fill: C.orange, weight: 800 })}
      ${text(60, 458, "两景真实 Landsat × 三种山地光照处理", 30, { fill: C.ink, weight: 600 })}
      ${handUnderline(662, 478, 250)}
      ${roundRect(60, 548, 960, 500, "none", 26, `stroke="${C.line}" stroke-width="3"`)}
      ${badge(82, 570, "真实观测", C.yellow, C.ink)}
      ${roundRect(60, 1074, 960, 118, C.panel, 24, `stroke="${C.line}" stroke-width="2"`)}
      ${text(92, 1122, "Shadow-risk B · 实际 B4 观测", 24, { fill: C.ink, weight: 700 })}
      ${text(92, 1160, "叠加 canonical lit / near-zero / shadow masks", 20, { fill: C.muted, weight: 500 })}
      ${footer()}`,
    [{ input: shadowBackground, left: 60, top: 548 }],
  );

  // 02 two actual acquisitions.
  await renderPng(
    "02_two_acquisitions.png",
    `${pageHeader("", "不是 10 个独立场景", "只有 2 景真实观测；10 个 fold 是空间挑战")}
      ${roundRect(60, 248, 468, 606, "none", 28, `stroke="${C.line}" stroke-width="3"`)}
      ${roundRect(552, 248, 468, 606, "none", 28, `stroke="${C.line}" stroke-width="3"`)}
      ${text(84, 292, "Clean A", 31, { fill: C.cream, weight: 700 })}
      ${text(576, 292, "Shadow-risk B", 31, { fill: C.cream, weight: 700 })}
      ${text(84, 328, "几乎全为 lit", 22, { fill: C.muted, weight: 700 })}
      ${text(576, 328, "包含真实 shadow + near-zero 风险区", 22, { fill: C.orange, weight: 700 })}
      ${roundRect(84, 350, 420, 430, "none", 16, `stroke="${C.line}" stroke-width="3"`)}
      ${roundRect(576, 350, 420, 430, "none", 16, `stroke="${C.line}" stroke-width="3"`)}
      ${roundRect(360, 624, 128, 128, "none", 10, `stroke="#FFFFFF" stroke-width="4"`)}${roundRect(852, 624, 128, 128, "none", 10, `stroke="#FFFFFF" stroke-width="4"`)}
      ${text(84, 818, "actual B4 observation + canonical mask inset", 17, { fill: C.muted, weight: 500 })}
      ${text(576, 818, "actual B4 observation + canonical mask inset", 17, { fill: C.muted, weight: 500 })}
      ${roundRect(60, 902, 960, 260, C.panel2, 26)}
      ${text(96, 968, "图例：", 22, { fill: C.cream, weight: 700 })}
      ${roundRect(184, 946, 20, 20, C.yellow, 5)}${text(214, 964, "lit", 22, { fill: C.cream, weight: 600 })}
      ${roundRect(320, 946, 20, 20, C.purple, 5)}${text(350, 964, "near-zero", 22, { fill: C.cream, weight: 600 })}
      ${roundRect(518, 946, 20, 20, C.orange, 5)}${text(548, 964, "shadow", 22, { fill: C.cream, weight: 600 })}
      ${multiline(96, 1044, ["这是两个已核验 acquisition，不是十次独立实验。", "空间 fold 即使保持间隔，仍不能自动视为独立统计重复。"], 23, 46, { fill: C.ink, weight: 600 })}
      ${handUnderline(454, 1060, 232)}
      ${footer()}`,
    [
      { input: cleanPanel, left: 84, top: 350 },
      { input: shadowPanel, left: 576, top: 350 },
      { input: cleanMaskInset, left: 362, top: 626 },
      { input: shadowMaskInset, left: 854, top: 626 },
    ],
  );

  // 03 schematic mechanism card.
  const methodCards = [
    {
      n: "01",
      title: "hard mask",
      body: ["支持区外明确拒答", "cos_i ≤ 0.1 → unsupported"],
      color: C.hard,
    },
    {
      n: "02",
      title: "soft weight",
      body: ["仍然回答", "但降低弱光区域对拟合的影响"],
      color: C.soft,
    },
    {
      n: "03",
      title: "bounded diffuse",
      body: ["全场景共享一个受限常数补偿", "允许回答更多弱光像元"],
      color: C.diffuse,
    },
  ];
  let mechanism = `${pageBase("", "它们回答问题的方式不同", "SCHEMATIC · 机制示意，不是新增拟合结果")}
    ${badge(734, 70, "SCHEMATIC", C.orangeSoft, C.ink)}`;
  methodCards.forEach((card, index) => {
    const y = 270 + index * 250;
    mechanism += `${roundRect(60, y, 960, 208, C.panel, 28)}
      ${roundRect(92, y + 36, 82, 82, card.color, 22)}
      ${text(133, y + 90, card.n, 30, { fill: "#FFFFFF", weight: 700, anchor: "middle" })}
      ${text(208, y + 72, card.title, 34, { fill: C.cream, weight: 700 })}
      ${multiline(208, y + 116, card.body, 23, 38, { fill: C.muted, weight: 500 })}`;
  });
  mechanism += `${roundRect(60, 1056, 960, 122, "#FFF0E7", 24, `stroke="${C.orange}" stroke-width="2"`)}
    ${text(94, 1110, "bounded diffuse ≠ 真实天空散射模型", 30, { fill: C.ink, weight: 700 })}
    ${handUnderline(333, 1120, 365)}
    ${text(94, 1150, "它只是合同范围内的受限常数探针，不是真实辐射传输模型。", 20, { fill: C.orange, weight: 600 })}
    ${footer()}`;
  await renderPng("03_mechanisms.png", mechanism);

  // 04 maximum-coverage and common-coverage comparison on one fixed-axis card.
  const coverage = { hard_mask: 0.8722982351774737, soft_weight_k30: 1, bounded_scene_constant_diffuse: 1 };
  const rawChart = groupedBars({
    x: 118, y: 420, width: 852, height: 160, maximum: 0.09, yTicks: [0, 0.03, 0.06, 0.09],
    legendY: 360, barLabelY: 10,
    groups: [{ label: "B4", values: full.B4 }, { label: "B5", values: full.B5 }],
  });
  const commonChart = groupedBars({
    x: 118, y: 882, width: 852, height: 160, maximum: 0.09, yTicks: [0, 0.03, 0.06, 0.09],
    legendY: 822, barLabelY: 10,
    groups: [{ label: "B4", values: common.B4 }, { label: "B5", values: common.B5 }],
  });
  await renderPng(
    "04_coverage_comparison.png",
    `${pageBase("", "同一批结果，换个比较条件会怎样？")}
      ${roundRect(60, 228, 960, 410, C.panel, 28)}
      ${text(92, 275, "各自在最大 coverage 上比较", 27, { fill: C.ink, weight: 700 })}
      ${roundRect(92, 302, 18, 18, C.hard, 5)}${text(120, 318, `hard ${fmt(coverage.hard_mask, 3)}`, 19, { fill: C.ink, weight: 600 })}
      ${roundRect(300, 302, 18, 18, C.soft, 5)}${text(328, 318, "soft 1.000", 19, { fill: C.ink, weight: 600 })}
      ${roundRect(512, 302, 18, 18, C.diffuse, 5)}${text(540, 318, "diffuse 1.000", 19, { fill: C.ink, weight: 600 })}
      ${text(714, 318, "它们回答的像元范围不同。", 18, { fill: C.orange, weight: 700 })}
      ${rawChart}
      ${marker(145, 665, 790, 70, C.yellow, 0.90)}
      ${text(540, 712, "统一到相同 80% coverage", 30, { fill: C.ink, weight: 800, anchor: "middle" })}
      ${roundRect(60, 754, 960, 378, C.panel, 28)}
      ${text(92, 801, "在相同回答范围内重新比较", 27, { fill: C.ink, weight: 700 })}
      ${commonChart}
      ${text(540, 1110, "没有跨波段稳定赢家。", 26, { fill: C.orange, weight: 800, anchor: "middle" })}
      ${marker(180, 1150, 720, 80, C.yellow, 0.78)}
      ${multiline(540, 1182, ["误差不和 coverage 绑定，", "就不是同一场比赛。"], 27, 36, { fill: C.ink, weight: 800, anchor: "middle" })}
      ${footer()}`,
  );

  // 05 local improvement alongside frozen diagnostic warnings.
  const localChart = pairedBars({
    x: 92, y: 420, width: 460, height: 230, maximum: 0.06, yTicks: [0, 0.03, 0.06],
    legendY: 350,
    groups: [
      { label: "shadow", values: local.shadow },
      { label: "near-zero", values: local.near_zero },
    ],
  });
  await renderPng(
    "05_mechanism_warning.png",
    `${rect(0, 0, W, H, C.deep)}${mountainMotif(1172)}${outerBorder()}${quoteMark(1010, 106, "end")}
      ${text(60, 126, "局部改善是真的", 52, { fill: C.ink, weight: 800 })}
      ${marker(54, 146, 540, 65)}
      ${text(60, 202, "机制解释还没成立", 52, { fill: C.orange, weight: 800 })}
      ${roundRect(60, 272, 522, 586, C.panel, 28)}
      ${text(92, 320, "Shadow-risk B · B5 MAE", 24, { fill: C.cream, weight: 700 })}
      ${localChart}
      ${roundRect(86, 718, 470, 116, C.panel2, 20)}
      ${text(106, 754, "hard mask：该区域明确拒答", 21, { fill: C.ink, weight: 800 })}
      ${multiline(106, 786, ["非零误差，也非失败值，", "因此不参与此处 MAE 柱状比较。"], 18, 25, { fill: C.muted, weight: 600 })}
      ${roundRect(608, 272, 412, 586, "#FFF0E7", 28, `stroke="${C.orange}" stroke-width="2"`)}
      ${roundRect(634, 302, 360, 154, C.panel, 22)}
      ${text(660, 355, "17 / 20", 46, { fill: C.orange, weight: 800 })}${text(660, 400, "diffuse 参数触及边界", 20, { fill: C.ink, weight: 700 })}
      ${roundRect(634, 478, 360, 154, C.panel, 22)}
      ${text(660, 531, "20 / 40", 46, { fill: C.orange, weight: 800 })}${text(660, 576, "结果对表面异质性敏感", 20, { fill: C.ink, weight: 700 })}
      ${roundRect(634, 654, 360, 174, C.panel, 22)}
      ${text(660, 707, "60 / 60", 46, { fill: C.orange, weight: 800 })}${text(660, 752, "残差空间诊断", 20, { fill: C.ink, weight: 700 })}${text(660, 784, "仍不能定案", 20, { fill: C.ink, weight: 700 })}
      ${roundRect(60, 900, 960, 204, C.panel2, 26)}
      ${multiline(92, 962, ["这是实际观测到的局部改善，", "但不足以反推‘真实漫射机制成立’。"], 30, 48, { fill: C.ink, weight: 800 })}
      ${handUnderline(432, 1024, 430)}
      ${marker(120, 1134, 840, 62, C.yellow, 0.72)}
      ${text(540, 1175, "局部误差改善 ≠ 稳定方法赢家 ≠ 物理机制成立", 23, { fill: C.ink, weight: 800, anchor: "middle" })}
      ${footer()}`,
  );

  // 06 conclusion.
  await renderPng(
    "06_conclusion.png",
    `${rect(0, 0, W, H, C.deep)}${mountainMotif(1172)}${outerBorder()}${quoteMark(64, 128)}
      ${text(60, 210, "算得更多，", 78, { fill: C.ink, weight: 800 })}
      ${marker(54, 238, 690, 88)}
      ${text(60, 312, "不等于更可信。", 78, { fill: C.orange, weight: 800 })}
      ${roundRect(60, 392, 960, 466, C.panel, 30)}
      ${text(96, 448, "四条结论", 27, { fill: C.orange, weight: 700 })}
      ${text(96, 522, "01", 23, { fill: C.orange, weight: 700 })}${text(160, 522, "error 必须和 coverage 绑定", 29, { fill: C.cream, weight: 700 })}
      ${text(96, 610, "02", 23, { fill: C.orange, weight: 700 })}${text(160, 610, "unsupported 是有边界的拒答，不是缺失成绩", 27, { fill: C.cream, weight: 700 })}
      ${text(96, 698, "03", 23, { fill: C.orange, weight: 700 })}${text(160, 698, "局部改善 ≠ 机制成立", 29, { fill: C.cream, weight: 700 })}
      ${roundRect(84, 742, 900, 84, C.panel2, 20)}
      ${text(104, 795, "04", 23, { fill: C.orange, weight: 800 })}${text(168, 795, "测试景不能参与重新校准", 30, { fill: C.ink, weight: 800 })}
      ${roundRect(60, 890, 960, 206, C.panel2, 28)}
      ${text(96, 940, "下一步", 23, { fill: C.orange, weight: 700 })}
      ${text(96, 988, "冻结 direct-only 基线，增加独立 acquisition；", 25, { fill: C.ink, weight: 700 })}
      ${text(96, 1032, "检验禁止测试景重新拟合后，三种方法还剩多少解释力。", 24, { fill: C.ink, weight: 700 })}
      ${handUnderline(96, 1002, 110, C.orange, 5)}${handUnderline(390, 1002, 190, C.orange, 5)}${handUnderline(174, 1046, 254, C.orange, 5)}
      ${marker(105, 1132, 870, 96, C.yellow, 0.76)}
      ${multiline(540, 1172, ["你更信任明确拒答，", "还是有边界地回答？"], 25, 36, { fill: C.ink, weight: 800, anchor: "middle" })}
      ${footer()}`,
  );

  // Contact sheet is an overview only; source cards remain their original 1080×1350 PNGs.
  const cardFiles = ["01_cover.png", "02_two_acquisitions.png", "03_mechanisms.png", "04_coverage_comparison.png", "05_mechanism_warning.png", "06_conclusion.png"];
  const cellW = 500;
  const cellH = 625;
  const sheetW = 1560;
  const sheetH = 1410;
  const sheetLayers = [];
  for (let i = 0; i < cardFiles.length; i += 1) {
    const column = i % 3;
    const row = Math.floor(i / 3);
    const image = await sharp(path.join(OUT, cardFiles[i])).resize(cellW, cellH).png().toBuffer();
    sheetLayers.push({ input: image, left: 20 + column * 520, top: 120 + row * 645 });
  }
  const sheetSvg = Buffer.from(`<svg width="${sheetW}" height="${sheetH}" xmlns="http://www.w3.org/2000/svg">
    <rect width="100%" height="100%" fill="${C.deep}"/>
    <text x="30" y="72" font-family="'PingFang SC','STHeiti','Arial Unicode MS',sans-serif" font-size="38" font-weight="700" fill="${C.cream}">MountainRS · 小红书图卡总览</text>
  </svg>`);
  await sharp({ create: { width: sheetW, height: sheetH, channels: 3, background: C.deep } })
    .composite([{ input: sheetSvg }, ...sheetLayers])
    .png({ compressionLevel: 9 })
    .toFile(path.join(OUT, "contact_sheet.png"));

  const figureSources = {
    schema: "mountainrs-xiaohongshu-post-03-figure-sources-v1",
    run_id: results.run_id,
    protocol_version: manifest.protocol_version,
    rendering: {
      renderer: "render_post_03.js",
      dimensions: "1080x1350",
      numeric_policy: "Values are read from frozen C5-D3 scalar evidence; no fitting, scoring, or result mutation occurs.",
      distinction: "Cards 01–02 use actual observation rasters plus canonical mask overlays. Card 03 is explicitly schematic. Cards 04–06 are descriptive communication graphics based on frozen scalar results.",
      visual_system: "Warm paper, bold black Chinese headlines, yellow marker strokes, orange-red annotations, pale cards and layered mountain silhouettes, continuing Xiaohongshu posts 01–02.",
    },
    figures: [
      {
        file: "01_cover.png",
        claim: "The cover uses a real Shadow-risk B B4 observation with canonical mask overlay; it makes no numerical comparison.",
        sources: [
          source(shadowB4, ["Landsat L2 SR B4 raster; actual observation background"]),
          source(shadowMasks, ["canonical bands: base_valid, shadow, near_zero, lit"]),
          source(reportPath, ["scope: two scenes / 10 descriptive buffered spatial challenges"]),
        ],
      },
      {
        file: "02_two_acquisitions.png",
        claim: "Clean A and Shadow-risk B are two verified acquisitions, not independent statistical replications.",
        sources: [
          source(cleanB4, ["Landsat L2 SR B4 raster; actual observation panel"]),
          source(shadowB4, ["Landsat L2 SR B4 raster; actual observation panel"]),
          source(cleanPreview, ["existing formal stage-6.5 Clean A image; displayed B4 reflectance panel"]),
          source(shadowPreview, ["existing formal stage-6.5 Shadow-risk B image; displayed B4 reflectance panel"]),
          source(cleanMasks, ["canonical bands: base_valid, shadow, near_zero, lit"]),
          source(shadowMasks, ["canonical bands: base_valid, shadow, near_zero, lit"]),
          source(reportPath, ["scope and spatial-fold interpretation"]),
        ],
      },
      {
        file: "03_mechanisms.png",
        claim: "A schematic comparison of the frozen hard mask, soft weight and bounded scene-constant diffuse mechanisms.",
        sources: [
          source(reportPath, ["method interpretation and limits; bounded diffuse is not real diffuse irradiance"]),
          source(manifestPath, ["protocol_version"]),
        ],
      },
      {
        file: "04_coverage_comparison.png",
        claim: "Maximum-coverage and common-80%-coverage views of the same frozen results show why error must be bound to coverage.",
        sources: [
          source(resultPath, ["method_summary[].median_fold_mae", "method_summary[].median_maximum_coverage"], {
            B4: { hard: full.B4.hard_mask, soft_k30: full.B4.soft_weight_k30, diffuse: full.B4.bounded_scene_constant_diffuse },
            B5: { hard: full.B5.hard_mask, soft_k30: full.B5.soft_weight_k30, diffuse: full.B5.bounded_scene_constant_diffuse },
            maximum_coverage_median: { hard: coverage.hard_mask, soft_k30: 1, diffuse: 1 },
          }),
          source(riskPath, ["scene=shadow_risk_b", "target_coverage=0.80", "comparison_scope=common_reachable", "median(mae) across five folds"], {
            B4: { hard: common.B4.hard_mask, soft_k30: common.B4.soft_weight_k30, diffuse: common.B4.bounded_scene_constant_diffuse },
            B5: { hard: common.B5.hard_mask, soft_k30: common.B5.soft_weight_k30, diffuse: common.B5.bounded_scene_constant_diffuse },
          }),
        ],
      },
      {
        file: "05_mechanism_warning.png",
        claim: "The local B5 improvement is real, but frozen diagnostics do not support a diffuse-mechanism claim.",
        sources: [
          source(partitionPath, ["scene=shadow_risk_b", "band=B5", "partition=shadow|near_zero", "median(mae) across five folds"], local),
          source(fitPath, ["method=bounded_scene_constant_diffuse", "boundary_hit=True count"], { boundary_hits: boundaryHits, total_diffuse_fits: diffuseFits.length }),
          source(heteroPath, ["surface_heterogeneity_sensitive=True count"], { sensitive, total: heterogeneity.length }),
          source(spatialPath, ["status starts with inconclusive"], { inconclusive, total: spatial.length }),
        ],
      },
      {
        file: "06_conclusion.png",
        claim: "A communication summary of the frozen C5-D3 warning boundary; it does not report a new model result.",
        sources: [
          source(reportPath, ["overall verdict, scope, interpretation limits"]),
          source(resultPath, ["overall_verdict", "overall_reason"]),
          source(manifestPath, ["run_id", "protocol_version"]),
        ],
      },
    ],
  };
  fs.writeFileSync(path.join(META_OUT, "figure_sources.json"), `${JSON.stringify(figureSources, null, 2)}\n`, "utf8");
  const readme = [
    "# MountainRS 小红书科研图卡",
    "",
    "本目录只包含基于已冻结 C5-D3 结果生成的传播图。它不执行模型、不重新拟合、不修改实验报告、scalar results、evidence 或任何 PF2 状态。",
    "",
    "## 文件",
    "",
    "- \`01_cover.png\` 至 \`06_conclusion.png\`：6 张 1080 × 1350（4:5）PNG 图卡。",
    "- \`contact_sheet.png\`：6 张图的缩略图总览。",
    "- \`figure_sources.json\`：每张图使用的相对 source file、字段与数值。",
    "- \`render_post_03.js\`：确定性渲染脚本。",
    "",
    "## 视觉约定",
    "",
    "- 延续前两篇：暖米白 \`#FFF9E8\` 纸张、墨黑 \`#111210\` 标题、黄色 \`#F7D34E\` 荧光笔、橙红 \`#E54817\` 批注与浅黄色山形。",
    "- 图表仍使用克制的灰、橙、橙红方法色；黄笔刷只承担叙事强调，不编码实验数值。",
    "- 图 01–02 的底图明确为 **actual observation**：已存在的 Landsat L2 SR B4 GeoTIFF，叠加 C5-D3 canonical masks。",
    "- 图 03 标为 **SCHEMATIC**；图 04–06 是冻结 scalar results 的描述性传播图，不是新实验。",
    "- 中文使用 Arial Unicode / STHeiti 的可嵌入 Unicode 字体族进行光栅化；最终 PNG 不依赖阅读设备字体。",
    "- 所有图统一页脚：\`2 acquisitions / 10 spatial challenges；空间折不是独立统计重复\`。",
    "",
    "## 复现",
    "",
    "在具备 Node.js 18+ 与 \`sharp\` 0.34+ 的环境中、从本目录运行：",
    "",
    "\`\`\`sh",
    "NODE_PATH=<sharp 所在 node_modules> node render_post_03.js",
    "\`\`\`",
    "",
    "脚本会先校验 run ID、WARNING verdict、六个 80% coverage 中位数、四个局部 B5 MAE 与三类诊断总数，再写出 PNG、contact sheet 与 source 清单。它只读取相对路径下的正式 C5-D3 文件，不会写入实验目录、evidence 或 PF2。",
    "",
  ].join("\n");
  fs.writeFileSync(path.join(META_OUT, "README.md"), readme, "utf8");
  console.log(JSON.stringify({
    status: "succeeded",
    figures: cardFiles,
    contact_sheet: "contact_sheet.png",
    source_manifest: "figure_sources.json",
    run_id: results.run_id,
  }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
