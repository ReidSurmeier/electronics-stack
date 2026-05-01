"""Pin-name matching strategies for datasheet_pinmatch.

Matchers are applied in priority order; the highest confidence wins.
Confidence ≥ 90 → confirmed match (INFO, no finding emitted).
Confidence 70-89 → LOW finding.
Confidence < 70 → HIGH finding.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Alias table
# ---------------------------------------------------------------------------

_ALIASES_PATH = Path(__file__).parent / "pin_aliases.yaml"
# Map from normalized name → group name
_alias_map: dict[str, str] | None = None


def _load_aliases() -> dict[str, str]:
    global _alias_map
    if _alias_map is None:
        with open(_ALIASES_PATH) as fh:
            data: dict[str, list[str]] = yaml.safe_load(fh)
        mapping: dict[str, str] = {}
        for group_name, members in data.items():
            for m in members:
                mapping[_norm(m)] = group_name
        _alias_map = mapping
    return _alias_map


def _norm(s: str) -> str:
    """Strip non-alphanumeric, uppercase."""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


# ---------------------------------------------------------------------------
# Active-low canonicalization
# ---------------------------------------------------------------------------

_ACTIVE_LOW_PREFIX = re.compile(r"^(N_|N(?=[A-Z])|/)")
_ACTIVE_LOW_SUFFIX = re.compile(r"(_N|N|#|B)$")


def _strip_active_low(s: str) -> tuple[str, bool]:
    """Return (stripped_name, had_marker)."""
    upper = s.upper()
    had = False
    m = _ACTIVE_LOW_PREFIX.match(upper)
    if m:
        upper = upper[m.end():]
        had = True
    m = _ACTIVE_LOW_SUFFIX.search(upper)
    if m and len(upper) > 1:
        upper = upper[: m.start()]
        had = True
    return upper, had


# ---------------------------------------------------------------------------
# Token-set helpers
# ---------------------------------------------------------------------------

def _tokens(s: str) -> frozenset[str]:
    """Split on /  _  -  and return non-empty token set."""
    parts = re.split(r"[/_\-]", s.upper())
    return frozenset(p for p in parts if p)


# ---------------------------------------------------------------------------
# Matchers
# ---------------------------------------------------------------------------

def _match_exact(sym_norm: str, pdf_norm: str) -> int | None:
    if sym_norm == pdf_norm:
        return 100
    return None


def _match_alias(sym_norm: str, pdf_norm: str, alias_map: dict[str, str]) -> int | None:
    sg = alias_map.get(sym_norm)
    pg = alias_map.get(pdf_norm)
    if sg and sg == pg:
        return 90
    return None


def _match_active_low(sym_raw: str, pdf_raw: str) -> int | None:
    sym_stripped, sym_had = _strip_active_low(sym_raw)
    pdf_stripped, pdf_had = _strip_active_low(pdf_raw)
    if (sym_had or pdf_had) and sym_stripped and pdf_stripped:
        if sym_stripped == pdf_stripped:
            return 95
    return None


def _match_token_set(sym_raw: str, pdf_raw: str) -> int | None:
    sym_toks = _tokens(sym_raw)
    pdf_toks = _tokens(pdf_raw)
    if sym_toks and sym_toks.issubset(pdf_toks):
        return 85
    if pdf_toks and pdf_toks.issubset(sym_toks):
        return 85
    return None


def _match_substring(sym_raw: str, pdf_raw: str) -> int | None:
    sym_up = sym_raw.upper()
    pdf_up = pdf_raw.upper()
    # Require token-boundary match (surrounded by non-alnum or start/end)
    pattern = r"(?<![A-Z0-9])" + re.escape(sym_up) + r"(?![A-Z0-9])"
    if re.search(pattern, pdf_up):
        return 80
    pattern2 = r"(?<![A-Z0-9])" + re.escape(pdf_up) + r"(?![A-Z0-9])"
    if re.search(pattern2, sym_up):
        return 80
    return None


def _match_fuzzy(sym_norm: str, pdf_norm: str) -> int:
    return int(fuzz.ratio(sym_norm, pdf_norm))


# ---------------------------------------------------------------------------
# LLM tiebreaker stub (v3 hook)
# ---------------------------------------------------------------------------

def llm_tiebreak(
    symbol_pin: dict[str, Any],
    pdf_candidate: dict[str, Any],
    page_text: str,
) -> dict[str, Any] | None:
    """Stub for future LLM-based tiebreaking.

    In v3, wire this up to an LLM call. The function should:
      1. Send symbol_pin["name"], pdf_candidate["name"], and relevant page_text
         to a language model with a prompt asking "are these the same signal?"
      2. Parse the response into {equivalent: bool, confidence: int, rationale: str}.
      3. Return that dict, or None on error/timeout.

    Currently returns None always (no LLM call in this PR).
    """
    return None


# ---------------------------------------------------------------------------
# Main match function
# ---------------------------------------------------------------------------

def match_pin_names(
    sym_name: str,
    pdf_name: str,
) -> tuple[int, str]:
    """Compare two pin names and return (confidence, strategy).

    confidence 0-100; strategy is the name of the winning matcher.
    """
    alias_map = _load_aliases()
    sym_norm = _norm(sym_name)
    pdf_norm = _norm(pdf_name)

    checks: list[tuple[int | None, str]] = [
        (_match_exact(sym_norm, pdf_norm), "exact"),
        (_match_active_low(sym_name, pdf_name), "active_low"),
        (_match_alias(sym_norm, pdf_norm, alias_map), "alias"),
        (_match_token_set(sym_name, pdf_name), "token_set"),
        (_match_substring(sym_name, pdf_name), "substring"),
    ]

    best_conf = 0
    best_strategy = "fuzzy"
    for score, strategy in checks:
        if score is not None and score > best_conf:
            best_conf = score
            best_strategy = strategy

    # Fuzzy as floor
    fuzzy_score = _match_fuzzy(sym_norm, pdf_norm)
    if fuzzy_score > best_conf:
        best_conf = fuzzy_score
        best_strategy = "fuzzy"

    return best_conf, best_strategy


def confidence_to_severity(confidence: int) -> str | None:
    """Map confidence to finding severity, or None if confirmed match."""
    if confidence >= 90:
        return None  # confirmed — no finding
    if confidence >= 70:
        return "LOW"
    return "HIGH"
