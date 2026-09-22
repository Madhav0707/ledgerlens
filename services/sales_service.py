from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import Customer, InventoryMovement, Payment, Product, Sale, SaleItem
from services.audit_service import record_audit

MONEY = Decimal("0.01")
PAYMENT_METHODS = {"cash", "upi", "card", "bank transfer", "other"}


@dataclass(frozen=True)
class SaleLine:
    product_id: int
    quantity: int


def record_sale(
    session: Session,
    *,
    business_id: int,
    lines: list[SaleLine],
    amount_paid: Decimal,
    payment_method: str,
    customer_id: int | None = None,
    discount: Decimal = Decimal("0.00"),
    reference: str | None = None,
    user_id: int | None = None,
) -> Sale:
    if not lines:
        raise ValueError("A sale must contain at least one product.")
    if any(line.quantity <= 0 for line in lines):
        raise ValueError("Sale quantities must be positive.")
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Unsupported payment method.")
    if amount_paid < 0 or discount < 0:
        raise ValueError("Payment and discount cannot be negative.")
    if reference is not None and not reference.strip():
        raise ValueError("Sale reference cannot be blank.")

    quantities: dict[int, int] = {}
    for line in lines:
        quantities[line.product_id] = quantities.get(line.product_id, 0) + line.quantity

    products = session.scalars(
        select(Product).where(Product.business_id == business_id, Product.id.in_(quantities.keys()))
    ).all()
    product_map = {product.id: product for product in products}
    if len(product_map) != len(quantities):
        raise ValueError("One or more products were not found in this business.")
    for product_id, quantity in quantities.items():
        if product_map[product_id].stock_quantity < quantity:
            raise ValueError(f"Insufficient stock for {product_map[product_id].name}.")

    if customer_id is not None and session.scalar(
        select(Customer.id).where(Customer.id == customer_id, Customer.business_id == business_id)
    ) is None:
        raise ValueError("Customer not found in this business.")

    subtotal = sum(
        (product_map[line.product_id].selling_price * line.quantity for line in lines),
        Decimal("0.00"),
    )
    total = (subtotal - discount).quantize(MONEY, rounding=ROUND_HALF_UP)
    if total < 0:
        raise ValueError("Discount cannot exceed the sale subtotal.")
    amount_paid = amount_paid.quantize(MONEY, rounding=ROUND_HALF_UP)
    if amount_paid > total:
        raise ValueError("Payment cannot exceed the sale total.")

    sale = Sale(
        business_id=business_id,
        customer_id=customer_id,
        reference=reference.strip() if reference else None,
        total_amount=total,
        status="confirmed",
    )
    session.add(sale)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ValueError("That sale reference has already been used.") from error

    for line in lines:
        product = product_map[line.product_id]
        product.stock_quantity -= line.quantity
        session.add(SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=line.quantity,
            unit_price=product.selling_price,
            unit_cost=product.cost_price,
        ))
        session.add(InventoryMovement(
            business_id=business_id,
            product_id=product.id,
            quantity_delta=-line.quantity,
            reason=f"sale {sale.id}",
        ))
    if amount_paid:
        session.add(Payment(
            business_id=business_id,
            sale_id=sale.id,
            amount=amount_paid,
            method=payment_method,
        ))
    record_audit(
        session, business_id=business_id, action="sale.confirmed", entity_type="sale",
        entity_id=sale.id, details={"total_amount": total, "amount_paid": amount_paid},
        user_id=user_id,
    )
    session.flush()
    return sale


def record_payment(
    session: Session,
    *,
    business_id: int,
    sale_id: int,
    amount: Decimal,
    method: str,
    user_id: int | None = None,
) -> Payment:
    if amount <= 0:
        raise ValueError("Payment must be greater than zero.")
    if method not in PAYMENT_METHODS:
        raise ValueError("Unsupported payment method.")
    sale = session.scalar(select(Sale).where(Sale.id == sale_id, Sale.business_id == business_id))
    if sale is None or sale.status != "confirmed":
        raise ValueError("Sale not found in this business.")
    total_paid = sum(
        (payment.amount for payment in session.scalars(select(Payment).where(Payment.sale_id == sale.id)).all()),
        Decimal("0.00"),
    )
    if total_paid + amount > sale.total_amount:
        raise ValueError("Payment cannot exceed the outstanding balance.")
    payment = Payment(business_id=business_id, sale_id=sale.id, amount=amount, method=method)
    session.add(payment)
    record_audit(
        session, business_id=business_id, action="customer_payment.recorded", entity_type="payment",
        entity_id=payment.id, details={"sale_id": sale.id, "amount": amount, "method": method},
        user_id=user_id,
    )
    session.flush()
    return payment