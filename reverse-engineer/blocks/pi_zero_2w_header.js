// pi_zero_2w_header.js — Raspberry Pi Zero 2 W 40-pin header. Models the
// header as the SBC's interface to the rest of the design. Pin names follow
// the standard Raspberry Pi 40-pin GPIO convention.
//
// Options:
//   variant: "zero2w" (default) | "zero" | "5" — same physical 40-pin header
//     but useful as metadata for BOM cross-check.

module.exports = {
  id: "pi_zero_2w_header",
  description: "Raspberry Pi Zero 2 W 40-pin GPIO header.",
  defaults: { variant: "zero2w" },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "Pi_Header_40pin",
      refPrefix: "J",
      value: `Pi ${o.variant} 40-pin header`,
      bodyText: `RPi ${o.variant}\n40-pin\nGPIO header`,
      width: 40.64,
      leftPins: [
        "3V3_PIN1", "5V_PIN2", "GPIO2_SDA1", "5V_PIN4", "GPIO3_SCL1",
        "GND_PIN6", "GPIO4_GPCLK0", "GPIO14_TXD", "GND_PIN9", "GPIO15_RXD",
        "GPIO17", "GPIO18_PCM_CLK", "GPIO27", "GND_PIN14", "GPIO22",
        "GPIO23", "3V3_PIN17", "GPIO24", "GPIO10_SPI_MOSI", "GND_PIN20",
      ],
      rightPins: [
        "GPIO9_SPI_MISO", "GPIO25", "GPIO11_SPI_SCLK", "GPIO8_SPI_CE0", "GND_PIN25",
        "GPIO7_SPI_CE1", "ID_SD", "ID_SC", "GND_PIN30", "GPIO5",
        "GPIO6", "GPIO12_PWM0", "GPIO13_PWM1", "GND_PIN34", "GPIO19_PCM_FS",
        "GPIO16", "GPIO26", "GPIO20_PCM_DIN", "GND_PIN39", "GPIO21_PCM_DOUT",
      ],
      datasheet: "https://datasheets.raspberrypi.com/rpizero2/raspberry-pi-zero-2-w-product-brief.pdf",
      description: `Raspberry Pi ${o.variant} 40-pin GPIO header. Standard Raspberry Pi pinout. 5V (pins 2, 4) sources up to ~2A from the SBC's USB power input — verify your SBC's PMIC budget. 3V3 (pins 1, 17) is rail-limited to ~50mA total. ID_SD/ID_SC reserved for HAT EEPROM (avoid use unless you are intentionally implementing a HAT).`,
    };
  },
  interface: {
    "3V3": "3V3_PIN1",
    "5V": "5V_PIN2",
    "GND": "GND_PIN6",
    "SDA": "GPIO2_SDA1",
    "SCL": "GPIO3_SCL1",
    "TX": "GPIO14_TXD",
    "RX": "GPIO15_RXD",
    "MOSI": "GPIO10_SPI_MOSI",
    "MISO": "GPIO9_SPI_MISO",
    "SCK": "GPIO11_SPI_SCLK",
    "CE0": "GPIO8_SPI_CE0",
    "CE1": "GPIO7_SPI_CE1",
    "I2S_BCLK": "GPIO18_PCM_CLK",
    "I2S_LRCLK": "GPIO19_PCM_FS",
    "I2S_DIN": "GPIO20_PCM_DIN",
    "I2S_DOUT": "GPIO21_PCM_DOUT",
    "PWM0": "GPIO12_PWM0",
    "PWM1": "GPIO13_PWM1",
  },
};
