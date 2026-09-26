import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

MAX_ROWS = 100
ALLOWED_TABLES = {
    "businesses",
    "customers",
    "products",
    "sales",
    "sale_items",
    "payments",
    "purchases",
    "purchase_items",
    "suppliers",
    "inventory_movements",
    "documents",
    "document_chunks",
    "audit_logs",
    "returns",
    "return_items",
    "refunds",
}
FORBIDDEN_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|REPLACE|TRUNCATE|GRANT|REVOKE|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)
TABLE_PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)


@dataclass(frozen=True)
class ValidatedQuery:
    statement: TextClause
    sql: str


def validate_read_only_sql(sql: str) -> ValidatedQuery:
    candidate = sql.strip()
    if not candidate:
        raise ValueError("The AI returned an empty SQL query.")
    if candidate.endswith(";"):
        candidate = candidate[:-1].rstrip()
    if ";" in candidate:
        raise ValueError("Multiple SQL statements are not allowed.")
    if "--" in candidate or "/*" in candidate or "*/" in candidate:
        raise ValueError("SQL comments are not allowed.")
    if not re.match(r"^(SELECT)\b", candidate, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed.")
    if FORBIDDEN_WORDS.search(candidate):
        raise ValueError("The query contains a forbidden SQL operation.")

    tables = {match.group(1).lower() for match in TABLE_PATTERN.finditer(candidate)}
    unknown_tables = tables - ALLOWED_TABLES
    if unknown_tables:
        raise ValueError(f"Unauthorized table(s): {', '.join(sorted(unknown_tables))}.")
    if not tables:
        raise ValueError("The query must read from an approved business table.")
    if not re.search(r"\bbusiness_id\s*=\s*:business_id\b", candidate, re.IGNORECASE):
        raise ValueError("The query must contain an independent business_id scope filter.")

    limit_match = re.search(r"\bLIMIT\s+(\d+)", candidate, re.IGNORECASE)
    if limit_match and int(limit_match.group(1)) > MAX_ROWS:
        raise ValueError(f"Query limit cannot exceed {MAX_ROWS} rows.")
    if not limit_match:
        candidate = f"{candidate} LIMIT {MAX_ROWS}"
    return ValidatedQuery(statement=text(candidate), sql=candidate)