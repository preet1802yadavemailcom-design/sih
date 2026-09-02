from __future__ import annotations

import pytest

from packages.connectors.transport import (
    RetryingTransport,
    TransportHTTPError,
    TransportRetryPolicy,
    DeterministicTransport,
    HTTPResponse,
)


def test_deterministic_transport_returns_configured_response() -> None:
    response = HTTPResponse(
        status_code=200,
        payload={"ok": True},
        headers={"content-type": "application/json"},
    )

    transport = DeterministicTransport(response)

    result = transport.request(
        "GET",
        "https://example.invalid/fare",
        timeout_seconds=5.0,
    )

    assert result == response


def test_deterministic_transport_records_request() -> None:
    transport = DeterministicTransport(
        HTTPResponse(200, {"ok": True}, {})
    )

    transport.request(
        "POST",
        "https://example.invalid/fare",
        headers={"Authorization": "Bearer test"},
        params={"route": "DEL-BOM"},
        json={"cabin": "ECONOMY"},
        timeout_seconds=7.5,
    )

    assert len(transport.calls) == 1
    assert transport.calls[0]["method"] == "POST"
    assert transport.calls[0]["url"] == "https://example.invalid/fare"
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer test"
    assert transport.calls[0]["params"]["route"] == "DEL-BOM"
    assert transport.calls[0]["json"]["cabin"] == "ECONOMY"
    assert transport.calls[0]["timeout_seconds"] == 7.5


def test_deterministic_transport_rejects_invalid_timeout() -> None:
    transport = DeterministicTransport(
        HTTPResponse(200, {}, {})
    )

    with pytest.raises(ValueError, match="greater than zero"):
        transport.request(
            "GET",
            "https://example.invalid",
            timeout_seconds=0,
        )


def test_retry_policy_validates_configuration() -> None:
    with pytest.raises(ValueError, match="at least one"):
        TransportRetryPolicy(max_attempts=0)

    with pytest.raises(ValueError, match="must not be negative"):
        TransportRetryPolicy(backoff_seconds=-1)


def test_response_classification_rejects_http_error() -> None:
    transport = DeterministicTransport(
        HTTPResponse(503, {"error": "unavailable"}, {})
    )
    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(max_attempts=1),
    )

    with pytest.raises(TransportHTTPError, match="503"):
        retrying.request(
            "GET",
            "https://example.invalid",
        )


def test_retrying_transport_retries_http_errors() -> None:
    transport = DeterministicTransport(
        HTTPResponse(503, {"error": "unavailable"}, {})
    )
    sleeps: list[float] = []

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(
            max_attempts=3,
            backoff_seconds=0.25,
        ),
        sleeper=sleeps.append,
    )

    with pytest.raises(TransportHTTPError):
        retrying.request(
            "GET",
            "https://example.invalid",
        )

    assert len(transport.calls) == 3
    assert sleeps == [0.25, 0.25]


def test_retrying_transport_returns_success_without_retry() -> None:
    transport = DeterministicTransport(
        HTTPResponse(200, {"ok": True}, {})
    )
    retrying = RetryingTransport(transport)

    result = retrying.request(
        "GET",
        "https://example.invalid",
    )

    assert result.status_code == 200
    assert len(transport.calls) == 1


def test_retrying_transport_does_not_retry_client_error() -> None:
    transport = DeterministicTransport(
        HTTPResponse(400, {"error": "bad request"}, {})
    )
    sleeps: list[float] = []

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(
            max_attempts=3,
            backoff_seconds=0.25,
        ),
        sleeper=sleeps.append,
    )

    with pytest.raises(TransportHTTPError, match="400"):
        retrying.request(
            "GET",
            "https://example.invalid",
        )

    assert len(transport.calls) == 1
    assert sleeps == []


def test_retrying_transport_retries_rate_limit() -> None:
    transport = DeterministicTransport(
        HTTPResponse(429, {"error": "rate limited"}, {})
    )
    sleeps: list[float] = []

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(
            max_attempts=3,
            backoff_seconds=0.1,
        ),
        sleeper=sleeps.append,
    )

    with pytest.raises(TransportHTTPError, match="429"):
        retrying.request(
            "GET",
            "https://example.invalid",
        )

    assert len(transport.calls) == 3
    assert sleeps == [0.1, 0.1]
