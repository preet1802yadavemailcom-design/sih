from __future__ import annotations

from collections.abc import Callable

from packages.connectors.base import QuoteConnector
from packages.connectors.capabilities import SourceCapability

ConnectorBuilder = Callable[..., QuoteConnector]


class ConnectorFactory:
    """Build connectors from persisted source capabilities."""

    def __init__(
        self,
        builders: dict[str, ConnectorBuilder] | None = None,
    ) -> None:
        self._builders = dict(builders or {})

    def register(
        self,
        source_id: str,
        builder: ConnectorBuilder,
    ) -> None:
        source_id = source_id.strip()

        if not source_id:
            raise ValueError("source_id must not be empty")

        if source_id in self._builders:
            raise ValueError(
                f"connector already registered for source '{source_id}'"
            )

        self._builders[source_id] = builder

    def create(
        self,
        capability: SourceCapability,
    ) -> QuoteConnector:
        source_id = capability.source_id

        if not capability.collection_allowed:
            raise PermissionError(
                f"collection not allowed for source '{source_id}'"
            )

        builder = self._builders.get(source_id)

        if builder is None:
            raise KeyError(
                f"no connector registered for source '{source_id}'"
            )

        connector = builder(capability=capability)

        if not isinstance(connector, QuoteConnector):
            raise TypeError(
                f"connector builder for source '{source_id}' "
                "must return QuoteConnector"
            )

        if connector.source_id != source_id:
            raise ValueError(
                f"connector source '{connector.source_id}' "
                f"does not match capability source '{source_id}'"
            )

        return connector
