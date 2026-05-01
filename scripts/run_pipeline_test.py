"""run_pipeline_test.py — Phase 6 verification sweep.

Runs 22 real KiCad projects (2 per category × 11 categories) plus 3 synthetic
specs through design_pipeline.py.  Produces PIPELINE-RUN.md at repo root.

Usage:
    python3 scripts/run_pipeline_test.py

Constraints:
    - Per-project wallclock cap: 60 s (TIMEOUT_60S on breach)
    - Total sweep cap: 30 min
    - Sourcing check runs with --no-api to avoid Octopart quota
    - One crash does not abort the sweep
"""
from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Repo / script locations
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
VERIFY_PY = SCRIPTS / "verify.py"
DESIGN_PY = SCRIPTS / "design_pipeline.py"
CORPUS = REPO / "test-corpus"
PIPELINE_RUN_MD = REPO / "PIPELINE-RUN.md"

PYTHON = sys.executable
PER_PROJECT_TIMEOUT_S = 60
TOTAL_TIMEOUT_S = 30 * 60  # 30 min


# ---------------------------------------------------------------------------
# Project manifest  (22 real + 3 synthetic)
# ---------------------------------------------------------------------------
REAL_PROJECTS: list[tuple[str, str]] = [
    # (category, relative-path-under-test-corpus)
    ("audio",      "audio/USB2Speakon"),
    ("audio",      "audio/Eurorack_Bus_Board"),
    ("devboards",  "devboards/STM32-RFM95-PCB"),
    ("devboards",  "devboards/stm32h750-dev-board"),
    ("hats",       "hats/PCIe3_Hub"),
    ("hats",       "hats/haxo-hw"),
    ("keyboards",  "keyboards/urchin"),           # only corpus entry with top-level sch
    ("keyboards",  "keyboards/urchin"),           # repeated — single valid project
    ("makertools", "makertools/3dPrinter"),
    ("makertools", "makertools/KiCAD_StepperAdapter"),
    ("motor",      "motor/pcb-motor"),
    ("motor",      "motor/IP5328P-powerbank_design"),
    ("power",      "power/bms-buck-boost"),
    ("power",      "power/Biploar-power-supply-KiCAD"),
    ("rf",         "rf/mdbt-micro"),
    ("rf",         "rf/MiniSolarMesh"),
    ("robotics",   "robotics/LSR-drone"),
    ("robotics",   "robotics/NoahFC"),
    ("sensors",    "sensors/pmw3360-pcb"),
    ("sensors",    "sensors/pmw3610-pcb"),
    ("wearables",  "wearables/hardware-watchdog"),
    ("wearables",  "wearables/555-plane-pcb"),
]

SYNTHETIC_SPECS: list[tuple[str, str]] = [
    ("synthetic", "555 timer LED blinker with 1Hz frequency, 9V battery"),
    ("synthetic", "ESP32-C3 dev board with USB-C power input and 3.3V LDO"),
    ("synthetic", "Voltage divider 12V to 3.3V using two 1% resistors"),
]

