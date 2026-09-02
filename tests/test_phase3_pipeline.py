from datetime import date, datetime, timedelta, timezone

from packages.connectors.demo import DemoConnector
from packages.ingestion.service import InMemoryRepository
from packages.orchestration import (
    CollectionJob,
    CollectionJobStatus,
    CollectionOrchestrator,
    CollectionPipeline,
    RetryPolicy,
)


def make_job(job_id: str = "e2e-001") -> CollectionJob:
    departure_date = datetime.now(timezone.utc).date() + timedelta(days=7)

    return CollectionJob.create(
        job_id=job_id,
        source_code="DEMO",
        origin="DEL",
        destination="BOM",
        departure_date=departure_date,
        advance_days=7,
    )


def test_demo_connector_runs_through_phase2_pipeline() -> None:
    repository = InMemoryRepository()
    pipeline = CollectionPipeline(
        repository=repository,
        orchestrator=CollectionOrchestrator(
            retry_policy=RetryPolicy(max_attempts=2)
        ),
    )

    result, execution = pipeline.run(
        make_job(),
        DemoConnector(),
    )

    assert result.status == CollectionJobStatus.SUCCEEDED
    assert result.attempts == 1

    assert execution is not None
    assert execution.records_seen == 1
    assert execution.records_accepted == 1
    assert execution.records_rejected == 0

    assert len(repository.runs) == 1
    assert len(repository.raw_quotes) == 1
    assert len(repository.observations) == 1
    assert len(repository.quality_results) == 1

    raw_quote = repository.raw_quotes[0]
    assert raw_quote["payload_sha256"]
    assert len(raw_quote["payload_sha256"]) == 64

    observation = repository.observations[0]
    assert observation["source_id"] == "DEMO"
    assert observation["origin_iata"] == "DEL"
    assert observation["destination_iata"] == "BOM"
    assert observation["advance_window"] == "T+7"
    assert observation["quality_status"] == "ACCEPTED"


def test_source_mismatch_is_rejected() -> None:
    repository = InMemoryRepository()
    pipeline = CollectionPipeline(
        repository=repository,
        orchestrator=CollectionOrchestrator(),
    )

    job = make_job("e2e-mismatch")

    class WrongConnector(DemoConnector):
        source_id = "WRONG"

    try:
        pipeline.run(job, WrongConnector())
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Expected source mismatch to fail")

def test_retry_after_connector_failure_does_not_duplicate_successful_quote() -> None:
    repository = InMemoryRepository()

    class FlakyConnector(DemoConnector):
        def __init__(self) -> None:
            self.calls = 0

        def collect(self, request):
            self.calls += 1

            if self.calls == 1:
                raise RuntimeError("temporary source failure")

            return super().collect(request)

    connector = FlakyConnector()

    pipeline = CollectionPipeline(
        repository=repository,
        orchestrator=CollectionOrchestrator(
            retry_policy=RetryPolicy(max_attempts=2)
        ),
    )

    result, execution = pipeline.run(
        make_job("retry-e2e-001"),
        connector,
    )

    assert result.status == CollectionJobStatus.SUCCEEDED
    assert result.attempts == 2

    assert execution is not None
    assert execution.records_seen == 1
    assert execution.records_accepted == 1

    # First attempt failed before producing a quote.
    # Only the successful attempt is persisted.
    assert len(repository.raw_quotes) == 1
    assert len(repository.observations) == 1
    assert len(repository.quality_results) == 1

    assert connector.calls == 2


def test_failed_collection_marks_run_failed() -> None:
    repository = InMemoryRepository()

    class AlwaysFailConnector(DemoConnector):
        def collect(self, request):
            raise RuntimeError("source unavailable")

    pipeline = CollectionPipeline(
        repository=repository,
        orchestrator=CollectionOrchestrator(
            retry_policy=RetryPolicy(max_attempts=2)
        ),
    )

    result, execution = pipeline.run(
        make_job("failure-e2e-001"),
        AlwaysFailConnector(),
    )

    assert result.status == CollectionJobStatus.FAILED
    assert result.attempts == 2
    assert execution is None

    assert len(repository.runs) == 1

    run = next(iter(repository.runs.values()))
    assert run["status"] == "FAILED"
    assert run["records_seen"] == 0
    assert run["records_accepted"] == 0
    assert run["records_rejected"] == 0

    assert len(repository.raw_quotes) == 0
    assert len(repository.observations) == 0
    assert len(repository.quality_results) == 0


def test_successful_job_is_not_collected_twice() -> None:
    repository = InMemoryRepository()
    connector = DemoConnector()

    orchestrator = CollectionOrchestrator(
        retry_policy=RetryPolicy(max_attempts=2)
    )

    pipeline = CollectionPipeline(
        repository=repository,
        orchestrator=orchestrator,
    )

    job = make_job("idempotent-e2e-001")

    first_result, first_execution = pipeline.run(job, connector)
    second_result, second_execution = pipeline.run(job, connector)

    assert first_result == second_result
    assert first_execution == second_execution

    # The completed orchestration result prevents a second collection.
    assert len(repository.runs) == 1
    assert len(repository.raw_quotes) == 1
    assert len(repository.observations) == 1
    assert len(repository.quality_results) == 1

def test_failed_collection_preserves_error_metadata() -> None:
    repository = InMemoryRepository()

    class AlwaysFailConnector(DemoConnector):
        def collect(self, request):
            raise TimeoutError("source request timed out")

    pipeline = CollectionPipeline(
        repository=repository,
        orchestrator=CollectionOrchestrator(
            retry_policy=RetryPolicy(max_attempts=2)
        ),
    )

    result, execution = pipeline.run(
        make_job("failure-metadata-001"),
        AlwaysFailConnector(),
    )

    assert result.status == CollectionJobStatus.FAILED
    assert result.attempts == 2
    assert execution is None

    run = next(iter(repository.runs.values()))

    assert run["status"] == "FAILED"
    assert run["error_code"] == "COLLECTION_TIMEOUTERROR"
    assert run["metadata"]["attempts"] == 2
    assert run["metadata"]["error"] == (
        "TimeoutError: source request timed out"
    )

def test_partial_collection_is_distinguished_from_total_failure() -> None:
    repository = InMemoryRepository()

    class PartialConnector(DemoConnector):
        def collect(self, request):
            successful_quote = super().collect(request)[0]

            # First quote is successfully produced and ingested.
            yield successful_quote

            # Source fails after one usable record.
            raise RuntimeError("source failed after partial collection")

    pipeline = CollectionPipeline(
        repository=repository,
        orchestrator=CollectionOrchestrator(
            retry_policy=RetryPolicy(max_attempts=1)
        ),
    )

    result, execution = pipeline.run(
        make_job("partial-001"),
        PartialConnector(),
    )

    assert result.status == CollectionJobStatus.FAILED
    assert execution is None

    run = next(iter(repository.runs.values()))

    assert run["status"] == "PARTIAL"
    assert run["records_seen"] == 1
    assert run["records_accepted"] == 1
    assert run["records_rejected"] == 0
    assert run["error_code"] == "COLLECTION_RUNTIMEERROR"
    assert run["metadata"]["attempts"] == 1
    assert run["metadata"]["error"] == (
        "RuntimeError: source failed after partial collection"
    )
