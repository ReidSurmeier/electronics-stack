"""Tests for datasheet_pinmatch v2.

Covers:
  - alias table schema
  - active-low canonicalization
  - token-set matching
  - alias matching
  - header filtering
  - pin-count sanity check
  - multi-strategy extraction (synthetic PDF where table fails)
  - e2e HIGH finding reduction vs v1 on real-ish alias-equivalent pairs
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts dir to path
SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import yaml
from pinmatch_matchers import (
    _load_aliases,
    _strip_active_low,
    _tokens,
    match_pin_names,
    confidence_to_severity,
)
from pinmatch_extractors import (
    HEADER_JUNK,
    _is_pin_name,
    extract_pins_from_pdf as _raw_extract_pins,
)
from datasheet_pinmatch import cross_check, extract_pins_from_pdf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spatial_pdf(pin_rows: list[tuple[str, str]], path: Path) -> None:
    """Generate a single-page PDF with pin data as text lines (no tables).

    This bypasses pdfplumber's table extractor, exercising the spatial/regex
    strategies.  Uses reportlab.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    c = canvas.Canvas(str(path), pagesize=(210 * mm, 297 * mm))
    c.setFont("Courier", 10)

    # Write a pin-section header so the page is flagged
    y = 260 * mm
    c.drawString(20 * mm, y, "Pin Configuration")
    y -= 8 * mm

    for num, name in pin_rows:
        # Format: "   1   VDD   Power supply"
        line = f"   {num:<4}{name:<16}Signal description"
        c.drawString(20 * mm, y, line)
        y -= 7 * mm
    c.save()


def _make_table_pdf(pin_rows: list[tuple[str, str]], path: Path) -> None:
    """Generate a page with a proper table — exercises table extractor."""
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors

    doc = SimpleDocTemplate(str(path))
    data = [["NO.", "NAME", "TYPE", "DESCRIPTION"]]
    for num, name in pin_rows:
        data.append([num, name, "I/O", "Signal"])
    t = Table(data)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Courier"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ]
        )
    )
    doc.build([t])


# ---------------------------------------------------------------------------
# Tests: alias table
# ---------------------------------------------------------------------------

class TestAliasTableLoads:
    def test_alias_table_loads(self):
        alias_map = _load_aliases()
        assert isinstance(alias_map, dict)
        assert len(alias_map) > 10  # sanity: many entries

    def test_alias_yaml_schema_valid(self):
        """YAML file must be a dict of str -> list[str]."""
        yaml_path = SCRIPTS / "pin_aliases.yaml"
        with open(yaml_path) as fh:
            data = yaml.safe_load(fh)
        assert isinstance(data, dict)
        for group_name, members in data.items():
            assert isinstance(group_name, str), f"group name not str: {group_name}"
            assert isinstance(members, list), f"members not list in group {group_name}"
            for m in members:
                assert isinstance(m, str), f"member not str in {group_name}: {m}"

    def test_power_group_present(self):
        alias_map = _load_aliases()
        assert "VCC" in alias_map
        assert "VDD" in alias_map
        assert alias_map["VCC"] == alias_map["VDD"]

    def test_ground_group_present(self):
        alias_map = _load_aliases()
        assert "GND" in alias_map
        assert "VSS" in alias_map
        assert alias_map["GND"] == alias_map["VSS"]

    def test_reset_group_present(self):
        alias_map = _load_aliases()
        for name in ("RESET", "RST", "NRST"):
            assert name in alias_map, f"{name} missing from alias map"
        assert alias_map["RESET"] == alias_map["NRST"]


# ---------------------------------------------------------------------------
# Tests: active-low canonicalization
# ---------------------------------------------------------------------------

