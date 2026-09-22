from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Business, InventoryMovement
from services.inventory_service import adjust_stock, create_product


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Test Shop", currency="INR")
        session.add(business)
        session.flush()
        yield session, business.id


def test_create_product_records_opening_stock(session):
    db, business_id = session
    product = create_product(
        db, business_id=business_id, name="Phone", sku="phone-1",
        cost_price=Decimal("10000.00"), selling_price=Decimal("12000.00"),
        stock_quantity=3, low_stock_threshold=1,
    )
    db.commit()
    assert product.sku == "PHONE-1"
    assert product.stock_quantity == 3
    assert db.query(InventoryMovement).one().quantity_delta == 3


def test_stock_cannot_become_negative(session):
    db, business_id = session
    product = create_product(
        db, business_id=business_id, name="Cable", sku="cable-1",
        cost_price=Decimal("100.00"), selling_price=Decimal("200.00"),
        stock_quantity=1, low_stock_threshold=1,
    )
    with pytest.raises(ValueError, match="negative"):
        adjust_stock(db, business_id=business_id, product_id=product.id, quantity_delta=-2, reason="sale")


def test_duplicate_sku_is_rejected_within_business(session):
    db, business_id = session
    values = dict(
        business_id=business_id, name="Adapter", sku="adapter-1",
        cost_price=Decimal("100.00"), selling_price=Decimal("200.00"),
        stock_quantity=0, low_stock_threshold=1,
    )
    create_product(db, **values)
    with pytest.raises(ValueError, match="SKU"):
        create_product(db, **values)


def test_stock_adjustment_cannot_cross_business_boundary(session):
    db, business_id = session
    other_business = Business(name="Other Shop", currency="INR")
    db.add(other_business)
    db.flush()
    product = create_product(
        db, business_id=business_id, name="Mouse", sku="mouse-1",
        cost_price=Decimal("100.00"), selling_price=Decimal("200.00"),
        stock_quantity=2, low_stock_threshold=1,
    )
    with pytest.raises(ValueError, match="not found"):
        adjust_stock(
            db, business_id=other_business.id, product_id=product.id,
            quantity_delta=1, reason="unauthorized adjustment",
        )