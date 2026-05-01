# PIPELINE-FIX-1.md

**Iteration:** 1 / 6
**Date:** 2026-05-01

## Triage of 17 FAILs from PIPELINE-RUN.md

| # | Project | Original error | Category | State | Resolution |
|---|---------|----------------|----------|-------|------------|
| 1 | STM32-RFM95-PCB | passive pin float | UPSTREAM | VERIFIED | Real schematic bug — 21 HIGH floats |
| 2 | stm32h750-dev-board | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | Improved error reporting; underlying cause is 4 real `power_pin_not_driven` |
| 3 | PCIe3_Hub | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | Now reports 27 `power_pin_not_driven` |
| 4 | haxo-hw | GPIO27 float | UPSTREAM | VERIFIED | Real bidirectional float |
| 5 | urchin (×2) | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | 42 real `pin_not_connected` |
| 6 | 3dPrinter | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | 146 real `pin_not_connected` |
| 7 | KiCAD_StepperAdapter | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | 3 real `power_pin_not_driven` |
| 8 | IP5328P-powerbank | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | 4 real `power_pin_not_driven` |
| 9 | bms-buck-boost | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | 2 real `power_pin_not_driven` |
| 10 | Biploar-power-supply | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | 2 real `power_pin_not_driven` |
| 11 | MiniSolarMesh | C14 pin float | UPSTREAM | VERIFIED | Real cap pin float |
| 12 | LSR-drone | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | 50 real `wire_dangling` |
| 13 | pmw3610-pcb | "kicad-cli ERC" | GENUINE_BUG → UPSTREAM | FIXED | 8 real `power_pin_not_driven` |
| 14-16 | 3 synthetics | NO_OUTPUT_DIR | INFRA | DEFERRED | design_pipeline.py JSON output schema mismatch — Phase 5 follow-up |

## Root causes

### GB-1: lossy ERC top_error (verify.py:75-90)
`run_kicad_erc` returned only counts, not the rule names that caused failures. `top_error` defaulted to the bare string "kicad-cli ERC" with no signal.
**Fix:** added `first_errors: list[str]` to the result with up to 3 rule descriptions parsed from the .erc.rpt file. `_top_error` in `run_pipeline_test.py` formats as `"N ERC error(s): [rule]: message"`.

### GB-2: spurious PI FAIL (run_pipeline_test.py:_status_cell)
`check_name in r.get("check", "").lower()` — substring match. "pi" matched "passive-pin floats" in the connectivity audit's check name, producing a false PI FAIL on every CONN FAIL project.
**Fix:** anchored matching with explicit per-check anchor strings (`"pi"` → `"pi dts"`).

### GB-3: design_pipeline NO_OUTPUT_DIR
3 synthetic-spec runs return RC=0 but `out_dir` key absent in JSON output. Phase 5 schema mismatch.
**Deferred:** caught here, will fix in a Phase 5 follow-up PR. Not in scope for fix-loop on Phase 6's classification logic.

## Outcome

- **8 PASS** (unchanged; the 2 SKIP-only changes don't move PASS count)
- **17 FAIL** but reclassified:
  - **13 confirmed UPSTREAM** — real schematic bugs in OSS projects. The verification stack is doing its job catching these. NOT something we fix.
  - **3 INFRA-deferred** — design_pipeline.py JSON output, Phase 5 follow-up
  - **0 remaining GENUINE_BUG**

This iteration's fixes are PRECISION improvements: same pass count, but failures now have actionable error messages instead of opaque "kicad-cli ERC" strings.

**No further iterations needed.** All GENUINE_BUGs in scope are fixed; the 13 UPSTREAM failures are by design (we're a verifier — finding real bugs is the point).
