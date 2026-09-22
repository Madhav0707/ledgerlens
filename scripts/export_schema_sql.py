from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_mock_engine

from database.models import Base


statements: list[str] = []


def dump(sql, *args, **kwargs):
    statements.append(str(sql.compile(dialect=engine.dialect)).rstrip() + ";")


engine = create_mock_engine("postgresql+psycopg://", dump)
Base.metadata.create_all(engine)
Path("schema.sql").write_text("\n\n".join(statements) + "\n", encoding="utf-8")
print(f"Exported {len(statements)} PostgreSQL statements to schema.sql")
