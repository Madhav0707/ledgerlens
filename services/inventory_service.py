from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import InventoryMovement, Product
from services.audit_service import record_audit


def create_product(
    session: Session,
    *,
    business_id: int,
    name: str,
    sku: str,
    cost_price: Decimal,
    selling_price: Decimal,
    stock_quantity: int,
    low_stock_threshold: int,
    user_id: int | None = None,
) -> Product:
    name = name.strip()
    sku = sku.strip().upper()
    if not name or not sku:
        raise ValueError("Product name and SKU are required.")
    if cost_price < 0 or selling_price < 0:
        raise ValueError("Prices cannot be negative.")
    if stock_quantity < 0:
        raise ValueError("Opening stock cannot be negative.")
    if low_stock_threshold < 0:
        raise ValueError("Low-stock threshold cannot be negative.")

    product = Product(
        business_id=business_id,
        name=name,
        sku=sku,
        cost_price=cost_price,
        selling_price=selling_price,
        stock_quantity=stock_quantity,
        low_stock_threshold=low_stock_threshold,
    )
    session.add(product)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ValueError("That SKU already exists in this business.") from error

    if stock_quantity:
        session.add(InventoryMovement(
            business_id=business_id,
            product_id=product.id,
            quantity_delta=stock_quantity,
            reason="opening stock",
        ))
    record_audit(
        session, business_id=business_id, action="product.created", entity_type="product",
        entity_id=product.id, details={"sku": product.sku, "opening_stock": stock_quantity},
        user_id=user_id,
    )
    return product


def adjust_stock(
    session: Session,
    *,
    business_id: int,
    product_id: int,
    quantity_delta: int,
    reason: str,
    user_id: int | None = None,
) -> Product:
    reason = reason.strip()
    if quantity_delta == 0:
        raise ValueError("Stock adjustment cannot be zero.")
    if not reason:
        raise ValueError("A reason is required for every stock adjustment.")

    product = session.scalar(
        select(Product).where(Product.id == product_id, Product.business_id == business_id)
    )
    if product is None:
        raise ValueError("Product not found in this business.")
    if product.stock_quantity + quantity_delta < 0:
        raise ValueError("Stock cannot become negative.")

    product.stock_quantity += quantity_delta
    session.add(InventoryMovement(
        business_id=business_id,
        product_id=product.id,
        quantity_delta=quantity_delta,
        reason=reason,
    ))
    session.flush()
    record_audit(
        session, business_id=business_id, action="stock.adjusted", entity_type="product",
        entity_id=product.id, details={"quantity_delta": quantity_delta, "reason": reason},
        user_id=user_id,
    )
    return product