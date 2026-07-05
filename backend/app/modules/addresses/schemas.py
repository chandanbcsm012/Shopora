"""Pydantic schemas for the addresses module, per docs/CONTRACTS.md field
contract for Address."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AddressType = Literal["home", "office", "warehouse", "other"]

# INR Currency & GST (foundation scope): standard 15-character GSTIN shape.
# Format only (not checksum, not government lookup) per docs/CONTRACTS.md.
GSTIN_PATTERN = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"


class AddressCreate(BaseModel):
    full_name: str
    phone: str
    alternate_phone: str | None = None
    company: str | None = None
    address_line1: str
    address_line2: str | None = None
    landmark: str | None = None
    city: str
    district: str | None = None
    state: str
    country: str
    postal_code: str
    delivery_instructions: str | None = None
    address_type: AddressType = "home"
    is_default_shipping: bool = False
    is_default_billing: bool = False
    gstin: str | None = Field(default=None, pattern=GSTIN_PATTERN)


class AddressUpdate(BaseModel):
    """All fields optional; only provided fields are updated."""

    full_name: str | None = None
    phone: str | None = None
    alternate_phone: str | None = None
    company: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    landmark: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    delivery_instructions: str | None = None
    address_type: AddressType | None = None
    is_default_shipping: bool | None = None
    is_default_billing: bool | None = None
    gstin: str | None = Field(default=None, pattern=GSTIN_PATTERN)


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: str
    phone: str
    alternate_phone: str | None = None
    company: str | None = None
    address_line1: str
    address_line2: str | None = None
    landmark: str | None = None
    city: str
    district: str | None = None
    state: str
    country: str
    postal_code: str
    delivery_instructions: str | None = None
    address_type: str
    is_default_shipping: bool
    is_default_billing: bool
    gstin: str | None = None
    created_at: datetime
    updated_at: datetime
