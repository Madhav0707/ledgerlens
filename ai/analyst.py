from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai.gemini_provider import GeminiProvider
from ai.sql_validator import validate_read_only_sql

SCHEMA_DESCRIPTION = """
businesses(id, name); customers(id, business_id, name); products(id, business_id, name, sku, cost_price, selling_price, stock_quantity, low_stock_threshold);
sales(id, business_id, customer_id, reference, total_amount, status, created_at); sale_items(sale_id, product_id, quantity, unit_price, unit_cost);
payments(id, business_id, sale_id, purchase_id, amount, method, created_at); purchases(id, business_id, supplier_id, reference, total_amount, status, created_at);
purchase_items(purchase_id, product_id, quantity, unit_cost); suppliers(id, business_id, name); inventory_movements(id, business_id, product_id, quantity_delta, reason, created_at).
"""


def run_analyst_query(
    session: Session,
    *,
    provider: GeminiProvider,
    question: str,
    business_id: int,
) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("Enter a question first.")
    proposal = provider.propose_sql(question.strip(), SCHEMA_DESCRIPTION)
    validated = validate_read_only_sql(proposal.sql)
    sql = validated.sql
    if session.bind is not None and session.bind.dialect.name == "sqlite":
        sql = sql.replace("CURDATE()", "CURRENT_DATE").replace("curdate()", "CURRENT_DATE")
    try:
        rows = [
            dict(row)
            for row in session.execute(text(sql), {"business_id": business_id}).mappings().all()
        ]
    except SQLAlchemyError as error:
        raise RuntimeError(
            "The generated read-only query could not run on the configured database. "
            "Try asking with a simpler date range or a specific metric."
        ) from error
    return {
        "sql": sql,
        "rationale": proposal.rationale,
        "rows": rows,
        "explanation": provider.explain(question, rows),
        "provenance": "Fact + Calculated + AI Interpretation",
    }