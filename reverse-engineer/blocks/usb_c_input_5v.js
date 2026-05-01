// usb_c_input_5v.js — USB-C connector + ESD diode + bulk cap front-end.
// Models a USB-C receptacle delivering 5V VBUS with ESD protection on D+/D- and
// a bulk capacitor across VBUS/GND. Treated as a single block-level symbol
// (the components are shown as one outline; the compiler pulls real parts from
// the BOM). Pins are the external interface to the rest of the design.
//
// Options:
//   currentRating: "3A" (default) | "5A" — used in BOM cross-check.
//   esdPart: e.g. "USBLC6-2SC6" — part for ESD diode block.
//   bulkCapUf: 22 (default) | 47 | 100 — bulk cap value.
//
// External pins (right side, output to rest of board):
//   5V_OUT, GND, USB_DP, USB_DM, CC1, CC2

module.exports = {
  id: "usb_c_input_5v",
  description: "USB-C 5V input with ESD protection and bulk cap.",
  defaults: { currentRating: "3A", esdPart: "USBLC6-2SC6", bulkCapUf: 22 },
  symbol(opts = {}) {
    const o = { ...this.defaults, ...opts };
    return {
      name: "USB_C_Input_5V",
      refPrefix: "J",
      value: `USB-C 5V input (${o.currentRating}, ${o.bulkCapUf}uF)`,
      bodyText: `USB-C\n5V/${o.currentRating}\n+ ESD + bulk`,
      width: 38.1,
      leftPins: [],
      rightPins: ["5V_OUT", "GND", "USB_DP", "USB_DM", "CC1", "CC2"],
      datasheet: "https://www.usb.org/document-library/usb-type-cr-cable-and-connector-specification-revision-22",
      description: `USB-C 5V input front-end. Includes USB-C receptacle, ${o.esdPart} ESD protection on USB_DP/USB_DM, and ${o.bulkCapUf}uF bulk cap across 5V_OUT and GND. Sized for ${o.currentRating} continuous draw. CC1/CC2 are pulled to the receptacle's CC pins; for sink-only operation tie 5.1k to GND on each (handled at the block-instance level if requested).`,
    };
  },
  // The block's "interface" — names that can be used in the spec's `nets` block.
  interface: {
    "5V": "5V_OUT",
    "GND": "GND",
    "DP": "USB_DP",
    "DM": "USB_DM",
    "CC1": "CC1",
    "CC2": "CC2",
  },
  side: "right", // pins live on right side of the block
};
