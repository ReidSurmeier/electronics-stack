#!/usr/bin/env python3
"""describe_to_spec.py — natural language → compile.js YAML spec.

Pipes a free-form description ("ESP32 weather station with BME280 over I2C,
OLED display, USB-C power") through Claude and emits a YAML spec compatible
with compile.js. Then optionally invokes compile.js to produce the .kicad_sch.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 describe_to_spec.py "ESP32 weather station with BME280 + OLED, USB-C power" \\
        --out output/weather_llm
    # OR pipe stdin:
    echo "ESP32 weather station..." | python3 describe_to_spec.py --out output/weather_llm

Defaults to claude-opus-4-7 (matches the user's max plan). Set
$REVERSE_ENGINEER_MODEL to override.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("Error: anthropic SDK not installed. Run: pip install anthropic")

HERE = Path(__file__).parent
BLOCKS_DIR = HERE / "blocks"

# Default model — Claude Opus 4.7. Falls back to env override if set.
DEFAULT_MODEL = os.environ.get("REVERSE_ENGINEER_MODEL", "claude-opus-4-5")


def load_block_catalog() -> str:
    """Build a compact, prompt-cacheable catalog of available blocks."""
    blocks_index_js = BLOCKS_DIR / "index.js"
    if not blocks_index_js.exists():
        sys.exit(f"Block library not found at {BLOCKS_DIR}")
    out = subprocess.run(
        [
            "node",
            "-e",
            (
                "const b = require('./blocks');"
                "const r = Object.entries(b).map(([k,v]) => ({"
                "id: k,"
                "description: v.description,"
                "interface: Object.keys(v.interface || {}),"
                "defaults: v.defaults || {}"
                "}));"
                "console.log(JSON.stringify(r, null, 2));"
            ),
        ],
        capture_output=True, text=True, cwd=str(HERE), check=True,
    )
    return out.stdout


SYSTEM_PROMPT = """You are a hardware engineer translating natural-language electronics design briefs into a YAML "spec" file consumed by a block-based KiCad schematic compiler.

The available blocks and their `interface` pins are listed below. You may ONLY use these blocks. If a brief asks for something with no matching block, choose the closest analog and include a `notes:` warning at the end of the YAML.

Block interface pins are friendly names (`SDA`, `5V`, `GND`, `MOSI`, …). Use them in the `nets:` section as `<block_name>.<pin>`.

Output rules:
- Emit ONLY YAML. No prose, no fenced code blocks, no preamble.
- Always include `project:`, `title:`, `rev: A`.
- Block instance names: snake_case prefixed `u_` for ICs/modules (`u_mcu`, `u_pwr`), `j_` for connectors (`j_usb`).
- Every block's `GND` must appear in a single `GND` net.
- Every powered block's primary supply pin (`VCC`, `3V3`, `5V`, etc.) must appear in a power net.
- Group I2C devices on `I2C_SDA` / `I2C_SCL`. Group SPI on `SPI_SCK` / `SPI_MOSI` / `SPI_MISO` plus per-CS net.
- For USB-C power, wire the USB data pair only if there is a peripheral that uses it (e.g. ESP32 USB-UART). Otherwise omit the data lines.
- Add a `notes:` block at the end summarizing assumptions, current-budget concerns, and anything the brief was unclear about.

Example output for "ESP32 with BME280 over I2C, USB-C power":
```yaml
project: ExampleBoard
title: ESP32 + BME280 board
rev: A

blocks:
  u_pwr:
    type: usb_c_input_5v
  u_reg:
    type: buck_3v3
    opts: { regType: ldo }
  u_mcu:
    type: mcu_esp32_wroom
  u_bme:
    type: bme280_i2c

nets:
  - net: VBUS_5V
    conns: [u_pwr.5V, u_reg.VIN, u_reg.EN]
  - net: P3V3
    conns: [u_reg.3V3, u_mcu.VCC, u_mcu.EN, u_bme.VCC]
  - net: GND
    conns: [u_pwr.GND, u_reg.GND_IN, u_reg.GND, u_mcu.GND, u_bme.GND]
  - net: I2C_SDA
    conns: [u_mcu.SDA, u_bme.SDA]
  - net: I2C_SCL
    conns: [u_mcu.SCL, u_bme.SCL]

notes: |
  Default LDO sized for ~1A; ESP32 WiFi TX peak is ~350mA so margin is OK.
```
"""


def call_claude(brief: str, catalog: str, model: str) -> str:
    client = anthropic.Anthropic()
    user_content = (
        "Here is the available block catalog (JSON):\n\n"
        f"{catalog}\n\n"
        "Brief:\n"
        f"{brief}\n\n"
        "Emit the YAML spec now."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    return text.strip()


def strip_code_fence(text: str) -> str:
    """Strip leading/trailing ```yaml fences if Claude added them anyway."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        text = text[first_nl + 1:] if first_nl > 0 else text
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("brief", nargs="?", help="Natural-language design brief. Reads stdin if omitted.")
    p.add_argument("--out", required=True, help="Output directory for the compiled KiCad project.")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model id (default: {DEFAULT_MODEL})")
    p.add_argument("--spec-only", action="store_true", help="Print/save spec YAML but skip compile.js.")
    p.add_argument("--bom", default=None, help="Optional BOM CSV passed through to compile.js.")
    args = p.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "ANTHROPIC_API_KEY not set. Export it from Bitwarden or your env "
            "(e.g. `export ANTHROPIC_API_KEY=$(bw get password anthropic-api)`)."
        )

    brief = args.brief or sys.stdin.read().strip()
    if not brief:
        sys.exit("No brief provided (positional arg or stdin).")

    catalog = load_block_catalog()
    print(f"Calling {args.model}…", file=sys.stderr)
    yaml_text = call_claude(brief, catalog, args.model)
    yaml_text = strip_code_fence(yaml_text)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / "spec.yaml"
    spec_path.write_text(yaml_text + "\n")
    print(f"Spec written to {spec_path}", file=sys.stderr)

    if args.spec_only:
        print(yaml_text)
        return 0

    cmd = ["node", str(HERE / "compile.js"), str(spec_path), "-o", str(out_dir), "-v"]
    if args.bom:
        cmd.extend(["--bom", args.bom])
    print(f"Running: {' '.join(cmd)}", file=sys.stderr)
    res = subprocess.run(cmd, cwd=str(HERE))
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
