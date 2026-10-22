import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="")
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def resolved_database_url(self) -> str:
        url = (
            self.database_url
            or os.getenv("POSTGRES_URL")
            or os.getenv("POSTGRES_PRISMA_URL")
            or os.getenv("POSTGRES_URL_NON_POOLING")
            or "postgresql+psycopg://sleeppilot:sleeppilot@localhost:5432/sleeppilot"
        )
        if url.startswith("postgres://"):
            url = "postgresql://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
            url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
        return url


settings = Settings()
