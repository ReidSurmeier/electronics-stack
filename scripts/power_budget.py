"""Power budget walker.

Reads a YAML rail-load spec next to the schematic (e.g. CM5_Vision_Workstation/power_budget.yaml):

    rails:
      "+12V":
        source: "RD-85A V2"
        capacity_w: 48
        loads:
          U2_carrier: { typ_w: 18, max_w: 22 }
          DS1_monitor: { typ_w: 25, max_w: 40 }
      "+5V":
        source: "RD-85A V1"
        capacity_w: 40
        loads:
          U20_hub: { typ_w: 4 }

Computes rail headroom under typical and worst-case loads.
"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml


def load_budget(path: str | Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def analyze(budget: dict) -> list[dict]:
    findings = []
    for rail_name, rail in budget.get("rails", {}).items():
        cap_w = float(rail.get("capacity_w", 0))
        loads = rail.get("loads", {})
        typ_total = sum(float(v.get("typ_w", 0)) for v in loads.values())
        max_total = sum(float(v.get("max_w", v.get("typ_w", 0))) for v in loads.values())
        headroom_typ = cap_w - typ_total
        headroom_max = cap_w - max_total
        severity = "PASS"
        if headroom_max < 0:
            severity = "FAIL"
        elif headroom_max < 0.1 * cap_w:
            severity = "RISK"
        elif headroom_typ < 0.15 * cap_w:
            severity = "TIGHT"
        findings.append({
            "rail": rail_name,
            "source": rail.get("source", "?"),
            "capacity_w": cap_w,
            "typ_load_w": typ_total,
            "max_load_w": max_total,
            "headroom_typ_w": headroom_typ,
            "headroom_max_w": headroom_max,
            "load_count": len(loads),
            "severity": severity,
        })
    return findings


def report(findings: list[dict]) -> str:
    lines = ["Power budget analysis:"]
    for f in findings:
        lines.append(
            f"  [{f['severity']:5s}] {f['rail']:>10s}  cap={f['capacity_w']:6.1f}W  "
            f"typ={f['typ_load_w']:6.1f}W  max={f['max_load_w']:6.1f}W  "
            f"headroom={f['headroom_max_w']:+6.1f}W  ({f['load_count']} loads on {f['source']})"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: power_budget.py <power_budget.yaml>")
        sys.exit(1)
    findings = analyze(load_budget(sys.argv[1]))
    print(report(findings))
    sys.exit(1 if any(f["severity"] in ("FAIL", "RISK") for f in findings) else 0)
