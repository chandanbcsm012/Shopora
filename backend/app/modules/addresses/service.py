"""Business logic for the addresses module: CRUD for a user's own address
book, plus the "only one default shipping / one default billing address at
a time" invariant, per docs/CONTRACTS.md.

Cross-module contract consumed by `orders`:

    async def get_address_for_user(db, address_id, user_id) -> Address | None

Returns None (never raises) if the address is missing or not owned by that
user — mirrors `catalog.service.get_available_product`'s "None means not
usable, caller decides the error" convention exactly.
"""
from __future__ import annotations

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.shared.error_codes import ErrorCode

from .models import Address
from .schemas import AddressCreate, AddressUpdate


async def list_addresses_for_user(db: AsyncSession, user_id: str) -> list[Address]:
    result = await db.execute(
        select(Address).where(Address.user_id == user_id).order_by(Address.created_at.desc())
    )
    return list(result.scalars().all())


async def _clear_default_flags(db: AsyncSession, user_id: str, *, shipping: bool, billing: bool, exclude_id: str | None = None) -> None:
    """Clear `is_default_shipping`/`is_default_billing` on the user's other
    addresses so at most one address of each kind is marked default. Done in
    the service layer (not a DB constraint), same transaction as the
    create/update that sets the new default."""
    if not shipping and not billing:
        return

    query = select(Address).where(Address.user_id == user_id)
    if exclude_id is not None:
        query = query.where(Address.id != exclude_id)
    others = (await db.execute(query)).scalars().all()

    for other in others:
        changed = False
        if shipping and other.is_default_shipping:
            other.is_default_shipping = False
            changed = True
        if billing and other.is_default_billing:
            other.is_default_billing = False
            changed = True
        if changed:
            db.add(other)


async def create_address(db: AsyncSession, user_id: str, data: AddressCreate) -> Address:
    address = Address(user_id=user_id, **data.model_dump())
    db.add(address)
    # Flush (not commit) so `address.id` is populated -- needed to exclude
    # this brand-new row from `_clear_default_flags`'s query below. Without
    # this, the query's autoflush would already have persisted this address
    # (with its default flags set), and the clearing loop would immediately
    # stomp on the very flags we just set.
    await db.flush()

    await _clear_default_flags(
        db,
        user_id,
        shipping=data.is_default_shipping,
        billing=data.is_default_billing,
        exclude_id=address.id,
    )

    await db.commit()
    await db.refresh(address)
    return address


async def _get_owned_address_or_404(db: AsyncSession, address_id: str, user_id: str) -> Address:
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == user_id)
    )
    address = result.scalar_one_or_none()
    if address is None:
        raise AppError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Address not found.",
            status.HTTP_404_NOT_FOUND,
            {"address_id": address_id},
        )
    return address


async def update_address(db: AsyncSession, address_id: str, user_id: str, data: AddressUpdate) -> Address:
    address = await _get_owned_address_or_404(db, address_id, user_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(address, field, value)
    db.add(address)

    await _clear_default_flags(
        db,
        user_id,
        shipping=updates.get("is_default_shipping", False),
        billing=updates.get("is_default_billing", False),
        exclude_id=address.id,
    )

    await db.commit()
    await db.refresh(address)
    return address


async def delete_address(db: AsyncSession, address_id: str, user_id: str) -> None:
    address = await _get_owned_address_or_404(db, address_id, user_id)
    await db.delete(address)
    await db.commit()


# ---------------------------------------------------------------------------
# Cross-module contract consumed by `orders` (see module docstring).
# ---------------------------------------------------------------------------


async def get_address_for_user(db: AsyncSession, address_id: str, user_id: str) -> Address | None:
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == user_id)
    )
    return result.scalar_one_or_none()
