// bme280_i2c.js — Bosch BME280 environmental sensor (temp/humidity/pressure)
// on I2C. Used by the smoke-test "weather station" example.
//
// Options:
//   addr: 0x76 (default — SDO=GND) | 0x77 (SDO=VDD).

module.exports = {
  id: "bme280_i2c",
  description: "Bosch BME280 temp/humidity/pressure sensor (I2C).",
  defaults: { addr: 0x76 },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "BME280_I2C",
      refPrefix: "U",
      value: `BME280 @0x${o.addr.toString(16).toUpperCase()}`,
      bodyText: `BME280\nI2C T/H/P\n0x${o.addr.toString(16).toUpperCase()}`,
      width: 30.48,
      leftPins: ["VDD", "GND", "SDA", "SCL"],
      rightPins: [],
      datasheet: "https://www.bosch-sensortec.com/products/environmental-sensors/humidity-sensors-bme280/",
      description: `Bosch BME280 combined temperature, humidity, and pressure sensor on I2C at 0x${o.addr.toString(16).toUpperCase()}. VDD = 1.71-3.6V (use 3.3V). 100nF decoupling on VDD. SDO pin pulled ${o.addr === 0x76 ? "low (GND)" : "high (VDD)"} inside the block.`,
    };
  },
  interface: {
    "VCC": "VDD",
    "GND": "GND",
    "SDA": "SDA",
    "SCL": "SCL",
  },
};
