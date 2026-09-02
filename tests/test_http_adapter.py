from datetime import datetime, timezone

import pytest

from packages.connectors.base import CollectionRequest
from packages.connectors.capabilities import (
    AccessMethod,
    AuthorizationStatus,
    CollectionCapability,
    ComplianceStatus,
    SourceCapability,
)
from packages.connectors.config import SourceHTTPConfig
from packages.connectors.http_adapter import (
    HTTPAdapterError,
    HTTPSourceAdapter,
)
from packages.connectors.transport import (
    DeterministicTransport,
    HTTPResponse,
)
from packages.contracts.models import QuoteIn


def make_capability() -> SourceCapability:
    return SourceCapability(
        source_id="SRC-TEST",
        access_method=AccessMethod.OFFICIAL_API,
        authorization_status=AuthorizationStatus.APPROVED,
        tos_status=ComplianceStatus.ALLOWED,
        robots_status=ComplianceStatus.UNKNOWN,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
            CollectionCapability.DOMESTIC_ROUTES,
            CollectionCapability.ECONOMY_FARES,
        }),
    )


def make_request() -> CollectionRequest:
    return CollectionRequest(
        source_id="SRC-TEST",
        origin_iata="DEL",
        destination_iata="BOM",
        departure_at=datetime(
            2026,
            10,
            1,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )


def canonical_quote(payload: dict) -> QuoteIn:
    return QuoteIn(
        source_id="SRC-TEST",
        origin_iata="DEL",
        destination_iata="BOM",
        captured_at=datetime(
            2026,
            9,
            2,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        departure_at=datetime(
            2026,
            10,
            1,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        cabin_class="ECONOMY",
        currency="INR",
        base_fare=int(payload["fare"]),
        total_payable=int(payload["fare"]),
        availability_status="AVAILABLE",
        raw_payload=payload,
    )


class StubHTTPAdapter(HTTPSourceAdapter):
    @property
    def endpoint_path(self) -> str:
        return "/v1/fares/search"

    def map_quote(self, payload):
        return canonical_quote(payload)


def make_adapter(response_payload):
    transport = DeterministicTransport(
        HTTPResponse(
            status_code=200,
            payload=response_payload,
            headers={"content-type": "application/json"},
        )
    )

    adapter = StubHTTPAdapter(
        capability=make_capability(),
        config=SourceHTTPConfig(
            base_url="https://api.example.test",
            api_key="test-secret",
            timeout_seconds=5,
        ),
        transport=transport,
    )

    return adapter, transport


def test_http_adapter_builds_authorized_request():
    adapter, transport = make_adapter(
        [{"fare": 2500}]
    )

    result = adapter.fetch(make_request())

    assert result == [{"fare": 2500}]
    assert len(transport.calls) == 1

    call = transport.calls[0]

    assert call["method"] == "POST"
    assert (
        call["url"]
        == "https://api.example.test/v1/fares/search"
    )
    assert call["headers"] == {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "[REDACTED]",
    }
    assert call["json"]["origin"] == "DEL"
    assert call["json"]["destination"] == "BOM"
    assert call["timeout_seconds"] == 5
    assert "test-secret" not in str(transport.calls)


def test_http_adapter_does_not_require_api_key():
    transport = DeterministicTransport(
        HTTPResponse(200, [{"fare": 2500}], {})
    )

    adapter = StubHTTPAdapter(
        capability=make_capability(),
        config=SourceHTTPConfig(
            base_url="https://api.example.test"
        ),
        transport=transport,
    )

    adapter.fetch(make_request())

    assert "Authorization" not in transport.calls[0]["headers"]


def test_http_adapter_rejects_non_list_payload():
    adapter, _ = make_adapter(
        {"quotes": [{"fare": 2500}]}
    )

    with pytest.raises(
        HTTPAdapterError,
        match="must be a list",
    ):
        adapter.fetch(make_request())


def test_http_adapter_rejects_non_object_items():
    adapter, _ = make_adapter(
        [{"fare": 2500}, "invalid"]
    )

    with pytest.raises(
        HTTPAdapterError,
        match="items must be objects",
    ):
        adapter.fetch(make_request())


def test_http_adapter_supports_endpoint_without_leading_slash():
    class NoSlashAdapter(StubHTTPAdapter):
        @property
        def endpoint_path(self) -> str:
            return "v1/fares"

    transport = DeterministicTransport(
        HTTPResponse(200, [], {})
    )

    adapter = NoSlashAdapter(
        capability=make_capability(),
        config=SourceHTTPConfig(
            base_url="https://api.example.test/"
        ),
        transport=transport,
    )

    adapter.fetch(make_request())

    assert (
        transport.calls[0]["url"]
        == "https://api.example.test/v1/fares"
    )


def test_http_adapter_rejects_invalid_base_url():
    with pytest.raises(ValueError, match="absolute HTTP"):
        StubHTTPAdapter(
            capability=make_capability(),
            config=SourceHTTPConfig(
                base_url="ftp://api.example.test"
            ),
            transport=DeterministicTransport(
                HTTPResponse(200, [], {})
            ),
        )


def test_http_adapter_keeps_source_id_from_capability():
    adapter, _ = make_adapter([])

    assert adapter.source_id == "SRC-TEST"
    assert adapter.capability == make_capability()


def test_canonicalize_returns_quote_in():
    adapter, _ = make_adapter([])

    payload = {"fare": 2500}

    result = adapter.canonicalize([payload])

    assert len(result) == 1
    assert isinstance(result[0], QuoteIn)
    assert result[0].total_payable == 2500


def test_canonicalize_preserves_raw_payload():
    adapter, _ = make_adapter([])

    payload = {"fare": 2500, "source_field": "ABC"}

    result = adapter.canonicalize([payload])

    assert result[0].raw_payload == payload


def test_canonicalize_rejects_invalid_mapping():
    class InvalidAdapter(StubHTTPAdapter):
        def map_quote(self, payload):
            return {"not": "QuoteIn"}

    adapter = InvalidAdapter(
        capability=make_capability(),
        config=SourceHTTPConfig(
            base_url="https://api.example.test"
        ),
        transport=DeterministicTransport(
            HTTPResponse(200, [], {})
        ),
    )

    with pytest.raises(
        HTTPAdapterError,
        match="must return QuoteIn",
    ):
        adapter.canonicalize([{"fare": 2500}])


def test_canonicalize_wraps_mapping_validation_errors():
    class BrokenAdapter(StubHTTPAdapter):
        def map_quote(self, payload):
            return QuoteIn(
                source_id="SRC-TEST",
                origin_iata="DEL",
                destination_iata="BOM",
                captured_at=datetime.now(timezone.utc),
                departure_at=datetime.now(timezone.utc),
                cabin_class="ECONOMY",
                currency="INR",
                base_fare="invalid",
                total_payable="invalid",
                availability_status="AVAILABLE",
                raw_payload=payload,
            )

    adapter = BrokenAdapter(
        capability=make_capability(),
        config=SourceHTTPConfig(
            base_url="https://api.example.test"
        ),
        transport=DeterministicTransport(
            HTTPResponse(200, [], {})
        ),
    )

    with pytest.raises(HTTPAdapterError, match="could not be mapped"):
        adapter.canonicalize([{"fare": 2500}])


def test_fetch_then_canonicalize_forms_source_boundary():
    adapter, _ = make_adapter(
        [
            {"fare": 2500},
            {"fare": 3100},
        ]
    )

    payloads = adapter.fetch(make_request())
    quotes = adapter.canonicalize(payloads)

    assert [quote.total_payable for quote in quotes] == [
        2500,
        3100,
    ]
    assert all(
        quote.source_id == "SRC-TEST"
        for quote in quotes
    )
