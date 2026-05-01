# PIPELINE-RUN.md — Phase 6 Verification Sweep

**Date:** 2026-05-01 15:39:03 UTC  
**Projects run:** 25 / 25  
**PASS:** 8  **FAIL:** 17  
**Total wallclock:** 10.2s (0.2 min)  

| project | category | checks_run | erc | conn | power | sourcing | pi | wallclock_s | peak_mem_mb | top_error |
|---------|----------|------------|-----|------|-------|----------|----|-------------|-------------|-----------|
| USB2Speakon | audio | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.31 | 61.0 |  |
| Eurorack_Bus_Board | audio | 6 | PASS | PASS | SKIP | SKIP | PASS | 0.62 | 188.9 |  |
| STM32-RFM95-PCB | devboards | 6 | PASS | FAIL | SKIP | SKIP | FAIL | 0.58 | 188.9 | U2 pin 9 'ANA' (passive) at (119.38, 80.00999999999999) has no label, wire, or no_connect. |
| stm32h750-dev-board | devboards | 6 | FAIL | FAIL | SKIP | SKIP | FAIL | 0.69 | 191.5 | kicad-cli ERC |
| PCIe3_Hub | hats | 6 | FAIL | FAIL | SKIP | SKIP | FAIL | 0.65 | 193.7 | kicad-cli ERC |
| haxo-hw | hats | 6 | PASS | FAIL | SKIP | SKIP | FAIL | 0.58 | 193.7 | J3 pin 13 'GPIO27' (bidirectional) at (222.25, 140.97) has no label, wire, or no_connect. |
| urchin | keyboards | 6 | FAIL | FAIL | SKIP | SKIP | FAIL | 0.51 | 193.7 | kicad-cli ERC |
| urchin | keyboards | 6 | FAIL | FAIL | SKIP | SKIP | FAIL | 0.52 | 193.7 | kicad-cli ERC |
| 3dPrinter | makertools | 6 | FAIL | FAIL | SKIP | SKIP | FAIL | 0.45 | 193.7 | kicad-cli ERC |
| KiCAD_StepperAdapter | makertools | 6 | FAIL | PASS | SKIP | SKIP | PASS | 0.45 | 193.7 | kicad-cli ERC |
| pcb-motor | motor | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.27 | 193.7 |  |
| IP5328P-powerbank_design | motor | 6 | FAIL | FAIL | SKIP | SKIP | FAIL | 0.51 | 193.7 | kicad-cli ERC |
| bms-buck-boost | power | 6 | FAIL | FAIL | SKIP | SKIP | FAIL | 0.53 | 193.7 | kicad-cli ERC |
| Biploar-power-supply-KiCAD | power | 6 | FAIL | PASS | SKIP | SKIP | PASS | 0.48 | 193.7 | kicad-cli ERC |
| mdbt-micro | rf | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.25 | 193.7 |  |
| MiniSolarMesh | rf | 6 | PASS | FAIL | SKIP | SKIP | FAIL | 0.56 | 193.7 | C14 pin 2 '~' (passive) at (251.46, 193.04) has no label, wire, or no_connect. |
| LSR-drone | robotics | 6 | FAIL | PASS | SKIP | SKIP | PASS | 0.54 | 193.7 | kicad-cli ERC |
| NoahFC | robotics | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.29 | 193.7 |  |
| pmw3360-pcb | sensors | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.29 | 193.7 |  |
| pmw3610-pcb | sensors | 6 | FAIL | FAIL | SKIP | SKIP | FAIL | 0.51 | 193.7 | kicad-cli ERC |
| hardware-watchdog | wearables | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.31 | 193.7 |  |
| 555-plane-pcb | wearables | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.28 | 193.7 |  |
| 555_timer_LED_blinker_with_1Hz_frequency_9V_batte | synthetic | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.02 | 193.7 | PIPELINE_RC=2: /usr/bin/python3: can't open file '/home/reidsurmeier/electronics-stack/scripts/design_pipeline.py': [Errno 2] No such f |
| ESP32-C3_dev_board_with_USB-C_power_input_and_3.3V | synthetic | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.02 | 193.7 | PIPELINE_RC=2: /usr/bin/python3: can't open file '/home/reidsurmeier/electronics-stack/scripts/design_pipeline.py': [Errno 2] No such f |
| Voltage_divider_12V_to_3.3V_using_two_1%_resistors | synthetic | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.02 | 193.7 | PIPELINE_RC=2: /usr/bin/python3: can't open file '/home/reidsurmeier/electronics-stack/scripts/design_pipeline.py': [Errno 2] No such f |
