"""kicad-jlcpcb-tools wrapper for electronics-stack MCP server.

kicad-jlcpcb-tools (https://github.com/Bouni/kicad-jlcpcb-tools) is a
KiCad action plugin — it ships as a KiCad Plugin Manager package, not a
pip-installable Python module. It has no published CLI mode as of v2026-05.

This wrapper provides the annotate_jlc_bom MCP interface stub and documents
the installation path. If the plugin is later installed into KiCad's plugin
directory, the ``annotate`` method will invoke it; otherwise it returns a
clear MISSING_PLUGIN error with installation instructions.

Installation (once per machine):
    1. Open KiCad → Plugin Manager → search "JLCPCB Tools" → Install
    2. Plugin dir: ~/.local/share/kicad/9.0/scripting/plugins/kicad_jlcpcb_tools/
    3. Alternatively: git clone https://github.com/Bouni/kicad-jlcpcb-tools
       into the plugins dir, then restart KiCad.

Alternative (already integrated):
    Use `run_kikit_fab` with `no_drc=True` — KiKit's JLCPCB fab module
    generates the same BOM+CPL files from a .kicad_pcb without needing
    the action plugin.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path


# Candidate plugin dirs (checked in order)
_PLUGIN_DIRS = [
    Path.home() / ".local/share/kicad/9.0/scripting/plugins/kicad_jlcpcb_tools",
    Path.home() / ".local/share/kicad/8.0/scripting/plugins/kicad_jlcpcb_tools",
    Path("/usr/share/kicad/scripting/plugins/kicad_jlcpcb_tools"),
]


def _find_plugin() -> Path | None:
    """Return the plugin root dir if installed, else None."""
    for d in _PLUGIN_DIRS:
        if (d / "__init__.py").exists() or (d / "plugin.py").exists():
            return d
    return None


class JlcpcbWrapper:
    """Wrapper around kicad-jlcpcb-tools action plugin.

    Falls back gracefully to a MISSING_PLUGIN error if the plugin is not
    installed, directing the caller to use ``run_kikit_fab`` instead.
    """

    @classmethod
    def from_env(cls) -> "JlcpcbWrapper":
        """Construct from environment. No credentials needed."""
        return cls()

    def annotate(
        self,
        schematic_path: str,
        out_dir: str | None = None,
    ) -> dict:
        """Annotate a KiCad schematic with LCSC part numbers and export BOM/CPL.

        Requires kicad-jlcpcb-tools plugin to be installed in KiCad's plugin
        directory. See module docstring for installation instructions.

        Args:
            schematic_path: Absolute path to the .kicad_sch file.
            out_dir:        Optional output directory for BOM/CPL files.
                            Defaults to the schematic's parent directory.

        Returns:
            On success:
                ``{"bom_path": str, "cpl_path": str, "rc": 0}``
            On missing plugin:
                ``{"rc": 2, "error": "MISSING_PLUGIN", "instructions": str,
                   "alternative": "run_kikit_fab"}``
            On subprocess failure:
                ``{"rc": int, "error": str, "stderr": str}``
        """
        plugin_dir = _find_plugin()
        if plugin_dir is None:
            return {
                "rc": 2,
                "error": "MISSING_PLUGIN",
                "instructions": (
                    "Install via KiCad Plugin Manager (search 'JLCPCB Tools') "
                    "or: git clone https://github.com/Bouni/kicad-jlcpcb-tools "
                    f"{_PLUGIN_DIRS[0]}"
                ),
                "alternative": (
                    "Use run_kikit_fab (MCP tool) — generates equivalent "
                    "JLCPCB BOM+CPL from .kicad_pcb without the action plugin."
                ),
            }

        # Plugin found — attempt CLI invocation if it exposes one
        cli_script = plugin_dir / "cli.py"
        out = Path(out_dir) if out_dir else Path(schematic_path).parent
        out.mkdir(parents=True, exist_ok=True)

        if cli_script.exists():
            r = subprocess.run(
                ["python3", str(cli_script), str(schematic_path), "--output", str(out)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            bom = next(out.glob("*BOM*.csv"), None)
            cpl = next(out.glob("*CPL*.csv"), None)
            return {
                "bom_path": str(bom) if bom else None,
                "cpl_path": str(cpl) if cpl else None,
                "rc": r.returncode,
                "stderr": r.stderr[:1000],
            }

        # Plugin dir exists but no CLI — document the gap
        return {
            "rc": 2,
            "error": "NO_CLI_MODE",
            "plugin_dir": str(plugin_dir),
            "note": (
                "kicad-jlcpcb-tools does not expose a CLI entry point. "
                "Use the KiCad GUI plugin, or use run_kikit_fab for headless BOM/CPL."
            ),
            "alternative": "run_kikit_fab",
        }

    def is_installed(self) -> bool:
        """Return True if the kicad-jlcpcb-tools plugin directory is present."""
        return _find_plugin() is not None
