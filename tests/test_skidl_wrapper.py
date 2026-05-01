"""Tests for SkidlWrapper.

Tests are behavioral — they accept both success and graceful failure
since KiCad symbol libraries may not be present in CI.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def test_import():
    """SkidlWrapper must be importable."""
    from skidl_wrapper import SkidlWrapper  # noqa: F401


def test_from_env_returns_instance():
    """from_env() returns a SkidlWrapper and sets KICAD9_SYMBOL_DIR."""
    from skidl_wrapper import SkidlWrapper
    w = SkidlWrapper.from_env()
    assert isinstance(w, SkidlWrapper)
    assert "KICAD9_SYMBOL_DIR" in os.environ


def test_generate_netlist_returns_dict(tmp_path):
    """generate_netlist() always returns a dict with 'rc' key."""
    from skidl_wrapper import SkidlWrapper
    w = SkidlWrapper.from_env()
    result = w.generate_netlist(
        parts=[{"lib": "Device", "name": "R", "refdes": "R1", "footprint": None}],
        nets=[{"name": "VCC", "connections": [{"refdes": "R1", "pin": "1"}]}],
        out_dir=str(tmp_path),
    )
    assert isinstance(result, dict)
    assert "rc" in result
    # rc is 0 (success) or 1 (missing symbol lib) — both acceptable
    assert result["rc"] in (0, 1)


def test_generate_netlist_empty_parts(tmp_path):
    """generate_netlist() with empty parts list returns a dict."""
    from skidl_wrapper import SkidlWrapper
    w = SkidlWrapper.from_env()
    result = w.generate_netlist(parts=[], nets=[], out_dir=str(tmp_path))
    assert isinstance(result, dict)
    assert "rc" in result


def test_generate_schematic_fallback(tmp_path):
    """generate_schematic() always returns a dict with rc, notes, warnings keys."""
    from skidl_wrapper import SkidlWrapper
    w = SkidlWrapper.from_env()
    result = w.generate_schematic(
        parts=[{"lib": "Device", "name": "C", "refdes": "C1", "footprint": None}],
        nets=[{"name": "GND", "connections": [{"refdes": "C1", "pin": "2"}]}],
        out_dir=str(tmp_path),
    )
    assert isinstance(result, dict)
    assert "rc" in result
    assert "notes" in result
    assert "warnings" in result


def test_generate_schematic_creates_out_dir(tmp_path):
    """generate_schematic() creates out_dir."""
    from skidl_wrapper import SkidlWrapper
    w = SkidlWrapper.from_env()
    out = tmp_path / "deep" / "out"
    w.generate_schematic(parts=[], nets=[], out_dir=str(out))
    assert out.exists()
