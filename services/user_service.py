from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import BusinessMembership, User
from security.authentication import hash_password


def create_employee(
    session: Session,
    *,
    business_id: int,
    full_name: str,
    email: str,
    password: str,
) -> User:
    if not full_name.strip() or not email.strip():
        raise ValueError("Employee name and email are required.")
    if len(password) < 8:
        raise ValueError("Employee password must contain at least 8 characters.")
    normalized_email = email.strip().lower()
    if session.scalar(select(User.id).where(User.email == normalized_email)) is not None:
        raise ValueError("That email is already registered.")
    user = User(
        full_name=full_name.strip(), email=normalized_email,
        password_hash=hash_password(password), is_active=True,
    )
    session.add(user)
    session.flush()
    session.add(BusinessMembership(business_id=business_id, user_id=user.id, role="employee"))
    session.flush()
    return user