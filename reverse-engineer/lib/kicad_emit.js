// kicad_emit.js — shared S-expression emission primitives for KiCad 9 .kicad_sch
// and .kicad_sym output. Modeled on CM5_Portable/scripts/generate_project.js.
//
// Usage:
//   const E = require('./kicad_emit');
//   const sym = E.symbolDefinition({ name: 'My_Block', leftPins: [...], rightPins: [...] });
//
// All blocks return their geometry through these primitives.

const { randomUUID } = require("crypto");

const G = 1.27;            // grid unit in mm (KiCad schematic standard)
const PIN_LEN = 3.81;      // default pin length (3 grid)
const TEXT_SIZE = 1.27;    // default text size
const PIN_TEXT_SIZE = 0.9; // default pin text size

function q(value) {
  return `"${String(value)
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\n/g, "\\n")}"`;
}

function fmt(value) {
  return Number(value).toFixed(3).replace(/\.?0+$/, "");
}

function propertyBlock(name, value, x, y, rot = 0, hidden = false, size = TEXT_SIZE, indent = "\t\t") {
  const hide = hidden ? "\n\t\t\t\t(hide yes)" : "";
  return `${indent}(property ${q(name)} ${q(value)}\n${indent}\t(at ${fmt(x)} ${fmt(y)} ${fmt(rot)})\n${indent}\t(effects\n${indent}\t\t(font\n${indent}\t\t\t(size ${fmt(size)} ${fmt(size)})\n${indent}\t\t)${hide}\n${indent}\t)\n${indent})`;
}

function pinSExpr(name, number, side, y, width, pinLen = PIN_LEN, size = PIN_TEXT_SIZE, electricalType = "passive") {
  const isLeft = side === "left";
  const x = isLeft ? -width / 2 - pinLen : width / 2 + pinLen;
  const angle = isLeft ? 0 : 180;
  return `\t\t\t(pin ${electricalType} line\n\t\t\t\t(at ${fmt(x)} ${fmt(y)} ${angle})\n\t\t\t\t(length ${fmt(pinLen)})\n\t\t\t\t(name ${q(name)}\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size ${fmt(size)} ${fmt(size)})\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t\t(number ${q(number)}\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size ${fmt(size)} ${fmt(size)})\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)`;
}

function normalizePins(spec) {
  let n = 1;
  for (const side of ["leftPins", "rightPins"]) {
    spec[side] = (spec[side] || []).map((entry) => {
      if (typeof entry === "string") {
        return { number: String(n++), name: entry };
      }
      const pin = { ...entry, number: String(entry.number ?? n) };
      n += 1;
      return pin;
    });
  }
  return spec;
}

function pinY(sidePins, idx, pitch) {
  return ((sidePins.length - 1) * pitch) / 2 - idx * pitch;
}

function symbolDefinition(spec, embeddedPrefix = "") {
  const name = embeddedPrefix ? `${embeddedPrefix}:${spec.name}` : spec.name;
  const width = spec.width ?? 35;
  const pitch = spec.pitch ?? 2.54;
  const maxPins = Math.max(spec.leftPins.length, spec.rightPins.length, 1);
  const height = spec.height ?? Math.max(15.24, (maxPins + 1) * pitch);
  const title = spec.bodyText ?? spec.value ?? spec.name;
  const refY = -height / 2 - 4;
  const valY = height / 2 + 4;
  const graphics = [];

  graphics.push(`\t\t\t(rectangle\n\t\t\t\t(start ${fmt(-width / 2)} ${fmt(height / 2)})\n\t\t\t\t(end ${fmt(width / 2)} ${fmt(-height / 2)})\n\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n\t\t\t\t\t(type default)\n\t\t\t\t)\n\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)`);
  graphics.push(`\t\t\t(text ${q(title)}\n\t\t\t\t(at 0 0 0)\n\t\t\t\t(effects\n\t\t\t\t\t(font\n\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)`);

  spec.leftPins.forEach((p, i) => graphics.push(pinSExpr(p.name, p.number, "left", pinY(spec.leftPins, i, pitch), width, spec.pinLen, spec.pinTextSize, p.electrical || "passive")));
  spec.rightPins.forEach((p, i) => graphics.push(pinSExpr(p.name, p.number, "right", pinY(spec.rightPins, i, pitch), width, spec.pinLen, spec.pinTextSize, p.electrical || "passive")));

  return `\t(symbol ${q(name)}\n\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t)\n\t\t(exclude_from_sim no)\n\t\t(in_bom ${spec.inBom === false ? "no" : "yes"})\n\t\t(on_board ${spec.onBoard === false ? "no" : "yes"})\n${propertyBlock("Reference", spec.refPrefix ?? "U", 0, refY, 0, false, 1.27, "\t\t")}\n${propertyBlock("Value", spec.value ?? spec.name, 0, valY, 0, false, 1.27, "\t\t")}\n${propertyBlock("Footprint", spec.footprint ?? "", 0, 0, 0, true, 1.27, "\t\t")}\n${propertyBlock("Datasheet", spec.datasheet ?? "~", 0, 0, 0, true, 1.27, "\t\t")}\n${propertyBlock("Description", spec.description ?? "", 0, 0, 0, true, 1.27, "\t\t")}\n\t\t(symbol ${q(`${spec.name}_1_1`)}\n${graphics.join("\n")}\n\t\t)\n\t\t(embedded_fonts no)\n\t)`;
}

