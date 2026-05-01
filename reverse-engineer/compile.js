#!/usr/bin/env node
// compile.js — reverse-engineer block compiler.
//
// Inputs:
//   <spec.yaml>          YAML describing project + block instantiations + nets
//   --bom <bom.csv>      Optional CSV BOM, used for cross-check (warn-only)
//   -o <output_dir>      Output directory for the KiCad project
//
// Outputs (in <output_dir>):
//   <project>.kicad_pro
//   <project>.kicad_sch
//   <project>.kicad_sym       (block symbol library)
//   sym-lib-table              (so KiCad finds the lib)
//   README.md                  (auto-generated build notes)
//
// Usage:
//   node compile.js examples/weather_station.yaml -o output/weather_station
//
// Spec file format (YAML):
//   project: WeatherStation
//   rev: A
//   blocks:
//     u_pwr:    { type: usb_c_input_5v }
//     u_reg:    { type: buck_3v3, opts: { regType: ldo } }
//     u_mcu:    { type: mcu_esp32_wroom }
//     u_oled:   { type: i2c_oled_ssd1306, opts: { addr: 0x3C } }
//     u_bme:    { type: bme280_i2c }
//   nets:
//     - { net: 5V,  conns: [u_pwr.5V, u_reg.VIN] }
//     - { net: 3V3, conns: [u_reg.3V3, u_mcu.VCC, u_oled.VCC, u_bme.VCC] }
//     - { net: GND, conns: [u_pwr.GND, u_reg.GND_IN, u_reg.GND, u_mcu.GND, u_oled.GND, u_bme.GND] }
//     - { net: I2C_SDA, conns: [u_mcu.SDA, u_oled.SDA, u_bme.SDA] }
//     - { net: I2C_SCL, conns: [u_mcu.SCL, u_oled.SCL, u_bme.SCL] }

const fs = require("fs");
const path = require("path");
const yaml = require("js-yaml");
const E = require("./lib/kicad_emit");
const blocks = require("./blocks");

function parseArgs(argv) {
  const out = { spec: null, bom: null, outDir: null, verbose: false };
  const args = argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "-o" || a === "--out") out.outDir = args[++i];
    else if (a === "--bom") out.bom = args[++i];
    else if (a === "-v" || a === "--verbose") out.verbose = true;
    else if (a === "-h" || a === "--help") {
      console.log("usage: node compile.js <spec.yaml> [--bom <bom.csv>] -o <out_dir> [-v]");
      process.exit(0);
    } else if (!out.spec) out.spec = a;
    else throw new Error(`Unexpected arg: ${a}`);
  }
  if (!out.spec) throw new Error("Missing <spec.yaml> argument");
  if (!out.outDir) throw new Error("Missing -o <out_dir> argument");
  return out;
}

function loadBom(file) {
  if (!file) return null;
  const raw = fs.readFileSync(file, "utf8");
  // Naive CSV parse; assumes no embedded commas. Sufficient for cross-check.
  const lines = raw.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) return [];
  const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
  return lines.slice(1).map((line) => {
    const cells = line.split(",").map((c) => c.trim());
    const row = {};
    header.forEach((h, i) => (row[h] = cells[i] || ""));
    return row;
  });
}

function resolveBlock(blockSpec, blockName) {
  const def = blocks[blockSpec.type];
  if (!def) {
    throw new Error(`Unknown block type "${blockSpec.type}" (in ${blockName}). Available: ${Object.keys(blocks).join(", ")}`);
  }
  const opts = blockSpec.opts || {};
  const sym = E.normalizePins(def.symbol(opts));
  // Compose human ref letters: u_pwr → U_PWR, but we want a unique short ref.
  return { name: blockName, def, opts, sym };
}

function autoLayout(instances) {
  // Place blocks on a coarse grid: 4 columns, ~80mm wide, ~80mm tall.
  // Power blocks (usb / regulator / bms) on the left column; everything else
  // flows left→right, top→bottom.
  const G = E.G;
  const colX = [G * 60, G * 130, G * 210, G * 290, G * 370];
  const rowY = [G * 60, G * 130, G * 200, G * 270, G * 340];

  const powerIds = new Set(["usb_c_input_5v", "buck_3v3", "linear_regulator_3v3", "bms_4s_protection", "decap_caps"]);
  const mcuIds = new Set(["mcu_esp32_wroom", "pi_zero_2w_header"]);

  const power = instances.filter((i) => powerIds.has(i.def.id));
  const mcu = instances.filter((i) => mcuIds.has(i.def.id));
  const peripherals = instances.filter((i) => !powerIds.has(i.def.id) && !mcuIds.has(i.def.id));

  const positions = {};
  power.forEach((b, i) => {
    positions[b.name] = { x: colX[0], y: rowY[i % rowY.length] };
  });
  mcu.forEach((b, i) => {
    positions[b.name] = { x: colX[2], y: rowY[Math.floor(i / 1) % rowY.length] };
  });
  peripherals.forEach((b, i) => {
    const col = 3 + Math.floor(i / rowY.length);
    const x = colX[Math.min(col, colX.length - 1)];
    const y = rowY[i % rowY.length];
    positions[b.name] = { x, y };
  });
  return positions;
}

