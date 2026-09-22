from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import Base, Business, Customer, InventoryMovement, Payment, Product, Sale, SaleItem
from services.inventory_service import create_product
from services.sales_service import SaleLine, record_payment, record_sale


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Sales Test Shop", currency="INR")
        customer = Customer(business_id=1, name="Asha")
        session.add(business)
        session.flush()
        customer.business_id = business.id
        session.add(customer)
        product = create_product(
            session, business_id=business.id, name="Phone", sku="phone-sale",
            cost_price=Decimal("10000.00"), selling_price=Decimal("12000.00"),
            stock_quantity=2, low_stock_threshold=1,
        )
        session.commit()
        yield session, business.id, customer.id, product.id


def test_sale_is_atomic_and_supports_partial_payment(session):
    db, business_id, customer_id, product_id = session
    sale = record_sale(
        db, business_id=business_id, customer_id=customer_id,
        lines=[SaleLine(product_id, 1)], amount_paid=Decimal("5000.00"),
        payment_method="upi", reference="INV-001",
    )
    db.commit()

    assert sale.total_amount == Decimal("12000.00")
    assert db.get(Product, product_id).stock_quantity == 1
    assert db.scalar(select(Payment.amount).where(Payment.sale_id == sale.id)) == Decimal("5000.00")
    assert db.scalar(select(SaleItem.quantity).where(SaleItem.sale_id == sale.id)) == 1

    record_payment(db, business_id=business_id, sale_id=sale.id, amount=Decimal("7000.00"), method="cash")
    db.commit()
    payments = db.scalars(select(Payment).where(Payment.sale_id == sale.id)).all()
    assert sum((payment.amount for payment in payments), Decimal("0.00")) == Decimal("12000.00")


def test_out_of_stock_sale_changes_nothing(session):
    db, business_id, customer_id, product_id = session
    with pytest.raises(ValueError, match="Insufficient stock"):
        record_sale(
            db, business_id=business_id, customer_id=customer_id,
            lines=[SaleLine(product_id, 3)], amount_paid=Decimal("0.00"),
            payment_method="cash", reference="INV-002",
        )
    db.rollback()
    assert db.scalar(select(Sale.id)) is None
    assert db.get(Product, product_id).stock_quantity == 2
    assert db.scalar(select(InventoryMovement.id).where(InventoryMovement.reason.like("sale%"))) is None


def test_payment_cannot_exceed_outstanding_balance(session):
    db, business_id, customer_id, product_id = session
    sale = record_sale(
        db, business_id=business_id, customer_id=customer_id,
        lines=[SaleLine(product_id, 1)], amount_paid=Decimal("10000.00"),
        payment_method="cash", reference="INV-003",
    )
    with pytest.raises(ValueError, match="outstanding"):
        record_payment(db, business_id=business_id, sale_id=sale.id, amount=Decimal("3000.00"), method="cash")


def test_sale_reference_prevents_duplicate_submission(session):
    db, business_id, customer_id, product_id = session
    record_sale(
        db, business_id=business_id, customer_id=customer_id,
        lines=[SaleLine(product_id, 1)], amount_paid=Decimal("0.00"),
        payment_method="cash", reference="INV-DUPLICATE",
    )
    db.commit()
    with pytest.raises(ValueError, match="already been used"):
        record_sale(
            db, business_id=business_id, customer_id=customer_id,
            lines=[SaleLine(product_id, 1)], amount_paid=Decimal("0.00"),
            payment_method="cash", reference="INV-DUPLICATE",
        )