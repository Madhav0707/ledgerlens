from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Business, Product
from services.cancellation_service import cancel_sale
from services.inventory_service import create_product
from services.sales_service import SaleLine, record_sale


def test_cancel_sale_restores_stock_and_records_status():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Cancel Shop", currency="INR")
        session.add(business)
        session.flush()
        product = create_product(
            session, business_id=business.id, name="Phone", sku="CANCEL-1",
            cost_price=Decimal("100"), selling_price=Decimal("150"),
            stock_quantity=2, low_stock_threshold=1,
        )
        sale = record_sale(
            session, business_id=business.id, lines=[SaleLine(product.id, 1)],
            amount_paid=Decimal("0"), payment_method="cash", reference="CANCEL-SALE",
        )
        session.commit()
        cancel_sale(session, business_id=business.id, sale_id=sale.id, reason="Duplicate entry", user_id=7)
        session.commit()
        assert session.get(Product, product.id).stock_quantity == 2
        assert session.get(type(sale), sale.id).status == "cancelled"


def test_cancelled_sale_cannot_be_cancelled_again():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Cancel Shop", currency="INR")
        session.add(business)
        session.flush()
        product = create_product(
            session, business_id=business.id, name="Cable", sku="CANCEL-2",
            cost_price=Decimal("10"), selling_price=Decimal("15"),
            stock_quantity=1, low_stock_threshold=1,
        )
        sale = record_sale(
            session, business_id=business.id, lines=[SaleLine(product.id, 1)],
            amount_paid=Decimal("0"), payment_method="cash", reference="CANCEL-SALE-2",
        )
        session.commit()
        cancel_sale(session, business_id=business.id, sale_id=sale.id, reason="Correction")
        with pytest.raises(ValueError, match="Only confirmed"):
            cancel_sale(session, business_id=business.id, sale_id=sale.id, reason="Again")