"""HTTP routes for cart + checkout + order history + invoices (docs/
CONTRACTS.md).

`router` is mounted by the Main Coordinator at `/api/v1` (see app/main.py
comment) -- do not add a prefix here. `admin_router` holds the new
`/admin/orders*` endpoints (same `router`/`admin_router` split pattern as
`auth`'s router.py), also mounted at plain `/api/v1` by the Main
Coordinator.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.auth.models import User
from app.modules.email.service import send_email
from app.modules.email.templates import order_confirmation_email
from app.modules.orders import service
from app.modules.orders.models import Order
from app.modules.orders.schemas import (
    AddCartItemRequest,
    AdminOrderStatusUpdate,
    CartOut,
    CheckoutRequest,
    OrderOut,
    OrderStatusHistoryOut,
    RefundRequest,
    UpdateCartItemRequest,
)
from app.modules.payments.schemas import PaymentOut
from app.shared.pagination import Page, PageParams

router = APIRouter()

# `admin_router` is mounted at plain /api/v1 (paths already include
# /admin/orders) -- resolved once at import time so tests can override this
# exact dependency callable via app.dependency_overrides[require_admin] = ...
admin_router = APIRouter()
require_admin = require_role("admin", "super_admin")


@router.get("/cart", response_model=CartOut)
async def get_cart(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CartOut:
    cart = await service.get_or_create_cart(db, current_user.id)
    return CartOut.model_validate(cart)


@router.post("/cart/items", response_model=CartOut)
async def add_cart_item(
    data: AddCartItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CartOut:
    cart = await service.add_item_to_cart(db, current_user.id, data.product_id, data.quantity)
    return CartOut.model_validate(cart)


@router.patch("/cart/items/{item_id}", response_model=CartOut)
async def update_cart_item(
    item_id: str,
    data: UpdateCartItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CartOut:
    cart = await service.update_cart_item(db, current_user.id, item_id, data.quantity)
    return CartOut.model_validate(cart)


@router.delete("/cart/items/{item_id}", response_model=CartOut)
async def remove_cart_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CartOut:
    cart = await service.remove_cart_item(db, current_user.id, item_id)
    return CartOut.model_validate(cart)


@router.post("/orders/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def checkout(
    data: CheckoutRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await service.checkout(db, current_user.id, data)
    order_out = await service.build_order_out(db, order)

    # Never send synchronously in the request path -- scheduled the same way
    # invitations/password-resets already do.
    background_tasks.add_task(
        send_email,
        current_user.email,
        f"Your Shopora order {order.id} is confirmed",
        order_confirmation_email(current_user.full_name, order_out, order_out.shipping_address),
    )

    return order_out


@router.get("/orders", response_model=Page[OrderOut])
async def list_orders(
    page_params: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[OrderOut]:
    page = await service.list_orders(db, current_user.id, page_params)
    orders: list[Order] = page.items
    items = [await service.build_order_out(db, o) for o in orders]
    return Page[OrderOut](
        items=items,
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await service.get_order(db, current_user.id, order_id)
    return await service.build_order_out(db, order)


@router.get("/orders/{order_id}/timeline", response_model=list[OrderStatusHistoryOut])
async def get_order_timeline(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrderStatusHistoryOut]:
    is_admin = current_user.role in ("admin", "super_admin")
    history = await service.get_order_timeline(db, order_id, current_user.id, is_admin)
    return [OrderStatusHistoryOut.model_validate(h) for h in history]


@router.get("/orders/{order_id}/invoice")
async def download_invoice(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    is_admin = current_user.role in ("admin", "super_admin")
    # Fetch once for the filename (invoice number), then again inside
    # get_invoice_pdf_bytes for the actual render -- both raise the same
    # 404/INVOICE_NOT_AVAILABLE errors for a missing/unauthorized order, so
    # ordering here doesn't change behavior, just cheaply duplicates a read.
    order = await service.get_order_for_view(db, order_id, current_user.id, is_admin)
    order_out = await service.build_order_out(db, order)
    pdf_bytes = await service.get_invoice_pdf_bytes(db, order_id, current_user.id, is_admin)

    filename = order_out.invoice_number or order_id
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )


# ---------------------------------------------------------------------------
# Admin order management -- lives on `admin_router`.
# ---------------------------------------------------------------------------


@admin_router.get("/admin/orders", response_model=Page[OrderOut])
async def admin_list_orders(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Page[OrderOut]:
    params = PageParams(page=page, page_size=page_size)
    orders, total = await service.list_all_orders_admin(db, params, status=status)
    items = [await service.build_order_out(db, o) for o in orders]
    return Page[OrderOut](items=items, total=total, page=params.page, page_size=params.page_size)


@admin_router.patch("/admin/orders/{order_id}/status", response_model=OrderOut)
async def admin_update_order_status(
    order_id: str,
    data: AdminOrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> OrderOut:
    order = await service.admin_update_status(db, order_id, data.status, data.note)
    return await service.build_order_out(db, order)


@admin_router.post("/admin/orders/{order_id}/refund", response_model=PaymentOut)
async def admin_refund_order(
    order_id: str,
    data: RefundRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> PaymentOut:
    payment = await service.admin_refund(db, order_id, data.amount_cents)
    return PaymentOut.model_validate(payment)
