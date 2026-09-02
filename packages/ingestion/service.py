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
        self._observation_by_raw_key: dict[tuple[str, str], dict[str, Any]] = {}

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

    def ingest(self, run_id: str, quote: QuoteIn) -> dict[str, Any]:
        raw_payload = quote.raw_payload
        run = self.runs[run_id]
        raw_hash = sha256_payload(raw_payload)
        raw_key = (run_id, raw_hash)

        existing = self._observation_by_raw_key.get(raw_key)
        if existing is not None:
            return existing

        run["records_seen"] += 1
        raw_id = str(uuid4())

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
        status_map = {
            "ACCEPT": "ACCEPTED",
            "REJECT": "REJECTED",
            "FLAG": "FLAGGED",
        }
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

        self._observation_by_raw_key[raw_key] = observation

        if decision.decision == "ACCEPT":
            run["records_accepted"] += 1
        else:
            run["records_rejected"] += 1

        return observation

    def finish_run(
        self,
        run_id: str,
        status: str = "SUCCEEDED",
        *,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        allowed_statuses = {
            "SUCCEEDED",
            "PARTIAL",
            "FAILED",
        }

        if status not in allowed_statuses:
            raise ValueError(
                f"invalid collection run status: {status}"
            )

        run = self.runs[run_id]
        run["completed_at"] = datetime.now(timezone.utc)
        run["status"] = status
        run["error_code"] = error_code

        if metadata:
            run["metadata"] = {
                **run.get("metadata", {}),
                **metadata,
            }
        else:
            run.setdefault("metadata", {})

        return run

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Return the persisted collection-run state."""
        try:
            return self.runs[run_id]
        except KeyError:
            raise KeyError(f"collection run not found: {run_id}") from None
