from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Shopora"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://ecommerce:ecommerce@localhost:5432/ecommerce"

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, value: str) -> str:
        # Managed Postgres providers (Render, Railway, etc.) hand out
        # postgres:// / postgresql:// URLs; SQLAlchemy's async engine needs
        # the +asyncpg driver suffix.
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    jwt_secret: str = "dev-secret-change-me-please-32-bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:5173"]

    # Used to build links inside transactional emails (invitations, password
    # resets) — the frontend route, not the API.
    frontend_url: str = "http://localhost:5173"

    invitation_token_expire_hours: int = 48
    password_reset_token_expire_minutes: int = 60
    password_reset_rate_limit_per_hour: int = 3

    smtp_host: str = "localhost"
    smtp_port: int = 1025  # Mailpit's default SMTP port (see docker-compose.yml)
    smtp_use_tls: bool = False
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@shopora.local"
    smtp_from_name: str = "Shopora"

    # INR Currency & GST (foundation scope) -- GST is India-specific and
    # fully opt-in: `gst_enabled` defaults to False so existing USD-only
    # checkout behavior is completely unaffected unless explicitly enabled.
    gst_enabled: bool = False
    default_gst_rate_percent: float = 18.0
    seller_state: str = "Maharashtra"
    seller_gstin: str | None = None
    tax_inclusive_pricing: bool = False


settings = Settings()
