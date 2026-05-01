"""Connectivity audit — catches the bugs ERC misses.

The KiCad 9 ERC pass-through that bit us: black-box symbols whose pins are typed
`passive` don't trigger pin_not_driven errors even when they're floating. So
ERC reports 0 errors but huge interface sections (LCD eDP cable, BTB connectors,
power distribution headers) are completely unwired.

This audit walks every (instance, pin) tuple and:
  1. Asks: is this pin coordinate covered by a label or a wire endpoint?
  2. If not: is it covered by a no_connect marker?
  3. If neither: it's floating (regardless of pin etype).

Reports HIGH-severity floats grouped by instance.
"""
from __future__ import annotations
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sch_parser import parse_schematic, get_symbol_def_for_instance, Schematic, SymbolInstance


SNAP = 0.01  # mm tolerance


def near(a: tuple[float, float], b: tuple[float, float], tol: float = SNAP) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) < tol


def pin_world_coord(inst: SymbolInstance, pin_at: tuple[float, float, float]) -> tuple[float, float]:
    """Translate a pin's symbol-local coordinate to schematic world coordinate.
    KiCad symbol Y axis is inverted relative to schematic Y (.kicad_sym is y-up,
    schematic is y-down)."""
    px, py, _ = pin_at
    # KiCad inverts Y when placing: world = inst + (px, -py) (no rotation handled — TODO)
    return (inst.at[0] + px, inst.at[1] - py)


def audit(sch: Schematic) -> list[dict]:
    """Return a list of finding dicts."""
    findings: list[dict] = []
    label_pts = [(l[1], l[2]) for l in sch.labels]
    wire_endpoints: list[tuple[float, float]] = []
    for w in sch.wires:
        if w:
            wire_endpoints.append(w[0])
            wire_endpoints.append(w[-1])
            wire_endpoints.extend(w)  # midpoints too
    nc_pts = sch.no_connects

    for inst in sch.instances:
        sd = get_symbol_def_for_instance(sch, inst)
        if not sd:
            continue
        for pin in sd.pins:
            wc = pin_world_coord(inst, pin.at)
            covered_by_label = any(near(wc, lp) for lp in label_pts)
            covered_by_wire = any(near(wc, ep) for ep in wire_endpoints)
            covered_by_nc = any(near(wc, np_) for np_ in nc_pts)
            if covered_by_label or covered_by_wire or covered_by_nc:
                continue
            findings.append({
                "severity": "HIGH" if pin.etype in ("power_in", "power_out", "input", "output") else "MEDIUM",
                "kind": "floating_pin",
                "refdes": inst.refdes,
                "lib_id": inst.lib_id,
                "value": inst.value,
                "pin_number": pin.number,
                "pin_name": pin.name,
                "pin_etype": pin.etype,
                "world_coord": wc,
                "note": f"{inst.refdes} pin {pin.number} '{pin.name}' ({pin.etype}) at {wc} has no label, wire, or no_connect.",
            })
    return findings


def report(findings: list[dict]) -> str:
    if not findings:
        return "Connectivity audit: PASS — every pin is labeled, wired, or NC.\n"
    lines = []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        grouped[f["refdes"]].append(f)
    high = sum(1 for f in findings if f["severity"] == "HIGH")
    med = sum(1 for f in findings if f["severity"] == "MEDIUM")
    lines.append(f"Connectivity audit: {len(findings)} floating pins ({high} HIGH, {med} MEDIUM)")
    for refdes, items in sorted(grouped.items()):
        lines.append(f"\n[{refdes}] {items[0]['lib_id']} \"{items[0]['value']}\"")
        for it in items:
            lines.append(f"  {it['severity']:6s} pin {it['pin_number']:>4s} {it['pin_name']:<30s} ({it['pin_etype']})")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: connectivity_audit.py <schematic.kicad_sch>")
        sys.exit(1)
    sch = parse_schematic(sys.argv[1])
    findings = audit(sch)
    print(report(findings))
    sys.exit(1 if any(f["severity"] == "HIGH" for f in findings) else 0)
