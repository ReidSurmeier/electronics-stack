// i2s_mic_inmp441.js — InvenSense INMP441 MEMS I2S microphone. Single-chip
// digital mic, 3.3V supply, includes the L/R address select and WS pulldown.
// Block exposes the standard I2S 3-wire interface + L/R select.
//
// Options:
//   channel: "L" (default) | "R" — sets L/R pin tie.

module.exports = {
  id: "i2s_mic_inmp441",
  description: "InvenSense INMP441 MEMS I2S microphone.",
  defaults: { channel: "L" },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "INMP441_I2S_Mic",
      refPrefix: "MK",
      value: `INMP441 I2S MEMS mic (channel ${o.channel})`,
      bodyText: `INMP441\nI2S MEMS mic\nch ${o.channel}`,
      width: 30.48,
      leftPins: ["VDD", "GND", "L_R_SEL"],
      rightPins: ["I2S_BCLK", "I2S_WS", "I2S_SD"],
      datasheet: "https://invensense.tdk.com/wp-content/uploads/2015/02/INMP441.pdf",
      description: `InvenSense INMP441 MEMS I2S microphone. VDD = 1.8-3.3V (use 3.3V), 0.1uF + 1uF decoupling. L_R_SEL ${o.channel === "L" ? "tied to GND for LEFT channel" : "tied to VDD for RIGHT channel"}. SD output is high-impedance during the unselected channel slot — multiple INMP441s can share the SD line as long as they have opposite L/R pins. Sample rate determined by master clock on BCLK; 64x WS for 24-bit data.`,
    };
  },
  interface: {
    "VCC": "VDD",
    "GND": "GND",
    "BCLK": "I2S_BCLK",
    "WS": "I2S_WS",
    "LRCLK": "I2S_WS",
    "SD": "I2S_SD",
  },
};
