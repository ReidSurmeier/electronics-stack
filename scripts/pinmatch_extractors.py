"""PDF pin extraction strategies for datasheet_pinmatch.

Four strategies are combined and deduplicated:
  table      — pdfplumber.extract_tables()
  spatial    — word-cluster analysis (x/y proximity)
  regex_fallback — line-regex on plain text (pages with zero hits from above)

Pin-section pages are detected and given higher confidence during dedup.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import pdfplumber

# Column header names that are NOT pin names
HEADER_JUNK: frozenset[str] = frozenset(
    {
        "PIN",
        "NAME",
        "NO",
        "NO.",
        "NUMBER",
        "TYPE",
        "FUNCTION",
        "DESCRIPTION",
        "I/O",
        "I_O",
        "PWR",
        "POWER",
        "SIGNAL",
        "SIGNALS",
        "DIRECTION",
        "COMMENT",
        "COMMENTS",
        "NOTE",
        "NOTES",
        "VOLTAGE",
        "LEVEL",
    }
)

# Keywords that identify pin-description pages
PIN_SECTION_KEYWORDS: tuple[str, ...] = (
    "Pin Description",
    "Pin Configuration",
    "Pin Functions",
    "Pinout",
    "Pin Assignments",
    "PIN DESCRIPTION",
    "PIN CONFIGURATION",
    "PIN FUNCTIONS",
    "PINOUT",
    "PIN ASSIGNMENTS",
    "Pin Definition",
    "PIN DEFINITION",
)

# Regex for a valid pin name: starts uppercase, max 20 chars total,
# may contain /\_-+# but no lowercase (real signal names are ALL-CAPS or short).
# 20-char cap filters long prose words like "SUBMITDOCUMENTATIONFEEDBACK" (26 chars).
_PIN_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_/\-+#]{0,19}$")
# Regex for a pin number: 1-3 digits only
_PIN_NUM_RE = re.compile(r"^\d{1,3}$")
# Line-fallback: number then whitespace then name at line start
_LINE_RE = re.compile(r"^\s*(\d{1,3})\s+([A-Z][A-Z0-9/_\-+#]{0,19})(?:\s|$)")


class PinCandidate(NamedTuple):
    number: str
    name: str
    page: int
    extractor: str
    raw_row: list[str] | None = None
    on_pin_section_page: bool = False


def _is_pin_name(s: str, strict_case: bool = False) -> bool:
    """True if s looks like a signal name (not a header or junk value).

    Args:
        s: Raw cell/word text.
        strict_case: If True (spatial strategy), reject words with lowercase
            letters — prose words have lowercase while signal names are ALLCAPS.
            If False (table strategy), allow mixed-case like "RSTn" or "nRESET".
    """
    if not s:
        return False
    stripped = s.strip()
    if strict_case:
        # Reject prose words — signal names are ALL-CAPS (or start with n/N for active-low)
        # Allow leading lowercase 'n' prefix (active-low convention: "nRESET")
        # but reject if there's lowercase *other than* a leading 'n' before an uppercase
        body = stripped.lstrip("n/")
        if re.search(r"[a-z]", body):
            return False
    clean = stripped.upper()
    if clean in HEADER_JUNK:
        return False
    # strip leading active-low markers for regex check
    test = re.sub(r"^[N/]_?", "", clean)
    if not test:
        return False
    return bool(_PIN_NAME_RE.match(clean))


def _is_pin_number(s: str) -> bool:
    return bool(s and _PIN_NUM_RE.match(s.strip()))


def _is_pin_section_page(text: str) -> bool:
    return any(kw in text for kw in PIN_SECTION_KEYWORDS)


# ---------------------------------------------------------------------------
# Strategy 1 — pdfplumber table extractor
# ---------------------------------------------------------------------------

def _extract_table_strategy(
    page: pdfplumber.page.Page,
    page_idx: int,
    on_pin_page: bool,
) -> list[PinCandidate]:
    candidates: list[PinCandidate] = []
    tables = page.extract_tables() or []
    for table in tables:
        for row in table:
            if not row:
                continue
            cells = [
                re.sub(r"\s+", "", c).strip() if c else "" for c in row
            ]
            # Multi-line cells get collapsed via re.sub above (strips \n)
            # Find first integer cell and first name cell (left to right)
            num_idx: int | None = None
            name_idx: int | None = None
            for ci, c in enumerate(cells):
                if num_idx is None and _is_pin_number(c):
                    num_idx = ci
                elif name_idx is None and _is_pin_name(c):
                    name_idx = ci
            if num_idx is not None and name_idx is not None and num_idx != name_idx:
                candidates.append(
                    PinCandidate(
                        number=cells[num_idx],
                        name=cells[name_idx],
                        page=page_idx + 1,
                        extractor="table",
                        raw_row=cells,
                        on_pin_section_page=on_pin_page,
                    )
                )
    return candidates


# ---------------------------------------------------------------------------
# Strategy 2 — spatial word clustering
# ---------------------------------------------------------------------------

def _cluster_by_row(words: list[dict], y_tol: float = 4.0) -> list[list[dict]]:
    """Group words into rows by y-coordinate proximity."""
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (round(w["top"] / y_tol), w["x0"]))
    rows: list[list[dict]] = []
    current_row: list[dict] = [sorted_words[0]]
    current_y = sorted_words[0]["top"]
    for w in sorted_words[1:]:
        if abs(w["top"] - current_y) <= y_tol:
            current_row.append(w)
        else:
            rows.append(current_row)
            current_row = [w]
            current_y = w["top"]
    if current_row:
        rows.append(current_row)
    return rows


def _extract_spatial_strategy(
    page: pdfplumber.page.Page,
    page_idx: int,
    on_pin_page: bool,
) -> list[PinCandidate]:
    candidates: list[PinCandidate] = []
    words = page.extract_words() or []
    if not words:
        return candidates
    rows = _cluster_by_row(words)
    for row_words in rows:
        texts = [w["text"].strip() for w in row_words]
        # Need at least a number + a name in this row
        nums = [t for t in texts if _is_pin_number(t)]
        names = [t for t in texts if _is_pin_name(t, strict_case=True)]
        if not nums or not names:
            continue
        # Require the number is leftmost or nearly so (within first 3 tokens)
        first_tokens = texts[:3]
        if not any(_is_pin_number(t) for t in first_tokens):
            continue
        # Take first valid num and first valid name
        num = nums[0]
        name = names[0]
        if num == name:
            continue
        candidates.append(
            PinCandidate(
                number=num,
                name=name,
                page=page_idx + 1,
                extractor="spatial",
                raw_row=texts,
                on_pin_section_page=on_pin_page,
            )
        )
    return candidates


# ---------------------------------------------------------------------------
# Strategy 3 — per-line regex fallback
# ---------------------------------------------------------------------------

def _extract_regex_strategy(
    page: pdfplumber.page.Page,
    page_idx: int,
    on_pin_page: bool,
) -> list[PinCandidate]:
    candidates: list[PinCandidate] = []
    text = page.extract_text() or ""
    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        num, name = m.group(1), m.group(2)
        if not _is_pin_name(name):
            continue
        candidates.append(
            PinCandidate(
                number=num,
                name=name,
                page=page_idx + 1,
                extractor="regex_fallback",
                raw_row=[line.strip()],
                on_pin_section_page=on_pin_page,
            )
        )
    return candidates


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_pins_from_pdf(
    pdf_path: str | Path,
    max_pages: int = 30,
    expected_pin_count: int | None = None,
) -> tuple[list[dict], dict]:
    """Extract pin candidates from a datasheet PDF using multiple strategies.

    Returns:
        (pins, extraction_summary) where pins is a list of dicts with keys:
            number, name, page, extractor, raw_row, on_pin_section_page
        and extraction_summary contains per-extractor counts and metadata.
    """
    all_candidates: list[PinCandidate] = []
    pin_section_pages: list[int] = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            text = page.extract_text() or ""
            on_pin_page = _is_pin_section_page(text)
            if on_pin_page and (i + 1) not in pin_section_pages:
                pin_section_pages.append(i + 1)

            table_hits = _extract_table_strategy(page, i, on_pin_page)
            spatial_hits = _extract_spatial_strategy(page, i, on_pin_page)

            # Regex fallback only for pages with zero hits from table+spatial
            if not table_hits and not spatial_hits:
                regex_hits = _extract_regex_strategy(page, i, on_pin_page)
            else:
                regex_hits = []

            all_candidates.extend(table_hits)
            all_candidates.extend(spatial_hits)
            all_candidates.extend(regex_hits)

    # Dedup: key = pin number. Keep best candidate per number.
    # Priority: (on_pin_section_page DESC, extractor_rank ASC)
    # This ensures page-4 "1 VDD" beats page-1 "1 Features".
    extractor_rank = {"table": 0, "spatial": 1, "regex_fallback": 2}

    def _candidate_score(c: PinCandidate) -> tuple[int, int]:
        # Lower tuple = better; sort ascending
        return (
            0 if c.on_pin_section_page else 1,
            extractor_rank.get(c.extractor, 9),
        )

    best_by_num: dict[str, PinCandidate] = {}
    for cand in all_candidates:
        num = cand.number
        if num not in best_by_num:
            best_by_num[num] = cand
        else:
            if _candidate_score(cand) < _candidate_score(best_by_num[num]):
                best_by_num[num] = cand

    pins = [c._asdict() for c in best_by_num.values()]

    # Sanity-check: drop pin number 0 (always junk) and numbers far beyond
    # the expected count (page numbers, footnote refs, etc.)
    if expected_pin_count is not None:
        cutoff = expected_pin_count + 4
        pins = [p for p in pins if 1 <= int(p["number"]) <= cutoff]
    else:
        # Always drop pin 0 regardless
        pins = [p for p in pins if int(p["number"]) >= 1]

    # Summary counters
    by_extractor: dict[str, int] = {"table": 0, "spatial": 0, "regex_fallback": 0}
    for p in pins:
        ext = p.get("extractor", "unknown")
        by_extractor[ext] = by_extractor.get(ext, 0) + 1

    extraction_summary = {
        "by_extractor": by_extractor,
        "pin_section_pages": pin_section_pages,
        "expected_pin_count": expected_pin_count,
    }

    return pins, extraction_summary
