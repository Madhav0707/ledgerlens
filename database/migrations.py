from sqlalchemy import inspect, text

from database.connection import engine


def apply_sqlite_dev_migrations() -> None:
    """Apply small forward-only migrations until Alembic is introduced."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "sales" not in inspector.get_table_names():
        sales_columns = set()
    else:
        sales_columns = {column["name"] for column in inspector.get_columns("sales")}
    payment_columns = (
        {column["name"] for column in inspector.get_columns("payments")}
        if "payments" in inspector.get_table_names() else set()
    )
    purchase_columns = (
        {column["name"] for column in inspector.get_columns("purchases")}
        if "purchases" in inspector.get_table_names() else set()
    )
    sale_item_columns = (
        {column["name"] for column in inspector.get_columns("sale_items")}
        if "sale_items" in inspector.get_table_names() else set()
    )
    with engine.begin() as connection:
        if "reference" not in sales_columns:
            connection.execute(text("ALTER TABLE sales ADD COLUMN reference VARCHAR(80)"))
        if "purchase_id" not in payment_columns:
            connection.execute(text("ALTER TABLE payments ADD COLUMN purchase_id INTEGER"))
        if "reference" not in purchase_columns:
            connection.execute(text("ALTER TABLE purchases ADD COLUMN reference VARCHAR(80)"))
        if "unit_cost" not in sale_item_columns:
            connection.execute(text("ALTER TABLE sale_items ADD COLUMN unit_cost NUMERIC(12, 2)"))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_sale_business_reference "
            "ON sales (business_id, reference)"
        ))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_business_reference "
            "ON purchases (business_id, reference)"
        ))