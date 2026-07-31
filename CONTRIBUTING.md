# Contributing

Read `AGENTS.md`, `PROJECT.md`, `CONTEXT.md`, and relevant ADRs before changing
behavior.

## Workflow

1. Create an isolated environment and run the repository contract.
2. Write a behavioral test that fails for the missing capability.
3. Implement the smallest change that makes it pass.
4. Refactor only while the focused and full suites remain green.
5. Update current-state docs and create an ADR for hard-to-reverse decisions.

Default tests must stay offline and must not download corpus projects, call
providers, spend quota, require credentials, or depend on a desktop session.

## Adding a provider

- Keep credentials, cache behavior, request details, and error translation
  inside the provider module.
- Return a normalized result through a narrow interface.
- Add fixture-backed tests for success, unavailable credentials, provider
  rejection, malformed data, and cache behavior.
- Wire the provider through both the MCP schema and handler.
- Document quota cost and opt-in live validation.

## Adding an integration wrapper

- Validate paths before invoking the external tool.
- Return explicit unavailable, skipped, success, and failure states.
- Put generated artifacts in the caller's output directory.
- Test missing executables and invalid inputs without installing the tool.
- Keep desktop-dependent behavior out of default CI.

## Pull requests

Keep each pull request independently reviewable. Include the red test, the
green implementation, validation commands, capability limits, and any
follow-up issue that remains.
