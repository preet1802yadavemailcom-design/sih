from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from packages.connectors.base import CollectionRequest, QuoteConnector
from packages.connectors.capabilities import CollectionCapability
from packages.contracts.models import QuoteIn


class SourceAdapter(QuoteConnector, ABC):
    """Base contract for authorized external source adapters.

    Implementations are responsible for translating a source-specific
    response into APIx canonical QuoteIn payloads.

    Network access, credentials, authorization, and source-specific
    compliance
    remain outside the canonical contract.
    """

    @abstractmethod
    def fetch(self, request: CollectionRequest) -> list[dict[str, Any]]:
        """Fetch source-specific quote payloads through an authorized channel."""
        raise NotImplementedError

    def collect(
        self,
        request: CollectionRequest,
    ) -> list[dict[str, Any]]:
        self.ensure_collection_allowed()
        self.ensure_capabilities(
            CollectionCapability.FARE_SEARCH,
            CollectionCapability.DOMESTIC_ROUTES,
            CollectionCapability.ECONOMY_FARES,
        )
        return self.fetch(request)

    @abstractmethod
    def map_quote(
        self,
        payload: dict[str, Any],
    ) -> QuoteIn:
        """Map one source payload into the APIx canonical quote contract."""
        raise NotImplementedError

    def canonicalize(
        self,
        payloads: list[dict[str, Any]],
    ) -> list[QuoteIn]:
        return [self.map_quote(payload) for payload in payloads]