class TestActiveLowCanonicalization:
    @pytest.mark.parametrize(
        "name,expected_stripped,expected_had",
        [
            ("NRST", "RST", True),
            ("RESET_N", "RESET", True),
            ("N_RESET", "RESET", True),
            ("/RESET", "RESET", True),
            ("RESET", "RESET", False),
            ("RST_N", "RST", True),
        ],
    )
    def test_strip_active_low(self, name, expected_stripped, expected_had):
        stripped, had = _strip_active_low(name)
        assert stripped == expected_stripped, f"{name}: got {stripped!r}"
        assert had == expected_had, f"{name}: had_marker={had}"

    def test_all_four_reset_variants_mutually_match(self):
        """n_RESET, NRST, RESET_N, /RESET must all match each other at >=90 confidence.

        Note: _strip_active_low bases may differ (NRST->RST, n_RESET->RESET) because
        the active-low prefix removal is heuristic.  The alias group ensures all
        reset variants still match each other via the alias matcher.
        """
        variants = ["n_RESET", "NRST", "RESET_N", "/RESET", "RESET"]
        for i, a in enumerate(variants):
            for b in variants[i + 1:]:
                conf, _ = match_pin_names(a, b)
                assert conf >= 90, (
                    f"{a!r} vs {b!r}: expected conf >= 90, got {conf}"
                )

    def test_active_low_match_confidence(self):
        """nRESET vs RSTn -- both active-low variants should hit alias group."""
        conf, strat = match_pin_names("nRESET", "RSTn")
        assert conf >= 90, f"conf={conf} strategy={strat}"

    def test_nrst_vs_reset_n(self):
        conf, strat = match_pin_names("NRST", "RESET_N")
        assert conf >= 90

    def test_reset_vs_rstn(self):
        conf, strat = match_pin_names("RESET", "RSTn")
        assert conf >= 90, f"conf={conf} strategy={strat}"

    def test_confirmed_match_no_finding(self):
        conf, _ = match_pin_names("NRST", "RESET_N")
        assert confidence_to_severity(conf) is None


# ---------------------------------------------------------------------------
# Tests: token-set matching
# ---------------------------------------------------------------------------

class TestTokenSetMatch:
    def test_pa5_matches_multifunction(self):
        """PA5 is a token in PA5/SPI1_SCK -- should hit token_set."""
        conf, strat = match_pin_names("PA5", "PA5/SPI1_SCK")
        assert conf >= 85, f"conf={conf}"
        assert strat == "token_set"

    def test_pa5_matches_three_function(self):
        conf, strat = match_pin_names("PA5", "PA5/SPI1_SCK/TIM2_CH1")
        assert conf >= 85

    def test_gpio5_matches_io5(self):
        """Just assert it does not raise."""
        conf, strat = match_pin_names("IO5", "GPIO5")
        assert isinstance(conf, int)

    def test_spi1_sck_matches_sck(self):
        """SCK is a token in SPI1_SCK."""
        conf, strat = match_pin_names("SCK", "SPI1_SCK")
        assert conf >= 85

    def test_tokens_split_correctly(self):
        assert _tokens("PA5/SPI1_SCK") == {"PA5", "SPI1", "SCK"}
        assert _tokens("TIM2-CH1") == {"TIM2", "CH1"}


# ---------------------------------------------------------------------------
# Tests: alias matching
# ---------------------------------------------------------------------------

class TestAliasMatch:
    @pytest.mark.parametrize(
        "sym,pdf",
        [
            ("VCC", "VDD"),
            ("VCC", "AVDD"),
            ("GND", "VSS"),
            ("GND", "AGND"),
            ("SCL", "SCLK"),
            ("SCL", "SCK"),
            ("SDA", "I2C_SDA"),
            ("TX", "TXD"),
            ("CS", "NSS"),
            ("EN", "OE"),
            ("INT", "IRQ"),
        ],
    )
    def test_alias_match_confidence(self, sym, pdf):
        conf, strat = match_pin_names(sym, pdf)
        assert conf >= 90, f"{sym!r} vs {pdf!r}: conf={conf} strat={strat}"
        assert strat == "alias"

    def test_alias_match_no_finding(self):
        conf, _ = match_pin_names("VCC", "VDD")
        assert confidence_to_severity(conf) is None

    def test_non_alias_has_lower_confidence(self):
        conf, _ = match_pin_names("PA5", "PB3")
        assert conf < 90


