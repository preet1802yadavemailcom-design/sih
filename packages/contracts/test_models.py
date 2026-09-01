import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from .models import QuoteIn

def valid_payload():
    now=datetime.now(timezone.utc)
    return dict(source_id='SRC-01', origin_iata='del', destination_iata='bom', captured_at=now,
                departure_at=now+timedelta(days=7), currency='inr', total_payable=Decimal('6150'), raw_payload={'x':1})

def test_quote_normalizes_codes():
    q=QuoteIn(**valid_payload())
    assert q.origin_iata=='DEL' and q.destination_iata=='BOM' and q.currency=='INR'

def test_quote_rejects_negative_total():
    p=valid_payload(); p['total_payable']=Decimal('-1')
    with pytest.raises(Exception): QuoteIn(**p)

def test_quote_rejects_departure_before_capture():
    p=valid_payload(); p['departure_at']=p['captured_at']
    with pytest.raises(Exception): QuoteIn(**p)
