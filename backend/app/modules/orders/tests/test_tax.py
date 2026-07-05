"""Pure-function tests for `orders/tax.py`'s GST engine, per
docs/CONTRACTS.md's "INR Currency & GST (foundation scope)" section. No
DB/HTTP dependency -- these exercise `calculate_gst` directly against
`app.core.config.settings`, monkeypatched per test.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.config import settings
from app.modules.orders.tax import TaxBreakdown, calculate_gst


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    """Every test starts from the documented defaults and only overrides
    what it needs -- avoids leaking state between tests."""
    monkeypatch.setattr(settings, "gst_enabled", False)
    monkeypatch.setattr(settings, "default_gst_rate_percent", 18.0)
    monkeypatch.setattr(settings, "seller_state", "Maharashtra")
    monkeypatch.setattr(settings, "seller_gstin", None)
    monkeypatch.setattr(settings, "tax_inclusive_pricing", False)


# ---------------------------------------------------------------------------
# Opt-in / no-op behavior
# ---------------------------------------------------------------------------


def test_gst_disabled_returns_none():
    settings.gst_enabled = False
    assert calculate_gst(10000, "Maharashtra") is None


def test_buyer_state_none_returns_none_even_when_enabled():
    settings.gst_enabled = True
    assert calculate_gst(10000, None) is None


def test_buyer_state_empty_string_returns_none():
    settings.gst_enabled = True
    assert calculate_gst(10000, "") is None


# ---------------------------------------------------------------------------
# Intrastate (CGST + SGST) vs interstate (IGST) + case/whitespace handling
# ---------------------------------------------------------------------------


def test_intrastate_case_insensitive_trimmed_state_match_splits_cgst_sgst():
    settings.gst_enabled = True
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(10000, "maharashtra ")  # different case + trailing space

    assert isinstance(breakdown, TaxBreakdown)
    assert breakdown.taxable_amount_cents == 10000
    assert breakdown.tax_total_cents == 1800  # 18% of 10000
    assert breakdown.cgst_cents == 900
    assert breakdown.sgst_cents == 900
    assert breakdown.igst_cents == 0
    assert breakdown.cgst_cents + breakdown.sgst_cents == breakdown.tax_total_cents
    assert breakdown.grand_total_cents == 11800


def test_interstate_different_state_charges_igst_only():
    settings.gst_enabled = True
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(10000, "Karnataka")

    assert breakdown.cgst_cents == 0
    assert breakdown.sgst_cents == 0
    assert breakdown.igst_cents == 1800
    assert breakdown.tax_total_cents == 1800
    assert breakdown.grand_total_cents == 11800


# ---------------------------------------------------------------------------
# Rounding correctness: the whole point of using Decimal, not float, and of
# deriving SGST as a remainder rather than rounding each half independently.
# ---------------------------------------------------------------------------


def test_odd_tax_total_splits_without_off_by_one_drift():
    """subtotal=61 paise @ 18% -> tax_total = 61 * 0.18 = 10.98 -> rounds to
    11 (an odd number of paise). Splitting 11 evenly into two halves is
    5.5/5.5 -- if each half were rounded independently (ROUND_HALF_UP),
    both halves would round *up* to 6, giving cgst+sgst == 12 != 11. The
    correct implementation rounds only one half and derives the other as
    the remainder, so the two always sum back to the exact tax_total_cents,
    no matter how the rate/amount combination lands.
    """
    settings.gst_enabled = True
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(61, "Maharashtra")

    assert breakdown.tax_total_cents == 11
    assert breakdown.cgst_cents == 6
    assert breakdown.sgst_cents == 5
    assert breakdown.cgst_cents + breakdown.sgst_cents == breakdown.tax_total_cents == 11


def test_odd_subtotal_18_percent_9_9_split_sums_exactly():
    """10001 cents @ 18% split into 9%/9% CGST/SGST -- verify the two halves
    always sum back to tax_total_cents exactly, no float-rounding drift."""
    settings.gst_enabled = True
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(10001, "Maharashtra")

    expected_tax_total = int(
        (Decimal(10001) * Decimal("18") / Decimal(100)).quantize(Decimal("1"))
    )
    assert breakdown.tax_total_cents == expected_tax_total
    assert breakdown.cgst_cents + breakdown.sgst_cents == breakdown.tax_total_cents


# ---------------------------------------------------------------------------
# Rate coverage: 0%, 5%, 12%, 18%, 28%
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", [0.0, 5.0, 12.0, 18.0, 28.0])
def test_various_gst_rates_intrastate(rate):
    settings.gst_enabled = True
    settings.default_gst_rate_percent = rate
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(100_00, "Maharashtra")  # INR 100.00

    expected_tax_total = int(
        (Decimal(10000) * Decimal(str(rate)) / Decimal(100)).quantize(Decimal("1"))
    )
    assert breakdown.tax_total_cents == expected_tax_total
    assert breakdown.cgst_cents + breakdown.sgst_cents == breakdown.tax_total_cents
    assert breakdown.taxable_amount_cents == 10000
    assert breakdown.grand_total_cents == 10000 + expected_tax_total


@pytest.mark.parametrize("rate", [0.0, 5.0, 12.0, 18.0, 28.0])
def test_various_gst_rates_interstate(rate):
    settings.gst_enabled = True
    settings.default_gst_rate_percent = rate
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(100_00, "Delhi")

    expected_tax_total = int(
        (Decimal(10000) * Decimal(str(rate)) / Decimal(100)).quantize(Decimal("1"))
    )
    assert breakdown.igst_cents == expected_tax_total
    assert breakdown.cgst_cents == 0
    assert breakdown.sgst_cents == 0


# ---------------------------------------------------------------------------
# Tax-inclusive vs exclusive pricing
# ---------------------------------------------------------------------------


def test_tax_exclusive_pricing_adds_tax_on_top():
    settings.gst_enabled = True
    settings.tax_inclusive_pricing = False
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(10000, "Maharashtra")

    assert breakdown.taxable_amount_cents == 10000
    assert breakdown.grand_total_cents == 11800  # 10000 + 18%


def test_tax_inclusive_pricing_backs_out_tax():
    settings.gst_enabled = True
    settings.tax_inclusive_pricing = True
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(11800, "Maharashtra")

    # taxable = 11800 / 1.18 = 10000 exactly in this case.
    assert breakdown.taxable_amount_cents == 10000
    assert breakdown.tax_total_cents == 1800
    # Inclusive pricing: the subtotal already included tax, so the grand
    # total charged is just the original (tax-inclusive) subtotal.
    assert breakdown.grand_total_cents == 11800
    # taxable + tax always reconciles back to the original subtotal exactly.
    assert breakdown.taxable_amount_cents + breakdown.tax_total_cents == 11800


def test_tax_inclusive_pricing_with_non_round_amount_reconciles_exactly():
    settings.gst_enabled = True
    settings.tax_inclusive_pricing = True
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(12345, "Karnataka")

    # No matter how the internal Decimal division rounds, taxable_amount +
    # tax_total must reconcile back to the original (inclusive) subtotal --
    # tax_total_cents is derived by subtraction, not independently rounded.
    assert breakdown.taxable_amount_cents + breakdown.tax_total_cents == 12345
    assert breakdown.igst_cents == breakdown.tax_total_cents
    assert breakdown.grand_total_cents == 12345


# ---------------------------------------------------------------------------
# Scale edge cases: large invoices, tiny amounts, zero.
# ---------------------------------------------------------------------------


def test_large_invoice_amount_no_overflow_or_precision_loss():
    settings.gst_enabled = True
    settings.seller_state = "Maharashtra"

    subtotal_cents = 999_999_999_99  # ~ INR 1 billion, in paise
    breakdown = calculate_gst(subtotal_cents, "Maharashtra")

    expected_tax_total = int(
        (Decimal(subtotal_cents) * Decimal("18") / Decimal(100)).quantize(Decimal("1"))
    )
    assert breakdown.tax_total_cents == expected_tax_total
    assert breakdown.cgst_cents + breakdown.sgst_cents == breakdown.tax_total_cents
    assert breakdown.grand_total_cents == subtotal_cents + expected_tax_total


def test_one_cent_subtotal_rounds_to_zero_tax_without_error():
    settings.gst_enabled = True
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(1, "Maharashtra")

    assert breakdown.taxable_amount_cents == 1
    assert breakdown.tax_total_cents == 0  # 1 * 0.18 = 0.18 -> rounds to 0
    assert breakdown.cgst_cents == 0
    assert breakdown.sgst_cents == 0
    assert breakdown.grand_total_cents == 1
    assert breakdown.effective_tax_rate_percent == 0.0


def test_zero_subtotal_does_not_divide_by_zero():
    settings.gst_enabled = True
    settings.seller_state = "Maharashtra"

    breakdown = calculate_gst(0, "Maharashtra")

    assert breakdown.taxable_amount_cents == 0
    assert breakdown.tax_total_cents == 0
    assert breakdown.grand_total_cents == 0
    assert breakdown.effective_tax_rate_percent == 0.0


def test_effective_tax_rate_percent_is_informational_float():
    settings.gst_enabled = True
    settings.seller_state = "Maharashtra"
    settings.default_gst_rate_percent = 18.0

    breakdown = calculate_gst(10000, "Maharashtra")

    assert breakdown.effective_tax_rate_percent == pytest.approx(18.0)
