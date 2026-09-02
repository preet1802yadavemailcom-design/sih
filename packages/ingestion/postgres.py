from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from packages.connectors.capabilities import SourceCapability
from packages.contracts.models import QuoteIn
from packages.ingestion.hash import sha256_payload
from packages.ingestion.normalizer import normalize_quote
from packages.quality.rules import evaluate_quote


class PostgresRepository:
    """PostgreSQL persistence adapter for the Phase 1 schema.

    The adapter deliberately uses SQL text against the existing schema rather
    than introducing a second ORM schema definition. This keeps database
    ownership in `migrations/001_initial.sql` and makes lineage explicit.
    """

    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, pool_pre_ping=True)

    def start_run(self, source_id: str) -> str:
        with self.engine.begin() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO collection_runs
                      (source_id, started_at, status)
                    VALUES (:source_id, :started_at, 'RUNNING')
                    RETURNING run_id
                """),
                {"source_id": source_id, "started_at": datetime.now(timezone.utc)},
            ).one()
            return str(row.run_id)

    def ingest(self, run_id: str, quote: QuoteIn) -> str:
        normalized = normalize_quote(quote)
        quality = evaluate_quote(quote)
        raw_hash = sha256_payload(quote.raw_payload)

        with self.engine.begin() as conn:
            route = conn.execute(
                text("""
                    SELECT route_id FROM routes
                    WHERE origin_iata = :origin AND destination_iata = :destination
                      AND active = TRUE
                """),
                {"origin": quote.origin_iata, "destination": quote.destination_iata},
            ).first()
            if route is None:
                raise ValueError(f"route not registered: {quote.origin_iata}-{quote.destination_iata}")

            raw = conn.execute(
                text("""
                    INSERT INTO raw_quotes
                      (run_id, captured_at, source_record_key, payload, payload_sha256, content_type)
                    VALUES
                      (:run_id, :captured_at, :source_record_key, CAST(:payload AS jsonb), :sha, :content_type)
                    ON CONFLICT (run_id, payload_sha256)
                    DO UPDATE SET payload_sha256 = EXCLUDED.payload_sha256
                    RETURNING raw_quote_id
                """),
                {
                    "run_id": run_id,
                    "captured_at": quote.captured_at,
                    "source_record_key": quote.flight_number,
                    "payload": __import__("json").dumps(quote.raw_payload, sort_keys=True, default=str),
                    "sha": raw_hash,
                    "content_type": "application/json",
                },
            ).one()

            existing_observation = conn.execute(
                text("""
                    SELECT observation_id
                    FROM observations
                    WHERE raw_quote_id = :raw_quote_id
                    LIMIT 1
                """),
                {"raw_quote_id": raw.raw_quote_id},
            ).first()

            if existing_observation is not None:
                return str(existing_observation.observation_id)

            observation = conn.execute(
                text("""
                    INSERT INTO observations
                      (raw_quote_id, route_id, source_id, collection_timestamp,
                       departure_at, advance_purchase_days, advance_window, currency,
                       base_fare_minor, mandatory_charges_minor, optional_charges_minor,
                       total_payable_minor, fare_family, availability_status,
                       quality_status, canonical_version)
                    VALUES
                      (:raw_quote_id, :route_id, :source_id, :collection_timestamp,
                       :departure_at, :advance_purchase_days, :advance_window, :currency,
                       :base_fare_minor, :mandatory_charges_minor, :optional_charges_minor,
                       :total_payable_minor, :fare_family, :availability_status,
                       :quality_status, :canonical_version)
                    RETURNING observation_id
                """),
                {
                    "raw_quote_id": raw.raw_quote_id,
                    "route_id": route.route_id,
                    "source_id": quote.source_id,
                    "collection_timestamp": quote.captured_at,
                    "departure_at": normalized["departure_at"],
                    "advance_purchase_days": normalized["advance_purchase_days"],
                    "advance_window": normalized["advance_window"],
                    "currency": normalized["currency"],
                    "base_fare_minor": normalized["base_fare_minor"],
                    "mandatory_charges_minor": normalized["mandatory_charges_minor"],
                    "optional_charges_minor": normalized["optional_charges_minor"],
                    "total_payable_minor": normalized["total_payable_minor"],
                    "fare_family": normalized["fare_family"],
                    "availability_status": normalized["availability_status"],
                    "quality_status": {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "FLAG": "FLAGGED"}[quality.decision],
                    "canonical_version": normalized["canonical_version"],
                },
            ).one()

            conn.execute(
                text("""
                    UPDATE collection_runs
                    SET records_seen = records_seen + 1,
                        records_accepted = records_accepted + CASE WHEN :decision = 'ACCEPT' THEN 1 ELSE 0 END,
                        records_rejected = records_rejected + CASE WHEN :decision <> 'ACCEPT' THEN 1 ELSE 0 END
                    WHERE run_id = :run_id
                """),
                {"decision": quality.decision, "run_id": run_id},
            )

            conn.execute(
                text("""
                    INSERT INTO quality_results
                      (observation_id, rule_version, quality_score, decision, reason_codes)
                    VALUES (:observation_id, 'P2.0', :score, :decision, :reasons)
                """),
                {
                    "observation_id": observation.observation_id,
                    "score": quality.score,
                    "decision": quality.decision,
                    "reasons": list(quality.reason_codes),
                },
            )
            return str(observation.observation_id)

    def finish_run(
        self,
        run_id: str,
        status: str = "SUCCEEDED",
        *,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        allowed_statuses = {
            "SUCCEEDED",
            "PARTIAL",
            "FAILED",
        }

        if status not in allowed_statuses:
            raise ValueError(
                f"invalid collection run status: {status}"
            )

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE collection_runs
                    SET completed_at = :completed_at,
                        status = :status,
                        error_code = :error_code,
                        metadata = COALESCE(metadata, '{}'::jsonb)
                                   || CAST(:metadata AS jsonb)
                    WHERE run_id = :run_id
                """),
                {
                    "completed_at": datetime.now(timezone.utc),
                    "status": status,
                    "error_code": error_code,
                    "metadata": __import__("json").dumps(
                        metadata or {},
                        sort_keys=True,
                        default=str,
                    ),
                    "run_id": run_id,
                },
            )

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Return the persisted collection-run state."""
        with self.engine.begin() as conn:
            row = conn.execute(
                text("""
                    SELECT
                        run_id,
                        source_id,
                        started_at,
                        completed_at,
                        status,
                        records_seen,
                        records_accepted,
                        records_rejected,
                        error_code,
                        metadata
                    FROM collection_runs
                    WHERE run_id = :run_id
                """),
                {"run_id": run_id},
            ).mappings().first()

            if row is None:
                raise KeyError(f"collection run not found: {run_id}")

            return dict(row)

    def get_source(self, source_id: str) -> dict[str, Any]:
        """Return the persisted source-registry record."""
        if not source_id.strip():
            raise ValueError("source_id must not be empty")

        with self.engine.begin() as conn:
            row = conn.execute(
                text("""
                    SELECT
                        source_id,
                        source_name,
                        source_type,
                        access_method,
                        authorization_status,
                        tos_status,
                        robots_status,
                        active,
                        metadata
                    FROM source_registry
                    WHERE source_id = :source_id
                """),
                {"source_id": source_id},
            ).mappings().first()

            if row is None:
                raise KeyError(f"source not found: {source_id}")

            return dict(row)

    def get_source_capability(self, source_id: str) -> "SourceCapability":
        """Resolve a persisted source-registry record into collection policy."""
        from packages.connectors.policy import SourcePolicyResolver

        record = self.get_source(source_id)
        return SourcePolicyResolver.from_record(record)
