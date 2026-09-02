from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from packages.contracts.models import QuoteIn
from packages.ingestion.postgres import PostgresRepository


def make_quote() -> QuoteIn:
    return QuoteIn(
        source_id="DEMO",
        origin_iata="DEL",
        destination_iata="BOM",
        captured_at=datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc),
        departure_at=datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc),
        arrival_at=None,
        marketing_carrier_code="6E",
        flight_number="DEMO101",
        cabin_class="ECONOMY",
        currency="INR",
        base_fare=5200,
        mandatory_charges=950,
        optional_charges=None,
        total_payable=6150,
        fare_family="ECONOMY",
        availability_status="AVAILABLE",
        raw_payload={
            "demo": True,
            "route": "DEL-BOM",
            "price": 6150,
        },
    )


def test_postgres_repository_creates_engine():
    with patch(
        "packages.ingestion.postgres.create_engine"
    ) as create_engine:
        fake_engine = MagicMock()
        create_engine.return_value = fake_engine

        repository = PostgresRepository("postgresql+psycopg://test:test@localhost/test")

        create_engine.assert_called_once_with(
            "postgresql+psycopg://test:test@localhost/test",
            pool_pre_ping=True,
        )
        assert repository.engine is fake_engine


def test_postgres_repository_start_run_returns_run_id():
    engine = MagicMock()
    connection = MagicMock()
    row = MagicMock()
    row.run_id = "run-123"

    connection.execute.return_value.one.return_value = row
    engine.begin.return_value.__enter__.return_value = connection

    with patch(
        "packages.ingestion.postgres.create_engine",
        return_value=engine,
    ):
        repository = PostgresRepository("postgresql+psycopg://test:test@localhost/test")

    result = repository.start_run("DEMO")

    assert result == "run-123"
    connection.execute.assert_called_once()


def test_postgres_repository_get_run_returns_mapping():
    engine = MagicMock()
    connection = MagicMock()

    mapping = {
        "run_id": "run-123",
        "source_id": "DEMO",
        "status": "RUNNING",
        "records_seen": 0,
        "records_accepted": 0,
        "records_rejected": 0,
    }

    connection.execute.return_value.mappings.return_value.first.return_value = mapping
    engine.begin.return_value.__enter__.return_value = connection

    with patch(
        "packages.ingestion.postgres.create_engine",
        return_value=engine,
    ):
        repository = PostgresRepository("postgresql+psycopg://test:test@localhost/test")

    result = repository.get_run("run-123")

    assert result == mapping
    connection.execute.assert_called_once()


def test_postgres_repository_get_run_missing_raises_key_error():
    engine = MagicMock()
    connection = MagicMock()

    connection.execute.return_value.mappings.return_value.first.return_value = None
    engine.begin.return_value.__enter__.return_value = connection

    with patch(
        "packages.ingestion.postgres.create_engine",
        return_value=engine,
    ):
        repository = PostgresRepository("postgresql+psycopg://test:test@localhost/test")

    with pytest.raises(KeyError, match="collection run not found"):
        repository.get_run("missing-run")


def test_postgres_repository_rejects_invalid_finish_status():
    engine = MagicMock()

    with patch(
        "packages.ingestion.postgres.create_engine",
        return_value=engine,
    ):
        repository = PostgresRepository("postgresql+psycopg://test:test@localhost/test")

    with pytest.raises(ValueError, match="invalid collection run status"):
        repository.finish_run("run-123", "INVALID")


def test_postgres_repository_finish_run_executes_update():
    engine = MagicMock()
    connection = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection

    with patch(
        "packages.ingestion.postgres.create_engine",
        return_value=engine,
    ):
        repository = PostgresRepository("postgresql+psycopg://test:test@localhost/test")

    repository.finish_run(
        "run-123",
        "PARTIAL",
        error_code="COLLECTION_RUNTIMEERROR",
        metadata={"attempts": 1},
    )

    connection.execute.assert_called_once()


def test_postgres_repository_ingest_requires_registered_route():
    engine = MagicMock()
    connection = MagicMock()

    connection.execute.return_value.first.return_value = None
    engine.begin.return_value.__enter__.return_value = connection

    with patch(
        "packages.ingestion.postgres.create_engine",
        return_value=engine,
    ):
        repository = PostgresRepository("postgresql+psycopg://test:test@localhost/test")

    with pytest.raises(ValueError, match="route not registered: DEL-BOM"):
        repository.ingest("run-123", make_quote())