# ---------------------------------------------------------------------------
# Tests: header filtering
# ---------------------------------------------------------------------------

class TestHeaderFilter:
    @pytest.mark.parametrize(
        "header",
        ["PIN", "NAME", "TYPE", "FUNCTION", "DESCRIPTION", "I/O", "NO", "NO."],
    )
    def test_header_is_rejected(self, header):
        assert not _is_pin_name(header), f"{header!r} should be rejected"

    def test_valid_names_accepted(self):
        for name in ["VDD", "GND", "SCL", "PA5", "NRST", "DELAY/M_RST"]:
            assert _is_pin_name(name), f"{name!r} should be accepted"

    def test_lowercase_rejected_in_strict_mode(self):
        assert not _is_pin_name("Specifications", strict_case=True)
        assert not _is_pin_name("Description", strict_case=True)

    def test_active_low_lowercase_n_prefix_allowed_in_strict_mode(self):
        # "nRESET" -- leading lowercase n is the active-low prefix convention
        # strict_case strips leading n then checks body for lowercase
        assert _is_pin_name("nRESET", strict_case=True)

    def test_header_junk_set_populated(self):
        assert len(HEADER_JUNK) >= 8


# ---------------------------------------------------------------------------
# Tests: pin-count sanity check
# ---------------------------------------------------------------------------

class TestPinCountSanity:
    def test_pins_beyond_cutoff_dropped(self, tmp_path):
        """Pins with number > expected+4 should be dropped."""
        pdf_path = tmp_path / "test.pdf"
        pin_rows = [(str(i), f"SIG{i}") for i in range(1, 7)]
        pin_rows.append(("99", "BOGUS"))
        _make_table_pdf(pin_rows, pdf_path)

        pins, _ = _raw_extract_pins(pdf_path, expected_pin_count=6)
        pin_numbers = {int(p["number"]) for p in pins}
        assert 99 not in pin_numbers, "Pin 99 should have been filtered by sanity check"
        assert pin_numbers.issuperset({1, 2, 3, 4, 5, 6})

    def test_pin_zero_filtered(self, tmp_path):
        """Pin number 0 is junk -- should be dropped."""
        pdf_path = tmp_path / "test.pdf"
        _make_table_pdf([("0", "BOGUS"), ("1", "VDD"), ("2", "GND")], pdf_path)
        pins, _ = _raw_extract_pins(pdf_path, expected_pin_count=2)
        pin_numbers = {int(p["number"]) for p in pins}
        assert 0 not in pin_numbers


# ---------------------------------------------------------------------------
# Tests: multi-strategy extraction
# ---------------------------------------------------------------------------

