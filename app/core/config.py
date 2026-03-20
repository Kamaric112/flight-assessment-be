from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BFF_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Flight BFF"
    debug: bool = False
    upstream_base_url: str = "https://mock-travel-api.vercel.app"
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 10.0
    max_connections: int = 20
    max_keepalive_connections: int = 10
    retry_attempts: int = 3
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_recovery_seconds: int = 20
    airport_cache_ttl_seconds: int = 86400
    booking_cache_ttl_seconds: int = 60
    default_page_size: int = 10
    max_page_size: int = Field(default=50)


@lru_cache
def get_settings() -> Settings:
    return Settings()

