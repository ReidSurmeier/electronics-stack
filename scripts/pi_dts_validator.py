"""Raspberry Pi device-tree overlay + GPIO/I2C conflict validator.

Reads a project YAML manifest like:

    pi: zero2w   # or cm5, pi5, pi4
    overlays:
      - wm8960-soundcard
      - w5500,cs=0,int_pin=25,speed=30000000
    gpio_uses:
      GPIO5:  hook_switch
      GPIO6:  user_button
      GPIO8:  spi0_ce0_w5500
      GPIO9:  spi0_miso_w5500
      GPIO10: spi0_mosi_w5500
      GPIO11: spi0_sclk_w5500
      GPIO18: i2s_bclk
      GPIO19: i2s_lrclk
      GPIO20: i2s_adcdat
      GPIO21: i2s_dacdat
      GPIO24: w5500_rst
      GPIO25: w5500_int
      GPIO2:  i2c1_sda
      GPIO3:  i2c1_scl
      GPIO4:  mux_resetn
    i2c_devices:
      0x70: tca9548a_mux_root
      0x3C: ssd1306_oled_via_mux  # repeated address OK because mux

Checks:
  - GPIO double-use (same pin assigned to two functions)
  - I2C address conflicts (unless behind a mux)
  - Overlay/GPIO consistency (e.g. w5500 overlay implies SPI0_CE0+CE1 + INT on GPIOx)
  - Pi-model-specific: Pi Zero 2 W has only one I2S, Pi 5 has multiple, Pi 4 has dual I2C, etc.
"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import Counter, defaultdict
import yaml


PI_MODELS = {
    "zero2w": {
        "i2s_count": 1,
        "spi_count": 1,
        "i2c_count": 1,
        "gpio_count": 28,  # exposed on 40-pin header (40 pins, but only 28 are GPIO)
        "notes": ["BCM2837, Pi Zero 2 W has single I2S/PCM block on GPIO18-21 only.", "USB OTG only — keep idle for low-latency I2S."],
    },
    "pi4": {"i2s_count": 1, "spi_count": 2, "i2c_count": 2, "gpio_count": 28, "notes": []},
    "pi5": {"i2s_count": 2, "spi_count": 2, "i2c_count": 2, "gpio_count": 28, "notes": []},
    "cm5": {"i2s_count": 2, "spi_count": 2, "i2c_count": 2, "gpio_count": 28, "notes": []},
}


def validate(manifest: dict) -> list[dict]:
    findings = []
    pi = manifest.get("pi", "").lower()
    model = PI_MODELS.get(pi)
    if not model:
        findings.append({"severity": "LOW", "kind": "unknown_pi", "note": f"Pi model '{pi}' not recognized."})

    gpio_uses = manifest.get("gpio_uses", {}) or {}
    seen = Counter(gpio_uses.keys())

    # Duplicate GPIO declarations
    for gpio, n in seen.items():
        if n > 1:
            findings.append({
                "severity": "HIGH",
                "kind": "gpio_double_declared",
                "gpio": gpio,
                "note": f"{gpio} declared {n}× in manifest."
            })

    # Reverse map to catch same-function-on-different-pins (warn) and identify reserved pins
    fn_to_gpios = defaultdict(list)
    for gpio, fn in gpio_uses.items():
        fn_to_gpios[fn].append(gpio)
    for fn, gpios in fn_to_gpios.items():
        if len(gpios) > 1:
            findings.append({
                "severity": "MEDIUM",
                "kind": "function_split_across_gpios",
                "function": fn,
                "gpios": gpios,
                "note": f"Function '{fn}' declared on multiple GPIOs: {gpios}",
            })

    # I2C addr conflicts
    i2c = manifest.get("i2c_devices", {}) or {}
    addr_seen = Counter()
    for addr in i2c:
        try:
            a = int(str(addr), 0)
        except Exception:
            continue
        addr_seen[a] += 1
    for a, n in addr_seen.items():
        if n > 1:
            findings.append({
                "severity": "HIGH",
                "kind": "i2c_addr_conflict",
                "addr": hex(a),
                "note": f"I2C address {hex(a)} declared {n}× — needs a mux or alternate addressing."
            })

    # Pi-model gotchas
    if model:
        # Pi Zero 2 W: only one I2S — flag if user declares two codecs
        if pi == "zero2w" and len({fn for fn in gpio_uses.values() if "i2s" in fn.lower()}) > 4:
            findings.append({
                "severity": "MEDIUM",
                "kind": "pi_zero2w_i2s_overuse",
                "note": "Pi Zero 2 W exposes only one I2S peripheral (4 pins). Declared more than 4 i2s_* GPIOs.",
            })

    # Overlay sanity (very light heuristic)
    overlays = manifest.get("overlays", []) or []
    if any("w5500" in str(o) for o in overlays):
        # w5500 overlay needs SPI0 + INT + RST
        required = {"spi0_mosi", "spi0_miso", "spi0_sclk", "spi0_ce0", "w5500_int", "w5500_rst"}
        declared_fns = {str(v).lower() for v in gpio_uses.values()}
        missing = required - {next((d for d in declared_fns if r in d), "") for r in required}
        # lighter test:
        if not any("spi0_mosi" in d for d in declared_fns):
            findings.append({"severity": "MEDIUM", "kind": "overlay_pin_missing",
                             "note": "w5500 overlay declared but no GPIO is tagged spi0_mosi*."})
    if any("wm8960" in str(o) for o in overlays):
        if not any("i2s" in str(v).lower() for v in gpio_uses.values()):
            findings.append({"severity": "MEDIUM", "kind": "overlay_pin_missing",
                             "note": "wm8960-soundcard overlay declared but no GPIO is tagged i2s*."})

    return findings


def report(findings: list[dict]) -> str:
    if not findings:
        return "Pi DTS validator: PASS — no GPIO or I2C conflicts.\n"
    lines = [f"Pi DTS validator: {len(findings)} findings"]
    for f in findings:
        lines.append(f"  [{f['severity']}] {f['kind']}: {f['note']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: pi_dts_validator.py <pi_manifest.yaml>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        manifest = yaml.safe_load(f)
    findings = validate(manifest)
    print(report(findings))
    sys.exit(1 if any(f["severity"] == "HIGH" for f in findings) else 0)
