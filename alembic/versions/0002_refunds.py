"""Add refund records for sale returns."""

from alembic import op
import sqlalchemy as sa

revision = "0002_refunds"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "refunds" in inspector.get_table_names():
        return
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("return_id", sa.Integer(), sa.ForeignKey("returns.id"), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_refunds_business_id", "refunds", ["business_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "refunds" not in inspector.get_table_names():
        return
    op.drop_index("ix_refunds_business_id", table_name="refunds")
    op.drop_table("refunds")
