from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from packages.contracts.models import QuoteIn


@dataclass(frozen=True)
class QualityDecision:
    decision: str
    score: Decimal
    reason_codes: tuple[str, ...]


def evaluate_quote(quote: QuoteIn) -> QualityDecision:
    reasons: list[str] = []
    score = Decimal("1.00000")

    if quote.availability_status == "SOLD_OUT":
        return QualityDecision("REJECT", Decimal("0"), ("SOLD_OUT",))

    if quote.total_payable is None:
        return QualityDecision("FLAG", Decimal("0.50000"), ("MISSING_TOTAL_PRICE",))

    if quote.total_payable == 0:
        reasons.append("ZERO_TOTAL_PRICE")
        score -= Decimal("0.50")

    # If all monetary components are present, require arithmetic consistency.
    # Only perform exact arithmetic validation when every component is known.
    # A missing optional component must not be treated as zero.
    components = [quote.base_fare, quote.mandatory_charges, quote.optional_charges]
    if all(v is not None for v in components):
        expected = sum(v for v in components if v is not None)
        if expected != quote.total_payable:
            reasons.append("TOTAL_COMPONENT_MISMATCH")
            score -= Decimal("0.40")

    if reasons:
        return QualityDecision("FLAG", max(score, Decimal("0")), tuple(reasons))
    return QualityDecision("ACCEPT", score, tuple())
