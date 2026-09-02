from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from packages.connectors.adapter import SourceAdapter
from packages.connectors.capabilities import (
    AccessMethod,
    AuthorizationStatus,
    CollectionCapability,
    ComplianceStatus,
    SourceCapability,
)
from packages.connectors.base import CollectionRequest
from packages.contracts.models import QuoteIn


def make_capability(source_id: str = "TEST") -> SourceCapability:
    return SourceCapability(
        source_id=source_id,
        access_method=AccessMethod.FILE_FEED,
        authorization_status=AuthorizationStatus.APPROVED,
        tos_status=ComplianceStatus.ALLOWED,
        robots_status=ComplianceStatus.ALLOWED,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
            CollectionCapability.DOMESTIC_ROUTES,
            CollectionCapability.ECONOMY_FARES,
        }),
    )


class StubAdapter(SourceAdapter):
    def __init__(self, capability: SourceCapability) -> None:
        self.source_id = capability.source_id
        self.capability = capability

    def fetch(
        self,
        request: CollectionRequest,
    ) -> list[dict[str, Any]]:
        return [{"source": self.source_id, "fare": 2500}]

    def map_quote(
        self,
        payload: dict[str, Any],
    ) -> QuoteIn:
        captured_at = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)

        return QuoteIn(
            source_id=self.source_id,
            origin_iata="DEL",
            destination_iata="BOM",
            captured_at=captured_at,
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



def make_request() -> CollectionRequest:
    return CollectionRequest(
        source_id="TEST",
        origin_iata="DEL",
        destination_iata="BOM",
        departure_at=datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc),
    )


def test_source_adapter_collect_delegates_to_fetch() -> None:
    adapter = StubAdapter(make_capability())

    assert adapter.collect(make_request()) == [
        {"source": "TEST", "fare": 2500}
    ]


def test_source_adapter_canonicalizes_payloads() -> None:
    adapter = StubAdapter(make_capability())

    quotes = adapter.canonicalize([
        {"source": "TEST", "fare": 2500},
        {"source": "TEST", "fare": 3100},
    ])

    assert len(quotes) == 2
    assert quotes[0].total_payable == 2500
    assert quotes[1].total_payable == 3100


def test_source_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        SourceAdapter()  # type: ignore[abstract]


def test_source_adapter_preserves_source_capability() -> None:
    capability = make_capability("SRC-01")
    adapter = StubAdapter(capability)

    assert adapter.source_id == "SRC-01"
    assert adapter.capability == capability


def test_source_adapter_blocks_unauthorized_collection() -> None:
    capability = make_capability("TEST")
    capability = capability.__class__(
        source_id=capability.source_id,
        access_method=capability.access_method,
        authorization_status=AuthorizationStatus.PENDING,
        tos_status=capability.tos_status,
        robots_status=capability.robots_status,
        capabilities=capability.capabilities,
        active=capability.active,
    )

    adapter = StubAdapter(capability)

    with pytest.raises(PermissionError, match="collection not allowed"):
        adapter.collect(make_request())


def test_source_adapter_blocks_missing_required_capability() -> None:
    capability = make_capability("TEST")
    capability = capability.__class__(
        source_id=capability.source_id,
        access_method=capability.access_method,
        authorization_status=capability.authorization_status,
        tos_status=capability.tos_status,
        robots_status=capability.robots_status,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
            CollectionCapability.DOMESTIC_ROUTES,
        }),
        active=capability.active,
    )

    adapter = StubAdapter(capability)

    with pytest.raises(
        PermissionError,
        match="ECONOMY_FARES",
    ):
        adapter.collect(make_request())


def test_source_adapter_collects_only_after_policy_gate() -> None:
    adapter = StubAdapter(make_capability())

    assert adapter.collect(make_request()) == [
        {"source": "TEST", "fare": 2500}
    ]
