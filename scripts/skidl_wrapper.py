"""skidl wrapper for electronics-stack MCP server.

Provides programmatic KiCad schematic / netlist generation via the
skidl Python library (v2.2.3+).

skidl maintains global state; always call skidl.reset() before a new
circuit so concurrent (or sequential) calls don't bleed into each other.

Import order matters: SkidlLogger must be set as the logging class
*before* the main skidl package is imported, otherwise _create_logger
falls back to plain Logger and crashes on bare_error/set_trace_depth.
"""
from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path

# Silence KICAD dir warnings before any skidl import
warnings.filterwarnings("ignore", message=".*KICAD.*SYMBOL.*DIR.*")
os.environ.setdefault("KICAD9_SYMBOL_DIR", "/usr/share/kicad/symbols")

# Must set SkidlLogger class BEFORE importing the skidl package so that
# _create_logger() creates a proper SkidlLogger (not a plain Logger).
from skidl.logger import SkidlLogger as _SkidlLogger  # noqa: E402
logging.setLoggerClass(_SkidlLogger)

import skidl  # noqa: E402  (must come after setLoggerClass)


class SkidlWrapper:
    """Wrapper around skidl for netlist / schematic generation."""

    # ---------------------------------------------------------------------------
    # Construction
    # ---------------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "SkidlWrapper":
        """Construct from environment.

        Ensures KICAD9_SYMBOL_DIR is set so skidl can resolve standard
        KiCad 9 symbol libraries.
        """
        os.environ.setdefault("KICAD9_SYMBOL_DIR", "/usr/share/kicad/symbols")
        return cls()

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _reset() -> None:
        """Reset skidl global circuit state."""
        skidl.reset()

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def generate_netlist(
        self,
        parts: list[dict],
        nets: list[dict],
        out_dir: str,
    ) -> dict:
        """Generate a KiCad netlist from a declarative parts + nets spec.

        Args:
            parts: List of part descriptors::

                [{"lib": "Device", "name": "R", "refdes": "R1",
                  "footprint": "R_0805"}]

            nets: List of net descriptors::

                [{"name": "VCC", "connections": [{"refdes": "R1", "pin": "1"}]}]

            out_dir: Directory where ``netlist.net`` will be written.

        Returns:
            On success: ``{"netlist_path": str, "rc": 0, "warnings": list[str]}``
            On failure: ``{"rc": 1, "error": str}``
        """
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        netlist_path = str(Path(out_dir) / "netlist.net")
        captured: list[str] = []

        try:
            self._reset()
            part_map: dict[str, object] = {}

            for p in parts:
                kwargs: dict = {}
                if p.get("footprint"):
                    kwargs["footprint"] = p["footprint"]
                try:
                    part = skidl.Part(p["lib"], p["name"], **kwargs)
                    part.ref = p["refdes"]
                    part_map[p["refdes"]] = part
                except Exception as ex:
                    captured.append(f"Part {p['refdes']}: {ex}")

            for n in nets:
                net = skidl.Net(n["name"])
                for conn in n.get("connections", []):
                    ref, pin = conn["refdes"], conn["pin"]
                    if ref in part_map:
                        try:
                            part_map[ref][pin] += net
                        except Exception as ex:
                            captured.append(f"Net {n['name']} {ref}.{pin}: {ex}")

            skidl.generate_netlist(file_=netlist_path)
            return {"netlist_path": netlist_path, "rc": 0, "warnings": captured}

        except Exception as exc:
            return {"rc": 1, "error": str(exc)}
        finally:
            try:
                self._reset()
            except Exception:
                pass

    def generate_schematic(
        self,
        parts: list[dict],
        nets: list[dict],
        out_dir: str,
    ) -> dict:
        """Generate a KiCad schematic (.kicad_sch) from a declarative spec.

        Falls back to netlist-only if skidl's ``generate_schematic`` is
        unavailable or fails (KiCad 9 support is partial in v2.2.3).

        Args:
            parts:   Same schema as :meth:`generate_netlist`.
            nets:    Same schema as :meth:`generate_netlist`.
            out_dir: Output directory.

        Returns:
            ``{"schematic_path": str|None, "netlist_path": str|None,
               "rc": int, "warnings": list[str], "notes": str}``
        """
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        sch_path = str(Path(out_dir) / "schematic.kicad_sch")

        # Always generate netlist first (reliable baseline)
        nl_result = self.generate_netlist(parts, nets, out_dir)
        if nl_result["rc"] != 0:
            return {
                "schematic_path": None,
                "netlist_path": None,
                "rc": 1,
                "warnings": [],
                "notes": nl_result.get("error", "netlist generation failed"),
            }

        netlist_path = nl_result["netlist_path"]

        # Attempt schematic generation
        notes = ""
        sch_out: str | None = None
        try:
            self._reset()
            part_map: dict[str, object] = {}
            for p in parts:
                kwargs: dict = {}
                if p.get("footprint"):
                    kwargs["footprint"] = p["footprint"]
                try:
                    part = skidl.Part(p["lib"], p["name"], **kwargs)
                    part.ref = p["refdes"]
                    part_map[p["refdes"]] = part
                except Exception:
                    pass
            for n in nets:
                net = skidl.Net(n["name"])
                for conn in n.get("connections", []):
                    ref, pin = conn["refdes"], conn["pin"]
                    if ref in part_map:
                        try:
                            part_map[ref][pin] += net
                        except Exception:
                            pass
            skidl.generate_schematic(file_=sch_path)
            if Path(sch_path).exists():
                sch_out = sch_path
                notes = "generate_schematic succeeded"
            else:
                notes = "generate_schematic ran but produced no file; netlist available"
        except AttributeError:
            notes = "skidl.generate_schematic not available in this version; netlist only"
        except Exception as exc:
            notes = f"generate_schematic failed ({exc}); netlist available"
        finally:
            try:
                self._reset()
            except Exception:
                pass

        return {
            "schematic_path": sch_out,
            "netlist_path": netlist_path,
            "rc": 0,
            "warnings": nl_result.get("warnings", []),
            "notes": notes,
        }
