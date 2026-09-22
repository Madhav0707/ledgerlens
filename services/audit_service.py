import json

from sqlalchemy.orm import Session

from database.models import AuditLog


def record_audit(
    session: Session,
    *,
    business_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    user_id: int | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        business_id=business_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details, default=str) if details else None,
    )
    session.add(entry)
    session.flush()
    return entry