from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import AuditLog, Base, Business, Product
from services.inventory_service import create_product


def test_product_creation_writes_business_scoped_audit_log():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Audit Shop", currency="INR")
        session.add(business)
        session.flush()
        product = create_product(
            session, business_id=business.id, name="Phone", sku="AUDIT-1",
            cost_price=Decimal("100"), selling_price=Decimal("150"),
            stock_quantity=2, low_stock_threshold=1,
        )
        session.commit()
        log = session.scalar(select(AuditLog).where(AuditLog.entity_id == product.id))
        assert log is not None
        assert log.business_id == business.id
        assert log.action == "product.created"