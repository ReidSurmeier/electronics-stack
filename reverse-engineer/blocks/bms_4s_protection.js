// bms_4s_protection.js — 4S Li-ion BMS + inline fuse + isolator switch + TVS.
// Single block that protects a 4S 14.4V nominal battery pack and presents
// a clean P+/P- output to the rest of the system. Models the BMS, fuse,
// switch, and TVS as one block; the BOM lists them as separate items.
//
// Options:
//   continuousA: 30 (default) — BMS continuous current rating in amps.
//   fuseA: 15 (default) — inline fuse rating in amps.
//   tvsPart: "1.5KE36CA" (default) — TVS part across PACK+/PACK-.

module.exports = {
  id: "bms_4s_protection",
  description: "4S Li-ion BMS + fuse + isolator + TVS.",
  defaults: { continuousA: 30, fuseA: 15, tvsPart: "1.5KE36CA" },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "BMS_4S_Protected",
      refPrefix: "U",
      value: `4S BMS ${o.continuousA}A + F${o.fuseA}A + iso + ${o.tvsPart}`,
      bodyText: `4S BMS\n${o.continuousA}A + ${o.fuseA}A fuse\n+ iso + TVS`,
      width: 50.8,
      leftPins: ["B-", "B1", "B2", "B3", "B+"],
      rightPins: ["P+", "P-"],
      datasheet: "https://www.aliexpress.com/wholesale/4S-30A-BMS.html",
      description: `4S Li-ion BMS (Daly/JBD-style) with ${o.continuousA}A continuous discharge, integrated balancing, per-cell OVP/UVP/OCP/SCP. Output P+/P- protected by an inline ${o.fuseA}A ATC blade fuse, a 60A SPST isolator switch, and a ${o.tvsPart} TVS clamp across P+/P-. B- is common ground with P- inside the block. Wire B- to cell-, B1/B2/B3 to inter-cell taps, B+ to cell+.`,
    };
  },
  interface: {
    "B-": "B-",
    "B1": "B1",
    "B2": "B2",
    "B3": "B3",
    "B+": "B+",
    "P+": "P+",
    "P-": "P-",
  },
};
