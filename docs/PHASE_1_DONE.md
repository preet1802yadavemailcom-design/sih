# Phase 1 — Definition of Done

## Completed in this foundation
- Canonical PostgreSQL model defined.
- Source authorization/ToS/robots state is first-class data.
- Raw quote payload is retained with SHA-256 identity.
- Collection runs are auditable.
- Canonical observation separates source data from APIx-generated fields.
- Advance-purchase windows are explicit.
- Fare components are extensible and nullable.
- Missing/sold-out/quality states are explicit.
- Methodology versions are persisted.
- Index values carry basket/methodology/coverage metadata.
- Lineage can connect published index → observations → raw quote → source/route.
- Pydantic contract validates the canonical quote input.
- Basic contract tests are included.

## Phase 1 intentionally does NOT include
- Live airline/OTA collectors.
- Anti-bot/CAPTCHA bypass.
- Production credentials.
- Index calculation.
- Dashboard.
- Forecasting/ML.

## Gate to Phase 2
A connector may be implemented only after its source has an approved/appropriate access path. The connector must emit `QuoteIn`, preserve the original payload, calculate collection timestamp itself, and never silently turn missing price into zero.
