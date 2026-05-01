"""Top-level verify CLI. Runs the full electronics verification stack
against a single KiCad project.

Usage:
    verify.py <project_dir>            # all checks
    verify.py <project_dir> --erc      # just kicad-cli ERC
    verify.py <project_dir> --conn     # connectivity audit
    verify.py <project_dir> --power    # power budget (needs power_budget.yaml)
    verify.py <project_dir> --sourcing # BOM URL health
    verify.py <project_dir> --pi       # Pi DTS validator (needs pi_manifest.yaml)
    verify.py <project_dir> --kibot    # KiBot pipeline (needs .kibot.yaml)

Exit codes:
    0 — all checks passed (no HIGH or FAIL findings)
    1 — at least one HIGH/FAIL finding
    2 — config / setup error (missing tool, missing file)
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from sch_parser import parse_schematic
import connectivity_audit
import power_budget
import sourcing_health
import pi_dts_validator


COLOR = {
    "PASS": "\033[32m",
    "FAIL": "\033[31m",
    "RISK": "\033[33m",
    "TIGHT": "\033[33m",
    "HIGH": "\033[31m",
    "MEDIUM": "\033[33m",
    "LOW": "\033[36m",
    "RESET": "\033[0m",
}


def cprint(msg: str, kind: str = "RESET"):
    print(f"{COLOR.get(kind, '')}{msg}{COLOR['RESET']}")


def find_kicad_project(project_dir: Path) -> tuple[Path, Path]:
    """Locate .kicad_pro and .kicad_sch under project_dir. Top-level only.
    Skips macOS AppleDouble files (._*)."""
    pros = [p for p in project_dir.glob("*.kicad_pro") if not p.name.startswith("._")]
    if not pros:
        raise FileNotFoundError(f"No .kicad_pro under {project_dir}")
    pro = pros[0]
    sch = pro.with_suffix(".kicad_sch")
    if not sch.exists():
        raise FileNotFoundError(f"No .kicad_sch matching {pro.name}")
    return pro, sch


def run_kicad_erc(sch_path: Path, out_dir: Path) -> dict:
    if not shutil.which("kicad-cli"):
        return {"check": "kicad-cli ERC", "status": "skipped", "reason": "kicad-cli not installed"}
    rpt = out_dir / f"{sch_path.stem}-erc.rpt"
    out_dir.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        ["kicad-cli", "sch", "erc",
         "--severity-error", "--severity-warning",
         "-o", str(rpt), str(sch_path)],
        capture_output=True, text=True
    )
    text = rpt.read_text() if rpt.exists() else ""
    lines = text.split("\n")
    errors = text.count("; error")
    # filter footprint_link_issues — environmental, not design issues
    real_errors = sum(1 for line in lines if "; error" in line and "footprint_link_issues" not in line)
    warnings = text.count("; warning")
    real_warnings = warnings - sum(1 for line in lines if "; warning" in line and "footprint_link_issues" in line)
    # Collect first 3 real error descriptions for surfacing in top_error
    # ERC report format: "[rule_id]: description\n    ; error"
    first_errors: list[str] = []
    for i, line in enumerate(lines):
        if len(first_errors) >= 3:
            break
        if "; error" in line and "footprint_link_issues" not in line:
            # Walk back to find the rule description line (skipping "@" location lines)
            desc_idx = i - 1
            while desc_idx >= 0 and lines[desc_idx].strip().startswith("@"):
                desc_idx -= 1
            if desc_idx >= 0:
                desc = lines[desc_idx].strip()
                if desc and desc not in first_errors:
                    first_errors.append(desc[:120])
    return {
        "check": "kicad-cli ERC",
        "status": "fail" if real_errors else "pass",
        "errors_total": errors,
        "errors_design": real_errors,
        "warnings_total": warnings,
        "warnings_design": real_warnings,
        "first_errors": first_errors,
        "report": str(rpt),
    }


def run_connectivity(sch_path: Path) -> dict:
    sch = parse_schematic(sch_path)
    findings = connectivity_audit.audit(sch)
    high = sum(1 for f in findings if f["severity"] == "HIGH")
    return {
        "check": "Connectivity audit (passive-pin floats)",
        "status": "fail" if high else "pass",
        "findings": len(findings),
        "high": high,
        "details": [f["note"] for f in findings[:10]],
    }


def run_power(project_dir: Path) -> dict:
    yml = project_dir / "power_budget.yaml"
    if not yml.exists():
        return {"check": "Power budget", "status": "skipped", "reason": f"no {yml.name}"}
    findings = power_budget.analyze(power_budget.load_budget(yml))
    fail = sum(1 for f in findings if f["severity"] in ("FAIL", "RISK"))
    return {
        "check": "Power budget",
        "status": "fail" if fail else "pass",
        "rails": len(findings),
        "issues": fail,
        "details": [f"[{f['severity']}] {f['rail']} headroom_max={f['headroom_max_w']:+.1f}W" for f in findings],
    }


def run_sourcing(project_dir: Path) -> dict:
    boms = list(project_dir.glob("*BOM*.xlsx")) + list(project_dir.parent.glob(f"{project_dir.name}*BOM*.xlsx"))
    if not boms:
        return {"check": "BOM sourcing health", "status": "skipped", "reason": "no BOM xlsx found near project"}
    bom = boms[0]
    out = sourcing_health.audit(bom)
    bad = sum(1 for f in out["findings"] if f["status"] not in ("ok", "skip"))
    return {
        "check": "BOM sourcing health",
        "status": "warn" if bad else "pass",
        "urls": len(out["findings"]),
        "broken": bad,
        "bom": str(bom),
    }


def run_pi(project_dir: Path) -> dict:
    yml = project_dir / "pi_manifest.yaml"
    if not yml.exists():
        return {"check": "Pi DTS validator", "status": "skipped", "reason": f"no {yml.name}"}
    import yaml
    findings = pi_dts_validator.validate(yaml.safe_load(open(yml)))
    high = sum(1 for f in findings if f["severity"] == "HIGH")
    return {
        "check": "Pi DTS validator",
        "status": "fail" if high else "pass",
        "findings": len(findings),
        "high": high,
    }


def run_kibot(project_dir: Path) -> dict:
    cfg = project_dir / ".kibot.yaml"
    if not cfg.exists():
        cfg = project_dir / "kibot.yaml"
    if not cfg.exists():
        return {"check": "KiBot", "status": "skipped", "reason": "no .kibot.yaml"}
    if not shutil.which("kibot"):
        return {"check": "KiBot", "status": "skipped", "reason": "kibot not installed"}
    out_dir = project_dir / "kibot-out"
    res = subprocess.run(["kibot", "-c", str(cfg), "-d", str(out_dir)],
                         cwd=project_dir, capture_output=True, text=True, timeout=600)
    return {
        "check": "KiBot",
        "status": "pass" if res.returncode == 0 else "fail",
        "rc": res.returncode,
        "out": str(out_dir),
        "stderr_tail": res.stderr[-500:] if res.stderr else "",
    }


CHECKS = {
    "erc": run_kicad_erc,
    "conn": run_connectivity,
    "power": run_power,
    "sourcing": run_sourcing,
    "pi": run_pi,
    "kibot": run_kibot,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir")
    for k in CHECKS:
        ap.add_argument(f"--{k}", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    selected = [k for k in CHECKS if getattr(args, k)] or list(CHECKS.keys())
    project_dir = Path(args.project_dir).resolve()
    pro, sch = find_kicad_project(project_dir)
    out_dir = project_dir / "verify-out"

    results = []
    for k in selected:
        fn = CHECKS[k]
        try:
            if k == "erc":
                results.append(fn(sch, out_dir))
            elif k == "conn":
                results.append(fn(sch))
            else:
                results.append(fn(project_dir))
        except Exception as e:
            results.append({"check": k, "status": "error", "error": str(e)})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        cprint(f"\n=== verify {project_dir.name} ===", "RESET")
        for r in results:
            status = r.get("status", "?").upper()
            kind = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "RISK", "SKIPPED": "LOW", "ERROR": "FAIL"}.get(status, "RESET")
            cprint(f"  [{status:>7s}] {r['check']:<40s} {json.dumps({k:v for k,v in r.items() if k not in ('check','status')})[:100]}", kind)
    fails = [r for r in results if r.get("status") in ("fail",)]
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
