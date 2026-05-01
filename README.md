# electronics-stack

Battle-tested verification + design pipeline for KiCad projects. Built on top of
KiCad 9, KiBot, and a custom Python layer that catches what stock ERC misses.

## Layout

```
electronics-stack/
├── scripts/                 — verification + sourcing scripts
│   ├── verify.py            — top-level CLI, runs the full stack
│   ├── sch_parser.py        — sexp parser for .kicad_sch / .kicad_sym
│   ├── connectivity_audit.py — passive-pin float detector
│   ├── power_budget.py      — rail load analyzer
│   ├── sourcing_health.py   — BOM URL + API checker
│   ├── pi_dts_validator.py  — Pi GPIO / I2C / overlay checker
│   ├── datasheet_pinmatch.py — symbol pins vs datasheet PDF
│   ├── digikey_client.py    — Digikey API v4 client
│   ├── mouser_client.py     — Mouser API v2 client
│   ├── octopart_client.py   — Nexar/Octopart GraphQL client (supply.domain)
│   ├── nexar_render.py      — Nexar Design API renderer (design.domain, GLB + primitives)
│   ├── run_corpus.py        — batch-run verify.py over a directory tree
│   └── install_pre_commit_hook.sh
├── mcp-server/              — MCP server exposing all tools to Claude
│   └── server.py
├── kibot/
│   └── sample.kibot.yaml    — starter KiBot config
├── reverse-engineer/        — spec → KiCad schematic compiler (block-library)
├── test-corpus/             — corpus of OSS PCB designs for stress testing
├── corpus-results/          — aggregated verify outputs from corpus runs
├── tools/                   — community tools (kiri, InteractiveHtmlBom, etc.)
├── .github-workflow-template.yml — CI template for KiCad projects
└── INSTALL.md               — install status of community tools
```

## Quickstart

```bash
# Verify a single project:
python3 ~/electronics-stack/scripts/verify.py /path/to/kicad/project

# Verify with all checks (ERC + connectivity + power + sourcing + Pi DTS + KiBot):
python3 ~/electronics-stack/scripts/verify.py /path/to/project

# Just one check:
python3 ~/electronics-stack/scripts/verify.py /path/to/project --erc
python3 ~/electronics-stack/scripts/verify.py /path/to/project --conn

# JSON output for downstream tools:
python3 ~/electronics-stack/scripts/verify.py /path/to/project --json

# Run on a corpus (every .kicad_pro under a directory tree):
python3 ~/electronics-stack/scripts/run_corpus.py ~/electronics-stack/test-corpus
```

## Per-project config

Drop these next to your `.kicad_pro` to enable optional checks:

- `power_budget.yaml` — rail loads → power budget analyzer
- `pi_manifest.yaml` — Pi GPIO/I2C usage → DTS validator
- `.kibot.yaml` — full KiBot pipeline (ERC + DRC + BOM + gerbers + 3D)

See `~/.claude/skills/electronics-verify/SKILL.md` for examples.

## Sourcing API setup

Drop credentials at `~/.config/electronics-stack/.env`:

```
DIGIKEY_CLIENT_ID=...
DIGIKEY_CLIENT_SECRET=...
MOUSER_API_KEY=...
NEXAR_CLIENT_ID=...
NEXAR_CLIENT_SECRET=...
GITHUB_TOKEN=...
```

`chmod 600 ~/.config/electronics-stack/.env` after.

Signup links:
- Digikey: https://developer.digikey.com/  (1000 req/day free)
- Mouser: https://www.mouser.com/api-signup/
- Nexar/Octopart: https://portal.nexar.com/ (1000 req/month free)
- GitHub PAT: https://github.com/settings/tokens (lifts API limit when crawling many repos)

Test:
```bash
python3 scripts/digikey_client.py "WM8960CGEFL"
python3 scripts/mouser_client.py "FQP30N06L"
python3 scripts/octopart_client.py "BQ25713RSNR"
```

## MCP server

