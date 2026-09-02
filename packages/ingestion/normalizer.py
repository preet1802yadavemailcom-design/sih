from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from packages.contracts.models import AdvanceWindow, QuoteIn

CANONICAL_VERSION = "P2.0"


def money_to_minor(value: Decimal | None) -> int | None:
    if value is None:
        return None
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def advance_window(days: int) -> AdvanceWindow:
    if days == 1:
        return AdvanceWindow.T1
    if days == 7:
        return AdvanceWindow.T7
    if days == 15:
        return AdvanceWindow.T15
    if days == 30:
        return AdvanceWindow.T30
    if days == 45:
        return AdvanceWindow.T45
    return AdvanceWindow.OTHER


def normalize_quote(quote: QuoteIn) -> dict[str, Any]:
    captured = quote.captured_at
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    departure = quote.departure_at
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)
    days = (departure.date() - captured.date()).days
    if days < 0:
        raise ValueError("departure date cannot precede capture date")

    return {
        "source_id": quote.source_id,
        "origin_iata": quote.origin_iata,
        "destination_iata": quote.destination_iata,
        "captured_at": captured,
        "departure_at": departure,
        "arrival_at": quote.arrival_at,
        "marketing_carrier_code": quote.marketing_carrier_code,
        "flight_number": quote.flight_number,
        "cabin_class": quote.cabin_class.value,
        "currency": quote.currency,
        "base_fare_minor": money_to_minor(quote.base_fare),
        "mandatory_charges_minor": money_to_minor(quote.mandatory_charges),
        "optional_charges_minor": money_to_minor(quote.optional_charges),
        "total_payable_minor": money_to_minor(quote.total_payable),
        "fare_family": quote.fare_family,
        "availability_status": quote.availability_status,
        "advance_purchase_days": days,
        "advance_window": advance_window(days).value,
        "canonical_version": CANONICAL_VERSION,
    }
