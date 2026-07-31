# ADR 0003: Treat generated designs as experimental drafts

- Status: accepted
- Date: 2026-07-31

## Context

The design pipeline can infer parts and produce schematic and BOM artifacts,
but the historical synthetic cases exposed incomplete result contracts.
Automated checks also cannot establish electrical safety, regulatory
compliance, layout quality, or manufacturability.

## Decision

Call all generated outputs design drafts. A successful software run means the
declared artifacts were produced and checks completed; it does not authorize
fabrication or component purchase.

## Consequences

- Reports retain limitations and human-review requirements.
- Tests verify output contracts and failure semantics, not hardware validity.
- Production-ready claims require independent electrical and manufacturing
  review outside this pipeline.
