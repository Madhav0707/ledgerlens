from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import Payment, Product, Purchase, Sale, SaleItem


def _bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    if end_date < start_date:
        raise ValueError("End date cannot be before start date.")
    return datetime.combine(start_date, time.min), datetime.combine(end_date + timedelta(days=1), time.min)


def business_report(session: Session, *, business_id: int, start_date: date, end_date: date) -> dict:
    start, end = _bounds(start_date, end_date)
    sales = session.scalars(
        select(Sale).where(
            Sale.business_id == business_id,
            Sale.status == "confirmed",
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    ).all()
    purchases = session.scalars(
        select(Purchase).where(
            Purchase.business_id == business_id,
            Purchase.status == "confirmed",
            Purchase.created_at >= start,
            Purchase.created_at < end,
        )
    ).all()
    sale_ids = [sale.id for sale in sales]
    purchase_ids = [purchase.id for purchase in purchases]
    sale_payments = session.scalars(
        select(Payment).where(Payment.business_id == business_id, Payment.sale_id.in_(sale_ids))
    ).all() if sale_ids else []
    purchase_payments = session.scalars(
        select(Payment).where(Payment.business_id == business_id, Payment.purchase_id.in_(purchase_ids))
    ).all() if purchase_ids else []

    revenue = sum((sale.total_amount for sale in sales), Decimal("0.00"))
    collected = sum((payment.amount for payment in sale_payments), Decimal("0.00"))
    purchases_total = sum((purchase.total_amount for purchase in purchases), Decimal("0.00"))
    supplier_paid = sum((payment.amount for payment in purchase_payments), Decimal("0.00"))
    sale_items = session.scalars(select(SaleItem).where(SaleItem.sale_id.in_(sale_ids))).all() if sale_ids else []
    missing_cost = any(item.unit_cost is None for item in sale_items)
    gross_profit = None if missing_cost else sum(
        ((item.unit_price - item.unit_cost) * item.quantity for item in sale_items),
        Decimal("0.00"),
    )
    payment_breakdown: dict[str, Decimal] = {}
    for payment in sale_payments:
        payment_breakdown[payment.method] = payment_breakdown.get(payment.method, Decimal("0.00")) + payment.amount
    inventory_value = session.scalar(
        select(func.coalesce(func.sum(Product.stock_quantity * Product.cost_price), 0)).where(
            Product.business_id == business_id
        )
    ) or Decimal("0.00")
    return {
        "revenue": revenue,
        "cash_collected": collected,
        "customer_receivables": revenue - collected,
        "purchases": purchases_total,
        "supplier_paid": supplier_paid,
        "supplier_payables": purchases_total - supplier_paid,
        "gross_profit": gross_profit,
        "gross_profit_available": not missing_cost,
        "inventory_value": Decimal(str(inventory_value)),
        "payment_breakdown": payment_breakdown,
        "sales_count": len(sales),
        "purchase_count": len(purchases),
    }