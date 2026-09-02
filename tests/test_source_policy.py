from packages.connectors.capabilities import (
    AccessMethod,
    AuthorizationStatus,
    CollectionCapability,
    ComplianceStatus,
    SourceCapability,
)
from packages.connectors.policy import SourcePolicyResolver


def make_record(**overrides):
    record = {
        "source_id": "SRC-TEST",
        "access_method": "OFFICIAL_API",
        "authorization_status": "APPROVED",
        "tos_status": "ALLOWED",
        "robots_status": "UNKNOWN",
        "active": True,
    }
    record.update(overrides)
    return record


def test_official_api_does_not_require_robots_allowed() -> None:
    capability = SourcePolicyResolver.from_record(
        make_record(
            access_method="OFFICIAL_API",
            robots_status="UNKNOWN",
        )
    )

    assert isinstance(capability, SourceCapability)
    assert capability.collection_allowed is True


def test_partner_api_requires_approved_authorization() -> None:
    capability = SourcePolicyResolver.from_record(
        make_record(
            access_method="PARTNER_API",
            authorization_status="PENDING",
        )
    )

    assert capability.collection_allowed is False


def test_permitted_scrape_requires_tos_and_robots_allowed() -> None:
    capability = SourcePolicyResolver.from_record(
        make_record(
            access_method="PERMITTED_SCRAPE",
            tos_status="ALLOWED",
            robots_status="DISALLOWED",
        )
    )

    assert capability.collection_allowed is False


def test_file_feed_requires_approved_authorization() -> None:
    capability = SourcePolicyResolver.from_record(
        make_record(
            access_method="FILE_FEED",
            authorization_status="APPROVED",
            tos_status="ALLOWED",
            robots_status="UNKNOWN",
        )
    )

    assert capability.collection_allowed is True


def test_unknown_access_method_is_blocked() -> None:
    capability = SourcePolicyResolver.from_record(
        make_record(
            access_method="UNKNOWN",
        )
    )

    assert capability.collection_allowed is False

def test_record_metadata_can_declare_source_capabilities() -> None:
    capability = SourcePolicyResolver.from_record(
        make_record(
            metadata={
                "capabilities": [
                    "FARE_SEARCH",
                    "DOMESTIC_ROUTES",
                ],
            }
        )
    )

    assert capability.supports(CollectionCapability.FARE_SEARCH) is True
    assert capability.supports(CollectionCapability.DOMESTIC_ROUTES) is True
    assert capability.supports(CollectionCapability.ECONOMY_FARES) is False

def test_unknown_metadata_capability_is_ignored() -> None:
    capability = SourcePolicyResolver.from_record(
        make_record(
            metadata={
                "capabilities": [
                    "FARE_SEARCH",
                    "NOT_A_REAL_CAPABILITY",
                ],
            }
        )
    )

    assert capability.supports(CollectionCapability.FARE_SEARCH) is True
    assert CollectionCapability.ECONOMY_FARES not in capability.capabilities

def test_missing_source_id_is_rejected() -> None:
    record = make_record()
    del record["source_id"]

    try:
        SourcePolicyResolver.from_record(record)
    except KeyError:
        pass
    else:
        raise AssertionError("Missing source_id was not rejected")


def test_invalid_authorization_status_is_rejected() -> None:
    try:
        SourcePolicyResolver.from_record(
            make_record(
                authorization_status="NOT_A_REAL_STATUS",
            )
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid authorization status was not rejected")


def test_inactive_source_remains_blocked_even_when_approved() -> None:
    capability = SourcePolicyResolver.from_record(
        make_record(
            authorization_status="APPROVED",
            active=False,
        )
    )

    assert capability.collection_allowed is False

def test_resolved_capability_can_be_supplied_to_connector() -> None:
    from packages.connectors.demo import DemoConnector

    capability = SourcePolicyResolver.from_record(
        make_record(
            metadata={
                "capabilities": [
                    "FARE_SEARCH",
                ],
            }
        )
    )

    connector = DemoConnector(capability=capability)

    assert connector.source_id == "SRC-TEST"
    assert connector.capability == capability
    assert connector.supports(CollectionCapability.FARE_SEARCH) is True
    assert connector.supports(CollectionCapability.DOMESTIC_ROUTES) is False

def test_connector_can_require_a_specific_collection_capability() -> None:
    from packages.connectors.demo import DemoConnector

    capability = SourcePolicyResolver.from_record(
        make_record(
            metadata={
                "capabilities": [
                    "FARE_SEARCH",
                ],
            }
        )
    )

    connector = DemoConnector(capability=capability)

    assert connector.supports(CollectionCapability.FARE_SEARCH) is True
    assert connector.supports(CollectionCapability.DOMESTIC_ROUTES) is False
    assert connector.supports(CollectionCapability.ECONOMY_FARES) is False
