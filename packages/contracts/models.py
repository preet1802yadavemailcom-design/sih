from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

class AdvanceWindow(str, Enum):
    T1='T+1'; T7='T+7'; T15='T+15'; T30='T+30'; T45='T+45'; OTHER='OTHER'

class CabinClass(str, Enum):
    ECONOMY='ECONOMY'; PREMIUM_ECONOMY='PREMIUM_ECONOMY'; BUSINESS='BUSINESS'; FIRST='FIRST'; UNKNOWN='UNKNOWN'

class QuoteIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: str = Field(min_length=1, max_length=32)
    origin_iata: str = Field(min_length=3, max_length=3)
    destination_iata: str = Field(min_length=3, max_length=3)
    captured_at: datetime
    departure_at: datetime
    arrival_at: datetime | None = None
    marketing_carrier_code: str | None = Field(default=None, max_length=3)
    flight_number: str | None = None
    cabin_class: CabinClass = CabinClass.UNKNOWN
    currency: str = Field(min_length=3, max_length=3)
    base_fare: Decimal | None = Field(default=None, ge=0)
    mandatory_charges: Decimal | None = Field(default=None, ge=0)
    optional_charges: Decimal | None = Field(default=None, ge=0)
    total_payable: Decimal | None = Field(default=None, ge=0)
    fare_family: str | None = None
    availability_status: str = 'AVAILABLE'
    raw_payload: dict[str, Any]

    @field_validator('origin_iata','destination_iata','currency','marketing_carrier_code', mode='before')
    @classmethod
    def uppercase_codes(cls, v):
        return v.upper() if isinstance(v, str) else v

    @field_validator('departure_at')
    @classmethod
    def departure_after_capture(cls, v, info):
        captured = info.data.get('captured_at')
        if captured and v <= captured:
            raise ValueError('departure_at must be after captured_at')
        return v

class ObservationOut(BaseModel):
    observation_id: str
    route_id: str
    source_id: str
    collection_timestamp: datetime
    departure_at: datetime
    advance_purchase_days: int = Field(ge=0)
    advance_window: AdvanceWindow
    currency: str
    total_payable_minor: int | None = Field(default=None, ge=0)
    quality_status: str
    canonical_version: str
