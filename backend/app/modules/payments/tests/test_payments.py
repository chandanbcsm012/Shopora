"""Tests for the payments module: the CODProvider/TestCardProvider adapter
behavior, `get_provider` lookup/validation, and the service-layer helpers
`orders` drives a Payment row's lifecycle through, per docs/CONTRACTS.md.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import AppError
from app.modules.orders.models import Order, OrderStatus  # noqa: F401 (registers orders table)
from app.modules.payments import service
from app.modules.payments.models import Payment
from app.modules.payments.providers import CODProvider, TestCardProvider, get_provider
from app.shared.base_model import Base

# ---------------------------------------------------------------------------
# Provider adapter behavior (no DB needed)
# ---------------------------------------------------------------------------


def _fake_payment(**overrides) -> Payment:
    payment = Payment(
        order_id="order-1",
        method=overrides.pop("method", "test_card"),
        status=overrides.pop("status", "pending"),
        amount_cents=overrides.pop("amount_cents", 1000),
        currency="USD",
        refunded_amount_cents=overrides.pop("refunded_amount_cents", 0),
    )
    for key, value in overrides.items():
        setattr(payment, key, value)
    return payment


async def test_cod_provider_process_always_pending():
    provider = CODProvider()
    payment = _fake_payment(method="cod")

    outcome = await provider.process(payment)

    assert outcome.status == "pending"
    assert outcome.provider_reference is None


async def test_cod_provider_refund_raises_not_refundable():
    provider = CODProvider()
    payment = _fake_payment(method="cod", status="pending")

    with pytest.raises(AppError) as exc_info:
        await provider.refund(payment, 1000)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code.value == "PAYMENT_NOT_REFUNDABLE"


async def test_test_card_provider_succeed_returns_captured_with_test_prefixed_reference():
    provider = TestCardProvider()
    payment = _fake_payment()

    outcome = await provider.process(payment, outcome="succeed")

    assert outcome.status == "captured"
    assert outcome.provider_reference.startswith("TEST-")
    assert outcome.failure_reason is None


async def test_test_card_provider_decline_returns_failed_with_reason():
    provider = TestCardProvider()
    payment = _fake_payment()

    outcome = await provider.process(payment, outcome="decline")

    assert outcome.status == "failed"
    assert outcome.failure_reason
    assert outcome.provider_reference is None


async def test_test_card_provider_defaults_to_succeed():
    provider = TestCardProvider()
    payment = _fake_payment()

    outcome = await provider.process(payment)

    assert outcome.status == "captured"


async def test_test_card_provider_has_no_card_data_fields():
    import inspect

    sig = inspect.signature(TestCardProvider.process)
    param_names = set(sig.parameters) - {"self", "payment", "kwargs"}
    assert param_names == {"outcome"}
    for forbidden in ("card_number", "cvv", "expiry", "card"):
        assert forbidden not in sig.parameters


async def test_get_provider_returns_cod_and_test_card():
    assert get_provider("cod").method == "cod"
    assert get_provider("test_card").method == "test_card"


async def test_get_provider_unknown_method_raises_invalid_payment_method():
    with pytest.raises(AppError) as exc_info:
        get_provider("bogus")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code.value == "INVALID_PAYMENT_METHOD"


# ---------------------------------------------------------------------------
# TestCardProvider.refund
# ---------------------------------------------------------------------------


async def test_test_card_refund_full_amount():
    provider = TestCardProvider()
    payment = _fake_payment(status="captured", amount_cents=1000, refunded_amount_cents=0)

    outcome = await provider.refund(payment, 1000)

    assert outcome.status == "refunded"
    assert outcome.provider_reference.startswith("TEST-")


async def test_test_card_refund_partial_amount():
    provider = TestCardProvider()
    payment = _fake_payment(status="captured", amount_cents=1000, refunded_amount_cents=0)

    outcome = await provider.refund(payment, 400)

    assert outcome.status == "partially_refunded"


async def test_test_card_refund_over_remaining_amount_rejected():
    provider = TestCardProvider()
    payment = _fake_payment(status="captured", amount_cents=1000, refunded_amount_cents=600)

    with pytest.raises(AppError) as exc_info:
        await provider.refund(payment, 500)  # only 400 left refundable

    assert exc_info.value.status_code == 409
    assert exc_info.value.code.value == "REFUND_EXCEEDS_PAYMENT_AMOUNT"


async def test_test_card_refund_pending_payment_rejected():
    provider = TestCardProvider()
    payment = _fake_payment(status="pending")

    with pytest.raises(AppError) as exc_info:
        await provider.refund(payment, 100)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code.value == "PAYMENT_NOT_REFUNDABLE"


async def test_test_card_refund_failed_payment_rejected():
    provider = TestCardProvider()
    payment = _fake_payment(status="failed")

    with pytest.raises(AppError) as exc_info:
        await provider.refund(payment, 100)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code.value == "PAYMENT_NOT_REFUNDABLE"


async def test_test_card_refund_already_refunded_payment_rejected():
    provider = TestCardProvider()
    payment = _fake_payment(status="refunded")

    with pytest.raises(AppError) as exc_info:
        await provider.refund(payment, 100)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code.value == "PAYMENT_NOT_REFUNDABLE"


async def test_test_card_refund_partially_refunded_payment_allows_further_refund():
    provider = TestCardProvider()
    payment = _fake_payment(status="partially_refunded", amount_cents=1000, refunded_amount_cents=400)

    outcome = await provider.refund(payment, 600)

    assert outcome.status == "refunded"


# ---------------------------------------------------------------------------
# Service-layer helpers (with a real in-memory DB, since Payment is a
# SQLAlchemy model)
# ---------------------------------------------------------------------------


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


async def _make_order(session, total_cents=1000) -> Order:
    order = Order(user_id="u1", status=OrderStatus.PENDING, total_cents=total_cents, currency="USD")
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def test_create_payment_persists_pending_row(session):
    order = await _make_order(session)

    payment = await service.create_payment(session, order.id, "cod", order.total_cents, "USD")
    await session.commit()

    assert payment.id is not None
    assert payment.order_id == order.id
    assert payment.status == "pending"
    assert payment.amount_cents == order.total_cents


async def test_apply_outcome_updates_payment_fields(session):
    order = await _make_order(session)
    payment = await service.create_payment(session, order.id, "test_card", order.total_cents, "USD")

    from app.modules.payments.providers import PaymentOutcome

    updated = await service.apply_outcome(
        session, payment, PaymentOutcome(status="captured", provider_reference="TEST-abc123")
    )

    assert updated.status == "captured"
    assert updated.provider_reference == "TEST-abc123"


async def test_refund_payment_full(session):
    order = await _make_order(session)
    payment = await service.create_payment(session, order.id, "test_card", 1000, "USD")
    from app.modules.payments.providers import PaymentOutcome

    payment = await service.apply_outcome(
        session, payment, PaymentOutcome(status="captured", provider_reference="TEST-x")
    )
    await session.commit()

    refunded = await service.refund_payment(session, payment, 1000)

    assert refunded.status == "refunded"
    assert refunded.refunded_amount_cents == 1000


async def test_refund_payment_partial(session):
    order = await _make_order(session)
    payment = await service.create_payment(session, order.id, "test_card", 1000, "USD")
    from app.modules.payments.providers import PaymentOutcome

    payment = await service.apply_outcome(
        session, payment, PaymentOutcome(status="captured", provider_reference="TEST-x")
    )
    await session.commit()

    refunded = await service.refund_payment(session, payment, 300)

    assert refunded.status == "partially_refunded"
    assert refunded.refunded_amount_cents == 300


async def test_refund_payment_over_remaining_raises(session):
    order = await _make_order(session)
    payment = await service.create_payment(session, order.id, "test_card", 1000, "USD")
    from app.modules.payments.providers import PaymentOutcome

    payment = await service.apply_outcome(
        session, payment, PaymentOutcome(status="captured", provider_reference="TEST-x")
    )
    await session.commit()

    with pytest.raises(AppError) as exc_info:
        await service.refund_payment(session, payment, 5000)

    assert exc_info.value.code.value == "REFUND_EXCEEDS_PAYMENT_AMOUNT"


async def test_refund_payment_cod_pending_raises_not_refundable(session):
    order = await _make_order(session)
    payment = await service.create_payment(session, order.id, "cod", 1000, "USD")
    await session.commit()

    with pytest.raises(AppError) as exc_info:
        await service.refund_payment(session, payment, 1000)

    assert exc_info.value.code.value == "PAYMENT_NOT_REFUNDABLE"


async def test_get_payment_for_order_returns_none_when_absent(session):
    order = await _make_order(session)

    assert await service.get_payment_for_order(session, order.id) is None


async def test_get_payment_for_order_returns_payment(session):
    order = await _make_order(session)
    payment = await service.create_payment(session, order.id, "cod", 1000, "USD")
    await session.commit()

    found = await service.get_payment_for_order(session, order.id)
    assert found is not None
    assert found.id == payment.id
