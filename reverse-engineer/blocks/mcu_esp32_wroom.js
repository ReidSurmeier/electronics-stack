// mcu_esp32_wroom.js — ESP32-WROOM-32 module with strapping resistors and a
// USB-UART interface for programming (CP2102 or CH340 — selectable).
// Externally exposes power, programming, and a usable subset of GPIO pins.
//
// Options:
//   uart: "cp2102" (default) | "ch340" | "none" (use external programmer).
//   bootButton: true (default) — adds a BOOT button on GPIO0.
//   en_pullup_kohm: 10 (default).

module.exports = {
  id: "mcu_esp32_wroom",
  description: "ESP32-WROOM-32 module with strapping + USB-UART for programming.",
  defaults: { uart: "cp2102", bootButton: true, en_pullup_kohm: 10 },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "ESP32_WROOM_32",
      refPrefix: "U",
      value: `ESP32-WROOM-32 (UART: ${o.uart})`,
      bodyText: "ESP32-WROOM-32\n+ strapping\n+ USB-UART",
      width: 50.8,
      leftPins: ["VCC", "GND", "EN", "BOOT", "USB_DP", "USB_DM"],
      rightPins: [
        "GPIO0", "GPIO1_TX", "GPIO2", "GPIO3_RX",
        "GPIO4", "GPIO5", "GPIO12", "GPIO13",
        "GPIO14", "GPIO15", "GPIO16", "GPIO17",
        "GPIO18_SCK", "GPIO19", "GPIO21_SDA", "GPIO22_SCL",
        "GPIO23_MOSI", "GPIO25_DAC1", "GPIO26_DAC2", "GPIO27",
        "GPIO32", "GPIO33", "GPIO34_IN", "GPIO35_IN",
        "GPIO36_VP", "GPIO39_VN",
      ],
      datasheet: "https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32_datasheet_en.pdf",
      description: `ESP32-WROOM-32 module. VCC = 3.3V (350mA peak during WiFi TX). EN has a ${o.en_pullup_kohm}k pull-up + 0.1uF cap. GPIO0/GPIO2/GPIO12/GPIO15 are strapping pins — leave floating during boot or use the dedicated programming circuit. ${o.uart === "none" ? "External programmer required (no on-board USB-UART)." : `On-board ${o.uart === "cp2102" ? "CP2102 USB-UART" : "CH340 USB-UART"} brings USB_DP/USB_DM in and exposes serial via GPIO1_TX/GPIO3_RX.`} ${o.bootButton ? "BOOT button between GPIO0 and GND." : ""} 10uF + 100nF decoupling on VCC.`,
    };
  },
  interface: {
    "VCC": "VCC",
    "GND": "GND",
    "EN": "EN",
    "USB_DP": "USB_DP",
    "USB_DM": "USB_DM",
    "GPIO0": "GPIO0",
    "TX": "GPIO1_TX",
    "RX": "GPIO3_RX",
    "GPIO2": "GPIO2",
    "GPIO4": "GPIO4",
    "GPIO5": "GPIO5",
    "SCK": "GPIO18_SCK",
    "MOSI": "GPIO23_MOSI",
    "MISO": "GPIO19",
    "SDA": "GPIO21_SDA",
    "SCL": "GPIO22_SCL",
    "DAC1": "GPIO25_DAC1",
    "DAC2": "GPIO26_DAC2",
    "I2S_BCLK": "GPIO26_DAC2",
    "I2S_LRCLK": "GPIO25_DAC1",
    "I2S_SD": "GPIO22_SCL",
  },
};
