from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Business, Product


def test_business_owned_product_and_unique_sku():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        business = Business(name="Mehta Electronics", currency="INR")
        session.add(business)
        session.flush()
        session.add(Product(
            business_id=business.id,
            name="Demo Phone",
            sku="PHONE-DEMO-001",
            cost_price=Decimal("10000.00"),
            selling_price=Decimal("12000.00"),
            stock_quantity=3,
            low_stock_threshold=2,
        ))
        session.commit()

        product = session.query(Product).one()
        assert product.business_id == business.id
        assert product.selling_price == Decimal("12000.00")
