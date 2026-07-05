"""Pydantic schemas for the site module (newsletter subscription + contact
form), per docs/CONTRACTS.md.

Note: email-validator (pydantic's EmailStr extra) isn't installed in the
scaffold's venv, so email fields are validated as plain strings here rather
than depending on an extra that isn't part of the given environment (same
convention `auth.schemas` already follows)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NewsletterSubscribeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ContactMessageCreate(BaseModel):
    name: str
    email: str = Field(min_length=3, max_length=255)
    subject: str
    message: str


class ContactMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    subject: str
    message: str
    created_at: datetime
