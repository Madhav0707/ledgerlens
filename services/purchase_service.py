from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import InventoryMovement, Payment, Product, Purchase, PurchaseItem, Supplier
from services.audit_service import record_audit

MONEY = Decimal("0.01")
PAYMENT_METHODS = {"cash", "upi", "card", "bank transfer", "other"}


@dataclass(frozen=True)
class PurchaseLine:
    product_id: int
    quantity: int
    unit_cost: Decimal


def record_purchase(
    session: Session,
    *,
    business_id: int,
    lines: list[PurchaseLine],
    amount_paid: Decimal,
    payment_method: str,
    supplier_id: int | None = None,
    reference: str | None = None,
    user_id: int | None = None,
) -> Purchase:
    if not lines:
        raise ValueError("A purchase must contain at least one product.")
    if any(line.quantity <= 0 for line in lines):
        raise ValueError("Purchase quantities must be positive.")
    if any(line.unit_cost < 0 for line in lines) or amount_paid < 0:
        raise ValueError("Purchase costs and payment cannot be negative.")
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Unsupported payment method.")
    if supplier_id is not None and session.scalar(
        select(Supplier.id).where(Supplier.id == supplier_id, Supplier.business_id == business_id)
    ) is None:
        raise ValueError("Supplier not found in this business.")

    product_ids = {line.product_id for line in lines}
    products = session.scalars(
        select(Product).where(Product.business_id == business_id, Product.id.in_(product_ids))
    ).all()
    product_map = {product.id: product for product in products}
    if len(product_map) != len(product_ids):
        raise ValueError("One or more products were not found in this business.")

    total = sum((line.unit_cost * line.quantity for line in lines), Decimal("0.00")).quantize(
        MONEY, rounding=ROUND_HALF_UP
    )
    amount_paid = amount_paid.quantize(MONEY, rounding=ROUND_HALF_UP)
    if amount_paid > total:
        raise ValueError("Payment cannot exceed the purchase total.")

    purchase = Purchase(
        business_id=business_id,
        supplier_id=supplier_id,
        reference=reference.strip() if reference else None,
        total_amount=total,
        status="confirmed",
    )
    session.add(purchase)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ValueError("That purchase reference has already been used.") from error

    for line in lines:
        product = product_map[line.product_id]
        old_stock = product.stock_quantity
        new_stock = old_stock + line.quantity
        if new_stock:
            product.cost_price = (
                (product.cost_price * old_stock + line.unit_cost * line.quantity) / new_stock
            ).quantize(MONEY, rounding=ROUND_HALF_UP)
        product.stock_quantity = new_stock
        session.add(PurchaseItem(
            purchase_id=purchase.id,
            product_id=product.id,
            quantity=line.quantity,
            unit_cost=line.unit_cost,
        ))
        session.add(InventoryMovement(
            business_id=business_id,
            product_id=product.id,
            quantity_delta=line.quantity,
            reason=f"purchase {purchase.id}",
        ))
    if amount_paid:
        session.add(Payment(
            business_id=business_id,
            purchase_id=purchase.id,
            amount=amount_paid,
            method=payment_method,
        ))
    record_audit(
        session, business_id=business_id, action="purchase.confirmed", entity_type="purchase",
        entity_id=purchase.id, details={"total_amount": total, "amount_paid": amount_paid},
        user_id=user_id,
    )
    session.flush()
    return purchase


def record_supplier_payment(
    session: Session,
    *,
    business_id: int,
    purchase_id: int,
    amount: Decimal,
    method: str,
    user_id: int | None = None,
) -> Payment:
    if amount <= 0:
        raise ValueError("Payment must be greater than zero.")
    if method not in PAYMENT_METHODS:
        raise ValueError("Unsupported payment method.")
    purchase = session.scalar(
        select(Purchase).where(Purchase.id == purchase_id, Purchase.business_id == business_id)
    )
    if purchase is None or purchase.status != "confirmed":
        raise ValueError("Purchase not found in this business.")
    payments = session.scalars(select(Payment).where(Payment.purchase_id == purchase.id)).all()
    paid = sum((payment.amount for payment in payments), Decimal("0.00"))
    if paid + amount > purchase.total_amount:
        raise ValueError("Payment cannot exceed the outstanding payable.")
    payment = Payment(
        business_id=business_id,
        purchase_id=purchase.id,
        amount=amount.quantize(MONEY, rounding=ROUND_HALF_UP),
        method=method,
    )
    session.add(payment)
    record_audit(
        session, business_id=business_id, action="supplier_payment.recorded", entity_type="payment",
        entity_id=payment.id, details={"purchase_id": purchase.id, "amount": amount, "method": method},
        user_id=user_id,
    )
    session.flush()
    return payment