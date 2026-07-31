# Electronics Stack project state

## Purpose

Electronics Stack combines deterministic KiCad checks, optional external
tool wrappers, quota-aware part lookup, datasheet pin comparison, and an MCP
adapter. It is intended to help inspect designs and create reviewable evidence.
It does not replace electrical, safety, compliance, or manufacturing review.

## Lifecycle

- Status: paused feature development; active repository re-baselining
- Canonical branch: `main`
- Runtime: local and on demand
- Deployment: none
- Public interface: command-line scripts plus a stdio MCP adapter
- Corpus: external repositories materialized from `test-corpus/manifest.csv`

The 2026-07-31 live audit found no Electronics Stack systemd service, Docker
container, or long-running process on the workstation and no matching
component in the healthy 44-component Droplet inventory. The MCP adapter is
therefore documented as spawn-on-use tooling, not a deployed service.

## Current evidence

The May 2026 pipeline run remains historical evidence:

- 8 corpus projects passed the selected checks.
- 6 were skipped because no top-level schematic was available.
- 13 failed with findings categorized as upstream design defects.
- 3 synthetic design cases failed because the generated-result contract was
  incomplete.

Those counts do not prove that every corpus project works. They also cannot be
reproduced from a fresh clone until the external corpus is materialized.

## Active work

- Establish a reproducible Python environment and continuous validation.
- Remove committed generated dependencies and undeclared corpus Git links.
- Reconcile the MCP provider list with the already-merged provider clients.
- Review open pull request #10 as an independent sourcing behavior change.
- Re-run the documented 25-project sample before publishing a new capability
  claim.

## Resume

Read `CONTEXT.md`, the ADRs, and the open GitHub issues. Run the repository
contract first, then install the test environment and run the full suite.
