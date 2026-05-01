from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["dev", "prod"] = "dev"

    DATABASE_URL: str | None = None
    DATABASE_URL_DEV: str = (
        "postgresql+asyncpg://orion:orion@localhost:5433/orion_dev"
    )

    CLERK_ISSUER: str | None = None
    ALLOWED_ORIGINS: str = ""

    @staticmethod
    def _normalize(url: str) -> str:
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        return url

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self._normalize(self.DATABASE_URL)
        if self.APP_ENV == "prod":
            raise RuntimeError(
                "APP_ENV=prod requires DATABASE_URL to be set explicitly"
            )
        return self._normalize(self.DATABASE_URL_DEV)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
