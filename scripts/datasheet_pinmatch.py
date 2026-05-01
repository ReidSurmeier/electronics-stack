"""Datasheet pin-cross-check.

Given a KiCad symbol library + a datasheet PDF, extract pin tables from the
PDF and fuzzy-match against the symbol's pin names. Flag mismatches.

Usage:
    datasheet_pinmatch.py <symbol_lib.kicad_sym> <symbol_name> <datasheet.pdf>

Catches issues like: WM8960 lib has pin 17 named "SCL" but datasheet calls it
"SCLK". Ships with a fuzzy-matcher that tolerates underscore/case/punctuation
differences.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

import pdfplumber
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).parent))
from sch_parser import load, find_all, sym_name, parse_pin


def normalize(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def extract_pins_from_pdf(pdf_path: str | Path, max_pages: int = 30) -> list[dict]:
    """Extract candidate (number, name) pin pairs from PDF tables.
    Heuristic — picks rows where one cell is a small integer (1-256) and another
    cell is a short uppercase string."""
    pins = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            tables = page.extract_tables()
            for table in tables or []:
                for row in table:
                    if not row:
                        continue
                    cells = [c.strip() if c else "" for c in row]
                    num_idx = None
                    name_idx = None
                    for ci, c in enumerate(cells):
                        if num_idx is None and re.fullmatch(r"\d{1,3}", c):
                            num_idx = ci
                        elif name_idx is None and re.fullmatch(r"[A-Z][A-Z0-9_/\-+]{0,30}", c):
                            name_idx = ci
                    if num_idx is not None and name_idx is not None and num_idx != name_idx:
                        pins.append({"number": cells[num_idx], "name": cells[name_idx], "page": i + 1})
    # dedupe by (number, name)
    seen = set()
    uniq = []
    for p in pins:
        key = (p["number"], p["name"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def get_symbol_pins(sym_lib_path: str | Path, sym_name_query: str) -> list[dict]:
    root = load(sym_lib_path)
    for symdef in find_all(root, "symbol"):
        if len(symdef) > 1 and symdef[1] == sym_name_query:
            pins = []
            for pin_node in find_all(symdef, "pin"):
                p = parse_pin(pin_node)
                pins.append({"number": p.number, "name": p.name, "etype": p.etype})
            return pins
    return []


def cross_check(symbol_pins: list[dict], pdf_pins: list[dict], min_score: int = 80) -> list[dict]:
    findings = []
    pdf_by_number = {p["number"]: p for p in pdf_pins}
    pdf_norm_names = [normalize(p["name"]) for p in pdf_pins]
    for sp in symbol_pins:
        n = sp["number"]
        if n not in pdf_by_number:
            findings.append({
                "severity": "MEDIUM",
                "kind": "pin_number_not_found",
                "symbol_pin": f"{n} '{sp['name']}'",
                "note": f"Pin {n} from symbol not found in PDF tables.",
            })
            continue
        pdf_name = pdf_by_number[n]["name"]
        sn = normalize(sp["name"])
        pn = normalize(pdf_name)
        if sn == pn:
            continue
        score = fuzz.ratio(sn, pn)
        # try alt match by name across all pdf pins
        best, best_score, _ = process.extractOne(sn, pdf_norm_names, scorer=fuzz.ratio) if pdf_norm_names else ("", 0, 0)
        if score >= min_score:
            findings.append({
                "severity": "LOW",
                "kind": "pin_name_close",
                "symbol_pin": f"{n} '{sp['name']}'",
                "pdf_pin": f"{n} '{pdf_name}'",
                "score": score,
                "note": f"Pin {n} symbol name '{sp['name']}' ≈ datasheet '{pdf_name}' (score {score}).",
            })
        else:
            findings.append({
                "severity": "HIGH",
                "kind": "pin_name_mismatch",
                "symbol_pin": f"{n} '{sp['name']}'",
                "pdf_pin": f"{n} '{pdf_name}'",
                "score": score,
                "note": f"Pin {n} symbol name '{sp['name']}' != datasheet '{pdf_name}' (score {score}).",
            })
    return findings


def report(findings: list[dict], symbol_pins: list[dict], pdf_pins: list[dict]) -> str:
    lines = [
        f"Datasheet pin-match audit:",
        f"  Symbol pins: {len(symbol_pins)}",
        f"  PDF candidate pins extracted: {len(pdf_pins)}",
        f"  Findings: {len(findings)}",
    ]
    for f in findings:
        lines.append(f"  [{f['severity']}] {f['note']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: datasheet_pinmatch.py <symbol_lib.kicad_sym> <symbol_name> <datasheet.pdf>")
        sys.exit(1)
    lib_path, sym, pdf_path = sys.argv[1:4]
    sp = get_symbol_pins(lib_path, sym)
    if not sp:
        print(f"Symbol '{sym}' not found in {lib_path}")
        sys.exit(2)
    pp = extract_pins_from_pdf(pdf_path)
    findings = cross_check(sp, pp)
    print(report(findings, sp, pp))
    sys.exit(1 if any(f["severity"] == "HIGH" for f in findings) else 0)
