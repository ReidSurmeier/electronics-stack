"""KiKit wrapper for electronics-stack MCP server.

Provides panelization, fab package generation (JLCPCB), and project
presentation via the KiKit CLI (v1.8.0+).

All methods invoke the kikit CLI as a subprocess to avoid import-time
side effects from the kikit Python API.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


def _run_kikit(command: Sequence[str]) -> tuple[int, str]:
    """Run KiKit with bounded, sanitized failure semantics."""
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        return 127, "KiKit executable is not available on PATH"
    except subprocess.TimeoutExpired:
        return 124, "KiKit timed out after 300 seconds"
    return result.returncode, (result.stderr or "")[:2000]


class KikitWrapper:
    """Thin subprocess wrapper around the KiKit CLI."""

    # ---------------------------------------------------------------------------
    # Construction
    # ---------------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "KikitWrapper":
        """Construct from environment. KiKit needs no credentials."""
        return cls()

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def panelize(
        self,
        board_path: str,
        out_dir: str,
        preset: str = "tightgrid-2x2",
    ) -> dict:
        """Panelize a .kicad_pcb using a KiKit preset.

        Args:
            board_path: Absolute path to the source .kicad_pcb file.
            out_dir:    Directory where the panelized .kicad_pcb will be written.
            preset:     KiKit panelization preset name (default: tightgrid-2x2).

        Returns:
            {"output": str, "rc": int, "stderr": str}
        """
        board = Path(board_path)
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        out_path = out / f"{board.stem}-panel.kicad_pcb"

        if not board.is_file():
            return {
                "output": str(out_path),
                "rc": 2,
                "stderr": f"board does not exist: {board}",
            }

        rc, stderr = _run_kikit(
            ["kikit", "panelize", "--preset", preset, str(board), str(out_path)]
        )
        return {
            "output": str(out_path),
            "rc": rc,
            "stderr": stderr,
        }

    def fab_jlcpcb(
        self,
        board_path: str,
        out_dir: str,
        no_drc: bool = True,
    ) -> dict:
        """Generate a JLCPCB-ready fabrication package.

        Produces Gerbers, drill files, BOM, and CPL (pick-and-place) in
        ``out_dir``.

        Args:
            board_path: Absolute path to the source .kicad_pcb file.
            out_dir:    Output directory for the fab package.
            no_drc:     Skip DRC before generating (default: True — DRC often
                        fails on third-party designs due to missing design rules).

        Returns:
            {"output": str, "rc": int, "stderr": str}
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        board = Path(board_path)

        if not board.is_file():
            return {
                "output": str(out),
                "rc": 2,
                "stderr": f"board does not exist: {board}",
            }

        cmd = ["kikit", "fab", "jlcpcb"]
        if no_drc:
            cmd.append("--no-drc")
        cmd += [str(board), str(out)]

        rc, stderr = _run_kikit(cmd)
        return {
            "output": str(out),
            "rc": rc,
            "stderr": stderr,
        }

    def present(
        self,
        board_path: str,
        out_dir: str,
        description: str = "PCB project",
    ) -> dict:
        """Generate a KiKit project presentation webpage.

        Args:
            board_path:  Absolute path to the source .kicad_pcb file.
            out_dir:     Output directory for the generated HTML/assets.
            description: Short text description for the page.

        Returns:
            {"output": str, "rc": int, "stderr": str, "note": str}

        Note:
            Rendering requires an X display. In headless environments the
            command may fail or produce a page without PCB renders.
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        board = Path(board_path)
        note = (
            "kikit present requires X display for PCB renders; "
            "headless may produce empty renders"
        )

        if not board.is_file():
            return {
                "output": str(out),
                "rc": 2,
                "stderr": f"board does not exist: {board}",
                "note": note,
            }

        rc, stderr = _run_kikit(
            [
                "kikit",
                "present",
                "boardpage",
                "-b",
                str(board),
                "-d",
                description,
                "-o",
                str(out),
            ]
        )
        return {
            "output": str(out),
            "rc": rc,
            "stderr": stderr,
            "note": note,
        }