function refForBlock(name, def, refCounters) {
  const prefix = def.symbol(def.defaults).refPrefix || "U";
  refCounters[prefix] = (refCounters[prefix] || 0) + 1;
  return `${prefix}${refCounters[prefix]}`;
}

// Returns the "side" (left|right) for a given external pin on a block instance.
function sideOfPin(spec, pinName) {
  if (spec.leftPins.find((p) => p.name === pinName)) return "left";
  if (spec.rightPins.find((p) => p.name === pinName)) return "right";
  return null;
}

// Resolve "u_mcu.SDA" → block instance + concrete pin name on the symbol.
function resolveConn(connStr, instances) {
  const [blockName, ifaceName] = connStr.split(".");
  const inst = instances.find((i) => i.name === blockName);
  if (!inst) throw new Error(`Connection refers to unknown block "${blockName}"`);
  const concretePin = (inst.def.interface || {})[ifaceName] || ifaceName;
  const side = sideOfPin(inst.sym, concretePin);
  if (!side) {
    throw new Error(`Pin "${ifaceName}" (resolved to "${concretePin}") not found on block ${blockName} (type ${inst.def.id})`);
  }
  return { inst, pinName: concretePin, side };
}

function bomCrossCheck(bom, instances, verbose) {
  if (!bom) return [];
  const warnings = [];
  // Try to match block values against BOM rows by Description / Part / Value.
  const haystack = bom.map((row) => Object.values(row).join(" ").toLowerCase());
  const tokens = (s) => s.toLowerCase().split(/[^a-z0-9]+/).filter((t) => t.length >= 3);
  for (const inst of instances) {
    const value = inst.sym.value || inst.def.id;
    const want = tokens(value);
    let matched = false;
    for (const hay of haystack) {
      if (want.some((t) => hay.includes(t))) { matched = true; break; }
    }
    if (!matched) {
      warnings.push(`BOM cross-check: no row matched block "${inst.name}" value "${value}"`);
    } else if (verbose) {
      console.log(`  ✓ BOM matched ${inst.name} ("${value}")`);
    }
  }
  return warnings;
}

