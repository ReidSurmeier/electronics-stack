# ADR 0002: Make provider access quota-safe and explicit

- Status: accepted
- Date: 2026-07-31

## Context

Distributor interfaces have different credentials, quotas, availability, and
cache lifetimes. Some historical tests intentionally disabled provider access
to preserve limited quotas.

## Decision

Keep default tests offline. Each provider owns its credentials, cache, and
error mapping behind a narrow interface. Network validation is opt-in and must
identify the provider and expected quota cost before it runs.

## Consequences

- Unit and pull-request validation use fixtures or local data.
- A missing key, block, or exhausted quota is unavailable evidence, not a pass.
- Provider responses are cached outside the repository and never committed.
