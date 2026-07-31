# Electronics Stack

[![Validate](https://github.com/ReidSurmeier/electronics-stack/actions/workflows/validate.yml/badge.svg)](https://github.com/ReidSurmeier/electronics-stack/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Electronics Stack is a local, on-demand KiCad verification and experimental
design-draft toolchain. It combines deterministic checks, optional external
tool wrappers, quota-aware component lookup, datasheet pin comparison, and a
stdio MCP adapter.

It produces engineering evidence. It does not certify electrical safety,
regulatory compliance, manufacturability, or production readiness.

## Status

The repository is being re-baselined around a reproducible environment and
explicit capability boundaries. Read [PROJECT.md](PROJECT.md) for current
state and [CONTEXT.md](CONTEXT.md) for the domain model.

The May 2026 reports are historical snapshots. They record 8 passes, 6 skips,
13 upstream-design failures, and 3 unresolved synthetic-pipeline
infrastructure failures; they are not an “all projects pass” claim.

## Modules

```text
scripts/
  verify.py                 project-level check coordinator
  sch_parser.py             KiCad schematic reader
  connectivity_audit.py     passive-pin connectivity findings
  power_budget.py           declared rail-capacity findings
  sourcing_health.py        BOM URL and provider findings
  pi_dts_validator.py       Pi GPIO, I2C, and overlay findings
  datasheet_pinmatch.py     symbol-to-datasheet comparison
  *_client.py               provider-specific access and caches
  *_wrapper.py              optional external-tool adapters
  design_pipeline.py        experimental design-draft generation
mcp-server/server.py        stdio MCP adapter
test-corpus/manifest.csv    provenance for external corpus projects
```

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[test,design]'
.venv/bin/python -m pytest -q
```

See [INSTALL.md](INSTALL.md) for current host evidence and optional system
tools. A successful Python install does not imply that KiCad, KiBot, KiKit,
ngspice, or desktop-dependent integrations are available.

## Verify a project

```bash
.venv/bin/python scripts/verify.py /path/to/project
.venv/bin/python scripts/verify.py /path/to/project --erc --conn
.venv/bin/python scripts/verify.py /path/to/project --json
```

Optional project files:

- `power_budget.yaml` enables declared rail-load analysis.
- `pi_manifest.yaml` enables Pi pin and overlay validation.
- `.kibot.yaml` enables the KiBot wrapper when KiBot is installed.

Checks that cannot run must retain an explicit skipped or unavailable reason.

## Corpus

Corpus repositories are external inputs, not committed source. The manifest
records their provenance and the downloader materializes shallow clones:

```bash
bash test-corpus/download_all.sh
.venv/bin/python scripts/run_corpus.py test-corpus
```

Downloading the corpus is a network operation and is never part of the default
test suite. Preserve upstream sources; write results under a separate output
directory.

## Provider access

Provider clients load credentials from host configuration and keep caches
outside Git. Do not put credentials in shell history, command arguments,
fixtures, reports, or issues. Network validation is opt-in because each
provider has different quota and access semantics.

The local jlcparts SQLite cache is the quota-free LCSC path. Digikey, Mouser,
Farnell, and Nexar/Octopart require their respective access configuration.
See [ADR 0002](docs/adr/0002-quota-safe-provider-access.md).

A sourcing audit uses local classification and ordinary HTTP checks by
default. Distributor APIs and managed-browser escalation are independent:

```bash
# No distributor API or Browserbase calls
.venv/bin/python scripts/sourcing_health.py BOM.xlsx

# Permit DigiKey/Mouser routing and lifecycle queries
.venv/bin/python scripts/sourcing_health.py BOM.xlsx --with-api

# Separately permit capped Browserbase checks for anti-scrape responses
.venv/bin/python scripts/sourcing_health.py BOM.xlsx --with-browserbase
```

Both opt-ins can be supplied together. Importing a provider module never
creates host cache or configuration directories; those are created only when
the client writes data.

## MCP adapter

The MCP adapter is a stdio process spawned by its client; it is not a deployed
service. Configure the client to run:

```text
python3 <checkout>/mcp-server/server.py
```

Its tool list covers project verification, individual checks, provider
lookups, optional wrappers, and design-draft generation. The server must expose
the same provider and failure semantics as the underlying modules.

## Design drafts

`scripts/design_pipeline.py` can produce a parts list, schematic draft, BOM,
and verification report from a limited free-text specification. Those outputs
are experimental. Human electrical and manufacturing review is required
before fabrication or purchase. See
[ADR 0003](docs/adr/0003-experimental-design-generation.md).

## Development

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q scripts mcp-server tests reverse-engineer
bash -n test-corpus/download_all.sh scripts/install_pre_commit_hook.sh
```

Start agent work with [AGENTS.md](AGENTS.md). Contribution and issue-tracker
conventions are in [CONTRIBUTING.md](CONTRIBUTING.md) and `docs/agents/`.

## License

MIT. See [LICENSE](LICENSE).
