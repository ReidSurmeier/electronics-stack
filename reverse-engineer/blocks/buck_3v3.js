// buck_3v3.js — generic 5V→3.3V regulator block. Configurable as LDO (AMS1117)
// or buck (MP1584). The block presents the same interface either way; the
// compiler only swaps the value text + datasheet.
//
// Options:
//   regType: "ldo" (default — AMS1117-3.3) | "buck" (MP1584).
//   maxCurrent: "1A" (default LDO) | "3A" (buck).
//   inputCap: 10 (default uF) — input cap.
//   outputCap: 22 (default uF) — output cap.

module.exports = {
  id: "buck_3v3",
  description: "5V to 3.3V regulator (LDO or buck).",
  defaults: { regType: "ldo", maxCurrent: "1A", inputCap: 10, outputCap: 22 },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    const isLdo = o.regType === "ldo";
    const part = isLdo ? "AMS1117-3.3" : "MP1584";
    const datasheet = isLdo
      ? "http://www.advanced-monolithic.com/pdf/ds1117.pdf"
      : "https://www.monolithicpower.com/en/mp1584.html";
    return {
      name: "Regulator_3V3",
      refPrefix: "U",
      value: `${part} 5V→3.3V ${o.maxCurrent}`,
      bodyText: `${part}\n5V → 3V3\n${o.maxCurrent}`,
      width: 35.56,
      leftPins: ["VIN", "EN", "GND_IN"],
      rightPins: ["3V3_OUT", "GND_OUT"],
      datasheet,
      description: `5V-to-3.3V regulator implemented as a ${isLdo ? "linear" : "buck"} converter using ${part}. Input capacitor ${o.inputCap}uF on VIN, output capacitor ${o.outputCap}uF on 3V3_OUT, both referenced to GND. EN may be tied to VIN for always-on operation.`,
    };
  },
  interface: {
    "VIN": "VIN",
    "EN": "EN",
    "GND_IN": "GND_IN",
    "3V3": "3V3_OUT",
    "GND": "GND_OUT",
  },
};
