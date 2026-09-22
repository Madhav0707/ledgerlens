from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import InventoryMovement, Product, Return, Sale, SaleItem
from services.audit_service import record_audit


def cancel_sale(
    session: Session,
    *,
    business_id: int,
    sale_id: int,
    reason: str,
    user_id: int | None = None,
) -> Sale:
    reason = reason.strip()
    if not reason:
        raise ValueError("A cancellation reason is required.")
    sale = session.scalar(select(Sale).where(Sale.id == sale_id, Sale.business_id == business_id))
    if sale is None:
        raise ValueError("Sale not found in this business.")
    if sale.status != "confirmed":
        raise ValueError("Only confirmed sales can be cancelled.")
    if session.scalar(select(Return.id).where(Return.sale_id == sale.id, Return.status == "confirmed")) is not None:
        raise ValueError("A sale with a confirmed return cannot be cancelled.")

    sale_items = session.scalars(select(SaleItem).where(SaleItem.sale_id == sale.id)).all()
    for item in sale_items:
        product = session.get(Product, item.product_id)
        if product is None:
            raise ValueError("A product on this sale no longer exists.")
        product.stock_quantity += item.quantity
        session.add(InventoryMovement(
            business_id=business_id,
            product_id=product.id,
            quantity_delta=item.quantity,
            reason=f"cancelled sale {sale.id}",
        ))
    sale.status = "cancelled"
    record_audit(
        session, business_id=business_id, user_id=user_id,
        action="sale.cancelled", entity_type="sale", entity_id=sale.id,
        details={"reason": reason, "sale_id": sale.id},
    )
    session.flush()
    return sale