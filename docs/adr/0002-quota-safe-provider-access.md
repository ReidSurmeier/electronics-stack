# ADR 0002: Make provider access quota-safe and explicit

- Status: accepted
- Date: 2026-07-31

## Context

Distributor interfaces have different credentials, quotas, availability, and
cache lifetimes. Some historical tests intentionally disabled provider access
to preserve limited quotas.

## Decision

Keep default tests offline. Each provider owns its credentials, cache, and
error mapping behind a narrow interface. Importing modules must not create
host state or contact a service.

The sourcing audit may perform ordinary HTTP checks by default, but provider
API routing requires `--with-api` and Browserbase escalation requires the
independent `--with-browserbase` flag. A local LCSC lookup is allowed without
either flag because normal client construction never refreshes or downloads
its database. Any refresh remains an explicit operation.

## Consequences

- Unit and pull-request validation use fixtures or local data.
- Anti-scrape responses remain explicitly unchecked when Browserbase is off.
- A missing key, block, or exhausted quota is unavailable evidence, not a pass.
- Provider responses are cached outside the repository and never committed.
- Provider command stderr is not returned because it may contain credentials.
