from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from packages.contracts.models import QuoteIn
from packages.ingestion.hash import sha256_payload
from packages.ingestion.normalizer import normalize_quote
from packages.quality.rules import evaluate_quote


class InMemoryRepository:
    """Reference repository for local development and unit tests.

    Production repository is intentionally separated so connector/quality logic
    can be tested without requiring PostgreSQL.
    """

    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {}
        self.raw_quotes: list[dict[str, Any]] = []
        self.observations: list[dict[str, Any]] = []
        self.quality_results: list[dict[str, Any]] = []

    def start_run(self, source_id: str) -> str:
        run_id = str(uuid4())
        self.runs[run_id] = {
            "run_id": run_id,
            "source_id": source_id,
            "started_at": datetime.now(timezone.utc),
            "status": "RUNNING",
            "records_seen": 0,
            "records_accepted": 0,
            "records_rejected": 0,
        }
        return run_id

    def ingest(self, run_id: str, raw_payload: dict[str, Any], quote: QuoteIn) -> dict[str, Any]:
        run = self.runs[run_id]
        run["records_seen"] += 1
        raw_id = str(uuid4())
        raw_hash = sha256_payload(raw_payload)
        self.raw_quotes.append({
            "raw_quote_id": raw_id,
            "run_id": run_id,
            "captured_at": quote.captured_at,
            "payload": raw_payload,
            "payload_sha256": raw_hash,
        })

        decision = evaluate_quote(quote)
        normalized = normalize_quote(quote)
        observation_id = str(uuid4())
        status_map = {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "FLAG": "FLAGGED"}
        quality_status = status_map[decision.decision]
        observation = {
            "observation_id": observation_id,
            "raw_quote_id": raw_id,
            **normalized,
            "quality_status": quality_status,
        }
        self.observations.append(observation)
        self.quality_results.append({
            "observation_id": observation_id,
            "rule_version": "P2.0",
            "quality_score": decision.score,
            "decision": decision.decision,
            "reason_codes": list(decision.reason_codes),
        })
        if decision.decision == "ACCEPT":
            run["records_accepted"] += 1
        else:
            run["records_rejected"] += 1
        return observation

    def finish_run(self, run_id: str, status: str = "SUCCEEDED") -> dict[str, Any]:
        self.runs[run_id]["completed_at"] = datetime.now(timezone.utc)
        self.runs[run_id]["status"] = status
        return self.runs[run_id]