function compile({ spec, bom, outDir, verbose }) {
  const specPath = path.resolve(spec);
  const yamlText = fs.readFileSync(specPath, "utf8");
  const cfg = yaml.load(yamlText);
  if (!cfg.project) throw new Error("Spec missing 'project' field");

  const projectName = cfg.project;
  const libName = `${projectName}_blocks`;
  const rootUuid = E.randomUUID();

  // Resolve all blocks.
  const instances = [];
  const refCounters = {};
  for (const [blockName, blockSpec] of Object.entries(cfg.blocks || {})) {
    const inst = resolveBlock(blockSpec, blockName);
    inst.ref = refForBlock(blockName, inst.def, refCounters);
    instances.push(inst);
  }

  if (verbose) console.log(`Resolved ${instances.length} block instances`);

  // Layout.
  const positions = autoLayout(instances);
  for (const inst of instances) {
    inst.pos = positions[inst.name];
  }

  // BOM cross-check.
  const bomData = bom ? loadBom(bom) : null;
  const warnings = bomCrossCheck(bomData, instances, verbose);

  // Build symbol library (one symbol per unique block-type-with-opts).
  // For simplicity we emit a unique symbol per instance — this is wasteful but
  // robust for blocks that vary by opts (e.g. SSD1306 with different addr).
  // We dedupe by symbol name.
  const seen = new Set();
  const uniqueSymbols = [];
  for (const inst of instances) {
    if (!seen.has(inst.sym.name)) {
      seen.add(inst.sym.name);
      uniqueSymbols.push(inst.sym);
    }
  }

  // Build schematic items.
  const schematicItems = [];
  schematicItems.push(E.textBlock(
    `${projectName} — auto-generated by reverse-engineer compile.js\nSpec: ${path.basename(specPath)}\nBlocks: ${instances.length}`,
    20, 25, 1.6
  ));

  // Place each instance.
  for (const inst of instances) {
    schematicItems.push(E.instance(
      inst.sym, inst.ref, inst.sym.value, inst.pos.x, inst.pos.y,
      libName, projectName, rootUuid
    ));
  }

  // Wire nets via labels. Every connection in `nets` becomes a (wire+label)
  // pair on its pin — KiCad treats matching label texts on different wires
  // as connected. This is the same pattern the user's CM5 generator uses.
  const usedPins = new Set();
  for (const netDef of cfg.nets || []) {
    const netName = netDef.net;
    if (!netName) throw new Error("Net entry missing 'net' field");
    for (const connStr of netDef.conns || []) {
      const { inst, pinName, side } = resolveConn(connStr, instances);
      const key = `${inst.name}.${pinName}`;
      if (usedPins.has(key)) {
        warnings.push(`Pin ${key} listed in multiple nets — last net wins`);
      }
      usedPins.add(key);
      schematicItems.push(...E.netLabelAt(inst.sym, side, pinName, inst.pos.x, inst.pos.y, netName));
    }
  }

  // Mark all unused interface-default pins as no_connect to satisfy ERC.
  for (const inst of instances) {
    for (const side of ["leftPins", "rightPins"]) {
      for (const p of inst.sym[side]) {
        const key = `${inst.name}.${p.name}`;
        if (!usedPins.has(key)) {
          schematicItems.push(E.noConnectAt(inst.sym, side === "leftPins" ? "left" : "right", p.name, inst.pos.x, inst.pos.y));
        }
      }
    }
  }

  // Emit files.
  fs.mkdirSync(outDir, { recursive: true });
  const symLib = E.buildSymLib(uniqueSymbols);
  const schematic = E.buildSchematic({
    rootUuid,
    libName,
    symbols: uniqueSymbols,
    schematicItems,
    projectName,
    title: cfg.title || projectName,
    rev: cfg.rev || "A",
    comments: cfg.comments || [`Generated from ${path.basename(specPath)}`],
  });
  const project = E.buildProject(projectName, rootUuid);
  const symTable = E.buildSymTable(libName);

  fs.writeFileSync(path.join(outDir, `${projectName}.kicad_pro`), `${JSON.stringify(project, null, 2)}\n`);
  fs.writeFileSync(path.join(outDir, `${projectName}.kicad_sch`), schematic);
  fs.writeFileSync(path.join(outDir, `${libName}.kicad_sym`), symLib);
  fs.writeFileSync(path.join(outDir, "sym-lib-table"), symTable);

  // README.
  const readme = renderReadme(projectName, cfg, instances, warnings);
  fs.writeFileSync(path.join(outDir, "README.md"), readme);

  return { projectName, instances, warnings, outDir };
}

function renderReadme(projectName, cfg, instances, warnings) {
  const lines = [
    `# ${projectName}`,
    "",
    `Auto-generated by \`reverse-engineer/compile.js\`. Open \`${projectName}.kicad_pro\` in KiCad 9.`,
    "",
    `Rev: ${cfg.rev || "A"}`,
    "",
    "## Blocks",
    "",
    "| Ref | Name | Type | Description |",
    "| --- | ---- | ---- | ----------- |",
    ...instances.map((i) => `| ${i.ref} | ${i.name} | \`${i.def.id}\` | ${i.sym.value} |`),
    "",
    "## Nets",
    "",
    ...((cfg.nets || []).map((n) => `- **${n.net}**: ${(n.conns || []).join(", ")}`)),
    "",
  ];
  if (warnings.length) {
    lines.push("## Warnings", "");
    warnings.forEach((w) => lines.push(`- ${w}`));
    lines.push("");
  }
  if (cfg.notes) {
    lines.push("## Notes", "", cfg.notes, "");
  }
  return lines.join("\n");
}

if (require.main === module) {
  try {
    const args = parseArgs(process.argv);
    const result = compile(args);
    console.log(`Compiled ${result.projectName} → ${result.outDir}`);
    console.log(`  ${result.instances.length} blocks, ${result.warnings.length} warnings`);
    if (result.warnings.length && args.verbose) {
      result.warnings.forEach((w) => console.log(`  ! ${w}`));
    }
  } catch (e) {
    console.error("Error:", e.message);
    if (process.env.DEBUG) console.error(e.stack);
    process.exit(1);
  }
}

module.exports = { compile, parseArgs };
