import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import Base, Business, BusinessMembership
from services.user_service import create_employee


def test_owner_can_create_employee_membership():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Staff Shop", currency="INR")
        session.add(business)
        session.flush()
        employee = create_employee(
            session, business_id=business.id, full_name="Shop Employee",
            email="staff@example.com", password="Password123",
        )
        session.commit()
        membership = session.query(BusinessMembership).one()
        assert employee.is_active
        assert membership.role == "employee"


def test_employee_password_is_validated():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        business = Business(name="Staff Shop", currency="INR")
        session.add(business)
        session.flush()
        with pytest.raises(ValueError, match="8 characters"):
            create_employee(
                session, business_id=business.id, full_name="Staff",
                email="staff@example.com", password="short",
            )