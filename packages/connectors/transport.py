from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Protocol
from urllib.parse import urlparse


class TransportError(RuntimeError):
    """Base error for source transport failures."""


class TransportTimeoutError(TransportError):
    """The upstream request exceeded its configured timeout."""


class TransportHTTPError(TransportError):
    """The upstream returned an unsuccessful HTTP response."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"upstream returned HTTP {status_code}")


@dataclass(frozen=True)
class HTTPResponse:
    status_code: int
    payload: Any
    headers: dict[str, str]


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
        raise TransportHTTPError(response.status_code)
    return response


def is_retryable_http_error(exc: TransportHTTPError) -> bool:
    return exc.status_code in RETRYABLE_HTTP_STATUS_CODES


def validate_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute HTTP(S) URL")
    return url


def build_auth_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _header_value(
    headers: dict[str, str],
    name: str,
) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _retry_after_seconds(response: HTTPResponse) -> float | None:
    value = _header_value(response.headers, "Retry-After")
    if value is None:
        return None

    try:
        seconds = float(value.strip())
    except ValueError:
        return None

    if seconds < 0:
        return None

    return seconds


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


class RetryingTransport:
    """Retry wrapper for transient transport failures."""

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

            except TransportHTTPError as exc:
                last_error = exc

                if not is_retryable_http_error(exc):
                    raise

                if attempt < self.retry_policy.max_attempts:
                    retry_after = None

                    if hasattr(self.transport, "response"):
                        response = getattr(self.transport, "response")
                        if isinstance(response, HTTPResponse):
                            retry_after = _retry_after_seconds(response)

                    delay = (
                        retry_after
                        if retry_after is not None
                        else self.retry_policy.backoff_seconds
                    )

                    if delay:
                        self._sleep(delay)

                    continue

                raise

            except TransportError as exc:
                last_error = exc

                if attempt < self.retry_policy.max_attempts:
                    if self.retry_policy.backoff_seconds:
                        self._sleep(self.retry_policy.backoff_seconds)
                    continue

                raise

        raise RuntimeError(
            "transport retry loop exited unexpectedly"
        ) from last_error


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
            raise ValueError(
                "timeout_seconds must be greater than zero"
            )

        safe_headers = dict(headers or {})

        if "Authorization" in safe_headers:
            safe_headers["Authorization"] = "[REDACTED]"

        self.calls.append({
            "method": method,
            "url": url,
            "headers": safe_headers,
            "params": dict(params or {}),
            "json": json,
            "timeout_seconds": timeout_seconds,
        })

        return self.response
