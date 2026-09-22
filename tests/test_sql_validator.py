import pytest

from ai.sql_validator import validate_read_only_sql
from ai.openrouter_provider import OpenRouterProvider
from ai.analyst import run_analyst_query
from config import Settings
from database.models import Base, Business
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_valid_query_is_scoped_and_limited():
    result = validate_read_only_sql(
        "SELECT name, stock_quantity FROM products WHERE business_id = :business_id"
    )
    assert result.sql.endswith("LIMIT 100")


@pytest.mark.parametrize("sql", [
    "DROP TABLE products",
    "UPDATE products SET stock_quantity = 0 WHERE business_id = :business_id",
    "SELECT * FROM products WHERE business_id = :business_id; DELETE FROM products",
    "SELECT * FROM users WHERE business_id = :business_id",
    "SELECT * FROM products LIMIT 1000 WHERE business_id = :business_id",
    "SELECT * FROM products",
])
def test_unsafe_or_unscoped_queries_are_rejected(sql):
    with pytest.raises(ValueError):
        validate_read_only_sql(sql)


def test_openrouter_provider_requires_a_key_without_network_call():
    provider = OpenRouterProvider(Settings(openrouter_api_key=""))
    assert not provider.configured
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        provider._complete("test")


def test_sqlite_adapts_mysql_current_date_function():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    class Provider:
        def propose_sql(self, question, schema):
            from ai.gemini_provider import SqlProposal
            return SqlProposal(sql="SELECT SUM(total_amount) AS total_revenue FROM sales WHERE business_id = :business_id AND DATE(created_at) = CURDATE()", rationale="")
        def explain(self, question, rows):
            return "Calculated from sales."
    with Session(engine) as session:
        business = Business(name="Test", currency="INR")
        session.add(business)
        session.commit()
        result = run_analyst_query(session, provider=Provider(), question="revenue today", business_id=business.id)
        assert result["rows"][0]["total_revenue"] is None
        assert "CURRENT_DATE" in result["sql"]