# Electronics Stack context

## Domain

Electronics Stack turns KiCad source and optional project metadata into
reviewable findings and generated artifacts. Its central concern is evidence:
which checks ran, what they observed, what could not run, and which external
assumptions remain.

## Glossary

- **Project** — one input directory containing a KiCad project and schematic.
- **Check** — one deterministic or explicitly external verification operation.
- **Finding** — a check result with severity, evidence, and an accountable
  failure or skip reason.
- **Verification report** — the collected findings for one project and run.
- **Provider** — a distributor or component-data source queried under its own
  credentials, quota, cache, and error semantics.
- **Cache** — local, rebuildable provider data that is never repository truth.
- **Corpus entry** — a third-party project described by the corpus manifest and
  materialized outside Git history for a test run.
- **Integration wrapper** — a narrow adapter around an optional executable or
  Python dependency such as KiKit, KiBot, or SKiDL.
- **Design draft** — generated schematic/BOM output that requires human review.
- **MCP adapter** — the stdio process translating tool calls into checks,
  provider lookups, wrappers, and design-draft operations.

## Module map

- `scripts/verify.py` coordinates project discovery and selected checks.
- `scripts/sch_parser.py` reads KiCad schematic structure for local checks.
- `scripts/connectivity_audit.py`, `power_budget.py`,
  `pi_dts_validator.py`, and `datasheet_pinmatch.py` produce findings.
- `scripts/*_client.py` implement provider-specific access and caching.
- `scripts/*_wrapper.py` isolate optional external-tool behavior.
- `scripts/design_pipeline.py` creates experimental design drafts.
- `mcp-server/server.py` exposes the toolchain through the MCP adapter.
- `test-corpus/manifest.csv` records corpus provenance; the corpus clones are
  inputs, not repository contents.

## Invariants

1. Source projects are read-only inputs unless a separate task explicitly
   authorizes a source change.
2. Default tests are hermetic and do not query providers, download the corpus,
   spend quota, or require a desktop.
3. Every skipped or unavailable check retains its reason in the report.
4. Credentials come from host configuration and never enter Git history.
5. Generated designs are design drafts, never manufacturing authority.
6. Provider caches and generated output are rebuildable and stay outside
   tracked source.
7. The MCP adapter is local and on demand; it has no implied service uptime.

## Out of scope

- Declaring a board electrically safe or production-ready
- Automatically ordering components or fabrication
- Scraping providers in violation of their access controls
- Treating third-party corpus repositories as maintained source
- Operating a public web service
