from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Protocol


class TransportError(RuntimeError):
    """Base error for source transport failures."""


class TransportTimeoutError(TransportError):
    """The upstream request exceeded its configured timeout."""


class TransportHTTPError(TransportError):
    """The upstream returned an unsuccessful HTTP response."""


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    payload: Any
    headers: dict[str, str]


class HTTPTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout_seconds: float = 10.0,
    ) -> HTTPResponse:
        ...


@dataclass(frozen=True)
class TransportRetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must not be negative")


RETRYABLE_HTTP_STATUS_CODES = frozenset({
    408,
    429,
    500,
    502,
    503,
    504,
})


def classify_response(response: HTTPResponse) -> HTTPResponse:
    if response.status_code < 200 or response.status_code >= 300:
        raise TransportHTTPError(
            f"upstream returned HTTP {response.status_code}"
        )
    return response


def is_retryable_http_error(exc: TransportHTTPError) -> bool:
    message = str(exc)
    return any(
        f"HTTP {status}" in message
        for status in RETRYABLE_HTTP_STATUS_CODES
    )


class RetryingTransport:
    """Retry wrapper for transient transport failures.

    The wrapped transport remains responsible for the actual HTTP request.
    """

    def __init__(
        self,
        transport: HTTPTransport,
        *,
        retry_policy: TransportRetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.transport = transport
        self.retry_policy = retry_policy or TransportRetryPolicy()
        self._sleep = sleeper

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout_seconds: float = 10.0,
    ) -> HTTPResponse:
        last_error: TransportError | None = None

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                response = self.transport.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout_seconds=timeout_seconds,
                )
                return classify_response(response)
            except TransportError as exc:
                last_error = exc

                if (
                    isinstance(exc, TransportHTTPError)
                    and not is_retryable_http_error(exc)
                ):
                    raise

                if attempt < self.retry_policy.max_attempts:
                    if self.retry_policy.backoff_seconds:
                        self._sleep(self.retry_policy.backoff_seconds)
                    continue

                raise last_error

        raise RuntimeError("transport retry loop exited unexpectedly")


class DeterministicTransport:
    """Test/local transport with no network access."""

    def __init__(self, response: HTTPResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        timeout_seconds: float = 10.0,
    ) -> HTTPResponse:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        self.calls.append({
            "method": method,
            "url": url,
            "headers": dict(headers or {}),
            "params": dict(params or {}),
            "json": json,
            "timeout_seconds": timeout_seconds,
        })

        return self.response
