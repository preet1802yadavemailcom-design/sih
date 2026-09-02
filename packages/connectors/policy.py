from __future__ import annotations

from typing import Any, Mapping

from packages.connectors.capabilities import (
    AccessMethod,
    AuthorizationStatus,
    CollectionCapability,
    ComplianceStatus,
    SourceCapability,
)


class SourcePolicyResolver:
    """Convert persisted source-registry data into collection policy."""

    @staticmethod
    def from_record(record: Mapping[str, Any]) -> SourceCapability:
        access_method = AccessMethod(record["access_method"])
        authorization_status = AuthorizationStatus(
            record["authorization_status"]
        )
        tos_status = ComplianceStatus(record["tos_status"])
        robots_status = ComplianceStatus(record["robots_status"])

        metadata = record.get("metadata") or {}
        raw_capabilities = metadata.get("capabilities", [])

        resolved_capabilities: set[CollectionCapability] = set()

        for value in raw_capabilities:
            try:
                resolved_capabilities.add(CollectionCapability(value))
            except (TypeError, ValueError):
                continue

        capabilities = frozenset(resolved_capabilities)

        if access_method == AccessMethod.UNKNOWN:
            capabilities = frozenset()

        return SourceCapability(
            source_id=str(record["source_id"]),
            access_method=access_method,
            authorization_status=authorization_status,
            tos_status=tos_status,
            robots_status=robots_status,
            capabilities=capabilities,
            active=bool(record["active"]),
        )
