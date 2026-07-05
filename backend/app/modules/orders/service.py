"""Service layer for the orders module: cart management + checkout + order
history + admin order management + invoices, per docs/CONTRACTS.md.

Cross-module dependency note (docs/ARCHITECTURE.md): orders calls into
catalog/addresses/payments' service layers only (never their SQLAlchemy
models), and never into auth beyond the `get_current_user` router
dependency. The Catalog Team is building
`app.modules.catalog.service.get_available_product` /
`app.modules.catalog.schemas.ProductOrderView` in parallel with this module,
so at the time this file was originally written those may not exist yet on
disk. The import below is wrapped in a try/except so that this module stays
importable (and unit-testable via monkeypatching `get_available_product`)
regardless of whether the Catalog Team has landed their file yet; once it
lands, the real implementation is picked up automatically with no change
needed here.

`addresses` and `payments` are new sibling modules built alongside this
Checkout/Addresses/Payments/Invoices extension, so their service layers are
imported directly (no try/except needed).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.modules.addresses import service as addresses_service
from app.modules.addresses.schemas import AddressOut
from app.modules.orders.invoice_pdf import generate_invoice_pdf
from app.modules.orders.models import (
    Cart,
    CartItem,
    Invoice,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
)
from app.modules.orders.schemas import CheckoutRequest, OrderItemOut, OrderOut
from app.modules.orders.tax import calculate_gst
from app.modules.payments import service as payments_service
from app.modules.payments.models import Payment
from app.modules.payments.providers import get_provider
from app.shared.error_codes import ErrorCode
from app.shared.pagination import Page, PageParams

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids a hard runtime dep
    from app.modules.catalog.schemas import ProductOrderView

try:
    from app.modules.catalog.service import get_available_product
except ImportError:  # pragma: no cover - Catalog Team's module not landed yet

    async def get_available_product(db: AsyncSession, product_id: str) -> "ProductOrderView | None":
        raise RuntimeError(
            "app.modules.catalog.service.get_available_product is not available yet. "
            "The Catalog Team's service.py has not been implemented/imported."
        )


# Raw core Table (not an ORM model import) used solely to read a product's
# `sku` at checkout time so `OrderItem.sku_snapshot` can be populated without
# importing catalog's `Product` model — see docs/ARCHITECTURE.md's rule that
# a module may only reach another module's *tables* via raw FK columns /
# ad hoc reads by table name, never its SQLAlchemy model class.
_products_table = table("products", column("id"), column("sku"))


async def _get_product_sku(db: AsyncSession, product_id: str) -> str:
    result = await db.execute(select(_products_table.c.sku).where(_products_table.c.id == product_id))
    sku = result.scalar_one_or_none()
    return sku or ""


async def get_or_create_cart(db: AsyncSession, user_id: str) -> Cart:
    result = await db.execute(
        select(Cart).where(Cart.user_id == user_id).options(selectinload(Cart.items))
    )
    cart = result.scalar_one_or_none()
    if cart is not None:
        return cart

    cart = Cart(user_id=user_id)
    db.add(cart)
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


def _find_cart_item_or_404(cart: Cart, item_id: str) -> CartItem:
    # Look up within the already-loaded `cart.items` collection (rather than
    # a fresh query) and mutate/remove through that collection everywhere,
    # so SQLAlchemy's cascade="all, delete-orphan" keeps the in-memory
    # collection and the DB rows consistent. Deleting a CartItem out of band
    # (e.g. a bare `db.delete(item)` on a row fetched via a separate query)
    # leaves a stale/deleted instance sitting in this identity-mapped Cart's
    # already-loaded `items` collection, which then resurfaces (and blows
    # up) on the next read of that same collection within the session.
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Cart item not found.", 404)
    return item


async def add_item_to_cart(db: AsyncSession, user_id: str, product_id: str, quantity: int) -> Cart:
    product = await get_available_product(db, product_id)
    if product is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Product not found.", 404)

    cart = await get_or_create_cart(db, user_id)

    existing = next((i for i in cart.items if i.product_id == product_id), None)
    if existing is not None:
        new_quantity = existing.quantity + quantity
        if new_quantity > product.stock_quantity:
            raise AppError(
                ErrorCode.INSUFFICIENT_STOCK,
                f"Only {product.stock_quantity} unit(s) of '{product.name}' available.",
                409,
            )
        existing.quantity = new_quantity
        existing.unit_price_cents = product.price_cents
        db.add(existing)
    else:
        if quantity > product.stock_quantity:
            raise AppError(
                ErrorCode.INSUFFICIENT_STOCK,
                f"Only {product.stock_quantity} unit(s) of '{product.name}' available.",
                409,
            )
        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=product_id,
                quantity=quantity,
                unit_price_cents=product.price_cents,
            )
        )

    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def update_cart_item(db: AsyncSession, user_id: str, item_id: str, quantity: int) -> Cart:
    cart = await get_or_create_cart(db, user_id)
    item = _find_cart_item_or_404(cart, item_id)
    item.quantity = quantity
    db.add(item)
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


async def remove_cart_item(db: AsyncSession, user_id: str, item_id: str) -> Cart:
    cart = await get_or_create_cart(db, user_id)
    item = _find_cart_item_or_404(cart, item_id)
    cart.items.remove(item)  # triggers delete-orphan cascade on flush
    await db.commit()
    await db.refresh(cart, attribute_names=["items"])
    return cart


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------


async def checkout(db: AsyncSession, user_id: str, data: CheckoutRequest) -> Order:
    cart = await get_or_create_cart(db, user_id)
    if not cart.items:
        raise AppError(ErrorCode.EMPTY_CART, "Cannot checkout an empty cart.", 400)

    # 1. Existing cart/stock validation (unchanged).
    order_items: list[OrderItem] = []
    currency = "USD"
    for cart_item in cart.items:
        product = await get_available_product(db, cart_item.product_id)
        if product is None:
            raise AppError(
                ErrorCode.PRODUCT_INACTIVE,
                f"Product {cart_item.product_id} is no longer available.",
                409,
            )
        if cart_item.quantity > product.stock_quantity:
            raise AppError(
                ErrorCode.INSUFFICIENT_STOCK,
                f"Only {product.stock_quantity} unit(s) of '{product.name}' available.",
                409,
            )
        currency = product.currency
        sku = await _get_product_sku(db, cart_item.product_id)
        order_items.append(
            OrderItem(
                product_id=cart_item.product_id,
                product_name_snapshot=product.name,
                sku_snapshot=sku,
                quantity=cart_item.quantity,
                # Price is locked in at add-to-cart time; checkout re-validates
                # *stock*, not price, so the customer-facing total doesn't
                # shift silently between add-to-cart and checkout.
                unit_price_cents=cart_item.unit_price_cents,
            )
        )

    total_cents = sum(oi.quantity * oi.unit_price_cents for oi in order_items)

    # 2. Resolve both addresses -- 404 if either is missing/not owned.
    shipping_address = await addresses_service.get_address_for_user(
        db, data.shipping_address_id, user_id
    )
    if shipping_address is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Shipping address not found.", 404)

    billing_address = await addresses_service.get_address_for_user(
        db, data.billing_address_id, user_id
    )
    if billing_address is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Billing address not found.", 404)

    # 3. Create the Order (+ OrderItems, + the two address FKs) at
    # status="pending", insert the (null -> pending) history row, empty the
    # cart -- all as today, just with addresses attached.
    order = Order(
        user_id=user_id,
        status=OrderStatus.PENDING,
        total_cents=total_cents,
        currency=currency,
        shipping_address_id=shipping_address.id,
        billing_address_id=billing_address.id,
    )
    order.items = order_items

    # INR Currency & GST (foundation scope): compute tax now that
    # `total_cents` is known and before the Payment is created below (so the
    # correct tax-inclusive amount gets charged). GST is India-specific --
    # only ever computed for INR orders -- and `calculate_gst` itself is a
    # no-op (returns None) unless `settings.gst_enabled` is on and the
    # shipping address carries a state, so this leaves every existing
    # USD/no-tax checkout path byte-for-byte unchanged.
    amount_to_charge_cents = total_cents
    if order.currency == "INR":
        breakdown = calculate_gst(total_cents, shipping_address.state)
        if breakdown is not None:
            order.taxable_amount_cents = breakdown.taxable_amount_cents
            order.cgst_cents = breakdown.cgst_cents
            order.sgst_cents = breakdown.sgst_cents
            order.igst_cents = breakdown.igst_cents
            order.tax_total_cents = breakdown.tax_total_cents
            order.grand_total_cents = breakdown.grand_total_cents
            amount_to_charge_cents = breakdown.grand_total_cents

    db.add(order)
    await db.flush()  # assign order.id for the history row FK below

    db.add(
        OrderStatusHistory(order_id=order.id, from_status=None, to_status=OrderStatus.PENDING.value)
    )

    # Empty the cart through its loaded collection (not a bare `db.delete`
    # per row) so the delete-orphan cascade updates both the DB and this
    # identity-mapped Cart's in-memory `items` list together -- see the note
    # on `_find_cart_item_or_404` above for why that matters.
    cart.items.clear()

    await db.commit()
    await db.refresh(order, attribute_names=["items"])

    # 4. Create a Payment row and run it through the provider.
    payment = await payments_service.create_payment(
        db, order.id, data.payment_method, amount_to_charge_cents, currency
    )
    provider = get_provider(data.payment_method)
    process_kwargs = (
        {"outcome": data.test_card_outcome} if data.payment_method == "test_card" else {}
    )
    outcome = await provider.process(payment, **process_kwargs)
    payment = await payments_service.apply_outcome(db, payment, outcome)

    if outcome.status in ("captured", "pending"):
        # 5. "paid" here means "order confirmed, payment method accepted" --
        # even for COD, where cash hasn't literally been collected yet. The
        # real distinction ("cash still owed" vs. "already charged") lives on
        # Payment.status, not Order.status.
        previous_status = order.status
        order.status = OrderStatus.PAID
        db.add(order)
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=previous_status.value,
                to_status=OrderStatus.PAID.value,
            )
        )

        invoice = Invoice(order_id=order.id)
        db.add(invoice)

        await db.commit()
        await db.refresh(order, attribute_names=["items"])
        return order

    # 6. outcome.status == "failed": commit the (cancelled) audit trail, then
    # raise -- the endpoint returns an error, not a 201, even though a
    # (cancelled) Order row now exists.
    previous_status = order.status
    order.status = OrderStatus.CANCELLED
    db.add(order)
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=previous_status.value,
            to_status=OrderStatus.CANCELLED.value,
            note=payment.failure_reason,
        )
    )
    await db.commit()

    raise AppError(ErrorCode.PAYMENT_FAILED, payment.failure_reason or "Payment failed.", 402)


# ---------------------------------------------------------------------------
# Order reads (owner-scoped) + OrderOut enrichment
# ---------------------------------------------------------------------------


async def list_orders(db: AsyncSession, user_id: str, page_params: PageParams) -> Page[Order]:
    base_query = select(Order).where(Order.user_id == user_id)

    count_result = await db.execute(select(Order.id).where(Order.user_id == user_id))
    total = len(count_result.scalars().all())

    result = await db.execute(
        base_query.options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .offset(page_params.offset)
        .limit(page_params.page_size)
    )
    orders = result.scalars().all()

    # NOTE: `Page` (app.shared.pagination) is a strict Pydantic v2 generic.
    # Order is a plain SQLAlchemy model (not a Pydantic-compatible type), so
    # parameterizing as `Page[Order]` would fail pydantic-core schema
    # generation. Instantiating the generic unparameterized (as below) is
    # supported by pydantic v2 and passes ORM instances through untouched;
    # the router is responsible for converting each Order -> OrderOut before
    # exposing a real `Page[OrderOut]` over the wire.
    return Page(items=orders, total=total, page=page_params.page, page_size=page_params.page_size)


async def get_order(db: AsyncSession, user_id: str, order_id: str) -> Order:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items))
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Order not found.", 404)
    return order


async def _get_invoice_for_order(db: AsyncSession, order_id: str) -> Invoice | None:
    result = await db.execute(select(Invoice).where(Invoice.order_id == order_id))
    return result.scalar_one_or_none()


async def build_order_out(db: AsyncSession, order: Order) -> OrderOut:
    """Enrich a raw `Order` ORM instance into the wire-level `OrderOut`,
    embedding its shipping/billing addresses (fetched through addresses'
    service layer, never the Address model directly), current payment
    status, and invoice number (if any). Used by every router path that
    returns an order: checkout, get, list, and the admin list."""

    shipping_address: AddressOut | None = None
    if order.shipping_address_id:
        address = await addresses_service.get_address_for_user(
            db, order.shipping_address_id, order.user_id
        )
        shipping_address = AddressOut.model_validate(address) if address else None

    billing_address: AddressOut | None = None
    if order.billing_address_id:
        address = await addresses_service.get_address_for_user(
            db, order.billing_address_id, order.user_id
        )
        billing_address = AddressOut.model_validate(address) if address else None

    payment = await payments_service.get_payment_for_order(db, order.id)
    payment_status = payment.status if payment is not None else None

    invoice = await _get_invoice_for_order(db, order.id)
    invoice_number = f"INV-{invoice.sequence_number:06d}" if invoice is not None else None

    return OrderOut(
        id=order.id,
        status=order.status,
        total_cents=order.total_cents,
        currency=order.currency,
        items=[OrderItemOut.model_validate(item) for item in order.items],
        created_at=order.created_at,
        shipping_address=shipping_address,
        billing_address=billing_address,
        payment_status=payment_status,
        invoice_number=invoice_number,
        taxable_amount_cents=order.taxable_amount_cents,
        cgst_cents=order.cgst_cents,
        sgst_cents=order.sgst_cents,
        igst_cents=order.igst_cents,
        tax_total_cents=order.tax_total_cents,
        grand_total_cents=order.grand_total_cents,
    )


async def get_order_for_view(
    db: AsyncSession, order_id: str, user_id: str | None, is_admin: bool
) -> Order:
    query = select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    if not is_admin:
        query = query.where(Order.user_id == user_id)
    order = (await db.execute(query)).scalar_one_or_none()
    if order is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Order not found.", 404)
    return order


async def get_order_timeline(
    db: AsyncSession, order_id: str, user_id: str, is_admin: bool
) -> list[OrderStatusHistory]:
    order = await get_order_for_view(db, order_id, user_id, is_admin)
    result = await db.execute(
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.created_at.asc())
    )
    return list(result.scalars().all())


async def get_invoice_pdf_bytes(
    db: AsyncSession, order_id: str, user_id: str, is_admin: bool
) -> bytes:
    order = await get_order_for_view(db, order_id, user_id, is_admin)
    invoice = await _get_invoice_for_order(db, order.id)
    if invoice is None:
        raise AppError(
            ErrorCode.INVOICE_NOT_AVAILABLE, "Invoice not available for this order.", 404
        )

    shipping_address = None
    if order.shipping_address_id:
        shipping_address = await addresses_service.get_address_for_user(
            db, order.shipping_address_id, order.user_id
        )
    billing_address = None
    if order.billing_address_id:
        billing_address = await addresses_service.get_address_for_user(
            db, order.billing_address_id, order.user_id
        )

    payment = await payments_service.get_payment_for_order(db, order.id)
    # Transient, non-persisted attributes -- used only by the PDF renderer to
    # print "payment method + status" per docs/CONTRACTS.md; never flushed to
    # the DB since `payment_method`/`payment_status` aren't mapped columns.
    order.payment_method = payment.method if payment is not None else None
    order.payment_status = payment.status if payment is not None else None

    return generate_invoice_pdf(order, invoice, shipping_address, billing_address)


# ---------------------------------------------------------------------------
# Admin order management
# ---------------------------------------------------------------------------


async def list_all_orders_admin(
    db: AsyncSession, params: PageParams, status: str | None = None
) -> tuple[list[Order], int]:
    query = select(Order).options(selectinload(Order.items))
    count_query = select(func.count()).select_from(Order)

    if status is not None:
        query = query.where(Order.status == status)
        count_query = count_query.where(Order.status == status)

    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(Order.created_at.desc()).offset(params.offset).limit(params.page_size)
    items = list((await db.execute(query)).scalars().unique().all())

    return items, total


async def admin_update_status(
    db: AsyncSession, order_id: str, new_status: str, note: str | None
) -> Order:
    order = await get_order_for_view(db, order_id, None, is_admin=True)

    previous_status = order.status
    order.status = OrderStatus(new_status)
    db.add(order)
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=previous_status.value,
            to_status=order.status.value,
            note=note,
        )
    )
    await db.commit()
    await db.refresh(order, attribute_names=["items"])
    return order


async def admin_refund(db: AsyncSession, order_id: str, amount_cents: int | None) -> Payment:
    order = await get_order_for_view(db, order_id, None, is_admin=True)

    payment = await payments_service.get_payment_for_order(db, order.id)
    if payment is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Payment not found for this order.", 404)

    remaining = payment.amount_cents - payment.refunded_amount_cents
    refund_amount = amount_cents if amount_cents is not None else remaining

    return await payments_service.refund_payment(db, payment, refund_amount)
