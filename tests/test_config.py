import pytest

from config import Settings, validate_runtime


def test_development_runtime_allows_local_sqlite():
    validate_runtime(Settings(app_env="development", database_url="sqlite:///test.db"))


@pytest.mark.parametrize(
    "settings",
    [
        Settings(app_env="production", database_url="sqlite:///test.db", app_secret_key="real", auto_create_schema=False),
        Settings(app_env="production", database_url="postgresql+psycopg://db", app_secret_key="development-only-change-me", auto_create_schema=False),
        Settings(app_env="production", database_url="postgresql+psycopg://db", app_secret_key="real", auto_create_schema=True),
    ],
)
def test_production_runtime_rejects_unsafe_defaults(settings):
    with pytest.raises(RuntimeError):
        validate_runtime(settings)


def test_production_runtime_accepts_explicit_safe_configuration():
    validate_runtime(Settings(
        app_env="production",
        database_url="postgresql+psycopg://ledgerlens:secret@db/ledgerlens",
        app_secret_key="a-long-production-secret",
        auto_create_schema=False,
    ))