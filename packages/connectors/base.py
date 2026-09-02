from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from packages.connectors.capabilities import (
    CollectionCapability,
    SourceCapability,
)
from packages.contracts.models import QuoteIn


@dataclass(frozen=True)
class CollectionRequest:
    source_id: str
    origin_iata: str
    destination_iata: str
    departure_at: datetime


class QuoteConnector(ABC):
    """Connector contract. Implement only for sources with permitted access."""

    source_id: str
    capability: SourceCapability

    @abstractmethod
    def collect(self, request: CollectionRequest) -> list[dict[str, Any]]:
        raise NotImplementedError

    def to_canonical(self, payload: dict[str, Any]) -> QuoteIn:
        return QuoteIn(**payload)

    def supports(self, capability: CollectionCapability) -> bool:
        return self.capability.supports(capability)

    def ensure_collection_allowed(self) -> None:
        if not self.capability.collection_allowed:
            raise PermissionError(
                f"collection not allowed for source '{self.source_id}'"
            )
