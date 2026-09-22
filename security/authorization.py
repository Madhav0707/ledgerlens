from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import BusinessMembership


def get_membership(session: Session, *, user_id: int, business_id: int) -> BusinessMembership | None:
    return session.scalar(
        select(BusinessMembership).where(
            BusinessMembership.user_id == user_id,
            BusinessMembership.business_id == business_id,
        )
    )


def require_role(session: Session, *, user_id: int, business_id: int, allowed_roles: set[str]) -> None:
    membership = get_membership(session, user_id=user_id, business_id=business_id)
    if membership is None or membership.role not in allowed_roles:
        raise PermissionError("You are not authorized for this operation.")