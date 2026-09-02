from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from packages.orchestration.models import (
    CollectionJob,
    CollectionJobResult,
    CollectionJobStatus,
    RetryPolicy,
)


class CollectionOrchestrator:
    """
    Deterministic orchestration layer.

    Owns retry/status behavior and completed-job idempotency.
    """

    def __init__(
        self,
        *,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleeper
        self._completed: dict[str, CollectionJobResult] = {}

    def get_completed(
        self,
        job_id: str,
    ) -> CollectionJobResult | None:
        return self._completed.get(job_id)

    def run(
        self,
        job: CollectionJob,
        collector: Callable[[CollectionJob], None],
    ) -> CollectionJobResult:
        previous = self._completed.get(job.job_id)
        if previous is not None:
            return previous

        attempts = 0
        last_error: str | None = None

        while attempts < self.retry_policy.max_attempts:
            attempts += 1

            try:
                collector(job)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"

                if attempts < self.retry_policy.max_attempts:
                    if self.retry_policy.backoff_seconds:
                        self._sleep(self.retry_policy.backoff_seconds)
                    continue

                result = CollectionJobResult(
                    job_id=job.job_id,
                    status=CollectionJobStatus.FAILED,
                    attempts=attempts,
                    error=last_error,
                )
                self._completed[job.job_id] = result
                return result

            result = CollectionJobResult(
                job_id=job.job_id,
                status=CollectionJobStatus.SUCCEEDED,
                attempts=attempts,
            )
            self._completed[job.job_id] = result
            return result

        raise RuntimeError("collection orchestration exited unexpectedly")
