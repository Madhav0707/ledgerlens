from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import Base, Business, InventoryMovement, Payment, Product, Supplier, Purchase
from services.inventory_service import create_product
from services.purchase_service import PurchaseLine, record_purchase, record_supplier_payment


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Purchase Test Shop", currency="INR")
        session.add(business)
        session.flush()
        supplier = Supplier(business_id=business.id, name="Jaipur Distributor")
        session.add(supplier)
        product = create_product(
            session, business_id=business.id, name="Phone", sku="phone-purchase",
            cost_price=Decimal("9000.00"), selling_price=Decimal("12000.00"),
            stock_quantity=0, low_stock_threshold=1,
        )
        session.commit()
        yield session, business.id, supplier.id, product.id


def test_purchase_increases_stock_and_creates_payable(session):
    db, business_id, supplier_id, product_id = session
    purchase = record_purchase(
        db, business_id=business_id, supplier_id=supplier_id,
        lines=[PurchaseLine(product_id, 2, Decimal("10000.00"))],
        amount_paid=Decimal("5000.00"), payment_method="bank transfer", reference="PO-001",
    )
    db.commit()
    assert purchase.total_amount == Decimal("20000.00")
    assert db.get(Product, product_id).stock_quantity == 2
    assert db.get(Product, product_id).cost_price == Decimal("10000.00")
    assert db.scalar(select(Payment.amount).where(Payment.purchase_id == purchase.id)) == Decimal("5000.00")
    assert db.scalar(select(InventoryMovement.quantity_delta).where(InventoryMovement.reason.like("purchase%"))) == 2


def test_supplier_payment_cannot_exceed_payable(session):
    db, business_id, supplier_id, product_id = session
    purchase = record_purchase(
        db, business_id=business_id, supplier_id=supplier_id,
        lines=[PurchaseLine(product_id, 1, Decimal("10000.00"))],
        amount_paid=Decimal("0.00"), payment_method="cash", reference="PO-002",
    )
    with pytest.raises(ValueError, match="outstanding payable"):
        record_supplier_payment(
            db, business_id=business_id, purchase_id=purchase.id,
            amount=Decimal("10001.00"), method="cash",
        )


def test_purchase_rejects_cross_business_supplier(session):
    db, business_id, _, product_id = session
    other = Business(name="Other", currency="INR")
    db.add(other)
    db.flush()
    other_supplier = Supplier(business_id=other.id, name="Other Supplier")
    db.add(other_supplier)
    db.flush()
    with pytest.raises(ValueError, match="Supplier not found"):
        record_purchase(
            db, business_id=business_id, supplier_id=other_supplier.id,
            lines=[PurchaseLine(product_id, 1, Decimal("100.00"))],
            amount_paid=Decimal("0.00"), payment_method="cash",
        )