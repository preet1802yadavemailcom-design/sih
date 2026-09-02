import pytest

from packages.connectors.capabilities import (
    AccessMethod,
    AuthorizationStatus,
    CollectionCapability,
    ComplianceStatus,
    SourceCapability,
)


def make_capability(
    *,
    authorization_status: AuthorizationStatus,
    active: bool = True,
) -> SourceCapability:
    return SourceCapability(
        source_id="SRC-TEST",
        access_method=AccessMethod.OFFICIAL_API,
        authorization_status=authorization_status,
        tos_status=ComplianceStatus.ALLOWED,
        robots_status=ComplianceStatus.ALLOWED,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
            CollectionCapability.DOMESTIC_ROUTES,
            CollectionCapability.ECONOMY_FARES,
        }),
        active=active,
    )


@pytest.mark.parametrize(
    "authorization_status",
    [
        AuthorizationStatus.PENDING,
        AuthorizationStatus.REJECTED,
        AuthorizationStatus.EXPIRED,
    ],
)
def test_collection_blocked_without_approved_authorization(
    authorization_status: AuthorizationStatus,
) -> None:
    capability = make_capability(
        authorization_status=authorization_status,
    )

    assert capability.collection_allowed is False
    assert capability.supports(CollectionCapability.FARE_SEARCH) is False


def test_collection_blocked_when_source_inactive() -> None:
    capability = make_capability(
        authorization_status=AuthorizationStatus.APPROVED,
        active=False,
    )

    assert capability.collection_allowed is False
    assert capability.supports(CollectionCapability.FARE_SEARCH) is False


def test_approved_active_source_supports_declared_capability() -> None:
    capability = make_capability(
        authorization_status=AuthorizationStatus.APPROVED,
    )

    assert capability.collection_allowed is True
    assert capability.supports(CollectionCapability.FARE_SEARCH) is True


def test_unsupported_capability_is_rejected() -> None:
    capability = make_capability(
        authorization_status=AuthorizationStatus.APPROVED,
    )

    # The source has no explicit baggage capability.
    assert capability.supports(
        CollectionCapability.FARE_SEARCH
    ) is True

@pytest.mark.parametrize(
    "tos_status",
    [
        ComplianceStatus.PROHIBITED,
    ],
)
def test_collection_blocked_by_prohibited_tos(
    tos_status: ComplianceStatus,
) -> None:
    capability = SourceCapability(
        source_id="SRC-TOS-BLOCKED",
        access_method=AccessMethod.OFFICIAL_API,
        authorization_status=AuthorizationStatus.APPROVED,
        tos_status=tos_status,
        robots_status=ComplianceStatus.ALLOWED,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
        }),
    )

    assert capability.collection_allowed is False


def test_collection_blocked_by_disallowed_robots() -> None:
    capability = SourceCapability(
        source_id="SRC-ROBOTS-BLOCKED",
        access_method=AccessMethod.PERMITTED_SCRAPE,
        authorization_status=AuthorizationStatus.APPROVED,
        tos_status=ComplianceStatus.ALLOWED,
        robots_status=ComplianceStatus.DISALLOWED,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
        }),
    )

    assert capability.collection_allowed is False


def test_unknown_compliance_does_not_grant_collection_access() -> None:
    capability = SourceCapability(
        source_id="SRC-UNKNOWN",
        access_method=AccessMethod.PERMITTED_SCRAPE,
        authorization_status=AuthorizationStatus.APPROVED,
        tos_status=ComplianceStatus.UNKNOWN,
        robots_status=ComplianceStatus.UNKNOWN,
        capabilities=frozenset({
            CollectionCapability.FARE_SEARCH,
        }),
    )

    assert capability.collection_allowed is False
