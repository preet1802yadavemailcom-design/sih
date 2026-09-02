from packages.connectors.base import QuoteConnector
from packages.connectors.capabilities import (
    AccessMethod,
    AuthorizationStatus,
    CollectionCapability,
    ComplianceStatus,
    SourceCapability,
)
from packages.connectors.factory import ConnectorFactory
from packages.orchestration.application import CollectionApplication
from packages.orchestration.runner import CollectionOrchestrator


class StubConnector(QuoteConnector):
    source_id = "SRC-APP"

    def collect(self, request):
        return []

    def to_canonical(self, payload):
        return payload


class StubRepository:
    def __init__(self, capability):
        self.capability = capability

    def get_source_capability(self, source_id):
        if source_id != self.capability.source_id:
            raise KeyError(f"unknown source: {source_id}")
        return self.capability


def make_capability():
    return SourceCapability(
        source_id="SRC-APP",
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


def make_application():
    capability = make_capability()
    repository = StubRepository(capability)
    factory = ConnectorFactory()
    factory.register("SRC-APP", lambda capability: StubConnector())
    orchestrator = CollectionOrchestrator()

    application = CollectionApplication(
        repository=repository,
        connector_factory=factory,
        orchestrator=orchestrator,
    )

    return application, repository, factory, capability


def test_application_creates_pipeline_with_repository_and_orchestrator():
    application, repository, _, _ = make_application()

    pipeline = application.create_pipeline()

    assert pipeline.repository is repository
    assert pipeline.orchestrator is application.orchestrator


def test_application_resolves_capability_through_repository():
    application, _, _, capability = make_application()

    connector = application.create_connector("SRC-APP")

    assert connector.source_id == capability.source_id


def test_application_creates_connector_through_factory():
    application, _, _, _ = make_application()

    connector = application.create_connector("SRC-APP")

    assert isinstance(connector, StubConnector)


def test_application_prepares_pipeline_and_connector_together():
    application, repository, _, _ = make_application()

    pipeline, connector = application.prepare_collection("SRC-APP")

    assert pipeline.repository is repository
    assert connector.source_id == "SRC-APP"


def test_application_propagates_unknown_source_error():
    application, _, _, _ = make_application()

    try:
        application.create_connector("SRC-UNKNOWN")
    except KeyError as exc:
        assert "unknown source" in str(exc)
    else:
        raise AssertionError("expected unknown source KeyError")
