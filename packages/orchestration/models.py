from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum


class CollectionJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be >= 0")


@dataclass(frozen=True)
class CollectionJob:
    job_id: str
    source_code: str
    origin: str
    destination: str
    departure_date: date
    advance_days: int
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id must not be empty")
        if not self.source_code.strip():
            raise ValueError("source_code must not be empty")
        if not self.origin.strip() or not self.destination.strip():
            raise ValueError("origin and destination must not be empty")
        if self.origin.upper() == self.destination.upper():
            raise ValueError("origin and destination must differ")
        if self.advance_days not in (1, 7, 15, 30, 45):
            raise ValueError(
                "advance_days must be one of 1, 7, 15, 30, or 45"
            )

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        source_code: str,
        origin: str,
        destination: str,
        departure_date: date,
        advance_days: int,
    ) -> "CollectionJob":
        return cls(
            job_id=job_id,
            source_code=source_code,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            advance_days=advance_days,
            created_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class CollectionJobResult:
    job_id: str
    status: CollectionJobStatus
    attempts: int
    error: str | None = None
