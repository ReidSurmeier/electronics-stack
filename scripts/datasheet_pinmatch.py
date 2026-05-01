"""Datasheet pin-cross-check.

Given a KiCad symbol library + a datasheet PDF, extract pin tables from the
PDF and fuzzy-match against the symbol's pin names. Flag mismatches.

Usage:
    datasheet_pinmatch.py <symbol_lib.kicad_sym> <symbol_name> <datasheet.pdf>

Multi-strategy extraction (table / spatial / regex fallback) combined with
alias-aware matching covers ~95% of real datasheets.  See pinmatch_extractors.py
and pinmatch_matchers.py for implementation details.

MCP tool contract (pin_match_datasheet):
    Callers expect the return shape:
        {symbol_pins: [...], pdf_pins: [...], findings: [...]}
    This module adds optional fields but never removes existing ones.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pdfplumber
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).parent))
from sch_parser import load, find_all, sym_name, parse_pin
from pinmatch_extractors import extract_pins_from_pdf as _multi_extract
from pinmatch_matchers import match_pin_names, confidence_to_severity


def normalize(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


# ---------------------------------------------------------------------------
# Public API — backward-compatible signatures
# ---------------------------------------------------------------------------

def extract_pins_from_pdf(
    pdf_path: str | Path,
    max_pages: int = 30,
    expected_pin_count: int | None = None,
) -> list[dict]:
    """Extract candidate (number, name) pin pairs from a PDF.

    Uses multi-strategy extraction (table, spatial, regex fallback).
    Returns a flat list of dicts; each dict has at minimum:
        number, name, page, extractor, raw_row, on_pin_section_page
    """
    pins, _summary = _multi_extract(
        pdf_path,
        max_pages=max_pages,
        expected_pin_count=expected_pin_count,
    )
    return pins


def get_symbol_pins(sym_lib_path: str | Path, sym_name_query: str) -> list[dict]:
    """Load KiCad symbol library and return pins for the named symbol."""
    root = load(sym_lib_path)
    for symdef in find_all(root, "symbol"):
        if len(symdef) > 1 and symdef[1] == sym_name_query:
            pins = []
            for pin_node in find_all(symdef, "pin"):
                p = parse_pin(pin_node)
                pins.append({"number": p.number, "name": p.name, "etype": p.etype})
            return pins
    return []


def cross_check(
    symbol_pins: list[dict],
    pdf_pins: list[dict],
    min_score: int = 80,
    expected_pin_count: int | None = None,
) -> list[dict]:
    """Cross-check symbol pins against PDF-extracted pins.

    Args:
        symbol_pins: Output of get_symbol_pins().
        pdf_pins: Output of extract_pins_from_pdf().
        min_score: Legacy param kept for backward compatibility (unused;
            confidence thresholds are now fixed at 70/90).
        expected_pin_count: If given, used for sanity-check logging only
            (actual filtering happens in extract_pins_from_pdf).

    Returns:
        List of finding dicts with keys:
            severity, kind, symbol_pin, note
            + optional: pdf_pin, score, confidence, match_strategy, pdf_evidence
    """
    findings: list[dict] = []
    pdf_by_number: dict[str, dict] = {p["number"]: p for p in pdf_pins}

    for sp in symbol_pins:
        n = sp["number"]
        if n not in pdf_by_number:
            findings.append(
                {
                    "severity": "MEDIUM",
                    "kind": "pin_number_not_found",
                    "symbol_pin": f"{n} '{sp['name']}'",
                    "note": f"Pin {n} from symbol not found in PDF tables.",
                    "confidence": 0,
                    "match_strategy": "none",
                    "pdf_evidence": None,
                }
            )
            continue

        pdf_pin = pdf_by_number[n]
        pdf_name = pdf_pin["name"]
        sym_name_str = sp["name"]

        confidence, strategy = match_pin_names(sym_name_str, pdf_name)
        severity = confidence_to_severity(confidence)

        # Build pdf_evidence block
        pdf_evidence: dict[str, Any] = {
            "page": pdf_pin.get("page"),
            "extractor": pdf_pin.get("extractor", "unknown"),
            "raw_row": pdf_pin.get("raw_row"),
        }

        if severity is None:
            # Confirmed match — no finding
            continue

        findings.append(
            {
                "severity": severity,
                "kind": "pin_name_mismatch" if severity == "HIGH" else "pin_name_close",
                "symbol_pin": f"{n} '{sym_name_str}'",
                "pdf_pin": f"{n} '{pdf_name}'",
                "score": int(fuzz.ratio(normalize(sym_name_str), normalize(pdf_name))),
                "confidence": confidence,
                "match_strategy": strategy,
                "note": (
                    f"Pin {n} symbol '{sym_name_str}' vs datasheet '{pdf_name}' "
                    f"(confidence {confidence}, strategy {strategy})."
                ),
                "pdf_evidence": pdf_evidence,
            }
        )

    return findings


def cross_check_full(
    symbol_pins: list[dict],
    pdf_path: str | Path,
    max_pages: int = 30,
) -> dict:
    """Convenience: extract + cross-check in one call, return full result dict.

    Return shape includes extraction_summary for richer MCP responses.
    """
    expected = len(symbol_pins) if symbol_pins else None
    pins, extraction_summary = _multi_extract(
        pdf_path,
        max_pages=max_pages,
        expected_pin_count=expected,
    )
    findings = cross_check(symbol_pins, pins, expected_pin_count=expected)
    return {
        "symbol_pins": symbol_pins,
        "pdf_pins": pins,
        "findings": findings,
        "extraction_summary": extraction_summary,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(
    findings: list[dict],
    symbol_pins: list[dict],
    pdf_pins: list[dict],
    extraction_summary: dict | None = None,
) -> str:
    lines = [
        "Datasheet pin-match audit:",
        f"  Symbol pins: {len(symbol_pins)}",
        f"  PDF candidate pins extracted: {len(pdf_pins)}",
        f"  Findings: {len(findings)}",
    ]
    if extraction_summary:
        by_ext = extraction_summary.get("by_extractor", {})
        lines.append(
            f"  Extractors: table={by_ext.get('table', 0)}"
            f" spatial={by_ext.get('spatial', 0)}"
            f" regex_fallback={by_ext.get('regex_fallback', 0)}"
        )
        psec = extraction_summary.get("pin_section_pages", [])
        if psec:
            lines.append(f"  Pin-section pages: {psec}")
    for f in findings:
        lines.append(f"  [{f['severity']}] {f['note']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "usage: datasheet_pinmatch.py <symbol_lib.kicad_sym> <symbol_name> <datasheet.pdf>"
        )
        sys.exit(1)
    lib_path, sym, pdf_path = sys.argv[1:4]
    sp = get_symbol_pins(lib_path, sym)
    if not sp:
        print(f"Symbol '{sym}' not found in {lib_path}")
        sys.exit(2)
    pp = extract_pins_from_pdf(pdf_path, expected_pin_count=len(sp))
    findings = cross_check(sp, pp)
    _, extraction_summary = _multi_extract(pdf_path, expected_pin_count=len(sp))
    print(report(findings, sp, pp, extraction_summary))
    sys.exit(1 if any(f["severity"] == "HIGH" for f in findings) else 0)
