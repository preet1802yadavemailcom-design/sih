from __future__ import annotations
import argparse
import os
from datetime import datetime, timedelta, timezone

from packages.connectors.base import CollectionRequest
from packages.connectors.demo import DemoConnector
from packages.ingestion.postgres import PostgresRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an APIx Phase 2 collection")
    parser.add_argument("--origin", default="DEL")
    parser.add_argument("--destination", default="BOM")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required for PostgreSQL collection")

    connector = DemoConnector()
    repo = PostgresRepository(args.database_url)
    request = CollectionRequest(connector.source_id, args.origin.upper(), args.destination.upper(), datetime.now(timezone.utc) + timedelta(days=args.days))
    run_id = repo.start_run(connector.source_id)
    try:
        for payload in connector.collect(request):
            quote = connector.to_canonical(payload)
            repo.ingest(run_id, quote)
        repo.finish_run(run_id)
        print(f"collection succeeded: run_id={run_id}")
    except Exception:
        repo.finish_run(run_id, "FAILED")
        raise


if __name__ == "__main__":
    main()
