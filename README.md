# APIx — Phase 2 Working Vertical Slice

Phase 2 extends the Phase 1 foundation into a working acquisition-to-observation pipeline.

## What is implemented
- Connector abstraction for permitted data sources.
- Deterministic local demo connector (no external network access).
- Pydantic canonical quote contract.
- Immutable raw-payload hashing.
- Fare normalization to minor currency units.
- T+1/T+7/T+15/T+30/T+45 lead-time classification.
- Quality engine with ACCEPT/REJECT/FLAG decisions.
- Collection-run metrics.
- FastAPI `/health`, demo collection, and observations endpoints.
- Unit tests.

## Important source-access rule
Production connectors must use an authorized API, partner feed, permitted scrape, manual/file feed, or another explicitly approved method. APIx does not implement anti-bot bypasses.

## Quick start

```bash
python -m pip install -e ".[test]"
pytest -q
uvicorn apps.api.main:app --reload
```

API explorer: `http://127.0.0.1:8000/docs`

## Database
Phase 1 PostgreSQL schema remains the system-of-record target. Phase 2 proves the ingestion semantics independently; the next integration step is a PostgreSQL repository using the existing schema.

## PostgreSQL collection

```bash
# PowerShell
$env:DATABASE_URL="postgresql+psycopg://apix:apix_dev_only@localhost:5432/apix"
docker compose up -d db
# Apply migrations/001_initial.sql, then seed/001_reference_data.sql and seed/002_phase2_demo_source.sql
python -m apps.collector.cli --origin DEL --destination BOM --days 7
```

The `DEMO` source is synthetic and local-only. It exists to prove the pipeline before an authorized live connector is introduced.
