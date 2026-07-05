"""HTTP routes for the addresses module (self-service address book), per
docs/CONTRACTS.md. Mounted by the Main Coordinator at `/api/v1` (paths here
carry no prefix of their own). All routes are scoped to `get_current_user`
— a user only ever sees/manages their own addresses, no admin gating."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

from . import service
from .schemas import AddressCreate, AddressOut, AddressUpdate

router = APIRouter()


@router.get("/addresses", response_model=list[AddressOut])
async def list_addresses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AddressOut]:
    addresses = await service.list_addresses_for_user(db, current_user.id)
    return [AddressOut.model_validate(a) for a in addresses]


@router.post("/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(
    data: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AddressOut:
    address = await service.create_address(db, current_user.id, data)
    return AddressOut.model_validate(address)


@router.patch("/addresses/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: str,
    data: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AddressOut:
    address = await service.update_address(db, address_id, current_user.id, data)
    return AddressOut.model_validate(address)


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_address(db, address_id, current_user.id)
