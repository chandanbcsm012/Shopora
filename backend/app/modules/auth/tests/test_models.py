"""Model-level tests for auth.models — run against an in-memory sqlite
engine, independent of the FastAPI app fixture (see backend/tests/conftest.py
for the API-level equivalent pattern)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.auth.models import RefreshToken, User
from app.shared.base_model import Base, utcnow


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


async def test_create_user_sets_defaults(session):
    user = User(
        email="alice@example.com",
        hashed_password="hashed-pw",
        full_name="Alice Example",
        role="customer",
    )
    session.add(user)
    await session.commit()

    assert user.id
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None


async def test_duplicate_email_raises_integrity_error(session):
    session.add(User(email="dup@example.com", hashed_password="x", full_name="A"))
    await session.commit()

    session.add(User(email="dup@example.com", hashed_password="y", full_name="B"))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_refresh_token_fk_and_relationship(session):
    user = User(email="bob@example.com", hashed_password="x", full_name="Bob")
    session.add(user)
    await session.commit()

    token = RefreshToken(
        user_id=user.id,
        token_hash="opaque-hash-value",
        expires_at=utcnow(),
    )
    session.add(token)
    await session.commit()

    assert token.id
    assert token.revoked_at is None

    await session.refresh(user, attribute_names=["refresh_tokens"])
    assert len(user.refresh_tokens) == 1
    assert user.refresh_tokens[0].id == token.id


async def test_refresh_token_can_be_revoked(session):
    user = User(email="carol@example.com", hashed_password="x", full_name="Carol")
    session.add(user)
    await session.commit()

    token = RefreshToken(user_id=user.id, token_hash="h", expires_at=utcnow())
    session.add(token)
    await session.commit()

    token.revoked_at = utcnow()
    await session.commit()
    await session.refresh(token)

    assert token.revoked_at is not None
