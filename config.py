from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./ledgerlens.db"
    app_secret_key: str = "development-only-change-me"
    auto_create_schema: bool = True
    session_timeout_minutes: int = 480
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    ai_provider: str = "gemini"
    openrouter_api_key: str = ""
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime(settings: Settings) -> None:
    if settings.app_env.lower() != "production":
        return
    if settings.app_secret_key in {"", "development-only-change-me", "replace-this-in-development"}:
        raise RuntimeError("Production requires a unique APP_SECRET_KEY.")
    if settings.database_url.startswith("sqlite"):
        raise RuntimeError("Production requires PostgreSQL; SQLite is for local development only.")
    if settings.auto_create_schema:
        raise RuntimeError("Production schema creation is disabled; run migrations before startup.")
