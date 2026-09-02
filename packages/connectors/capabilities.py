from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AuthorizationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ComplianceStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    ALLOWED = "ALLOWED"
    RESTRICTED = "RESTRICTED"
    PROHIBITED = "PROHIBITED"
    DISALLOWED = "DISALLOWED"
    MIXED = "MIXED"


class AccessMethod(StrEnum):
    OFFICIAL_API = "OFFICIAL_API"
    PARTNER_API = "PARTNER_API"
    PERMITTED_SCRAPE = "PERMITTED_SCRAPE"
    MANUAL = "MANUAL"
    FILE_FEED = "FILE_FEED"
    UNKNOWN = "UNKNOWN"


class CollectionCapability(StrEnum):
    FARE_SEARCH = "FARE_SEARCH"
    DOMESTIC_ROUTES = "DOMESTIC_ROUTES"
    ECONOMY_FARES = "ECONOMY_FARES"


@dataclass(frozen=True)
class SourceCapability:
    source_id: str
    access_method: AccessMethod
    authorization_status: AuthorizationStatus
    tos_status: ComplianceStatus
    robots_status: ComplianceStatus
    capabilities: frozenset[CollectionCapability]
    active: bool = True

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")

    @property
    def collection_allowed(self) -> bool:
        if not self.active:
            return False

        if self.authorization_status != AuthorizationStatus.APPROVED:
            return False

        if self.tos_status != ComplianceStatus.ALLOWED:
            return False

        if self.access_method in {
            AccessMethod.OFFICIAL_API,
            AccessMethod.PARTNER_API,
            AccessMethod.FILE_FEED,
        }:
            return True

        if self.access_method == AccessMethod.PERMITTED_SCRAPE:
            return self.robots_status == ComplianceStatus.ALLOWED

        return False

    def supports(self, capability: CollectionCapability) -> bool:
        return self.collection_allowed and capability in self.capabilities
