from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from packages.connectors.base import CollectionRequest, QuoteConnector
from packages.orchestration.models import CollectionJob
from packages.orchestration.runner import CollectionOrchestrator


@dataclass(frozen=True)
class CollectionExecution:
    job_id: str
    run_id: str
    records_seen: int
    records_accepted: int
    records_rejected: int


class CollectionRepository(Protocol):
    def start_run(self, source_id: str) -> str:
        ...

    def ingest(
        self,
        run_id: str,
        quote: Any,
    ) -> Any:
        ...

    def finish_run(
        self,
        run_id: str,
        status: str = "SUCCEEDED",
        *,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        ...

    def get_run(self, run_id: str) -> dict[str, Any]:
        ...


class CollectionPipeline:
    """Connects Phase-3 orchestration to the Phase-2 ingestion pipeline."""

    def __init__(
        self,
        *,
        repository: CollectionRepository,
        orchestrator: CollectionOrchestrator,
    ) -> None:
        self.repository = repository
        self.orchestrator = orchestrator
        self._executions: dict[str, CollectionExecution] = {}

    def run(
        self,
        job: CollectionJob,
        connector: QuoteConnector,
    ) -> tuple[Any, CollectionExecution | None]:

        previous_result = self.orchestrator.get_completed(job.job_id)

        if previous_result is not None:
            return (
                previous_result,
                self._executions.get(job.job_id),
            )

        if connector.source_id != job.source_code:
            raise ValueError(
                f"connector source '{connector.source_id}' "
                f"does not match job source '{job.source_code}'"
            )

        connector.ensure_collection_allowed()

        run_id = self.repository.start_run(connector.source_id)

        request = CollectionRequest(
            source_id=connector.source_id,
            origin_iata=job.origin,
            destination_iata=job.destination,
            departure_at=datetime.combine(
                job.departure_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            ),
        )

        def collect_once(_: CollectionJob) -> None:
            payloads = connector.collect(request)

            for payload in payloads:
                quote = connector.to_canonical(payload)

                self.repository.ingest(
                    run_id=run_id,
                    quote=quote,
                )

        result = self.orchestrator.run(job, collect_once)

        if result.status.value == "SUCCEEDED":
            self.repository.finish_run(
                run_id,
                "SUCCEEDED",
                metadata={
                    "attempts": result.attempts,
                },
            )

            run = self.repository.get_run(run_id)

            execution = CollectionExecution(
                job_id=job.job_id,
                run_id=run_id,
                records_seen=run["records_seen"],
                records_accepted=run["records_accepted"],
                records_rejected=run["records_rejected"],
            )

            self._executions[job.job_id] = execution

            return result, execution

        run = self.repository.get_run(run_id)

        # A collection that produced usable records before failing is PARTIAL.
        status = (
            "PARTIAL"
            if run["records_seen"] > 0
            else "FAILED"
        )

        error_code = "COLLECTION_FAILED"

        if result.error:
            error_type = result.error.split(":", 1)[0]
            error_code = f"COLLECTION_{error_type.upper()}"

        self.repository.finish_run(
            run_id,
            status,
            error_code=error_code,
            metadata={
                "attempts": result.attempts,
                "error": result.error,
            },
        )

        return result, None
