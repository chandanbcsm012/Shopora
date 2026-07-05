from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Note: email-validator (pydantic's EmailStr extra) isn't installed in the
# scaffold's venv, so email fields are validated as plain strings here
# rather than depending on an extra that isn't part of the given environment.


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8)
    full_name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Admin panel additions
# ---------------------------------------------------------------------------
class BootstrapStatus(BaseModel):
    admin_exists: bool


class BootstrapRequest(BaseModel):
    """Same shape as UserCreate; creates the first admin user."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8)
    full_name: str


class UserRoleUpdate(BaseModel):
    role: Literal["super_admin", "admin", "manager", "customer"]


class UserStatusUpdate(BaseModel):
    is_active: bool


# ---------------------------------------------------------------------------
# Invitation / password reset additions
# ---------------------------------------------------------------------------


class InviteUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str
    role: Literal["super_admin", "admin", "manager", "customer"]
    notes: str | None = None


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None


class InvitationPreview(BaseModel):
    email: str
    full_name: str
    role: str
    expires_at: datetime


class AcceptInvitationRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