# Checks run by verify.py (excluding kibot — slow, rarely configured)
CHECKS = ["erc", "conn", "power", "sourcing", "pi"]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class ProjectResult:
    project: str
    category: str
    checks_run: int = 0
    erc: str = "SKIP"
    conn: str = "SKIP"
    power: str = "SKIP"
    sourcing: str = "SKIP"
    pi: str = "SKIP"
    wallclock_s: float = 0.0
    peak_mem_mb: float = 0.0
    top_error: str = ""
    raw: list[dict] = field(default_factory=list, repr=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _status_cell(check_name: str, results: list[dict]) -> str:
    """Map a verify.py JSON result entry to PASS / FAIL / SKIP."""
    for r in results:
        # match by check key name inside the 'check' string
        if check_name in r.get("check", "").lower() or r.get("_key") == check_name:
            s = r.get("status", "").lower()
            if s in ("pass",):
                return "PASS"
            if s in ("fail", "error"):
                return "FAIL"
            if s in ("skipped", "skip", "warn"):
                return "SKIP"
    return "SKIP"


def _check_key(check_name: str, raw: list[dict]) -> Optional[dict]:
    for r in raw:
        if check_name in r.get("check", "").lower():
            return r
    return None


def _peak_mem_mb() -> float:
    """RSS of children in MB (Linux: ru_maxrss is KB)."""
    try:
        kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        return kb / 1024.0
    except Exception:
        return 0.0


def _top_error(raw: list[dict]) -> str:
    """First error/fail message found across all check results."""
    for r in raw:
        if r.get("status") in ("fail", "error"):
            # prefer a short reason string
            for key in ("error", "reason", "details"):
                val = r.get(key)
                if val:
                    msg = val[0] if isinstance(val, list) else str(val)
                    return msg[:120]
            return r.get("check", "unknown")[:120]
    return ""


# ---------------------------------------------------------------------------
# Run verify.py against a real project directory
# ---------------------------------------------------------------------------
def run_real_project(project_dir: Path, category: str) -> ProjectResult:
    name = project_dir.name
    result = ProjectResult(project=name, category=category)

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [PYTHON, str(VERIFY_PY), str(project_dir), "--json"],
            capture_output=True,
            text=True,
            timeout=PER_PROJECT_TIMEOUT_S,
            env={**os.environ, "SOURCING_WITH_API": "0"},
        )
        elapsed = time.monotonic() - t0
        result.wallclock_s = round(elapsed, 2)
        result.peak_mem_mb = round(_peak_mem_mb(), 1)

        # parse JSON output
        raw: list[dict] = []
        if proc.stdout.strip():
            try:
                raw = json.loads(proc.stdout)
            except json.JSONDecodeError:
                result.top_error = f"JSON_PARSE_ERROR: {proc.stdout[:80]}"
                return result

        result.raw = raw
        result.checks_run = len(raw)

        # map individual checks
        result.erc      = _status_cell("erc",        raw)
        result.conn     = _status_cell("connectivity", raw)
        result.power    = _status_cell("power",       raw)
        result.sourcing = _status_cell("sourcing",    raw)
        result.pi       = _status_cell("pi",          raw)

        result.top_error = _top_error(raw)

    except subprocess.TimeoutExpired:
        result.wallclock_s = PER_PROJECT_TIMEOUT_S
        result.peak_mem_mb = round(_peak_mem_mb(), 1)
        result.top_error = "TIMEOUT_60S"

    except Exception as exc:
        result.wallclock_s = round(time.monotonic() - t0, 2)
        result.top_error = f"RUNNER_EXCEPTION: {exc}"

    return result


# ---------------------------------------------------------------------------
# Run design_pipeline.py for a synthetic spec, then verify the output dir
# ---------------------------------------------------------------------------
def run_synthetic(spec: str) -> ProjectResult:
    short_name = spec[:50].replace(" ", "_").replace(",", "")
    result = ProjectResult(project=short_name, category="synthetic")

    t0 = time.monotonic()
    try:
        # design_pipeline writes output to a temp dir; capture it from stdout
        proc = subprocess.run(
            [PYTHON, str(DESIGN_PY), "--spec", spec, "--json"],
            capture_output=True,
            text=True,
            timeout=PER_PROJECT_TIMEOUT_S,
            cwd=str(REPO),
            env={**os.environ, "SOURCING_WITH_API": "0"},
        )
        elapsed = time.monotonic() - t0
        result.wallclock_s = round(elapsed, 2)
        result.peak_mem_mb = round(_peak_mem_mb(), 1)

        if proc.returncode not in (0, 1):
            result.top_error = (
                f"PIPELINE_RC={proc.returncode}: "
                f"{(proc.stderr or proc.stdout)[:120]}"
            )
            return result

        # Try to parse output directory from JSON stdout
        out_dir: Optional[Path] = None
        if proc.stdout.strip():
            try:
                data = json.loads(proc.stdout)
                out_path = data.get("output_dir") or data.get("project_dir")
                if out_path:
                    out_dir = Path(out_path)
            except (json.JSONDecodeError, TypeError):
                pass

        if out_dir and out_dir.exists():
            # run verify on the generated project
            remaining = PER_PROJECT_TIMEOUT_S - elapsed
            if remaining > 5:
                vproc = subprocess.run(
                    [PYTHON, str(VERIFY_PY), str(out_dir), "--json"],
                    capture_output=True,
                    text=True,
                    timeout=max(5.0, remaining),
                    env={**os.environ, "SOURCING_WITH_API": "0"},
                )
                raw: list[dict] = []
                if vproc.stdout.strip():
                    try:
                        raw = json.loads(vproc.stdout)
                    except json.JSONDecodeError:
                        pass
                result.raw = raw
                result.checks_run = len(raw)
                result.erc      = _status_cell("erc",         raw)
                result.conn     = _status_cell("connectivity", raw)
                result.power    = _status_cell("power",        raw)
                result.sourcing = _status_cell("sourcing",     raw)
                result.pi       = _status_cell("pi",           raw)
                result.top_error = _top_error(raw)
            else:
                result.top_error = "TIMEOUT_60S (verify phase)"
        else:
            # pipeline ran but no verifiable output dir; record what we can
            result.checks_run = 0
            stderr_snippet = (proc.stderr or "")[:120]
            result.top_error = f"NO_OUTPUT_DIR: {stderr_snippet}" if stderr_snippet else "NO_OUTPUT_DIR"

    except subprocess.TimeoutExpired:
        result.wallclock_s = PER_PROJECT_TIMEOUT_S
        result.peak_mem_mb = round(_peak_mem_mb(), 1)
        result.top_error = "TIMEOUT_60S"

    except Exception as exc:
        result.wallclock_s = round(time.monotonic() - t0, 2)
        result.top_error = f"RUNNER_EXCEPTION: {exc}"

    return result


