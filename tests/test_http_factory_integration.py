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
from packages.connectors.factory import ConnectorFactory
from packages.connectors.http_adapter import HTTPSourceAdapter
from packages.connectors.transport import (
    DeterministicTransport,
    HTTPResponse,
)


def capability(
    *,
    source_id="SRC-FACTORY",
    authorized=True,
):
    return SourceCapability(
        source_id=source_id,
        access_method=AccessMethod.OFFICIAL_API,
        authorization_status=(
            AuthorizationStatus.APPROVED
            if authorized
            else AuthorizationStatus.PENDING
        ),
        tos_status=ComplianceStatus.ALLOWED,
        robots_status=ComplianceStatus.UNKNOWN,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
            CollectionCapability.DOMESTIC_ROUTES,
            CollectionCapability.ECONOMY_FARES,
        }),
    )


class FactoryHTTPAdapter(HTTPSourceAdapter):
    @property
    def endpoint_path(self):
        return "/v1/fares/search"

    def map_quote(self, payload):
        return payload


def make_transport():
    return DeterministicTransport(
        HTTPResponse(
            200,
            [{"fare": 2500}],
            {},
        )
    )


def make_config():
    return SourceHTTPConfig(
        base_url="https://api.example.test",
        api_key="factory-test-key",
        timeout_seconds=5,
    )


def make_request():
    return CollectionRequest(
        source_id="SRC-FACTORY",
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


def test_factory_can_build_http_adapter_with_dependency_injection():
    factory = ConnectorFactory()

    factory.register(
        "SRC-FACTORY",
        lambda capability: FactoryHTTPAdapter(
            capability=capability,
            config=make_config(),
            transport=make_transport(),
        ),
    )

    adapter = factory.create(capability())

    assert isinstance(adapter, FactoryHTTPAdapter)
    assert adapter.source_id == "SRC-FACTORY"


def test_factory_passes_persisted_capability_to_adapter():
    factory = ConnectorFactory()
    received = []

    def builder(capability):
        received.append(capability)
        return FactoryHTTPAdapter(
            capability=capability,
            config=make_config(),
            transport=make_transport(),
        )

    factory.register("SRC-FACTORY", builder)

    source_capability = capability()
    adapter = factory.create(source_capability)

    assert adapter.capability == source_capability
    assert received == [source_capability]


def test_factory_blocks_unauthorized_http_source_before_builder():
    factory = ConnectorFactory()
    called = []

    def builder(capability):
        called.append(True)
        return FactoryHTTPAdapter(
            capability=capability,
            config=make_config(),
            transport=make_transport(),
        )

    factory.register("SRC-FACTORY", builder)

    with pytest.raises(PermissionError, match="collection not allowed"):
        factory.create(
            capability(authorized=False)
        )

    assert called == []


def test_factory_keeps_source_identity_consistent():
    factory = ConnectorFactory()

    factory.register(
        "SRC-FACTORY",
        lambda capability: FactoryHTTPAdapter(
            capability=capability,
            config=make_config(),
            transport=make_transport(),
        ),
    )

    adapter = factory.create(capability())

    assert adapter.source_id == adapter.capability.source_id


def test_factory_built_adapter_can_fetch():
    factory = ConnectorFactory()

    transport = make_transport()

    factory.register(
        "SRC-FACTORY",
        lambda capability: FactoryHTTPAdapter(
            capability=capability,
            config=make_config(),
            transport=transport,
        ),
    )

    adapter = factory.create(capability())

    payloads = adapter.fetch(make_request())

    assert payloads == [{"fare": 2500}]
    assert len(transport.calls) == 1