Expose all checks as MCP tools to Claude Code. Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "electronics": {
      "command": "python3",
      "args": ["/home/reidsurmeier/electronics-stack/mcp-server/server.py"]
    }
  }
}
```

Tools: `verify_project`, `run_erc`, `audit_connectivity`, `audit_power_budget`,
`audit_sourcing`, `validate_pi_manifest`, `lookup_part`, `pin_match_datasheet`,
`run_kibot`, `parse_schematic`, `nexar_render`, `nexar_list_projects`.

## Nexar Design API (PCB rendering)

`scripts/nexar_render.py` wraps Nexar's Design GraphQL API to pull a 3D GLB
mesh + a JSON dump of PCB primitives (tracks, pads, vias, layer stack, outline)
for any PCB stored in an Altium 365 workspace.

**Source-of-truth constraint:** The Nexar Design API does NOT accept KiCad
project uploads. The PCB must live in an Altium 365 workspace. For pure-KiCad
projects, use `kicad-cli pcb export step|glb` directly (separate path).

**Required scope: `design.domain`** — distinct from `supply.domain` used for
Digikey/Octopart sourcing. If your existing Nexar app only has Supply, go to
https://portal.nexar.com → your app → Permissions → add `design.domain` and
accept the developer agreement. The token cache will refresh on next call.

**Sample commands:**

```bash
# List Altium 365 workspaces this app can see
python3 scripts/nexar_render.py workspaces

# List projects in default workspace
python3 scripts/nexar_render.py projects

# Render a project (downloads .glb, .pcb.json, .meta.json)
python3 scripts/nexar_render.py render \
    --project-name "MyPcb" \
    --out ~/renders/mypcb
```

**Limits / cost:** Nexar's Design API is gated by the developer agreement;
rate limits aren't documented at the same granularity as Supply. The
`mesh3D` GLB is generated server-side and may take seconds for large boards.
Token cache is at `~/.cache/electronics-stack/nexar_design/token.json`.

The reference WinForms demo (`tools/nexar-design-render-demo`, .NET 6 / OpenGL)
is Windows-only and not runnable on this Linux box; the GraphQL queries were
mirrored from `Nexar.Client/Resources/Queries.graphql` into the Python wrapper.

## Claude skill

`~/.claude/skills/electronics-verify/SKILL.md` is the user-facing slash command.
Invoke: `/electronics-verify <project_dir>` (or just describe what you want
verified — Claude will pick up on the trigger words).

## Pre-commit hook

```bash
cd /your/kicad/project
~/electronics-stack/scripts/install_pre_commit_hook.sh
```

Installs a hook that runs `--erc --conn` on changed `.kicad_sch` files.

## CI (GitHub Actions)

Copy `.github-workflow-template.yml` to your KiCad repo's
`.github/workflows/kicad-verify.yml` and adjust paths.

## Community tools layered in

- **KiBot** (`INTI-CMNB/KiBot`) — CI pipeline; runs ERC, DRC, BOM, gerbers, 3D, ibom, schematic PDFs from one config
- **InteractiveHtmlBom** — interactive PCB BOM viewer (clickable footprints)
- **Kiri** (`leoheck/kiri`) — visual schematic/PCB diff between git revs
- **Docling** — PDF table extraction for datasheets (better than pdfplumber alone)
- **PySpice + ngspice** — SPICE simulation
- **kicad-happy** Claude Code plugin (`aklofas/kicad-happy`) — 12 more KiCad skills incl 44 EMC pre-compliance rules. Install: `/plugin marketplace add aklofas/kicad-happy`

See `INSTALL.md` for what's installed and what needs manual setup.

## Known gaps (roadmap)

- **Pin world-coordinate calc doesn't honor symbol rotation** in connectivity_audit.py. Most KiCad placements are at 0° so this rarely false-positives. Fix is small.
- **KiBot strict sch parser** chokes on hand-rolled `kicad_sym` files (the user's JS-generated symbols). Use `kicad-cli` directly for those projects; KiBot for projects authored in the GUI.
- **Datasheet pin-match is fuzzy**, ~80% accurate. Verify HIGH findings manually.
- **Reverse-engineer (spec → schematic)** is a v0 prototype. See `reverse-engineer/README.md`.

## License

MIT.
