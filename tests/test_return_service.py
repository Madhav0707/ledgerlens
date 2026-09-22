from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import AuditLog, Base, Business, Product, Refund, SaleItem, User
from services.inventory_service import create_product
from services.return_service import record_sale_return
from services.sales_service import SaleLine, record_sale


def test_return_restores_stock_and_cannot_exceed_sold_quantity():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Return Shop", currency="INR")
        session.add(business)
        session.flush()
        product = create_product(
            session, business_id=business.id, name="Phone", sku="RETURN-1",
            cost_price=Decimal("100"), selling_price=Decimal("150"),
            stock_quantity=2, low_stock_threshold=1,
        )
        sale = record_sale(
            session, business_id=business.id, lines=[SaleLine(product.id, 1)],
            amount_paid=Decimal("150"), payment_method="cash", reference="RETURN-SALE",
        )
        session.commit()
        sale_item_id = session.query(SaleItem).one().id
        returned = record_sale_return(
            session, business_id=business.id, sale_id=sale.id,
            items={sale_item_id: 1}, reason="Customer return", user_id=42, refund_method="cash",
        )
        session.commit()
        assert returned.total_amount == Decimal("150.00")
        assert session.get(Product, product.id).stock_quantity == 2
        assert session.query(Refund).one().amount == Decimal("150.00")
        assert session.query(AuditLog).filter_by(action="refund.recorded", user_id=42).one()
        with pytest.raises(ValueError, match="exceeds"):
            record_sale_return(
                session, business_id=business.id, sale_id=sale.id,
                items={sale_item_id: 1}, reason="Duplicate return",
            )