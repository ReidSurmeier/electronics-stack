# ADR 0001: Keep the runtime local and on demand

- Status: accepted
- Date: 2026-07-31

## Context

The repository contains command-line modules and a stdio MCP adapter. A live
audit found no Electronics Stack service or container on the workstation and
no component in the Droplet registry. The historical documentation described
the MCP adapter as something a client spawns.

## Decision

Treat Electronics Stack as a local, on-demand toolchain. The MCP adapter is a
process lifecycle owned by its invoking client. No uptime, public endpoint, or
host service is part of this repository's contract.

## Consequences

- Normal validation does not inspect or restart a service.
- Host deployment requires a separate ADR and explicit runtime ownership.
- Documentation must distinguish installation from a currently running tool.
