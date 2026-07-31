"""Public schema and dispatch contracts for the stdio MCP adapter."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp-server" / "server.py"


def _load_server_module():
    spec = importlib.util.spec_from_file_location("electronics_mcp_server", SERVER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lookup_part_schema_lists_every_implemented_provider() -> None:
    module = _load_server_module()
    tools = asyncio.run(module.list_tools())
    lookup = next(tool for tool in tools if tool.name == "lookup_part")

    providers = lookup.inputSchema["properties"]["providers"]["items"]["enum"]
    assert providers == ["digikey", "mouser", "octopart", "lcsc", "farnell"]
    assert lookup.inputSchema["properties"]["providers"]["default"] == ["lcsc"]


def test_lookup_part_dispatches_offline_lcsc_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_server_module()
    monkeypatch.setenv("ELECTRONICS_LCSC_DB", str(tmp_path / "missing.sqlite3"))

    content = asyncio.run(
        module.call_tool(
            "lookup_part",
            {"mpn": "STM32F103C8T6", "providers": ["lcsc"]},
        )
    )
    result = json.loads(content[0].text)

    assert list(result) == ["lcsc"]
    assert "refresh" in result["lcsc"]["error"]


def test_adapter_errors_are_structured_without_tracebacks(tmp_path: Path) -> None:
    module = _load_server_module()

    content = asyncio.run(
        module.call_tool(
            "run_erc",
            {"schematic_path": str(tmp_path / "missing.kicad_sch")},
        )
    )
    text = content[0].text
    result = json.loads(text)

    assert result["tool"] == "run_erc"
    assert result["error"]
    assert "Traceback" not in text
    assert "environ" not in text


def test_audit_sourcing_schema_and_dispatch_require_explicit_network_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_server_module()
    tools = asyncio.run(module.list_tools())
    audit_tool = next(tool for tool in tools if tool.name == "audit_sourcing")

    properties = audit_tool.inputSchema["properties"]
    assert properties["with_api"]["default"] is False
    assert properties["with_browserbase"]["default"] is False

    calls: list[tuple[str, bool, bool]] = []

    def fake_audit(
        xlsx_path: str,
        *,
        with_api: bool = False,
        with_browserbase: bool = False,
    ) -> dict:
        calls.append((xlsx_path, with_api, with_browserbase))
        return {"rows_checked": 0, "findings": []}

    monkeypatch.setattr(module.sourcing_health, "audit", fake_audit)
    content = asyncio.run(
        module.call_tool(
            "audit_sourcing",
            {
                "xlsx_path": "fixtures/BOM.xlsx",
                "with_api": True,
                "with_browserbase": True,
            },
        )
    )

    assert calls == [("fixtures/BOM.xlsx", True, True)]
    assert json.loads(content[0].text)["rows_checked"] == 0
