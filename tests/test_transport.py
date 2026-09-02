import pytest

from packages.connectors.transport import (
    DeterministicTransport,
    HTTPResponse,
    RetryingTransport,
    TransportHTTPError,
    TransportRetryPolicy,
    build_auth_headers,
    classify_response,
    is_retryable_http_error,
    validate_http_url,
)


def test_deterministic_transport_returns_response():
    response = HTTPResponse(
        status_code=200,
        payload={"ok": True},
        headers={},
    )
    transport = DeterministicTransport(response)

    result = transport.request("GET", "https://example.test")

    assert result == response


def test_deterministic_transport_records_request():
    response = HTTPResponse(200, {"ok": True}, {})
    transport = DeterministicTransport(response)

    transport.request(
        "POST",
        "https://example.test/search",
        headers={"X-Test": "yes"},
        params={"route": "DEL-BOM"},
        json={"cabin": "ECONOMY"},
        timeout_seconds=5.0,
    )

    assert transport.calls == [{
        "method": "POST",
        "url": "https://example.test/search",
        "headers": {"X-Test": "yes"},
        "params": {"route": "DEL-BOM"},
        "json": {"cabin": "ECONOMY"},
        "timeout_seconds": 5.0,
    }]


def test_deterministic_transport_rejects_invalid_timeout():
    transport = DeterministicTransport(
        HTTPResponse(200, {}, {})
    )

    with pytest.raises(ValueError, match="timeout_seconds"):
        transport.request(
            "GET",
            "https://example.test",
            timeout_seconds=0,
        )


def test_retry_policy_requires_positive_attempts():
    with pytest.raises(ValueError, match="max_attempts"):
        TransportRetryPolicy(max_attempts=0)


def test_retry_policy_rejects_negative_backoff():
    with pytest.raises(ValueError, match="backoff_seconds"):
        TransportRetryPolicy(backoff_seconds=-1)


def test_retrying_transport_retries_503():
    response = HTTPResponse(503, {"error": "busy"}, {})
    transport = DeterministicTransport(response)
    attempts = []

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(
            max_attempts=3,
            backoff_seconds=0,
        ),
        sleeper=lambda seconds: attempts.append(seconds),
    )

    with pytest.raises(TransportHTTPError) as exc_info:
        retrying.request("GET", "https://example.test")

    assert exc_info.value.status_code == 503
    assert len(transport.calls) == 3
    assert attempts == []


def test_400_does_not_retry():
    response = HTTPResponse(400, {"error": "bad"}, {})
    transport = DeterministicTransport(response)

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(max_attempts=3),
    )

    with pytest.raises(TransportHTTPError) as exc_info:
        retrying.request("GET", "https://example.test")

    assert exc_info.value.status_code == 400
    assert len(transport.calls) == 1


def test_429_is_retryable():
    response = HTTPResponse(429, {"error": "rate_limited"}, {})
    transport = DeterministicTransport(response)

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(max_attempts=2),
    )

    with pytest.raises(TransportHTTPError):
        retrying.request("GET", "https://example.test")

    assert len(transport.calls) == 2


def test_successful_response_is_not_retried():
    response = HTTPResponse(200, {"ok": True}, {})
    transport = DeterministicTransport(response)

    retrying = RetryingTransport(transport)

    result = retrying.request("GET", "https://example.test")

    assert result == response
    assert len(transport.calls) == 1


def test_classify_response_rejects_http_error():
    with pytest.raises(TransportHTTPError) as exc_info:
        classify_response(
            HTTPResponse(404, {}, {})
        )

    assert exc_info.value.status_code == 404


def test_retryable_status_classification_is_structured():
    assert is_retryable_http_error(
        TransportHTTPError(503)
    )
    assert is_retryable_http_error(
        TransportHTTPError(429)
    )
    assert not is_retryable_http_error(
        TransportHTTPError(400)
    )


def test_validate_http_url_accepts_http():
    assert (
        validate_http_url("http://example.test")
        == "http://example.test"
    )


def test_validate_http_url_accepts_https():
    assert (
        validate_http_url("https://example.test/api")
        == "https://example.test/api"
    )


def test_validate_http_url_rejects_relative_url():
    with pytest.raises(ValueError, match="absolute HTTP"):
        validate_http_url("/api/search")


def test_validate_http_url_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="absolute HTTP"):
        validate_http_url("ftp://example.test/data")


def test_build_auth_headers_without_key():
    assert build_auth_headers(None) == {}
    assert build_auth_headers("") == {}


def test_build_auth_headers_with_key():
    assert build_auth_headers("secret-value") == {
        "Authorization": "Bearer secret-value"
    }


def test_deterministic_transport_redacts_authorization_header():
    response = HTTPResponse(200, {"ok": True}, {})
    transport = DeterministicTransport(response)

    transport.request(
        "GET",
        "https://example.test",
        headers={
            "Authorization": "Bearer super-secret-key",
            "X-Test": "yes",
        },
    )

    assert transport.calls[0]["headers"] == {
        "Authorization": "[REDACTED]",
        "X-Test": "yes",
    }
    assert "super-secret-key" not in str(transport.calls)


def test_retry_after_header_controls_retry_delay():
    response = HTTPResponse(
        429,
        {"error": "rate_limited"},
        {"Retry-After": "2"},
    )
    transport = DeterministicTransport(response)
    delays: list[float] = []

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(
            max_attempts=2,
            backoff_seconds=10,
        ),
        sleeper=delays.append,
    )

    with pytest.raises(TransportHTTPError):
        retrying.request("GET", "https://example.test")

    assert delays == [2.0]
    assert len(transport.calls) == 2


def test_retry_after_header_is_case_insensitive():
    response = HTTPResponse(
        503,
        {},
        {"retry-after": "1.5"},
    )
    transport = DeterministicTransport(response)
    delays: list[float] = []

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(
            max_attempts=2,
            backoff_seconds=10,
        ),
        sleeper=delays.append,
    )

    with pytest.raises(TransportHTTPError):
        retrying.request("GET", "https://example.test")

    assert delays == [1.5]


def test_invalid_retry_after_falls_back_to_backoff():
    response = HTTPResponse(
        429,
        {},
        {"Retry-After": "not-a-number"},
    )
    transport = DeterministicTransport(response)
    delays: list[float] = []

    retrying = RetryingTransport(
        transport,
        retry_policy=TransportRetryPolicy(
            max_attempts=2,
            backoff_seconds=3,
        ),
        sleeper=delays.append,
    )

    with pytest.raises(TransportHTTPError):
        retrying.request("GET", "https://example.test")

    assert delays == [3]
