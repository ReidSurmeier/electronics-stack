# Electronics Stack installation

## Current workstation evidence

Audit date: 2026-07-31.

The current WSL host did not expose the following executables on `PATH`:

- `kicad-cli`
- `kibot`
- `kikit`
- `generate_interactive_bom`
- `ngspice`
- `kintree`
- `docling`

The system Python also lacked the repository's declared test dependencies,
including MCP, OpenPyXL, pdfplumber, RapidFuzz, ReportLab, sexpdata, and SKiDL.
This means a clean environment must be installed before the historical
pipeline results can be revalidated on this host.

## Python environment

Create an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[test,design]'
.venv/bin/python -m pytest -q
```

The base dependencies cover the deterministic Python checks and MCP adapter.
The `design` extra installs SKiDL. KiCad, KiBot, KiKit, InteractiveHtmlBom,
ngspice, and other system integrations remain optional and must report an
explicit unavailable or skipped result when absent.

## External tools

External repositories are not committed as orphan Git links. Install or clone
them explicitly when their integration is needed:

| Tool | Purpose | Upstream |
| --- | --- | --- |
| KiCad | Canonical ERC and board tooling | <https://www.kicad.org/> |
| KiBot | KiCad output automation | <https://github.com/INTI-CMNB/KiBot> |
| KiKit | Panelization and fabrication output | <https://github.com/yaqwsx/KiKit> |
| InteractiveHtmlBom | Assembly visualization | <https://github.com/openscopeproject/InteractiveHtmlBom> |
| Ki-nTree | Part and inventory integration | <https://github.com/sparkmicro/Ki-nTree> |
| Kiri | Visual KiCad history comparison | <https://github.com/leoheck/kiri> |
| Nexar render demo | Design API reference implementation | <https://github.com/NexarDeveloper/nexar-design-render-demo> |

## Provider configuration

Provider credentials belong in host configuration with mode `0600`, never in
the repository. Network validation is opt-in because provider quotas and
access conditions vary. `--with-api` permits distributor API calls, while
`--with-browserbase` independently permits managed-browser escalation. The
default sourcing command can still issue ordinary HTTP requests to URLs in the
BOM; it does not use either provider mechanism. See ADR 0002.

The LCSC client is offline during normal construction. Populate or refresh its
jlcparts database only through the explicit refresh operation documented by
`scripts/lcsc_client.py`; importing the client never downloads data.

### Current LCSC evidence

On 2026-07-31, 7-Zip 23.01 was installed from the Ubuntu package repository.
The explicit refresh reused the existing 13-part archive and extracted a
5.6 GB SQLite database. The refreshed upstream schema uses
`jlc_components`, not the legacy `components`/`manufacturers` tables.

Validation on that database reported:

- SQLite `PRAGMA quick_check`: `ok`
- 7,157,071 component rows
- C8734 ID lookup: found
- exact-MPN keyword lookup: three results at a limit of three
- C8734 price parsing: six quantity tiers

These counts are dated cache evidence, not a stable upstream invariant. The
client supports both the current and legacy table layouts through fixture
tests and fails clearly when it encounters an unknown schema.

Nexar Supply and Design APIs use different OAuth scopes and separate caches.
The Design API operates on Altium 365 projects; it does not accept KiCad
uploads. Pure-KiCad rendering must use KiCad's own export tools.

## Historical note

The previous version of this document recorded successful installs on
2026-04-30, including KiCad 9.0.8, KiBot, KiKit, InteractiveHtmlBom, Docling,
Ki-nTree, PySpice, and ngspice. Those observations describe an earlier
environment and are not current-host verification. Recover that revision from
Git history when exact historical commands or failure text are needed.