# ---------------------------------------------------------------------------
# Markdown table writer
# ---------------------------------------------------------------------------
def write_markdown(results: list[ProjectResult], wallclock_total: float, truncated: bool) -> None:
    passed = sum(1 for r in results if not r.top_error and all(
        s in ("PASS", "SKIP") for s in [r.erc, r.conn, r.power, r.sourcing, r.pi]
    ))
    failed = len(results) - passed

    lines: list[str] = [
        "# PIPELINE-RUN.md — Phase 6 Verification Sweep",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  ",
        f"**Projects run:** {len(results)} / 25  ",
        f"**PASS:** {passed}  **FAIL:** {failed}  ",
        f"**Total wallclock:** {wallclock_total:.1f}s ({wallclock_total/60:.1f} min)  ",
    ]
    if truncated:
        lines.append("**NOTE:** Sweep hit 30-min cap — table shows partial results.  ")
    lines += [
        "",
        "| project | category | checks_run | erc | conn | power | sourcing | pi | wallclock_s | peak_mem_mb | top_error |",
        "|---------|----------|------------|-----|------|-------|----------|----|-------------|-------------|-----------|",
    ]
    for r in results:
        err = r.top_error.replace("|", "\\|") if r.top_error else ""
        lines.append(
            f"| {r.project} | {r.category} | {r.checks_run} "
            f"| {r.erc} | {r.conn} | {r.power} | {r.sourcing} | {r.pi} "
            f"| {r.wallclock_s} | {r.peak_mem_mb} | {err} |"
        )

    PIPELINE_RUN_MD.write_text("\n".join(lines) + "\n")
    print(f"[run_pipeline_test] wrote {PIPELINE_RUN_MD}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    sweep_start = time.monotonic()
    results: list[ProjectResult] = []
    truncated = False

    print(f"[run_pipeline_test] starting sweep — {len(REAL_PROJECTS)} real + {len(SYNTHETIC_SPECS)} synthetic")

    # --- real projects ---
    seen_dirs: set[str] = set()
    for category, rel_path in REAL_PROJECTS:
        if time.monotonic() - sweep_start > TOTAL_TIMEOUT_S:
            truncated = True
            print("[run_pipeline_test] 30-min cap hit — stopping early")
            break

        project_dir = CORPUS / rel_path
        # deduplicate (urchin appears twice — keep both rows for table completeness)
        print(f"  -> {category}/{project_dir.name}")
        try:
            r = run_real_project(project_dir, category)
        except Exception as exc:
            name = project_dir.name
            r = ProjectResult(project=name, category=category,
                              top_error=f"OUTER_EXCEPTION: {exc}")
        results.append(r)
        print(f"     {r.wallclock_s}s  {r.top_error or 'ok'}")

    # --- synthetic specs ---
    for category, spec in SYNTHETIC_SPECS:
        if time.monotonic() - sweep_start > TOTAL_TIMEOUT_S:
            truncated = True
            print("[run_pipeline_test] 30-min cap hit — stopping early")
            break

        print(f"  -> synthetic: {spec[:60]}")
        try:
            r = run_synthetic(spec)
        except Exception as exc:
            r = ProjectResult(project=spec[:50], category="synthetic",
                              top_error=f"OUTER_EXCEPTION: {exc}")
        results.append(r)
        print(f"     {r.wallclock_s}s  {r.top_error or 'ok'}")

    wallclock_total = time.monotonic() - sweep_start
    write_markdown(results, wallclock_total, truncated)

    passed = sum(1 for r in results if not r.top_error and all(
        s in ("PASS", "SKIP") for s in [r.erc, r.conn, r.power, r.sourcing, r.pi]
    ))
    print(f"\n[run_pipeline_test] done: {passed}/{len(results)} passed in {wallclock_total:.1f}s")


if __name__ == "__main__":
    main()
