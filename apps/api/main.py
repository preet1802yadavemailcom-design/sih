from __future__ import annotations
from fastapi import FastAPI, HTTPException
from packages.connectors.base import CollectionRequest
from packages.connectors.demo import DemoConnector
from packages.ingestion.service import InMemoryRepository
from datetime import datetime, timedelta, timezone

app = FastAPI(title="APIx", version="0.2.0")
repo = InMemoryRepository()
connector = DemoConnector()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "apix-api", "phase": 2}


@app.post("/v1/collections/demo")
def collect_demo(origin: str = "DEL", destination: str = "BOM") -> dict:
    departure = datetime.now(timezone.utc) + timedelta(days=7)
    request = CollectionRequest("DEMO", origin.upper(), destination.upper(), departure)
    run_id = repo.start_run(connector.source_id)
    try:
        for payload in connector.collect(request):
            quote = connector.to_canonical(payload)
            repo.ingest(run_id, payload["raw_payload"], quote)
        return repo.finish_run(run_id)
    except Exception as exc:
        repo.runs[run_id]["error_code"] = type(exc).__name__
        repo.finish_run(run_id, "FAILED")
        raise HTTPException(status_code=500, detail="collection failed") from exc


@app.get("/v1/observations")
def observations() -> dict:
    return {"count": len(repo.observations), "items": repo.observations}
