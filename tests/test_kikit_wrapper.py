"""Tests for KikitWrapper.

Behavioral tests — do not test actual panelization (requires a real .kicad_pcb).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def test_import():
    """KikitWrapper must be importable."""
    from kikit_wrapper import KikitWrapper  # noqa: F401


def test_from_env():
    """from_env() returns a KikitWrapper instance."""
    from kikit_wrapper import KikitWrapper
    w = KikitWrapper.from_env()
    assert isinstance(w, KikitWrapper)


def test_panelize_bad_path(tmp_path):
    """panelize() with a nonexistent board path returns a dict with rc != 0."""
    from kikit_wrapper import KikitWrapper
    w = KikitWrapper.from_env()
    result = w.panelize(
        board_path=str(tmp_path / "nonexistent.kicad_pcb"),
        out_dir=str(tmp_path / "out"),
    )
    assert isinstance(result, dict)
    assert "rc" in result
    assert "output" in result
    assert "stderr" in result
    assert result["rc"] != 0


def test_fab_bad_path(tmp_path):
    """fab_jlcpcb() with a nonexistent board path returns a dict with rc != 0."""
    from kikit_wrapper import KikitWrapper
    w = KikitWrapper.from_env()
    result = w.fab_jlcpcb(
        board_path=str(tmp_path / "nonexistent.kicad_pcb"),
        out_dir=str(tmp_path / "out"),
    )
    assert isinstance(result, dict)
    assert "rc" in result
    assert result["rc"] != 0


def test_present_bad_path(tmp_path):
    """present() with a nonexistent board path returns a dict with note field."""
    from kikit_wrapper import KikitWrapper
    w = KikitWrapper.from_env()
    result = w.present(
        board_path=str(tmp_path / "nonexistent.kicad_pcb"),
        out_dir=str(tmp_path / "out"),
    )
    assert isinstance(result, dict)
    assert "rc" in result
    assert "note" in result


def test_panelize_creates_out_dir(tmp_path):
    """panelize() creates out_dir even if board doesn't exist."""
    from kikit_wrapper import KikitWrapper
    w = KikitWrapper.from_env()
    out = tmp_path / "deep" / "nested" / "out"
    w.panelize(
        board_path=str(tmp_path / "nonexistent.kicad_pcb"),
        out_dir=str(out),
    )
    assert out.exists()
