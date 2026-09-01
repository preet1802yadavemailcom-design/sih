# APIx — Phase 1 Foundation

Phase 1 implements the database and canonical data-contract foundation for the Real-time Airfare Price Index (APIx).

## Scope
- PostgreSQL schema for sources, routes, flights, collection runs, raw quotes, canonical observations, fare components, quality results, route weights, index values, and lineage.
- Versioned canonical contracts using Pydantic.
- Deterministic validation and normalization primitives.
- Seed/reference data for initial routes and known source registry entries.
- Migration and test scaffolding.

## Deliberate constraints
- Raw payloads are immutable application data; the schema uses append-only raw quote records.
- Source access is connector-specific and must respect source authorization/terms. No anti-bot bypass is implemented.
- Missing price and quality status are explicit states; NULL is not silently interpreted as zero.
- Index computation is Phase 2; this phase stores the inputs and methodology/version identifiers needed for reproducibility.

## Suggested stack
- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x + Alembic
- PostgreSQL 16+
- pytest

## Run database
```bash
docker compose up -d db
```
Then apply `migrations/001_initial.sql` using your PostgreSQL migration runner.
