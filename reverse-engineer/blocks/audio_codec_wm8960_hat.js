// audio_codec_wm8960_hat.js — Cirrus Logic WM8960 stereo audio codec with the
// usual bias network (REFGND decoupling cap, MIC bias output, AVDD/DCVDD
// decoupling). Modeled after the Waveshare WM8960 HAT for the Pi but exposed
// generically as I2S + I2C.
//
// Options:
//   masterMode: false (default — codec is I2S slave) | true.
//   spkAmp: true (default — on-board class-D speaker amplifier) | false.

module.exports = {
  id: "audio_codec_wm8960_hat",
  description: "WM8960 stereo audio codec with mic bias + speaker amp.",
  defaults: { masterMode: false, spkAmp: true },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "WM8960_Codec",
      refPrefix: "U",
      value: `WM8960 codec (${o.masterMode ? "master" : "slave"}${o.spkAmp ? ", spk amp" : ""})`,
      bodyText: "WM8960\nstereo codec\nI2S + I2C",
      width: 45.72,
      leftPins: ["AVDD_3V3", "DCVDD_3V3", "GND", "I2C_SDA", "I2C_SCL", "I2S_BCLK", "I2S_LRCLK", "I2S_DIN", "I2S_DOUT"],
      rightPins: ["MIC_BIAS", "MIC_LP", "MIC_LN", "MIC_RP", "MIC_RN", "HP_L", "HP_R", "SPK_LP", "SPK_LN", "SPK_RP", "SPK_RN"],
      datasheet: "https://statics.cirrus.com/pubs/proDatasheet/WM8960_v4.4.pdf",
      description: `WM8960 stereo audio codec. AVDD/DCVDD = 3.3V (separate rails recommended), each with 10uF + 100nF decoupling. REFGND requires a 1uF cap to GND (handled internally to this block). I2C address 0x1A. I2S in ${o.masterMode ? "master" : "slave"} mode. ${o.spkAmp ? "On-board class-D bridge-tied speaker amp drives SPK_LP/LN and SPK_RP/RN to 4-8 ohm speakers; do not common any output." : "Headphone outputs only — no speaker amp on this variant."} MIC_BIAS supplies 0.65*AVDD to electret microphones.`,
    };
  },
  interface: {
    "VCC": "AVDD_3V3",
    "DVCC": "DCVDD_3V3",
    "GND": "GND",
    "SDA": "I2C_SDA",
    "SCL": "I2C_SCL",
    "BCLK": "I2S_BCLK",
    "LRCLK": "I2S_LRCLK",
    "DIN": "I2S_DIN",
    "DOUT": "I2S_DOUT",
  },
};
