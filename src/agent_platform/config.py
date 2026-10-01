from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Agent Platform"
    environment: str = "development"
    application_version: str = "0.1.0"
    database_url: str | None = None
    oidc_issuer_url: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_groups_claim: str = "groups"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_default_model: str | None = None
    llm_provider: str = "openai-compatible"
    telemetry_capture_inputs: bool = False
    telemetry_capture_outputs: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
