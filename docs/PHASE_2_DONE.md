# APIx — Phase 2 Working Vertical Slice

Phase 2 implements the first end-to-end acquisition-to-canonical-observation pipeline, including a PostgreSQL persistence adapter, without accessing live airline/OTA sites.

## Delivered
- Connector abstraction for authorized sources.
- Deterministic local `DEMO` connector for development/tests only.
- Canonical quote validation through the Phase 1 Pydantic contract.
- Stable SHA-256 hashing for raw payload identity.
- Normalization into minor currency units and advance-purchase windows.
- Deterministic quality rules with ACCEPT/REJECT/FLAG decisions.
- In-memory repository for fast unit tests and a PostgreSQL repository adapter for system-of-record persistence.
- FastAPI health endpoint, demo collection endpoint, and observation endpoint.
- Automated unit tests for normalization, quality, and hashing.

## Pipeline

```text
Connector
  -> QuoteIn
  -> Raw payload hash
  -> Normalize
  -> Quality
  -> Canonical observation
  -> Collection run metrics
```

## Production boundary
The DEMO connector is intentionally non-networked. A live connector must be added only for an approved API, partner feed, file feed, or other explicitly permitted source. No anti-bot bypass is implemented.

## Run

```bash
python -m pip install -e ".[test]"
pytest -q
uvicorn apps.api.main:app --reload
```

Then open `/docs` for the API explorer.

## PostgreSQL persistence

Set `DATABASE_URL` from `.env.example`, start PostgreSQL with `docker compose up -d db`, apply Phase 1 migration and seed, then run the collector. The live connector boundary remains intentionally separate from the demo connector.