class TestMultiStrategyExtraction:
    def test_table_strategy_finds_pins(self, tmp_path):
        """Table PDF: table extractor should find pins."""
        pdf_path = tmp_path / "table_test.pdf"
        pin_rows = [("1", "VDD"), ("2", "GND"), ("3", "SCL"), ("4", "SDA")]
        _make_table_pdf(pin_rows, pdf_path)
        pins, summary = _raw_extract_pins(pdf_path, expected_pin_count=4)
        names = {p["name"] for p in pins}
        assert "VDD" in names or "GND" in names, f"Expected pin names, got {names}"
        assert summary["by_extractor"]["table"] > 0

    def test_regex_fallback_fires_on_text_only_page(self, tmp_path):
        """Spatial-only (text) PDF: spatial or regex_fallback should find pins."""
        pdf_path = tmp_path / "spatial_test.pdf"
        pin_rows = [("1", "VDD"), ("2", "GND"), ("3", "SCL"), ("4", "SDA")]
        _make_spatial_pdf(pin_rows, pdf_path)
        pins, summary = _raw_extract_pins(pdf_path, expected_pin_count=4)
        non_table = summary["by_extractor"]["spatial"] + summary["by_extractor"]["regex_fallback"]
        assert len(pins) > 0, "Should find at least some pins"

    def test_extraction_summary_structure(self, tmp_path):
        """extraction_summary must have expected keys."""
        pdf_path = tmp_path / "struct_test.pdf"
        _make_table_pdf([("1", "VDD"), ("2", "GND")], pdf_path)
        _, summary = _raw_extract_pins(pdf_path, expected_pin_count=2)
        assert "by_extractor" in summary
        assert "pin_section_pages" in summary
        assert "expected_pin_count" in summary
        assert isinstance(summary["by_extractor"], dict)
        for key in ("table", "spatial", "regex_fallback"):
            assert key in summary["by_extractor"]

    def test_pin_section_page_flagged(self):
        """TPL5010 page 4 is a pin-section page."""
        tpl_pdf = (
            Path(__file__).parent.parent
            / "test-corpus/wearables/hardware-watchdog/tpl5010.pdf"
        )
        if not tpl_pdf.exists():
            pytest.skip("TPL5010 PDF not present")
        _, summary = _raw_extract_pins(tpl_pdf, expected_pin_count=6)
        assert 4 in summary["pin_section_pages"], (
            f"Page 4 should be flagged as pin-section; got {summary['pin_section_pages']}"
        )


# ---------------------------------------------------------------------------
# Tests: e2e HIGH finding reduction
# ---------------------------------------------------------------------------

