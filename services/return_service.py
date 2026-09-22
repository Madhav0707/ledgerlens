from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import InventoryMovement, Product, Refund, Return, ReturnItem, Sale, SaleItem
from services.audit_service import record_audit


def record_sale_return(
    session: Session,
    *,
    business_id: int,
    sale_id: int,
    items: dict[int, int],
    reason: str,
    user_id: int | None = None,
    refund_method: str | None = None,
) -> Return:
    reason = reason.strip()
    if not items or not reason:
        raise ValueError("Return items and a reason are required.")
    if refund_method is not None and refund_method not in {"cash", "upi", "card", "bank transfer", "other"}:
        raise ValueError("Unsupported refund method.")
    if any(quantity <= 0 for quantity in items.values()):
        raise ValueError("Return quantities must be positive.")
    sale = session.scalar(select(Sale).where(Sale.id == sale_id, Sale.business_id == business_id))
    if sale is None or sale.status != "confirmed":
        raise ValueError("Sale not found in this business.")
    sale_items = session.scalars(select(SaleItem).where(SaleItem.sale_id == sale.id)).all()
    item_map = {item.id: item for item in sale_items}
    if set(items) - set(item_map):
        raise ValueError("One or more sale items do not belong to this sale.")

    existing_returns = session.scalars(
        select(ReturnItem).join(Return).where(Return.sale_id == sale.id, Return.status == "confirmed")
    ).all()
    returned_by_item: dict[int, int] = {}
    for returned in existing_returns:
        returned_by_item[returned.sale_item_id] = returned_by_item.get(returned.sale_item_id, 0) + returned.quantity
    for sale_item_id, quantity in items.items():
        if returned_by_item.get(sale_item_id, 0) + quantity > item_map[sale_item_id].quantity:
            raise ValueError("Return quantity exceeds the quantity sold.")

    total = sum(
        (item_map[item_id].unit_price * quantity for item_id, quantity in items.items()),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return_record = Return(
        business_id=business_id, sale_id=sale.id, total_amount=total,
        reason=reason, status="confirmed",
    )
    session.add(return_record)
    session.flush()
    for sale_item_id, quantity in items.items():
        sale_item = item_map[sale_item_id]
        session.add(ReturnItem(
            return_id=return_record.id, sale_item_id=sale_item.id,
            quantity=quantity, unit_price=sale_item.unit_price,
        ))
        session.add(InventoryMovement(
            business_id=business_id, product_id=sale_item.product_id,
            quantity_delta=quantity, reason=f"return {return_record.id}",
        ))
        product = session.get(Product, sale_item.product_id)
        if product is not None:
            product.stock_quantity += quantity
    record_audit(
        session, business_id=business_id, user_id=user_id, action="sale.returned", entity_type="return",
        entity_id=return_record.id, details={"sale_id": sale.id, "total_amount": total, "reason": reason},
    )
    if refund_method is not None:
        session.add(Refund(
            business_id=business_id, return_id=return_record.id,
            amount=total, method=refund_method,
        ))
        record_audit(
            session, business_id=business_id, user_id=user_id,
            action="refund.recorded", entity_type="refund", entity_id=return_record.id,
            details={"amount": total, "method": refund_method},
        )
    session.flush()
    return return_record