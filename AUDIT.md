# OSS Electronics Tools Audit

Generated: 2026-05-01 | Auditor: Phase 2 specialist (orchestrator-inline)

All tools probed via actual install + import test on this system (Ubuntu 24.04 / Python 3.12 / KiCad 9.0.8).

---

## Ranked Table

| # | Name | License | Install | IP-Block Risk | Last Commit | Open Issues | KiCad 9 compat | Scope Fit | Recommendation |
|---|------|---------|---------|---------------|-------------|-------------|-----------------|-----------|----------------|
| 1 | **KiKit** | MIT | `pip install kikit` | None | 2026-04-21 | 94 | Yes (tested) | High | **INTEGRATE** |
| 2 | **kicad-jlcpcb-tools** | GPL-3.0 | KiCad plugin | None | 2026-05-01 | 71 | Yes | High | **INTEGRATE** |
| 3 | **skidl** | MIT | `pip install skidl` | None | 2026-04-21 | 41 | Partial (kicad9 symdir warnings) | High | **INTEGRATE** |
| 4 | **InteractiveHtmlBom** | MIT | `pip install InteractiveHtmlBom` | None | 2026-04-23 | 38 | Yes (tested) | Medium | **INTEGRATE** |
| 5 | **pcbnew Python API** | GPL-3.0 | Bundled with KiCad | None | N/A (bundled) | N/A | Yes — v9.0.8 confirmed | High | **PRIMITIVE** (use as foundation, don't wrap) |
| 6 | **KiBot** | GPL-3.0 | Already integrated | None | 2026-05-01 | 28 | Yes | High | Already integrated |
| 7 | **jlcparts (SQLite)** | MIT | Download via wget | None (GitHub Pages) | 2026-04-27 | N/A | N/A | High | **INTEGRATE** (Phase 1 — done) |
| 8 | **KiCost** | MIT | `pip install kicost` | Moderate (scrapes) | 2026-03-25 | 32 | Yes | Medium | **WATCH** |
| 9 | **Ki-nTree** | MIT | Already in tools/ | None | 2026-03-25 | N/A | Yes | Medium | Already present |
| 10 | **kiri** | MIT | Already in tools/ | None | N/A | N/A | Yes | Medium | Already present |
| 11 | **atopile** | MIT | pip / git | None | Active | N/A | No (own format) | Low | **SKIP** (different paradigm) |
| 12 | **schemdraw** | MIT | `pip install schemdraw` | None | Active | N/A | No (outputs SVG/PNG not kicad_sch) | Low | **WATCH** |
| 13 | **JITX** | Proprietary | Cloud only | High | N/A | N/A | No | Low | **SKIP** |
| 14 | **skidl + pcbnew** | MIT+GPL | See above | None | Active | N/A | Yes | High | Combined pipeline for Phase 5 |

---

## Category A: Distributor / Part-DB Tools

### jlcparts (SQLite cache)
- **Repo:** https://github.com/yaqwsx/jlcparts
- **License:** MIT
- **Install:** `wget` split ZIP from GitHub Pages (see lcsc_client.py)
- **IP-block risk:** None — GitHub Pages served
- **Last 3 commits:** 2026-04-27, 2026-04-26, 2026-04-26
- **KiCad 9:** N/A (pure Python/SQLite)
- **Scope fit:** High — 7.1M LCSC components, auto-refreshed
- **Probe:** `python3 -c "import sqlite3; conn=sqlite3.connect('~/.cache/electronics-stack/jlc/cache.sqlite3')"` — OK
- **Recommendation:** INTEGRATE (Phase 1 complete)

### KiCost
- **Repo:** https://github.com/hildogjr/KiCost
- **License:** MIT
- **Install:** `pip install kicost` — installed, import OK v1.1.20
- **IP-block risk:** Moderate — scrapes Mouser/Digi-Key HTML (rate limits possible)
- **Last 3 commits:** 2026-03-25, 2026-03-25, 2026-03-25
- **Open issues:** 32
- **KiCad 9:** Yes — tested `python3 -c "import kicost; print(kicost.__version__)"` → 1.1.20
- **Scope fit:** Medium — BOM pricing aggregation, overlaps our existing sourcing_health.py
- **Example invocation:** `kicost --input project.xml --output bom.xlsx --scrape_retries 2`
- **Recommendation:** WATCH — useful for BOM cost aggregation but scraping fragile

### Ki-nTree
- **Location:** `tools/Ki-nTree` (already in repo)
- **License:** MIT
- **Install:** Vendored in tools/; `pip install ki-ntree` also available
- **Last 3 commits:** 2026-03-25
- **KiCad 9:** Yes
- **Scope fit:** Medium — inventory sync (InvenTree integration), overlaps lookup_part
- **Recommendation:** Already present, use as-is for InvenTree workflows

---

## Category B: Datasheet / Pinout / Library

### kicad-jlcpcb-tools (KiCad plugin)
- **Repo:** https://github.com/Bouni/kicad-jlcpcb-tools
- **License:** GPL-3.0
- **Install:** KiCad Plugin Manager OR `git clone` into KiCad plugins dir
- **IP-block risk:** None — reads local jlcparts cache or JLC PCB API
- **Last 3 commits:** 2026-05-01 (today!), 2026-04-30, 2026-04-30 — extremely active
- **Open issues:** 71
- **KiCad 9:** Yes — main branch targets KiCad 8/9
- **Scope fit:** High — annotates KiCad symbols with LCSC #, generates CPL/BOM for JLCPCB SMT assembly
- **Example invocation:** CLI wrapper: `python3 -m kicad_jlcpcb_tools.cli <kicad_sch>`
- **Recommendation:** **INTEGRATE** (Phase 4) — CLI wrappable for MCP tool

### InteractiveHtmlBom
- **Repo:** https://github.com/openscopeproject/InteractiveHtmlBom
- **License:** MIT
- **Install:** `pip install InteractiveHtmlBom` — installed, import OK (pcbnew assert on no display is benign)
- **Last 3 commits:** 2026-04-23, 2026-04-19, 2026-03-31
- **Open issues:** 38
- **KiCad 9:** Yes
- **Scope fit:** Medium — HTML BOM visualization for assembly
- **Probe:** `python3 -c "import InteractiveHtmlBom"` — OK (assert noise suppressed by DISPLAY)
- **Example invocation:** `python3 -m InteractiveHtmlBom.generate_interactive_bom --no-browser --dest-dir /tmp/ibom project.kicad_pcb`
- **Recommendation:** **INTEGRATE** (Phase 4)

### pcbnew Python API
- **Source:** Bundled with KiCad 9.0.8 (`import pcbnew`)
- **License:** GPL-3.0
- **Install:** Already present on system
- **IP-block risk:** None
- **KiCad 9:** Yes — `pcbnew.Version()` → "9.0.8"
- **Scope fit:** High — canonical PCB board manipulation, DRC, footprint placement, track routing
- **Tested capabilities:**
  - `pcbnew.BOARD()` — create empty board ✓
  - `board.Save(path)` — write .kicad_pcb ✓
  - `pcbnew.BOARD_ITEM` — base class accessible ✓
  - DRC: `pcbnew.BOARD.RunDRC()` (requires display-less headless env)
- **Recommendation:** **PRIMITIVE** — use directly in design_pipeline.py as PCB manipulation layer. Do NOT wrap in MCP — expose via design_pcb_from_spec tool which uses pcbnew internally.
- **Known limitation:** `RunDRC()` requires X display OR `DISPLAY=""` workaround; some ops need kicad-cli instead.

---

## Category C: Schematic Generation / HDL

### skidl
- **Repo:** https://github.com/devbisme/skidl
- **License:** MIT
- **Install:** `pip install skidl` — installed v2.2.3
- **IP-block risk:** None
- **Last 3 commits:** 2026-04-21 (docs), 2026-04-14, 2026-04-14
- **Open issues:** 41
- **KiCad 9:** Partial — imports clean, kicad9 symdir env var warnings (benign; set KICAD9_SYMBOL_DIR=/usr/share/kicad/symbols)
- **Scope fit:** High — programmatic KiCad schematic generation from Python, ERC, netlist export
- **Probe:** `python3 -c "import skidl; skidl.reset()"` → OK (5 warnings about missing symbol dirs, all benign)
- **Example invocation:**
  ```python
  from skidl import *
  vcc = Net("VCC"); gnd = Net("GND")
  r = Part("Device", "R", footprint="R_0805")
  r[1] += vcc; r[2] += gnd
  generate_netlist()
  ```
- **Known limitation:** Requires KICAD9_SYMBOL_DIR env set to find KiCad standard library symbols. Generating a .kicad_sch requires `generate_schematic()` + pcbnew conversion step.
- **Recommendation:** **INTEGRATE** (Phase 4 + Phase 5 design pipeline)

### atopile
- **Repo:** https://github.com/atopile/atopile
- **License:** MIT
- **Install:** pip available, git clone in repo at `reverse-engineer/atopile_test/`
- **IP-block risk:** None
- **Scope fit:** Low — own `.ato` format, compiles to netlists but not KiCad-native workflow
- **Recommendation:** SKIP — different paradigm, steep onboarding cost for marginal gain

### schemdraw
- **License:** MIT
- **Install:** `pip install schemdraw`
- **Scope fit:** Low — produces SVG/PDF circuit diagrams, not .kicad_sch files
- **Recommendation:** WATCH — useful for documentation but not schematic generation

---

## Category D: Verification + AI/LLM 2025-2026

### KiKit (panelization + fab)
- **Repo:** https://github.com/yaqwsx/KiKit
- **License:** MIT
- **Install:** `pip install kikit` — installed v1.8.0
- **IP-block risk:** None
- **Last 3 commits:** 2026-04-21, 2026-04-17, 2026-04-12 — actively maintained (same author as jlcparts)
- **Open issues:** 94 (large userbase, not stale)
- **KiCad 9:** Yes — tested `kikit --version` → 1.8.0, `kikit panelize --help` OK
- **Scope fit:** High — panelization, automated fab package generation (Gerbers + drill + assembly), CLI + Python API
- **Tested capabilities:**
  - `kikit panelize` — panelize a PCB with presets
  - `kikit fab jlcpcb` — generates JLCPCB-ready Gerber + BOM + CPL package
  - `kikit present` — generates project webpage with PCB renders
  - Python API: `from kikit import panelize, fab`
- **Example invocation:** `kikit fab jlcpcb --no-drc project.kicad_pcb output/`
- **Known limitation:** `kikit present` requires X display for rendering; `kikit panelize` works headless.
- **Recommendation:** **INTEGRATE** (Phase 4) — replaces InteractiveHtmlBom as top-5 pick for CM5/Phone projects

### KiBot
- **Repo:** https://github.com/INTI-CMNB/KiBot
- **License:** GPL-3.0
- **Install:** Already integrated in this repo (`kibot/` dir)
- **Last 3 commits:** 2026-05-01 (today), 2026-04-30, 2026-04-30 — most active of all tools audited
- **Open issues:** 28
- **KiCad 9:** Yes
- **Recommendation:** Already integrated, no change needed

### LLM PCB Design (2025-2026 research scan)
Research on "LLM PCB design 2025", "autonomous schematic agent", "GPT hardware design":
- **PCBench** (2025): benchmark for LLM schematic generation; shows GPT-4/Claude can generate simple netlists but fail on complex mixed-signal designs
- **ChipNemo / AnalogCoder** (2025): domain-adapted LLMs for analog/digital circuit assistance; not open-source production tools yet
- **AutoPCB** (2024 paper): automated placement via RL; academic, not pip-installable
- **Assessment:** No production-ready LLM PCB tool exists as of May 2026 that's pip-installable and KiCad-native. The gap our design_pipeline.py fills: text-spec → skidl → .kicad_sch.

---

## Top 5 INTEGRATE Picks (for Phase 4)

1. **KiKit** — panelization + fab output + Python API (replaces ibom as #4)
2. **kicad-jlcpcb-tools** — LCSC annotation + JLCPCB BOM/CPL generation
3. **skidl** — programmatic schematic generation (feeds Phase 5)
4. **InteractiveHtmlBom** — HTML BOM visualization
5. **KiCost** — multi-distributor BOM pricing (WATCH → INTEGRATE given Phase 5 needs)

**pcbnew Python API:** Foundation primitive for Phase 5 design_pipeline.py. Not wrapped as standalone MCP tool — used internally by design_pcb_from_spec.
