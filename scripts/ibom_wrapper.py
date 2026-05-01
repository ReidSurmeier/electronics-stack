"""InteractiveHtmlBom wrapper for electronics-stack MCP server.

Generates an interactive HTML BOM from a .kicad_pcb file via the
InteractiveHtmlBom CLI module.

The DISPLAY environment variable is forced to empty string so the
underlying pcbnew assertion on "no display" is suppressed and the
module runs headless.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


class IbomWrapper:
    """Wrapper around InteractiveHtmlBom.generate_interactive_bom."""

    # ---------------------------------------------------------------------------
    # Construction
    # ---------------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "IbomWrapper":
        """Construct from environment. No credentials required."""
        return cls()

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def render_interactive_bom(
        self,
        pcb_path: str,
        out_dir: str,
        extra_args: list[str] | None = None,
    ) -> dict:
        """Render an interactive HTML BOM for a KiCad PCB file.

        Args:
            pcb_path:   Absolute path to the .kicad_pcb file.
            out_dir:    Directory where the generated HTML will be written.
            extra_args: Optional additional CLI arguments passed to
                        ``generate_interactive_bom`` (e.g. ``["--dark-mode"]``).

        Returns:
            ``{"html_path": str|None, "rc": int, "stderr": str}``

            ``html_path`` is the first ``*.html`` found in *out_dir* after
            the run, or ``None`` if nothing was produced.
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        cmd = [
            "python3", "-m", "InteractiveHtmlBom.generate_interactive_bom",
            "--no-browser",
            "--dest-dir", str(out),
        ] + (extra_args or []) + [str(pcb_path)]

        env = {**os.environ, "DISPLAY": ""}

        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        # Find generated HTML
        html_files = sorted(out.glob("*.html"))
        html_path = str(html_files[0]) if html_files else None

        return {
            "html_path": html_path,
            "rc": r.returncode,
            "stderr": r.stderr[:1000],
        }
