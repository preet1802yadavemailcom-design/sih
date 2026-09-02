from datetime import date

import pytest

from packages.orchestration import (
    CollectionJob,
    CollectionJobStatus,
    CollectionOrchestrator,
    RetryPolicy,
)


def make_job(job_id: str = "job-001") -> CollectionJob:
    return CollectionJob.create(
        job_id=job_id,
        source_code="DEMO",
        origin="DEL",
        destination="BOM",
        departure_date=date(2026, 9, 10),
        advance_days=7,
    )


def test_successful_collection() -> None:
    calls: list[str] = []

    def collector(job: CollectionJob) -> None:
        calls.append(job.job_id)

    result = CollectionOrchestrator().run(make_job(), collector)

    assert result.status == CollectionJobStatus.SUCCEEDED
    assert result.attempts == 1
    assert result.error is None
    assert calls == ["job-001"]


def test_retry_then_success() -> None:
    attempts = 0

    def collector(_: CollectionJob) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary source failure")

    result = CollectionOrchestrator(
        retry_policy=RetryPolicy(max_attempts=3),
    ).run(make_job(), collector)

    assert result.status == CollectionJobStatus.SUCCEEDED
    assert result.attempts == 3
    assert attempts == 3


def test_failure_after_retry_limit() -> None:
    attempts = 0

    def collector(_: CollectionJob) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("source unavailable")

    result = CollectionOrchestrator(
        retry_policy=RetryPolicy(max_attempts=3),
    ).run(make_job(), collector)

    assert result.status == CollectionJobStatus.FAILED
    assert result.attempts == 3
    assert result.error == "RuntimeError: source unavailable"
    assert attempts == 3


def test_completed_job_is_idempotent() -> None:
    calls = 0

    def collector(_: CollectionJob) -> None:
        nonlocal calls
        calls += 1

    orchestrator = CollectionOrchestrator()
    first = orchestrator.run(make_job(), collector)
    second = orchestrator.run(make_job(), collector)

    assert first == second
    assert calls == 1


def test_invalid_advance_window_is_rejected() -> None:
    with pytest.raises(ValueError):
        CollectionJob.create(
            job_id="job-invalid",
            source_code="DEMO",
            origin="DEL",
            destination="BOM",
            departure_date=date(2026, 9, 10),
            advance_days=10,
        )
