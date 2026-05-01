# reverse-engineer

Prototype tool: takes a textual electronics design description (and optionally
a BOM) and produces a draft KiCad 9 schematic.

## Approach

Block-library compiler. A YAML "spec" lists pre-built circuit blocks and the
nets that connect them; `compile.js` emits a complete `.kicad_sch` +
`.kicad_sym` + `.kicad_pro`. ERC-clean by construction.

For free-form natural-language input, `describe_to_spec.py` calls Claude to
translate a brief into the YAML spec, then pipes through `compile.js`.

## Quickstart

```bash
# install deps (one-time)
npm install                     # for js-yaml
pip install anthropic           # for the LLM bridge (optional)

# compile a YAML spec
node compile.js examples/pi_audio_oled.yaml -o output/pi_audio_oled

# verify ERC
kicad-cli sch erc output/pi_audio_oled/PiAudioOLED.kicad_sch \
  --severity-all -o /tmp/erc.rpt

# natural-language → KiCad (LLM bridge)
export ANTHROPIC_API_KEY=...
python3 describe_to_spec.py "ESP32 weather station with BME280 + OLED, USB-C power" \
  --out output/weather
```

## Layout

```
reverse-engineer/
  compile.js               # YAML spec → KiCad project compiler
  describe_to_spec.py      # natural-language → YAML spec (Claude)
  lib/kicad_emit.js        # shared S-expression emission primitives
  blocks/                  # 12 reusable circuit blocks
    index.js               # auto-registers every *.js sibling
    *.js                   # one block per file
  examples/                # ready-to-build example specs
  output/                  # compiled KiCad projects
  atopile_test/            # atopile investigation (see findings below)
```

## Block library

12 blocks (see `blocks/README.md` for full list):

- `usb_c_input_5v`, `buck_3v3`, `linear_regulator_3v3`, `bms_4s_protection`,
  `decap_caps`
- `mcu_esp32_wroom`, `pi_zero_2w_header`
- `i2c_oled_ssd1306`, `bme280_i2c`, `i2s_mic_inmp441`,
  `audio_codec_wm8960_hat`, `rj45_magnetics_w5500`

Each block exposes a friendly `interface` (e.g. `SDA`, `VCC`, `GND`) decoupled
from the actual pin name on the symbol — so spec files survive symbol
re-shuffling.

## Spec format

```yaml
project: ExampleBoard
title: Example Board
rev: A

blocks:
  u_pwr:  { type: usb_c_input_5v }
  u_reg:  { type: buck_3v3, opts: { regType: ldo } }
  u_mcu:  { type: mcu_esp32_wroom }
  u_oled: { type: i2c_oled_ssd1306, opts: { addr: 0x3C } }

nets:
  - net: VBUS_5V
    conns: [u_pwr.5V, u_reg.VIN, u_reg.EN]
  - net: P3V3
    conns: [u_reg.3V3, u_mcu.VCC, u_mcu.EN, u_oled.VCC]
  - net: GND
    conns: [u_pwr.GND, u_reg.GND_IN, u_reg.GND, u_mcu.GND, u_oled.GND]
  - net: I2C_SDA
    conns: [u_mcu.SDA, u_oled.SDA]
  - net: I2C_SCL
    conns: [u_mcu.SCL, u_oled.SCL]
```

## atopile investigation

atopile (v0.12.5 installed via `uv tool install atopile`) is a declarative
`.ato` language that builds to a KiCad **PCB** layout (`.kicad_pcb`) plus a
netlist (`.net`) and BOM. It does **not** emit a `.kicad_sch` schematic; the
intended workflow is to open the project in KiCad and let atopile update the
PCB in place. For our use case (schematic generation as a verification artifact),
that's the wrong output. atopile is also opinionated about its own component
library and would require building atopile-flavored `Module` definitions for
every block — duplicating the JS block library.

`circuit-synth` does emit `.kicad_sch` directly from Python and is actively
maintained (v0.12.1, Jan 2026), but it would require porting the existing JS
block library and re-validating against the user's CM5_Portable / Phone_Project
generators.

The block-library JS approach (option 4) wins because:
1. Re-uses the user's existing `generate_project.js` S-expression patterns.
2. Emits `.kicad_sch` directly (no GUI step, no PCB layout phase).
3. Block surface is small and debuggable — pure data transformation.
4. ERC-clean by construction (every interface pin is wired or no_connect).
