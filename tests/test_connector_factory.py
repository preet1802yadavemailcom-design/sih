import pytest

from packages.connectors.capabilities import (
    AccessMethod,
    AuthorizationStatus,
    CollectionCapability,
    ComplianceStatus,
    SourceCapability,
)
from packages.connectors.demo import DemoConnector
from packages.connectors.factory import ConnectorFactory


def make_capability(
    source_id: str = "DEMO",
    *,
    authorization_status: AuthorizationStatus = AuthorizationStatus.APPROVED,
) -> SourceCapability:
    return SourceCapability(
        source_id=source_id,
        access_method=AccessMethod.FILE_FEED,
        authorization_status=authorization_status,
        tos_status=ComplianceStatus.ALLOWED,
        robots_status=ComplianceStatus.ALLOWED,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
            CollectionCapability.DOMESTIC_ROUTES,
            CollectionCapability.ECONOMY_FARES,
        }),
    )


def test_factory_creates_registered_connector_with_capability() -> None:
    factory = ConnectorFactory({"DEMO": DemoConnector})

    capability = make_capability()

    connector = factory.create(capability)

    assert isinstance(connector, DemoConnector)
    assert connector.source_id == "DEMO"
    assert connector.capability == capability


def test_factory_blocks_unauthorized_source_before_builder() -> None:
    called = False

    def builder(**kwargs):
        nonlocal called
        called = True
        return DemoConnector(**kwargs)

    factory = ConnectorFactory({"DEMO": builder})

    capability = make_capability(
        authorization_status=AuthorizationStatus.PENDING
    )

    with pytest.raises(PermissionError, match="collection not allowed"):
        factory.create(capability)

    assert called is False


def test_factory_rejects_unknown_source() -> None:
    factory = ConnectorFactory()

    with pytest.raises(
        KeyError,
        match="no connector registered for source 'SRC-UNKNOWN'",
    ):
        factory.create(make_capability("SRC-UNKNOWN"))


def test_factory_rejects_empty_registration_source() -> None:
    factory = ConnectorFactory()

    with pytest.raises(ValueError, match="source_id must not be empty"):
        factory.register("   ", DemoConnector)


def test_factory_rejects_duplicate_registration() -> None:
    factory = ConnectorFactory({"DEMO": DemoConnector})

    with pytest.raises(
        ValueError,
        match="connector already registered",
    ):
        factory.register("DEMO", DemoConnector)


def test_factory_rejects_builder_source_mismatch() -> None:
    class WrongConnector(DemoConnector):
        def __init__(self, *, capability=None):
            super().__init__(capability=capability)
            self.source_id = "WRONG"

    factory = ConnectorFactory({"DEMO": WrongConnector})

    with pytest.raises(
        ValueError,
        match="does not match capability source",
    ):
        factory.create(make_capability("DEMO"))


def test_factory_rejects_non_connector_builder_result() -> None:
    capability = make_capability("DEMO")
    factory = ConnectorFactory()

    factory.register("DEMO", lambda **_: object())

    with pytest.raises(TypeError, match="must return QuoteConnector"):
        factory.create(capability)


def test_factory_creates_source_adapter() -> None:
    from packages.connectors.adapter import SourceAdapter

    class FactoryAdapter(SourceAdapter):
        def __init__(self, capability):
            self.source_id = capability.source_id
            self.capability = capability

        def fetch(self, request):
            return []

        def map_quote(self, payload):
            raise NotImplementedError

    capability = make_capability("DEMO")
    factory = ConnectorFactory()
    factory.register("DEMO", FactoryAdapter)

    connector = factory.create(capability)

    assert isinstance(connector, SourceAdapter)
    assert connector.source_id == "DEMO"
    assert connector.capability == capability
