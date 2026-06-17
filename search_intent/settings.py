"""Application settings sourced from environment variables.

Secrets and environment-specific values live here (never in JSON config).
Env var names match those documented in the README.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    env: str = Field("development", alias="SEARCH_INTENT_ENV")
    host: str = Field("0.0.0.0", alias="SEARCH_INTENT_HOST")
    port: int = Field(8080, alias="SEARCH_INTENT_PORT")
    config_dir: str = Field("./config", alias="SEARCH_INTENT_CONFIG_DIR")
    plugin_dir: str = Field("./plugins", alias="SEARCH_INTENT_PLUGIN_DIR")

    # Inbound JWT
    jwt_secret: str | None = Field(None, alias="SEARCH_INTENT_JWT_SECRET")
    jwt_issuer: str | None = Field(None, alias="SEARCH_INTENT_JWT_ISSUER")
    jwt_audience: str | None = Field(None, alias="SEARCH_INTENT_JWT_AUDIENCE")
    jwks_url: str | None = Field(None, alias="SEARCH_INTENT_JWKS_URL")

    # Target API
    target_api_base_url: str | None = Field(None, alias="TARGET_API_BASE_URL")
    target_api_token: str | None = Field(None, alias="TARGET_API_TOKEN")
    target_api_key: str | None = Field(None, alias="TARGET_API_KEY")

    # Cache
    redis_url: str | None = Field(None, alias="REDIS_URL")


def get_settings() -> Settings:
    return Settings()
