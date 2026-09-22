import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Business, BusinessMembership, User
from security.authorization import require_role


def test_employee_cannot_use_owner_only_operation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Auth Shop", currency="INR")
        employee = User(email="employee@example.com", password_hash="hash", full_name="Employee")
        session.add_all([business, employee])
        session.flush()
        session.add(BusinessMembership(business_id=business.id, user_id=employee.id, role="employee"))
        session.commit()
        with pytest.raises(PermissionError):
            require_role(
                session, user_id=employee.id, business_id=business.id, allowed_roles={"owner"}
            )


def test_owner_can_use_owner_only_operation():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Auth Shop", currency="INR")
        owner = User(email="owner@example.com", password_hash="hash", full_name="Owner")
        session.add_all([business, owner])
        session.flush()
        session.add(BusinessMembership(business_id=business.id, user_id=owner.id, role="owner"))
        session.commit()
        require_role(session, user_id=owner.id, business_id=business.id, allowed_roles={"owner"})