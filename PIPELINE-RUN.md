# PIPELINE-RUN.md — Phase 6 Verification Sweep

**Date:** 2026-05-01 15:45:41 UTC  
**Projects run:** 25 / 25  
**PASS:** 8  **FAIL:** 17  
**Total wallclock:** 10.6s (0.2 min)  

| project | category | checks_run | erc | conn | power | sourcing | pi | wallclock_s | peak_mem_mb | top_error |
|---------|----------|------------|-----|------|-------|----------|----|-------------|-------------|-----------|
| USB2Speakon | audio | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.25 | 60.9 |  |
| Eurorack_Bus_Board | audio | 6 | PASS | PASS | SKIP | SKIP | SKIP | 0.59 | 188.4 |  |
| STM32-RFM95-PCB | devboards | 6 | PASS | FAIL | SKIP | SKIP | SKIP | 0.51 | 188.4 | U2 pin 9 'ANA' (passive) at (119.38, 80.00999999999999) has no label, wire, or no_connect. |
| stm32h750-dev-board | devboards | 6 | FAIL | FAIL | SKIP | SKIP | SKIP | 0.63 | 190.6 | 4 ERC error(s): [power_pin_not_driven]: Input Power pin not driven by any Output Power pins |
| PCIe3_Hub | hats | 6 | FAIL | FAIL | SKIP | SKIP | SKIP | 0.69 | 193.2 | 27 ERC error(s): [power_pin_not_driven]: Input Power pin not driven by any Output Power pins |
| haxo-hw | hats | 6 | PASS | FAIL | SKIP | SKIP | SKIP | 0.56 | 193.2 | J3 pin 13 'GPIO27' (bidirectional) at (222.25, 140.97) has no label, wire, or no_connect. |
| urchin | keyboards | 6 | FAIL | FAIL | SKIP | SKIP | SKIP | 0.54 | 193.2 | 42 ERC error(s): [pin_not_connected]: Pin not connected |
| urchin | keyboards | 6 | FAIL | FAIL | SKIP | SKIP | SKIP | 0.52 | 193.2 | 42 ERC error(s): [pin_not_connected]: Pin not connected |
| 3dPrinter | makertools | 6 | FAIL | FAIL | SKIP | SKIP | SKIP | 0.46 | 193.2 | 146 ERC error(s): [pin_not_connected]: Pin not connected |
| KiCAD_StepperAdapter | makertools | 6 | FAIL | PASS | SKIP | SKIP | SKIP | 0.47 | 193.2 | 3 ERC error(s): [power_pin_not_driven]: Input Power pin not driven by any Output Power pins |
| pcb-motor | motor | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.28 | 193.2 |  |
| IP5328P-powerbank_design | motor | 6 | FAIL | FAIL | SKIP | SKIP | SKIP | 0.68 | 193.2 | 4 ERC error(s): [power_pin_not_driven]: Input Power pin not driven by any Output Power pins |
| bms-buck-boost | power | 6 | FAIL | FAIL | SKIP | SKIP | SKIP | 0.53 | 193.2 | 2 ERC error(s): [power_pin_not_driven]: Input Power pin not driven by any Output Power pins |
| Biploar-power-supply-KiCAD | power | 6 | FAIL | PASS | SKIP | SKIP | SKIP | 0.5 | 193.2 | 2 ERC error(s): [power_pin_not_driven]: Input Power pin not driven by any Output Power pins |
| mdbt-micro | rf | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.25 | 193.2 |  |
| MiniSolarMesh | rf | 6 | PASS | FAIL | SKIP | SKIP | SKIP | 0.57 | 193.2 | C14 pin 2 '~' (passive) at (251.46, 193.04) has no label, wire, or no_connect. |
| LSR-drone | robotics | 6 | FAIL | PASS | SKIP | SKIP | SKIP | 0.54 | 193.2 | 50 ERC error(s): [wire_dangling]: Wires not connected to anything |
| NoahFC | robotics | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.25 | 193.2 |  |
| pmw3360-pcb | sensors | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.26 | 193.2 |  |
| pmw3610-pcb | sensors | 6 | FAIL | FAIL | SKIP | SKIP | SKIP | 0.49 | 193.2 | 8 ERC error(s): [power_pin_not_driven]: Input Power pin not driven by any Output Power pins |
| hardware-watchdog | wearables | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.25 | 193.2 |  |
| 555-plane-pcb | wearables | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.25 | 193.2 |  |
| 555_timer_LED_blinker_with_1Hz_frequency_9V_batte | synthetic | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.17 | 193.2 | NO_OUTPUT_DIR |
| ESP32-C3_dev_board_with_USB-C_power_input_and_3.3V | synthetic | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.18 | 193.2 | NO_OUTPUT_DIR |
| Voltage_divider_12V_to_3.3V_using_two_1%_resistors | synthetic | 0 | SKIP | SKIP | SKIP | SKIP | SKIP | 0.19 | 193.2 | NO_OUTPUT_DIR |