// Build a placed symbol instance in the schematic.
function instance(spec, ref, value, x, y, libName, projectName, rootUuid, overrides = {}) {
  const width = spec.width ?? 35;
  const pitch = spec.pitch ?? 2.54;
  const maxPins = Math.max(spec.leftPins.length, spec.rightPins.length, 1);
  const height = spec.height ?? Math.max(15.24, (maxPins + 1) * pitch);
  const uuid = randomUUID();
  const footprint = overrides.footprint ?? spec.footprint ?? "";
  const datasheet = overrides.datasheet ?? spec.datasheet ?? "~";
  const description = overrides.description ?? spec.description ?? "";

  const allPinNumbers = [...spec.leftPins, ...spec.rightPins].map((p) => p.number);
  const pins = allPinNumbers
    .map((num) => `\t\t(pin ${q(num)}\n\t\t\t(uuid ${q(randomUUID())})\n\t\t)`)
    .join("\n");

  return `\t(symbol\n\t\t(lib_id ${q(`${libName}:${spec.name}`)})\n\t\t(at ${fmt(x)} ${fmt(y)} 0)\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom ${spec.inBom === false ? "no" : "yes"})\n\t\t(on_board ${spec.onBoard === false ? "no" : "yes"})\n\t\t(dnp no)\n\t\t(uuid ${q(uuid)})\n${propertyBlock("Reference", ref, x, y - height / 2 - 4, 0, false, 1.27, "\t\t")}\n${propertyBlock("Value", value, x, y + height / 2 + 4, 0, false, 1.27, "\t\t")}\n${propertyBlock("Footprint", footprint, x, y, 0, true, 1.27, "\t\t")}\n${propertyBlock("Datasheet", datasheet, x, y, 0, true, 1.27, "\t\t")}\n${propertyBlock("Description", description, x, y, 0, true, 1.27, "\t\t")}\n${pins}${pins ? "\n" : ""}\t\t(instances\n\t\t\t(project ${q(projectName)}\n\t\t\t\t(path ${q(`/${rootUuid}`)}\n\t\t\t\t\t(reference ${q(ref)})\n\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)`;
}

// Compute the absolute position of a pin on a placed instance.
function endpoint(spec, side, pinName, x, y) {
  const width = spec.width ?? 35;
  const pinLen = spec.pinLen ?? PIN_LEN;
  const pitch = spec.pitch ?? 2.54;
  const pins = side === "left" ? spec.leftPins : spec.rightPins;
  const idx = pins.findIndex((p) => p.name === pinName || p.number === String(pinName));
  if (idx < 0) {
    throw new Error(`Pin ${pinName} not found on ${spec.name} ${side}`);
  }
  const xLocal = side === "left" ? -width / 2 - pinLen : width / 2 + pinLen;
  return { x: x + xLocal, y: y - pinY(pins, idx, pitch) };
}

