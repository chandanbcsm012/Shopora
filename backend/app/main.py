from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler, validation_error_handler
from app.modules.addresses.router import router as addresses_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import admin_router as auth_admin_router
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import admin_router as catalog_admin_router
from app.modules.catalog.router import router as catalog_router
from app.modules.media.router import router as media_router
from app.modules.orders.router import admin_router as orders_admin_router
from app.modules.orders.router import router as orders_router
from app.modules.site.router import admin_router as site_admin_router
from app.modules.site.router import router as site_router
from app.modules.wishlist.router import router as wishlist_router

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(auth_admin_router, prefix="/api/v1", tags=["auth-admin"])
app.include_router(catalog_router, prefix="/api/v1", tags=["catalog"])
app.include_router(catalog_admin_router, prefix="/api/v1", tags=["catalog-admin"])
app.include_router(orders_router, prefix="/api/v1", tags=["orders"])
app.include_router(orders_admin_router, prefix="/api/v1", tags=["orders-admin"])
app.include_router(media_router, prefix="/api/v1/media", tags=["media"])
app.include_router(audit_router, prefix="/api/v1", tags=["audit"])
app.include_router(addresses_router, prefix="/api/v1", tags=["addresses"])
app.include_router(wishlist_router, prefix="/api/v1", tags=["wishlist"])
app.include_router(site_router, prefix="/api/v1", tags=["site"])
app.include_router(site_admin_router, prefix="/api/v1", tags=["site-admin"])

MEDIA_STORAGE_DIR = Path(__file__).resolve().parent.parent / "media_storage"
MEDIA_STORAGE_DIR.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_STORAGE_DIR)), name="media")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
