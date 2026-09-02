from __future__ import annotations
from datetime import datetime, timedelta, timezone

from packages.connectors.base import CollectionRequest
from packages.connectors.demo import DemoConnector
from packages.ingestion.service import InMemoryRepository


def run_demo_collection() -> dict:
    connector = DemoConnector()
    repo = InMemoryRepository()
    departure = datetime.now(timezone.utc) + timedelta(days=7)
    request = CollectionRequest("DEMO", "DEL", "BOM", departure)
    run_id = repo.start_run(connector.source_id)
    payloads = connector.collect(request)
    for payload in payloads:
        quote = connector.to_canonical(payload)
        repo.ingest(run_id, payload["raw_payload"], quote)
    return repo.finish_run(run_id)


if __name__ == "__main__":
    print(run_demo_collection())
