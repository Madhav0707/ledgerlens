from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Business, Product, Supplier
from services.inventory_service import create_product
from services.purchase_service import PurchaseLine, record_purchase
from services.reporting_service import business_report
from services.sales_service import SaleLine, record_sale


def test_report_separates_revenue_collections_payables_and_profit():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Report Shop", currency="INR")
        session.add(business)
        session.flush()
        supplier = Supplier(business_id=business.id, name="Supplier")
        session.add(supplier)
        product = create_product(
            session, business_id=business.id, name="Phone", sku="report-phone",
            cost_price=Decimal("100.00"), selling_price=Decimal("150.00"),
            stock_quantity=2, low_stock_threshold=1,
        )
        sale = record_sale(
            session, business_id=business.id,
            lines=[SaleLine(product.id, 1)], amount_paid=Decimal("100.00"),
            payment_method="cash", reference="REPORT-SALE",
        )
        purchase = record_purchase(
            session, business_id=business.id, supplier_id=supplier.id,
            lines=[PurchaseLine(product.id, 2, Decimal("110.00"))],
            amount_paid=Decimal("100.00"), payment_method="upi", reference="REPORT-PURCHASE",
        )
        session.commit()
        result = business_report(session, business_id=business.id, start_date=date.today(), end_date=date.today())

        assert result["revenue"] == sale.total_amount
        assert result["cash_collected"] == Decimal("100.00")
        assert result["customer_receivables"] == Decimal("50.00")
        assert result["purchases"] == purchase.total_amount
        assert result["supplier_payables"] == Decimal("120.00")
        assert result["gross_profit"] == Decimal("50.00")