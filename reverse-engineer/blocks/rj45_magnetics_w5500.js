// rj45_magnetics_w5500.js — Wiznet W5500 SPI Ethernet controller with an
// integrated-magnetics RJ45 jack (HanRun HR911105A or equivalent). Single
// block presents an SPI interface + an RJ45 connector externally.
//
// Options:
//   addr: 0 (default) — W5500 chip-select index.
//   ledStyle: "amber-green" (default) | "green-yellow" — LED color pair.

module.exports = {
  id: "rj45_magnetics_w5500",
  description: "Wiznet W5500 SPI Ethernet + RJ45 with integrated magnetics.",
  defaults: { addr: 0, ledStyle: "amber-green" },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "W5500_RJ45_Mag",
      refPrefix: "U",
      value: `W5500 + HR911105A RJ45 (LED ${o.ledStyle})`,
      bodyText: "W5500\n+ RJ45 magjack\nSPI Ethernet",
      width: 50.8,
      leftPins: ["3V3", "GND", "SPI_SCK", "SPI_MOSI", "SPI_MISO", "SPI_CS", "INT", "RST"],
      rightPins: ["RJ45_TXP", "RJ45_TXN", "RJ45_RXP", "RJ45_RXN", "LED_LINK", "LED_ACT"],
      datasheet: "https://www.wiznet.io/product-item/w5500/",
      description: `Wiznet W5500 SPI-to-Ethernet controller paired with a HanRun HR911105A RJ45 with integrated magnetics. CS index ${o.addr}. SPI mode 0/3, up to 80 MHz. Requires 3.3V supply with 100nF + 10uF decoupling, a 25 MHz crystal (on-board), and 50-ohm differential trace impedance to RJ45 magjack. The block hides the magnetics, termination caps, and Bob Smith network. INT is open-drain and should pull up to 3V3. RST active-low.`,
    };
  },
  interface: {
    "3V3": "3V3",
    "GND": "GND",
    "SCK": "SPI_SCK",
    "MOSI": "SPI_MOSI",
    "MISO": "SPI_MISO",
    "CS": "SPI_CS",
    "INT": "INT",
    "RST": "RST",
  },
};
