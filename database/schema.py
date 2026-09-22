from database.connection import engine
from database.models import Base


def create_schema() -> None:
    """Create the development schema; Alembic will own production migrations later."""
    Base.metadata.create_all(engine)