function wire(x1, y1, x2, y2) {
  return `\t(wire\n\t\t(pts\n\t\t\t(xy ${fmt(x1)} ${fmt(y1)}) (xy ${fmt(x2)} ${fmt(y2)})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type solid)\n\t\t)\n\t\t(uuid ${q(randomUUID())})\n\t)`;
}

function label(text, x, y, angle = 0, size = 1.0) {
  return `\t(label ${q(text)}\n\t\t(at ${fmt(x)} ${fmt(y)} ${fmt(angle)})\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size ${fmt(size)} ${fmt(size)})\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid ${q(randomUUID())})\n\t)`;
}

function textBlock(text, x, y, size = 1.27) {
  return `\t(text ${q(text)}\n\t\t(exclude_from_sim no)\n\t\t(at ${fmt(x)} ${fmt(y)} 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size ${fmt(size)} ${fmt(size)})\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid ${q(randomUUID())})\n\t)`;
}

function netLabelAt(spec, side, pinName, instX, instY, netName, labelOffset = G * 8) {
  const p = endpoint(spec, side, pinName, instX, instY);
  const lx = side === "left" ? p.x - labelOffset : p.x + labelOffset;
  const ly = p.y;
  return [wire(p.x, p.y, lx, ly), label(netName, lx, ly, 0, 0.9)];
}

function noConnectAt(spec, side, pinName, instX, instY) {
  const p = endpoint(spec, side, pinName, instX, instY);
  return `\t(no_connect\n\t\t(at ${fmt(p.x)} ${fmt(p.y)})\n\t\t(uuid ${q(randomUUID())})\n\t)`;
}

// Project / file emission helpers.

function buildSymLib(symbols) {
  return `(kicad_symbol_lib\n\t(version 20241209)\n\t(generator "reverse-engineer")\n\t(generator_version "1.0")\n${symbols.map((s) => symbolDefinition(s)).join("\n")}\n)\n`;
}

function buildSchematic({ rootUuid, libName, symbols, schematicItems, projectName, title = projectName, rev = "A", date = new Date().toISOString().slice(0, 10), comments = [] }) {
  const commentBlock = comments
    .map((c, i) => `\t\t(comment ${i + 1} ${q(c)})`)
    .join("\n");
  return `(kicad_sch\n\t(version 20250114)\n\t(generator "reverse-engineer")\n\t(generator_version "1.0")\n\t(uuid ${q(rootUuid)})\n\t(paper "A2")\n\t(title_block\n\t\t(title ${q(title)})\n\t\t(date ${q(date)})\n\t\t(rev ${q(rev)})\n\t\t(company "Generated by reverse-engineer compile.js")\n${commentBlock}\n\t)\n\t(lib_symbols\n${symbols.map((s) => symbolDefinition(s, libName)).join("\n")}\n\t)\n${schematicItems.join("\n")}\n\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n\t(embedded_fonts no)\n)\n`;
}

function buildProject(projectName, rootUuid) {
  return {
    board: {
      design_settings: {
        defaults: {},
        diff_pair_dimensions: [],
        drc_exclusions: [],
        rules: {},
        track_widths: [],
        via_dimensions: [],
      },
    },
    boards: [],
    libraries: { pinned_footprint_libs: [], pinned_symbol_libs: [] },
    meta: { filename: `${projectName}.kicad_pro`, version: 1 },
    net_settings: { classes: [], meta: { version: 0 } },
    pcbnew: { page_layout_descr_file: "" },
    sheets: [[rootUuid, "Root"]],
    text_variables: {},
  };
}

function buildSymTable(libName) {
  return `(sym_lib_table\n\t(lib (name "${libName}") (type "KiCad") (uri "\${KIPRJMOD}/${libName}.kicad_sym") (options "") (descr "Block library for reverse-engineer compiled project"))\n)\n`;
}

module.exports = {
  G,
  PIN_LEN,
  q,
  fmt,
  propertyBlock,
  normalizePins,
  pinY,
  symbolDefinition,
  instance,
  endpoint,
  wire,
  label,
  textBlock,
  netLabelAt,
  noConnectAt,
  buildSymLib,
  buildSchematic,
  buildProject,
  buildSymTable,
  randomUUID,
};
