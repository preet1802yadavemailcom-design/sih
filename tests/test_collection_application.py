from datetime import date

from packages.connectors.base import QuoteConnector
from packages.connectors.capabilities import (
    AccessMethod,
    AuthorizationStatus,
    CollectionCapability,
    ComplianceStatus,
    SourceCapability,
)
from packages.connectors.factory import ConnectorFactory
from packages.contracts.models import QuoteIn
from packages.ingestion.service import InMemoryRepository
from packages.orchestration.application import CollectionApplication
from packages.orchestration.models import CollectionJob, CollectionJobStatus
from packages.orchestration.runner import CollectionOrchestrator


class StubConnector(QuoteConnector):
    source_id = "SRC-APP"

    def __init__(self, capability=None):
        self.capability = capability

    def collect(self, request):
        return [
            {
                "source_id": "SRC-APP",
                "origin_iata": request.origin_iata,
                "destination_iata": request.destination_iata,
                "captured_at": request.departure_at - __import__("datetime").timedelta(hours=1),
                "departure_at": request.departure_at,
                "cabin_class": "ECONOMY",
                "currency": "INR",
                "base_fare": 2500,
                "total_payable": 2500,
                "availability_status": "AVAILABLE",
                "raw_payload": {"fare": 2500},
            }
        ]

    def to_canonical(self, payload):
        return QuoteIn(**payload)


def make_capability():
    return SourceCapability(
        source_id="SRC-APP",
        access_method=AccessMethod.OFFICIAL_API,
        authorization_status=AuthorizationStatus.APPROVED,
        tos_status=ComplianceStatus.ALLOWED,
        robots_status=ComplianceStatus.UNKNOWN,
        capabilities=frozenset(
            {
                CollectionCapability.FARE_SEARCH,
                CollectionCapability.DOMESTIC_ROUTES,
                CollectionCapability.ECONOMY_FARES,
            }
        ),
    )


class ApplicationRepository(InMemoryRepository):
    def __init__(self, capability):
        super().__init__()
        self.capability = capability

    def get_source_capability(self, source_id):
        if source_id != self.capability.source_id:
            raise KeyError(f"unknown source: {source_id}")
        return self.capability


def make_job(job_id="JOB-APP-001", source_code="SRC-APP"):
    return CollectionJob.create(
        job_id=job_id,
        source_code=source_code,
        origin="DEL",
        destination="BOM",
        departure_date=date(2026, 10, 1),
        advance_days=30,
    )


def make_application():
    capability = make_capability()
    repository = ApplicationRepository(capability)

    factory = ConnectorFactory()
    factory.register("SRC-APP", StubConnector)

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
    assert connector.capability is capability


def test_application_creates_connector_through_factory():
    application, _, _, _ = make_application()

    connector = application.create_connector("SRC-APP")

    assert isinstance(connector, StubConnector)


def test_application_prepares_pipeline_and_connector_together():
    application, repository, _, _ = make_application()

    pipeline, connector = application.prepare_collection("SRC-APP")

    assert pipeline.repository is repository
    assert pipeline.orchestrator is application.orchestrator
    assert connector.source_id == "SRC-APP"


def test_application_propagates_unknown_source_error():
    application, _, _, _ = make_application()

    try:
        application.create_connector("SRC-UNKNOWN")
    except KeyError as exc:
        assert "unknown source" in str(exc)
    else:
        raise AssertionError("expected unknown source KeyError")


def test_application_run_executes_complete_collection_flow():
    application, repository, _, _ = make_application()

    result, execution = application.run(make_job())

    assert result.status == CollectionJobStatus.SUCCEEDED, result
    assert result.attempts == 1

    assert execution is not None
    assert execution.job_id == "JOB-APP-001"
    assert execution.records_seen == 1
    assert execution.records_accepted == 1
    assert execution.records_rejected == 0

    assert len(repository.raw_quotes) == 1
    assert len(repository.observations) == 1


def test_application_run_reuses_completed_job_result():
    application, repository, _, _ = make_application()
    job = make_job()

    first_result, first_execution = application.run(job)
    second_result, second_execution = application.run(job)

    assert second_result is first_result
    assert second_execution is first_execution

    assert len(repository.raw_quotes) == 1
    assert len(repository.observations) == 1


def test_application_run_propagates_unknown_source():
    application, _, _, _ = make_application()

    job = make_job(
        job_id="JOB-UNKNOWN",
        source_code="SRC-UNKNOWN",
    )

    try:
        application.run(job)
    except KeyError as exc:
        assert "unknown source" in str(exc)
    else:
        raise AssertionError("expected unknown source KeyError")
