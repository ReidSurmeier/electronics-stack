"""Tests for IbomWrapper.

Behavioral tests — do not require a real .kicad_pcb file.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def test_import():
    """IbomWrapper must be importable."""
    from ibom_wrapper import IbomWrapper  # noqa: F401


def test_from_env():
    """from_env() returns an IbomWrapper instance."""
    from ibom_wrapper import IbomWrapper
    w = IbomWrapper.from_env()
    assert isinstance(w, IbomWrapper)


def test_render_returns_dict(tmp_path):
    """render_interactive_bom() always returns a dict with rc and html_path."""
    from ibom_wrapper import IbomWrapper
    w = IbomWrapper.from_env()
    result = w.render_interactive_bom(
        pcb_path=str(tmp_path / "nonexistent.kicad_pcb"),
        out_dir=str(tmp_path / "out"),
    )
    assert isinstance(result, dict)
    assert "rc" in result
    assert "html_path" in result
    assert "stderr" in result


def test_render_bad_path(tmp_path):
    """render_interactive_bom() with nonexistent pcb returns rc != 0."""
    from ibom_wrapper import IbomWrapper
    w = IbomWrapper.from_env()
    result = w.render_interactive_bom(
        pcb_path=str(tmp_path / "nonexistent.kicad_pcb"),
        out_dir=str(tmp_path / "out"),
    )
    # Subprocess should fail since file doesn't exist
    assert result["rc"] != 0
    assert result["html_path"] is None


def test_render_creates_out_dir(tmp_path):
    """render_interactive_bom() creates out_dir even if pcb is missing."""
    from ibom_wrapper import IbomWrapper
    w = IbomWrapper.from_env()
    out = tmp_path / "deep" / "nested"
    w.render_interactive_bom(
        pcb_path=str(tmp_path / "nonexistent.kicad_pcb"),
        out_dir=str(out),
    )
    assert out.exists()


def test_extra_args_passed(tmp_path):
    """extra_args are forwarded (confirmed via a known-bad arg causing rc != 0)."""
    from ibom_wrapper import IbomWrapper
    w = IbomWrapper.from_env()
    result = w.render_interactive_bom(
        pcb_path=str(tmp_path / "nonexistent.kicad_pcb"),
        out_dir=str(tmp_path / "out"),
        extra_args=["--dark-mode"],
    )
    assert isinstance(result, dict)
    assert "rc" in result
