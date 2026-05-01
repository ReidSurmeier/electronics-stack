// linear_regulator_3v3.js — discrete LDO topology (TO-220 or SOT-223 LDO with
// input/output caps). For 12V or higher input (where buck_3v3 buck would be
// preferred); kept as a separate block because it has 3 pins (no EN) and
// different cap recommendations.
//
// Options:
//   part: "LM1117-3.3" (default) | "AMS1117-3.3" | "LD1117V33".
//   inputV: "5V" (default) | "12V" — affects thermal advice.
//   inputCap: 10 (uF) — input cap.
//   outputCap: 22 (uF) — output cap.

module.exports = {
  id: "linear_regulator_3v3",
  description: "Discrete 3-pin LDO 3.3V regulator (LM1117-3.3 etc).",
  defaults: { part: "LM1117-3.3", inputV: "5V", inputCap: 10, outputCap: 22 },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "LDO_3V3_Discrete",
      refPrefix: "U",
      value: `${o.part} discrete LDO (in ${o.inputV})`,
      bodyText: `${o.part}\n${o.inputV} → 3V3\n+ caps`,
      width: 33.02,
      leftPins: ["VIN", "GND_IN"],
      rightPins: ["3V3_OUT", "GND_OUT"],
      datasheet: "https://www.ti.com/lit/ds/symlink/lm1117.pdf",
      description: `${o.part} 3-pin LDO regulator, ${o.inputV} input → 3.3V output. ${o.inputCap}uF input cap, ${o.outputCap}uF output cap (low-ESR ceramic for AMS1117; tantalum or ceramic for LM1117/LD1117). ${o.inputV === "12V" ? "Significant power dissipation at 12V input — verify thermal pad / heatsink requirement at the load current." : "5V → 3.3V drop is 1.7V; ~85mW per 50mA load — TO-220 unnecessary at sub-200mA loads."} For >300mA loads consider buck_3v3 instead.`,
    };
  },
  interface: {
    "VIN": "VIN",
    "GND_IN": "GND_IN",
    "3V3": "3V3_OUT",
    "GND": "GND_OUT",
  },
};
