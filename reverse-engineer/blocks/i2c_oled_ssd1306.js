// i2c_oled_ssd1306.js — SSD1306 OLED display module on I2C with on-board
// pull-up resistors (4.7k typical). Most SSD1306 modules already have pull-ups,
// so this block models them as part of the block. If your design has multiple
// I2C devices, only one block should provide the pull-ups (set hasPullups:false).
//
// Options:
//   addr: 0x3C (default) | 0x3D — I2C address.
//   hasPullups: true (default) — 4.7k pull-ups on SDA/SCL inside the block.
//   width: 128 (default) | 64 — display pixel width.

module.exports = {
  id: "i2c_oled_ssd1306",
  description: "SSD1306 0.96in OLED I2C display.",
  defaults: { addr: 0x3c, hasPullups: true, width: 128 },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "SSD1306_OLED",
      refPrefix: "U",
      value: `SSD1306 OLED ${o.width}x64 I2C @0x${o.addr.toString(16).toUpperCase()}`,
      bodyText: `SSD1306\nI2C OLED\n0x${o.addr.toString(16).toUpperCase()}`,
      width: 35.56,
      leftPins: ["VCC", "GND", "SDA", "SCL"],
      rightPins: [],
      datasheet: "https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf",
      description: `SSD1306 ${o.width}x64 OLED on I2C at 0x${o.addr.toString(16).toUpperCase()}. ${o.hasPullups ? "On-board 4.7k pull-ups on SDA/SCL." : "External pull-ups required (not provided by this block)."} VCC = 3.3V (some modules accept 5V via on-board LDO; verify silkscreen).`,
    };
  },
  interface: {
    "VCC": "VCC",
    "GND": "GND",
    "SDA": "SDA",
    "SCL": "SCL",
  },
  side: "left",
};
