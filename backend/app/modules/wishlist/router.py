"""HTTP routes for the wishlist module (self-service wishlist), per
docs/CONTRACTS.md. Mounted by the Main Coordinator at `/api/v1` (paths here
carry no prefix of their own). All routes are scoped to `get_current_user`
— a user only ever sees/manages their own wishlist, no admin gating."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

from . import service
from .schemas import AddToWishlistRequest, WishlistItemOut

router = APIRouter()


@router.get("/wishlist", response_model=list[WishlistItemOut])
async def list_wishlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WishlistItemOut]:
    items = await service.list_wishlist(db, current_user.id)
    return [WishlistItemOut.model_validate(i) for i in items]


@router.post("/wishlist", response_model=WishlistItemOut, status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    data: AddToWishlistRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WishlistItemOut:
    item = await service.add_to_wishlist(db, current_user.id, data.product_id)
    return WishlistItemOut.model_validate(item)


@router.delete("/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.remove_from_wishlist(db, current_user.id, product_id)
