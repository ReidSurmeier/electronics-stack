# Block Library

Reusable circuit blocks for the reverse-engineer compiler. Each `*.js`
file exports an object with:

- `id` — string identifier (matches filename, used in spec files)
- `description` — short human description
- `defaults` — default option values
- `symbol(opts)` — returns a kicad-emit `spec` (name, leftPins, rightPins,
  refPrefix, value, bodyText, datasheet, description)
- `interface` — map from friendly names (used in spec `nets`) to actual pin
  names on the symbol. e.g. `{ "5V": "5V_OUT", "GND": "GND" }`

## Available blocks

| id | description |
|---|---|
| `usb_c_input_5v` | USB-C 5V input + ESD protection + bulk cap |
| `buck_3v3` | 5V → 3.3V regulator (LDO or buck — see `regType`) |
| `linear_regulator_3v3` | Discrete 3-pin LDO 3.3V (LM1117 / AMS1117) |
| `mcu_esp32_wroom` | ESP32-WROOM-32 with strapping + USB-UART |
| `pi_zero_2w_header` | Raspberry Pi Zero 2 W 40-pin GPIO header |
| `i2c_oled_ssd1306` | SSD1306 0.96in OLED I2C display |
| `bme280_i2c` | Bosch BME280 temp/humidity/pressure (I2C) |
| `i2s_mic_inmp441` | InvenSense INMP441 MEMS I2S microphone |
| `audio_codec_wm8960_hat` | WM8960 stereo codec + speaker amp |
| `rj45_magnetics_w5500` | Wiznet W5500 SPI Ethernet + RJ45 magjack |
| `bms_4s_protection` | 4S Li-ion BMS + fuse + isolator + TVS |
| `decap_caps` | Generic decoupling cap network (service block) |

## Pin sides

By default a block has its `leftPins` on the left (input/power) and `rightPins`
on the right (signals/output). The compiler uses `endpoint(spec, side, ...)`
to find absolute coordinates, so blocks can choose either side for their
interface — the `side` field on the block (or implicit from which list a pin
is in) tells the compiler which side to emit net labels off of.

## Adding a new block

1. Create `blocks/<id>.js`
2. Export `id`, `description`, `defaults`, `symbol(opts)`, `interface`
3. The compiler picks it up automatically via `blocks/index.js`
