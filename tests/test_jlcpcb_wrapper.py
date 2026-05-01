"""Tests for JlcpcbWrapper.

kicad-jlcpcb-tools is a KiCad action plugin not installable via pip.
Tests verify graceful fallback behavior when the plugin is not present.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def test_import():
    """JlcpcbWrapper must be importable."""
    from jlcpcb_wrapper import JlcpcbWrapper  # noqa: F401


def test_from_env():
    """from_env() returns a JlcpcbWrapper instance."""
    from jlcpcb_wrapper import JlcpcbWrapper
    w = JlcpcbWrapper.from_env()
    assert isinstance(w, JlcpcbWrapper)


def test_is_installed_returns_bool():
    """is_installed() returns a bool regardless of plugin state."""
    from jlcpcb_wrapper import JlcpcbWrapper
    w = JlcpcbWrapper.from_env()
    assert isinstance(w.is_installed(), bool)


def test_annotate_missing_plugin(tmp_path):
    """annotate() returns MISSING_PLUGIN dict when plugin is not installed."""
    from jlcpcb_wrapper import JlcpcbWrapper
    w = JlcpcbWrapper.from_env()
    if w.is_installed():
        pytest.skip("kicad-jlcpcb-tools plugin is installed — skipping missing-plugin test")
    result = w.annotate(str(tmp_path / "nonexistent.kicad_sch"))
    assert isinstance(result, dict)
    assert "rc" in result
    assert result["rc"] == 2
    assert result.get("error") in ("MISSING_PLUGIN", "NO_CLI_MODE")
    assert "alternative" in result


def test_annotate_returns_dict(tmp_path):
    """annotate() always returns a dict with rc key."""
    from jlcpcb_wrapper import JlcpcbWrapper
    w = JlcpcbWrapper.from_env()
    result = w.annotate(str(tmp_path / "nonexistent.kicad_sch"))
    assert isinstance(result, dict)
    assert "rc" in result
