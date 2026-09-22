from database.connection import normalize_database_url


def test_postgres_urls_use_psycopg_driver():
    assert normalize_database_url("postgresql://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalize_database_url("postgres://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"


def test_sqlite_url_is_unchanged():
    assert normalize_database_url("sqlite:///ledgerlens.db") == "sqlite:///ledgerlens.db"