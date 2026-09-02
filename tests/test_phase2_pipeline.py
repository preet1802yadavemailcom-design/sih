from datetime import datetime, timedelta, timezone
from decimal import Decimal

from packages.contracts.models import QuoteIn
from packages.ingestion.hash import sha256_payload
from packages.ingestion.normalizer import normalize_quote
from packages.quality.rules import evaluate_quote


def payload(days=7):
    now = datetime.now(timezone.utc)
    return {
        "source_id": "DEMO",
        "origin_iata": "del",
        "destination_iata": "bom",
        "captured_at": now,
        "departure_at": now + timedelta(days=days),
        "currency": "inr",
        "base_fare": Decimal("5200"),
        "mandatory_charges": Decimal("950"),
        "total_payable": Decimal("6150"),
        "raw_payload": {"x": 1},
    }


def test_normalization_produces_minor_units_and_window():
    q = QuoteIn(**payload())
    n = normalize_quote(q)
    assert n["total_payable_minor"] == 615000
    assert n["advance_window"] == "T+7"
    assert n["canonical_version"] == "P2.0"


def test_quality_accepts_consistent_quote():
    q = QuoteIn(**payload())
    result = evaluate_quote(q)
    assert result.decision == "ACCEPT"
    assert result.score == Decimal("1.00000")


def test_quality_flags_component_mismatch():
    p = payload()
    p["optional_charges"] = Decimal("0")
    p["total_payable"] = Decimal("7000")
    q = QuoteIn(**p)
    result = evaluate_quote(q)
    assert result.decision == "FLAG"
    assert "TOTAL_COMPONENT_MISMATCH" in result.reason_codes


def test_hash_is_deterministic():
    assert sha256_payload({"b": 2, "a": 1}) == sha256_payload({"a": 1, "b": 2})
