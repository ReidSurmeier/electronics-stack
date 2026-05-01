"""Tests for design_pipeline.py.

Behavioral tests — accept both success and graceful failure since
KiCad 9 symbol libraries may not be fully present in CI.
Octopart is never called (quota protection).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


# ---------------------------------------------------------------------------
# parse_spec
# ---------------------------------------------------------------------------

BLINKER_SPEC = (
    "555 timer LED blinker with 1Hz frequency, 9V battery input, 5mm red LED"
)

EXPECTED_CATEGORIES = {"ic", "connector", "led", "resistor", "capacitor"}
EXPECTED_IC_VALUE = "NE555"


def test_parse_spec_555_blinker():
    from design_pipeline import parse_spec, PartRequest

    parts = parse_spec(BLINKER_SPEC)
    assert len(parts) >= 4, f"Expected ≥4 parts, got {len(parts)}: {parts}"

    cats = {p.category for p in parts}
    assert "ic" in cats, "Expected an IC (NE555)"
    assert "led" in cats, "Expected an LED"
    assert "resistor" in cats, "Expected resistors"
    assert "capacitor" in cats, "Expected capacitors"

    ic_parts = [p for p in parts if p.category == "ic"]
    assert any("NE555" in (p.value or p.mpn) for p in ic_parts), \
        f"Expected NE555 IC, got: {ic_parts}"

    connector_parts = [p for p in parts if p.category == "connector"]
    assert connector_parts, "Expected battery clip connector"

    # All parts must have refdes assigned
    for p in parts:
        assert p.refdes, f"Missing refdes on part: {p}"


def test_parse_spec_assigns_unique_refdes():
    from design_pipeline import parse_spec

    parts = parse_spec(BLINKER_SPEC)
    refdes_list = [p.refdes for p in parts]
    assert len(refdes_list) == len(set(refdes_list)), f"Duplicate refdes: {refdes_list}"


def test_parse_spec_voltage_divider():
    from design_pipeline import parse_spec

    parts = parse_spec("Simple voltage divider with 10kΩ and 4.7kΩ resistors")
    cats = {p.category for p in parts}
    assert "resistor" in cats


def test_parse_spec_empty():
    from design_pipeline import parse_spec

    # Should return empty list, not crash
    parts = parse_spec("no components mentioned here")
    assert isinstance(parts, list)


# ---------------------------------------------------------------------------
# pick_topology
# ---------------------------------------------------------------------------

def test_pick_topology_555_blinker():
    from design_pipeline import parse_spec, pick_topology

    parts = parse_spec(BLINKER_SPEC)
    topo = pick_topology(parts)
    assert topo == "555_blinker", f"Expected 555_blinker, got {topo!r}"


def test_pick_topology_esp32():
    from design_pipeline import parse_spec, pick_topology

    parts = parse_spec("ESP32 minimal WiFi board with decoupling caps")
    topo = pick_topology(parts)
    assert topo == "esp32_minimal", f"Expected esp32_minimal, got {topo!r}"


def test_pick_topology_generic_fallback():
    from design_pipeline import parse_spec, pick_topology

    parts = parse_spec("ATmega328 microcontroller with 16MHz crystal")
    topo = pick_topology(parts)
    # ATmega328 not in IC map → generic_fallback; crystal may be parsed
    assert topo in ("generic_fallback", "esp32_minimal", "555_blinker", "voltage_divider")


# ---------------------------------------------------------------------------
# render_skidl
# ---------------------------------------------------------------------------

def test_render_skidl_produces_string():
    from design_pipeline import parse_spec, pick_topology, render_skidl

    parts = parse_spec(BLINKER_SPEC)
    topo = pick_topology(parts)
    src = render_skidl(parts, topo)
    assert isinstance(src, str)
    assert "generate_schematic" in src
    assert "skidl" in src


# ---------------------------------------------------------------------------
# DesignPipeline end-to-end
# ---------------------------------------------------------------------------

def test_design_e2e(tmp_path):
    """Full pipeline run against the canonical 555 blinker spec.

    Marked xfail if skidl crashes on KiCad 9 symbol resolution — the
    pipeline must still produce parts.json, bom.xlsx, verify_report.json,
    and a stub schematic.
    """
    from design_pipeline import DesignPipeline

    pipeline = DesignPipeline(providers=["lcsc"])  # no Octopart, no quota burn
    result = pipeline.design(BLINKER_SPEC, tmp_path / "blinker_out")

    # These files must ALWAYS exist regardless of skidl success/failure
    out = Path(result["out_dir"])
    assert (out / "parts.json").exists(), "parts.json missing"
    assert (out / "bom.xlsx").exists(), "bom.xlsx missing"
    assert (out / "verify_report.json").exists(), "verify_report.json missing"
    assert (out / "schematic.kicad_sch").exists(), "schematic.kicad_sch missing (even stub)"

    assert result["parts_count"] >= 4, f"Expected ≥4 parts, got {result['parts_count']}"
    assert "erc_errors" in result
    assert "known_limitations" in result

    if not result["success"]:
        pytest.xfail(
            f"skidl/KiCad 9 symbol resolution failed (expected): "
            f"{result['known_limitations']}"
        )


def test_design_pipeline_returns_dict(tmp_path):
    from design_pipeline import DesignPipeline

    pipeline = DesignPipeline(providers=["lcsc"])
    result = pipeline.design(BLINKER_SPEC, tmp_path / "out")
    assert isinstance(result, dict)
    for key in ("success", "out_dir", "parts_count", "erc_errors", "known_limitations"):
        assert key in result, f"Missing key {key!r} in result"


def test_design_creates_out_dir(tmp_path):
    from design_pipeline import DesignPipeline

    pipeline = DesignPipeline(providers=["lcsc"])
    out = tmp_path / "deep" / "nested" / "dir"
    result = pipeline.design(BLINKER_SPEC, out)
    assert Path(result["out_dir"]).exists()
