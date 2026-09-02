from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.connectors.factory import ConnectorFactory
from packages.orchestration.models import CollectionJob, CollectionJobResult
from packages.orchestration.pipeline import CollectionExecution, CollectionPipeline
from packages.orchestration.runner import CollectionOrchestrator


@dataclass
class CollectionApplication:
    """Composition root for APIx collection orchestration."""

    repository: Any
    connector_factory: ConnectorFactory
    orchestrator: CollectionOrchestrator
    _executions: dict[str, CollectionExecution] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def create_pipeline(self) -> CollectionPipeline:
        return CollectionPipeline(
            repository=self.repository,
            orchestrator=self.orchestrator,
        )

    def create_connector(self, source_id: str):
        capability = self.repository.get_source_capability(source_id)
        return self.connector_factory.create(capability)

    def prepare_collection(self, source_id: str) -> tuple[CollectionPipeline, Any]:
        connector = self.create_connector(source_id)
        pipeline = self.create_pipeline()
        return pipeline, connector

    def run(
        self,
        job: CollectionJob,
    ) -> tuple[CollectionJobResult, CollectionExecution | None]:
        """Execute one collection job through the composed application."""
        cached_execution = self._executions.get(job.job_id)
        completed_result = self.orchestrator.get_completed(job.job_id)

        if completed_result is not None:
            return completed_result, cached_execution

        pipeline, connector = self.prepare_collection(job.source_code)

        result, execution = pipeline.run(job, connector)

        if execution is not None:
            self._executions[job.job_id] = execution

        return result, execution
