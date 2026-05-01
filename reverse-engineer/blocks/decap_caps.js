// decap_caps.js — generic decoupling cap network. Drops 100nF + 10uF caps
// across the requested rail and GND. Useful as a "service" block — you don't
// usually wire it explicitly in `nets`, you just attach it to a rail.
//
// Options:
//   rail: "3V3" (default) — net name to decouple.
//   count: 4 (default) — number of 100nF caps (one per major IC).
//   bulkUf: 10 (default) — bulk cap value in uF.

module.exports = {
  id: "decap_caps",
  description: "Generic decoupling cap network (100nF x N + bulk).",
  defaults: { rail: "3V3", count: 4, bulkUf: 10 },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "Decap_Network",
      refPrefix: "C",
      value: `Decap ${o.rail}: ${o.count}x100nF + ${o.bulkUf}uF`,
      bodyText: `Decap\n${o.rail}\n${o.count}x100nF\n+ ${o.bulkUf}uF`,
      width: 30.48,
      leftPins: ["RAIL", "GND"],
      rightPins: [],
      datasheet: "~",
      description: `Decoupling network on ${o.rail}: ${o.count} x 100nF MLCC ceramic (one per IC supply pin), one ${o.bulkUf}uF bulk capacitor. All return to GND. Place 100nF caps directly at IC power pins; place bulk near the regulator output / supply entry. Net name on RAIL pin is "${o.rail}".`,
    };
  },
  interface: {
    "VCC": "RAIL",
    "RAIL": "RAIL",
    "GND": "GND",
  },
};
