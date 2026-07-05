"""GST (Goods & Services Tax) calculation for INR orders, per
docs/CONTRACTS.md's "INR Currency & GST (foundation scope)" section.

Pure functions only -- no DB/HTTP access -- so this module is fully
testable in isolation. Only invoked by `orders.service.checkout` when
`order.currency == "INR"`; GST is India-specific and doesn't apply to any
other currency.

Money is always integer cents/paise in, integer cents/paise out. Rate math
uses `Decimal` internally (never raw float division on money) so that
splitting a rate into CGST/SGST halves never drifts from the combined
total by a rounding cent -- see `calculate_gst`'s intrastate branch.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from app.core.config import settings


class TaxBreakdown(BaseModel):
    taxable_amount_cents: int
    cgst_cents: int
    sgst_cents: int
    igst_cents: int
    tax_total_cents: int
    grand_total_cents: int
    effective_tax_rate_percent: float


def _round_cents(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_gst(subtotal_cents: int, buyer_state: str | None) -> TaxBreakdown | None:
    if not settings.gst_enabled or not buyer_state:
        return None

    rate = Decimal(str(settings.default_gst_rate_percent))
    subtotal = Decimal(subtotal_cents)

    if settings.tax_inclusive_pricing:
        # `subtotal_cents` already includes tax -- back out the pre-tax
        # taxable amount: taxable = subtotal / (1 + rate/100).
        taxable_amount = subtotal / (Decimal(1) + rate / Decimal(100))
        taxable_amount_cents = _round_cents(taxable_amount)
        tax_total_cents = subtotal_cents - taxable_amount_cents
    else:
        # `subtotal_cents` is pre-tax -- tax is added on top.
        taxable_amount_cents = subtotal_cents
        tax_total = subtotal * rate / Decimal(100)
        tax_total_cents = _round_cents(tax_total)

    is_intrastate = buyer_state.strip().casefold() == settings.seller_state.strip().casefold()

    if is_intrastate:
        # Split the tax total evenly into CGST + SGST. Round each half
        # independently would risk cgst_cents + sgst_cents != tax_total_cents
        # for odd totals (e.g. 1 paisa off) -- instead round only the CGST
        # half and derive SGST as the remainder, guaranteeing the two halves
        # always sum back to tax_total_cents exactly.
        half = Decimal(tax_total_cents) / Decimal(2)
        cgst_cents = _round_cents(half)
        sgst_cents = tax_total_cents - cgst_cents
        igst_cents = 0
    else:
        cgst_cents = 0
        sgst_cents = 0
        igst_cents = tax_total_cents

    if settings.tax_inclusive_pricing:
        grand_total_cents = subtotal_cents
    else:
        grand_total_cents = taxable_amount_cents + tax_total_cents

    effective_tax_rate_percent = (
        (tax_total_cents / taxable_amount_cents * 100) if taxable_amount_cents > 0 else 0.0
    )

    return TaxBreakdown(
        taxable_amount_cents=taxable_amount_cents,
        cgst_cents=cgst_cents,
        sgst_cents=sgst_cents,
        igst_cents=igst_cents,
        tax_total_cents=tax_total_cents,
        grand_total_cents=grand_total_cents,
        effective_tax_rate_percent=effective_tax_rate_percent,
    )