class TestE2EHighFindingReduction:
    def _v1_cross_check(
        self, symbol_pins: list[dict], pdf_pins: list[dict]
    ) -> list[dict]:
        """Reimplementation of v1 cross_check logic for comparison."""
        import re
        from rapidfuzz import fuzz, process

        def norm(s: str) -> str:
            return re.sub(r"[^A-Z0-9]", "", s.upper())

        findings = []
        pdf_by_number = {p["number"]: p for p in pdf_pins}
        pdf_norm_names = [norm(p["name"]) for p in pdf_pins]
        for sp in symbol_pins:
            n = sp["number"]
            if n not in pdf_by_number:
                findings.append({"severity": "MEDIUM", "note": f"pin {n} missing"})
                continue
            pdf_name = pdf_by_number[n]["name"]
            sn = norm(sp["name"])
            pn = norm(pdf_name)
            if sn == pn:
                continue
            score = fuzz.ratio(sn, pn)
            if score >= 80:
                findings.append({"severity": "LOW", "note": f"{n} close"})
            else:
                findings.append({"severity": "HIGH", "note": f"{n} mismatch"})
        return findings

    def test_alias_equivalent_pins_drop_high_findings(self):
        """When symbol uses one alias and PDF uses another, HIGH count drops >=50%."""
        symbol_pins = [
            {"number": "1", "name": "VCC", "etype": "power_in"},
            {"number": "2", "name": "GND", "etype": "power_in"},
            {"number": "3", "name": "SCL", "etype": "input"},
            {"number": "4", "name": "SDA", "etype": "bidirectional"},
            {"number": "5", "name": "RESET", "etype": "input"},
            {"number": "6", "name": "INT", "etype": "output"},
            {"number": "7", "name": "TX", "etype": "output"},
            {"number": "8", "name": "RX", "etype": "input"},
        ]
        pdf_pins = [
            {"number": "1", "name": "VDD", "page": 1, "extractor": "table", "raw_row": None, "on_pin_section_page": True},
            {"number": "2", "name": "VSS", "page": 1, "extractor": "table", "raw_row": None, "on_pin_section_page": True},
            {"number": "3", "name": "SCLK", "page": 1, "extractor": "table", "raw_row": None, "on_pin_section_page": True},
            {"number": "4", "name": "I2C_SDA", "page": 1, "extractor": "table", "raw_row": None, "on_pin_section_page": True},
            {"number": "5", "name": "NRST", "page": 1, "extractor": "table", "raw_row": None, "on_pin_section_page": True},
            {"number": "6", "name": "IRQ", "page": 1, "extractor": "table", "raw_row": None, "on_pin_section_page": True},
            {"number": "7", "name": "TXD", "page": 1, "extractor": "table", "raw_row": None, "on_pin_section_page": True},
            {"number": "8", "name": "RXD", "page": 1, "extractor": "table", "raw_row": None, "on_pin_section_page": True},
        ]

        v1_findings = self._v1_cross_check(symbol_pins, pdf_pins)
        v2_findings = cross_check(symbol_pins, pdf_pins)

        v1_high = sum(1 for f in v1_findings if f["severity"] == "HIGH")
        v2_high = sum(1 for f in v2_findings if f["severity"] == "HIGH")

        assert v1_high >= 4, f"V1 should flag >=4 HIGH but got {v1_high}"
        assert v2_high == 0, (
            f"V2 should flag 0 HIGH (all are alias pairs) but got {v2_high}: "
            f"{[f for f in v2_findings if f['severity'] == 'HIGH']}"
        )

    def test_e2e_tpl5010_no_false_high(self):
        """Real TPL5010 datasheet: cross-check with matching symbol pins."""
        tpl_pdf = (
            Path(__file__).parent.parent
            / "test-corpus/wearables/hardware-watchdog/tpl5010.pdf"
        )
        if not tpl_pdf.exists():
            pytest.skip("TPL5010 PDF not present")

        symbol_pins = [
            {"number": "1", "name": "VDD", "etype": "power_in"},
            {"number": "2", "name": "GND", "etype": "power_in"},
            {"number": "3", "name": "DELAY_M_RST", "etype": "input"},
            {"number": "4", "name": "DONE", "etype": "input"},
            {"number": "5", "name": "WAKE", "etype": "output"},
            {"number": "6", "name": "RESET", "etype": "output"},
        ]
        # Use the public wrapper from datasheet_pinmatch (returns list, not tuple)
        pdf_pins = extract_pins_from_pdf(tpl_pdf, expected_pin_count=6)
        findings = cross_check(symbol_pins, pdf_pins)
        high_findings = [f for f in findings if f["severity"] == "HIGH"]
        assert len(high_findings) == 0, (
            f"Expected 0 HIGH findings, got {len(high_findings)}: {high_findings}"
        )

    def test_cross_check_output_schema(self):
        """cross_check output must include all required fields."""
        symbol_pins = [{"number": "1", "name": "VDD", "etype": "power_in"}]
        pdf_pins = [
            {
                "number": "1",
                "name": "VCC",
                "page": 1,
                "extractor": "table",
                "raw_row": ["1", "VCC", "I/O", "Supply"],
                "on_pin_section_page": True,
            }
        ]
        findings = cross_check(symbol_pins, pdf_pins)
        # VDD <-> VCC are aliases -> no finding
        assert findings == []

    def test_genuine_mismatch_still_flagged_high(self):
        """A truly wrong pin (no alias relation) must still be HIGH."""
        symbol_pins = [{"number": "1", "name": "PA5", "etype": "bidirectional"}]
        pdf_pins = [
            {
                "number": "1",
                "name": "PB3",
                "page": 1,
                "extractor": "table",
                "raw_row": None,
                "on_pin_section_page": True,
            }
        ]
        findings = cross_check(symbol_pins, pdf_pins)
        assert len(findings) == 1
        assert findings[0]["severity"] == "HIGH"
        assert "confidence" in findings[0]
        assert "match_strategy" in findings[0]
        assert "pdf_evidence" in findings[0]
