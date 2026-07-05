# Owned by the Database Team. Define Category, Brand, Product, and
# ProductImage SQLAlchemy models here per docs/CONTRACTS.md.
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin, UUIDPKMixin


class Category(UUIDPKMixin, TimestampMixin, Base):
    """catalog.Category — id, name, slug (unique), parent_id (FK
    categories, nullable), image_url (nullable, admin panel addition),
    created_at, updated_at (per docs/CONTRACTS.md)."""

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, index=True
    )
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    parent: Mapped["Category | None"] = relationship(
        remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list["Category"]] = relationship(back_populates="parent")
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Brand(UUIDPKMixin, TimestampMixin, Base):
    """catalog.Brand — id, name, slug (unique), created_at, updated_at
    (per docs/CONTRACTS.md)."""

    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="brand")


class Product(UUIDPKMixin, TimestampMixin, Base):
    """catalog.Product — id, name, slug (unique), description, brand_id
    (FK brands, nullable), category_id (FK categories), price_cents,
    currency, sku (unique), stock_quantity, is_active, created_at,
    updated_at (per docs/CONTRACTS.md).

    `stock_quantity` is a placeholder single-warehouse counter per the
    CONTRACTS.md note; a future Inventory module will own real stock
    ledgers/reservations without changing this field's shape.
    """

    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_id: Mapped[str | None] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    brand: Mapped["Brand | None"] = relationship(back_populates="products")
    category: Mapped["Category"] = relationship(back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )


class ProductImage(UUIDPKMixin, Base):
    """catalog.ProductImage — id, product_id (FK products), url, alt_text,
    sort_order (per docs/CONTRACTS.md)."""

    __tablename__ = "product_images"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped["Product"] = relationship(back_populates="images")
