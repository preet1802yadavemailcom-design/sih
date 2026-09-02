from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.connectors.factory import ConnectorFactory
from packages.orchestration.pipeline import CollectionPipeline
from packages.orchestration.runner import CollectionOrchestrator


@dataclass(frozen=True)
class CollectionApplication:
    """Composition root for APIx collection orchestration."""

    repository: Any
    connector_factory: ConnectorFactory
    orchestrator: CollectionOrchestrator

    def create_pipeline(self) -> CollectionPipeline:
        return CollectionPipeline(
            repository=self.repository,
            orchestrator=self.orchestrator,
        )

    def create_connector(self, source_id: str):
        capability = self.repository.get_source_capability(source_id)
        return self.connector_factory.create(capability)

    def prepare_collection(self, source_id: str) -> tuple:
        connector = self.create_connector(source_id)
        pipeline = self.create_pipeline()
        return pipeline, connector
