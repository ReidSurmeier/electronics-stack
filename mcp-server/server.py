"""MCP server: electronics

Exposes the verification stack as MCP tools so Claude Code (or any MCP client)
can call them directly in any session.

Tools:
    - verify_project        : run full verify.py against a project dir
    - run_erc               : kicad-cli ERC only
    - audit_connectivity    : passive-pin float audit
    - audit_power_budget    : rail load analysis
    - audit_sourcing        : BOM URL health + optional API lifecycle
    - validate_pi_manifest  : Pi GPIO/I2C/overlay validator
    - lookup_part           : Digikey/Mouser/Octopart MPN search
    - pin_match_datasheet   : symbol pins vs datasheet PDF
    - run_kibot             : KiBot pipeline runner
    - parse_schematic       : structural dump of a kicad_sch
    - nexar_render          : render an Altium 365 PCB via Nexar Design API
    - nexar_list_projects   : list projects in an Altium 365 workspace
    - run_kikit_panelize    : panelize a .kicad_pcb via KiKit
    - run_kikit_fab         : generate JLCPCB fab package via KiKit
    - run_kikit_present     : generate KiKit project presentation webpage
    - generate_schematic_skidl : generate a KiCad netlist/schematic from a declarative parts+nets spec

Run:
    python3 ~/electronics-stack/mcp-server/server.py

Add to Claude Code's MCP config (~/.claude.json or settings.json):
    {
      "mcpServers": {
        "electronics": {
          "command": "python3",
          "args": ["/home/reidsurmeier/electronics-stack/mcp-server/server.py"]
        }
      }
    }
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path

# add scripts dir to path
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

import sch_parser
import connectivity_audit
import power_budget
import sourcing_health
import pi_dts_validator
import datasheet_pinmatch


server = Server("electronics-verify")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="verify_project",
            description="Run the full electronics verification stack on a KiCad project directory. Returns ERC, connectivity, power budget, sourcing, and Pi-DTS results in JSON.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_dir": {"type": "string", "description": "Absolute path to a directory containing a .kicad_pro file."},
                    "checks": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["erc", "conn", "power", "sourcing", "pi", "kibot"]},
                        "description": "Optional list of checks to run. Default = all."
                    }
                },
                "required": ["project_dir"]
            }
        ),
        Tool(
            name="run_erc",
            description="Run kicad-cli sch erc on a schematic. Returns error/warning counts split into design vs environmental.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schematic_path": {"type": "string", "description": "Absolute path to a .kicad_sch file."}
                },
                "required": ["schematic_path"]
            }
        ),
        Tool(
            name="audit_connectivity",
            description="Walk every (instance, pin) tuple in a schematic and flag floating pins — including the passive-typed pins that ERC silently passes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schematic_path": {"type": "string", "description": "Absolute path to a .kicad_sch file."}
                },
                "required": ["schematic_path"]
            }
        ),
        Tool(
            name="audit_power_budget",
            description="Analyze rail loads vs capacity from a power_budget.yaml. Flags rails with negative or low headroom.",
            inputSchema={
                "type": "object",
                "properties": {
                    "yaml_path": {"type": "string"}
                },
                "required": ["yaml_path"]
            }
        ),
        Tool(
            name="audit_sourcing",
            description="Walk a BOM xlsx Sourcing sheet, hit each URL, flag 404s. Optionally enrich with Digikey/Mouser API metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "xlsx_path": {"type": "string"},
                    "with_api": {"type": "boolean", "default": False}
                },
                "required": ["xlsx_path"]
            }
        ),
        Tool(
            name="validate_pi_manifest",
            description="Validate a Pi project's pi_manifest.yaml: GPIO double-use, I2C addr conflicts, overlay/pin consistency.",
            inputSchema={
                "type": "object",
                "properties": {"yaml_path": {"type": "string"}},
                "required": ["yaml_path"]
            }
        ),
        Tool(
            name="lookup_part",
            description="Search Digikey, Mouser, and/or Octopart for an MPN. Returns availability, lifecycle status, pricing, datasheet URL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mpn": {"type": "string"},
                    "providers": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["digikey", "mouser", "octopart"]},
                        "default": ["digikey", "mouser", "octopart"]
                    }
                },
                "required": ["mpn"]
            }
        ),
        Tool(
            name="pin_match_datasheet",
            description="Cross-check a KiCad symbol's pin name table against a datasheet PDF. Flags mismatches and renames (e.g. SCL vs SCLK).",
            inputSchema={
                "type": "object",
                "properties": {
                    "sym_lib_path": {"type": "string"},
                    "symbol_name": {"type": "string"},
                    "datasheet_pdf_path": {"type": "string"}
                },
                "required": ["sym_lib_path", "symbol_name", "datasheet_pdf_path"]
            }
        ),
        Tool(
            name="run_kibot",
            description="Run a KiBot CI pipeline against a project. Requires .kibot.yaml in the project root.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_dir": {"type": "string"},
                    "config": {"type": "string", "description": "Optional path to a kibot config YAML (defaults to .kibot.yaml in project_dir)."}
                },
                "required": ["project_dir"]
            }
        ),
        Tool(
            name="parse_schematic",
            description="Return a structural summary of a KiCad schematic: title, rev, instance count, refdes list, label list, wire count.",
            inputSchema={
                "type": "object",
                "properties": {"schematic_path": {"type": "string"}},
                "required": ["schematic_path"]
            }
        ),
        Tool(
            name="nexar_render",
            description=(
                "Render a PCB design via the Nexar Design API. Pulls a GLB 3D mesh "
                "and a JSON dump of PCB primitives (pads, tracks, vias, layer stack, outline) "
                "from an Altium 365 workspace. NOTE: source-of-truth must be Altium 365 — "
                "this API does NOT accept KiCad uploads. Requires Nexar app with `design.domain` scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Nexar project ID. Either this or project_name required."},
                    "project_name": {"type": "string", "description": "Lookup project by name in the (default) workspace."},
                    "workspace_url": {"type": "string", "description": "Optional Altium 365 workspace URL. Defaults to user's default workspace."},
                    "out_dir": {"type": "string", "description": "Output directory for .glb / .pcb.json / .meta.json."},
                    "include_glb": {"type": "boolean", "default": True},
                    "include_primitives": {"type": "boolean", "default": True}
                },
                "required": ["out_dir"]
            }
        ),
        Tool(
            name="run_kikit_panelize",
            description="Panelize a .kicad_pcb file using a KiKit preset. Produces a panel-ready .kicad_pcb in out_dir.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_path": {"type": "string", "description": "Absolute path to source .kicad_pcb"},
                    "out_dir": {"type": "string", "description": "Output directory (default: same dir as board)"},
                    "preset": {"type": "string", "description": "KiKit panelization preset (default: tightgrid-2x2)"},
                },
                "required": ["board_path"],
            },
        ),
        Tool(
            name="run_kikit_fab",
            description="Generate a JLCPCB-ready fabrication package (Gerbers, BOM, CPL) from a .kicad_pcb.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_path": {"type": "string", "description": "Absolute path to source .kicad_pcb"},
                    "out_dir": {"type": "string", "description": "Output directory for fab package"},
                    "no_drc": {"type": "boolean", "description": "Skip DRC before generating (default: true)", "default": True},
                },
                "required": ["board_path"],
            },
        ),
        Tool(
            name="run_kikit_present",
            description="Generate a KiKit project presentation webpage with PCB renders. Requires X display for renders.",
            inputSchema={
                "type": "object",
                "properties": {
                    "board_path": {"type": "string", "description": "Absolute path to source .kicad_pcb"},
                    "out_dir": {"type": "string", "description": "Output directory for HTML assets"},
                    "description": {"type": "string", "description": "Short project description for the page"},
                },
                "required": ["board_path"],
            },
        ),
        Tool(
            name="nexar_list_projects",
            description="List visible Nexar Design projects (Altium 365 workspaces and projects). Requires `design.domain` scope.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_url": {"type": "string", "description": "Optional. Defaults to default workspace; pass empty to list workspaces only."},
                    "list_workspaces_only": {"type": "boolean", "default": False}
                }
            }
        ),
        Tool(
            name="generate_schematic_skidl",
            description="Generate a KiCad netlist (.net) and optional schematic (.kicad_sch) from a declarative parts+nets spec using skidl. Falls back to netlist-only on KiCad 9 compatibility issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "parts": {
                        "type": "array",
                        "description": "List of parts: [{lib, name, refdes, footprint?}]",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lib": {"type": "string"},
                                "name": {"type": "string"},
                                "refdes": {"type": "string"},
                                "footprint": {"type": "string"},
                            },
                            "required": ["lib", "name", "refdes"],
                        },
                    },
                    "nets": {
                        "type": "array",
                        "description": "List of nets: [{name, connections: [{refdes, pin}]}]",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "connections": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "refdes": {"type": "string"},
                                            "pin": {"type": "string"},
                                        },
                                        "required": ["refdes", "pin"],
                                    },
                                },
                            },
                            "required": ["name"],
                        },
                    },
                    "out_dir": {"type": "string", "description": "Output directory for generated files"},
                },
                "required": ["parts", "nets", "out_dir"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "verify_project":
            import subprocess
            args = ["python3", str(SCRIPTS / "verify.py"), arguments["project_dir"], "--json"]
            for c in arguments.get("checks", []):
                args.append(f"--{c}")
            r = subprocess.run(args, capture_output=True, text=True, timeout=600)
            return [TextContent(type="text", text=r.stdout or r.stderr)]

        if name == "run_erc":
            import subprocess
            sch = arguments["schematic_path"]
            rpt_path = Path(sch).with_suffix(".erc.rpt")
            r = subprocess.run(
                ["kicad-cli", "sch", "erc", "--severity-error", "--severity-warning",
                 "-o", str(rpt_path), sch],
                capture_output=True, text=True, timeout=120
            )
            text = rpt_path.read_text() if rpt_path.exists() else ""
            errors = text.count("; error")
            real_errors = sum(1 for line in text.split("\n") if "; error" in line and "footprint_link_issues" not in line)
            return [TextContent(type="text", text=json.dumps({
                "errors_total": errors, "errors_design": real_errors,
                "report_path": str(rpt_path),
                "report_excerpt": text[:4000]
            }, indent=2))]

        if name == "audit_connectivity":
            sch = sch_parser.parse_schematic(arguments["schematic_path"])
            findings = connectivity_audit.audit(sch)
            return [TextContent(type="text", text=json.dumps(findings, indent=2))]

        if name == "audit_power_budget":
            findings = power_budget.analyze(power_budget.load_budget(arguments["yaml_path"]))
            return [TextContent(type="text", text=json.dumps(findings, indent=2))]

        if name == "audit_sourcing":
            out = sourcing_health.audit(arguments["xlsx_path"])
            return [TextContent(type="text", text=json.dumps(out, indent=2))]

        if name == "validate_pi_manifest":
            import yaml as _yaml
            findings = pi_dts_validator.validate(_yaml.safe_load(open(arguments["yaml_path"])))
            return [TextContent(type="text", text=json.dumps(findings, indent=2))]

        if name == "lookup_part":
            mpn = arguments["mpn"]
            providers = arguments.get("providers") or ["digikey", "mouser", "octopart"]
            results = {}
            if "digikey" in providers:
                try:
                    from digikey_client import DigikeyClient
                    results["digikey"] = DigikeyClient.from_env().keyword_search(mpn, limit=3)
                except Exception as e:
                    results["digikey"] = {"error": str(e)}
            if "mouser" in providers:
                try:
                    from mouser_client import MouserClient
                    results["mouser"] = MouserClient.from_env().keyword_search(mpn, records=3)
                except Exception as e:
                    results["mouser"] = {"error": str(e)}
            if "octopart" in providers:
                try:
                    from octopart_client import OctopartClient
                    results["octopart"] = OctopartClient.from_env().search_mpn(mpn, limit=3)
                except Exception as e:
                    results["octopart"] = {"error": str(e)}
            return [TextContent(type="text", text=json.dumps(results, indent=2)[:8000])]

        if name == "pin_match_datasheet":
            sp = datasheet_pinmatch.get_symbol_pins(arguments["sym_lib_path"], arguments["symbol_name"])
            pp = datasheet_pinmatch.extract_pins_from_pdf(arguments["datasheet_pdf_path"])
            findings = datasheet_pinmatch.cross_check(sp, pp)
            return [TextContent(type="text", text=json.dumps({
                "symbol_pins": sp, "pdf_pins": pp[:50], "findings": findings
            }, indent=2))]

        if name == "run_kibot":
            import subprocess
            pd = Path(arguments["project_dir"])
            cfg = Path(arguments.get("config") or pd / ".kibot.yaml")
            out_dir = pd / "kibot-out"
            r = subprocess.run(["kibot", "-c", str(cfg), "-d", str(out_dir)],
                               cwd=pd, capture_output=True, text=True, timeout=900)
            return [TextContent(type="text", text=json.dumps({
                "rc": r.returncode,
                "stdout_tail": r.stdout[-2000:],
                "stderr_tail": r.stderr[-2000:],
                "out": str(out_dir)
            }, indent=2))]

        if name == "nexar_render":
            from nexar_render import render as _nexar_render
            out = _nexar_render(
                project_id=arguments.get("project_id"),
                out_dir=Path(arguments["out_dir"]),
                workspace_url=arguments.get("workspace_url"),
                project_name=arguments.get("project_name"),
                download_glb=arguments.get("include_glb", True),
                dump_primitives=arguments.get("include_primitives", True),
            )
            return [TextContent(type="text", text=json.dumps(out, indent=2))]

        if name == "nexar_list_projects":
            from nexar_render import NexarDesignClient
            client = NexarDesignClient.from_env()
            if arguments.get("list_workspaces_only"):
                return [TextContent(type="text", text=json.dumps(client.workspaces(), indent=2))]
            ws_url = arguments.get("workspace_url")
            if not ws_url:
                wss = client.workspaces()
                if not wss:
                    return [TextContent(type="text", text=json.dumps({"error": "No workspaces visible to this app"}))]
                ws_url = next((w for w in wss if w.get("isDefault")), wss[0])["url"]
            return [TextContent(type="text", text=json.dumps({
                "workspace_url": ws_url,
                "projects": client.projects(ws_url),
            }, indent=2))]

        if name == "parse_schematic":
            sch = sch_parser.parse_schematic(arguments["schematic_path"])
            return [TextContent(type="text", text=json.dumps({
                "title": sch.title, "rev": sch.rev,
                "instance_count": len(sch.instances),
                "label_count": len(sch.labels),
                "wire_count": len(sch.wires),
                "no_connect_count": len(sch.no_connects),
                "refdes": sorted(i.refdes for i in sch.instances),
            }, indent=2))]

        if name == "run_kikit_panelize":
            from kikit_wrapper import KikitWrapper
            board = arguments["board_path"]
            out = arguments.get("out_dir") or str(Path(board).parent / "kikit-panel")
            preset = arguments.get("preset", "tightgrid-2x2")
            result = KikitWrapper.from_env().panelize(board, out, preset)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "run_kikit_fab":
            from kikit_wrapper import KikitWrapper
            board = arguments["board_path"]
            out = arguments.get("out_dir") or str(Path(board).parent / "kikit-fab")
            no_drc = arguments.get("no_drc", True)
            result = KikitWrapper.from_env().fab_jlcpcb(board, out, no_drc)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "run_kikit_present":
            from kikit_wrapper import KikitWrapper
            board = arguments["board_path"]
            out = arguments.get("out_dir") or str(Path(board).parent / "kikit-present")
            desc = arguments.get("description", "PCB project")
            result = KikitWrapper.from_env().present(board, out, desc)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "generate_schematic_skidl":
            from skidl_wrapper import SkidlWrapper
            result = SkidlWrapper.from_env().generate_schematic(
                parts=arguments["parts"],
                nets=arguments["nets"],
                out_dir=arguments["out_dir"],
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        import traceback
        return [TextContent(type="text", text=f"ERROR in {name}: {e}\n{traceback.format_exc()}")]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
