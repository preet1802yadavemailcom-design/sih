from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .base import CollectionRequest, QuoteConnector


class DemoConnector(QuoteConnector):
    """Deterministic local connector used for development and tests only.

    It does not access a live airline/OTA website or bypass any controls.
    Replace with an authorized API/partner implementation in production.
    """

    source_id = "DEMO"

    def collect(self, request: CollectionRequest) -> list[dict[str, Any]]:
        captured = datetime.now(timezone.utc)
        return [
            {
                "source_id": self.source_id,
                "origin_iata": request.origin_iata,
                "destination_iata": request.destination_iata,
                "captured_at": captured,
                "departure_at": request.departure_at,
                "arrival_at": None,
                "marketing_carrier_code": "6E",
                "flight_number": "DEMO101",
                "cabin_class": "ECONOMY",
                "currency": "INR",
                "base_fare": Decimal("5200"),
                "mandatory_charges": Decimal("950"),
                "optional_charges": None,
                "total_payable": Decimal("6150"),
                "fare_family": "ECONOMY",
                "availability_status": "AVAILABLE",
                "raw_payload": {
                    "demo": True,
                    "route": f"{request.origin_iata}-{request.destination_iata}",
                    "price": 6150,
                },
            }
        ]
