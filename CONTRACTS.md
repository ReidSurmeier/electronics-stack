# CONTRACTS.md — Electronics Stack Expansion Pipeline

## File Ownership

| Phase | Specialist | Files Owned |
|-------|-----------|-------------|
| 1 | lcsc-specialist | scripts/lcsc_client.py, mcp-server/server.py (lcsc branch only) |
| 2 | audit-specialist (x4 subagents) | AUDIT.md |
| 3 | farnell-specialist | scripts/farnell_client.py, mcp-server/server.py (farnell branch only) |
| 4 | integration-specialist | scripts/skidl_wrapper.py, scripts/ibom_wrapper.py, scripts/jlcpcb_wrapper.py, mcp-server/server.py (integration branch) |
| 5 | pipeline-specialist | scripts/design_pipeline.py, mcp-server/server.py (pipeline branch) |
| 6 | qa-specialist | PIPELINE-RUN.md |
| 7 | fixloop-specialist | PIPELINE-FINAL.md, scripts/*.py (bug fixes only) |

## Interfaces

### LcscClient (scripts/lcsc_client.py)
```python
class LcscClient:
    @classmethod
    def from_env(cls) -> LcscClient: ...
    def keyword_search(self, mpn: str, limit: int = 5) -> list[dict]: ...
    def lookup_lcsc_id(self, c_code: str) -> dict: ...

# Return schema per part:
{
  "mpn": str,
  "manufacturer": str,
  "lcsc_id": str,           # e.g. "C8734"
  "basic_extended": str,    # "Basic" | "Extended" | "Preferred"
  "stock": int,
  "price_tiers": [{"qty": int, "price_usd": float}],
  "package": str,
  "datasheet_url": str | None
}
```

### FarnellClient (scripts/farnell_client.py)
```python
class FarnellClient:
    @classmethod
    def from_env(cls) -> FarnellClient: ...
    def keyword_search(self, mpn: str, limit: int = 3) -> list[dict]: ...

# Return schema per part:
{
  "mpn": str,
  "manufacturer": str,
  "sku": str,
  "stock": int,
  "price_tiers": [{"qty": int, "price_usd": float}],
  "datasheet_url": str | None,
  "image_url": str | None
}
```

### MCP lookup_part extension
- providers enum adds: "lcsc", "farnell"
- Each provider: try/except, on missing key returns {"error": "FARNELL_API_KEY not set"}
- lcsc branch: if "lcsc" in providers -> LcscClient.from_env().keyword_search(mpn)
- farnell branch: if "farnell" in providers -> FarnellClient.from_env().keyword_search(mpn)

### AUDIT.md format
Ranked table per tool: name | license | install | ip-block-risk | last-commit | scope-fit | recommendation

### design_pipeline.py MCP tool
```python
# MCP tool: design_pcb_from_spec
# Input: spec (str), out_dir (str)
# Output files: {out_dir}/parts.json, schematic.kicad_sch, bom.xlsx, verify_report.json
```

## Success Criteria

| Phase | Pass Condition |
|-------|---------------|
| 1 | LcscClient imports, keyword_search("STM32F103C8T6") returns ≥1 result with lcsc_id |
| 2 | AUDIT.md written, ≥12 tools rated, top 3 INTEGRATE picks identified |
| 3 | FarnellClient imports, gracefully errors on missing key, returns valid data with key set |
| 4 | 3 wrappers importable, 3 MCP tools registered and callable |
| 5 | design_pcb_from_spec produces all 4 output files for a test spec |
| 6 | PIPELINE-RUN.md covers 25 projects with pass/fail per check |
| 7 | PIPELINE-FINAL.md: each project PASS/SKIP/FAIL with root cause |

## Branches
All specialists commit to: `pipeline/electronics-expansion/{phase}-{domain}`
Base: main (or current HEAD)
